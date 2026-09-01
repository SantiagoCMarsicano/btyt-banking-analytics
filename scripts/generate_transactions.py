#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""BTYT — Transactions + Account Balances generator — V2.3 bank-network integrated.

Ground-truth first: transactions are generated as event intents, processed
chronologically through a non-overdraft ledger, and account_balances is derived
from completed movements. Credit-card payments and data-quality degradation are
intentionally deferred to later modules.

V2.3 structural changes:
- preserves all validated V2.2 behavioral, liquidity, internal-transfer, and ledger mechanics;
- reads the canonical V4 bank-network outputs from data/generated;
- assigns transfer_scope and counterparty_bank_id after counterparty_type is finalized;
- uses annual domestic market weights plus realized bank affinities for domestic bank selection;
- uses foreign world-selection weights plus realized affinities for international bank selection;
- keeps internal BTYT transfers mapped to B000 and external institutions outside the BTYT ledger.
"""
from __future__ import annotations

import calendar
import math
import secrets
import zlib
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "data" / "generated"
INTERIM = ROOT / "data" / "interim"

CUSTOMERS_PATH = GENERATED / "customers.csv"
ACCOUNTS_PATH = GENERATED / "accounts.csv"
CARDS_PATH = GENERATED / "cards.csv"
LOANS_PATH = GENERATED / "loans.csv"
LOAN_SNAPSHOT_PATH = GENERATED / "loan_monthly_snapshot.csv"
LOAN_BRIDGE_PATH = INTERIM / "loan_lifecycle_bridge.csv"
BRANCHES_PATH = GENERATED / "branches.csv"
BANKS_PATH = GENERATED / "banks.csv"
BANK_WORLD_PATH = GENERATED / "bank_world_parameters.csv"
BANK_MARKET_PATH = GENERATED / "bank_market_weights.csv"
BANK_MACRO_PATH = GENERATED / "bank_macro_environment.csv"

TX_OUT = GENERATED / "transactions.csv"
BAL_OUT = GENERATED / "account_balances.csv"
TRAITS_OUT = INTERIM / "customer_transaction_traits.csv"
ROLES_OUT = INTERIM / "account_roles.csv"
AUDIT_OUT = INTERIM / "transaction_generation_audit.csv"
WORLD_OUT = INTERIM / "transaction_world_parameters.csv"
INTERNAL_PAIRS_OUT = INTERIM / "internal_transfer_pairs.csv"

# -----------------------------------------------------------------------------
# WORLD SEED
# -----------------------------------------------------------------------------
# By default, every execution creates a new BTYT transaction world.
# If you ever want to reproduce a particularly interesting world, replace
# None with the printed WORLD_SEED from that run.
REPRODUCE_WORLD_SEED = None
WORLD_SEED = (
    int(REPRODUCE_WORLD_SEED)
    if REPRODUCE_WORLD_SEED is not None
    else secrets.randbits(32)
)
TRANSACTION_SEED = WORLD_SEED
DEVELOPMENT_CUSTOMERS = 5_000
SMOKE_TEST = True 
SMOKE_TEST_CUSTOMERS = 250
SAVE_INTERIM = True
OBS_START = pd.Period("2021-01", freq="M")
OBS_END = pd.Period("2026-12", freq="M")

TX_COLS = [
    "transaction_id", "account_id", "transaction_datetime", "transaction_type",
    "direction", "channel", "amount", "counterparty_type",
    "transfer_scope", "counterparty_bank_id", "transaction_branch_id",
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
BANK_CONTEXT = None


def stable_seed(*parts) -> int:
    text = "|".join(str(x) for x in (TRANSACTION_SEED, *parts))
    return zlib.crc32(text.encode("utf-8")) & 0xFFFFFFFF


def rng_for(*parts):
    return np.random.default_rng(stable_seed(*parts))


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


def load_data():
    required_paths = [
        CUSTOMERS_PATH, ACCOUNTS_PATH, BRANCHES_PATH, BANKS_PATH,
        BANK_WORLD_PATH, BANK_MARKET_PATH, BANK_MACRO_PATH,
    ]
    for p in required_paths:
        if not p.exists():
            raise FileNotFoundError(p)

    d = {
        "customers": pd.read_csv(CUSTOMERS_PATH, dtype={"customer_id":str,"primary_branch_id":str}),
        "accounts": pd.read_csv(ACCOUNTS_PATH, dtype={"account_id":str,"customer_id":str,"product_id":str,"branch_id":str}),
        "branches": pd.read_csv(BRANCHES_PATH, dtype={"branch_id":str}),
        "banks": pd.read_csv(BANKS_PATH, dtype={"bank_id":str}),
        "bank_world": pd.read_csv(BANK_WORLD_PATH, dtype={"bank_id":str}),
        "bank_market": pd.read_csv(BANK_MARKET_PATH, dtype={"bank_id":str}),
        "bank_macro": pd.read_csv(BANK_MACRO_PATH),
    }
    optional = {"cards":CARDS_PATH,"loans":LOANS_PATH,"loan_snapshot":LOAN_SNAPSHOT_PATH,"loan_bridge":LOAN_BRIDGE_PATH}
    for k,p in optional.items():
        d[k] = pd.read_csv(p, dtype=str if k=="loan_bridge" else None) if p.exists() else pd.DataFrame()

    require(d["customers"], {"customer_id","customer_type","registration_year","customer_status"}, "customers")
    require(d["accounts"], {"account_id","customer_id","product_id","branch_id","opening_year","account_status","closing_year","opening_channel"}, "accounts")
    require(d["branches"], {"branch_id","branch_size","status","opening_year","closing_year","department","locality","region"}, "branches")
    require(d["banks"], {"bank_id","bank_name","bank_scope","bank_status"}, "banks")
    require(d["bank_world"], {
        "world_seed","bank_id","realized_usd_affinity","realized_business_affinity",
        "realized_large_transfer_affinity","foreign_selection_weight"
    }, "bank_world_parameters")
    require(d["bank_market"], {"world_seed","bank_id","year","market_weight"}, "bank_market_weights")
    require(d["bank_macro"], {"year","cross_border_factor"}, "bank_macro_environment")
    return d


def sample_population(d):
    # Transactions must be sampled from the same frozen customer universe that
    # actually has generated accounts. Sampling from the full 20k customer
    # master would select many customers outside the frozen 10k account build.
    d["customers"]["customer_id"] = d["customers"]["customer_id"].astype(str)
    d["accounts"]["customer_id"] = d["accounts"]["customer_id"].astype(str)

    account_customer_ids = pd.Index(d["accounts"]["customer_id"].dropna().unique())
    eligible = d["customers"][d["customers"]["customer_id"].isin(account_customer_ids)].copy()

    target_n = SMOKE_TEST_CUSTOMERS if SMOKE_TEST else DEVELOPMENT_CUSTOMERS
    n = min(target_n, len(eligible))
    ids = set(eligible["customer_id"].sample(n=n, random_state=TRANSACTION_SEED).astype(str))

    d["customers"] = d["customers"][d["customers"]["customer_id"].isin(ids)].copy()
    for k in ["accounts", "cards", "loans"]:
        if not d[k].empty and "customer_id" in d[k].columns:
            d[k]["customer_id"] = d[k]["customer_id"].astype(str)
            d[k] = d[k][d[k]["customer_id"].isin(ids)].copy()

    if not d["loans"].empty:
        loan_ids = set(d["loans"]["loan_id"].astype(str))
        for k in ["loan_snapshot", "loan_bridge"]:
            if not d[k].empty and "loan_id" in d[k].columns:
                d[k]["loan_id"] = d[k]["loan_id"].astype(str)
                d[k] = d[k][d[k]["loan_id"].isin(loan_ids)].copy()
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
    r = np.random.default_rng(stable_seed("world-parameters"))
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
    age=2026-pd.to_numeric(c.get("birth_year",45),errors="coerce"); age=age.fillna(45).clip(18,100)
    business=(c["customer_type"].str.upper()=="BUSINESS").astype(float)
    corr=np.eye(9); pairs={(0,1):.25,(0,3):.30,(0,4):.35,(1,2):-.45,(1,4):.20,(3,5):-.30,(4,7):.35,(0,8):.25}
    for (i,j),v in pairs.items(): corr[i,j]=corr[j,i]=v
    z=np.random.default_rng(TRANSACTION_SEED+100).multivariate_normal(np.zeros(9),corr,size=len(c))
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
    factor={2021:.63,2022:.72,2023:.82,2024:.90,2025:.96,2026:1}[period.year]
    r=rng_for("scale",c["customer_id"],period); yr=rng_for("year-scale",c["customer_id"],period.year)
    v=float(t["financial_volatility"]); season=1.0
    if str(c["customer_type"]).upper()=="BUSINESS":
        sector=str(c.get("business_sector","")).upper(); s=float(t["business_seasonality"])
        if any(k in sector for k in ["TOUR","HOTEL","RESTAUR"]): season+=s*(.20 if period.month in [12,1,2] else -.04)
        elif any(k in sector for k in ["AGRI","RURAL","LIVESTOCK"]): season+=s*(.12 if period.month in [3,4,5,9,10] else -.025)
        elif any(k in sector for k in ["RETAIL","COMMER","TRADE"]): season+=s*(.10 if period.month==12 else 0)
    return max(1000,anchor_uyu(c)*factor*np.exp(yr.normal(0,.06*v))*np.exp(r.normal(0,.07*v))*season)


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


def build_bank_context(d):
    """Build compact lookup tables for V4 counterparty-bank selection."""
    banks = d["banks"].copy()
    world = d["bank_world"].copy()
    market = d["bank_market"].copy()
    macro = d["bank_macro"].copy()

    banks["bank_id"] = banks["bank_id"].astype(str)
    world["bank_id"] = world["bank_id"].astype(str)
    market["bank_id"] = market["bank_id"].astype(str)
    market["year"] = pd.to_numeric(market["year"], errors="raise").astype(int)
    macro["year"] = pd.to_numeric(macro["year"], errors="raise").astype(int)

    active = banks.loc[banks["bank_status"].astype(str).str.upper().eq("ACTIVE")].copy()
    domestic_ids = tuple(active.loc[active["bank_scope"].eq("DOMESTIC"), "bank_id"].astype(str))
    foreign_ids = tuple(active.loc[active["bank_scope"].eq("FOREIGN"), "bank_id"].astype(str))

    if "B000" in domestic_ids:
        raise ValueError("BTYT B000 must not be classified as DOMESTIC in banks.csv.")
    if not domestic_ids:
        raise ValueError("No active domestic external banks found.")
    if not foreign_ids:
        raise ValueError("No active foreign banks found.")

    bank_world_seeds = pd.to_numeric(world["world_seed"], errors="raise").astype(int).unique()
    market_world_seeds = pd.to_numeric(market["world_seed"], errors="raise").astype(int).unique()
    if len(bank_world_seeds) != 1 or len(market_world_seeds) != 1:
        raise ValueError("Bank network inputs must each contain exactly one world_seed.")
    if int(bank_world_seeds[0]) != int(market_world_seeds[0]):
        raise ValueError("Bank world seed mismatch between parameters and market weights.")
    bank_world_seed = int(bank_world_seeds[0])

    affinity_cols = [
        "realized_usd_affinity",
        "realized_business_affinity",
        "realized_large_transfer_affinity",
        "foreign_selection_weight",
    ]
    world_lookup = world.set_index("bank_id")[affinity_cols].to_dict(orient="index")

    for bank_id in (*domestic_ids, *foreign_ids):
        if bank_id not in world_lookup:
            raise ValueError(f"Missing bank-world parameters for {bank_id}.")

    market_lookup = {}
    for year, g in market.groupby("year", sort=False):
        external = g[g["bank_id"].isin(domestic_ids)].copy()
        if set(external["bank_id"]) != set(domestic_ids):
            missing = sorted(set(domestic_ids) - set(external["bank_id"]))
            raise ValueError(f"Domestic market weights missing {missing} in {year}.")
        weights = external.set_index("bank_id")["market_weight"].astype(float).to_dict()
        market_lookup[int(year)] = weights

    required_years = set(range(OBS_START.year, OBS_END.year + 1))
    if set(market_lookup) != required_years:
        raise ValueError("bank_market_weights.csv does not cover every transaction year.")

    macro_lookup = macro.set_index("year")["cross_border_factor"].astype(float).to_dict()
    if not required_years.issubset(macro_lookup):
        raise ValueError("bank_macro_environment.csv does not cover every transaction year.")

    foreign_base = {}
    for bank_id in foreign_ids:
        value = float(world_lookup[bank_id]["foreign_selection_weight"])
        if not np.isfinite(value) or value <= 0:
            raise ValueError(f"Invalid foreign selection weight for {bank_id}.")
        foreign_base[bank_id] = value

    return {
        "bank_world_seed": bank_world_seed,
        "bank_names": active.set_index("bank_id")["bank_name"].astype(str).to_dict(),
        "domestic_ids": domestic_ids,
        "foreign_ids": foreign_ids,
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
    """Choose domestic-external versus international before choosing a bank."""
    if BANK_CONTEXT is None:
        raise RuntimeError("BANK_CONTEXT has not been initialized.")

    amount_uyu = float(amount) * (FX[int(period.year)] if currency == "USD" else 1.0)
    large = transfer_large_signal(amount_uyu)
    cross_border = float(BANK_CONTEXT["macro_cross_border"][int(period.year)])
    ext_affinity = float(traits["external_bank_affinity"])

    # International activity is intentionally conditional rather than a fixed share.
    # USD denomination, business status, large amounts, customer external-bank
    # affinity, and the V4 cross-border macro state all raise its probability.
    logit = -2.35
    logit += 1.35 if currency == "USD" else 0.0
    logit += 0.65 if ctype == "BUSINESS" else 0.0
    logit += 1.05 * large
    logit += 0.75 * (ext_affinity - 0.5)
    logit += 0.35 * cross_border
    p_international = float(np.clip(sigmoid(logit), 0.025, 0.72))

    return "INTERNATIONAL" if r.random() < p_international else "DOMESTIC_EXTERNAL"


def bank_selection_score(bank_id, base_weight, currency, ctype, amount_uyu, customer_id):
    """Convert V4 prominence and affinities into a conditional transfer score."""
    params = BANK_CONTEXT["world"][bank_id]
    usd_aff = float(params["realized_usd_affinity"])
    business_aff = float(params["realized_business_affinity"])
    large_aff = float(params["realized_large_transfer_affinity"])
    large = transfer_large_signal(amount_uyu)

    currency_fit = math.exp((1.00 if currency == "USD" else -0.20) * (usd_aff - 0.5))
    customer_fit = math.exp((0.80 if ctype == "BUSINESS" else -0.15) * (business_aff - 0.5))
    amount_fit = math.exp(1.00 * large * (large_aff - 0.5))

    # Stable customer-bank taste creates persistent relationship heterogeneity
    # without overwriting structural market prominence or bank specialization.
    pref_rng = rng_for("customer-bank-fit", customer_id, bank_id)
    behavioral_fit = math.exp(float(pref_rng.normal(0.0, 0.16)))

    return max(float(base_weight), 1e-12) * currency_fit * customer_fit * amount_fit * behavioral_fit


def choose_external_bank(r, scope, ctype, period, currency, amount, customer_id):
    """Choose a bank only inside the previously selected transfer scope."""
    year = int(period.year)
    amount_uyu = float(amount) * (FX[year] if currency == "USD" else 1.0)

    if scope == "DOMESTIC_EXTERNAL":
        bank_ids = BANK_CONTEXT["domestic_ids"]
        base = BANK_CONTEXT["market"][year]
    elif scope == "INTERNATIONAL":
        bank_ids = BANK_CONTEXT["foreign_ids"]
        base = BANK_CONTEXT["foreign_base"]
    else:
        raise ValueError(f"Unsupported external transfer scope: {scope}")

    scores = np.array([
        bank_selection_score(
            bank_id, base[bank_id], currency, ctype, amount_uyu, customer_id
        )
        for bank_id in bank_ids
    ], dtype=float)

    if not np.isfinite(scores).all() or scores.sum() <= 0:
        raise ValueError(f"Invalid bank-selection scores for scope {scope}.")

    return str(r.choice(np.asarray(bank_ids, dtype=object), p=scores / scores.sum()))


def resolve_transfer_bank(event, account, customer, traits, period, sequence):
    """Resolve transfer_scope and counterparty_bank_id from final counterparty semantics."""
    tt = str(event["transaction_type"])
    cp = str(event["counterparty_type"])

    if tt not in {"TRANSFER_IN", "TRANSFER_OUT"}:
        return None, None

    if cp == "BTYT_CUSTOMER":
        return "INTERNAL", "B000"

    if cp != "OTHER_BANK":
        return None, None

    ctype = str(customer["customer_type"]).upper()
    currency = CURRENCY[str(account["product_id"])]
    r = rng_for(
        "bank-counterparty", account["account_id"], period, sequence,
        event.get("source"), event.get("amount"), cp,
    )
    scope = choose_external_scope(r, ctype, traits, period, currency, event["amount"])
    bank_id = choose_external_bank(
        r, scope, ctype, period, currency, event["amount"], str(customer["customer_id"])
    )
    return scope, bank_id


def merchant_probs(c,t,period):
    alpha=np.array([5,2.4,2,3,1.6,1.4,1.8,.9,1.3,.9,1.8,1.5,2,1.2,.8,.8,1.0],float)
    alpha[12]*=.75+1.10*float(t["digital_preference"]); alpha[1]*=.8+.6*float(t["spending_propensity"]); alpha[8]*=.8+.6*float(t["spending_propensity"])
    if str(c["customer_type"]).upper()=="BUSINESS": alpha*=.7; alpha[15]*=4.5; alpha[14]*=2; alpha[13]*=1.5
    p=rng_for("dirichlet",c["customer_id"]).dirichlet(alpha)
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
        if role=="PAYROLL" and not business:return choose(r,["EMPLOYER","BTYT_CUSTOMER","OTHER_BANK","GOVERNMENT","OTHER"],[4,1.2,1+2*ext,.5,.6])
        return choose(r,["BTYT_CUSTOMER","OTHER_BANK","GOVERNMENT","SUPPLIER","OTHER"] if business else ["EMPLOYER","BTYT_CUSTOMER","OTHER_BANK","GOVERNMENT","OTHER"],[1.3,1.2+2*ext,.5,.4,1] if business else [.5,1.8,1+2*ext,.4,.8])
    if business:return choose(r,["SUPPLIER","OTHER_BANK","BTYT_CUSTOMER","GOVERNMENT","OTHER"],[2.4,1+2*ext,1.1,.8,.5])
    return choose(r,["BTYT_CUSTOMER","OTHER_BANK","GOVERNMENT","OTHER"],[2.1,1+2*ext,.4,.8])


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


def event_datetime(r,period,tt,cp,ch,ctype,preferred=None):
    nd=calendar.monthrange(period.year,period.month)[1]; days=np.arange(1,nd+1); w=np.ones(nd,float)
    for i,d in enumerate(days):
        wd=datetime(period.year,period.month,int(d)).weekday(); w[i]*=(1.7 if wd<5 else .35) if ctype=="BUSINESS" else (1.2 if tt=="DEBIT_PURCHASE" and wd>=5 else 1)
        if cp=="EMPLOYER":w[i]*=5 if d<=5 or d>=nd-2 else .55
        if preferred is not None:w[i]*=math.exp(-.35*abs(d-preferred))+.05
    day=int(r.choice(days,p=w/w.sum()))
    if ch=="BRANCH":
        # BRANCH transactions must occur on weekdays. If the sampled day falls
        # on a weekend, move to the nearest valid weekday without getting
        # trapped on day 1 when the month starts on Saturday/Sunday.
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
    e=branches[branches.apply(lambda x:branch_open(x,period),axis=1)].copy(); w=np.ones(len(e))*.15
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


def loan_index(loans,snap,bridge,accounts,roles):
    out=defaultdict(list)
    if loans.empty or snap.empty:return out
    for col in ["actual_payment","outstanding_balance"]:snap[col]=pd.to_numeric(snap[col],errors="coerce").fillna(0)
    snap["year_month"]=snap["year_month"].astype(str)
    rolemap=roles.set_index("account_id")["account_role"].to_dict(); omap={}
    if not bridge.empty and {"loan_id","origination_month_internal"}.issubset(bridge.columns):omap=bridge.set_index("loan_id")["origination_month_internal"].astype(str).to_dict()
    def pick(cid,curr,p,r):
        g=accounts[(accounts["customer_id"]==cid)&(accounts["product_id"].map(CURRENCY)==curr)&(accounts["first_obs_month"]<=p)&(accounts["last_obs_month"]>=p)&(~accounts["product_id"].isin(FIXED))]
        if g.empty:return None
        ww=[{"BUSINESS_OPERATING":3,"PRIMARY_TRANSACTIONAL":2.7,"PAYROLL":2.2,"SECONDARY":.9,"SAVINGS":.7,"USD_RESERVE":.7}.get(rolemap.get(x,"SECONDARY"),.5) for x in g["account_id"]]
        return choose(r,g["account_id"].tolist(),ww)
    for L in loans.itertuples(index=False):
        lid=str(L.loan_id);cid=str(L.customer_id);prod=str(L.product_id);curr=str(L.currency);orig=float(L.original_amount);r=rng_for("loan",lid);prob=.76 if prod in {"P012","P013","P014"} else .84
        if prod!="P016":
            p=None
            if lid in omap:
                try:p=pd.Period(omap[lid][:7],freq="M")
                except:pass
            if p is None:
                y=int(L.origination_year);p=pd.Period(f"{y}-{int(r.integers(1,13)):02d}",freq="M")
            if OBS_START<=p<=OBS_END and r.random()<prob:
                aid=pick(cid,curr,p,r)
                if aid:out[(aid,str(p))].append(("LOAN_DISBURSEMENT",money(orig),lid))
        g=snap[snap["loan_id"].astype(str)==lid].sort_values("year_month");prev=None
        for s in g.itertuples(index=False):
            try:p=pd.Period(str(s.year_month)[:7],freq="M")
            except:continue
            if not OBS_START<=p<=OBS_END:continue
            pay=float(s.actual_payment); bal=float(s.outstanding_balance)
            if prod=="P016" and prev is not None:
                draw=max(0,bal-prev+pay)
                if draw>max(10,.002*orig) and r.random()<prob:
                    aid=pick(cid,curr,p,r)
                    if aid:out[(aid,str(p))].append(("LOAN_DISBURSEMENT",money(draw),lid))
            if pay>0 and r.random()<prob:
                aid=pick(cid,curr,p,r)
                if aid:out[(aid,str(p))].append(("LOAN_PAYMENT",money(pay),lid))
            prev=bal
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
            scope, bank_id = resolve_transfer_bank(e, a, c, t, period, j)
            e["transfer_scope"] = scope
            e["counterparty_bank_id"] = bank_id
            r=rng_for("exec",a["account_id"],period,j,e["source"]);status="COMPLETED";reason=None
            if e["transaction_type"] not in {"LOAN_DISBURSEMENT","INTEREST_CREDIT"}:reason=op_failure(r,e);status="FAILED" if reason else "COMPLETED"
            if status=="COMPLETED" and e["direction"]=="DEBIT" and e["amount"]>balance+.005:status="FAILED";reason="INSUFFICIENT_FUNDS"
            if status=="COMPLETED":
                if e["direction"]=="CREDIT":balance=money(balance+e["amount"]);inflow=money(inflow+e["amount"])
                else:balance=money(balance-e["amount"]);outflow=money(outflow+e["amount"])
            tx.append({k:e.get(k) for k in ["account_id","transaction_datetime","transaction_type","direction","channel","amount","counterparty_type","transfer_scope","counterparty_bank_id","transaction_branch_id","merchant_category"]}|{"transaction_status":status,"failure_reason":reason,"_month":str(period),"_source":e["source"]})
        # closure sweep
        if str(a["account_status"]).upper()=="CLOSED" and period==a["last_obs_month"] and balance>.005:
            ev=make_event(a,c,t,role,period,"TRANSFER_OUT",balance,branches,"ACCOUNT_CLOSURE_SWEEP");ev["transaction_datetime"]=pd.Timestamp(datetime(period.year,period.month,calendar.monthrange(period.year,period.month)[1],15,45,0));scope,bank_id=resolve_transfer_bank(ev,a,c,t,period,"closure");ev["transfer_scope"]=scope;ev["counterparty_bank_id"]=bank_id;tx.append({k:ev.get(k) for k in ["account_id","transaction_datetime","transaction_type","direction","channel","amount","counterparty_type","transfer_scope","counterparty_bank_id","transaction_branch_id","merchant_category"]}|{"transaction_status":"COMPLETED","failure_reason":None,"_month":str(period),"_source":ev["source"]});outflow=money(outflow+balance);balance=0.0
        bals.append({"account_id":a["account_id"],"year_month":str(period),"opening_balance":money(opening),"total_inflows":money(inflow),"total_outflows":money(outflow),"closing_balance":money(balance)})
    return tx,bals



# -----------------------------------------------------------------------------
# INTERNAL BTYT TRANSFER NETWORK
# -----------------------------------------------------------------------------

def build_internal_account_pools(accounts, roles):
    role_map = roles.set_index("account_id")["account_role"].to_dict()
    pools = {}
    for period in pd.period_range(OBS_START, OBS_END, freq="M"):
        active = accounts[
            (accounts["first_obs_month"] <= period)
            & (accounts["last_obs_month"] >= period)
            & (~accounts["product_id"].isin(FIXED))
        ].copy()
        active["currency"] = active["product_id"].map(CURRENCY)
        active["role"] = active["account_id"].map(role_map).fillna("SECONDARY")
        active["weight"] = active["role"].map({
            "BUSINESS_OPERATING": 3.0,
            "PRIMARY_TRANSACTIONAL": 2.7,
            "PAYROLL": 2.3,
            "SECONDARY": 1.0,
            "SAVINGS": 0.8,
            "USD_RESERVE": 0.8,
        }).fillna(0.7)
        for currency, g in active.groupby("currency", sort=False):
            pools[(str(period), currency)] = {
                "account_id": g["account_id"].astype(str).to_numpy(),
                "customer_id": g["customer_id"].astype(str).to_numpy(),
                "weight": g["weight"].astype(float).to_numpy(),
            }
    return pools


def pick_internal_counterpart(r, pools, period, currency, own_account_id, own_customer_id):
    pool = pools.get((str(period), currency))
    if pool is None or len(pool["account_id"]) == 0:
        return None
    mask = (
        (pool["account_id"] != str(own_account_id))
        & (pool["customer_id"] != str(own_customer_id))
    )
    if not mask.any():
        return None
    ids = pool["account_id"][mask]
    weights = pool["weight"][mask]
    weights = weights / weights.sum()
    return str(r.choice(ids, p=weights))


def replay_with_internal_transfers(tx, balance_skeleton, accounts, roles):
    """Replay the ledger and make every completed BTYT_CUSTOMER transfer atomic."""
    tx = tx.copy().reset_index(drop=True)
    tx["_base_event_id"] = np.arange(len(tx), dtype=np.int64)
    tx["transaction_datetime"] = pd.to_datetime(tx["transaction_datetime"])

    account_meta = accounts.set_index("account_id")[["customer_id", "product_id"]].copy()
    account_customer = account_meta["customer_id"].astype(str).to_dict()
    account_currency = account_meta["product_id"].map(CURRENCY).to_dict()
    pools = build_internal_account_pools(accounts, roles)

    first_opening = (
        balance_skeleton.sort_values(["account_id", "year_month"])
        .groupby("account_id", as_index=True)["opening_balance"]
        .first()
        .astype(float)
        .to_dict()
    )
    live_balance = {str(k): money(v) for k, v in first_opening.items()}

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
        base_id = int(row["_base_event_id"])
        r = rng_for("internal-counterpart", base_id, aid, dt.isoformat())
        counterpart = pick_internal_counterpart(
            r, pools, period, currency, aid, cid
        )
        if counterpart is not None:
            internal_map[base_id] = counterpart

    ordered = tx.sort_values(
        ["transaction_datetime", "_base_event_id"], kind="mergesort"
    ).reset_index(drop=True)

    replayed = []
    pair_sequence = 0

    for row in ordered.to_dict("records"):
        aid = str(row["account_id"])
        amount_value = money(row["amount"])
        tt = str(row["transaction_type"])
        direction = str(row["direction"])
        base_id = int(row["_base_event_id"])
        internal = (
            tt in {"TRANSFER_IN", "TRANSFER_OUT"}
            and row.get("counterparty_type") == "BTYT_CUSTOMER"
            and base_id in internal_map
        )

        original_reason = row.get("failure_reason")
        operational_reason = (
            original_reason
            if pd.notna(original_reason) and original_reason != "INSUFFICIENT_FUNDS"
            else None
        )

        if internal:
            counterpart = str(internal_map[base_id])
            if tt == "TRANSFER_OUT":
                sender, receiver = aid, counterpart
                original_leg = "OUT"
            else:
                sender, receiver = counterpart, aid
                original_leg = "IN"

            status = "COMPLETED"
            reason = None
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
                pair_sequence += 1
                internal_id = f"IT{pair_sequence:010d}"
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
                    "counterparty_bank_id": "B000",
                    "transaction_branch_id": row.get("transaction_branch_id"),
                    "transaction_status": "COMPLETED",
                    "merchant_category": None,
                    "failure_reason": None,
                    "_month": str(pd.Timestamp(row["transaction_datetime"]).to_period("M")),
                    "_source": f"INTERNAL_PAIR:{internal_id}",
                    "_base_event_id": base_id,
                    "_internal_id": internal_id,
                    "_internal_leg": "IN" if opposite_tt == "TRANSFER_IN" else "OUT",
                }
                replayed.append(original)
                replayed.append(opposite)
            else:
                replayed.append(original)
            continue

        status = "COMPLETED"
        reason = None
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

    completed = replayed[replayed["transaction_status"] == "COMPLETED"].copy()
    completed["year_month"] = pd.to_datetime(
        completed["transaction_datetime"]
    ).dt.to_period("M").astype(str)
    completed["credit_value"] = np.where(
        completed["direction"] == "CREDIT", completed["amount"], 0.0
    )
    completed["debit_value"] = np.where(
        completed["direction"] == "DEBIT", completed["amount"], 0.0
    )
    agg = completed.groupby(["account_id", "year_month"], as_index=False).agg(
        total_inflows=("credit_value", "sum"),
        total_outflows=("debit_value", "sum"),
    )

    skeleton = balance_skeleton[["account_id", "year_month"]].copy()
    rebuilt = skeleton.merge(
        agg, on=["account_id", "year_month"], how="left"
    ).fillna({"total_inflows": 0.0, "total_outflows": 0.0})

    balance_rows = []
    for aid, g in rebuilt.sort_values(["account_id", "year_month"]).groupby(
        "account_id", sort=False
    ):
        opening = money(first_opening.get(str(aid), 0.0))
        for rec in g.itertuples(index=False):
            inflow = money(rec.total_inflows)
            outflow = money(rec.total_outflows)
            closing = money(opening + inflow - outflow)
            balance_rows.append({
                "account_id": str(aid),
                "year_month": str(rec.year_month),
                "opening_balance": opening,
                "total_inflows": inflow,
                "total_outflows": outflow,
                "closing_balance": closing,
            })
            opening = closing

    rebuilt_balances = pd.DataFrame(balance_rows)[BAL_COLS]
    return replayed, rebuilt_balances


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


def bank_counterparty_validation(tx):
    metrics = {}
    transfers = tx[tx["transaction_type"].isin(["TRANSFER_IN", "TRANSFER_OUT"])].copy()
    non_transfers = tx[~tx["transaction_type"].isin(["TRANSFER_IN", "TRANSFER_OUT"])].copy()

    all_bank_ids = set(BANK_CONTEXT["bank_names"]) | {"B000"}
    domestic_ids = set(BANK_CONTEXT["domestic_ids"])
    foreign_ids = set(BANK_CONTEXT["foreign_ids"])

    metrics["nontransfer_scope_present"] = int(non_transfers["transfer_scope"].notna().sum())
    metrics["nontransfer_bank_present"] = int(non_transfers["counterparty_bank_id"].notna().sum())

    bank_values = transfers["counterparty_bank_id"].dropna().astype(str)
    metrics["bad_counterparty_bank_fk"] = int((~bank_values.isin(all_bank_ids)).sum())

    internal = transfers[transfers["counterparty_type"].eq("BTYT_CUSTOMER")]
    metrics["bad_internal_scope"] = int((internal["transfer_scope"] != "INTERNAL").sum())
    metrics["bad_internal_bank"] = int((internal["counterparty_bank_id"] != "B000").sum())

    external = transfers[transfers["counterparty_type"].eq("OTHER_BANK")]
    metrics["external_scope_missing"] = int(external["transfer_scope"].isna().sum())
    metrics["bad_external_scope"] = int((~external["transfer_scope"].isin(["DOMESTIC_EXTERNAL", "INTERNATIONAL"])).sum())
    metrics["external_bank_missing"] = int(external["counterparty_bank_id"].isna().sum())
    metrics["external_btyt_bank"] = int(external["counterparty_bank_id"].astype(str).eq("B000").sum())

    dom = external[external["transfer_scope"].eq("DOMESTIC_EXTERNAL")]
    intl = external[external["transfer_scope"].eq("INTERNATIONAL")]
    metrics["bad_domestic_bank_scope"] = int((~dom["counterparty_bank_id"].astype(str).isin(domestic_ids)).sum())
    metrics["bad_international_bank_scope"] = int((~intl["counterparty_bank_id"].astype(str).isin(foreign_ids)).sum())

    other = transfers[~transfers["counterparty_type"].isin(["BTYT_CUSTOMER", "OTHER_BANK"])]
    metrics["other_transfer_scope_present"] = int(other["transfer_scope"].notna().sum())
    metrics["other_transfer_bank_present"] = int(other["counterparty_bank_id"].notna().sum())
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
    m.update(bank_counterparty_validation(tx))
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

    external = transfers[transfers["counterparty_type"].eq("OTHER_BANK") & transfers["counterparty_bank_id"].notna()]
    if len(external):
        print("\nExternal counterparty banks:")
        counts = external["counterparty_bank_id"].value_counts()
        for bank_id,n in counts.items():
            name = BANK_CONTEXT["bank_names"].get(str(bank_id), str(bank_id))
            print(f"  {bank_id:5s} {name:<28} {n:10,} {100*n/len(external):7.2f}%")

    print("\nIntegrity:")
    for k,v in validation.items():
        if k not in {"validation_pass","errors"}:print(f"  {k:30s} {'PASS' if v==0 else f'FAIL ({v})'}")
    print(f"\nVALIDATION: {'PASS' if validation['validation_pass'] else 'FAIL'}")
    if validation["errors"]:print(validation["errors"])


def main():
    global BANK_CONTEXT
    d=sample_population(load_data());BANK_CONTEXT=build_bank_context(d);a=lifecycle(d["accounts"]);roles=build_roles(a,d["customers"]);traits=build_traits(d["customers"],a);cmap=d["customers"].set_index("customer_id", drop=False);tmap=traits.set_index("customer_id", drop=False);rmap=roles.set_index("account_id")["account_role"].to_dict();debit=debit_links(d["cards"]);lidx=loan_index(d["loans"],d["loan_snapshot"],d["loan_bridge"],a,roles)
    print("="*72);print("BTYT TRANSACTION ENGINE — V2.3 BANK-NETWORK INTEGRATED");print("="*72);print(f"Customers: {len(d['customers']):,}");print(f"Accounts: {len(a):,}");print(f"Loan-linked buckets: {len(lidx):,}");print(f"Smoke test: {SMOKE_TEST}");print(f"WORLD_SEED: {WORLD_SEED}");print(f"Bank network: {len(BANK_CONTEXT['domestic_ids'])} domestic external + {len(BANK_CONTEXT['foreign_ids'])} foreign counterparties");print(f"BANK_WORLD_SEED: {BANK_CONTEXT['bank_world_seed']}");print("World parameters:");[print(f"  {k:28s} {v:.4f}") for k,v in WORLD.items()];print()
    alltx=[];allb=[]
    for i,ar in enumerate(a.to_dict("records"),1):
        cid=str(ar["customer_id"]);tx,b=process_account(pd.Series(ar),cmap.loc[cid],tmap.loc[cid],rmap.get(ar["account_id"],"SECONDARY"),d["branches"],debit,lidx);alltx+=tx;allb+=b
        if i%500==0 or i==len(a):print(f"Processed {i:>6,}/{len(a):,} accounts | transaction intents {len(alltx):>10,}")

    tx=pd.DataFrame(alltx)
    bals=pd.DataFrame(allb)[BAL_COLS]

    print("\nPairing and replaying internal BTYT transfers...")
    tx,bals=replay_with_internal_transfers(tx,bals,a,roles)

    tx=tx.sort_values(["transaction_datetime","account_id"],kind="mergesort").reset_index(drop=True)
    tx["transaction_id"]=[f"T{i:010d}" for i in range(1,len(tx)+1)]
    tx["transaction_datetime"]=pd.to_datetime(tx["transaction_datetime"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    tx["amount"]=pd.to_numeric(tx["amount"]).round(2)

    validation=validate(tx,bals,a,d["branches"]);report(tx,bals,validation)
    if not validation["validation_pass"]:raise SystemExit("Validation failed; outputs not saved.")

    pair_audit=build_internal_pair_audit(tx,a)

    GENERATED.mkdir(parents=True,exist_ok=True);INTERIM.mkdir(parents=True,exist_ok=True);tx[TX_COLS].to_csv(TX_OUT,index=False);bals.to_csv(BAL_OUT,index=False)
    if SAVE_INTERIM:
        traits.to_csv(TRAITS_OUT,index=False);roles.to_csv(ROLES_OUT,index=False);pd.DataFrame([{"metric":k,"value":v} for k,v in validation.items()]).to_csv(AUDIT_OUT,index=False);pd.DataFrame([WORLD]).assign(world_seed=WORLD_SEED,transaction_seed=TRANSACTION_SEED,bank_world_seed=BANK_CONTEXT["bank_world_seed"]).to_csv(WORLD_OUT,index=False);pair_audit.to_csv(INTERNAL_PAIRS_OUT,index=False)
    print(f"\nSaved: {TX_OUT} {tx[TX_COLS].shape}");print(f"Saved: {BAL_OUT} {bals.shape}");print(f"Saved: {INTERNAL_PAIRS_OUT} {pair_audit.shape}")


if __name__=="__main__":main()
