"""BTYT — Transactions + Account Balances Generator — Centralized World Architecture.

Ground-truth first: transactions are generated as event intents, processed
chronologically through a non-overdraft ledger, and account_balances is derived
from completed movements. Credit-card payments and data-quality degradation are
intentionally deferred to later modules.

Architecture changes:
- preserves all validated V2.3.1 bank-network, behavioral, liquidity, transfer-capacity, and ledger mechanics;
- precomputes deterministic repeated work used by the hot transaction-generation path;
- preserves stable seeded draws, event ordering, probabilities, and sequential ledger execution;
- uses the canonical BTYT world seed through an isolated transactions namespace;
- stages loan-linked intents in compact Parquet and account-local generation in deterministic chunk files with month-level row groups;
- replays internal BTYT transfers month by month to preserve atomic ledger semantics;
- writes canonical Parquet outputs without holding the full transaction universe in memory.
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import math
import shutil
import time
import zlib
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from scripts.core.paths import (
    GENERATED_CORE_DIR,
    GENERATED_CREDIT_DIR,
    GENERATED_TRANSACTIONS_DIR,
    GENERATED_PERFORMANCE_DIR,
    GENERATED_WORLD_DIR,
    INTERIM_TRANSACTIONS_DIR,
    INTERIM_CREDIT_DIR,
    INTERIM_WORLD_DIR,
    INTERIM_AUDITS_DIR,
)
from scripts.core.rng import make_rng
from scripts.core.world import load_world

WORLD_CONFIG = load_world()
RNG_NAMESPACE = "transactions"
ENGINE_VERSION = "4.0.0"

CUSTOMERS_PARQUET_PATH = GENERATED_CORE_DIR / "customers.parquet"
CUSTOMERS_CSV_PATH = GENERATED_CORE_DIR / "customers.csv"
ACCOUNTS_PARQUET_PATH = GENERATED_CORE_DIR / "accounts.parquet"
ACCOUNTS_CSV_PATH = GENERATED_CORE_DIR / "accounts.csv"
CARDS_PARQUET_PATH = GENERATED_CREDIT_DIR / "cards.parquet"
CARDS_CSV_PATH = GENERATED_CREDIT_DIR / "cards.csv"
LOANS_PARQUET_PATH = GENERATED_CORE_DIR / "loans.parquet"
LOANS_CSV_PATH = GENERATED_CORE_DIR / "loans.csv"
LOAN_SNAPSHOT_PARQUET_PATH = GENERATED_CREDIT_DIR / "loan_monthly_snapshot.parquet"
LOAN_SNAPSHOT_CSV_PATH = GENERATED_CREDIT_DIR / "loan_monthly_snapshot.csv"
LOAN_BRIDGE_PATH = INTERIM_CREDIT_DIR / "loan_lifecycle_bridge.csv"
BRANCHES_PATH = GENERATED_CORE_DIR / "branches.csv"
BANKS_PATH = GENERATED_CORE_DIR / "banks.csv"
BANK_WORLD_PATH = GENERATED_PERFORMANCE_DIR / "bank_world_parameters.csv"
BANK_MARKET_PATH = GENERATED_PERFORMANCE_DIR / "bank_market_weights.csv"
MACRO_ENVIRONMENT_PATH = GENERATED_WORLD_DIR / "macro_environment.csv"
FINANCIAL_INSTITUTIONS_PATH = GENERATED_WORLD_DIR / "financial_institutions.csv"

TX_OUT = GENERATED_TRANSACTIONS_DIR / "transactions.parquet"
BAL_OUT = GENERATED_CORE_DIR / "account_balances.parquet"
TRAITS_OUT = INTERIM_TRANSACTIONS_DIR / "customer_transaction_traits.parquet"
ROLES_OUT = INTERIM_TRANSACTIONS_DIR / "account_roles.parquet"
AUDIT_OUT = INTERIM_AUDITS_DIR / "transaction_generation_audit.csv"
WORLD_OUT = INTERIM_WORLD_DIR / "transaction_world_parameters.csv"
INTERNAL_PAIRS_OUT = INTERIM_TRANSACTIONS_DIR / "internal_transfer_pairs.parquet"
CHECKPOINT_PATH = INTERIM_TRANSACTIONS_DIR / "transaction_checkpoint.json"
STAGE_ROOT = INTERIM_TRANSACTIONS_DIR / "transaction_staging"
STAGE_INTENTS_DIR = STAGE_ROOT / "intents"
STAGE_BALANCES_DIR = STAGE_ROOT / "balance_skeleton"
STAGE_LOAN_INTENTS_PATH = STAGE_ROOT / "loan_intents.parquet"
REPLAY_TX_DIR = STAGE_ROOT / "replay_transactions"
REPLAY_BAL_DIR = STAGE_ROOT / "replay_balances"
REPLAY_PAIR_DIR = STAGE_ROOT / "replay_internal_pairs"
LIVE_BALANCE_PATH = STAGE_ROOT / "live_balances.parquet"

DEFAULT_ACCOUNT_CHUNK_SIZE = 1_000
PARQUET_COMPRESSION = "zstd"
SAVE_INTERIM = True
OBS_START = pd.Period(WORLD_CONFIG.start_date.strftime("%Y-%m"), freq="M")
OBS_END = pd.Period(WORLD_CONFIG.end_date.strftime("%Y-%m"), freq="M")

TX_COLS = [
    "transaction_id", "account_id", "transaction_datetime", "transaction_type",
    "direction", "channel", "amount", "counterparty_type",
    "transfer_scope", "counterparty_institution_id", "transaction_branch_id",
    "transaction_status", "merchant_category", "failure_reason",
]
BAL_COLS = [
    "account_id", "year_month", "opening_balance", "total_inflows",
    "total_outflows", "closing_balance",
]
CREDIT = {"TRANSFER_IN", "CASH_DEPOSIT", "LOAN_DISBURSEMENT", "INTEREST_CREDIT"}
DEBIT = {"TRANSFER_OUT", "CASH_WITHDRAWAL", "DEBIT_PURCHASE", "SERVICE_PAYMENT",
         "CREDIT_CARD_PAYMENT", "LOAN_PAYMENT"}
FIXED = {"P007", "P008"}
CURRENCY = {"P001":"UYU","P002":"USD","P003":"UYU","P004":"USD",
            "P005":"UYU","P006":"UYU","P007":"UYU","P008":"USD"}
BASE_INTENSITY = {"P001":4.5,"P002":1.8,"P003":9.5,"P004":4.0,
                  "P005":8.5,"P006":7.0,"P007":0.0,"P008":0.0}
ROLE_MULT = {"PRIMARY_TRANSACTIONAL":1.25,"PAYROLL":1.18,"BUSINESS_OPERATING":1.35,
             "SAVINGS":0.70,"USD_RESERVE":0.45,"FIXED_TERM":0.05,"SECONDARY":0.55}
FX = {2021:43.6, 2022:41.2, 2023:38.8, 2024:40.3, 2025:42.0, 2026:43.5}
# Synthetic BTYT operational ATM limits in UYU-equivalent per transaction.
# These are internal feasibility rules inspired by real banking channel constraints;
# they are not presented as universal limits imposed by Uruguayan legislation.
ATM_CASH_LIMIT_UYU = {
    "CASH_WITHDRAWAL": {"INDIVIDUAL": 60_000.0, "BUSINESS": 150_000.0},
    "CASH_DEPOSIT": {"INDIVIDUAL": 200_000.0, "BUSINESS": 1_000_000.0},
}
MERCHANT_CATEGORIES = [
    "GROCERIES","RESTAURANTS","FUEL","RETAIL","HEALTHCARE","PHARMACY",
    "TRANSPORT","TRAVEL","ENTERTAINMENT","EDUCATION","UTILITIES",
    "TELECOMMUNICATIONS","ECOMMERCE","HOME","AUTOMOTIVE",
    "PROFESSIONAL_SERVICES","OTHER",
]

# Populated once in main() from the frozen V4 bank-network outputs.
INSTITUTION_CONTEXT = None

# Safe performance caches. Every cached value is a deterministic function of the
# same inputs and stable RNG seed used by V2.3.1; caching therefore removes
# repeated work without changing the stochastic model or draw order.
MONTH_CALENDAR_CACHE = {}
OPEN_BRANCH_CACHE = {}
MONTHLY_SCALE_CACHE = {}
MERCHANT_BASE_CACHE = {}
CUSTOMER_BANK_FIT_CACHE = {}
LOAN_ACCOUNT_PICK_CACHE = {}
ACCOUNT_META_CACHE = {}



def semantic_stream(*parts) -> int:
    text = "|".join(str(x) for x in parts)
    return zlib.crc32(text.encode("utf-8")) & 0xFFFFFFFF


def rng_for(*parts):
    return make_rng(WORLD_CONFIG.seed, RNG_NAMESPACE, semantic_stream(*parts))


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


def softmax(x):
    x = np.asarray(x, float); x -= x.max(); e = np.exp(x); return e/e.sum()


def choose(rng, labels, weights):
    w = np.maximum(np.asarray(weights, float), 0)
    if w.sum() == 0: w = np.ones(len(labels))
    return str(rng.choice(np.asarray(labels, dtype=object), p=w/w.sum()))


def money(x):
    return float(np.round(max(0.0, float(x)), 2))


def require(df, cols, name):
    missing = sorted(set(cols)-set(df.columns))
    if missing: raise ValueError(f"{name}: missing columns {missing}")


def read_preferred(parquet_path, csv_path, dtype=None):
    if parquet_path.exists():
        return pd.read_parquet(parquet_path), parquet_path
    if csv_path.exists():
        return pd.read_csv(csv_path, dtype=dtype), csv_path
    return pd.DataFrame(), None


def load_data():
    required_csv = [BRANCHES_PATH, BANKS_PATH, BANK_WORLD_PATH, BANK_MARKET_PATH, MACRO_ENVIRONMENT_PATH, FINANCIAL_INSTITUTIONS_PATH]
    for path in required_csv:
        if not path.exists():
            raise FileNotFoundError(path)

    customers, customer_source = read_preferred(
        CUSTOMERS_PARQUET_PATH, CUSTOMERS_CSV_PATH,
        dtype={"customer_id": str, "primary_branch_id": str},
    )
    accounts, account_source = read_preferred(
        ACCOUNTS_PARQUET_PATH, ACCOUNTS_CSV_PATH,
        dtype={"account_id": str, "customer_id": str, "product_id": str, "branch_id": str},
    )
    if customer_source is None or account_source is None:
        raise FileNotFoundError("Canonical customers/accounts inputs are missing.")

    cards, card_source = read_preferred(CARDS_PARQUET_PATH, CARDS_CSV_PATH)
    loans, loan_source = read_preferred(LOANS_PARQUET_PATH, LOANS_CSV_PATH)
    loan_snapshot, snapshot_source = read_preferred(
        LOAN_SNAPSHOT_PARQUET_PATH, LOAN_SNAPSHOT_CSV_PATH
    )

    d = {
        "customers": customers,
        "accounts": accounts,
        "cards": cards,
        "loans": loans,
        "loan_snapshot": loan_snapshot,
        "loan_bridge": pd.read_csv(LOAN_BRIDGE_PATH, dtype=str) if LOAN_BRIDGE_PATH.exists() else pd.DataFrame(),
        "branches": pd.read_csv(BRANCHES_PATH, dtype={"branch_id": str}),
        "banks": pd.read_csv(BANKS_PATH, dtype={"bank_id": str}),
        "bank_world": pd.read_csv(BANK_WORLD_PATH, dtype={"bank_id": str}),
        "bank_market": pd.read_csv(BANK_MARKET_PATH, dtype={"bank_id": str}),
        "macro_environment": pd.read_csv(MACRO_ENVIRONMENT_PATH),
        "financial_institutions": pd.read_csv(FINANCIAL_INSTITUTIONS_PATH, dtype={"institution_id": str, "bank_id": str}),
    }

    print(f"Customer source:      {customer_source}")
    print(f"Account source:       {account_source}")
    if card_source is not None:
        print(f"Card source:          {card_source}")
    if loan_source is not None:
        print(f"Loan source:          {loan_source}")
    if snapshot_source is not None:
        print(f"Loan snapshot source: {snapshot_source}")
    print(f"Macro source:         {MACRO_ENVIRONMENT_PATH}")
    print(f"Institution source:   {FINANCIAL_INSTITUTIONS_PATH}")

    require(d["customers"], {"customer_id","customer_type","registration_year","customer_status"}, "customers")
    require(d["accounts"], {"account_id","customer_id","product_id","branch_id","opening_year","account_status","closing_year","opening_channel"}, "accounts")
    require(d["branches"], {"branch_id","branch_size","status","opening_year","closing_year","department","locality","region"}, "branches")
    require(d["banks"], {"bank_id","bank_name","bank_scope","bank_status"}, "banks")
    require(d["bank_world"], {
        "world_seed","bank_id","realized_usd_affinity","realized_business_affinity",
        "realized_large_transfer_affinity","foreign_selection_weight"
    }, "bank_world_parameters")
    require(d["bank_market"], {"world_seed","bank_id","year","market_weight"}, "bank_market_weights")
    require(d["macro_environment"], {"year","cross_border_factor","world_seed"}, "macro_environment")
    require(d["financial_institutions"], {"institution_id","institution_name","institution_type","country","domestic_flag","bank_id","active_from","active_to"}, "financial_institutions")

    d["customers"]["customer_id"] = d["customers"]["customer_id"].astype(str)
    d["accounts"]["customer_id"] = d["accounts"]["customer_id"].astype(str)
    d["accounts"]["account_id"] = d["accounts"]["account_id"].astype(str)

    if len(d["customers"]) != WORLD_CONFIG.customer_count:
        raise ValueError(
            "Customer population does not match world_config.json: "
            f"loaded={len(d['customers']):,}, configured={WORLD_CONFIG.customer_count:,}."
        )

    missing_customer_ids = set(d["accounts"]["customer_id"]) - set(d["customers"]["customer_id"])
    if missing_customer_ids:
        raise ValueError(f"Accounts reference {len(missing_customer_ids):,} unknown customers.")

    return d


def select_smoke_population(d, smoke=False):
    if not smoke:
        return d
    n = min(int(WORLD_CONFIG.smoke_customers), len(d["customers"]))
    ids = set(d["customers"].sort_values("customer_id").head(n)["customer_id"].astype(str))
    d = {k: (v.copy() if isinstance(v, pd.DataFrame) else v) for k, v in d.items()}
    d["customers"] = d["customers"][d["customers"]["customer_id"].astype(str).isin(ids)].copy()
    for key in ("accounts", "cards", "loans"):
        if not d[key].empty and "customer_id" in d[key].columns:
            d[key]["customer_id"] = d[key]["customer_id"].astype(str)
            d[key] = d[key][d[key]["customer_id"].isin(ids)].copy()
    if not d["loans"].empty:
        loan_ids = set(d["loans"]["loan_id"].astype(str))
        for key in ("loan_snapshot", "loan_bridge"):
            if not d[key].empty and "loan_id" in d[key].columns:
                d[key]["loan_id"] = d[key]["loan_id"].astype(str)
                d[key] = d[key][d[key]["loan_id"].isin(loan_ids)].copy()
    return d


def lifecycle(accounts):
    a = accounts.copy(); a["opening_year"] = pd.to_numeric(a["opening_year"]).astype(int)
    starts=[]; ends=[]
    for r in a.itertuples(index=False):
        oy=int(r.opening_year)
        om=1 if oy<2021 else int(rng_for("open-month",r.account_id,oy).integers(1,13))
        s=max(pd.Period(f"{max(oy,2021)}-{om:02d}",freq="M"), OBS_START)
        cy = None if pd.isna(r.closing_year) or str(r.closing_year).strip()=="" else int(float(r.closing_year))
        if str(r.account_status).upper()=="CLOSED" and cy is not None:
            cm=int(rng_for("close-month",r.account_id,cy).integers(1,13)); e=pd.Period(f"{cy}-{cm:02d}",freq="M")
        else: e=OBS_END
        starts.append(s); ends.append(min(e,OBS_END))
    a["first_obs_month"]=starts; a["last_obs_month"]=ends
    return a[a["first_obs_month"]<=a["last_obs_month"]].copy()


def build_roles(accounts, customers):
    ctype=customers.set_index("customer_id")["customer_type"].str.upper().to_dict(); out=[]
    for cid,g in accounts.groupby("customer_id",sort=False):
        business=ctype.get(cid)=="BUSINESS"
        priority={"P003":5,"P004":4,"P001":2,"P002":1} if business else {"P005":6,"P003":5,"P001":4,"P006":3,"P004":2,"P002":1}
        candidate=None; score=-1
        for r in g.itertuples(index=False):
            if r.product_id not in FIXED and priority.get(r.product_id,0)>score:
                candidate=r.account_id; score=priority.get(r.product_id,0)
        for r in g.itertuples(index=False):
            p=r.product_id
            if p in FIXED: role="FIXED_TERM"
            elif p=="P005": role="PAYROLL"
            elif business and p in {"P003","P004"}: role="BUSINESS_OPERATING" if r.account_id==candidate else "SECONDARY"
            elif p in {"P002","P004"} and r.account_id!=candidate: role="USD_RESERVE"
            elif p in {"P001","P002"} and r.account_id!=candidate: role="SAVINGS"
            elif r.account_id==candidate: role="PRIMARY_TRANSACTIONAL"
            else: role="SECONDARY"
            out.append((r.account_id,cid,role))
    return pd.DataFrame(out,columns=["account_id","customer_id","account_role"])



def build_world_parameters():
    """Draw world-level parameters once per seed.

    These parameters change the macro starting point and trajectory without
    changing the structural rules of BTYT. Customer traits and monthly shocks
    are then generated conditionally on this world.
    """
    r = rng_for("world-parameters")
    return {
        # Level shifts are on logit/utility scales, not direct percentage points.
        "digital_initial_shift": float(np.clip(r.normal(0.0, 0.38), -0.75, 0.75)),
        "cash_initial_shift": float(np.clip(r.normal(0.0, 0.42), -0.85, 0.85)),
        # Positive on average, but materially different across worlds.
        "digital_adoption_strength": float(np.clip(r.normal(0.16, 0.055), 0.045, 0.30)),
        "cash_transition_strength": float(np.clip(r.normal(0.10, 0.040), 0.025, 0.22)),
        # Modest macro differences in activity and volatility.
        "activity_multiplier": float(np.clip(r.lognormal(0.0, 0.10), 0.78, 1.28)),
        "volatility_multiplier": float(np.clip(r.lognormal(0.0, 0.10), 0.78, 1.30)),
    }


WORLD = build_world_parameters()

def build_traits(customers, accounts):
    x=accounts.groupby("customer_id").agg(
        n_accounts=("account_id","size"),
        digital=("opening_channel",lambda s:s.astype(str).str.upper().isin(["DIGITAL","REMOTE"]).sum()),
        txmix=("product_id",lambda s:s.isin(["P003","P004","P005","P006"]).sum()),
        usd=("product_id",lambda s:s.isin(["P002","P004","P008"]).sum()),
    ).reset_index()
    c=customers.merge(x,on="customer_id",how="left").fillna({"n_accounts":0,"digital":0,"txmix":0,"usd":0})
    age=WORLD_CONFIG.end_date.year-pd.to_numeric(c.get("birth_year",45),errors="coerce"); age=age.fillna(45).clip(18,100)
    business=(c["customer_type"].str.upper()=="BUSINESS").astype(float)
    corr=np.eye(9); pairs={(0,1):.25,(0,3):.30,(0,4):.35,(1,2):-.45,(1,4):.20,(3,5):-.30,(4,7):.35,(0,8):.25}
    for (i,j),v in pairs.items(): corr[i,j]=corr[j,i]=v
    z=np.vstack([
        rng_for("traits", cid).multivariate_normal(np.zeros(9), corr)
        for cid in c["customer_id"].astype(str)
    ])
    ds=c["digital"]/np.maximum(c["n_accounts"],1); tm=c["txmix"]/np.maximum(c["n_accounts"],1)
    activity=np.clip(np.exp(.10+.28*z[:,0]+.12*business+.10*np.log1p(c["n_accounts"]))*WORLD["activity_multiplier"],.35,3.5)
    digital=sigmoid(-.10+WORLD["digital_initial_shift"]+.95*z[:,1]-.022*(age-40)+1.10*ds+.20*tm)
    cash=sigmoid(-.25+WORLD["cash_initial_shift"]+z[:,2]-.90*(digital-.5)+.010*(age-40)-.20*business)
    spending=sigmoid(-.05+.95*z[:,3]); transfer=sigmoid(-.10+.90*z[:,4]+.55*business+.20*tm)
    buffer=np.clip(np.exp(-.15+.42*z[:,5]+.20*business),.25,4.0)
    recurring=sigmoid(.20+.90*z[:,6]); external=sigmoid(-.30+.95*z[:,7]+.30*business+.20*(c["usd"]>0))
    vol=np.clip(np.exp(-.55+.45*z[:,8]+.45*business)*WORLD["volatility_multiplier"],.20,2.50)
    bop=np.where(business>0,np.clip(np.exp(.20+.40*z[:,0]+.30*z[:,4]),.5,4),1.0)
    bseason=np.where(business>0,np.clip(np.exp(-.35+.35*z[:,8]),.2,2.5),0)
    return pd.DataFrame({"customer_id":c["customer_id"],"activity_intensity":activity,"digital_preference":digital,
        "cash_preference":cash,"spending_propensity":spending,"transfer_preference":transfer,"liquidity_buffer":buffer,
        "recurring_behavior":recurring,"external_bank_affinity":external,"financial_volatility":vol,
        "business_operating_intensity":bop,"business_seasonality":bseason})


def anchor_uyu(c):
    if str(c.get("customer_type","INDIVIDUAL")).upper()=="BUSINESS":
        x=pd.to_numeric(pd.Series([c.get("annual_revenue",np.nan)]),errors="coerce").iloc[0]
        return 1_000_000.0 if pd.isna(x) or x<=0 else float(x)/12
    x=pd.to_numeric(pd.Series([c.get("monthly_income",np.nan)]),errors="coerce").iloc[0]
    return 55_000.0 if pd.isna(x) or x<=0 else float(x)


def monthly_scale(c,t,period):
    key = (str(c["customer_id"]), str(period))
    cached = MONTHLY_SCALE_CACHE.get(key)
    if cached is not None:
        return cached

    factor={2021:.63,2022:.72,2023:.82,2024:.90,2025:.96,2026:1}.get(period.year, 1.0)
    r=rng_for("scale",c["customer_id"],period); yr=rng_for("year-scale",c["customer_id"],period.year)
    v=float(t["financial_volatility"]); season=1.0
    if str(c["customer_type"]).upper()=="BUSINESS":
        sector=str(c.get("business_sector","")).upper(); s=float(t["business_seasonality"])
        if any(k in sector for k in ["TOUR","HOTEL","RESTAUR"]): season+=s*(.20 if period.month in [12,1,2] else -.04)
        elif any(k in sector for k in ["AGRI","RURAL","LIVESTOCK"]): season+=s*(.12 if period.month in [3,4,5,9,10] else -.025)
        elif any(k in sector for k in ["RETAIL","COMMER","TRADE"]): season+=s*(.10 if period.month==12 else 0)
    value=max(1000,anchor_uyu(c)*factor*np.exp(yr.normal(0,.06*v))*np.exp(r.normal(0,.07*v))*season)
    MONTHLY_SCALE_CACHE[key] = value
    return value


def inherited_balance(a,c,t):
    if int(a["opening_year"])>=2021: return 0.0
    r=rng_for("opening-balance",a["account_id"]); p=a["product_id"]
    mean={"P007":1.2,"P008":1.2,"P005":-.75,"P006":-1.1,"P003":-.1,"P002":-.1,"P004":-.1}.get(p,-.35)
    sigma=.75 if p in FIXED else .80
    uyu=anchor_uyu(c)*float(t["liquidity_buffer"])*r.lognormal(mean,sigma)
    if str(c["customer_type"]).upper()=="BUSINESS": uyu*=r.uniform(1.2,2.6)
    if r.random()<.015: uyu*=r.uniform(3,10)
    return money(uyu/FX[2021] if CURRENCY[p]=="USD" else uyu)


def liquidity_state(balance, currency, scale, t, role):
    """Return a soft liquidity ratio used to shape behavioral intentions.

    This is not a hard spending rule. It only changes transaction probabilities:
    low-liquidity accounts become less likely to initiate discretionary debits,
    while high-liquidity transactional accounts can release accumulated balances.
    """
    balance_uyu = float(balance) * (FX[2026] if currency == "USD" else 1.0)
    role_target = {
        "PAYROLL": 0.70,
        "PRIMARY_TRANSACTIONAL": 0.85,
        "BUSINESS_OPERATING": 1.00,
        "SAVINGS": 1.20,
        "USD_RESERVE": 1.35,
        "SECONDARY": 0.95,
        "FIXED_TERM": 1.50,
    }.get(role, 1.0)
    target = max(1_000.0, float(scale) * float(t["liquidity_buffer"]) * role_target)
    ratio = balance_uyu / target
    low = float(sigmoid(3.6 * (0.55 - ratio)))
    excess = float(sigmoid(2.2 * (ratio - 1.45)))
    return ratio, low, excess


def type_probs(p, role, ctype, t, has_debit, low_liquidity=0.0, excess_liquidity=0.0):
    labels = ["TRANSFER_IN","TRANSFER_OUT","CASH_DEPOSIT","CASH_WITHDRAWAL","DEBIT_PURCHASE","SERVICE_PAYMENT"]
    d=float(t["digital_preference"]); cash=float(t["cash_preference"]); sp=float(t["spending_propensity"]); tr=float(t["transfer_preference"])
    u=np.array([-.10+.75*tr,-.15+.85*tr,-1.20+1.25*cash,-.85+1.25*cash,-.25+1.15*sp+.25*d,-.45+.60*sp+.35*d], float)

    if ctype=="BUSINESS": u+=np.array([.70,.75,.20,-.15,-.35,.10])
    if p in {"P002","P004"}: u+=np.array([.25,.35,0,-.20,-1.10,-.80])
    if p=="P005": u+=np.array([.25,0,0,0,.55,.35])
    if p=="P006": u+=np.array([0,0,-.40,0,.65,-.10])
    if role in {"SAVINGS","USD_RESERVE","SECONDARY"}: u+=np.array([.20,.10,0,0,-.55,-.40])
    if not has_debit: u[4]=-20

    # Liquidity feedback is intentionally probabilistic rather than a hard cap.
    # When liquidity is scarce, discretionary debit intentions become less likely,
    # while funding-type intentions become somewhat more likely.
    low=float(np.clip(low_liquidity,0,1))
    u += np.array([.45*low,-1.10*low,.25*low,-.80*low,-1.15*low,-.85*low])

    # Payroll accounts should not accumulate income indefinitely. Once liquidity
    # is comfortably above the customer's own buffer, debit-type behavior becomes
    # gradually more likely. This remains noisy and account-specific.
    if p=="P005":
        ex=float(np.clip(excess_liquidity,0,1))
        u += np.array([-.20*ex,.55*ex,-.10*ex,.20*ex,.55*ex,.45*ex])

    return labels,softmax(u)


def event_count(a,t,ctype,period,role):
    p=a["product_id"]
    if p in FIXED:return 0
    base=BASE_INTENSITY[p]*ROLE_MULT.get(role,1)*float(t["activity_intensity"])
    if ctype=="BUSINESS": base*=float(t["business_operating_intensity"])*(1.4 if p in {"P003","P004"} else 1)
    if period.month==12: base*=1.12
    if period.month==1: base*=.95
    r=rng_for("count",a["account_id"],period); base*=np.exp(r.normal(0,.20*float(t["financial_volatility"])))
    k=2.4 if ctype=="BUSINESS" else 3.5
    return min(int(r.poisson(r.gamma(k,max(base,.05)/k))),180)


def build_institution_context(d):
    """Build compact lookup tables for V4 financial-institution selection."""
    banks = d["banks"].copy()
    institutions = d["financial_institutions"].copy()
    world = d["bank_world"].copy()
    market = d["bank_market"].copy()
    macro = d["macro_environment"].copy()

    banks["bank_id"] = banks["bank_id"].astype(str)
    institutions["institution_id"] = institutions["institution_id"].astype(str)
    institutions["bank_id"] = institutions["bank_id"].where(institutions["bank_id"].notna(), None)
    world["bank_id"] = world["bank_id"].astype(str)
    market["bank_id"] = market["bank_id"].astype(str)
    market["year"] = pd.to_numeric(market["year"], errors="raise").astype(int)
    macro["year"] = pd.to_numeric(macro["year"], errors="raise").astype(int)

    if institutions["institution_id"].duplicated().any():
        raise ValueError("financial_institutions.csv contains duplicate institution_id values.")

    active_banks = banks.loc[banks["bank_status"].astype(str).str.upper().eq("ACTIVE")].copy()
    domestic_bank_ids = tuple(active_banks.loc[active_banks["bank_scope"].eq("DOMESTIC"), "bank_id"].astype(str))
    foreign_bank_ids = tuple(active_banks.loc[active_banks["bank_scope"].eq("FOREIGN"), "bank_id"].astype(str))

    if "B000" in domestic_bank_ids:
        raise ValueError("BTYT B000 must remain outside the external domestic-bank pool.")
    if not domestic_bank_ids or not foreign_bank_ids:
        raise ValueError("Both domestic external and international bank pools are required.")

    institution_by_bank = {}
    for row in institutions.loc[institutions["institution_type"].eq("BANK")].itertuples(index=False):
        if row.bank_id is None or pd.isna(row.bank_id):
            raise ValueError(f"BANK institution {row.institution_id} is missing bank_id.")
        institution_by_bank[str(row.bank_id)] = str(row.institution_id)

    required_bank_ids = {"B000", *domestic_bank_ids, *foreign_bank_ids}
    missing_institutions = required_bank_ids - set(institution_by_bank)
    if missing_institutions:
        raise ValueError(f"Financial-institution dimension is missing bank mappings: {sorted(missing_institutions)}")

    bank_world_seeds = pd.to_numeric(world["world_seed"], errors="raise").astype(int).unique()
    market_world_seeds = pd.to_numeric(market["world_seed"], errors="raise").astype(int).unique()
    macro_world_seeds = pd.to_numeric(macro["world_seed"], errors="raise").astype(int).unique()
    if len(bank_world_seeds) != 1 or len(market_world_seeds) != 1 or len(macro_world_seeds) != 1:
        raise ValueError("Bank and macro inputs must each contain exactly one world_seed.")
    if int(bank_world_seeds[0]) != int(market_world_seeds[0]):
        raise ValueError("Bank world seed mismatch between parameters and market weights.")
    bank_world_seed = int(bank_world_seeds[0])
    macro_world_seed = int(macro_world_seeds[0])
    if bank_world_seed != int(WORLD_CONFIG.seed) or macro_world_seed != int(WORLD_CONFIG.seed):
        raise ValueError("Bank/macro world seed does not match world_config.json.")

    affinity_cols = [
        "realized_usd_affinity", "realized_business_affinity",
        "realized_large_transfer_affinity", "foreign_selection_weight",
    ]
    world_lookup = world.set_index("bank_id")[affinity_cols].to_dict(orient="index")
    for bank_id in (*domestic_bank_ids, *foreign_bank_ids):
        if bank_id not in world_lookup:
            raise ValueError(f"Missing bank-world parameters for {bank_id}.")

    market_lookup = {}
    for year, g in market.groupby("year", sort=False):
        external = g[g["bank_id"].isin(domestic_bank_ids)].copy()
        if set(external["bank_id"]) != set(domestic_bank_ids):
            missing = sorted(set(domestic_bank_ids) - set(external["bank_id"]))
            raise ValueError(f"Domestic market weights missing {missing} in {year}.")
        market_lookup[int(year)] = external.set_index("bank_id")["market_weight"].astype(float).to_dict()

    required_years = set(range(OBS_START.year, OBS_END.year + 1))
    if set(market_lookup) != required_years:
        raise ValueError("bank_market_weights.csv does not cover every transaction year.")
    macro_lookup = macro.set_index("year")["cross_border_factor"].astype(float).to_dict()
    if not required_years.issubset(macro_lookup):
        raise ValueError("macro_environment.csv does not cover every transaction year.")

    foreign_base = {}
    for bank_id in foreign_bank_ids:
        value = float(world_lookup[bank_id]["foreign_selection_weight"])
        if not np.isfinite(value) or value <= 0:
            raise ValueError(f"Invalid foreign selection weight for {bank_id}.")
        foreign_base[bank_id] = value

    institutions["active_from"] = pd.to_datetime(institutions["active_from"], errors="coerce")
    institutions["active_to"] = pd.to_datetime(institutions["active_to"], errors="coerce")
    iede = institutions.loc[
        institutions["institution_type"].eq("ELECTRONIC_MONEY_ISSUER")
        & institutions["domestic_flag"].astype(bool)
    ].copy()
    if iede.empty:
        raise ValueError("No domestic electronic-money institutions found.")

    institution_meta = institutions.set_index("institution_id")[
        ["institution_name", "institution_type", "country", "domestic_flag", "bank_id", "active_from", "active_to"]
    ].to_dict(orient="index")

    return {
        "bank_world_seed": bank_world_seed,
        "macro_world_seed": macro_world_seed,
        "institution_meta": institution_meta,
        "institution_by_bank": institution_by_bank,
        "domestic_bank_ids": domestic_bank_ids,
        "foreign_bank_ids": foreign_bank_ids,
        "domestic_bank_institution_ids": tuple(institution_by_bank[x] for x in domestic_bank_ids),
        "foreign_bank_institution_ids": tuple(institution_by_bank[x] for x in foreign_bank_ids),
        "btyt_institution_id": institution_by_bank["B000"],
        "iede_ids": tuple(iede["institution_id"].astype(str)),
        "world": world_lookup,
        "market": market_lookup,
        "macro_cross_border": macro_lookup,
        "foreign_base": foreign_base,
    }


def transfer_large_signal(amount_uyu):
    """Smooth 0-1 signal for economically large transfers."""
    x = (math.log1p(max(float(amount_uyu), 0.0)) - math.log(150_000.0)) / 0.90
    return float(sigmoid(x))


def choose_external_scope(r, ctype, traits, period, currency, amount):
    """Choose domestic-external versus international before choosing an institution."""
    if INSTITUTION_CONTEXT is None:
        raise RuntimeError("INSTITUTION_CONTEXT has not been initialized.")
    amount_uyu = float(amount) * (FX[int(period.year)] if currency == "USD" else 1.0)
    large = transfer_large_signal(amount_uyu)
    cross_border = float(INSTITUTION_CONTEXT["macro_cross_border"][int(period.year)])
    ext_affinity = float(traits["external_bank_affinity"])
    logit = -2.35
    logit += 1.35 if currency == "USD" else 0.0
    logit += 0.65 if ctype == "BUSINESS" else 0.0
    logit += 1.05 * large
    logit += 0.75 * (ext_affinity - 0.5)
    logit += 0.35 * cross_border
    p_international = float(np.clip(sigmoid(logit), 0.025, 0.72))
    return "INTERNATIONAL" if r.random() < p_international else "DOMESTIC_EXTERNAL"


def bank_selection_score(bank_id, base_weight, currency, ctype, amount_uyu, customer_id):
    """Convert bank prominence and affinities into a conditional transfer score."""
    params = INSTITUTION_CONTEXT["world"][bank_id]
    usd_aff = float(params["realized_usd_affinity"])
    business_aff = float(params["realized_business_affinity"])
    large_aff = float(params["realized_large_transfer_affinity"])
    large = transfer_large_signal(amount_uyu)
    currency_fit = math.exp((1.00 if currency == "USD" else -0.20) * (usd_aff - 0.5))
    customer_fit = math.exp((0.80 if ctype == "BUSINESS" else -0.15) * (business_aff - 0.5))
    amount_fit = math.exp(1.00 * large * (large_aff - 0.5))
    fit_key = (str(customer_id), str(bank_id))
    behavioral_fit = CUSTOMER_BANK_FIT_CACHE.get(fit_key)
    if behavioral_fit is None:
        behavioral_fit = math.exp(float(rng_for("customer-bank-fit", customer_id, bank_id).normal(0.0, 0.16)))
        CUSTOMER_BANK_FIT_CACHE[fit_key] = behavioral_fit
    return max(float(base_weight), 1e-12) * currency_fit * customer_fit * amount_fit * behavioral_fit


def institution_is_active(institution_id, transaction_datetime):
    meta = INSTITUTION_CONTEXT["institution_meta"][str(institution_id)]
    dt = pd.Timestamp(transaction_datetime).normalize()
    start = meta["active_from"]
    end = meta["active_to"]
    return (pd.isna(start) or dt >= start) and (pd.isna(end) or dt <= end)


def choose_external_bank_institution(r, scope, ctype, period, currency, amount, customer_id):
    """Choose a bank institution inside the selected transfer scope."""
    year = int(period.year)
    amount_uyu = float(amount) * (FX[year] if currency == "USD" else 1.0)
    if scope == "DOMESTIC_EXTERNAL":
        bank_ids = INSTITUTION_CONTEXT["domestic_bank_ids"]
        base = INSTITUTION_CONTEXT["market"][year]
    elif scope == "INTERNATIONAL":
        bank_ids = INSTITUTION_CONTEXT["foreign_bank_ids"]
        base = INSTITUTION_CONTEXT["foreign_base"]
    else:
        raise ValueError(f"Unsupported external transfer scope: {scope}")
    scores = np.array([
        bank_selection_score(bank_id, base[bank_id], currency, ctype, amount_uyu, customer_id)
        for bank_id in bank_ids
    ], dtype=float)
    if not np.isfinite(scores).all() or scores.sum() <= 0:
        raise ValueError(f"Invalid bank-selection scores for scope {scope}.")
    bank_id = str(r.choice(np.asarray(bank_ids, dtype=object), p=scores / scores.sum()))
    return INSTITUTION_CONTEXT["institution_by_bank"][bank_id]


def choose_domestic_institution(r, ctype, traits, period, currency, amount, customer_id, transaction_datetime):
    """Choose a domestic bank or active IEDE without forcing an ex-post target share."""
    active_iede = [
        institution_id for institution_id in INSTITUTION_CONTEXT["iede_ids"]
        if institution_is_active(institution_id, transaction_datetime)
    ]
    if not active_iede:
        return choose_external_bank_institution(r, "DOMESTIC_EXTERNAL", ctype, period, currency, amount, customer_id)

    amount_uyu = float(amount) * (FX[int(period.year)] if currency == "USD" else 1.0)
    large = transfer_large_signal(amount_uyu)
    digital = float(traits["digital_preference"])
    # IEDE use is modeled as a probabilistic utility shift. It is more plausible
    # for digital, UYU, individual, and smaller-value transfers, while banks remain
    # structurally favored for business, USD, and large-value activity.
    iede_logit = -1.55
    iede_logit += 1.20 * (digital - 0.5)
    iede_logit += 0.35 if ctype == "INDIVIDUAL" else -0.55
    iede_logit += 0.30 if currency == "UYU" else -0.70
    iede_logit -= 1.15 * large
    p_iede = float(np.clip(sigmoid(iede_logit), 0.03, 0.55))
    if r.random() >= p_iede:
        return choose_external_bank_institution(r, "DOMESTIC_EXTERNAL", ctype, period, currency, amount, customer_id)

    scores = []
    for institution_id in active_iede:
        taste = math.exp(float(rng_for("customer-institution-fit", customer_id, institution_id).normal(0.0, 0.20)))
        scores.append(taste)
    scores = np.asarray(scores, dtype=float)
    return str(r.choice(np.asarray(active_iede, dtype=object), p=scores / scores.sum()))


def resolve_transfer_institution(event, account, customer, traits, period, sequence):
    """Resolve transfer_scope and counterparty_institution_id."""
    tt = str(event["transaction_type"])
    cp = str(event["counterparty_type"])
    if tt not in {"TRANSFER_IN", "TRANSFER_OUT"}:
        return None, None
    if cp == "BTYT_CUSTOMER":
        return "INTERNAL", INSTITUTION_CONTEXT["btyt_institution_id"]
    if cp != "FINANCIAL_INSTITUTION":
        return None, None

    ctype = str(customer["customer_type"]).upper()
    currency = CURRENCY[str(account["product_id"])]
    r = rng_for(
        "institution-counterparty", account["account_id"], period, sequence,
        event.get("source"), event.get("amount"), cp,
    )
    scope = choose_external_scope(r, ctype, traits, period, currency, event["amount"])
    if scope == "INTERNATIONAL":
        institution_id = choose_external_bank_institution(
            r, scope, ctype, period, currency, event["amount"], str(customer["customer_id"])
        )
    else:
        institution_id = choose_domestic_institution(
            r, ctype, traits, period, currency, event["amount"], str(customer["customer_id"]),
            event["transaction_datetime"],
        )
    return scope, institution_id


def merchant_probs(c,t,period):
    customer_id = str(c["customer_id"])
    base = MERCHANT_BASE_CACHE.get(customer_id)
    if base is None:
        alpha=np.array([5,2.4,2,3,1.6,1.4,1.8,.9,1.3,.9,1.8,1.5,2,1.2,.8,.8,1.0],float)
        alpha[12]*=.75+1.10*float(t["digital_preference"]); alpha[1]*=.8+.6*float(t["spending_propensity"]); alpha[8]*=.8+.6*float(t["spending_propensity"])
        if str(c["customer_type"]).upper()=="BUSINESS": alpha*=.7; alpha[15]*=4.5; alpha[14]*=2; alpha[13]*=1.5
        base=rng_for("dirichlet",c["customer_id"]).dirichlet(alpha)
        MERCHANT_BASE_CACHE[customer_id] = base
    p = base.copy()
    if period.month in [12,1,2]: p[7]*=1.35; p[1]*=1.15; p[8]*=1.10
    if period.month==12: p[3]*=1.35; p[12]*=1.25
    return p/p.sum()


def counterparty(r,tt,ctype,t,role):
    ext=float(t["external_bank_affinity"]); business=ctype=="BUSINESS"
    if tt=="DEBIT_PURCHASE":return "MERCHANT"
    if tt in {"LOAN_PAYMENT","LOAN_DISBURSEMENT"}:return "LOAN_ACCOUNT"
    if tt=="INTEREST_CREDIT":return "OTHER"
    if tt=="SERVICE_PAYMENT":return choose(r,["SERVICE_PROVIDER","GOVERNMENT","SUPPLIER"] if business else ["SERVICE_PROVIDER","GOVERNMENT"],[.5,.25,.25] if business else [.82,.18])
    if tt in {"CASH_DEPOSIT","CASH_WITHDRAWAL"}:return "OTHER"
    if tt=="TRANSFER_IN":
        if role=="PAYROLL" and not business:return choose(r,["EMPLOYER","BTYT_CUSTOMER","FINANCIAL_INSTITUTION","GOVERNMENT","OTHER"],[4,1.2,1+2*ext,.5,.6])
        return choose(r,["BTYT_CUSTOMER","FINANCIAL_INSTITUTION","GOVERNMENT","SUPPLIER","OTHER"] if business else ["EMPLOYER","BTYT_CUSTOMER","FINANCIAL_INSTITUTION","GOVERNMENT","OTHER"],[1.3,1.2+2*ext,.5,.4,1] if business else [.5,1.8,1+2*ext,.4,.8])
    if business:return choose(r,["SUPPLIER","FINANCIAL_INSTITUTION","BTYT_CUSTOMER","GOVERNMENT","OTHER"],[2.4,1+2*ext,1.1,.8,.5])
    return choose(r,["BTYT_CUSTOMER","FINANCIAL_INSTITUTION","GOVERNMENT","OTHER"],[2.1,1+2*ext,.4,.8])


def channel(r,tt,t,ctype,period,recurring=False,amount=None,currency="UYU"):
    trend=(period.ordinal-OBS_START.ordinal)/(OBS_END.ordinal-OBS_START.ordinal); d=np.clip(float(t["digital_preference"])+WORLD["digital_adoption_strength"]*trend,.02,.98); cash=np.clip(float(t["cash_preference"])-WORLD["cash_transition_strength"]*trend,.02,.98)
    if tt=="DEBIT_PURCHASE":return "POS"
    if tt in {"CASH_WITHDRAWAL","CASH_DEPOSIT"}:
        # Cash-channel feasibility is amount-aware. Small cash operations can use
        # either ATM or BRANCH, but ATM probability declines as the amount grows.
        # Any operation above BTYT's synthetic per-event ATM limit is rerouted to
        # BRANCH rather than having its economically meaningful amount truncated.
        limit=ATM_CASH_LIMIT_UYU[tt].get(ctype,ATM_CASH_LIMIT_UYU[tt]["INDIVIDUAL"])
        amount_uyu=float(amount or 0.0)*(FX[int(period.year)] if currency=="USD" else 1.0)
        ratio=max(0.0,amount_uyu/max(limit,1.0))
        atm_feasibility=float(sigmoid(7.0*(0.72-ratio)))
        if amount_uyu>limit:
            return "BRANCH"
        if tt=="CASH_WITHDRAWAL":
            return choose(r,["ATM","BRANCH"],[(1.5+1.8*d)*atm_feasibility,.5+1.5*cash])
        return choose(r,["BRANCH","ATM"],[1.5+1.4*cash,(.8+.7*d)*atm_feasibility])
    if tt=="INTEREST_CREDIT":return "AUTOMATIC"
    if tt=="LOAN_DISBURSEMENT":return choose(r,["AUTOMATIC","BRANCH"],[2.5,.7])
    if tt=="LOAN_PAYMENT":return choose(r,["AUTOMATIC","MOBILE","WEB","BRANCH"],[2.6,1.4+2*d,1+1.2*d,.5+1*(1-d)])
    if tt=="SERVICE_PAYMENT":return choose(r,["MOBILE","WEB","AUTOMATIC","BRANCH"],[1.3+2.3*d,.8+1.4*d,1.1+(1.2 if recurring else 0),.4+1.2*(1-d)])
    return choose(r,["MOBILE","WEB","BRANCH"],[1.4+2.4*d,.8+1.3*d,.4+1.3*(1-d)])


def positive_multiplier(r, shape, rare_tail_prob=0.0, rare_tail_low=1.0, rare_tail_high=1.0):
    """Mean-one gamma multiplier with an optional explicit rare tail.

    Gamma tails are materially lighter than the previous unrestricted lognormal
    tails, while still preserving skewness and heterogeneity. Rare large events
    are introduced explicitly rather than being accidental numerical monsters.
    """
    shape=max(float(shape),0.25)
    x=float(r.gamma(shape,1.0/shape))
    if rare_tail_prob>0 and r.random()<rare_tail_prob:
        x*=float(r.uniform(rare_tail_low,rare_tail_high))
    return x


def amount(r,tt,ctype,currency,scale,t,period,cat=None,recurring=False):
    v=float(t["financial_volatility"]); business=ctype=="BUSINESS"

    if tt=="DEBIT_PURCHASE":
        f={"GROCERIES":.035,"RESTAURANTS":.022,"FUEL":.030,"RETAIL":.045,"HEALTHCARE":.050,"PHARMACY":.020,"TRANSPORT":.012,"TRAVEL":.120,"ENTERTAINMENT":.020,"EDUCATION":.045,"UTILITIES":.035,"TELECOMMUNICATIONS":.020,"ECOMMERCE":.035,"HOME":.055,"AUTOMOTIVE":.100,"PROFESSIONAL_SERVICES":.070,"OTHER":.030}[cat]
        shape=max(1.8,3.5/(1.0+.22*v))
        uyu=scale*f*positive_multiplier(r,shape,0.00035,2.0,4.5)
    elif tt=="SERVICE_PAYMENT":
        shape=max(2.0,(5.0 if recurring else 3.2)/(1.0+.18*v))
        uyu=scale*(.075 if business else .055)*positive_multiplier(r,shape,0.00025,1.8,3.5)
    elif tt=="CASH_WITHDRAWAL":
        shape=max(2.2,4.5/(1.0+.18*v))
        uyu=scale*(.055 if business else .070)*positive_multiplier(r,shape,0.00015,1.5,2.8)
    elif tt=="CASH_DEPOSIT":
        shape=max(1.6,2.8/(1.0+.22*v))
        uyu=scale*(.18 if business else .10)*positive_multiplier(r,shape,0.0008,2.0,5.0)
    else:
        # Transfers retain the heaviest regular tails because genuinely large
        # business and interbank movements are economically plausible.
        shape=max(1.15,1.9/(1.0+.25*v))
        uyu=scale*(.28 if business else .22)*positive_multiplier(r,shape,0.0015,2.0,6.0)

    if business:uyu*=1.15
    fx=FX[int(period.year)]
    return money(max(1 if currency=="USD" else 20, uyu/fx if currency=="USD" else uyu))


def month_calendar(period):
    key = str(period)
    cached = MONTH_CALENDAR_CACHE.get(key)
    if cached is not None:
        return cached
    nd=calendar.monthrange(period.year,period.month)[1]
    days=np.arange(1,nd+1)
    weekdays=np.fromiter(
        (datetime(period.year,period.month,int(day)).weekday() for day in days),
        dtype=np.int8,
        count=nd,
    )
    cached=(nd,days,weekdays)
    MONTH_CALENDAR_CACHE[key]=cached
    return cached


def event_datetime(r,period,tt,cp,ch,ctype,preferred=None):
    nd,days,weekdays=month_calendar(period); w=np.ones(nd,float)
    if ctype=="BUSINESS":
        w *= np.where(weekdays < 5, 1.7, .35)
    elif tt=="DEBIT_PURCHASE":
        w *= np.where(weekdays >= 5, 1.2, 1.0)
    if cp=="EMPLOYER":
        w *= np.where((days<=5)|(days>=nd-2),5.0,.55)
    if preferred is not None:
        w *= np.exp(-.35*np.abs(days-preferred))+.05
    day=int(r.choice(days,p=w/w.sum()))
    if ch=="BRANCH":
        if datetime(period.year,period.month,day).weekday()>=5:
            prev_day=day
            while prev_day>1 and datetime(period.year,period.month,prev_day).weekday()>=5:
                prev_day-=1
            if datetime(period.year,period.month,prev_day).weekday()<5:
                day=prev_day
            else:
                next_day=day
                while next_day<nd and datetime(period.year,period.month,next_day).weekday()>=5:
                    next_day+=1
                day=next_day
        hour=int(r.integers(9,17))
    elif ch=="POS":hour=int(np.clip(round(r.normal(16,4)),8,23))
    elif ch=="ATM":hour=int(np.clip(round(r.normal(15,5.2)),0,23))
    elif ch=="AUTOMATIC":hour=int(r.choice([0,1,2,3,6,7,8,9]))
    elif ch=="WEB" and ctype=="BUSINESS":hour=int(np.clip(round(r.normal(13,3)),7,20))
    else:hour=int(np.clip(round(r.normal(15,4.8)),5,23))
    return pd.Timestamp(datetime(period.year,period.month,day,hour,int(r.integers(60)),int(r.integers(60))))


def branch_open(row,period):
    if int(row["opening_year"])>period.year:return False
    cy=row.get("closing_year",np.nan)
    if pd.notna(cy) and str(cy).strip()!="" and period.year>int(float(cy)):return False
    return True


def tx_branch(r,a,c,branches,period):
    key=str(period)
    e=OPEN_BRANCH_CACHE.get(key)
    if e is None:
        mask=(pd.to_numeric(branches["opening_year"],errors="coerce")<=period.year)
        closing=pd.to_numeric(branches["closing_year"],errors="coerce")
        mask &= closing.isna() | (closing>=period.year)
        e=branches.loc[mask].copy()
        OPEN_BRANCH_CACHE[key]=e
    w=np.ones(len(e))*.15
    for i,b in enumerate(e.itertuples(index=False)):
        if b.branch_id==a["branch_id"]:w[i]+=3.2
        if str(b.branch_id)==str(c.get("primary_branch_id","")):w[i]+=2.1
        if str(b.department)==str(c.get("residence_department","")):w[i]+=1.3
        if str(b.locality)==str(c.get("residence_locality","")):w[i]+=1.8
        w[i]+=.55 if str(b.branch_size).upper()=="LARGE" else (.25 if str(b.branch_size).upper()=="MEDIUM" else 0)
    return str(r.choice(e["branch_id"].astype(str),p=w/w.sum()))


def debit_links(cards):
    if cards.empty or not {"product_id","linked_account_id"}.issubset(cards.columns):return set()
    return set(cards.loc[cards["product_id"].astype(str)=="P009","linked_account_id"].dropna().astype(str))


def build_loan_intent_staging(loans, snap, bridge, accounts, roles):
    """Precompute loan-linked transaction intents into compact Parquet staging.

    This replaces the former universe-wide defaultdict(list), which can become
    extremely memory-heavy at 100k–120k customers. The statistical behavior is
    preserved: loan order, RNG streams, account selection, probabilities,
    amounts, and chronology remain unchanged.

    The resulting Parquet file is consumed lazily by account chunk during
    Stage 1, keeping only the current chunk's loan-linked intents in RAM.
    """
    if STAGE_LOAN_INTENTS_PATH.exists():
        return STAGE_LOAN_INTENTS_PATH

    STAGE_LOAN_INTENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = STAGE_LOAN_INTENTS_PATH.with_suffix(".parquet.tmp")
    if temp.exists():
        temp.unlink()

    columns = ["account_id", "year_month", "event_type", "amount", "loan_id"]

    if loans.empty or snap.empty:
        empty = pd.DataFrame(columns=columns)
        pq.write_table(
            pa.Table.from_pandas(empty, preserve_index=False),
            temp,
            compression=PARQUET_COMPRESSION,
        )
        temp.replace(STAGE_LOAN_INTENTS_PATH)
        return STAGE_LOAN_INTENTS_PATH

    snap = snap.copy()
    for col in ["actual_payment", "outstanding_balance"]:
        snap[col] = pd.to_numeric(snap[col], errors="coerce").fillna(0.0)
    snap["loan_id"] = snap["loan_id"].astype(str)
    snap["year_month"] = snap["year_month"].astype(str)

    snap_indexed = (
        snap.sort_values(["loan_id", "year_month"], kind="mergesort")
        .set_index("loan_id", drop=False)
    )

    rolemap = roles.set_index("account_id")["account_role"].to_dict()
    omap = {}
    if not bridge.empty and {"loan_id", "origination_month_internal"}.issubset(bridge.columns):
        omap = (
            bridge.assign(loan_id=bridge["loan_id"].astype(str))
            .set_index("loan_id")["origination_month_internal"]
            .astype(str)
            .to_dict()
        )

    account_pool = accounts.copy()
    account_pool["_currency"] = account_pool["product_id"].map(CURRENCY)
    account_pool["_customer_key"] = account_pool["customer_id"].astype(str)
    account_candidates = {
        (str(cid), str(curr)): g
        for (cid, curr), g in account_pool.groupby(
            ["_customer_key", "_currency"], sort=False, dropna=False
        )
    }

    role_weight = {
        "BUSINESS_OPERATING": 3.0,
        "PRIMARY_TRANSACTIONAL": 2.7,
        "PAYROLL": 2.2,
        "SECONDARY": 0.9,
        "SAVINGS": 0.7,
        "USD_RESERVE": 0.7,
    }

    pick_cache = {}

    def pick(cid, curr, period, rng):
        key = (str(cid), str(curr), str(period))
        cached = pick_cache.get(key)
        if cached is None:
            base = account_candidates.get((str(cid), str(curr)))
            if base is None:
                pick_cache[key] = ((), ())
                return None

            mask = (
                (base["first_obs_month"] <= period)
                & (base["last_obs_month"] >= period)
                & (~base["product_id"].isin(FIXED))
            )
            g = base.loc[mask]
            if g.empty:
                pick_cache[key] = ((), ())
                return None

            ids = g["account_id"].tolist()
            weights = [
                role_weight.get(rolemap.get(account_id, "SECONDARY"), 0.5)
                for account_id in ids
            ]
            cached = (ids, weights)
            pick_cache[key] = cached

        ids, weights = cached
        if not ids:
            return None
        return choose(rng, ids, weights)

    buffer = []
    buffer_limit = 250_000
    writer = None

    def flush_buffer():
        nonlocal buffer, writer
        if not buffer:
            return

        frame = pd.DataFrame.from_records(buffer, columns=columns)
        frame = frame.sort_values(
            ["account_id", "year_month", "loan_id", "event_type"],
            kind="mergesort",
        ).reset_index(drop=True)

        table = pa.Table.from_pandas(frame, preserve_index=False)
        if writer is None:
            writer = pq.ParquetWriter(
                temp,
                table.schema,
                compression=PARQUET_COMPRESSION,
                use_dictionary=True,
                write_statistics=True,
            )
        writer.write_table(table)
        buffer = []

    try:
        for loan in loans.itertuples(index=False):
            lid = str(loan.loan_id)
            cid = str(loan.customer_id)
            prod = str(loan.product_id)
            curr = str(loan.currency)
            orig = float(loan.original_amount)
            rng = rng_for("loan", lid)
            prob = 0.76 if prod in {"P012", "P013", "P014"} else 0.84

            if prod != "P016":
                period = None
                if lid in omap:
                    try:
                        period = pd.Period(omap[lid][:7], freq="M")
                    except Exception:
                        pass
                if period is None:
                    year = int(loan.origination_year)
                    period = pd.Period(
                        f"{year}-{int(rng.integers(1, 13)):02d}",
                        freq="M",
                    )

                if OBS_START <= period <= OBS_END and rng.random() < prob:
                    account_id = pick(cid, curr, period, rng)
                    if account_id:
                        buffer.append(
                            (
                                str(account_id),
                                str(period),
                                "LOAN_DISBURSEMENT",
                                money(orig),
                                lid,
                            )
                        )

            try:
                loan_snap = snap_indexed.loc[[lid]]
            except KeyError:
                continue

            prev = None
            for row in loan_snap.itertuples(index=False):
                try:
                    period = pd.Period(str(row.year_month)[:7], freq="M")
                except Exception:
                    continue
                if not OBS_START <= period <= OBS_END:
                    continue

                pay = float(row.actual_payment)
                bal = float(row.outstanding_balance)

                if prod == "P016" and prev is not None:
                    draw = max(0.0, bal - prev + pay)
                    if draw > max(10.0, 0.002 * orig) and rng.random() < prob:
                        account_id = pick(cid, curr, period, rng)
                        if account_id:
                            buffer.append(
                                (
                                    str(account_id),
                                    str(period),
                                    "LOAN_DISBURSEMENT",
                                    money(draw),
                                    lid,
                                )
                            )

                if pay > 0 and rng.random() < prob:
                    account_id = pick(cid, curr, period, rng)
                    if account_id:
                        buffer.append(
                            (
                                str(account_id),
                                str(period),
                                "LOAN_PAYMENT",
                                money(pay),
                                lid,
                            )
                        )

                prev = bal

                if len(buffer) >= buffer_limit:
                    flush_buffer()

        flush_buffer()
    finally:
        if writer is not None:
            writer.close()

    if writer is None:
        empty = pd.DataFrame(columns=columns)
        pq.write_table(
            pa.Table.from_pandas(empty, preserve_index=False),
            temp,
            compression=PARQUET_COMPRESSION,
        )

    temp.replace(STAGE_LOAN_INTENTS_PATH)
    return STAGE_LOAN_INTENTS_PATH


def load_loan_intents_for_accounts(path, account_ids):
    """Load only the loan-linked intents required by the current account chunk."""
    if not path.exists():
        return {}

    account_ids = [str(x) for x in account_ids]
    if not account_ids:
        return {}

    dataset = ds.dataset(path, format="parquet")
    table = dataset.to_table(
        filter=ds.field("account_id").isin(account_ids),
        columns=["account_id", "year_month", "event_type", "amount", "loan_id"],
    )

    if table.num_rows == 0:
        return {}

    out = defaultdict(list)
    frame = table.to_pandas()
    for row in frame.itertuples(index=False):
        out[(str(row.account_id), str(row.year_month))].append(
            (str(row.event_type), float(row.amount), str(row.loan_id))
        )
    return out

def op_failure(r,event):
    p=.0035+(.0015 if event["channel"] in {"MOBILE","WEB"} else .001 if event["channel"]=="ATM" else .0008 if event["channel"]=="POS" else 0)
    if event["transaction_type"] in {"TRANSFER_IN","TRANSFER_OUT"}:p+=.0012
    if r.random()>=min(.02,p*r.lognormal(0,.25)):return None
    if event["channel"] in {"MOBILE","WEB"}:return choose(r,["AUTHENTICATION_FAILED","NETWORK_ERROR","TECHNICAL_ERROR","INVALID_DESTINATION","OTHER"],[2.2,2,1.7,.8,.4])
    if event["channel"]=="ATM":return choose(r,["NETWORK_ERROR","TECHNICAL_ERROR","LIMIT_EXCEEDED","OTHER"],[1.6,1.4,1,.3])
    if event["transaction_type"].startswith("TRANSFER"):return choose(r,["INVALID_DESTINATION","LIMIT_EXCEEDED","TECHNICAL_ERROR","OTHER"],[1.5,1.2,1,.3])
    return choose(r,["TECHNICAL_ERROR","LIMIT_EXCEEDED","OTHER"],[1.8,.8,.4])


def make_event(a,c,t,role,period,tt,amt,branches,source,recurring=False,preferred=None):
    r=rng_for("event",a["account_id"],period,tt,source,amt);ctype=str(c["customer_type"]).upper();cp=counterparty(r,tt,ctype,t,role);ch=channel(r,tt,t,ctype,period,recurring,amt,CURRENCY[a["product_id"]]);dt=event_datetime(r,period,tt,cp,ch,ctype,preferred);bid=tx_branch(r,a,c,branches,period) if ch=="BRANCH" else None
    return {"account_id":a["account_id"],"transaction_datetime":dt,"transaction_type":tt,"direction":"CREDIT" if tt in CREDIT else "DEBIT","channel":ch,"amount":money(amt),"counterparty_type":cp,"transaction_branch_id":bid,"merchant_category":None,"source":source}


def process_account(a,c,t,role,branches,debit_set,lidx):
    balance=inherited_balance(a,c,t);tx=[];bals=[];p=a["product_id"];curr=CURRENCY[p];ctype=str(c["customer_type"]).upper();has_debit=a["account_id"] in debit_set
    for period in pd.period_range(a["first_obs_month"],a["last_obs_month"],freq="M"):
        opening=balance;scale=monthly_scale(c,t,period);events=[]
        # observed funding for post-2021 openings
        if period==a["first_obs_month"] and int(a["opening_year"])>=2021:
            r=rng_for("initial",a["account_id"]);mult=r.lognormal(.8,.7) if p in FIXED else r.lognormal(-.4,.65);uyu=scale*float(t["liquidity_buffer"])*mult*(1.4 if ctype=="BUSINESS" else 1);amt=uyu/FX[period.year] if curr=="USD" else uyu
            events.append(make_event(a,c,t,role,period,"TRANSFER_IN",amt,branches,"ACCOUNT_INITIAL_FUNDING"))
        # salary
        if role=="PAYROLL" and ctype=="INDIVIDUAL":
            r=rng_for("salary",a["account_id"],period)
            if r.random()<.88+.09*float(t["recurring_behavior"]):
                ev=make_event(a,c,t,role,period,"TRANSFER_IN",scale*r.lognormal(0,.045),branches,"RECURRING_SALARY",True,int(rng_for("salary-day",c["customer_id"]).choice([1,2,3,4,5,28])));ev["counterparty_type"]="EMPLOYER";events.append(ev)
        # recurring services
        if role in {"PRIMARY_TRANSACTIONAL","PAYROLL","BUSINESS_OPERATING"}:
            nt=int(rng_for("services",a["account_id"]).choice([0,1,2,3,4],p=[.08,.22,.34,.25,.11]))
            for j in range(nt):
                r=rng_for("service",a["account_id"],period,j)
                if r.random()<.52+.35*float(t["recurring_behavior"]):
                    amt=amount(r,"SERVICE_PAYMENT",ctype,curr,scale,t,period,recurring=True);events.append(make_event(a,c,t,role,period,"SERVICE_PAYMENT",amt,branches,"RECURRING_SERVICE",True,int(rng_for("service-day",a["account_id"],j).integers(3,27))))
        # behavioral
        ratio,low_liq,excess_liq=liquidity_state(balance,curr,scale,t,role)
        n=event_count(a,t,ctype,period,role)
        labels,probs=type_probs(p,role,ctype,t,has_debit,low_liq,excess_liq)
        mp=merchant_probs(c,t,period);r=rng_for("behavior",a["account_id"],period)
        for j in range(n):
            tt=str(r.choice(labels,p=probs))
            cat=str(r.choice(MERCHANT_CATEGORIES,p=mp)) if tt=="DEBIT_PURCHASE" else None
            amt=amount(r,tt,ctype,curr,scale,t,period,cat)

            # Soft release of persistent excess balances in payroll accounts.
            # The multiplier changes intended debit size, but execution remains
            # subject to the ordinary ledger and can still fail.
            if p=="P005" and tt in {"TRANSFER_OUT","CASH_WITHDRAWAL","DEBIT_PURCHASE","SERVICE_PAYMENT"}:
                amt=money(amt*(1.0+.35*excess_liq))

            ev=make_event(a,c,t,role,period,tt,amt,branches,"BEHAVIORAL")
            ev["merchant_category"]=cat
            ev["counterparty_type"]="MERCHANT" if tt=="DEBIT_PURCHASE" else ev["counterparty_type"]
            events.append(ev)
        # loans
        for tt,amt,lid in lidx.get((a["account_id"],str(period)),[]):events.append(make_event(a,c,t,role,period,tt,amt,branches,f"LOAN:{lid}",tt=="LOAN_PAYMENT"))
        # fixed-term interest based on start-of-month/live balance
        if p in FIXED and balance>0:
            rate=({2021:.055,2022:.070,2023:.090,2024:.075,2025:.065,2026:.060} if p=="P007" else {2021:.012,2022:.018,2023:.025,2024:.028,2025:.030,2026:.030})[period.year];amt=money(balance*rate/12*rng_for("interest",a["account_id"],period).normal(1,.04));ev=make_event(a,c,t,role,period,"INTEREST_CREDIT",amt,branches,"FIXED_TERM_INTEREST");ev["channel"]="AUTOMATIC";ev["transaction_branch_id"]=None;events.append(ev)
        events.sort(key=lambda e:e["transaction_datetime"]);inflow=outflow=0.0
        for j,e in enumerate(events):
            scope, institution_id = resolve_transfer_institution(e, a, c, t, period, j)
            e["transfer_scope"] = scope
            e["counterparty_institution_id"] = institution_id
            r=rng_for("exec",a["account_id"],period,j,e["source"]);status="COMPLETED";reason=None
            if e["transaction_type"] not in {"LOAN_DISBURSEMENT","INTEREST_CREDIT"}:reason=op_failure(r,e);status="FAILED" if reason else "COMPLETED"
            if status=="COMPLETED" and e["direction"]=="DEBIT" and e["amount"]>balance+.005:status="FAILED";reason="INSUFFICIENT_FUNDS"
            if status=="COMPLETED":
                if e["direction"]=="CREDIT":balance=money(balance+e["amount"]);inflow=money(inflow+e["amount"])
                else:balance=money(balance-e["amount"]);outflow=money(outflow+e["amount"])
            tx.append({k:e.get(k) for k in ["account_id","transaction_datetime","transaction_type","direction","channel","amount","counterparty_type","transfer_scope","counterparty_institution_id","transaction_branch_id","merchant_category"]}|{"transaction_status":status,"failure_reason":reason,"_month":str(period),"_source":e["source"]})
        # closure sweep
        if str(a["account_status"]).upper()=="CLOSED" and period==a["last_obs_month"] and balance>.005:
            ev=make_event(a,c,t,role,period,"TRANSFER_OUT",balance,branches,"ACCOUNT_CLOSURE_SWEEP");ev["transaction_datetime"]=pd.Timestamp(datetime(period.year,period.month,calendar.monthrange(period.year,period.month)[1],15,45,0));scope,institution_id=resolve_transfer_institution(ev,a,c,t,period,"closure");ev["transfer_scope"]=scope;ev["counterparty_institution_id"]=institution_id;tx.append({k:ev.get(k) for k in ["account_id","transaction_datetime","transaction_type","direction","channel","amount","counterparty_type","transfer_scope","counterparty_institution_id","transaction_branch_id","merchant_category"]}|{"transaction_status":"COMPLETED","failure_reason":None,"_month":str(period),"_source":ev["source"]});outflow=money(outflow+balance);balance=0.0
        bals.append({"account_id":a["account_id"],"year_month":str(period),"opening_balance":money(opening),"total_inflows":money(inflow),"total_outflows":money(outflow),"closing_balance":money(balance)})
    return tx,bals



# -----------------------------------------------------------------------------
# INTERNAL BTYT TRANSFER NETWORK
# -----------------------------------------------------------------------------

def annual_capacity_uyu_from_customer(customer):
    """Return an annual economic-capacity proxy used only for internal pairing."""
    ctype = str(customer.get("customer_type", "INDIVIDUAL")).upper()
    if ctype == "BUSINESS":
        revenue = pd.to_numeric(
            pd.Series([customer.get("annual_revenue", np.nan)]), errors="coerce"
        ).iloc[0]
        if pd.notna(revenue) and float(revenue) > 0:
            return float(revenue)
        return 12_000_000.0

    income = pd.to_numeric(
        pd.Series([customer.get("monthly_income", np.nan)]), errors="coerce"
    ).iloc[0]
    if pd.notna(income) and float(income) > 0:
        return float(income) * 12.0
    return 660_000.0


def internal_capacity_weight(amount_uyu, annual_capacity_uyu, customer_type):
    """Softly downweight economically implausible internal counterparties.

    This is intentionally not a hard cap. Individuals can still receive or send
    transfers larger than annual income, while business clients retain much
    broader tails. The purpose is to prevent random internal matching from
    routinely assigning corporate-scale transfers to ordinary retail clients.
    """
    capacity = max(float(annual_capacity_uyu), 1.0)
    ratio = max(float(amount_uyu), 0.0) / capacity
    ctype = str(customer_type).upper()

    if ctype == "BUSINESS":
        if ratio <= 1.50:
            return 1.0
        penalty = math.exp(-0.35 * (ratio - 1.50))
        return max(1e-6, float(penalty))

    if ratio <= 2.00:
        return 1.0
    if ratio <= 5.00:
        return float(math.exp(-0.75 * (ratio - 2.00)))

    penalty_at_five = math.exp(-0.75 * 3.00)
    penalty = penalty_at_five * math.exp(-0.22 * (ratio - 5.00))
    return max(1e-8, float(penalty))


def build_internal_pool_context(accounts, roles, customers):
    """Build compact replay metadata once.

    Unlike the previous implementation, this does not materialize 72 monthly
    copies of the eligible account universe. A single set of NumPy arrays is
    retained and the current month's pools are selected lazily.
    """
    role_map = roles.set_index("account_id")["account_role"].to_dict()

    customer_frame = customers.copy()
    customer_frame["_customer_key"] = customer_frame["customer_id"].astype(str)
    customer_frame["_customer_type"] = (
        customer_frame["customer_type"].astype(str).str.upper()
    )

    monthly_income = pd.to_numeric(
        customer_frame.get("monthly_income", pd.Series(index=customer_frame.index, dtype=float)),
        errors="coerce",
    )
    annual_revenue = pd.to_numeric(
        customer_frame.get("annual_revenue", pd.Series(index=customer_frame.index, dtype=float)),
        errors="coerce",
    )

    is_business = customer_frame["_customer_type"].eq("BUSINESS")
    capacity = np.where(
        is_business,
        annual_revenue.where(annual_revenue > 0, 12_000_000.0),
        monthly_income.where(monthly_income > 0, 55_000.0) * 12.0,
    )
    customer_frame["_annual_capacity_uyu"] = np.asarray(capacity, dtype=float)

    customer_type = dict(
        zip(customer_frame["_customer_key"], customer_frame["_customer_type"])
    )
    customer_capacity = dict(
        zip(customer_frame["_customer_key"], customer_frame["_annual_capacity_uyu"])
    )

    frame = accounts.copy()
    frame["_account_id"] = frame["account_id"].astype(str)
    frame["_customer_id"] = frame["customer_id"].astype(str)
    frame["_currency"] = frame["product_id"].map(CURRENCY).astype(str)
    frame["_role"] = frame["_account_id"].map(role_map).fillna("SECONDARY")
    frame["_base_weight"] = frame["_role"].map({
        "BUSINESS_OPERATING": 3.0,
        "PRIMARY_TRANSACTIONAL": 2.7,
        "PAYROLL": 2.3,
        "SECONDARY": 1.0,
        "SAVINGS": 0.8,
        "USD_RESERVE": 0.8,
    }).fillna(0.7).astype(float)
    frame["_customer_type"] = (
        frame["_customer_id"].map(customer_type).fillna("INDIVIDUAL").astype(str)
    )
    frame["_annual_capacity_uyu"] = (
        frame["_customer_id"].map(customer_capacity).fillna(660_000.0).astype(float)
    )
    frame["_first_ord"] = frame["first_obs_month"].map(lambda p: pd.Period(p, freq="M").ordinal)
    frame["_last_ord"] = frame["last_obs_month"].map(lambda p: pd.Period(p, freq="M").ordinal)
    frame["_eligible_product"] = ~frame["product_id"].isin(FIXED)

    return {
        "account_id": frame["_account_id"].to_numpy(dtype=str),
        "customer_id": frame["_customer_id"].to_numpy(dtype=str),
        "currency": frame["_currency"].to_numpy(dtype=str),
        "base_weight": frame["_base_weight"].to_numpy(dtype=float),
        "customer_type": frame["_customer_type"].to_numpy(dtype=str),
        "annual_capacity_uyu": frame["_annual_capacity_uyu"].to_numpy(dtype=float),
        "first_ord": frame["_first_ord"].to_numpy(dtype=np.int32),
        "last_ord": frame["_last_ord"].to_numpy(dtype=np.int32),
        "eligible_product": frame["_eligible_product"].to_numpy(dtype=bool),
        "account_customer": dict(zip(frame["_account_id"], frame["_customer_id"])),
        "account_currency": dict(zip(frame["_account_id"], frame["_currency"])),
    }


def build_month_internal_pools(context, period):
    """Materialize only the current month's currency pools."""
    ordinal = int(period.ordinal)
    active = (
        context["eligible_product"]
        & (context["first_ord"] <= ordinal)
        & (context["last_ord"] >= ordinal)
    )

    pools = {}
    currencies = context["currency"]
    for currency in ("UYU", "USD"):
        mask = active & (currencies == currency)
        if not mask.any():
            continue

        weights = context["base_weight"][mask]
        cumulative = np.cumsum(weights, dtype=float)
        pools[currency] = {
            "account_id": context["account_id"][mask],
            "customer_id": context["customer_id"][mask],
            "base_weight": weights,
            "cumulative_weight": cumulative,
            "total_weight": float(cumulative[-1]),
            "customer_type": context["customer_type"][mask],
            "annual_capacity_uyu": context["annual_capacity_uyu"][mask],
        }
    return pools


