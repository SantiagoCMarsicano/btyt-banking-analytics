"""BTYT relational-model application script.

Applies only decisions already audited and approved:
- semantic type conversions
- monetary precision conversions
- 23 primary keys
- 28 foreign keys (NOT VALID)
- audited NOT NULL constraints
- audited CHECK constraints (NOT VALID)

No arguments means no changes. Extra indexes and historical validation
remain separate phases.
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
    print("BTYT RELATIONAL MODEL APPLY")
    print("=" * 72)
    print(f"Database : {db}")
    print(f"Server   : {version}\n")
    if db != DB_NAME:
        raise RuntimeError(f"Connected to {db!r}; expected {DB_NAME!r}. Aborting.")


def execute(engine, label, sql):
    print(f"\n[APPLY] {label}")
    with engine.begin() as connection:
        connection.execute(text(sql))
    print(f"[DONE ] {label}")


def constraint_exists(engine, schema, table, name):
    sql = text("""
        SELECT EXISTS (
            SELECT 1
            FROM pg_constraint con
            JOIN pg_class c ON c.oid = con.conrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = :schema
              AND c.relname = :table
              AND con.conname = :name
        );
    """)
    with engine.connect() as connection:
        return bool(connection.execute(sql, {"schema": schema, "table": table, "name": name}).scalar_one())


def current_column_type(engine, schema, table, column):
    sql = text("""
        SELECT data_type
        FROM information_schema.columns
        WHERE table_schema = :schema
          AND table_name = :table
          AND column_name = :column;
    """)
    with engine.connect() as connection:
        return connection.execute(sql, {"schema": schema, "table": table, "column": column}).scalar_one_or_none()


def apply_type(engine, schema, table, column, target, using, precheck=None):
    current = current_column_type(engine, schema, table, column)
    if current is None:
        raise RuntimeError(f"Column not found: {schema}.{table}.{column}")

    if target.startswith("numeric") and current == "numeric":
        print(f"\n[SKIP ] {schema}.{table}.{column} already NUMERIC")
        return
    if current == target:
        print(f"\n[SKIP ] {schema}.{table}.{column} already {target}")
        return

    if precheck:
        with engine.connect() as connection:
            bad_rows = int(connection.execute(text(precheck)).scalar_one())
        if bad_rows:
            raise RuntimeError(f"Pre-check failed for {schema}.{table}.{column}: {bad_rows:,} incompatible rows")

    sql = f'ALTER TABLE "{schema}"."{table}" ALTER COLUMN "{column}" TYPE {target} USING {using};'
    execute(engine, f"{schema}.{table}.{column}: {current} -> {target}", sql)


SEMANTIC_TYPES = [
    ("core","branches","opening_year","integer",'"opening_year"::integer'),
    ("core","branches","closing_year","integer",'"closing_year"::integer'),
    ("core","branches","closure_reason","text",'"closure_reason"::text'),
    ("core","customers","birth_year","integer",'"birth_year"::integer'),
    ("core","customers","registration_year","integer",'"registration_year"::integer'),
    ("core","customers","closing_year","integer",'"closing_year"::integer'),
    ("core","customers","foundation_year","integer",'"foundation_year"::integer'),
    ("core","accounts","opening_year","integer",'"opening_year"::integer'),
    ("core","accounts","closing_year","integer",'"closing_year"::integer'),
    ("core","products","launch_year","integer",'"launch_year"::integer'),
    ("banking","account_balances","year_month","date",'to_date("year_month", \'YYYY-MM\')'),
    ("banking","cards","issue_year","integer",'"issue_year"::integer'),
    ("banking","cards","closing_year","integer",'"closing_year"::integer'),
    ("banking","loan_monthly_snapshot","year_month","date",'to_date("year_month", \'YYYY-MM\')'),
    ("banking","loans","origination_year","integer",'"origination_year"::integer'),
    ("banking","loans","term_months","integer",'"term_months"::integer'),
    ("banking","loans","closing_year","integer",'"closing_year"::integer'),
    ("marketing","campaigns","start_date","date",'"start_date"::date'),
    ("marketing","campaigns","end_date","date",'"end_date"::date'),
    ("market","bank_financials","year","integer",'"year"::integer'),
    ("market","bank_market_weights","year","integer",'"year"::integer'),
    ("market","bank_monthly_performance","year_month","date",'to_date("year_month", \'YYYY-MM\')'),
    ("market","branch_monthly_performance","year_month","date",'to_date("year_month", \'YYYY-MM\')'),
    ("market","external_shocks","start_month","date",'to_date("start_month", \'YYYY-MM\')'),
    ("market","external_shocks","peak_month","date",'to_date("peak_month", \'YYYY-MM\')'),
    ("market","external_shocks","end_month","date",'to_date("end_month", \'YYYY-MM\')'),
    ("market","external_shocks","recovery_end_month","date",'to_date("recovery_end_month", \'YYYY-MM\')'),
    ("market","external_shocks","duration_months","integer",'"duration_months"::integer'),
    ("market","external_shocks","recovery_months","integer",'"recovery_months"::integer'),
    ("market","financial_institutions","active_from","date",'"active_from"::date'),
    ("market","macro_environment","year","integer",'"year"::integer'),
]

MONEY_18_2 = [
    ("banking","account_balances","opening_balance"),("banking","account_balances","total_inflows"),
    ("banking","account_balances","total_outflows"),("banking","account_balances","closing_balance"),
    ("banking","loan_monthly_snapshot","outstanding_balance"),("banking","loan_monthly_snapshot","scheduled_payment"),
    ("banking","loan_monthly_snapshot","actual_payment"),("banking","loan_monthly_snapshot","arrears_amount"),
    ("banking","loans","original_amount"),("banking","transactions","amount"),
    ("core","customers","monthly_income"),("core","customers","annual_revenue"),
    ("market","bank_monthly_performance","average_deposits"),("market","bank_monthly_performance","average_loan_balance"),
    ("market","branch_monthly_performance","average_deposits"),("market","branch_monthly_performance","average_loan_balance"),
]

LARGE_COLUMNS = ["transaction_volume","interest_income","interest_expense","net_interest_income","fee_income","total_revenue","personnel_cost","fixed_cost","variable_cost","operational_cost","total_operating_cost","credit_loss","pre_provision_profit","net_income"]
MONEY_20_2 = [
    ("market","bank_financials",c) for c in ["revenue","operating_costs","net_income","total_assets","total_deposits","total_loans","equity"]
] + [
    ("market",t,c) for t in ["bank_monthly_performance","branch_monthly_performance"] for c in LARGE_COLUMNS
]


def apply_semantic_types(engine):
    print("\n--- SEMANTIC TYPES ---")
    for args in SEMANTIC_TYPES:
        apply_type(engine, *args)
    apply_type(
        engine, "market", "financial_institutions", "active_to", "date", "NULL::date",
        precheck="SELECT COUNT(*) FROM market.financial_institutions WHERE active_to IS NOT NULL;",
    )


def apply_precision(engine):
    print("\n--- FINANCIAL PRECISION ---")
    print("Rates, ratios, simulation variables and coordinates remain DOUBLE PRECISION.")
    for schema, table, column in MONEY_18_2:
        if (schema, table, column) == ("banking", "transactions", "amount"):
            print("\n[WARN ] transactions.amount has ~76.8M rows; conversion can take substantial time/disk.")
        apply_type(engine, schema, table, column, "numeric(18,2)", f'"{column}"::numeric(18,2)')
    for schema, table, column in MONEY_20_2:
        apply_type(engine, schema, table, column, "numeric(20,2)", f'"{column}"::numeric(20,2)')


PRIMARY_KEYS = [
    ("core","branches","pk_branches",["branch_id"]),("core","customers","pk_customers",["customer_id"]),
    ("core","accounts","pk_accounts",["account_id"]),("core","products","pk_products",["product_id"]),
    ("banking","cards","pk_cards",["card_id"]),("banking","loans","pk_loans",["loan_id"]),
    ("banking","transactions","pk_transactions",["transaction_id"]),
    ("banking","account_balances","pk_account_balances",["account_id","year_month"]),
    ("banking","loan_monthly_snapshot","pk_loan_monthly_snapshot",["loan_id","year_month"]),
    ("marketing","campaigns","pk_campaigns",["campaign_id"]),
    ("marketing","campaign_customers","pk_campaign_customers",["campaign_id","customer_id"]),
    ("marketing","campaign_exposures","pk_campaign_exposures",["exposure_id"]),
    ("market","banks","pk_banks",["bank_id"]),("market","bank_financials","pk_bank_financials",["bank_id","year"]),
    ("market","bank_market_weights","pk_bank_market_weights",["bank_id","year"]),
    ("market","bank_world_parameters","pk_bank_world_parameters",["world_seed","bank_id"]),
    ("market","bank_monthly_performance","pk_bank_monthly_performance",["year_month"]),
    ("market","branch_monthly_performance","pk_branch_monthly_performance",["branch_id","year_month"]),
    ("market","financial_institutions","pk_financial_institutions",["institution_id"]),
    ("market","macro_environment","pk_macro_environment",["year"]),("market","external_shocks","pk_external_shocks",["shock_id"]),
    ("reference","campaign_channels","pk_campaign_channels",["campaign_id","channel"]),
    ("reference","campaign_geography","pk_campaign_geography",["campaign_id","geography_level","geography_value"]),
]


def apply_primary_keys(engine):
    print("\n--- PRIMARY KEYS ---")
    for schema, table, name, columns in PRIMARY_KEYS:
        if constraint_exists(engine, schema, table, name):
            print(f"\n[SKIP ] {schema}.{table}.{name} already exists")
            continue
        if (schema, table) == ("banking", "transactions"):
            print("\n[WARN ] pk_transactions builds a unique index over ~76.8M IDs.")
        cols = ", ".join(f'"{c}"' for c in columns)
        execute(engine, f"{schema}.{table}.{name}", f'ALTER TABLE "{schema}"."{table}" ADD CONSTRAINT "{name}" PRIMARY KEY ({cols});')


FOREIGN_KEYS = [
    ("core","customers","fk_customers_primary_branch","primary_branch_id","core","branches","branch_id"),
    ("core","accounts","fk_accounts_customer","customer_id","core","customers","customer_id"),
    ("core","accounts","fk_accounts_product","product_id","core","products","product_id"),
    ("core","accounts","fk_accounts_branch","branch_id","core","branches","branch_id"),
    ("core","branches","fk_branches_parent_branch","parent_branch_id","core","branches","branch_id"),
    ("banking","cards","fk_cards_customer","customer_id","core","customers","customer_id"),
    ("banking","cards","fk_cards_product","product_id","core","products","product_id"),
    ("banking","cards","fk_cards_linked_account","linked_account_id","core","accounts","account_id"),
    ("banking","loans","fk_loans_customer","customer_id","core","customers","customer_id"),
    ("banking","loans","fk_loans_product","product_id","core","products","product_id"),
    ("banking","loans","fk_loans_branch","branch_id","core","branches","branch_id"),
    ("banking","account_balances","fk_account_balances_account","account_id","core","accounts","account_id"),
    ("banking","loan_monthly_snapshot","fk_loan_monthly_snapshot_loan","loan_id","banking","loans","loan_id"),
    ("banking","transactions","fk_transactions_account","account_id","core","accounts","account_id"),
    ("banking","transactions","fk_transactions_branch","transaction_branch_id","core","branches","branch_id"),
    ("banking","transactions","fk_transactions_counterparty_institution","counterparty_institution_id","market","financial_institutions","institution_id"),
    ("marketing","campaigns","fk_campaigns_target_product","target_product_id","core","products","product_id"),
    ("marketing","campaign_customers","fk_campaign_customers_campaign","campaign_id","marketing","campaigns","campaign_id"),
    ("marketing","campaign_customers","fk_campaign_customers_customer","customer_id","core","customers","customer_id"),
    ("marketing","campaign_exposures","fk_campaign_exposures_campaign","campaign_id","marketing","campaigns","campaign_id"),
    ("marketing","campaign_exposures","fk_campaign_exposures_customer","customer_id","core","customers","customer_id"),
    ("reference","campaign_channels","fk_campaign_channels_campaign","campaign_id","marketing","campaigns","campaign_id"),
    ("reference","campaign_geography","fk_campaign_geography_campaign","campaign_id","marketing","campaigns","campaign_id"),
    ("market","bank_financials","fk_bank_financials_bank","bank_id","market","banks","bank_id"),
    ("market","bank_market_weights","fk_bank_market_weights_bank","bank_id","market","banks","bank_id"),
    ("market","bank_world_parameters","fk_bank_world_parameters_bank","bank_id","market","banks","bank_id"),
    ("market","branch_monthly_performance","fk_branch_monthly_performance_branch","branch_id","core","branches","branch_id"),
    ("market","financial_institutions","fk_financial_institutions_bank","bank_id","market","banks","bank_id"),
]


def apply_foreign_keys(engine):
    print("\n--- FOREIGN KEYS ---")
    print("FKs are created NOT VALID; historical validation remains separate.")
    for cs, ct, name, cc, ps, pt, pc in FOREIGN_KEYS:
        if constraint_exists(engine, cs, ct, name):
            print(f"\n[SKIP ] {cs}.{ct}.{name} already exists")
            continue
        sql = f'ALTER TABLE "{cs}"."{ct}" ADD CONSTRAINT "{name}" FOREIGN KEY ("{cc}") REFERENCES "{ps}"."{pt}" ("{pc}") NOT VALID;'
        execute(engine, f"{cs}.{ct}.{name}", sql)



# =====================================================================
# NOT NULL AND CHECK CONSTRAINTS
# =====================================================================

NOT_NULL_COLUMNS = [
    ("core", "accounts", "customer_id"),
    ("core", "accounts", "product_id"),
    ("core", "accounts", "branch_id"),
    ("banking", "cards", "customer_id"),
    ("banking", "cards", "product_id"),
    ("banking", "loans", "customer_id"),
    ("banking", "loans", "product_id"),
    ("banking", "loans", "branch_id"),
    ("banking", "transactions", "account_id"),
    ("marketing", "campaign_exposures", "campaign_id"),
    ("marketing", "campaign_exposures", "customer_id"),
]

CHECK_CONSTRAINTS = [
    ("banking", "transactions",
     "ck_transactions_amount_nonnegative",
     '"amount" >= 0'),

    ("banking", "loan_monthly_snapshot",
     "ck_loan_snapshot_dpd_nonnegative",
     '"days_past_due" >= 0'),

    ("banking", "loan_monthly_snapshot",
     "ck_loan_snapshot_outstanding_balance_nonnegative",
     '"outstanding_balance" >= 0'),

    ("banking", "loan_monthly_snapshot",
     "ck_loan_snapshot_scheduled_payment_nonnegative",
     '"scheduled_payment" >= 0'),

    ("banking", "loan_monthly_snapshot",
     "ck_loan_snapshot_actual_payment_nonnegative",
     '"actual_payment" >= 0'),

    ("banking", "loan_monthly_snapshot",
     "ck_loan_snapshot_arrears_nonnegative",
     '"arrears_amount" >= 0'),

    ("banking", "loans",
     "ck_loans_original_amount_positive",
     '"original_amount" > 0'),

    ("banking", "loans",
     "ck_loans_term_months_positive",
     '"term_months" > 0'),

    ("core", "customers",
     "ck_customers_monthly_income_nonnegative",
     '"monthly_income" >= 0'),

    ("core", "customers",
     "ck_customers_annual_revenue_nonnegative",
     '"annual_revenue" >= 0'),

    ("core", "branches",
     "ck_branches_closing_after_opening",
     '"closing_year" IS NULL OR "opening_year" IS NULL OR "closing_year" >= "opening_year"'),

    ("core", "accounts",
     "ck_accounts_closing_after_opening",
     '"closing_year" IS NULL OR "opening_year" IS NULL OR "closing_year" >= "opening_year"'),

    ("core", "customers",
     "ck_customers_closing_after_registration",
     '"closing_year" IS NULL OR "registration_year" IS NULL OR "closing_year" >= "registration_year"'),

    ("marketing", "campaigns",
     "ck_campaigns_end_after_start",
     '"end_date" IS NULL OR "start_date" IS NULL OR "end_date" >= "start_date"'),

    ("market", "financial_institutions",
     "ck_financial_institutions_active_period",
     '"active_to" IS NULL OR "active_from" IS NULL OR "active_to" >= "active_from"'),

    ("market", "external_shocks",
     "ck_external_shocks_start_peak",
     '"start_month" IS NULL OR "peak_month" IS NULL OR "start_month" <= "peak_month"'),

    ("market", "external_shocks",
     "ck_external_shocks_peak_end",
     '"peak_month" IS NULL OR "end_month" IS NULL OR "peak_month" <= "end_month"'),

    ("market", "external_shocks",
     "ck_external_shocks_end_recovery",
     '"end_month" IS NULL OR "recovery_end_month" IS NULL OR "end_month" <= "recovery_end_month"'),

    ("core", "accounts",
     "ck_accounts_status_closing_year",
     """("account_status" = 'ACTIVE' AND "closing_year" IS NULL)
        OR ("account_status" = 'CLOSED' AND "closing_year" IS NOT NULL)"""),

    ("banking", "cards",
     "ck_cards_status_closing_year",
     """("card_status" = 'ACTIVE' AND "closing_year" IS NULL)
        OR ("card_status" = 'CLOSED' AND "closing_year" IS NOT NULL)"""),

    ("banking", "loans",
     "ck_loans_active_closing_year",
     """"loan_status" <> 'ACTIVE' OR "closing_year" IS NULL"""),

    ("banking", "transactions",
     "ck_transactions_status_failure_reason",
     """("transaction_status" = 'COMPLETED' AND "failure_reason" IS NULL)
        OR ("transaction_status" = 'FAILED' AND "failure_reason" IS NOT NULL)"""),

    ("banking", "transactions",
     "ck_transactions_channel_branch",
     """("channel" = 'BRANCH' AND "transaction_branch_id" IS NOT NULL)
        OR ("channel" <> 'BRANCH' AND "transaction_branch_id" IS NULL)"""),

    ("banking", "transactions",
     "ck_nontransfer_scope_null",
     """"transaction_type" IN ('TRANSFER_IN', 'TRANSFER_OUT')
        OR "transfer_scope" IS NULL"""),

    ("marketing", "campaign_customers",
     "ck_campaign_customers_exposure_date",
     """("exposure_status" = 'EXPOSED' AND "exposure_date" IS NOT NULL)
        OR ("exposure_status" = 'NOT_EXPOSED' AND "exposure_date" IS NULL)"""),

    ("marketing", "campaign_customers",
     "ck_campaign_customers_unexposed_response",
     """"exposure_status" <> 'NOT_EXPOSED'
        OR "response_status" IS NULL"""),

    ("marketing", "campaign_customers",
     "ck_campaign_customers_response_date",
     """("response_status" IS NULL AND "response_date" IS NULL)
        OR ("response_status" = 'NO_RESPONSE' AND "response_date" IS NULL)
        OR ("response_status" IN ('POSITIVE', 'NEUTRAL', 'NEGATIVE')
            AND "response_date" IS NOT NULL)"""),
]


def column_is_not_null(engine, schema, table, column):
    sql = text("""
        SELECT is_nullable = 'NO'
        FROM information_schema.columns
        WHERE table_schema = :schema
          AND table_name = :table
          AND column_name = :column;
    """)
    with engine.connect() as connection:
        result = connection.execute(
            sql,
            {"schema": schema, "table": table, "column": column},
        ).scalar_one_or_none()

    if result is None:
        raise RuntimeError(f"Column not found: {schema}.{table}.{column}")

    return bool(result)


def apply_not_null_constraints(engine):
    print("\n--- NOT NULL CONSTRAINTS ---")

    for schema, table, column in NOT_NULL_COLUMNS:
        label = f"{schema}.{table}.{column}"

        if column_is_not_null(engine, schema, table, column):
            print(f"\n[SKIP ] {label} already NOT NULL")
            continue

        execute(
            engine,
            f"{label}: SET NOT NULL",
            f'ALTER TABLE "{schema}"."{table}" '
            f'ALTER COLUMN "{column}" SET NOT NULL;',
        )


def apply_check_constraints(engine):
    print("\n--- CHECK CONSTRAINTS ---")
    print("CHECK constraints are created NOT VALID; historical validation remains separate.")

    for schema, table, name, expression in CHECK_CONSTRAINTS:
        if constraint_exists(engine, schema, table, name):
            print(f"\n[SKIP ] {schema}.{table}.{name} already exists")
            continue

        sql = (
            f'ALTER TABLE "{schema}"."{table}" '
            f'ADD CONSTRAINT "{name}" '
            f'CHECK ({expression}) NOT VALID;'
        )

        execute(engine, f"{schema}.{table}.{name}", sql)


def apply_constraints(engine):
    apply_not_null_constraints(engine)
    apply_check_constraints(engine)

def inspect_model(engine):
    sql = text("""
        SELECT n.nspname AS schema_name, c.relname AS table_name,
               con.conname AS constraint_name, con.contype, con.convalidated
        FROM pg_constraint con
        JOIN pg_class c ON c.oid = con.conrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = ANY(:schemas)
          AND con.contype IN ('p','f','c')
        ORDER BY n.nspname, c.relname, con.contype, con.conname;
    """)

    with engine.connect() as connection:
        rows = connection.execute(
            sql,
            {"schemas": BTYT_SCHEMAS},
        ).mappings().all()

    pk = sum(r["contype"] == "p" for r in rows)
    fk = sum(r["contype"] == "f" for r in rows)
    ck = sum(r["contype"] == "c" for r in rows)

    print("\n" + "=" * 72)
    print("RELATIONAL MODEL INSPECTION")
    print("=" * 72)

    for r in rows:
        kind = {"p": "PK", "f": "FK", "c": "CHECK"}[r["contype"]]
        print(
            f'{r["schema_name"]}.{r["table_name"]:<38} '
            f'{kind:<6} {r["constraint_name"]:<52} '
            f'validated={r["convalidated"]}'
        )

    print(f"\nPrimary keys : {pk} / 23")
    print(f"Foreign keys : {fk} / 28")
    print(f"Check constraints : {ck} / {len(CHECK_CONSTRAINTS)}")

    not_null_applied = 0
    print("\nAudited NOT NULL columns:")

    for schema, table, column in NOT_NULL_COLUMNS:
        applied = column_is_not_null(engine, schema, table, column)
        not_null_applied += int(applied)
        status = "YES" if applied else "NO"
        print(f"  {schema}.{table}.{column:<35} {status}")

    print(
        f"\nAudited NOT NULL : "
        f"{not_null_applied} / {len(NOT_NULL_COLUMNS)}"
    )

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Apply approved BTYT PostgreSQL relational-model changes."
    )
    parser.add_argument("--types", action="store_true", help="Apply audited semantic type conversions.")
    parser.add_argument("--precision", action="store_true", help="Apply audited monetary precision conversions.")
    parser.add_argument("--pk", action="store_true", help="Create the 23 audited primary keys.")
    parser.add_argument("--fk", action="store_true", help="Create the 28 approved foreign keys as NOT VALID.")
    parser.add_argument("--constraints", action="store_true", help="Apply audited NOT NULL and CHECK constraints.")
    parser.add_argument("--inspect", action="store_true", help="Inspect current PK/FK/CHECK/NOT NULL state without modifying it.")
    parser.add_argument("--all", action="store_true", help="Apply types, precision, PKs, FKs and constraints in that order.")
    return parser.parse_args()


def main():
    args = parse_arguments()

    if not any([
        args.types,
        args.precision,
        args.pk,
        args.fk,
        args.constraints,
        args.inspect,
        args.all,
    ]):
        print("No phase selected. Nothing was modified.")
        print(
            "Use --types, --precision, --pk, --fk, "
            "--constraints, --inspect, or --all."
        )
        return

    engine = create_db_engine()

    try:
        verify_connection(engine)

        if args.all or args.types:
            apply_semantic_types(engine)

        if args.all or args.precision:
            apply_precision(engine)

        if args.all or args.pk:
            apply_primary_keys(engine)

        if args.all or args.fk:
            apply_foreign_keys(engine)

        if args.all or args.constraints:
            apply_constraints(engine)

        inspect_model(engine)

        print("\n" + "=" * 72)
        print("RELATIONAL MODEL APPLY PHASE COMPLETE")
        print("=" * 72)

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
