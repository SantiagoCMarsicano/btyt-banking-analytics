#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""BTYT — Post-generation economic audit for Transactions V2.3.

This script never regenerates or mutates canonical data. It reads the frozen
outputs and evaluates economic plausibility after structural validation passed.
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1] if Path(__file__).resolve().parent.name == "scripts" else Path.cwd()
GENERATED = ROOT / "data" / "generated"
INTERIM = ROOT / "data" / "interim"

TX_PATH = GENERATED / "transactions.csv"
BAL_PATH = GENERATED / "account_balances.csv"
ACCOUNTS_PATH = GENERATED / "accounts.csv"
CUSTOMERS_PATH = GENERATED / "customers.csv"
LOANS_PATH = GENERATED / "loans.csv"
SNAPSHOT_PATH = GENERATED / "loan_monthly_snapshot.csv"
BANKS_PATH = GENERATED / "banks.csv"
PAIRS_PATH = INTERIM / "internal_transfer_pairs.csv"

FX = {2021: 43.6, 2022: 41.2, 2023: 38.8, 2024: 40.3, 2025: 42.0, 2026: 43.5}
TRANSFER_TYPES = {"TRANSFER_IN", "TRANSFER_OUT"}


def pct(x):
    return f"{100*x:.2f}%"


def money(x):
    return f"{x:,.2f}"


def section(title):
    print("\n" + "=" * 88)
    print(title)
    print("=" * 88)


def q(series, qs=(0.50, 0.90, 0.95, 0.99, 0.999, 1.0)):
    s = pd.to_numeric(series, errors="coerce").dropna()
    return s.quantile(list(qs)) if len(s) else pd.Series(dtype=float)


def load():
    required = [TX_PATH, BAL_PATH, ACCOUNTS_PATH, CUSTOMERS_PATH, BANKS_PATH]
    for p in required:
        if not p.exists():
            raise FileNotFoundError(p)

    tx = pd.read_csv(
        TX_PATH,
        dtype={
            "transaction_id": str, "account_id": str, "transaction_type": str,
            "direction": str, "channel": str, "counterparty_type": str,
            "transfer_scope": str, "counterparty_bank_id": str,
            "transaction_branch_id": str, "transaction_status": str,
            "merchant_category": str, "failure_reason": str,
        },
        parse_dates=["transaction_datetime"],
    )
    bal = pd.read_csv(BAL_PATH, dtype={"account_id": str, "year_month": str})
    acc = pd.read_csv(ACCOUNTS_PATH, dtype={"account_id": str, "customer_id": str, "product_id": str})
    cus = pd.read_csv(CUSTOMERS_PATH, dtype={"customer_id": str})
    banks = pd.read_csv(BANKS_PATH, dtype={"bank_id": str})
    loans = pd.read_csv(LOANS_PATH, dtype={"loan_id": str, "customer_id": str, "product_id": str}) if LOANS_PATH.exists() else pd.DataFrame()
    snap = pd.read_csv(SNAPSHOT_PATH, dtype={"loan_id": str, "year_month": str}) if SNAPSHOT_PATH.exists() else pd.DataFrame()
    pairs = pd.read_csv(PAIRS_PATH, dtype=str) if PAIRS_PATH.exists() else pd.DataFrame()
    return tx, bal, acc, cus, banks, loans, snap, pairs