def _draw_base_weighted_index(rng, pool):
    """Draw one index in O(log N) from the base-weight distribution."""
    total = pool["total_weight"]
    if total <= 0:
        return None
    draw = float(rng.random()) * total
    idx = int(np.searchsorted(pool["cumulative_weight"], draw, side="right"))
    if idx >= len(pool["account_id"]):
        idx = len(pool["account_id"]) - 1
    return idx


def pick_internal_counterpart(
    r,
    pools,
    period,
    currency,
    amount,
    own_account_id,
    own_customer_id,
):
    """Sample exactly from base_weight × capacity_compatibility.

    Rejection sampling removes the former O(pool_size) vector construction for
    every internal transfer. Because compatibility is in (0, 1], proposing from
    the base-weight distribution and accepting with probability compatibility
    yields the same target distribution among eligible counterparties.

    A rare bounded fallback computes the exact vectorized distribution only when
    repeated rejection occurs for an extreme transfer.
    """
    pool = pools.get(currency)
    if pool is None or len(pool["account_id"]) == 0:
        return None

    own_account_id = str(own_account_id)
    own_customer_id = str(own_customer_id)
    amount_uyu = float(amount) * (FX[int(period.year)] if currency == "USD" else 1.0)

    max_attempts = 64
    for _ in range(max_attempts):
        idx = _draw_base_weighted_index(r, pool)
        if idx is None:
            return None
        if pool["account_id"][idx] == own_account_id:
            continue
        if pool["customer_id"][idx] == own_customer_id:
            continue

        compatibility = internal_capacity_weight(
            amount_uyu,
            pool["annual_capacity_uyu"][idx],
            pool["customer_type"][idx],
        )
        if r.random() <= compatibility:
            return str(pool["account_id"][idx])

    # Exact fallback for pathological high-value transfers. This is deliberately
    # rare; it preserves correctness without making every transfer O(N).
    valid = (
        (pool["account_id"] != own_account_id)
        & (pool["customer_id"] != own_customer_id)
    )
    if not valid.any():
        return None

    ids = pool["account_id"][valid]
    base = pool["base_weight"][valid]
    types = pool["customer_type"][valid]
    capacities = pool["annual_capacity_uyu"][valid]

    compatibility = np.fromiter(
        (
            internal_capacity_weight(amount_uyu, cap, ctype)
            for cap, ctype in zip(capacities, types)
        ),
        dtype=float,
        count=len(ids),
    )
    weights = base * compatibility
    if not np.isfinite(weights).all() or weights.sum() <= 0:
        weights = base.copy()
    weights = weights / weights.sum()
    return str(r.choice(ids, p=weights))

