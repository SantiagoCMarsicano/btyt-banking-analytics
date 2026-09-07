"""BTYT final cross-system audit — V2.1.0.

Read-only integrity audit for the frozen Part I synthetic banking universe.
It does not modify generated datasets and does not recalibrate any DGP.

The audit checks:
- primary-key and foreign-key integrity;
- lifecycle and temporal coherence;
- account / card / loan / transaction relationships;
- transaction semantics and monthly balance reconciliation;
- loan snapshot coherence;
- branch and bank references;
- external-shock structural chronology when those outputs exist;
- campaign selection / exposure / response chronology when those outputs exist;
- observation-window boundaries.

The script intentionally distinguishes hard integrity failures from optional checks
whose source files are not present.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from scripts.core.paths import (
    GENERATED_CAMPAIGNS_DIR,
    GENERATED_CORE_DIR,
    GENERATED_CREDIT_DIR,
    GENERATED_DATA_DIR,
    GENERATED_PERFORMANCE_DIR,
    GENERATED_TRANSACTIONS_DIR,
    INTERIM_AUDITS_DIR,
    INTERIM_CREDIT_DIR,
    INTERIM_DATA_DIR,
    INTERIM_WORLD_DIR,
    OPERATIONAL_DATA_DIR,
    WORLD_ROOT,
)


# All runtime data paths are resolved centrally through scripts.core.paths.
# With an active BTYT world, every audit input and output remains isolated
# inside that world's directory.
ROOT = WORLD_ROOT

GENERATED = GENERATED_DATA_DIR
GENERATED_CORE = GENERATED_CORE_DIR
GENERATED_CREDIT = GENERATED_CREDIT_DIR
GENERATED_TRANSACTIONS = GENERATED_TRANSACTIONS_DIR
GENERATED_CAMPAIGNS = GENERATED_CAMPAIGNS_DIR
GENERATED_PERFORMANCE = GENERATED_PERFORMANCE_DIR

INTERIM = INTERIM_DATA_DIR
INTERIM_WORLD = INTERIM_WORLD_DIR
INTERIM_CREDIT = INTERIM_CREDIT_DIR
INTERIM_AUDITS = INTERIM_AUDITS_DIR

OPERATIONAL = OPERATIONAL_DATA_DIR

OBS_START = pd.Timestamp("2021-01-01")
OBS_END = pd.Timestamp("2026-12-31 23:59:59")

RESULTS = []
DETAILS = []


def record(section, check, passed, detail=""):
    passed = bool(passed)
    RESULTS.append((section, check, passed, str(detail)))
    status = "PASS" if passed else "FAIL"
    print(f"  {check:<52} {status}")
    if detail:
        DETAILS.append((section, check, status, str(detail)))


def skip(section, check, detail):
    RESULTS.append((section, check, None, str(detail)))
    print(f"  {check:<52} SKIP")
    DETAILS.append((section, check, "SKIP", str(detail)))


def load_table(path, dtype=None):
    if path is None or not Path(path).exists():
        return None

    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".parquet":
        return pd.read_parquet(path)

    if suffix == ".csv":
        return pd.read_csv(path, dtype=dtype, low_memory=False)

    raise ValueError(f"Unsupported dataset format: {path}")


def first_existing(*paths):
    for path in paths:
        if path is not None and Path(path).exists():
            return Path(path)
    return None


def canonical_candidates(*paths):
    expanded = []
    for path in paths:
        p = Path(path)
        if p.suffix:
            expanded.append(p)
        else:
            expanded.extend([p.with_suffix(".parquet"), p.with_suffix(".csv")])
    return expanded


def resolve_dataset(name, *paths, required=False):
    candidates = canonical_candidates(*paths)
    resolved = first_existing(*candidates)

    if required and resolved is None:
        searched = "\\n  - ".join(str(p) for p in candidates)
        raise FileNotFoundError(
            f"Missing mandatory canonical dataset: {name}. Searched:\\n  - {searched}"
        )

    return resolved


def normalize_id(df, columns):
    """Normalize identifier columns without changing their semantic value.

    CSV inference can load nullable integer identifiers such as transaction_branch_id
    as floats because blank rows coexist with numeric IDs. In that case pandas may
    represent branch 17 as 17.0, while branches.csv contains 17. This function
    canonicalizes only integer-like numeric strings and preserves alphanumeric IDs.
    """
    if df is None:
        return

    for col in columns:
        if col not in df.columns:
            continue

        s = df[col].astype("string").str.strip()

        # Canonicalize values such as "1.0" -> "1" while leaving identifiers such
        # as "B001", "A000123", or other alphanumeric keys untouched.
        numeric = pd.to_numeric(s, errors="coerce")
        integer_like = numeric.notna() & np.isfinite(numeric) & np.isclose(
            numeric, np.round(numeric), atol=1e-12
        )

        if integer_like.any():
            s.loc[integer_like] = np.round(
                numeric.loc[integer_like]
            ).astype("Int64").astype("string")

        df[col] = s


def parse_date(series):
    return pd.to_datetime(series, errors="coerce")


def parse_month(series):
    return pd.to_datetime(series.astype(str).str[:7] + "-01", errors="coerce")


def numeric(series):
    return pd.to_numeric(series, errors="coerce")


def unique_nonnull(df, col):
    return df[col].dropna().is_unique


def fk_ok(child, child_col, parent, parent_col):
    vals = set(child[child_col].dropna().astype(str))
    parents = set(parent[parent_col].dropna().astype(str))
    missing = vals - parents
    return len(missing) == 0, missing


def section_header(name):
    print()
    print(name)
    print("-" * len(name))


def audit_customers(customers):
    section = "Core banking"
    section_header(section)
    record(section, "customer_id primary key", unique_nonnull(customers, "customer_id"))
    if "registration_year" in customers:
        y = numeric(customers["registration_year"])
        record(section, "customer registration year is valid", y.notna().all() and y.between(1900, 2026).all())
    if "customer_status" in customers:
        record(section, "customer status populated", customers["customer_status"].notna().all())


def audit_accounts(accounts, customers, branches):
    section = "Core banking"
    record(section, "account_id primary key", unique_nonnull(accounts, "account_id"))

    ok, missing = fk_ok(accounts, "customer_id", customers, "customer_id")
    record(section, "account -> customer foreign key", ok, f"missing={len(missing)}")

    if branches is not None and "branch_id" in accounts and "branch_id" in branches:
        ok, missing = fk_ok(accounts, "branch_id", branches, "branch_id")
        record(section, "account -> branch foreign key", ok, f"missing={len(missing)}")

    oy = numeric(accounts["opening_year"])
    record(section, "account opening year populated", oy.notna().all())

    if "closing_year" in accounts:
        cy = numeric(accounts["closing_year"])
        mask = cy.notna()
        record(section, "account closing year >= opening year", ((cy[mask] >= oy[mask]).all()))

    if "account_status" in accounts and "closing_year" in accounts:
        closed = accounts["account_status"].astype(str).str.upper().eq("CLOSED")
        cy = numeric(accounts["closing_year"])
        record(section, "closed accounts have closing year", cy[closed].notna().all())


def audit_cards(cards, customers, accounts):
    if cards is None or cards.empty:
        skip("Core banking", "card integrity", "cards.csv not present or empty")
        return

    id_col = "card_id" if "card_id" in cards else None
    if id_col:
        record("Core banking", "card_id primary key", unique_nonnull(cards, id_col))

    if "customer_id" in cards:
        ok, missing = fk_ok(cards, "customer_id", customers, "customer_id")
        record("Core banking", "card -> customer foreign key", ok, f"missing={len(missing)}")

    link_col = "linked_account_id" if "linked_account_id" in cards else (
        "account_id" if "account_id" in cards else None
    )
    if link_col:
        nonnull = cards[cards[link_col].notna()]
        ok, missing = fk_ok(nonnull, link_col, accounts, "account_id")
        record("Core banking", "card -> account foreign key", ok, f"missing={len(missing)}")

        if "customer_id" in cards:
            owner = accounts.set_index("account_id")["customer_id"].astype(str).to_dict()
            mask = cards[link_col].notna()
            same = cards.loc[mask].apply(
                lambda r: owner.get(str(r[link_col])) == str(r["customer_id"]), axis=1
            )
            record("Core banking", "linked card/account customer coherence", same.all())


def audit_loans(loans, snapshot, customers, branches):
    section = "Credit lifecycle"
    section_header(section)

    if loans is None or loans.empty:
        skip(section, "loan integrity", "loans.csv not present or empty")
        return

    record(section, "loan_id primary key", unique_nonnull(loans, "loan_id"))

    if "customer_id" in loans:
        ok, missing = fk_ok(loans, "customer_id", customers, "customer_id")
        record(section, "loan -> customer foreign key", ok, f"missing={len(missing)}")

    if branches is not None and "branch_id" in loans:
        ok, missing = fk_ok(loans, "branch_id", branches, "branch_id")
        record(section, "loan -> branch foreign key", ok, f"missing={len(missing)}")

    if snapshot is None or snapshot.empty:
        skip(section, "loan monthly snapshot", "loan_monthly_snapshot.csv not present or empty")
        return

    normalize_id(snapshot, ["loan_id"])
    ok, missing = fk_ok(snapshot, "loan_id", loans, "loan_id")
    record(section, "snapshot -> loan foreign key", ok, f"missing={len(missing)}")

    if {"loan_id", "year_month"}.issubset(snapshot.columns):
        record(section, "loan-month snapshot primary key",
               ~snapshot.duplicated(["loan_id", "year_month"]).any())

    if "outstanding_balance" in snapshot:
        bal = numeric(snapshot["outstanding_balance"])
        record(section, "snapshot balances non-negative",
               bal.notna().all() and (bal >= -0.01).all())

    if "actual_payment" in snapshot:
        pay = numeric(snapshot["actual_payment"])
        record(section, "snapshot payments non-negative",
               pay.notna().all() and (pay >= -0.01).all())


def audit_transactions(tx, balances, accounts, branches, banks):
    section = "Transactions"
    section_header(section)

    if tx is None or tx.empty:
        record(section, "transactions dataset exists", False)
        return

    if "transaction_id" in tx:
        record(section, "transaction_id primary key", unique_nonnull(tx, "transaction_id"))

    ok, missing = fk_ok(tx, "account_id", accounts, "account_id")
    record(section, "transaction -> account foreign key", ok, f"missing={len(missing)}")

    if "transaction_datetime" in tx:
        dt = parse_date(tx["transaction_datetime"])
        record(section, "transaction datetimes parse", dt.notna().all())
        record(section, "transaction dates within observation window",
               dt.notna().all() and (dt >= OBS_START).all() and (dt <= OBS_END).all())

    if "amount" in tx:
        amt = numeric(tx["amount"])
        record(section, "transaction amounts non-negative",
               amt.notna().all() and (amt >= 0).all())

    if {"transaction_status", "failure_reason"}.issubset(tx.columns):
        status = tx["transaction_status"].astype(str).str.upper()
        reason = tx["failure_reason"]
        completed = status.eq("COMPLETED")
        failed = status.eq("FAILED")
        record(section, "transaction statuses recognized", (completed | failed).all())
        record(section, "completed transactions have no failure reason",
               reason[completed].isna().all() | reason[completed].astype(str).str.strip().isin(["", "nan", "None"]).all())
        record(section, "failed transactions have failure reason",
               reason[failed].notna().all())

    if {"transaction_type", "direction"}.issubset(tx.columns):
        credit = {"TRANSFER_IN", "CASH_DEPOSIT", "LOAN_DISBURSEMENT", "INTEREST_CREDIT"}
        debit = {"TRANSFER_OUT", "CASH_WITHDRAWAL", "DEBIT_PURCHASE",
                 "SERVICE_PAYMENT", "CREDIT_CARD_PAYMENT", "LOAN_PAYMENT"}
        tt = tx["transaction_type"].astype(str)
        direction = tx["direction"].astype(str).str.upper()
        good = ((tt.isin(credit)) & direction.eq("CREDIT")) | ((tt.isin(debit)) & direction.eq("DEBIT"))
        record(section, "transaction type/direction coherence", good.all())

    if "transaction_branch_id" in tx and branches is not None:
        nonnull = tx[tx["transaction_branch_id"].notna()]
        if len(nonnull):
            ok, missing = fk_ok(nonnull, "transaction_branch_id", branches, "branch_id")
            record(section, "transaction -> branch foreign key", ok, f"missing={len(missing)}")

    if "counterparty_bank_id" in tx and banks is not None:
        nonnull = tx[tx["counterparty_bank_id"].notna()]
        if len(nonnull):
            allowed = set(banks["bank_id"].dropna().astype(str))
            allowed.add("B000")
            missing = set(nonnull["counterparty_bank_id"].astype(str)) - allowed
            record(section, "counterparty bank references valid", not missing, f"missing={len(missing)}")

    if {"transaction_type", "counterparty_type", "transfer_scope", "counterparty_bank_id"}.issubset(tx.columns):
        transfer = tx["transaction_type"].astype(str).isin(["TRANSFER_IN", "TRANSFER_OUT"])
        internal = transfer & tx["counterparty_type"].astype(str).eq("BTYT_CUSTOMER")
        scope = tx["transfer_scope"].astype(str)
        bank = tx["counterparty_bank_id"].astype(str)
        record(section, "internal transfer semantics",
               (scope[internal].eq("INTERNAL") & bank[internal].eq("B000")).all())

    audit_balances(tx, balances, accounts)


def audit_balances(tx, balances, accounts):
    section = "Balances"
    section_header(section)

    if balances is None or balances.empty:
        record(section, "account_balances dataset exists", False)
        return

    record(section, "account-month balance primary key",
           ~balances.duplicated(["account_id", "year_month"]).any())

    ok, missing = fk_ok(balances, "account_id", accounts, "account_id")
    record(section, "balance -> account foreign key", ok, f"missing={len(missing)}")

    for col in ["opening_balance", "total_inflows", "total_outflows", "closing_balance"]:
        if col in balances:
            balances[col] = numeric(balances[col])

    identity = (
        balances["opening_balance"] + balances["total_inflows"]
        - balances["total_outflows"] - balances["closing_balance"]
    ).abs()
    record(section, "monthly balance identity", (identity <= 0.02).all(),
           f"max_abs_diff={identity.max():.6f}")

    record(section, "closing balances non-negative",
           (balances["closing_balance"] >= -0.01).all())

    b = balances.copy()
    b["_m"] = parse_month(b["year_month"])
    b = b.sort_values(["account_id", "_m"])
    prev = b.groupby("account_id", sort=False)["closing_balance"].shift()
    prev_month = b.groupby("account_id", sort=False)["_m"].shift()
    consecutive = (b["_m"].dt.to_period("M") - prev_month.dt.to_period("M")).apply(
        lambda x: getattr(x, "n", np.nan) if pd.notna(x) else np.nan
    )
    mask = consecutive.eq(1)
    continuity = (b.loc[mask, "opening_balance"] - prev[mask]).abs()
    record(section, "month-to-month balance continuity",
           (continuity <= 0.02).all(),
           f"max_abs_diff={continuity.max() if len(continuity) else 0:.6f}")

    if {"transaction_status", "direction", "amount", "transaction_datetime"}.issubset(tx.columns):
        t = tx[tx["transaction_status"].astype(str).str.upper().eq("COMPLETED")].copy()
        t["_month"] = parse_date(t["transaction_datetime"]).dt.to_period("M").astype(str)
        t["amount"] = numeric(t["amount"])
        t["_in"] = np.where(t["direction"].astype(str).str.upper().eq("CREDIT"), t["amount"], 0.0)
        t["_out"] = np.where(t["direction"].astype(str).str.upper().eq("DEBIT"), t["amount"], 0.0)
        agg = t.groupby(["account_id", "_month"], sort=False).agg(
            tx_inflows=("_in", "sum"),
            tx_outflows=("_out", "sum"),
        ).reset_index()

        m = balances.merge(
            agg,
            left_on=["account_id", "year_month"],
            right_on=["account_id", "_month"],
            how="left",
        )
        m[["tx_inflows", "tx_outflows"]] = m[["tx_inflows", "tx_outflows"]].fillna(0.0)
        din = (m["total_inflows"] - m["tx_inflows"]).abs()
        dout = (m["total_outflows"] - m["tx_outflows"]).abs()
        record(section, "completed inflows reconcile to balances", (din <= 0.02).all(),
               f"max_abs_diff={din.max():.6f}")
        record(section, "completed outflows reconcile to balances", (dout <= 0.02).all(),
               f"max_abs_diff={dout.max():.6f}")


def audit_branches(branches, branch_perf):
    section = "Branch performance"
    section_header(section)

    if branches is None:
        record(section, "branches dataset exists", False)
        return

    record(section, "branch_id primary key", unique_nonnull(branches, "branch_id"))

    if branch_perf is None or branch_perf.empty:
        skip(section, "branch performance integrity", "branch_monthly_performance.csv not present or empty")
        return

    ok, missing = fk_ok(branch_perf, "branch_id", branches, "branch_id")
    record(section, "branch performance -> branch foreign key", ok, f"missing={len(missing)}")

    month_col = "year_month" if "year_month" in branch_perf else None
    if month_col:
        record(section, "branch-month performance primary key",
               ~branch_perf.duplicated(["branch_id", month_col]).any())


def audit_banks(banks, bank_market, bank_financials, bank_macro, bank_perf):
    section = "Bank performance"
    section_header(section)

    if banks is None:
        record(section, "banks dataset exists", False)
        return

    record(section, "bank_id primary key", unique_nonnull(banks, "bank_id"))

    for name, df in [
        ("bank market weights", bank_market),
        ("bank financials", bank_financials),
    ]:
        if df is None or df.empty:
            skip(section, name, f"{name} dataset not present or empty")
            continue
        if "bank_id" in df:
            ok, missing = fk_ok(df, "bank_id", banks, "bank_id")
            record(section, f"{name} -> bank foreign key", ok, f"missing={len(missing)}")

    if bank_market is not None and {"year", "market_weight"}.issubset(bank_market.columns):
        mw = bank_market.copy()
        mw["market_weight"] = numeric(mw["market_weight"])
        sums = mw.groupby("year")["market_weight"].sum()
        # Support either shares (1.0) or percentages (100.0).
        dist = np.minimum((sums - 1.0).abs(), (sums - 100.0).abs())
        record(section, "annual market weights reconcile", (dist <= 0.02).all(),
               f"year_sums={sums.round(4).to_dict()}")

    if bank_macro is not None and "year" in bank_macro:
        years = set(numeric(bank_macro["year"]).dropna().astype(int))
        record(section, "bank macro covers 2021-2026", set(range(2021, 2027)).issubset(years))

    if bank_perf is not None and not bank_perf.empty:
        month_col = "year_month" if "year_month" in bank_perf else None
        if month_col:
            record(section, "bank-month performance primary key",
                   ~bank_perf.duplicated([month_col]).any())


def audit_shocks(master_shocks, customer_state, idio):
    section = "External shocks"
    section_header(section)

    if master_shocks is None or master_shocks.empty:
        skip(section, "external shock layer", "external_shocks.csv not present or empty")
        return

    id_col = "shock_id" if "shock_id" in master_shocks else (
        "event_id" if "event_id" in master_shocks else None
    )
    if id_col:
        record(section, f"{id_col} primary key", unique_nonnull(master_shocks, id_col))

    date_cols = [c for c in ["start_date", "end_date"] if c in master_shocks]
    if len(date_cols) == 2:
        s = parse_date(master_shocks["start_date"])
        e = parse_date(master_shocks["end_date"])
        record(section, "shock start <= end", (s <= e).all())

    if customer_state is not None and not customer_state.empty:
        if {"customer_id", "year_month"}.issubset(customer_state.columns):
            record(section, "customer shock state grain unique",
                   ~customer_state.duplicated(["customer_id", "year_month"]).any())

    if idio is not None and not idio.empty:
        iid = "event_id" if "event_id" in idio else None
        if iid:
            record(section, "idiosyncratic event primary key", unique_nonnull(idio, iid))


def audit_campaigns(campaigns, campaign_customers, exposures, customers):
    section = "Campaign behavior"
    section_header(section)

    if campaigns is None or campaigns.empty:
        skip(section, "campaign layer", "campaigns.csv not present or empty")
        return

    record(section, "campaign_id primary key", unique_nonnull(campaigns, "campaign_id"))

    if {"start_date", "end_date"}.issubset(campaigns.columns):
        s = parse_date(campaigns["start_date"])
        e = parse_date(campaigns["end_date"])
        record(section, "campaign start <= end", (s <= e).all())

    if campaign_customers is None or campaign_customers.empty:
        skip(section, "campaign customer behavior", "campaign_customers.csv not present or empty")
        return

    normalize_id(campaign_customers, ["campaign_id", "customer_id"])
    record(section, "campaign-customer primary key",
           ~campaign_customers.duplicated(["campaign_id", "customer_id"]).any())

    ok, missing = fk_ok(campaign_customers, "campaign_id", campaigns, "campaign_id")
    record(section, "campaign customer -> campaign foreign key", ok, f"missing={len(missing)}")

    # Acquisition campaigns may legitimately contain future customers, so a customer
    # absent at selection time is not automatically treated as a targeting failure.
    known = set(customers["customer_id"].astype(str))
    campaign_ids = set(campaign_customers["customer_id"].dropna().astype(str))
    unknown = campaign_ids - known
    record(section, "campaign customer IDs belong to frozen customer universe",
           not unknown, f"missing={len(unknown)}")

    if {"selection_date", "exposure_date", "response_date"}.issubset(campaign_customers.columns):
        sel = parse_date(campaign_customers["selection_date"])
        exp = parse_date(campaign_customers["exposure_date"])
        resp = parse_date(campaign_customers["response_date"])
        record(section, "exposure occurs after selection",
               (exp.dropna() >= sel[exp.notna()]).all())
        record(section, "response occurs after exposure",
               (resp.dropna() >= exp[resp.notna()]).all())

    if exposures is None or exposures.empty:
        skip(section, "campaign exposure events", "campaign_exposures.csv not present or empty")
        return

    if "exposure_id" in exposures:
        record(section, "exposure_id primary key", unique_nonnull(exposures, "exposure_id"))

    ok, missing = fk_ok(exposures, "campaign_id", campaigns, "campaign_id")
    record(section, "exposure -> campaign foreign key", ok, f"missing={len(missing)}")

    selected_pairs = set(zip(
        campaign_customers["campaign_id"].astype(str),
        campaign_customers["customer_id"].astype(str),
    ))
    exposure_pairs = set(zip(
        exposures["campaign_id"].astype(str),
        exposures["customer_id"].astype(str),
    ))
    missing_pairs = exposure_pairs - selected_pairs
    record(section, "every exposure belongs to selected relationship",
           not missing_pairs, f"missing_pairs={len(missing_pairs)}")


def audit_operational_exports(canonical, operational, reliability_world, reliability_audit):
    section = "Operational reliability"
    section_header(section)

    if operational is None or not operational:
        skip(
            section,
            "operational export layer",
            "data/operational not present or no exports resolved",
        )
        return

    protected_datasets = [
        "customers",
        "accounts",
        "cards",
        "loans",
        "branches",
        "transactions",
    ]

    for name in protected_datasets:
        source = canonical.get(name)
        out = operational.get(name)

        if source is None or out is None:
            skip(
                section,
                f"{name} operational export",
                "canonical or operational dataset not present",
            )
            continue

        record(
            section,
            f"{name} operational row count preserved",
            len(source) == len(out),
            f"canonical={len(source)} operational={len(out)}",
        )

        if name == "transactions":
            protected_cols = [
                "transaction_id",
                "account_id",
                "amount",
                "direction",
                "transaction_status",
                "failure_reason",
                "transaction_type",
            ]

            left = source.sort_values("transaction_id").reset_index(drop=True)
            right = out.sort_values("transaction_id").reset_index(drop=True)

            protected_ok = True
            changed = []

            for col in protected_cols:
                if col not in left.columns or col not in right.columns:
                    continue

                a = left[col]
                b = right[col]

                if pd.api.types.is_numeric_dtype(a):
                    same = np.isclose(
                        pd.to_numeric(a, errors="coerce"),
                        pd.to_numeric(b, errors="coerce"),
                        equal_nan=True,
                    ).all()
                else:
                    same = a.fillna("<NA>").astype(str).equals(
                        b.fillna("<NA>").astype(str)
                    )

                if not same:
                    protected_ok = False
                    changed.append(col)

            record(
                section,
                "protected transaction truth preserved operationally",
                protected_ok,
                f"changed={changed}",
            )

    canonical_exp = canonical.get("campaign_exposures")
    operational_exp = operational.get("campaign_exposures")

    if canonical_exp is not None and operational_exp is not None:
        record(
            section,
            "campaign exposure operational row count not reduced",
            len(operational_exp) >= len(canonical_exp),
            f"canonical={len(canonical_exp)} operational={len(operational_exp)}",
        )

    if reliability_world is not None:
        required_cols = {
            "world_seed",
            "mode",
            "reliability_level",
            "incident_id",
            "incident_family",
            "affected_system",
            "start_date",
            "end_date",
            "latent_severity",
        }
        record(
            section,
            "reliability world schema",
            required_cols.issubset(reliability_world.columns),
            f"missing={sorted(required_cols - set(reliability_world.columns))}",
        )

    if reliability_audit is not None:
        required_cols = {
            "dataset",
            "anomaly_family",
            "records_exposed",
            "records_affected",
            "realized_rate",
        }
        schema_ok = required_cols.issubset(reliability_audit.columns)

        record(
            section,
            "reliability audit schema",
            schema_ok,
            f"missing={sorted(required_cols - set(reliability_audit.columns))}",
        )

        if schema_ok and not reliability_audit.empty:
            exposed = numeric(reliability_audit["records_exposed"])
            affected = numeric(reliability_audit["records_affected"])
            rate = numeric(reliability_audit["realized_rate"])

            record(
                section,
                "reliability audit counts coherent",
                exposed.notna().all()
                and affected.notna().all()
                and (affected >= 0).all()
                and (exposed >= 0).all()
                and (affected <= exposed).all(),
            )

            record(
                section,
                "reliability realized rates bounded",
                rate.notna().all() and rate.between(0, 1).all(),
            )


def main():
    print("=" * 92)
    print("BTYT FINAL CROSS-SYSTEM AUDIT — V2.1.0")
    print("=" * 92)
    print(f"Root: {ROOT}")

    paths = {
        "customers": resolve_dataset(
            "customers",
            GENERATED_CORE / "customers",
            required=True,
        ),
        "accounts": resolve_dataset(
            "accounts",
            GENERATED_CORE / "accounts",
            required=True,
        ),
        "cards": resolve_dataset(
            "cards",
            GENERATED_CORE / "cards",
            GENERATED_CREDIT / "cards",
        ),
        "loans": resolve_dataset(
            "loans",
            GENERATED_CORE / "loans",
            GENERATED_CREDIT / "loans",
        ),
        "loan_snapshot": resolve_dataset(
            "loan_monthly_snapshot",
            GENERATED_CREDIT / "loan_monthly_snapshot",
            required=True,
        ),
        "transactions": resolve_dataset(
            "transactions",
            GENERATED_TRANSACTIONS / "transactions",
            required=True,
        ),
        "balances": resolve_dataset(
            "account_balances",
            GENERATED_CORE / "account_balances",
            GENERATED_TRANSACTIONS / "account_balances",
            required=True,
        ),
        "branches": resolve_dataset(
            "branches",
            GENERATED_CORE / "branches",
            required=True,
        ),
        "branch_perf": resolve_dataset(
            "branch_monthly_performance",
            GENERATED_PERFORMANCE / "branch_monthly_performance",
            required=True,
        ),
        "bank_perf": resolve_dataset(
            "bank_monthly_performance",
            GENERATED_PERFORMANCE / "bank_monthly_performance",
            required=True,
        ),
        "banks": resolve_dataset(
            "banks",
            GENERATED_CORE / "banks",
            required=True,
        ),
        "bank_market": resolve_dataset(
            "bank_market_weights",
            GENERATED_PERFORMANCE / "bank_market_weights",
            GENERATED_CORE / "bank_market_weights",
        ),
        "bank_financials": resolve_dataset(
            "bank_financials",
            GENERATED_PERFORMANCE / "bank_financials",
            GENERATED_CORE / "bank_financials",
        ),
        "bank_macro": resolve_dataset(
            "bank_macro_environment",
            GENERATED_PERFORMANCE / "bank_macro_environment",
            GENERATED_CORE / "bank_macro_environment",
        ),
        "external_shocks": resolve_dataset(
            "external_shocks",
            GENERATED_PERFORMANCE / "external_shocks",
            GENERATED_CORE / "external_shocks",
        ),
        "external_customer_state": resolve_dataset(
            "external_customer_monthly_state",
            INTERIM_WORLD / "external_customer_monthly_state",
        ),
        "external_idio": resolve_dataset(
            "external_idiosyncratic_events",
            INTERIM_WORLD / "external_idiosyncratic_events",
        ),
        "campaigns": resolve_dataset(
            "campaigns",
            GENERATED_CAMPAIGNS / "campaigns",
        ),
        "campaign_customers": resolve_dataset(
            "campaign_customers",
            GENERATED_CAMPAIGNS / "campaign_customers",
            required=True,
        ),
        "campaign_exposures": resolve_dataset(
            "campaign_exposures",
            GENERATED_CAMPAIGNS / "campaign_exposures",
            required=True,
        ),
        "operational_customers": resolve_dataset(
            "operational customers",
            OPERATIONAL / "customers",
        ),
        "operational_accounts": resolve_dataset(
            "operational accounts",
            OPERATIONAL / "accounts",
        ),
        "operational_cards": resolve_dataset(
            "operational cards",
            OPERATIONAL / "cards",
        ),
        "operational_loans": resolve_dataset(
            "operational loans",
            OPERATIONAL / "loans",
        ),
        "operational_branches": resolve_dataset(
            "operational branches",
            OPERATIONAL / "branches",
        ),
        "operational_transactions": resolve_dataset(
            "operational transactions",
            OPERATIONAL / "transactions",
        ),
        "operational_campaign_customers": resolve_dataset(
            "operational campaign_customers",
            OPERATIONAL / "campaign_customers",
        ),
        "operational_campaign_exposures": resolve_dataset(
            "operational campaign_exposures",
            OPERATIONAL / "campaign_exposures",
        ),
        "reliability_world": resolve_dataset(
            "data_reliability_world",
            INTERIM / "data_reliability_world",
        ),
        "reliability_audit": resolve_dataset(
            "data_reliability_audit",
            INTERIM / "data_reliability_audit",
        ),
        "operational_lineage": resolve_dataset(
            "operational_export_sources",
            INTERIM / "operational_export_sources",
        ),
    }

    print()
    print("Resolved datasets")
    print("-" * 92)
    for name, path in paths.items():
        print(
            f"  {name:<34} "
            f"{str(path) if path is not None else 'NOT FOUND / OPTIONAL'}"
        )

    data = {
        name: load_table(path) if path is not None else None
        for name, path in paths.items()
    }

    print()
    print("Resolved shapes")
    print("-" * 92)
    for name, df in data.items():
        if df is None:
            continue
        print(
            f"  {name:<34} rows={len(df):>10,}  "
            f"cols={len(df.columns):>4}"
        )

    for df in data.values():
        normalize_id(
            df,
            [
                "customer_id",
                "account_id",
                "linked_account_id",
                "card_id",
                "loan_id",
                "branch_id",
                "transaction_branch_id",
                "bank_id",
                "counterparty_bank_id",
                "campaign_id",
                "exposure_id",
                "shock_id",
                "event_id",
            ],
        )

    audit_customers(data["customers"])
    audit_accounts(
        data["accounts"],
        data["customers"],
        data["branches"],
    )
    audit_cards(
        data["cards"],
        data["customers"],
        data["accounts"],
    )
    audit_loans(
        data["loans"],
        data["loan_snapshot"],
        data["customers"],
        data["branches"],
    )
    audit_transactions(
        data["transactions"],
        data["balances"],
        data["accounts"],
        data["branches"],
        data["banks"],
    )
    audit_branches(
        data["branches"],
        data["branch_perf"],
    )
    audit_banks(
        data["banks"],
        data["bank_market"],
        data["bank_financials"],
        data["bank_macro"],
        data["bank_perf"],
    )
    audit_shocks(
        data["external_shocks"],
        data["external_customer_state"],
        data["external_idio"],
    )
    audit_campaigns(
        data["campaigns"],
        data["campaign_customers"],
        data["campaign_exposures"],
        data["customers"],
    )

    canonical_for_operational = {
        "customers": data["customers"],
        "accounts": data["accounts"],
        "cards": data["cards"],
        "loans": data["loans"],
        "branches": data["branches"],
        "transactions": data["transactions"],
        "campaign_customers": data["campaign_customers"],
        "campaign_exposures": data["campaign_exposures"],
    }

    operational = {
        "customers": data["operational_customers"],
        "accounts": data["operational_accounts"],
        "cards": data["operational_cards"],
        "loans": data["operational_loans"],
        "branches": data["operational_branches"],
        "transactions": data["operational_transactions"],
        "campaign_customers": data["operational_campaign_customers"],
        "campaign_exposures": data["operational_campaign_exposures"],
    }

    audit_operational_exports(
        canonical_for_operational,
        operational,
        data["reliability_world"],
        data["reliability_audit"],
    )

    print()
    print("=" * 92)
    print("BTYT FINAL CROSS-SYSTEM AUDIT — SUMMARY")
    print("=" * 92)

    sections = [
        "Core banking",
        "Credit lifecycle",
        "Transactions",
        "Balances",
        "Branch performance",
        "Bank performance",
        "External shocks",
        "Campaign behavior",
        "Operational reliability",
    ]

    section_status = {}
    for section in sections:
        vals = [
            passed
            for result_section, _, passed, _ in RESULTS
            if result_section == section and passed is not None
        ]

        if not vals:
            section_status[section] = None
            label = "SKIP"
        else:
            section_status[section] = all(vals)
            label = "PASS" if section_status[section] else "FAIL"

        print(f"{section:<32} {label}")

    hard_results = [
        passed
        for _, _, passed, _ in RESULTS
        if passed is not None
    ]
    final_pass = bool(hard_results) and all(hard_results)

    print("-" * 92)
    print(
        f"{'Referential integrity':<32} "
        f"{'PASS' if final_pass else 'CHECK ABOVE'}"
    )
    print(
        f"{'Temporal integrity':<32} "
        f"{'PASS' if final_pass else 'CHECK ABOVE'}"
    )
    print(
        f"{'Financial reconciliation':<32} "
        f"{'PASS' if final_pass else 'CHECK ABOVE'}"
    )
    print(
        f"{'Operational reliability contract':<32} "
        f"{'PASS' if final_pass else 'CHECK ABOVE'}"
    )
    print("-" * 92)
    print(f"FINAL VALIDATION: {'PASS' if final_pass else 'FAIL'}")

    if DETAILS:
        print()
        print("Details / skipped checks")
        print("-" * 92)
        for section, check, status, detail in DETAILS:
            print(
                f"[{status}] {section} / {check}: {detail}"
            )

    INTERIM_AUDITS.mkdir(parents=True, exist_ok=True)

    results_df = pd.DataFrame(
        RESULTS,
        columns=["section", "check", "passed", "detail"],
    )
    results_df["status"] = results_df["passed"].map(
        {True: "PASS", False: "FAIL"}
    ).fillna("SKIP")

    results_out = INTERIM_AUDITS / "cross_system_audit_results.csv"
    results_df[
        ["section", "check", "status", "detail"]
    ].to_csv(
        results_out,
        index=False,
    )

    resolved_rows = []
    for name, path in paths.items():
        df = data.get(name)
        resolved_rows.append(
            {
                "dataset": name,
                "path": str(path) if path is not None else "",
                "exists": path is not None,
                "rows": len(df) if df is not None else np.nan,
                "columns": (
                    len(df.columns)
                    if df is not None
                    else np.nan
                ),
            }
        )

    resolved_out = (
        INTERIM_AUDITS / "cross_system_resolved_sources.csv"
    )
    pd.DataFrame(resolved_rows).to_csv(
        resolved_out,
        index=False,
    )

    print()
    print(f"Saved audit results:   {results_out}")
    print(f"Saved source registry: {resolved_out}")

    if not final_pass:
        raise SystemExit(1)

    print()
    print("BTYT FINAL CROSS-SYSTEM AUDIT V2.1.0: PASS")
    print("All canonical datasets remained read-only.")


if __name__ == "__main__":
    main()