def main():
    tx, bal, acc, cus, banks, loans, snap, pairs = load()
    tx["amount"] = pd.to_numeric(tx["amount"], errors="coerce")
    tx["year"] = tx["transaction_datetime"].dt.year
    tx["year_month"] = tx["transaction_datetime"].dt.to_period("M").astype(str)
    tx["completed"] = tx["transaction_status"].eq("COMPLETED")

    account_customer = acc.set_index("account_id")["customer_id"].to_dict()
    tx["customer_id"] = tx["account_id"].map(account_customer)

    # Currency is inferred from the frozen account product architecture.
    currency_map = {
        "P001": "UYU", "P002": "USD", "P003": "UYU", "P004": "USD",
        "P005": "UYU", "P006": "UYU", "P007": "UYU", "P008": "USD",
    }
    account_currency = acc.set_index("account_id")["product_id"].map(currency_map).to_dict()
    tx["currency"] = tx["account_id"].map(account_currency)
    tx["amount_uyu"] = tx["amount"] * np.where(tx["currency"].eq("USD"), tx["year"].map(FX), 1.0)

    section("BTYT TRANSACTIONS V2.3 — POST-GENERATION ECONOMIC AUDIT")
    print(f"Transactions: {len(tx):,}")
    print(f"Completed: {tx['completed'].sum():,} ({pct(tx['completed'].mean())})")
    print(f"Accounts represented: {tx['account_id'].nunique():,}")
    print(f"Customers represented: {tx['customer_id'].nunique():,}")
    print(f"Account-months: {len(bal):,}")
    print(f"Internal transfer pairs: {len(pairs):,}")

    section("1. ACTIVITY BY YEAR")
    annual = tx.groupby("year").agg(
        transactions=("transaction_id", "size"),
        completed=("completed", "sum"),
        total_amount_uyu=("amount_uyu", "sum"),
        median_amount_uyu=("amount_uyu", "median"),
        active_accounts=("account_id", "nunique"),
        active_customers=("customer_id", "nunique"),
    )
    annual["failed_rate"] = 1 - annual["completed"] / annual["transactions"]
    annual["tx_per_active_account"] = annual["transactions"] / annual["active_accounts"]
    print(annual.to_string(formatters={"failed_rate": pct, "total_amount_uyu": money, "median_amount_uyu": money, "tx_per_active_account": lambda x: f"{x:.1f}"}))

    section("2. CHANNEL MIGRATION BY YEAR (% OF TRANSACTIONS)")
    channel = pd.crosstab(tx["year"], tx["channel"], normalize="index") * 100
    print(channel.round(2).to_string())
    if 2021 in channel.index and 2026 in channel.index:
        print("\n2021 -> 2026 percentage-point change:")
        print((channel.loc[2026] - channel.loc[2021]).sort_values(ascending=False).round(2).to_string())

    section("3. CASH USAGE BY YEAR")
    cash = tx[tx["transaction_type"].isin(["CASH_WITHDRAWAL", "CASH_DEPOSIT"])]
    cash_share = cash.groupby("year").size() / tx.groupby("year").size()
    print((cash_share * 100).round(2).rename("cash_tx_share_pct").to_string())

    section("4. FAILURE RATE BY YEAR")
    fail = tx.groupby("year")["completed"].apply(lambda s: 100 * (1 - s.mean()))
    print(fail.round(3).rename("failed_pct").to_string())

    transfers = tx[tx["transaction_type"].isin(TRANSFER_TYPES)].copy()
    section("5. TRANSFER SCOPE BY YEAR (% OF TRANSFERS)")
    scope = pd.crosstab(transfers["year"], transfers["transfer_scope"], normalize="index") * 100
    print(scope.round(2).to_string())

    section("6. EXTERNAL TRANSFER FLOWS — COUNTS AND UYU-EQUIVALENT AMOUNTS")
    ext = transfers[transfers["transfer_scope"].isin(["DOMESTIC_EXTERNAL", "INTERNATIONAL"])].copy()
    ext_completed = ext[ext["completed"]].copy()
    flow_count = pd.crosstab(ext_completed["year"], ext_completed["transaction_type"])
    flow_amt = ext_completed.pivot_table(index="year", columns="transaction_type", values="amount_uyu", aggfunc="sum", fill_value=0)
    for col in ["TRANSFER_IN", "TRANSFER_OUT"]:
        if col not in flow_count: flow_count[col] = 0
        if col not in flow_amt: flow_amt[col] = 0.0
    flow_count["net_count_in_minus_out"] = flow_count["TRANSFER_IN"] - flow_count["TRANSFER_OUT"]
    flow_amt["net_amount_in_minus_out"] = flow_amt["TRANSFER_IN"] - flow_amt["TRANSFER_OUT"]
    print("Counts:")
    print(flow_count.to_string())
    print("\nAmounts (UYU equivalent):")
    print(flow_amt.to_string(formatters={c: money for c in flow_amt.columns}))

    section("7. EXTERNAL COUNTERPARTY BANKS BY YEAR — COMPLETED TRANSFERS")
    bank_names = banks.set_index("bank_id")["bank_name"].astype(str).to_dict()
    ext_completed["bank_name"] = ext_completed["counterparty_bank_id"].map(bank_names).fillna(ext_completed["counterparty_bank_id"])
    bank_year = pd.crosstab(ext_completed["bank_name"], ext_completed["year"])
    bank_year["TOTAL"] = bank_year.sum(axis=1)
    print(bank_year.sort_values("TOTAL", ascending=False).to_string())

    section("8. EXTERNAL TRANSFER SIZE BY BANK")
    bank_size = ext_completed.groupby(["counterparty_bank_id", "bank_name"]).agg(
        n=("transaction_id", "size"),
        median_uyu=("amount_uyu", "median"),
        p95_uyu=("amount_uyu", lambda s: s.quantile(.95)),
        p99_uyu=("amount_uyu", lambda s: s.quantile(.99)),
        total_uyu=("amount_uyu", "sum"),
        usd_share=("currency", lambda s: s.eq("USD").mean()),
    ).sort_values("n", ascending=False)
    print(bank_size.to_string(formatters={"median_uyu": money, "p95_uyu": money, "p99_uyu": money, "total_uyu": money, "usd_share": pct}))

    section("9. TRANSACTION AMOUNT OUTLIERS — COMPLETED ONLY")
    completed = tx[tx["completed"]].copy()
    by_type = completed.groupby("transaction_type")["amount_uyu"].agg(
        n="size", median="median", mean="mean", max="max",
        p95=lambda s: s.quantile(.95), p99=lambda s: s.quantile(.99), p999=lambda s: s.quantile(.999)
    ).sort_values("n", ascending=False)
    print(by_type.to_string(formatters={c: money for c in ["median", "mean", "max", "p95", "p99", "p999"]}))
    print("\nTop 20 completed transactions by UYU-equivalent amount:")
    cols = ["transaction_id", "transaction_datetime", "transaction_type", "amount", "currency", "amount_uyu", "account_id", "transfer_scope", "counterparty_bank_id"]
    print(completed.nlargest(20, "amount_uyu")[cols].to_string(index=False, formatters={"amount": money, "amount_uyu": money}))

    section("10. CUSTOMER / ACCOUNT ACTIVITY CONCENTRATION")
    acct_counts = tx.groupby("account_id").size().sort_values(ascending=False)
    cust_counts = tx.groupby("customer_id").size().sort_values(ascending=False)
    print("Transactions per account quantiles:")
    print(q(acct_counts).round(1).to_string())
    print("\nTransactions per customer quantiles:")
    print(q(cust_counts).round(1).to_string())
    total = len(tx)
    for label, s in [("accounts", acct_counts), ("customers", cust_counts)]:
        n1 = max(1, int(np.ceil(len(s) * .01)))
        n5 = max(1, int(np.ceil(len(s) * .05)))
        print(f"Top 1% of {label}: {pct(s.iloc[:n1].sum()/total)} of transactions")
        print(f"Top 5% of {label}: {pct(s.iloc[:n5].sum()/total)} of transactions")

    section("11. ACCOUNT BALANCE DISTRIBUTION")
    for col in ["opening_balance", "total_inflows", "total_outflows", "closing_balance"]:
        bal[col] = pd.to_numeric(bal[col], errors="coerce")
    print("Closing balance quantiles in native account currency:")
    print(q(bal["closing_balance"]).round(2).to_string())
    print(f"Negative closing balances: {(bal['closing_balance'] < -0.005).sum():,}")
    print(f"Zero closing balances: {(bal['closing_balance'].abs() <= .005).sum():,} ({pct((bal['closing_balance'].abs() <= .005).mean())})")

    annual_bal = bal.copy()
    annual_bal["year"] = pd.to_numeric(annual_bal["year_month"].str[:4], errors="coerce")
    year_end = annual_bal.sort_values("year_month").groupby(["account_id", "year"], as_index=False).tail(1)
    print("\nYear-end aggregate closing balance (native currencies mixed; trend diagnostic only):")
    print(year_end.groupby("year")["closing_balance"].sum().apply(money).to_string())

    section("12. LOAN TRANSACTION RECONCILIATION DIAGNOSTICS")
    loan_tx = tx[tx["transaction_type"].isin(["LOAN_PAYMENT", "LOAN_DISBURSEMENT"])].copy()
    print(f"LOAN_PAYMENT rows: {(loan_tx['transaction_type']=='LOAN_PAYMENT').sum():,}")
    print(f"LOAN_DISBURSEMENT rows: {(loan_tx['transaction_type']=='LOAN_DISBURSEMENT').sum():,}")
    print(f"Completed loan payments: {((loan_tx['transaction_type']=='LOAN_PAYMENT') & loan_tx['completed']).sum():,}")
    print(f"Completed loan disbursements: {((loan_tx['transaction_type']=='LOAN_DISBURSEMENT') & loan_tx['completed']).sum():,}")
    if not loans.empty:
        print(f"Master loans: {len(loans):,}")
        print(f"Borrowers in master: {loans['customer_id'].nunique():,}")
    if not snap.empty:
        snap["actual_payment"] = pd.to_numeric(snap["actual_payment"], errors="coerce").fillna(0.0)
        positive_payment_months = int((snap["actual_payment"] > 0).sum())
        print(f"Snapshot loan-months with actual_payment > 0: {positive_payment_months:,}")
        print("Note: transaction rows need not equal snapshot positive-payment months because the transaction engine uses an observation probability and account eligibility rules.")

    section("13. AUDIT FLAGS")
    flags = []
    if tx["amount"].isna().any() or (tx["amount"] < 0).any():
        flags.append("FAIL: invalid transaction amounts detected")
    if tx["customer_id"].isna().any():
        flags.append("FAIL: transaction account missing customer mapping")
    if (bal["closing_balance"] < -0.005).any():
        flags.append("FAIL: negative closing balance detected")
    if ext["counterparty_bank_id"].isna().any():
        flags.append("FAIL: external transfer missing bank id")
    if not set(ext["counterparty_bank_id"].dropna()).issubset(set(banks["bank_id"])):
        flags.append("FAIL: external transfer bank id outside banks.csv")
    if len(annual) != 6 or set(annual.index) != set(range(2021, 2027)):
        flags.append("WARN: transaction years do not cover exactly 2021-2026")
    if not flags:
        flags.append("PASS: no structural/economic audit red flags triggered")
    for flag in flags:
        print(flag)

    print("\nAudit complete. This script does not modify canonical files.")


if __name__ == "__main__":
    main()