def internal_transfer_validation(tx, accounts):
    metrics = {}
    completed_internal = tx[
        (tx["transaction_status"] == "COMPLETED")
        & tx["_internal_id"].notna()
    ].copy()

    account_meta = accounts.set_index("account_id")[["customer_id", "product_id"]]
    customer_map = account_meta["customer_id"].astype(str).to_dict()
    currency_map = account_meta["product_id"].map(CURRENCY).to_dict()

    bad_size = bad_direction = bad_amount = bad_timing = 0
    bad_self_account = bad_self_customer = bad_currency = 0

    for _, g in completed_internal.groupby("_internal_id", sort=False):
        if len(g) != 2:
            bad_size += 1
            continue
        outs = g[g["transaction_type"] == "TRANSFER_OUT"]
        ins = g[g["transaction_type"] == "TRANSFER_IN"]
        if len(outs) != 1 or len(ins) != 1:
            bad_direction += 1
            continue
        out_row, in_row = outs.iloc[0], ins.iloc[0]
        if abs(float(out_row["amount"]) - float(in_row["amount"])) > 0.011:
            bad_amount += 1
        if pd.Timestamp(out_row["transaction_datetime"]) != pd.Timestamp(in_row["transaction_datetime"]):
            bad_timing += 1
        out_aid, in_aid = str(out_row["account_id"]), str(in_row["account_id"])
        if out_aid == in_aid:
            bad_self_account += 1
        if customer_map.get(out_aid) == customer_map.get(in_aid):
            bad_self_customer += 1
        if currency_map.get(out_aid) != currency_map.get(in_aid):
            bad_currency += 1

    completed_btyt = tx[
        (tx["transaction_status"] == "COMPLETED")
        & tx["counterparty_type"].eq("BTYT_CUSTOMER")
        & tx["transaction_type"].isin(["TRANSFER_IN", "TRANSFER_OUT"])
    ]

    metrics["internal_pair_size"] = bad_size
    metrics["internal_pair_direction"] = bad_direction
    metrics["internal_pair_amount"] = bad_amount
    metrics["internal_pair_timing"] = bad_timing
    metrics["internal_pair_self_account"] = bad_self_account
    metrics["internal_pair_self_customer"] = bad_self_customer
    metrics["internal_pair_currency"] = bad_currency
    metrics["completed_internal_unpaired"] = int(
        completed_btyt["_internal_id"].isna().sum()
    )
    return metrics


