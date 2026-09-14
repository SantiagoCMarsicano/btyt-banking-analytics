"""BTYT historical relational-constraint validation.

Validates constraints that were previously created as NOT VALID:
- 28 foreign keys
- 27 check constraints

Final architecture:
- 7 schemas
- 23 tables

This script does not create, modify, or delete data.
It only validates existing constraints against historical rows.

No arguments means no changes.

Examples:
    python scripts/database/validate_relational_model.py --inspect
    python scripts/database/validate_relational_model.py --check
    python scripts/database/validate_relational_model.py --fk
    python scripts/database/validate_relational_model.py --all
"""

from getpass import getpass
import argparse

from sqlalchemy import create_engine, text


DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "BTYT"
DB_USER = "postgres"

BTYT_SCHEMAS = [
    "core",
    "banking",
    "marketing",
    "reference",
    "market",
    "macro",
    "performance",
]

FINAL_SCHEMA_LAYOUT = {
    "core": ["branches", "customers", "accounts", "products"],
    "banking": [
        "cards",
        "loans",
        "transactions",
        "account_balances",
        "loan_monthly_snapshot",
    ],
    "marketing": ["campaigns", "campaign_customers", "campaign_exposures"],
    "reference": ["campaign_channels", "campaign_geography"],
    "market": [
        "banks",
        "bank_financials",
        "bank_market_weights",
        "bank_world_parameters",
        "financial_institutions",
    ],
    "macro": ["macro_environment", "external_shocks"],
    "performance": ["bank_monthly_performance", "branch_monthly_performance"],
}



def inspect_schema_layout(engine):
    """Inspect the exact final 7-schema / 23-table architecture."""

    sql = text("""
        SELECT table_schema AS schema_name, table_name
        FROM information_schema.tables
        WHERE table_schema = ANY(:schemas)
          AND table_type = 'BASE TABLE'
        ORDER BY table_schema, table_name;
    """)

    with engine.connect() as connection:
        rows = connection.execute(
            sql,
            {"schemas": BTYT_SCHEMAS},
        ).mappings().all()

    observed = {}
    for row in rows:
        observed.setdefault(row["schema_name"], []).append(row["table_name"])

    print("\n" + "=" * 72)
    print("FINAL SCHEMA LAYOUT INSPECTION")
    print("=" * 72)

    total_observed = 0
    all_pass = True

    for schema in BTYT_SCHEMAS:
        expected = set(FINAL_SCHEMA_LAYOUT[schema])
        actual = set(observed.get(schema, []))

        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)

        passed = not missing and not unexpected
        all_pass = all_pass and passed
        total_observed += len(actual)

        status = "PASS" if passed else "FAIL"

        print(
            f"[{status}] {schema:<12} "
            f"{len(actual)} / {len(expected)} tables"
        )

        if missing:
            print(f"       Missing    : {', '.join(missing)}")

        if unexpected:
            print(f"       Unexpected : {', '.join(unexpected)}")

    total_status = "PASS" if all_pass and total_observed == 23 else "FAIL"

    print(
        f"\n[{total_status}] Observed BTYT tables: "
        f"{total_observed} / 23"
    )

    return all_pass and total_observed == 23

def create_db_engine():
    password = getpass("PostgreSQL password: ")
    url = f"postgresql+psycopg://{DB_USER}:{password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(url)


def verify_connection(engine):
    with engine.connect() as connection:
        db = connection.execute(text("SELECT current_database();")).scalar_one()
        version = connection.execute(text("SELECT version();")).scalar_one()

    print("=" * 72)
    print("BTYT RELATIONAL MODEL HISTORICAL VALIDATION")
    print("=" * 72)
    print(f"Database : {db}")
    print(f"Server   : {version}\n")

    if db != DB_NAME:
        raise RuntimeError(f"Connected to {db!r}; expected {DB_NAME!r}. Aborting.")


def constraint_state(engine, schema, table, name):
    sql = text("""
        SELECT
            con.contype,
            con.convalidated
        FROM pg_constraint con
        JOIN pg_class c
          ON c.oid = con.conrelid
        JOIN pg_namespace n
          ON n.oid = c.relnamespace
        WHERE n.nspname = :schema
          AND c.relname = :table
          AND con.conname = :name;
    """)

    with engine.connect() as connection:
        row = connection.execute(
            sql,
            {"schema": schema, "table": table, "name": name},
        ).mappings().one_or_none()

    return row


def validate_constraint(engine, schema, table, name, expected_type):
    state = constraint_state(engine, schema, table, name)

    if state is None:
        raise RuntimeError(
            f"Constraint not found: {schema}.{table}.{name}"
        )

    actual_type = state["contype"]

    if actual_type != expected_type:
        raise RuntimeError(
            f"Constraint type mismatch for {schema}.{table}.{name}: "
            f"expected {expected_type!r}, found {actual_type!r}"
        )

    if state["convalidated"]:
        print(f"[SKIP ] {schema}.{table}.{name}: already validated")
        return

    sql = (
        f'ALTER TABLE "{schema}"."{table}" '
        f'VALIDATE CONSTRAINT "{name}";'
    )

    print(f"[APPLY] {schema}.{table}.{name}")

    with engine.begin() as connection:
        connection.execute(text(sql))

    print(f"[DONE ] {schema}.{table}.{name}")


