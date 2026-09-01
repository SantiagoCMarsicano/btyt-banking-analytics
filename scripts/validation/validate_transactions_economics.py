#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
BTYT — Transaction Engine Economic Validation

It does NOT modify any generated data.

Main objectives:
1. Evaluate transaction activity over time.
2. Evaluate digital adoption and cash transition.
3. Compare behavior across account products.
4. Evaluate transaction amount distributions.
5. Evaluate account balance distributions.
6. Evaluate transaction failures and insufficient-funds behavior.
7. Evaluate individual vs business behavior.
8. Evaluate customer heterogeneity and concentration.
9. Evaluate fixed-term deposit behavior.
10. Detect potentially suspicious economic patterns.

This validation complements the structural/integrity validation already
performed inside generate_transactions.py.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# =============================================================================
# Paths
# =============================================================================

ROOT = Path(__file__).resolve().parents[1]

PROCESSED = ROOT / "data" / "processed"

TRANSACTIONS_PATH = PROCESSED / "transactions.csv"
BALANCES_PATH = PROCESSED / "account_balances.csv"
ACCOUNTS_PATH = PROCESSED / "accounts.csv"
CUSTOMERS_PATH = PROCESSED / "customers.csv"


# =============================================================================
# Configuration
# =============================================================================

FIXED_TERM_PRODUCTS = {"P007", "P008"}

CASH_TYPES = {
    "CASH_DEPOSIT",
    "CASH_WITHDRAWAL",
}

DIGITAL_CHANNELS = {
    "MOBILE",
    "WEB",
}

PHYSICAL_CHANNELS = {
    "BRANCH",
    "ATM",
}

CREDIT_TYPES = {
    "TRANSFER_IN",
    "CASH_DEPOSIT",
    "LOAN_DISBURSEMENT",
    "INTEREST_CREDIT",
}

DEBIT_TYPES = {
    "TRANSFER_OUT",
    "CASH_WITHDRAWAL",
    "DEBIT_PURCHASE",
    "SERVICE_PAYMENT",
    "CREDIT_CARD_PAYMENT",
    "LOAN_PAYMENT",
}

EXPECTED_PRODUCTS = {
    "P001",
    "P002",
    "P003",
    "P004",
    "P005",
    "P006",
    "P007",
    "P008",
}

AMOUNT_QUANTILES = [
    0.01,
    0.10,
    0.25,
    0.50,
    0.75,
    0.90,
    0.95,
    0.99,
]


# =============================================================================
# Formatting helpers
# =============================================================================