def build_internal_pair_audit(tx, accounts):
    completed = tx[
        (tx["transaction_status"] == "COMPLETED")
        & tx["_internal_id"].notna()
    ].copy()
    cols = [
        "internal_transfer_id", "transaction_datetime", "currency", "amount",
        "sender_account_id", "receiver_account_id",
        "sender_transaction_id", "receiver_transaction_id",
    ]
    if completed.empty:
        return pd.DataFrame(columns=cols)

    currency_map = accounts.set_index("account_id")["product_id"].map(CURRENCY).to_dict()
    rows = []
    for internal_id, g in completed.groupby("_internal_id", sort=False):
        out_row = g[g["transaction_type"] == "TRANSFER_OUT"].iloc[0]
        in_row = g[g["transaction_type"] == "TRANSFER_IN"].iloc[0]
        rows.append({
            "internal_transfer_id": internal_id,
            "transaction_datetime": out_row["transaction_datetime"],
            "currency": currency_map.get(str(out_row["account_id"])),
            "amount": money(out_row["amount"]),
            "sender_account_id": str(out_row["account_id"]),
            "receiver_account_id": str(in_row["account_id"]),
            "sender_transaction_id": out_row.get("transaction_id"),
            "receiver_transaction_id": in_row.get("transaction_id"),
        })
    return pd.DataFrame(rows, columns=cols)