# Order is intentional:
# smaller/medium tables first, very large transaction-related validations last.

FOREIGN_KEYS = [
    ("core", "branches", "fk_branches_parent_branch"),
    ("core", "customers", "fk_customers_primary_branch"),
    ("core", "accounts", "fk_accounts_customer"),
    ("core", "accounts", "fk_accounts_product"),
    ("core", "accounts", "fk_accounts_branch"),

    ("banking", "cards", "fk_cards_customer"),
    ("banking", "cards", "fk_cards_product"),
    ("banking", "cards", "fk_cards_linked_account"),
    ("banking", "loans", "fk_loans_customer"),
    ("banking", "loans", "fk_loans_product"),
    ("banking", "loans", "fk_loans_branch"),
    ("banking", "account_balances", "fk_account_balances_account"),
    ("banking", "loan_monthly_snapshot", "fk_loan_monthly_snapshot_loan"),

    ("marketing", "campaigns", "fk_campaigns_target_product"),
    ("marketing", "campaign_customers", "fk_campaign_customers_campaign"),
    ("marketing", "campaign_customers", "fk_campaign_customers_customer"),
    ("marketing", "campaign_exposures", "fk_campaign_exposures_campaign"),
    ("marketing", "campaign_exposures", "fk_campaign_exposures_customer"),

    ("reference", "campaign_channels", "fk_campaign_channels_campaign"),
    ("reference", "campaign_geography", "fk_campaign_geography_campaign"),

    ("market", "bank_financials", "fk_bank_financials_bank"),
    ("market", "bank_market_weights", "fk_bank_market_weights_bank"),
    ("market", "bank_world_parameters", "fk_bank_world_parameters_bank"),
    ("performance", "branch_monthly_performance", "fk_branch_monthly_performance_branch"),
    ("market", "financial_institutions", "fk_financial_institutions_bank"),

    # Largest table last.
    ("banking", "transactions", "fk_transactions_account"),
    ("banking", "transactions", "fk_transactions_branch"),
    ("banking", "transactions", "fk_transactions_counterparty_institution"),
]


CHECK_CONSTRAINTS = [
    ("core", "branches", "ck_branches_closing_after_opening"),
    ("core", "accounts", "ck_accounts_closing_after_opening"),
    ("core", "accounts", "ck_accounts_status_closing_year"),
    ("core", "customers", "ck_customers_closing_after_registration"),
    ("core", "customers", "ck_customers_monthly_income_nonnegative"),
    ("core", "customers", "ck_customers_annual_revenue_nonnegative"),

    ("banking", "cards", "ck_cards_status_closing_year"),
    ("banking", "loans", "ck_loans_original_amount_positive"),
    ("banking", "loans", "ck_loans_term_months_positive"),
    ("banking", "loans", "ck_loans_active_closing_year"),

    ("banking", "loan_monthly_snapshot", "ck_loan_snapshot_dpd_nonnegative"),
    ("banking", "loan_monthly_snapshot", "ck_loan_snapshot_outstanding_balance_nonnegative"),
    ("banking", "loan_monthly_snapshot", "ck_loan_snapshot_scheduled_payment_nonnegative"),
    ("banking", "loan_monthly_snapshot", "ck_loan_snapshot_actual_payment_nonnegative"),
    ("banking", "loan_monthly_snapshot", "ck_loan_snapshot_arrears_nonnegative"),

    ("marketing", "campaigns", "ck_campaigns_end_after_start"),
    ("marketing", "campaign_customers", "ck_campaign_customers_exposure_date"),
    ("marketing", "campaign_customers", "ck_campaign_customers_unexposed_response"),
    ("marketing", "campaign_customers", "ck_campaign_customers_response_date"),

    ("market", "financial_institutions", "ck_financial_institutions_active_period"),
    ("macro", "external_shocks", "ck_external_shocks_start_peak"),
    ("macro", "external_shocks", "ck_external_shocks_peak_end"),
    ("macro", "external_shocks", "ck_external_shocks_end_recovery"),

    # Largest table last.
    ("banking", "transactions", "ck_transactions_amount_nonnegative"),
    ("banking", "transactions", "ck_transactions_status_failure_reason"),
    ("banking", "transactions", "ck_transactions_channel_branch"),
    ("banking", "transactions", "ck_nontransfer_scope_null"),
]


def validate_foreign_keys(engine):
    print("\n--- FOREIGN KEY HISTORICAL VALIDATION ---\n")

    for schema, table, name in FOREIGN_KEYS:
        validate_constraint(
            engine,
            schema,
            table,
            name,
            expected_type="f",
        )


def validate_checks(engine):
    print("\n--- CHECK CONSTRAINT HISTORICAL VALIDATION ---\n")

    for schema, table, name in CHECK_CONSTRAINTS:
        validate_constraint(
            engine,
            schema,
            table,
            name,
            expected_type="c",
        )


