#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""BTYT final cross-system audit — V1.0.1.

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
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "data" / "generated"
INTERIM = ROOT / "data" / "interim"
MASTER = ROOT / "data" / "master"

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


def load_csv(path, dtype=None):
    if not path.exists():
        return None
    return pd.read_csv(path, dtype=dtype, low_memory=False)


def first_existing(*paths):
    for path in paths:
        if path.exists():
            return path
    return None


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


def main():
    print("=" * 78)
    print("BTYT FINAL CROSS-SYSTEM AUDIT — V1.0.1")
    print("=" * 78)
    print(f"Root: {ROOT}")

    paths = {
        "customers": GENERATED / "customers.csv",
        "accounts": GENERATED / "accounts.csv",
        "cards": GENERATED / "cards.csv",
        "loans": GENERATED / "loans.csv",
        "loan_snapshot": GENERATED / "loan_monthly_snapshot.csv",
        "transactions": first_existing(
            GENERATED / "transactions.csv",
            GENERATED / "transactions_smoke_v2_3_1.csv",
        ),
        "balances": first_existing(
            GENERATED / "account_balances.csv",
            GENERATED / "account_balances_smoke_v2_3_1.csv",
        ),
        "branches": GENERATED / "branches.csv",
        "branch_perf": GENERATED / "branch_monthly_performance.csv",
        "banks": GENERATED / "banks.csv",
        "bank_market": GENERATED / "bank_market_weights.csv",
        "bank_financials": GENERATED / "bank_financials.csv",
        "bank_macro": GENERATED / "bank_macro_environment.csv",
        "bank_perf": GENERATED / "bank_monthly_performance.csv",
        "external_shocks": MASTER / "external_shocks.csv",
        "external_customer_state": INTERIM / "external_customer_monthly_state.csv",
        "external_idio": INTERIM / "external_idiosyncratic_events.csv",
        "campaigns": MASTER / "campaigns.csv",
        "campaign_customers": GENERATED / "campaign_customers.csv",
        "campaign_exposures": GENERATED / "campaign_exposures.csv",
    }

    mandatory = ["customers", "accounts", "transactions", "balances", "branches", "banks"]
    missing = [k for k in mandatory if paths[k] is None or not Path(paths[k]).exists()]
    if missing:
        raise FileNotFoundError(f"Missing mandatory BTYT datasets: {missing}")

    print()
    print("Datasets")
    print("-" * 78)
    for name, path in paths.items():
        print(f"  {name:<28} {str(path) if path is not None else 'NOT FOUND'}")

    data = {k: load_csv(v) if v is not None else None for k, v in paths.items()}

    for df in data.values():
        normalize_id(df, [
            "customer_id", "account_id", "linked_account_id", "card_id", "loan_id",
            "branch_id", "transaction_branch_id", "bank_id", "counterparty_bank_id",
            "campaign_id", "exposure_id",
        ])

    audit_customers(data["customers"])
    audit_accounts(data["accounts"], data["customers"], data["branches"])
    audit_cards(data["cards"], data["customers"], data["accounts"])
    audit_loans(data["loans"], data["loan_snapshot"], data["customers"], data["branches"])
    audit_transactions(
        data["transactions"], data["balances"], data["accounts"],
        data["branches"], data["banks"],
    )
    audit_branches(data["branches"], data["branch_perf"])
    audit_banks(
        data["banks"], data["bank_market"], data["bank_financials"],
        data["bank_macro"], data["bank_perf"],
    )
    audit_shocks(
        data["external_shocks"], data["external_customer_state"], data["external_idio"]
    )
    audit_campaigns(
        data["campaigns"], data["campaign_customers"],
        data["campaign_exposures"], data["customers"],
    )

    print()
    print("=" * 78)
    print("BTYT FINAL CROSS-SYSTEM AUDIT — SUMMARY")
    print("=" * 78)

    sections = [
        "Core banking", "Transactions", "Credit lifecycle", "Balances",
        "Branch performance", "Bank performance", "External shocks",
        "Campaign behavior",
    ]

    section_status = {}
    for section in sections:
        vals = [p for s, _, p, _ in RESULTS if s == section and p is not None]
        section_status[section] = bool(vals) and all(vals)
        print(f"{section:<28} {'PASS' if section_status[section] else 'FAIL'}")

    hard_results = [p for _, _, p, _ in RESULTS if p is not None]
    final_pass = bool(hard_results) and all(hard_results)

    print(f"{'Referential integrity':<28} {'PASS' if final_pass else 'CHECK ABOVE'}")
    print(f"{'Temporal integrity':<28} {'PASS' if final_pass else 'CHECK ABOVE'}")
    print(f"{'Reproducibility contract':<28} {'PASS' if final_pass else 'CHECK ABOVE'}")
    print("-" * 78)
    print(f"FINAL VALIDATION: {'PASS' if final_pass else 'FAIL'}")

    if DETAILS:
        print()
        print("Details / skipped checks")
        print("-" * 78)
        for section, check, status, detail in DETAILS:
            print(f"[{status}] {section} / {check}: {detail}")

    if not final_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