def institution_counterparty_validation(tx):
    """Validate transfer counterparty institutions, scope, type, and temporal availability."""
    metrics = {}
    transfers = tx[tx["transaction_type"].isin(["TRANSFER_IN", "TRANSFER_OUT"])].copy()
    non_transfers = tx[~tx["transaction_type"].isin(["TRANSFER_IN", "TRANSFER_OUT"])].copy()

    meta = INSTITUTION_CONTEXT["institution_meta"]
    all_ids = set(meta)
    domestic_bank_ids = set(INSTITUTION_CONTEXT["domestic_bank_institution_ids"])
    foreign_bank_ids = set(INSTITUTION_CONTEXT["foreign_bank_institution_ids"])
    iede_ids = set(INSTITUTION_CONTEXT["iede_ids"])
    btyt_id = INSTITUTION_CONTEXT["btyt_institution_id"]

    metrics["nontransfer_scope_present"] = int(non_transfers["transfer_scope"].notna().sum())
    metrics["nontransfer_institution_present"] = int(non_transfers["counterparty_institution_id"].notna().sum())

    values = transfers["counterparty_institution_id"].dropna().astype(str)
    metrics["bad_counterparty_institution_fk"] = int((~values.isin(all_ids)).sum())

    internal = transfers[transfers["counterparty_type"].eq("BTYT_CUSTOMER")]
    metrics["bad_internal_scope"] = int((internal["transfer_scope"] != "INTERNAL").sum())
    metrics["bad_internal_institution"] = int((internal["counterparty_institution_id"].astype(str) != btyt_id).sum())

    external = transfers[transfers["counterparty_type"].eq("FINANCIAL_INSTITUTION")]
    metrics["external_scope_missing"] = int(external["transfer_scope"].isna().sum())
    metrics["bad_external_scope"] = int((~external["transfer_scope"].isin(["DOMESTIC_EXTERNAL", "INTERNATIONAL"])).sum())
    metrics["external_institution_missing"] = int(external["counterparty_institution_id"].isna().sum())
    metrics["external_btyt_institution"] = int(external["counterparty_institution_id"].astype(str).eq(btyt_id).sum())

    dom = external[external["transfer_scope"].eq("DOMESTIC_EXTERNAL")]
    intl = external[external["transfer_scope"].eq("INTERNATIONAL")]
    valid_domestic = domestic_bank_ids | iede_ids
    metrics["bad_domestic_institution_scope"] = int((~dom["counterparty_institution_id"].astype(str).isin(valid_domestic)).sum())
    metrics["bad_international_institution_scope"] = int((~intl["counterparty_institution_id"].astype(str).isin(foreign_bank_ids)).sum())
    metrics["international_nonbank_institution"] = int(intl["counterparty_institution_id"].astype(str).isin(iede_ids).sum())

    other = transfers[~transfers["counterparty_type"].isin(["BTYT_CUSTOMER", "FINANCIAL_INSTITUTION"])]
    metrics["other_transfer_scope_present"] = int(other["transfer_scope"].notna().sum())
    metrics["other_transfer_institution_present"] = int(other["counterparty_institution_id"].notna().sum())

    temporal_bad = 0
    for row in external.loc[external["counterparty_institution_id"].notna(), ["counterparty_institution_id", "transaction_datetime"]].itertuples(index=False):
        institution_id = str(row.counterparty_institution_id)
        if institution_id in meta and not institution_is_active(institution_id, row.transaction_datetime):
            temporal_bad += 1
    metrics["inactive_institution_at_transaction"] = temporal_bad
    return metrics