def inspect_validation(engine):
    """Inspect the exact FK/CHECK validation plan and current state."""

    print("\n" + "=" * 72)
    print("HISTORICAL VALIDATION INSPECTION")
    print("=" * 72)

    tracked = []

    for schema, table, name in FOREIGN_KEYS:
        state = constraint_state(engine, schema, table, name)

        if state is None:
            tracked.append({
                "schema": schema,
                "table": table,
                "name": name,
                "kind": "FK",
                "exists": False,
                "validated": False,
                "type_ok": False,
            })
            continue

        tracked.append({
            "schema": schema,
            "table": table,
            "name": name,
            "kind": "FK",
            "exists": True,
            "validated": bool(state["convalidated"]),
            "type_ok": state["contype"] == "f",
        })

    for schema, table, name in CHECK_CONSTRAINTS:
        state = constraint_state(engine, schema, table, name)

        if state is None:
            tracked.append({
                "schema": schema,
                "table": table,
                "name": name,
                "kind": "CHECK",
                "exists": False,
                "validated": False,
                "type_ok": False,
            })
            continue

        tracked.append({
            "schema": schema,
            "table": table,
            "name": name,
            "kind": "CHECK",
            "exists": True,
            "validated": bool(state["convalidated"]),
            "type_ok": state["contype"] == "c",
        })

    for row in tracked:
        if not row["exists"]:
            status = "MISSING"
        elif not row["type_ok"]:
            status = "TYPE_MISMATCH"
        elif row["validated"]:
            status = "VALIDATED"
        else:
            status = "NOT_VALIDATED"

        print(
            f'{row["schema"]}.{row["table"]:<38} '
            f'{row["kind"]:<6} '
            f'{row["name"]:<55} '
            f'{status}'
        )

    fk_rows = [row for row in tracked if row["kind"] == "FK"]
    ck_rows = [row for row in tracked if row["kind"] == "CHECK"]

    fk_valid = sum(
        row["exists"] and row["type_ok"] and row["validated"]
        for row in fk_rows
    )
    ck_valid = sum(
        row["exists"] and row["type_ok"] and row["validated"]
        for row in ck_rows
    )

    fk_missing = sum(not row["exists"] for row in fk_rows)
    ck_missing = sum(not row["exists"] for row in ck_rows)

    fk_type_mismatch = sum(
        row["exists"] and not row["type_ok"]
        for row in fk_rows
    )
    ck_type_mismatch = sum(
        row["exists"] and not row["type_ok"]
        for row in ck_rows
    )

    print("\nSummary:")
    print(
        f"Foreign keys validated        : "
        f"{fk_valid} / {len(FOREIGN_KEYS)}"
    )
    print(
        f"Check constraints validated   : "
        f"{ck_valid} / {len(CHECK_CONSTRAINTS)}"
    )

    expected_total = len(FOREIGN_KEYS) + len(CHECK_CONSTRAINTS)
    valid_total = fk_valid + ck_valid

    print(
        f"Tracked historical constraints: "
        f"{valid_total} / {expected_total}"
    )

    print(f"Missing foreign keys          : {fk_missing}")
    print(f"Missing CHECK constraints     : {ck_missing}")
    print(f"FK type mismatches            : {fk_type_mismatch}")
    print(f"CHECK type mismatches         : {ck_type_mismatch}")

    overall_pass = (
        fk_valid == len(FOREIGN_KEYS)
        and ck_valid == len(CHECK_CONSTRAINTS)
        and fk_missing == 0
        and ck_missing == 0
        and fk_type_mismatch == 0
        and ck_type_mismatch == 0
    )

    print(
        f"\n[{'PASS' if overall_pass else 'FAIL'}] "
        f"Historical relational validation"
    )

    return fk_valid, ck_valid, overall_pass

def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate BTYT historical relational constraints."
    )
    parser.add_argument(
        "--fk",
        action="store_true",
        help="Validate the 28 existing foreign keys.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the 27 existing CHECK constraints.",
    )
    parser.add_argument(
        "--schema-layout",
        action="store_true",
        help="Inspect the final 7-schema / 23-table architecture.",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Inspect schema layout and FK/CHECK validation state without modifying anything.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate CHECK constraints, then foreign keys, then inspect.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not any([
        args.fk,
        args.check,
        args.schema_layout,
        args.inspect,
        args.all,
    ]):
        print(
            "No action selected. Nothing changed.\n\n"
            "Use one of:\n"
            "  --schema-layout\n"
            "  --inspect\n"
            "  --check\n"
            "  --fk\n"
            "  --all"
        )
        return

    engine = create_db_engine()

    try:
        verify_connection(engine)

        if args.all:
            inspect_schema_layout(engine)
            validate_checks(engine)
            validate_foreign_keys(engine)
            inspect_validation(engine)
            return

        if args.schema_layout:
            inspect_schema_layout(engine)

        if args.check:
            validate_checks(engine)

        if args.fk:
            validate_foreign_keys(engine)

        if args.inspect:
            inspect_schema_layout(engine)
            inspect_validation(engine)
        elif args.check or args.fk:
            inspect_validation(engine)

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()