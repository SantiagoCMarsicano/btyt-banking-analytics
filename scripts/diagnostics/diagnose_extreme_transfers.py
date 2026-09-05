#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""BTYT — Extreme transfer/customer plausibility diagnostic.

Purpose:
- inspect the accounts/customers behind the largest completed transfers;
- compare transfer size with customer income/revenue capacity;
- identify whether extreme transfers are concentrated in plausible business clients;
- flag suspicious retail or capacity-inconsistent outliers.

This script is read-only. It does not modify canonical BTYT files.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

GENERATED = ROOT / "data" / "generated"
GENERATED_CORE = GENERATED / "core"
GENERATED_TRANSACTIONS = GENERATED / "transactions"

TRANSACTIONS_PATH = GENERATED_TRANSACTIONS / "transactions.csv"
ACCOUNTS_PATH = GENERATED_CORE / "accounts.csv"
CUSTOMERS_PATH = GENERATED_CORE / "customers.csv"
BANKS_PATH = GENERATED_CORE / "banks.csv"

TOP_N_TRANSACTIONS = 40
TOP_N_CUSTOMERS = 20

FX = {
    2021: 43.6,
    2022: 41.2,
    2023: 38.8,
    2024: 40.3,
    2025: 42.0,
    2026: 43.5,
}

PRODUCT_CURRENCY = {
    "P001": "UYU",
    "P002": "USD",
    "P003": "UYU",
    "P004": "USD",
    "P005": "UYU",
    "P006": "UYU",
    "P007": "UYU",
    "P008": "USD",
}


def require(df: pd.DataFrame, cols: set[str], name: str) -> None:
    missing = sorted(cols - set(df.columns))
    if missing:
        raise ValueError(f"{name}: missing columns {missing}")


def fmt_money(x: float) -> str:
    return f"{float(x):,.2f}"


def load_data():
    for path in [
        TRANSACTIONS_PATH,
        ACCOUNTS_PATH,
        CUSTOMERS_PATH,
        BANKS_PATH,
    ]:
        if not path.exists():
            raise FileNotFoundError(path)

    tx = pd.read_csv(
        TRANSACTIONS_PATH,
        dtype={
            "transaction_id": str,
            "account_id": str,
            "transaction_type": str,
            "counterparty_bank_id": str,
            "transfer_scope": str,
        },
    )
    accounts = pd.read_csv(
        ACCOUNTS_PATH,
        dtype={
            "account_id": str,
            "customer_id": str,
            "product_id": str,
            "branch_id": str,
        },
    )
    customers = pd.read_csv(
        CUSTOMERS_PATH,
        dtype={"customer_id": str},
    )
    banks = pd.read_csv(
        BANKS_PATH,
        dtype={"bank_id": str},
    )

    require(
        tx,
        {
            "transaction_id",
            "account_id",
            "transaction_datetime",
            "transaction_type",
            "amount",
            "transaction_status",
            "transfer_scope",
            "counterparty_bank_id",
        },
        "transactions",
    )
    require(
        accounts,
        {"account_id", "customer_id", "product_id", "branch_id"},
        "accounts",
    )
    require(
        customers,
        {"customer_id", "customer_type"},
        "customers",
    )
    require(
        banks,
        {"bank_id", "bank_name"},
        "banks",
    )

    return tx, accounts, customers, banks


def customer_capacity_uyu(row: pd.Series) -> tuple[float, str]:
    customer_type = str(row.get("customer_type", "")).upper()

    if customer_type == "BUSINESS":
        annual_revenue = pd.to_numeric(
            pd.Series([row.get("annual_revenue", np.nan)]),
            errors="coerce",
        ).iloc[0]
        if pd.notna(annual_revenue) and annual_revenue > 0:
            return float(annual_revenue), "annual_revenue"

    monthly_income = pd.to_numeric(
        pd.Series([row.get("monthly_income", np.nan)]),
        errors="coerce",
    ).iloc[0]
    if pd.notna(monthly_income) and monthly_income > 0:
        return float(monthly_income) * 12.0, "monthly_income_x12"

    return np.nan, "unavailable"