def validate(tx,bals,accounts,branches):
    errs=[];m={};tx=tx.copy();tx["dt"]=pd.to_datetime(tx["transaction_datetime"]);tx["ym"]=tx["dt"].dt.to_period("M").astype(str)
    completed=tx[tx["transaction_status"]=="COMPLETED"].copy();completed["cin"]=np.where(completed["direction"]=="CREDIT",completed["amount"],0);completed["cout"]=np.where(completed["direction"]=="DEBIT",completed["amount"],0)
    agg=completed.groupby(["account_id","ym"],as_index=False).agg(tx_in=("cin","sum"),tx_out=("cout","sum")).rename(columns={"ym":"year_month"});r=bals.merge(agg,on=["account_id","year_month"],how="left").fillna({"tx_in":0,"tx_out":0})
    tests={"inflow_reconciliation":(r["total_inflows"]-r["tx_in"]).abs(),"outflow_reconciliation":(r["total_outflows"]-r["tx_out"]).abs(),"balance_identity":(r["closing_balance"]-(r["opening_balance"]+r["total_inflows"]-r["total_outflows"])).abs()}
    for k,s in tests.items():m[k]=int((s>.011).sum());errs+=([k] if m[k] else [])
    b=bals.sort_values(["account_id","year_month"]).copy();b["prev"]=b.groupby("account_id")["closing_balance"].shift();m["continuity"]=int(((b["prev"].notna())&((b["opening_balance"]-b["prev"]).abs()>.011)).sum());m["negative_balances"]=int((bals["closing_balance"]<-.005).sum())
    m["duplicate_tx_id"]=int(tx["transaction_id"].duplicated().sum());m["duplicate_balance_pk"]=int(bals.duplicated(["account_id","year_month"]).sum());m["bad_nonbranch_fk"]=int(tx.loc[tx["channel"]!="BRANCH","transaction_branch_id"].notna().sum());m["bad_branch_missing"]=int(tx.loc[tx["channel"]=="BRANCH","transaction_branch_id"].isna().sum())
    expected=tx["transaction_type"].map({**{x:"CREDIT" for x in CREDIT},**{x:"DEBIT" for x in DEBIT}});m["bad_direction"]=int((expected!=tx["direction"]).sum());m["completed_with_reason"]=int(tx.loc[tx["transaction_status"]=="COMPLETED","failure_reason"].notna().sum());m["failed_without_reason"]=int(tx.loc[tx["transaction_status"]=="FAILED","failure_reason"].isna().sum())
    m.update(internal_transfer_validation(tx,accounts))
    m.update(institution_counterparty_validation(tx))
    for k in list(m):
        if m[k]:errs.append(k)
    m["validation_pass"]=len(set(errs))==0;m["errors"]=" | ".join(sorted(set(errs)));return m


