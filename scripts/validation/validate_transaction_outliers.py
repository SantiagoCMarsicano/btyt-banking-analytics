from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "processed"

tx = pd.read_csv(
    DATA_DIR / "transactions.csv",
    usecols=[
        "transaction_id", "account_id", "transaction_datetime",
        "transaction_type", "channel", "amount",
        "transaction_status", "counterparty_type", "merchant_category"
    ],
)
accounts = pd.read_csv(
    DATA_DIR / "accounts.csv",
    usecols=["account_id", "customer_id", "product_id"],
)
customers = pd.read_csv(
    DATA_DIR / "customers.csv",
    usecols=["customer_id", "customer_type"],
)

tx["amount"] = pd.to_numeric(tx["amount"], errors="coerce")
df = (
    tx.merge(accounts, on="account_id", how="left", validate="many_to_one")
      .merge(customers, on="customer_id", how="left", validate="many_to_one")
)
df = df[df["transaction_status"].eq("COMPLETED")].copy()

print("=" * 96)
print("BTYT TRANSACTION ENGINE — EXTREME AMOUNT AUDIT")
print("=" * 96)
print(f"Completed transactions: {len(df):,}")

types = [
    "CASH_WITHDRAWAL",
    "DEBIT_PURCHASE",
    "CASH_DEPOSIT",
    "SERVICE_PAYMENT",
    "TRANSFER_OUT",
    "TRANSFER_IN",
]

for tx_type in types:
    s = df[df["transaction_type"].eq(tx_type)].nlargest(20, "amount").copy()
    print("\n" + "-" * 96)
    print(f"TOP 20 — {tx_type}")
    print("-" * 96)
    if s.empty:
        print("No completed transactions.")
        continue
    cols = [
        "transaction_id", "transaction_datetime", "amount",
        "customer_type", "product_id", "channel",
        "counterparty_type", "merchant_category"
    ]
    s = s[cols]
    s["amount"] = s["amount"].map(lambda x: f"{x:,.2f}")
    print(s.to_string(index=False))

print("\n" + "-" * 96)
print("PHYSICAL CASH SUMMARY")
print("-" * 96)

cash = df[df["transaction_type"].isin(["CASH_WITHDRAWAL", "CASH_DEPOSIT"])].copy()
cash_summary = (
    cash.groupby(["transaction_type", "channel", "customer_type"], dropna=False)
        .agg(
            transactions=("transaction_id", "size"),
            median_amount=("amount", "median"),
            p99_amount=("amount", lambda s: s.quantile(0.99)),
            max_amount=("amount", "max"),
        )
        .reset_index()
)
for c in ["median_amount", "p99_amount", "max_amount"]:
    cash_summary[c] = cash_summary[c].map(lambda x: f"{x:,.2f}")
print(cash_summary.to_string(index=False))

print("\n" + "-" * 96)
print("DEBIT PURCHASE SUMMARY")
print("-" * 96)

p = df[df["transaction_type"].eq("DEBIT_PURCHASE")].copy()
purchase_summary = (
    p.groupby(["customer_type", "product_id"], dropna=False)
     .agg(
         transactions=("transaction_id", "size"),
         median_amount=("amount", "median"),
         p99_amount=("amount", lambda s: s.quantile(0.99)),
         p999_amount=("amount", lambda s: s.quantile(0.999)),
         max_amount=("amount", "max"),
     )
     .reset_index()
     .sort_values("max_amount", ascending=False)
)
for c in ["median_amount", "p99_amount", "p999_amount", "max_amount"]:
    purchase_summary[c] = purchase_summary[c].map(lambda x: f"{x:,.2f}")
print(purchase_summary.to_string(index=False))

print("\n" + "=" * 96)
print("AUDIT COMPLETE")
print("=" * 96)
print(
    "Interpret the records before changing the DGP. Large business transfers may "
    "be plausible; very large ATM withdrawals or individual debit purchases deserve review."
)
