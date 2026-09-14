"""BTYT historical relational-constraint validation.

Validates constraints that were previously created as NOT VALID:
- 28 foreign keys
- 27 check constraints

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

BTYT_SCHEMAS = ["core", "banking", "marketing", "market", "reference"]


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
    ("market", "branch_monthly_performance", "fk_branch_monthly_performance_branch"),
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
    ("market", "external_shocks", "ck_external_shocks_start_peak"),
    ("market", "external_shocks", "ck_external_shocks_peak_end"),
    ("market", "external_shocks", "ck_external_shocks_end_recovery"),

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
    sql = text("""
        SELECT
            n.nspname AS schema_name,
            c.relname AS table_name,
            con.conname AS constraint_name,
            con.contype AS constraint_type,
            con.convalidated AS validated
        FROM pg_constraint con
        JOIN pg_class c
          ON c.oid = con.conrelid
        JOIN pg_namespace n
          ON n.oid = c.relnamespace
        WHERE n.nspname = ANY(:schemas)
          AND con.contype IN ('f', 'c')
        ORDER BY
            n.nspname,
            c.relname,
            con.contype,
            con.conname;
    """)

    with engine.connect() as connection:
        rows = connection.execute(
            sql,
            {"schemas": BTYT_SCHEMAS},
        ).mappings().all()

    print("\n" + "=" * 72)
    print("HISTORICAL VALIDATION INSPECTION")
    print("=" * 72)

    for row in rows:
        kind = "FK" if row["constraint_type"] == "f" else "CHECK"
        print(
            f'{row["schema_name"]}.{row["table_name"]:<38} '
            f'{kind:<5} '
            f'{row["constraint_name"]:<55} '
            f'validated={row["validated"]}'
        )

    fk_rows = [row for row in rows if row["constraint_type"] == "f"]
    ck_rows = [row for row in rows if row["constraint_type"] == "c"]

    fk_valid = sum(bool(row["validated"]) for row in fk_rows)
    ck_valid = sum(bool(row["validated"]) for row in ck_rows)

    print("\nSummary:")
    print(f"Foreign keys validated : {fk_valid} / {len(FOREIGN_KEYS)}")
    print(f"Check constraints validated : {ck_valid} / {len(CHECK_CONSTRAINTS)}")

    expected_total = len(FOREIGN_KEYS) + len(CHECK_CONSTRAINTS)
    actual_total = len(fk_rows) + len(ck_rows)

    print(f"Tracked historical constraints : {actual_total} / {expected_total}")

    if len(fk_rows) != len(FOREIGN_KEYS):
        print(
            f"[WARN ] PostgreSQL reports {len(fk_rows)} FK constraints in BTYT schemas; "
            f"the validation plan expects {len(FOREIGN_KEYS)}."
        )

    if len(ck_rows) != len(CHECK_CONSTRAINTS):
        print(
            f"[WARN ] PostgreSQL reports {len(ck_rows)} CHECK constraints in BTYT schemas; "
            f"the validation plan expects {len(CHECK_CONSTRAINTS)}."
        )

    return fk_valid, ck_valid


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
        "--inspect",
        action="store_true",
        help="Inspect FK/CHECK validation state without modifying anything.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate CHECK constraints, then foreign keys, then inspect.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not any([args.fk, args.check, args.inspect, args.all]):
        print(
            "No action selected. Nothing changed.\n\n"
            "Use one of:\n"
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
            validate_checks(engine)
            validate_foreign_keys(engine)
            inspect_validation(engine)
            return

        if args.check:
            validate_checks(engine)

        if args.fk:
            validate_foreign_keys(engine)

        if args.inspect or args.check or args.fk:
            inspect_validation(engine)

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