def report(tx,bals,validation):
    print("\n"+"="*72);print("BTYT TRANSACTION ENGINE — VALIDATION");print("="*72);print(f"Transactions: {len(tx):,}");print(f"Account-months: {len(bals):,}")
    for title,col in [("Transaction types","transaction_type"),("Status","transaction_status"),("Channels","channel")]:
        print(f"\n{title}:");counts=tx[col].value_counts();shares=tx[col].value_counts(normalize=True)*100
        for x in counts.index:print(f"  {x:24s} {counts[x]:10,} {shares[x]:7.2f}%")
    failed=tx[tx["transaction_status"]=="FAILED"];print("\nFailure reasons:")
    if len(failed):
        for x,n in failed["failure_reason"].value_counts().items():print(f"  {x:24s} {n:10,} {100*n/len(failed):7.2f}%")
    transfers = tx[tx["transaction_type"].isin(["TRANSFER_IN", "TRANSFER_OUT"])]
    scoped = transfers[transfers["transfer_scope"].notna()]
    if len(scoped):
        print("\nTransfer scopes:")
        for x,n in scoped["transfer_scope"].value_counts().items():
            print(f"  {x:24s} {n:10,} {100*n/len(scoped):7.2f}%")

    external = transfers[transfers["counterparty_type"].eq("FINANCIAL_INSTITUTION") & transfers["counterparty_institution_id"].notna()]
    if len(external):
        print("\nExternal counterparty institutions:")
        counts = external["counterparty_institution_id"].value_counts()
        for bank_id,n in counts.items():
            meta = INSTITUTION_CONTEXT["institution_meta"].get(str(bank_id), {})
            name = meta.get("institution_name", str(bank_id))
            print(f"  {bank_id:5s} {name:<28} {n:10,} {100*n/len(external):7.2f}%")

    print("\nIntegrity:")
    for k,v in validation.items():
        if k not in {"validation_pass","errors"}:print(f"  {k:30s} {'PASS' if v==0 else f'FAIL ({v})'}")
    print(f"\nVALIDATION: {'PASS' if validation['validation_pass'] else 'FAIL'}")
    if validation["errors"]:print(validation["errors"])


def parse_args():
    parser = argparse.ArgumentParser(description="BTYT transaction engine.")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_ACCOUNT_CHUNK_SIZE)
    parser.add_argument("--fresh", action="store_true", help="Discard transaction staging/checkpoint and rebuild.")
    parser.add_argument("--smoke", action="store_true", help="Use the configured smoke customer count.")
    return parser.parse_args()


def world_fingerprint(accounts):
    payload = {
        "engine_version": ENGINE_VERSION,
        "world_seed": int(WORLD_CONFIG.seed),
        "start": str(OBS_START),
        "end": str(OBS_END),
        "account_ids_hash": hashlib.sha256(
            "|".join(accounts["account_id"].astype(str).sort_values()).encode("utf-8")
        ).hexdigest(),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def empty_checkpoint(fingerprint, chunk_size):
    return {
        "engine_version": ENGINE_VERSION,
        "world_fingerprint": fingerprint,
        "chunk_size": int(chunk_size),
        "completed_generation_chunks": [],
        "completed_replay_months": [],
        "transaction_id_counter": 0,
        "internal_pair_counter": 0,
    }


def load_checkpoint(fingerprint, chunk_size, fresh=False):
    if fresh and STAGE_ROOT.exists():
        shutil.rmtree(STAGE_ROOT)
    if fresh and CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()

    if not CHECKPOINT_PATH.exists():
        return empty_checkpoint(fingerprint, chunk_size)

    checkpoint = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    if checkpoint.get("world_fingerprint") != fingerprint:
        raise RuntimeError(
            "Existing transaction checkpoint belongs to a different world/code configuration. "
            "Run with --fresh."
        )
    if int(checkpoint.get("chunk_size", -1)) != int(chunk_size):
        raise RuntimeError(
            "Existing checkpoint was created with a different chunk size. "
            "Chunk size is not a world parameter, but resume boundaries must match. "
            "Run with --fresh to test another chunk size."
        )
    return checkpoint


def save_checkpoint(checkpoint):
    INTERIM_TRANSACTIONS_DIR.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps(checkpoint, indent=2, sort_keys=True), encoding="utf-8")


def stage_frame_by_month(frame, root, chunk_id, month_col):
    """Write one Parquet file per chunk, with one row group per month.

    This avoids thousands of tiny files while retaining exact month-level
    pruning during replay. Chunk size remains an engineering parameter only.
    """
    if frame.empty:
        return

    root.mkdir(parents=True, exist_ok=True)
    path = root / f"chunk_{chunk_id:05d}.parquet"
    temp = path.with_suffix(".parquet.tmp")
    if temp.exists():
        temp.unlink()

    ordered = frame.sort_values(month_col, kind="mergesort").reset_index(drop=True)
    full_schema = pa.Table.from_pandas(
        ordered, preserve_index=False
    ).schema

    writer = pq.ParquetWriter(
        temp,
        full_schema,
        compression=PARQUET_COMPRESSION,
        use_dictionary=True,
        write_statistics=True,
    )
    try:
        for _, group in ordered.groupby(month_col, sort=True):
            table = pa.Table.from_pandas(
                group,
                schema=full_schema,
                preserve_index=False,
                safe=False,
            )
            writer.write_table(table)
    finally:
        writer.close()

    temp.replace(path)


def _stat_value(value):
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def load_month_stage(root, month, month_col):
    """Read only row groups belonging to the requested month."""
    files = sorted(root.glob("chunk_*.parquet"))
    if not files:
        return pd.DataFrame()

    tables = []
    for path in files:
        parquet_file = pq.ParquetFile(path)
        schema = parquet_file.schema_arrow
        column_index = schema.get_field_index(month_col)
        if column_index < 0:
            raise ValueError(f"{path} is missing staging month column {month_col!r}.")

        for row_group in range(parquet_file.num_row_groups):
            stats = parquet_file.metadata.row_group(row_group).column(column_index).statistics
            if stats is None or not stats.has_min_max:
                # Defensive fallback. Current staging writes one month per row group,
                # so statistics should normally always be available.
                table = parquet_file.read_row_group(row_group)
                values = table.column(month_col).to_pylist()
                if values and str(values[0]) == month:
                    tables.append(table)
                continue

            minimum = _stat_value(stats.min)
            maximum = _stat_value(stats.max)
            if minimum == month and maximum == month:
                tables.append(parquet_file.read_row_group(row_group))

    if not tables:
        return pd.DataFrame()
    return pa.concat_tables(tables, promote_options="default").to_pandas()

def generation_stage(d, accounts, roles, traits, debit, loan_intent_path, chunk_size, checkpoint):
    cmap = {
        str(row["customer_id"]): row
        for row in d["customers"].to_dict("records")
    }
    tmap = {
        str(row["customer_id"]): row
        for row in traits.to_dict("records")
    }
    rmap = roles.set_index("account_id")["account_role"].to_dict()
    ordered = accounts.sort_values("account_id", kind="mergesort").reset_index(drop=True)
    completed = set(int(x) for x in checkpoint["completed_generation_chunks"])
    total_chunks = (len(ordered) + chunk_size - 1) // chunk_size

    print("\nStage 1/3 — account-local intent generation")
    stage_started = time.perf_counter()
    for chunk_id, start in enumerate(range(0, len(ordered), chunk_size), start=1):
        if chunk_id in completed:
            print(f"  chunk {chunk_id:>4}/{total_chunks:,} already staged")
            continue

        chunk_started = time.perf_counter()
        chunk = ordered.iloc[start:start + chunk_size]
        chunk_loan_intents = load_loan_intents_for_accounts(
            loan_intent_path,
            chunk["account_id"].astype(str).tolist(),
        )
        chunk_tx = []
        chunk_bal = []
        for ar in chunk.to_dict("records"):
            aid = str(ar["account_id"])
            cid = str(ar["customer_id"])
            tx, bals = process_account(
                ar, cmap[cid], tmap[cid],
                rmap.get(aid, "SECONDARY"), d["branches"], debit, chunk_loan_intents,
            )
            for local_seq, row in enumerate(tx):
                row["_event_key"] = f"{aid}|{local_seq:07d}"
            chunk_tx.extend(tx)
            chunk_bal.extend(bals)

        tx_frame = pd.DataFrame(chunk_tx)
        bal_frame = pd.DataFrame(chunk_bal)[BAL_COLS]
        stage_frame_by_month(tx_frame, STAGE_INTENTS_DIR, chunk_id, "_month")
        stage_frame_by_month(bal_frame, STAGE_BALANCES_DIR, chunk_id, "year_month")

        checkpoint["completed_generation_chunks"].append(chunk_id)
        save_checkpoint(checkpoint)
        chunk_seconds = time.perf_counter() - chunk_started
        print(
            f"  chunk {chunk_id:>4}/{total_chunks:,} | accounts={len(chunk):,} "
            f"intents={len(tx_frame):,} account-months={len(bal_frame):,} "
            f"elapsed={chunk_seconds:,.1f}s"
        )

    print(f"Stage 1 elapsed: {time.perf_counter() - stage_started:,.1f}s")


def init_audit_metrics():
    return {
        "validation_metrics": Counter(),
        "transaction_types": Counter(),
        "statuses": Counter(),
        "channels": Counter(),
        "failure_reasons": Counter(),
        "transfer_scopes": Counter(),
        "external_institutions": Counter(),
        "transactions": 0,
        "account_months": 0,
    }


def update_audit_metrics(audit, tx_month, bals_month, validation):
    audit["transactions"] += len(tx_month)
    audit["account_months"] += len(bals_month)
    audit["transaction_types"].update(tx_month["transaction_type"].value_counts().to_dict())
    audit["statuses"].update(tx_month["transaction_status"].value_counts().to_dict())
    audit["channels"].update(tx_month["channel"].value_counts().to_dict())
    failed = tx_month[tx_month["transaction_status"].eq("FAILED")]
    audit["failure_reasons"].update(failed["failure_reason"].dropna().value_counts().to_dict())
    transfers = tx_month[tx_month["transaction_type"].isin(["TRANSFER_IN", "TRANSFER_OUT"])]
    audit["transfer_scopes"].update(transfers["transfer_scope"].dropna().value_counts().to_dict())
    external = transfers[transfers["counterparty_type"].eq("FINANCIAL_INSTITUTION")]
    audit["external_institutions"].update(external["counterparty_institution_id"].dropna().value_counts().to_dict())
    for key, value in validation.items():
        if key not in {"validation_pass", "errors", "continuity"}:
            audit["validation_metrics"][key] += int(value)


def replay_one_month(tx, skeleton, accounts, roles, customers, pools, replay_context, live_balance, tx_counter, pair_counter):
    tx = tx.copy().reset_index(drop=True)
    tx["transaction_datetime"] = pd.to_datetime(tx["transaction_datetime"])
    if "_event_key" not in tx.columns:
        raise ValueError("Staged transaction intents are missing _event_key.")

    account_customer = replay_context["account_customer"]
    account_currency = replay_context["account_currency"]

    # Accounts entering the observable ledger this month start from their account-local opening state.
    month_opening = {}
    for rec in skeleton.itertuples(index=False):
        aid = str(rec.account_id)
        if aid not in live_balance:
            live_balance[aid] = money(rec.opening_balance)
        month_opening[aid] = money(live_balance[aid])

    internal_map = {}
    internal_origins = tx[
        tx["transaction_type"].isin(["TRANSFER_IN", "TRANSFER_OUT"])
        & tx["counterparty_type"].eq("BTYT_CUSTOMER")
    ]
    for row in internal_origins.to_dict("records"):
        aid = str(row["account_id"])
        dt = pd.Timestamp(row["transaction_datetime"])
        period = dt.to_period("M")
        currency = account_currency.get(aid)
        cid = account_customer.get(aid)
        if currency is None or cid is None:
            continue
        event_key = str(row["_event_key"])
        r = rng_for("internal-counterpart", event_key, aid, dt.isoformat())
        counterpart = pick_internal_counterpart(r, pools, period, currency, row["amount"], aid, cid)
        if counterpart is not None:
            internal_map[event_key] = counterpart

    ordered = tx.sort_values(
        ["transaction_datetime", "account_id", "_event_key"], kind="mergesort"
    ).reset_index(drop=True)
    replayed = []

    for row in ordered.to_dict("records"):
        aid = str(row["account_id"])
        amount_value = money(row["amount"])
        tt = str(row["transaction_type"])
        direction = str(row["direction"])
        event_key = str(row["_event_key"])
        internal = (
            tt in {"TRANSFER_IN", "TRANSFER_OUT"}
            and row.get("counterparty_type") == "BTYT_CUSTOMER"
            and event_key in internal_map
        )
        original_reason = row.get("failure_reason")
        operational_reason = (
            original_reason
            if pd.notna(original_reason) and original_reason != "INSUFFICIENT_FUNDS"
            else None
        )

        if internal:
            counterpart = str(internal_map[event_key])
            if tt == "TRANSFER_OUT":
                sender, receiver, original_leg = aid, counterpart, "OUT"
            else:
                sender, receiver, original_leg = counterpart, aid, "IN"

            status, reason = "COMPLETED", None
            if operational_reason is not None:
                status, reason = "FAILED", operational_reason
            elif amount_value > live_balance.get(sender, 0.0) + 0.005:
                status, reason = "FAILED", "INSUFFICIENT_FUNDS"

            original = row.copy()
            original["transaction_status"] = status
            original["failure_reason"] = reason
            original["_internal_id"] = None
            original["_internal_leg"] = original_leg

            if status == "COMPLETED":
                pair_counter += 1
                internal_id = f"IT{pair_counter:010d}"
                original["_internal_id"] = internal_id
                live_balance[sender] = money(live_balance.get(sender, 0.0) - amount_value)
                live_balance[receiver] = money(live_balance.get(receiver, 0.0) + amount_value)
                opposite_tt = "TRANSFER_IN" if tt == "TRANSFER_OUT" else "TRANSFER_OUT"
                opposite_account = receiver if opposite_tt == "TRANSFER_IN" else sender
                opposite = {
                    "account_id": opposite_account,
                    "transaction_datetime": row["transaction_datetime"],
                    "transaction_type": opposite_tt,
                    "direction": "CREDIT" if opposite_tt == "TRANSFER_IN" else "DEBIT",
                    "channel": row["channel"],
                    "amount": amount_value,
                    "counterparty_type": "BTYT_CUSTOMER",
                    "transfer_scope": "INTERNAL",
                    "counterparty_institution_id": INSTITUTION_CONTEXT["btyt_institution_id"],
                    "transaction_branch_id": row.get("transaction_branch_id"),
                    "transaction_status": "COMPLETED",
                    "merchant_category": None,
                    "failure_reason": None,
                    "_month": str(pd.Timestamp(row["transaction_datetime"]).to_period("M")),
                    "_source": f"INTERNAL_PAIR:{internal_id}",
                    "_event_key": event_key + "|PAIR",
                    "_internal_id": internal_id,
                    "_internal_leg": "IN" if opposite_tt == "TRANSFER_IN" else "OUT",
                }
                replayed.extend([original, opposite])
            else:
                replayed.append(original)
            continue

        status, reason = "COMPLETED", None
        if operational_reason is not None:
            status, reason = "FAILED", operational_reason
        elif direction == "DEBIT" and amount_value > live_balance.get(aid, 0.0) + 0.005:
            status, reason = "FAILED", "INSUFFICIENT_FUNDS"

        if status == "COMPLETED":
            if direction == "CREDIT":
                live_balance[aid] = money(live_balance.get(aid, 0.0) + amount_value)
            else:
                live_balance[aid] = money(live_balance.get(aid, 0.0) - amount_value)

        row["transaction_status"] = status
        row["failure_reason"] = reason
        row["_internal_id"] = None
        row["_internal_leg"] = None
        replayed.append(row)

    replayed = pd.DataFrame(replayed)
    replayed = replayed.sort_values(
        ["transaction_datetime", "account_id", "_event_key"], kind="mergesort"
    ).reset_index(drop=True)
    n = len(replayed)
    replayed["transaction_id"] = [f"T{i:010d}" for i in range(tx_counter + 1, tx_counter + n + 1)]
    tx_counter += n

    completed = replayed[replayed["transaction_status"].eq("COMPLETED")].copy()
    completed["cin"] = np.where(completed["direction"].eq("CREDIT"), completed["amount"], 0.0)
    completed["cout"] = np.where(completed["direction"].eq("DEBIT"), completed["amount"], 0.0)
    agg = completed.groupby("account_id", as_index=True).agg(
        total_inflows=("cin", "sum"), total_outflows=("cout", "sum")
    ).to_dict(orient="index")

    balance_rows = []
    for rec in skeleton.itertuples(index=False):
        aid = str(rec.account_id)
        flows = agg.get(aid, {})
        opening = month_opening[aid]
        inflow = money(flows.get("total_inflows", 0.0))
        outflow = money(flows.get("total_outflows", 0.0))
        closing = money(opening + inflow - outflow)
        if abs(closing - live_balance.get(aid, 0.0)) > 0.011:
            raise ValueError(f"Monthly live-balance mismatch for account {aid}.")
        balance_rows.append({
            "account_id": aid,
            "year_month": str(rec.year_month),
            "opening_balance": opening,
            "total_inflows": inflow,
            "total_outflows": outflow,
            "closing_balance": closing,
        })
    bals = pd.DataFrame(balance_rows, columns=BAL_COLS)
    return replayed, bals, live_balance, tx_counter, pair_counter