def severity_label(row: pd.Series) -> str:
    amount = float(row["amount_uyu"])
    ctype = str(row["customer_type"]).upper()
    capacity = row["annual_capacity_uyu"]
    ratio = row["amount_to_capacity"]

    if ctype != "BUSINESS":
        if amount >= 20_000_000:
            return "REVIEW_RETAIL_EXTREME"
        if pd.notna(ratio) and ratio >= 3.0:
            return "REVIEW_RETAIL_CAPACITY"
        return "OK_RETAIL"

    if pd.notna(ratio):
        if ratio >= 2.0:
            return "REVIEW_BUSINESS_CAPACITY"
        if ratio >= 0.75:
            return "LARGE_BUSINESS_TRANSFER"

    if amount >= 500_000_000:
        return "REVIEW_ABSOLUTE_EXTREME"

    return "OK_BUSINESS"


def main():
    print("=" * 92)
    print("BTYT — EXTREME TRANSFER / CUSTOMER PLAUSIBILITY DIAGNOSTIC")
    print("=" * 92)

    tx, accounts, customers, banks = load_data()

    tx["transaction_datetime"] = pd.to_datetime(
        tx["transaction_datetime"],
        errors="raise",
    )
    tx["year"] = tx["transaction_datetime"].dt.year.astype(int)
    tx["amount"] = pd.to_numeric(tx["amount"], errors="raise")

    account_meta = accounts[
        ["account_id", "customer_id", "product_id", "branch_id"]
    ].copy()
    account_meta["currency"] = account_meta["product_id"].map(PRODUCT_CURRENCY)

    if account_meta["currency"].isna().any():
        missing_products = sorted(
            account_meta.loc[
                account_meta["currency"].isna(),
                "product_id",
            ].dropna().unique()
        )
        raise ValueError(
            f"Missing currency mapping for products: {missing_products}"
        )

    transfer = tx[
        tx["transaction_type"].isin(["TRANSFER_IN", "TRANSFER_OUT"])
        & tx["transaction_status"].eq("COMPLETED")
    ].copy()

    transfer = transfer.merge(
        account_meta,
        on="account_id",
        how="left",
        validate="many_to_one",
    )

    if transfer["customer_id"].isna().any():
        raise ValueError("Some transfer rows could not be linked to accounts.")

    transfer["fx"] = np.where(
        transfer["currency"].eq("USD"),
        transfer["year"].map(FX),
        1.0,
    )

    if pd.isna(transfer["fx"]).any():
        bad_years = sorted(
            transfer.loc[transfer["fx"].isna(), "year"].unique()
        )
        raise ValueError(f"Missing FX anchors for years: {bad_years}")

    transfer["amount_uyu"] = transfer["amount"] * transfer["fx"]

    bank_names = banks.set_index("bank_id")["bank_name"].astype(str).to_dict()
    transfer["counterparty_bank_name"] = (
        transfer["counterparty_bank_id"].map(bank_names)
    )

    transfer = transfer.merge(
        customers,
        on="customer_id",
        how="left",
        validate="many_to_one",
    )

    if transfer["customer_type"].isna().any():
        raise ValueError("Some transfer rows could not be linked to customers.")

    capacities = transfer.apply(customer_capacity_uyu, axis=1)
    transfer["annual_capacity_uyu"] = [x[0] for x in capacities]
    transfer["capacity_source"] = [x[1] for x in capacities]

    transfer["amount_to_capacity"] = np.where(
        transfer["annual_capacity_uyu"] > 0,
        transfer["amount_uyu"] / transfer["annual_capacity_uyu"],
        np.nan,
    )

    transfer["diagnostic_flag"] = transfer.apply(severity_label, axis=1)

    print(f"Completed transfers: {len(transfer):,}")
    print(
        "Customers represented in completed transfers: "
        f"{transfer['customer_id'].nunique():,}"
    )
    print()

    print("=" * 92)
    print(f"1. TOP {TOP_N_TRANSACTIONS} COMPLETED TRANSFERS")
    print("=" * 92)

    top = transfer.nlargest(TOP_N_TRANSACTIONS, "amount_uyu").copy()

    top_cols = [
        "transaction_id",
        "transaction_datetime",
        "transaction_type",
        "account_id",
        "customer_id",
        "customer_type",
        "product_id",
        "currency",
        "amount",
        "amount_uyu",
        "annual_capacity_uyu",
        "amount_to_capacity",
        "transfer_scope",
        "counterparty_bank_name",
        "diagnostic_flag",
    ]

    display_top = top[top_cols].copy()
    display_top["amount"] = display_top["amount"].map(fmt_money)
    display_top["amount_uyu"] = display_top["amount_uyu"].map(fmt_money)
    display_top["annual_capacity_uyu"] = display_top[
        "annual_capacity_uyu"
    ].map(lambda x: "NA" if pd.isna(x) else fmt_money(x))
    display_top["amount_to_capacity"] = display_top[
        "amount_to_capacity"
    ].map(lambda x: "NA" if pd.isna(x) else f"{x:.2f}x")

    print(display_top.to_string(index=False))
    print()

    print("=" * 92)
    print("2. SPECIAL ACCOUNTS FROM PREVIOUS ECONOMIC AUDIT")
    print("=" * 92)

    special_accounts = ["A0018004", "A0015861"]
    special = transfer[transfer["account_id"].isin(special_accounts)].copy()

    if special.empty:
        print("No completed transfers found for the requested accounts.")
    else:
        for account_id, g in special.groupby("account_id", sort=True):
            row = g.iloc[0]
            print()
            print(f"Account: {account_id}")
            print(f"Customer: {row['customer_id']}")
            print(f"Customer type: {row['customer_type']}")
            print(f"Product: {row['product_id']} ({row['currency']})")
            print(f"Branch: {row['branch_id']}")

            if "monthly_income" in g.columns:
                value = pd.to_numeric(
                    pd.Series([row.get("monthly_income")]),
                    errors="coerce",
                ).iloc[0]
                if pd.notna(value):
                    print(f"Monthly income: {fmt_money(value)} UYU")

            if "annual_revenue" in g.columns:
                value = pd.to_numeric(
                    pd.Series([row.get("annual_revenue")]),
                    errors="coerce",
                ).iloc[0]
                if pd.notna(value):
                    print(f"Annual revenue: {fmt_money(value)} UYU")

            if "business_sector" in g.columns:
                print(f"Business sector: {row.get('business_sector')}")

            capacity = row["annual_capacity_uyu"]
            print(
                "Annual capacity proxy: "
                + ("NA" if pd.isna(capacity) else f"{fmt_money(capacity)} UYU")
            )
            print(f"Completed transfers: {len(g):,}")
            print(
                "Total completed transfer amount: "
                f"{fmt_money(g['amount_uyu'].sum())} UYU"
            )
            print(
                "Largest completed transfer: "
                f"{fmt_money(g['amount_uyu'].max())} UYU"
            )

            if pd.notna(capacity) and capacity > 0:
                print(
                    "Largest transfer / annual capacity: "
                    f"{g['amount_uyu'].max() / capacity:.2f}x"
                )

            print("Largest 10 transfers:")
            s = g.nlargest(10, "amount_uyu")[
                [
                    "transaction_datetime",
                    "transaction_type",
                    "amount_uyu",
                    "transfer_scope",
                    "counterparty_bank_name",
                    "diagnostic_flag",
                ]
            ].copy()
            s["amount_uyu"] = s["amount_uyu"].map(fmt_money)
            print(s.to_string(index=False))

    print()
    print("=" * 92)
    print(f"3. TOP {TOP_N_CUSTOMERS} CUSTOMERS BY SINGLE LARGEST TRANSFER")
    print("=" * 92)

    customer_summary = (
        transfer.groupby("customer_id", as_index=False)
        .agg(
            customer_type=("customer_type", "first"),
            transfer_count=("transaction_id", "size"),
            total_transfer_uyu=("amount_uyu", "sum"),
            max_transfer_uyu=("amount_uyu", "max"),
            annual_capacity_uyu=("annual_capacity_uyu", "first"),
        )
    )

    customer_summary["max_to_capacity"] = np.where(
        customer_summary["annual_capacity_uyu"] > 0,
        customer_summary["max_transfer_uyu"]
        / customer_summary["annual_capacity_uyu"],
        np.nan,
    )

    customer_summary = customer_summary.nlargest(
        TOP_N_CUSTOMERS,
        "max_transfer_uyu",
    )

    display_customers = customer_summary.copy()
    for col in [
        "total_transfer_uyu",
        "max_transfer_uyu",
        "annual_capacity_uyu",
    ]:
        display_customers[col] = display_customers[col].map(
            lambda x: "NA" if pd.isna(x) else fmt_money(x)
        )
    display_customers["max_to_capacity"] = display_customers[
        "max_to_capacity"
    ].map(lambda x: "NA" if pd.isna(x) else f"{x:.2f}x")

    print(display_customers.to_string(index=False))

    print()
    print("=" * 92)
    print("4. FLAG COUNTS")
    print("=" * 92)

    flags = (
        transfer["diagnostic_flag"]
        .value_counts()
        .rename_axis("flag")
        .reset_index(name="transactions")
    )
    flags["share"] = flags["transactions"] / len(transfer) * 100.0
    flags["share"] = flags["share"].map(lambda x: f"{x:.4f}%")
    print(flags.to_string(index=False))

    print()
    print("=" * 92)
    print("5. HIGH-SEVERITY CASES")
    print("=" * 92)

    review_flags = {
        "REVIEW_RETAIL_EXTREME",
        "REVIEW_RETAIL_CAPACITY",
        "REVIEW_BUSINESS_CAPACITY",
        "REVIEW_ABSOLUTE_EXTREME",
    }

    review = transfer[transfer["diagnostic_flag"].isin(review_flags)].copy()

    print(f"Transactions requiring review: {len(review):,}")
    print(
        "Customers requiring review: "
        f"{review['customer_id'].nunique():,}"
    )

    if not review.empty:
        review_summary = (
            review.groupby(
                ["customer_id", "customer_type", "diagnostic_flag"],
                as_index=False,
            )
            .agg(
                transactions=("transaction_id", "size"),
                max_transfer_uyu=("amount_uyu", "max"),
                annual_capacity_uyu=("annual_capacity_uyu", "first"),
            )
        )
        review_summary["max_to_capacity"] = np.where(
            review_summary["annual_capacity_uyu"] > 0,
            review_summary["max_transfer_uyu"]
            / review_summary["annual_capacity_uyu"],
            np.nan,
        )
        review_summary = review_summary.sort_values(
            "max_transfer_uyu",
            ascending=False,
        )

        for col in ["max_transfer_uyu", "annual_capacity_uyu"]:
            review_summary[col] = review_summary[col].map(
                lambda x: "NA" if pd.isna(x) else fmt_money(x)
            )
        review_summary["max_to_capacity"] = review_summary[
            "max_to_capacity"
        ].map(lambda x: "NA" if pd.isna(x) else f"{x:.2f}x")

        print(review_summary.head(50).to_string(index=False))

    print()
    print("=" * 92)
    print("6. DIAGNOSTIC VERDICT")
    print("=" * 92)

    retail_extreme = transfer[
        transfer["diagnostic_flag"].isin(
            {"REVIEW_RETAIL_EXTREME", "REVIEW_RETAIL_CAPACITY"}
        )
    ]
    business_extreme = transfer[
        transfer["diagnostic_flag"].isin(
            {"REVIEW_BUSINESS_CAPACITY", "REVIEW_ABSOLUTE_EXTREME"}
        )
    ]

    if retail_extreme.empty and business_extreme.empty:
        print(
            "PASS: no capacity-inconsistent extreme transfers were detected "
            "under the diagnostic rules."
        )
    else:
        print(
            "REVIEW: one or more extreme transfers are inconsistent with the "
            "customer capacity heuristics."
        )
        print(
            f"  Retail flagged transactions: {len(retail_extreme):,}"
        )
        print(
            f"  Business flagged transactions: {len(business_extreme):,}"
        )
        print(
            "Do not alter the transaction DGP automatically. Inspect the listed "
            "customers first and decide whether the case is economically plausible."
        )

    print()
    print("Diagnostic complete. Canonical files were not modified.")


if __name__ == "__main__":
    main()