def print_header(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def print_subheader(title: str) -> None:
    print()
    print("-" * 80)
    print(title)
    print("-" * 80)


def safe_pct(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return np.nan

    return 100.0 * numerator / denominator


def format_integer(value: int | float) -> str:
    return f"{int(value):,}"


def print_series(series: pd.Series) -> None:
    if len(series) == 0:
        print("No data.")
        return

    print(series.to_string())


def print_dataframe(df: pd.DataFrame) -> None:
    if df.empty:
        print("No data.")
        return

    print(df.to_string())


# =============================================================================
# Data loading
# =============================================================================

def validate_input_files() -> None:
    required_files = [
        TRANSACTIONS_PATH,
        BALANCES_PATH,
        ACCOUNTS_PATH,
        CUSTOMERS_PATH,
    ]

    missing = [
        path
        for path in required_files
        if not path.exists()
    ]

    if missing:
        missing_text = "\n".join(str(path) for path in missing)

        raise FileNotFoundError(
            "Required BTYT input files are missing:\n"
            f"{missing_text}"
        )


def load_data() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    validate_input_files()

    print("Loading transactions...")
    tx = pd.read_csv(
        TRANSACTIONS_PATH,
        parse_dates=["transaction_datetime"],
        low_memory=False,
    )

    print("Loading account balances...")
    balances = pd.read_csv(
        BALANCES_PATH,
        low_memory=False,
    )

    print("Loading accounts...")
    accounts = pd.read_csv(
        ACCOUNTS_PATH,
        low_memory=False,
    )

    print("Loading customers...")
    customers = pd.read_csv(
        CUSTOMERS_PATH,
        low_memory=False,
    )

    return tx, balances, accounts, customers


# =============================================================================
# Data preparation
# =============================================================================

def prepare_data(
    tx: pd.DataFrame,
    balances: pd.DataFrame,
    accounts: pd.DataFrame,
    customers: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    tx = tx.copy()
    balances = balances.copy()
    accounts = accounts.copy()
    customers = customers.copy()

    # -------------------------------------------------------------------------
    # Transaction time variables
    # -------------------------------------------------------------------------

    tx["year"] = tx["transaction_datetime"].dt.year
    tx["month"] = tx["transaction_datetime"].dt.month

    tx["year_month"] = (
        tx["transaction_datetime"]
        .dt.to_period("M")
        .astype(str)
    )

    tx["is_failed"] = (
        tx["transaction_status"]
        .eq("FAILED")
    )

    tx["is_completed"] = (
        tx["transaction_status"]
        .eq("COMPLETED")
    )

    tx["is_cash"] = (
        tx["transaction_type"]
        .isin(CASH_TYPES)
    )

    tx["is_digital"] = (
        tx["channel"]
        .isin(DIGITAL_CHANNELS)
    )

    tx["is_physical"] = (
        tx["channel"]
        .isin(PHYSICAL_CHANNELS)
    )

    tx["is_insufficient_funds"] = (
        tx["failure_reason"]
        .eq("INSUFFICIENT_FUNDS")
    )

    # -------------------------------------------------------------------------
    # Normalize account identifiers
    # -------------------------------------------------------------------------

    tx["account_id"] = tx["account_id"].astype(str)
    accounts["account_id"] = accounts["account_id"].astype(str)
    balances["account_id"] = balances["account_id"].astype(str)

    accounts["customer_id"] = accounts["customer_id"].astype(str)
    customers["customer_id"] = customers["customer_id"].astype(str)

    # -------------------------------------------------------------------------
    # Merge transaction -> account
    # -------------------------------------------------------------------------

    account_cols = [
        "account_id",
        "customer_id",
        "product_id",
    ]

    optional_account_cols = [
        "branch_id",
        "opening_year",
        "account_status",
        "closing_year",
        "opening_channel",
    ]

    for column in optional_account_cols:
        if column in accounts.columns:
            account_cols.append(column)

    tx_enriched = tx.merge(
        accounts[account_cols],
        on="account_id",
        how="left",
        validate="many_to_one",
    )

    # -------------------------------------------------------------------------
    # Merge transaction -> customer
    # -------------------------------------------------------------------------

    customer_cols = [
        "customer_id",
        "customer_type",
    ]

    optional_customer_cols = [
        "monthly_income",
        "annual_revenue",
        "employment_status",
        "business_sector",
        "company_size",
        "residence_department",
        "primary_branch_id",
    ]

    for column in optional_customer_cols:
        if column in customers.columns:
            customer_cols.append(column)

    tx_enriched = tx_enriched.merge(
        customers[customer_cols],
        on="customer_id",
        how="left",
        validate="many_to_one",
    )

    # -------------------------------------------------------------------------
    # Balance preparation
    # -------------------------------------------------------------------------

    balances["year_month"] = balances["year_month"].astype(str)

    balances_enriched = balances.merge(
        accounts[account_cols],
        on="account_id",
        how="left",
        validate="many_to_one",
    )

    balances_enriched = balances_enriched.merge(
        customers[customer_cols],
        on="customer_id",
        how="left",
        validate="many_to_one",
    )

    return tx_enriched, balances_enriched, accounts


# =============================================================================
# Basic dataset summary
# =============================================================================

def validate_dataset_summary(
    tx: pd.DataFrame,
    balances: pd.DataFrame,
) -> None:
    print_header(
        "BTYT TRANSACTION ENGINE — ECONOMIC VALIDATION"
    )

    print(
        f"Transactions:        "
        f"{format_integer(len(tx))}"
    )

    print(
        f"Account-months:       "
        f"{format_integer(len(balances))}"
    )

    print(
        f"Accounts represented: "
        f"{format_integer(tx['account_id'].nunique())}"
    )

    print(
        f"Customers represented:"
        f" {format_integer(tx['customer_id'].nunique())}"
    )

    print(
        f"Observation window:   "
        f"{tx['transaction_datetime'].min()} "
        f"to "
        f"{tx['transaction_datetime'].max()}"
    )

    avg_tx_account_month = (
        len(tx) / len(balances)
        if len(balances)
        else np.nan
    )

    print(
        f"Average transactions per account-month: "
        f"{avg_tx_account_month:,.2f}"
    )


# =============================================================================
# Annual activity
# =============================================================================

def validate_annual_activity(
    tx: pd.DataFrame,
) -> pd.DataFrame:
    print_subheader(
        "1. TRANSACTION ACTIVITY BY YEAR"
    )

    yearly = (
        tx.groupby("year")
        .agg(
            transactions=(
                "transaction_id",
                "count",
            ),
            accounts=(
                "account_id",
                "nunique",
            ),
            customers=(
                "customer_id",
                "nunique",
            ),
        )
    )

    yearly["tx_per_account"] = (
        yearly["transactions"]
        / yearly["accounts"]
    )

    yearly["tx_per_customer"] = (
        yearly["transactions"]
        / yearly["customers"]
    )

    yearly = yearly.round(2)

    print_dataframe(yearly)

    return yearly


# =============================================================================
# Channel evolution
# =============================================================================

def validate_channels(
    tx: pd.DataFrame,
) -> pd.DataFrame:
    print_subheader(
        "2. CHANNEL SHARE BY YEAR (%)"
    )

    channel_counts = (
        tx.groupby(
            ["year", "channel"]
        )
        .size()
        .unstack(fill_value=0)
    )

    channel_share = (
        channel_counts
        .div(
            channel_counts.sum(axis=1),
            axis=0,
        )
        .mul(100)
        .round(2)
    )

    print_dataframe(channel_share)

    print()
    print("Digital share (MOBILE + WEB):")

    digital = (
        tx.groupby("year")["is_digital"]
        .mean()
        .mul(100)
        .round(2)
    )

    print_series(digital)

    print()
    print("Physical banking share (BRANCH + ATM):")

    physical = (
        tx.groupby("year")["is_physical"]
        .mean()
        .mul(100)
        .round(2)
    )

    print_series(physical)

    return channel_share


# =============================================================================
# Cash transition
# =============================================================================

def validate_cash_transition(
    tx: pd.DataFrame,
) -> pd.Series:
    print_subheader(
        "3. CASH TRANSITION"
    )

    cash_share = (
        tx.groupby("year")["is_cash"]
        .mean()
        .mul(100)
        .round(2)
    )

    print("Cash transactions / all transactions (%)")
    print_series(cash_share)

    print()
    print("Cash composition:")

    cash_detail = (
        tx[
            tx["transaction_type"]
            .isin(CASH_TYPES)
        ]
        .groupby(
            ["year", "transaction_type"]
        )
        .size()
        .unstack(fill_value=0)
    )

    if not cash_detail.empty:
        cash_detail = (
            cash_detail
            .div(
                tx.groupby("year").size(),
                axis=0,
            )
            .mul(100)
            .round(2)
        )

    print_dataframe(cash_detail)

    return cash_share


# =============================================================================
# Transaction type evolution
# =============================================================================

def validate_transaction_types(
    tx: pd.DataFrame,
) -> pd.DataFrame:
    print_subheader(
        "4. TRANSACTION TYPE SHARE BY YEAR (%)"
    )

    counts = (
        tx.groupby(
            ["year", "transaction_type"]
        )
        .size()
        .unstack(fill_value=0)
    )

    share = (
        counts
        .div(
            counts.sum(axis=1),
            axis=0,
        )
        .mul(100)
        .round(2)
    )

    print_dataframe(share)

    return share


# =============================================================================
# Product behavior
# =============================================================================

def validate_product_behavior(
    tx: pd.DataFrame,
) -> pd.DataFrame:
    print_subheader(
        "5. PRODUCT BEHAVIOR"
    )

    product = (
        tx.groupby("product_id")
        .agg(
            transactions=(
                "transaction_id",
                "count",
            ),
            accounts=(
                "account_id",
                "nunique",
            ),
            customers=(
                "customer_id",
                "nunique",
            ),
            median_amount=(
                "amount",
                "median",
            ),
            mean_amount=(
                "amount",
                "mean",
            ),
            failure_rate=(
                "is_failed",
                "mean",
            ),
            cash_share=(
                "is_cash",
                "mean",
            ),
            digital_share=(
                "is_digital",
                "mean",
            ),
        )
    )

    product["tx_per_account"] = (
        product["transactions"]
        / product["accounts"]
    )

    product[
        "failure_rate"
    ] *= 100

    product[
        "cash_share"
    ] *= 100

    product[
        "digital_share"
    ] *= 100

    product = product[
        [
            "transactions",
            "accounts",
            "customers",
            "tx_per_account",
            "median_amount",
            "mean_amount",
            "failure_rate",
            "cash_share",
            "digital_share",
        ]
    ].round(2)

    print_dataframe(product)

    missing_products = (
        EXPECTED_PRODUCTS
        - set(product.index)
    )

    if missing_products:
        print()
        print(
            "Products without transaction activity:",
            sorted(missing_products),
        )

    return product


# =============================================================================
# Customer-type behavior
# =============================================================================

def validate_customer_types(
    tx: pd.DataFrame,
) -> pd.DataFrame:
    print_subheader(
        "6. INDIVIDUAL VS BUSINESS BEHAVIOR"
    )

    result = (
        tx.groupby("customer_type")
        .agg(
            transactions=(
                "transaction_id",
                "count",
            ),
            customers=(
                "customer_id",
                "nunique",
            ),
            accounts=(
                "account_id",
                "nunique",
            ),
            median_amount=(
                "amount",
                "median",
            ),
            mean_amount=(
                "amount",
                "mean",
            ),
            failure_rate=(
                "is_failed",
                "mean",
            ),
            cash_share=(
                "is_cash",
                "mean",
            ),
            digital_share=(
                "is_digital",
                "mean",
            ),
        )
    )

    result["tx_per_customer"] = (
        result["transactions"]
        / result["customers"]
    )

    result[
        "failure_rate"
    ] *= 100

    result[
        "cash_share"
    ] *= 100

    result[
        "digital_share"
    ] *= 100

    result = result[
        [
            "transactions",
            "customers",
            "accounts",
            "tx_per_customer",
            "median_amount",
            "mean_amount",
            "failure_rate",
            "cash_share",
            "digital_share",
        ]
    ].round(2)

    print_dataframe(result)

    return result


# =============================================================================
# Amount distributions
# =============================================================================

def validate_amounts(
    tx: pd.DataFrame,
) -> pd.DataFrame:
    print_subheader(
        "7. TRANSACTION AMOUNT DISTRIBUTIONS"
    )

    completed = tx[
        tx["transaction_status"]
        .eq("COMPLETED")
    ].copy()

    quantiles = (
        completed
        .groupby("transaction_type")[
            "amount"
        ]
        .quantile(AMOUNT_QUANTILES)
        .unstack()
    )

    quantiles.columns = [
        f"p{int(q * 100):02d}"
        for q in quantiles.columns
    ]

    quantiles = quantiles.round(2)

    print(
        "Completed transaction amount quantiles:"
    )
    print_dataframe(quantiles)

    print()
    print("Maximum amounts:")

    maximums = (
        completed
        .groupby("transaction_type")[
            "amount"
        ]
        .max()
        .sort_values(
            ascending=False
        )
        .round(2)
    )

    print_series(maximums)

    return quantiles


# =============================================================================
# Failure behavior
# =============================================================================

def validate_failures(
    tx: pd.DataFrame,
) -> tuple[pd.Series, pd.DataFrame]:
    print_subheader(
        "8. FAILURE BEHAVIOR"
    )

    yearly_failure = (
        tx.groupby("year")[
            "is_failed"
        ]
        .mean()
        .mul(100)
        .round(2)
    )

    print("Failure rate by year (%)")
    print_series(yearly_failure)

    print()
    print(
        "Insufficient funds / all transactions (%)"
    )

    insufficient_year = (
        tx.groupby("year")[
            "is_insufficient_funds"
        ]
        .mean()
        .mul(100)
        .round(2)
    )

    print_series(insufficient_year)

    print()
    print("Failure reason distribution:")

    failed = tx[
        tx["is_failed"]
    ]

    failure_reasons = (
        failed["failure_reason"]
        .value_counts()
        .to_frame("count")
    )

    failure_reasons["share_pct"] = (
        100
        * failure_reasons["count"]
        / len(failed)
    ).round(2)

    print_dataframe(failure_reasons)

    print()
    print("Failure rate by product (%)")

    failure_product = (
        tx.groupby("product_id")
        .agg(
            total_transactions=(
                "transaction_id",
                "count",
            ),
            failed=(
                "is_failed",
                "sum",
            ),
            insufficient_funds=(
                "is_insufficient_funds",
                "sum",
            ),
        )
    )

    failure_product[
        "failure_rate"
    ] = (
        100
        * failure_product["failed"]
        / failure_product[
            "total_transactions"
        ]
    )

    failure_product[
        "insufficient_funds_rate"
    ] = (
        100
        * failure_product[
            "insufficient_funds"
        ]
        / failure_product[
            "total_transactions"
        ]
    )

    failure_product = (
        failure_product
        .round(2)
    )

    print_dataframe(failure_product)

    print()
    print("Failure rate by transaction type (%)")

    failure_type = (
        tx.groupby("transaction_type")
        .agg(
            total_transactions=(
                "transaction_id",
                "count",
            ),
            failed=(
                "is_failed",
                "sum",
            ),
            insufficient_funds=(
                "is_insufficient_funds",
                "sum",
            ),
        )
    )

    failure_type["failure_rate"] = (
        100
        * failure_type["failed"]
        / failure_type[
            "total_transactions"
        ]
    )

    failure_type[
        "insufficient_funds_rate"
    ] = (
        100
        * failure_type[
            "insufficient_funds"
        ]
        / failure_type[
            "total_transactions"
        ]
    )

    failure_type = (
        failure_type
        .sort_values(
            "failure_rate",
            ascending=False,
        )
        .round(2)
    )

    print_dataframe(failure_type)

    return yearly_failure, failure_product


# =============================================================================
# Balance distributions
# =============================================================================

def validate_balances(
    balances: pd.DataFrame,
) -> pd.DataFrame:
    print_subheader(
        "9. ACCOUNT BALANCE DISTRIBUTIONS"
    )

    quantile_levels = [
        0.00,
        0.01,
        0.10,
        0.25,
        0.50,
        0.75,
        0.90,
        0.95,
        0.99,
        1.00,
    ]

    balance_quantiles = (
        balances[
            "closing_balance"
        ]
        .quantile(
            quantile_levels
        )
        .round(2)
    )

    balance_quantiles.index = [
        f"p{int(q * 100):02d}"
        for q in quantile_levels
    ]

    print("Closing balance quantiles:")
    print_series(balance_quantiles)

    zero_share = (
        balances[
            "closing_balance"
        ]
        .eq(0)
        .mean()
        * 100
    )

    negative_count = (
        balances[
            "closing_balance"
        ]
        .lt(0)
        .sum()
    )

    print()
    print(
        f"Zero closing balances: "
        f"{zero_share:.2f}%"
    )

    print(
        f"Negative closing balances: "
        f"{negative_count:,}"
    )

    print()
    print(
        "Median and mean closing balance "
        "by product:"
    )

    product_balance = (
        balances.groupby("product_id")
        .agg(
            account_months=(
                "account_id",
                "count",
            ),
            accounts=(
                "account_id",
                "nunique",
            ),
            median_opening_balance=(
                "opening_balance",
                "median",
            ),
            mean_opening_balance=(
                "opening_balance",
                "mean",
            ),
            median_closing_balance=(
                "closing_balance",
                "median",
            ),
            mean_closing_balance=(
                "closing_balance",
                "mean",
            ),
            median_inflows=(
                "total_inflows",
                "median",
            ),
            median_outflows=(
                "total_outflows",
                "median",
            ),
        )
        .round(2)
    )

    print_dataframe(product_balance)

    return product_balance


# =============================================================================
# Failure vs monthly liquidity
# =============================================================================

def validate_failure_liquidity(
    tx: pd.DataFrame,
    balances: pd.DataFrame,
) -> pd.DataFrame:
    print_subheader(
        "10. FAILURE VS MONTHLY LIQUIDITY"
    )

    failed = tx[
        tx["is_failed"]
    ].copy()

    if failed.empty:
        print("No failed transactions.")
        return pd.DataFrame()

    monthly_balance = balances[
        [
            "account_id",
            "year_month",
            "opening_balance",
            "closing_balance",
            "total_inflows",
            "total_outflows",
        ]
    ].copy()

    failed = failed.merge(
        monthly_balance,
        on=[
            "account_id",
            "year_month",
        ],
        how="left",
        validate="many_to_one",
    )

    result = (
        failed.groupby(
            "failure_reason",
            dropna=False,
        )
        .agg(
            failed_transactions=(
                "transaction_id",
                "count",
            ),
            median_transaction_amount=(
                "amount",
                "median",
            ),
            median_opening_balance=(
                "opening_balance",
                "median",
            ),
            median_closing_balance=(
                "closing_balance",
                "median",
            ),
            median_monthly_inflows=(
                "total_inflows",
                "median",
            ),
            median_monthly_outflows=(
                "total_outflows",
                "median",
            ),
        )
        .sort_values(
            "failed_transactions",
            ascending=False,
        )
        .round(2)
    )

    print_dataframe(result)

    print()
    print(
        "NOTE: opening_balance is the beginning-of-month balance, "
        "not the exact balance immediately before the failed event."
    )

    return result


# =============================================================================
# Account activity distribution
# =============================================================================

def validate_account_activity(
    tx: pd.DataFrame,
) -> pd.Series:
    print_subheader(
        "11. ACCOUNT ACTIVITY HETEROGENEITY"
    )

    account_month_activity = (
        tx.groupby(
            [
                "account_id",
                "year_month",
            ]
        )
        .size()
    )

    quantiles = (
        account_month_activity
        .quantile(
            [
                0.01,
                0.10,
                0.25,
                0.50,
                0.75,
                0.90,
                0.95,
                0.99,
                1.00,
            ]
        )
        .round(2)
    )

    quantiles.index = [
        "p01",
        "p10",
        "p25",
        "p50",
        "p75",
        "p90",
        "p95",
        "p99",
        "max",
    ]

    print(
        "Transactions per active account-month:"
    )

    print_series(quantiles)

    return quantiles


# =============================================================================
# Customer concentration
# =============================================================================

def validate_customer_concentration(
    tx: pd.DataFrame,
) -> dict[str, float]:
    print_subheader(
        "12. CUSTOMER ACTIVITY CONCENTRATION"
    )

    customer_tx = (
        tx.groupby("customer_id")
        .size()
        .sort_values(
            ascending=False
        )
    )

    total_transactions = (
        customer_tx.sum()
    )

    n_customers = (
        len(customer_tx)
    )

    def top_share(
        fraction: float,
    ) -> float:
        n_top = max(
            1,
            int(
                np.ceil(
                    n_customers
                    * fraction
                )
            ),
        )

        return (
            100
            * customer_tx.iloc[
                :n_top
            ].sum()
            / total_transactions
        )

    results = {
        "top_1_pct": top_share(0.01),
        "top_5_pct": top_share(0.05),
        "top_10_pct": top_share(0.10),
        "top_20_pct": top_share(0.20),
    }

    for name, value in results.items():
        label = (
            name
            .replace("_", " ")
            .upper()
        )

        print(
            f"{label:<15}: "
            f"{value:6.2f}%"
        )

    print()
    print(
        "Customer transaction count quantiles:"
    )

    customer_quantiles = (
        customer_tx
        .quantile(
            [
                0.01,
                0.10,
                0.25,
                0.50,
                0.75,
                0.90,
                0.95,
                0.99,
                1.00,
            ]
        )
        .round(2)
    )

    print_series(customer_quantiles)

    return results


# =============================================================================
# Fixed-term deposit validation
# =============================================================================

def validate_fixed_term_behavior(
    tx: pd.DataFrame,
) -> pd.DataFrame:
    print_subheader(
        "13. FIXED-TERM DEPOSIT BEHAVIOR"
    )

    fixed = tx[
        tx["product_id"]
        .isin(FIXED_TERM_PRODUCTS)
    ]

    if fixed.empty:
        print(
            "No fixed-term transaction activity found."
        )

        return pd.DataFrame()

    type_distribution = (
        fixed.groupby(
            [
                "product_id",
                "transaction_type",
            ]
        )
        .size()
        .unstack(fill_value=0)
    )

    type_share = (
        type_distribution
        .div(
            type_distribution
            .sum(axis=1),
            axis=0,
        )
        .mul(100)
        .round(2)
    )

    print(
        "Fixed-term transaction type share (%)"
    )

    print_dataframe(type_share)

    print()
    print(
        "Average transactions per "
        "fixed-term account:"
    )

    activity = (
        fixed.groupby("product_id")
        .agg(
            transactions=(
                "transaction_id",
                "count",
            ),
            accounts=(
                "account_id",
                "nunique",
            ),
        )
    )

    activity[
        "tx_per_account"
    ] = (
        activity["transactions"]
        / activity["accounts"]
    )

    activity = activity.round(2)

    print_dataframe(activity)

    return type_share


# =============================================================================
# Monthly trend smoothness
# =============================================================================

def validate_monthly_volatility(
    tx: pd.DataFrame,
) -> pd.DataFrame:
    print_subheader(
        "14. MONTHLY AGGREGATE ACTIVITY"
    )

    monthly = (
        tx.groupby("year_month")
        .agg(
            transactions=(
                "transaction_id",
                "count",
            ),
            accounts=(
                "account_id",
                "nunique",
            ),
            failed=(
                "is_failed",
                "mean",
            ),
            cash_share=(
                "is_cash",
                "mean",
            ),
            digital_share=(
                "is_digital",
                "mean",
            ),
        )
    )

    monthly["failed"] *= 100
    monthly["cash_share"] *= 100
    monthly["digital_share"] *= 100

    monthly[
        "tx_growth_pct"
    ] = (
        monthly["transactions"]
        .pct_change()
        .mul(100)
    )

    monthly = monthly.round(2)

    print(
        "First 12 months:"
    )

    print_dataframe(
        monthly.head(12)
    )

    print()
    print(
        "Last 12 months:"
    )

    print_dataframe(
        monthly.tail(12)
    )

    print()
    print(
        "Monthly transaction growth distribution:"
    )

    growth_stats = (
        monthly["tx_growth_pct"]
        .describe(
            percentiles=[
                0.05,
                0.10,
                0.25,
                0.50,
                0.75,
                0.90,
                0.95,
            ]
        )
        .round(2)
    )

    print_series(growth_stats)

    return monthly


# =============================================================================
# Automated diagnostic warnings
# =============================================================================

def generate_diagnostics(
    tx: pd.DataFrame,
    balances: pd.DataFrame,
) -> list[str]:
    print_subheader(
        "15. AUTOMATED DIAGNOSTIC FLAGS"
    )

    messages: list[str] = []

    years = sorted(
        tx["year"]
        .dropna()
        .unique()
    )

    # -------------------------------------------------------------------------
    # Digital trend
    # -------------------------------------------------------------------------

    digital_year = (
        tx.groupby("year")[
            "is_digital"
        ]
        .mean()
    )

    if (
        len(years) >= 2
        and digital_year.iloc[-1]
        > digital_year.iloc[0]
    ):
        messages.append(
            "[PASS] Digital channel share is higher "
            "at the end of the observation window."
        )
    else:
        messages.append(
            "[WARN] Digital channel share does not "
            "increase over the observation window."
        )

    # -------------------------------------------------------------------------
    # Cash trend
    # -------------------------------------------------------------------------

    cash_year = (
        tx.groupby("year")[
            "is_cash"
        ]
        .mean()
    )

    if (
        len(years) >= 2
        and cash_year.iloc[-1]
        < cash_year.iloc[0]
    ):
        messages.append(
            "[PASS] Cash usage is lower at the end "
            "of the observation window."
        )
    else:
        messages.append(
            "[WARN] Cash usage does not decline "
            "over the observation window."
        )

    # -------------------------------------------------------------------------
    # Failure rate
    # -------------------------------------------------------------------------

    failure_rate = (
        tx["is_failed"]
        .mean()
    )

    if failure_rate > 0.08:
        messages.append(
            f"[WARN] Overall failure rate is high: "
            f"{failure_rate * 100:.2f}%."
        )
    else:
        messages.append(
            f"[INFO] Overall failure rate: "
            f"{failure_rate * 100:.2f}%."
        )

    # -------------------------------------------------------------------------
    # Insufficient funds
    # -------------------------------------------------------------------------

    insufficient_rate = (
        tx["is_insufficient_funds"]
        .mean()
    )

    if insufficient_rate > 0.04:
        messages.append(
            f"[WARN] Insufficient-funds failures "
            f"represent "
            f"{insufficient_rate * 100:.2f}% "
            f"of all transactions."
        )
    else:
        messages.append(
            f"[INFO] Insufficient-funds failures "
            f"represent "
            f"{insufficient_rate * 100:.2f}% "
            f"of all transactions."
        )

    # -------------------------------------------------------------------------
    # Failure-reason concentration
    # -------------------------------------------------------------------------

    failed = tx[
        tx["is_failed"]
    ]

    if len(failed):
        insufficient_failure_share = (
            failed[
                "is_insufficient_funds"
            ]
            .mean()
        )

        if (
            insufficient_failure_share
            > 0.85
        ):
            messages.append(
                "[WARN] Failure reasons are highly "
                "concentrated in INSUFFICIENT_FUNDS."
            )

    # -------------------------------------------------------------------------
    # Negative balances
    # -------------------------------------------------------------------------

    negative_balances = (
        balances[
            "closing_balance"
        ]
        .lt(0)
        .sum()
    )

    if negative_balances == 0:
        messages.append(
            "[PASS] No negative closing balances."
        )
    else:
        messages.append(
            f"[FAIL] Found "
            f"{negative_balances:,} "
            f"negative closing balances."
        )

    # -------------------------------------------------------------------------
    # Zero balances
    # -------------------------------------------------------------------------

    zero_share = (
        balances[
            "closing_balance"
        ]
        .eq(0)
        .mean()
    )

    if zero_share > 0.50:
        messages.append(
            f"[WARN] More than half of account-months "
            f"close at zero balance "
            f"({zero_share * 100:.2f}%)."
        )
    else:
        messages.append(
            f"[INFO] Zero-balance account-months: "
            f"{zero_share * 100:.2f}%."
        )

    # -------------------------------------------------------------------------
    # Extreme transaction concentration
    # -------------------------------------------------------------------------

    customer_tx = (
        tx.groupby("customer_id")
        .size()
        .sort_values(
            ascending=False
        )
    )

    if len(customer_tx):
        n_top = max(
            1,
            int(
                np.ceil(
                    len(customer_tx)
                    * 0.01
                )
            ),
        )

        top_1_share = (
            customer_tx
            .iloc[:n_top]
            .sum()
            / customer_tx.sum()
        )

        if top_1_share > 0.40:
            messages.append(
                f"[WARN] Top 1% of customers generate "
                f"{top_1_share * 100:.2f}% "
                f"of transactions."
            )
        else:
            messages.append(
                f"[INFO] Top 1% customer transaction "
                f"share: "
                f"{top_1_share * 100:.2f}%."
            )

    # -------------------------------------------------------------------------
    # Print results
    # -------------------------------------------------------------------------

    for message in messages:
        print(message)

    return messages


# =============================================================================
# Referential sanity checks
# =============================================================================

def validate_enrichment(
    tx: pd.DataFrame,
) -> None:
    print_subheader(
        "16. ECONOMIC ENRICHMENT SANITY"
    )

    missing_product = (
        tx["product_id"]
        .isna()
        .sum()
    )

    missing_customer = (
        tx["customer_id"]
        .isna()
        .sum()
    )

    missing_customer_type = (
        tx["customer_type"]
        .isna()
        .sum()
    )

    print(
        f"Transactions without product: "
        f"{missing_product:,}"
    )

    print(
        f"Transactions without customer: "
        f"{missing_customer:,}"
    )

    print(
        f"Transactions without customer type: "
        f"{missing_customer_type:,}"
    )


# =============================================================================
# Final summary
# =============================================================================

def print_final_summary(
    diagnostics: list[str],
) -> None:
    print_header(
        "BTYT ECONOMIC VALIDATION — SUMMARY"
    )

    warnings = [
        message
        for message in diagnostics
        if message.startswith(
            "[WARN]"
        )
    ]

    failures = [
        message
        for message in diagnostics
        if message.startswith(
            "[FAIL]"
        )
    ]

    passes = [
        message
        for message in diagnostics
        if message.startswith(
            "[PASS]"
        )
    ]

    print(
        f"PASS flags: {len(passes)}"
    )

    print(
        f"WARN flags: {len(warnings)}"
    )

    print(
        f"FAIL flags: {len(failures)}"
    )

    if failures:
        status = "FAIL"
    elif warnings:
        status = "REVIEW"
    else:
        status = "PASS"

    print()
    print(
        f"ECONOMIC VALIDATION STATUS: "
        f"{status}"
    )

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "Warnings are diagnostic indicators, not hard "
        "validation failures."
    )

    print(
        "The purpose of this script is to identify "
        "patterns that deserve economic interpretation "
        "before the transaction engine is frozen."
    )


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    tx, balances, accounts, customers = (
        load_data()
    )

    (
        tx,
        balances,
        accounts,
    ) = prepare_data(
        tx,
        balances,
        accounts,
        customers,
    )

    validate_dataset_summary(
        tx,
        balances,
    )

    validate_annual_activity(tx)

    validate_channels(tx)

    validate_cash_transition(tx)

    validate_transaction_types(tx)

    validate_product_behavior(tx)

    validate_customer_types(tx)

    validate_amounts(tx)

    validate_failures(tx)

    validate_balances(balances)

    validate_failure_liquidity(
        tx,
        balances,
    )

    validate_account_activity(tx)

    validate_customer_concentration(tx)

    validate_fixed_term_behavior(tx)

    validate_monthly_volatility(tx)

    diagnostics = (
        generate_diagnostics(
            tx,
            balances,
        )
    )

    validate_enrichment(tx)

    print_final_summary(
        diagnostics
    )


if __name__ == "__main__":
    main()