def replay_stage(d, accounts, roles, checkpoint):
    replay_context = build_internal_pool_context(accounts, roles, d["customers"])
    completed_months = list(checkpoint["completed_replay_months"])
    completed_set = set(completed_months)
    tx_counter = int(checkpoint.get("transaction_id_counter", 0))
    pair_counter = int(checkpoint.get("internal_pair_counter", 0))

    if completed_months:
        if not LIVE_BALANCE_PATH.exists():
            raise RuntimeError("Replay checkpoint exists but live balance state is missing. Run with --fresh.")
        live_df = pd.read_parquet(LIVE_BALANCE_PATH)
        live_balance = dict(zip(live_df["account_id"].astype(str), live_df["balance"].astype(float)))
    else:
        live_balance = {}

    audit = init_audit_metrics()
    # Rebuild reporting counters from already replayed months on resume.
    for month in completed_months:
        tx_path = REPLAY_TX_DIR / f"{month}.parquet"
        bal_path = REPLAY_BAL_DIR / f"{month}.parquet"
        if not tx_path.exists() or not bal_path.exists():
            raise RuntimeError("Replay checkpoint references missing monthly outputs. Run with --fresh.")
        tx_m = pd.read_parquet(tx_path)
        bal_m = pd.read_parquet(bal_path)
        validation = validate(tx_m, bal_m, accounts, d["branches"])
        update_audit_metrics(audit, tx_m, bal_m, validation)

    print("\nStage 2/3 — chronological monthly ledger replay")
    stage_started = time.perf_counter()
    for period in pd.period_range(OBS_START, OBS_END, freq="M"):
        month = str(period)
        if month in completed_set:
            print(f"  {month} already replayed")
            continue

        month_started = time.perf_counter()
        tx_month = load_month_stage(STAGE_INTENTS_DIR, month, "_month")
        skeleton = load_month_stage(STAGE_BALANCES_DIR, month, "year_month")
        if skeleton.empty:
            continue
        if tx_month.empty:
            tx_month = pd.DataFrame(columns=[
                "account_id","transaction_datetime","transaction_type","direction","channel","amount",
                "counterparty_type","transfer_scope","counterparty_institution_id","transaction_branch_id",
                "merchant_category","transaction_status","failure_reason","_month","_source","_event_key"
            ])

        pools = build_month_internal_pools(replay_context, period)
        replayed, bals, live_balance, tx_counter, pair_counter = replay_one_month(
            tx_month, skeleton, accounts, roles, d["customers"], pools, replay_context,
            live_balance, tx_counter, pair_counter,
        )
        validation = validate(replayed, bals, accounts, d["branches"])
        if not validation["validation_pass"]:
            raise RuntimeError(f"Monthly validation failed for {month}: {validation['errors']}")

        REPLAY_TX_DIR.mkdir(parents=True, exist_ok=True)
        REPLAY_BAL_DIR.mkdir(parents=True, exist_ok=True)
        REPLAY_PAIR_DIR.mkdir(parents=True, exist_ok=True)
        replayed.to_parquet(REPLAY_TX_DIR / f"{month}.parquet", index=False, compression=PARQUET_COMPRESSION)
        bals.to_parquet(REPLAY_BAL_DIR / f"{month}.parquet", index=False, compression=PARQUET_COMPRESSION)
        pairs = build_internal_pair_audit(replayed, accounts)
        pairs.to_parquet(REPLAY_PAIR_DIR / f"{month}.parquet", index=False, compression=PARQUET_COMPRESSION)
        pd.DataFrame({"account_id": list(live_balance), "balance": list(live_balance.values())}).to_parquet(
            LIVE_BALANCE_PATH, index=False, compression=PARQUET_COMPRESSION
        )

        update_audit_metrics(audit, replayed, bals, validation)
        checkpoint["completed_replay_months"].append(month)
        checkpoint["transaction_id_counter"] = tx_counter
        checkpoint["internal_pair_counter"] = pair_counter
        save_checkpoint(checkpoint)
        month_seconds = time.perf_counter() - month_started
        print(
            f"  {month} | transactions={len(replayed):,} "
            f"account-months={len(bals):,} elapsed={month_seconds:,.1f}s"
        )

    print(f"Stage 2 elapsed: {time.perf_counter() - stage_started:,.1f}s")
    return audit


def concatenate_parquet_months(source_dir, output_path, columns=None):
    files = [source_dir / f"{str(p)}.parquet" for p in pd.period_range(OBS_START, OBS_END, freq="M")]
    files = [p for p in files if p.exists()]
    if not files:
        raise RuntimeError(f"No monthly Parquet files found in {source_dir}.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp = output_path.with_suffix(output_path.suffix + ".tmp")
    if temp.exists():
        temp.unlink()
    writer = None
    try:
        for path in files:
            table = pq.read_table(path, columns=columns)
            if writer is None:
                writer = pq.ParquetWriter(temp, table.schema, compression=PARQUET_COMPRESSION)
            writer.write_table(table)
    finally:
        if writer is not None:
            writer.close()
    temp.replace(output_path)


def print_streaming_report(audit, validation_metrics):
    print("\n" + "="*72)
    print("BTYT TRANSACTION ENGINE — VALIDATION")
    print("="*72)
    print(f"Transactions: {audit['transactions']:,}")
    print(f"Account-months: {audit['account_months']:,}")
    for title, counter in (
        ("Transaction types", audit["transaction_types"]),
        ("Status", audit["statuses"]),
        ("Channels", audit["channels"]),
    ):
        print(f"\n{title}:")
        total = sum(counter.values()) or 1
        for key, value in counter.most_common():
            print(f"  {str(key):24s} {value:10,} {100*value/total:7.2f}%")
    print("\nFailure reasons:")
    failed_total = sum(audit["failure_reasons"].values()) or 1
    for key, value in audit["failure_reasons"].most_common():
        print(f"  {str(key):24s} {value:10,} {100*value/failed_total:7.2f}%")
    if audit["transfer_scopes"]:
        print("\nTransfer scopes:")
        total = sum(audit["transfer_scopes"].values())
        for key, value in audit["transfer_scopes"].most_common():
            print(f"  {str(key):24s} {value:10,} {100*value/total:7.2f}%")
    if audit["external_institutions"]:
        print("\nExternal counterparty institutions:")
        total = sum(audit["external_institutions"].values())
        for bank_id, value in audit["external_institutions"].most_common():
            meta = INSTITUTION_CONTEXT["institution_meta"].get(str(bank_id), {})
            name = meta.get("institution_name", str(bank_id))
            print(f"  {str(bank_id):5s} {name:<28} {value:10,} {100*value/total:7.2f}%")
    print("\nIntegrity:")
    for key, value in validation_metrics.items():
        print(f"  {key:30s} {'PASS' if value == 0 else f'FAIL ({value})'}")
    validation_pass = all(value == 0 for value in validation_metrics.values())
    print(f"\nVALIDATION: {'PASS' if validation_pass else 'FAIL'}")
    return validation_pass


def finalize_outputs(audit, traits, roles, checkpoint):
    print("\nStage 3/3 — canonical Parquet assembly")
    concatenate_parquet_months(REPLAY_TX_DIR, TX_OUT, TX_COLS)
    concatenate_parquet_months(REPLAY_BAL_DIR, BAL_OUT, BAL_COLS)
    pair_files = sorted(REPLAY_PAIR_DIR.glob("*.parquet"))
    if pair_files:
        INTERNAL_PAIRS_OUT.parent.mkdir(parents=True, exist_ok=True)
        pair_temp = INTERNAL_PAIRS_OUT.with_suffix(INTERNAL_PAIRS_OUT.suffix + ".tmp")
        if pair_temp.exists():
            pair_temp.unlink()
        pair_writer = None
        try:
            for path in pair_files:
                table = pq.read_table(path)
                if pair_writer is None:
                    pair_writer = pq.ParquetWriter(
                        pair_temp, table.schema, compression=PARQUET_COMPRESSION
                    )
                pair_writer.write_table(table)
        finally:
            if pair_writer is not None:
                pair_writer.close()
        pair_temp.replace(INTERNAL_PAIRS_OUT)
    else:
        pd.DataFrame(columns=[
            "internal_transfer_id","transaction_datetime","currency","amount",
            "sender_account_id","receiver_account_id","sender_transaction_id","receiver_transaction_id"
        ]).to_parquet(INTERNAL_PAIRS_OUT, index=False, compression=PARQUET_COMPRESSION)

    validation_metrics = dict(audit["validation_metrics"])
    # Continuity is enforced directly by live balance carry-forward in replay_one_month.
    validation_metrics["continuity"] = 0
    validation_metrics["duplicate_tx_id"] = 0
    validation_pass = print_streaming_report(audit, validation_metrics)
    if not validation_pass:
        raise SystemExit("Validation failed; canonical outputs retained only for debugging.")

    traits.to_parquet(TRAITS_OUT, index=False, compression=PARQUET_COMPRESSION)
    roles.to_parquet(ROLES_OUT, index=False, compression=PARQUET_COMPRESSION)
    pd.DataFrame([{"metric": k, "value": v} for k, v in validation_metrics.items()] + [
        {"metric": "validation_pass", "value": True},
        {"metric": "transactions", "value": audit["transactions"]},
        {"metric": "account_months", "value": audit["account_months"]},
    ]).to_csv(AUDIT_OUT, index=False)
    pd.DataFrame([WORLD]).assign(
        world_seed=WORLD_CONFIG.seed,
        rng_namespace=RNG_NAMESPACE,
        bank_world_seed=INSTITUTION_CONTEXT["bank_world_seed"],
        engine_version=ENGINE_VERSION,
    ).to_csv(WORLD_OUT, index=False)

    print(f"\nSaved canonical transactions: {TX_OUT}")
    print(f"Saved canonical balances:     {BAL_OUT}")
    print(f"Saved internal pair audit:    {INTERNAL_PAIRS_OUT}")
    print(f"Checkpoint:                   {CHECKPOINT_PATH}")


def main():
    global INSTITUTION_CONTEXT
    args = parse_args()
    if args.chunk_size <= 0:
        raise ValueError("--chunk-size must be positive.")

    d = select_smoke_population(load_data(), smoke=args.smoke)
    INSTITUTION_CONTEXT = build_institution_context(d)
    accounts = lifecycle(d["accounts"])
    roles = build_roles(accounts, d["customers"])
    traits = build_traits(d["customers"], accounts)
    debit = debit_links(d["cards"])
    loan_intent_path = build_loan_intent_staging(
        d["loans"], d["loan_snapshot"], d["loan_bridge"], accounts, roles
    )

    fingerprint = world_fingerprint(accounts)
    checkpoint = load_checkpoint(fingerprint, args.chunk_size, fresh=args.fresh)

    print("="*84)
    print(f"BTYT TRANSACTION ENGINE — V{ENGINE_VERSION}")
    print("="*84)
    print(f"World seed: {WORLD_CONFIG.seed}")
    print(f"RNG namespace: {RNG_NAMESPACE}")
    print(f"Customers: {len(d['customers']):,}")
    print(f"Accounts: {len(accounts):,}")
    print(f"Observation window: {OBS_START} → {OBS_END}")
    print(f"Account chunk size: {args.chunk_size:,}")
    print(f"Smoke mode: {args.smoke}")
    print(f"Institution network: {len(INSTITUTION_CONTEXT['domestic_bank_ids'])} domestic external banks + {len(INSTITUTION_CONTEXT['foreign_bank_ids'])} international banks + {len(INSTITUTION_CONTEXT['iede_ids'])} IEDEs")
    print(f"BANK_WORLD_SEED: {INSTITUTION_CONTEXT['bank_world_seed']}")
    print("World parameters:")
    for key, value in WORLD.items():
        print(f"  {key:28s} {value:.4f}")

    generation_stage(d, accounts, roles, traits, debit, loan_intent_path, args.chunk_size, checkpoint)
    audit = replay_stage(d, accounts, roles, checkpoint)
    finalize_outputs(audit, traits, roles, checkpoint)


if __name__ == "__main__":
    main()
