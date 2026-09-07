from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.core.paths import GENERATED_CORE_DIR, GENERATED_WORLD_DIR


# =============================================================================
# BTYT FINANCIAL INSTITUTIONS GENERATOR
# =============================================================================

OUTPUT_PATH = GENERATED_WORLD_DIR / "financial_institutions.csv"

INSTITUTION_TYPE_BANK = "BANK"
INSTITUTION_TYPE_IEDE = "ELECTRONIC_MONEY_ISSUER"

COUNTRY_URUGUAY = "Uruguay"


# =============================================================================
# ELECTRONIC MONEY INSTITUTIONS
# =============================================================================
#
# These institutions are modeled as financial counterparties but do not
# participate in the BTYT banking-market-share model.
#
# active_from represents the date from which the institution/product is
# considered available to the BTYT transaction universe.
#
# Historical dates:
# - Midinero / Findarin S.A.: 2015-04-15
# - Prex / Econstar S.A.: 2015-09-23
# - OCA Blue / OCA Dinero Electrónico S.A.: 2020-07-07
# - Mercado Pago Uruguay: 2023-07-11
#
# Mercado Pago's modeled start date corresponds to the effective authorization
# relevant to general electronic-money issuance within the BTYT use case.
# =============================================================================

ELECTRONIC_MONEY_INSTITUTIONS = [
    {
        "institution_id": "IEDE_PREX",
        "institution_name": "Prex",
        "legal_name": "Econstar S.A.",
        "institution_type": INSTITUTION_TYPE_IEDE,
        "country": COUNTRY_URUGUAY,
        "domestic_flag": True,
        "bank_id": None,
        "active_from": "2015-09-23",
        "active_to": None,
    },
    {
        "institution_id": "IEDE_MIDINERO",
        "institution_name": "Midinero",
        "legal_name": "Findarin S.A.",
        "institution_type": INSTITUTION_TYPE_IEDE,
        "country": COUNTRY_URUGUAY,
        "domestic_flag": True,
        "bank_id": None,
        "active_from": "2015-04-15",
        "active_to": None,
    },
    {
        "institution_id": "IEDE_OCA_BLUE",
        "institution_name": "OCA Blue",
        "legal_name": "OCA Dinero Electrónico S.A.",
        "institution_type": INSTITUTION_TYPE_IEDE,
        "country": COUNTRY_URUGUAY,
        "domestic_flag": True,
        "bank_id": None,
        "active_from": "2020-07-07",
        "active_to": None,
    },
    {
        "institution_id": "IEDE_MERCADO_PAGO",
        "institution_name": "Mercado Pago Uruguay",
        "legal_name": "MercadoPago Uruguay S.R.L.",
        "institution_type": INSTITUTION_TYPE_IEDE,
        "country": COUNTRY_URUGUAY,
        "domestic_flag": True,
        "bank_id": None,
        "active_from": "2023-07-11",
        "active_to": None,
    },
]


# =============================================================================
# SOURCE LOADING
# =============================================================================

def find_banks_path() -> Path:
    """
    Locate the canonical BTYT banks dimension.

    The canonical location is data/generated/core/banks.csv.
    Additional candidates are retained only as defensive compatibility paths.
    """
    candidates = [
        GENERATED_CORE_DIR / "banks.csv",
        GENERATED_WORLD_DIR / "banks.csv",
        GENERATED_WORLD_DIR.parent / "banks.csv",
    ]

    for path in candidates:
        if path.exists():
            return path

    checked_paths = "\n".join(
        f"  - {path}"
        for path in candidates
    )

    raise FileNotFoundError(
        "Could not locate banks.csv. Checked:\n"
        f"{checked_paths}"
    )


# =============================================================================
# BANK INSTITUTIONS
# =============================================================================

def make_bank_institution_id(bank_id: str) -> str:
    """
    Create a stable semantic institution identifier for a bank.
    """
    return f"BANK_{str(bank_id).strip()}"


def build_bank_institutions(
    banks: pd.DataFrame,
) -> pd.DataFrame:
    """
    Convert the existing BTYT bank dimension into financial-institution rows.

    banks.csv remains the canonical source for bank-specific information.

    Domestic/international classification is derived exclusively from
    operating_country. bank_scope is deliberately not used because it has
    a different semantic role in the banking model.
    """
    required_columns = {
        "bank_id",
        "bank_name",
        "operating_country",
    }

    missing_columns = (
        required_columns - set(banks.columns)
    )

    if missing_columns:
        raise ValueError(
            "banks.csv is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    rows = []

    for row in banks.itertuples(index=False):
        bank_id = str(row.bank_id).strip()
        bank_name = str(row.bank_name).strip()
        country = str(row.operating_country).strip()

        if not bank_id:
            raise ValueError(
                "banks.csv contains an empty bank_id."
            )

        if not bank_name:
            raise ValueError(
                f"Bank {bank_id} contains an empty bank_name."
            )

        if not country:
            raise ValueError(
                f"Bank {bank_id} contains an empty operating_country."
            )

        domestic_flag = (
            country.casefold()
            == COUNTRY_URUGUAY.casefold()
        )

        rows.append(
            {
                "institution_id": make_bank_institution_id(
                    bank_id
                ),
                "institution_name": bank_name,
                "legal_name": bank_name,
                "institution_type": INSTITUTION_TYPE_BANK,
                "country": country,
                "domestic_flag": domestic_flag,
                "bank_id": bank_id,
                "active_from": None,
                "active_to": None,
            }
        )

    return pd.DataFrame(rows)


# =============================================================================
# ELECTRONIC MONEY INSTITUTIONS
# =============================================================================

def build_electronic_money_institutions() -> pd.DataFrame:
    """
    Build the explicitly modeled Uruguayan electronic-money institutions.
    """
    return pd.DataFrame(
        ELECTRONIC_MONEY_INSTITUTIONS
    )


# =============================================================================
# VALIDATION
# =============================================================================

def validate_financial_institutions(
    institutions: pd.DataFrame,
    banks: pd.DataFrame,
) -> None:
    """
    Validate structural and referential integrity of the institution dimension.
    """
    required_columns = [
        "institution_id",
        "institution_name",
        "legal_name",
        "institution_type",
        "country",
        "domestic_flag",
        "bank_id",
        "active_from",
        "active_to",
    ]

    missing_columns = (
        set(required_columns)
        - set(institutions.columns)
    )

    if missing_columns:
        raise ValueError(
            "Financial institution dimension is missing columns: "
            + ", ".join(sorted(missing_columns))
        )

    if institutions.empty:
        raise ValueError(
            "Financial institution dimension is empty."
        )

    # -------------------------------------------------------------------------
    # Primary key
    # -------------------------------------------------------------------------

    if institutions["institution_id"].isna().any():
        raise ValueError(
            "institution_id contains null values."
        )

    if institutions["institution_id"].duplicated().any():
        duplicates = (
            institutions.loc[
                institutions["institution_id"]
                .duplicated(keep=False),
                "institution_id",
            ]
            .astype(str)
            .tolist()
        )

        raise ValueError(
            "Duplicate institution_id values detected: "
            f"{duplicates}"
        )

    # -------------------------------------------------------------------------
    # Required descriptive fields
    # -------------------------------------------------------------------------

    for column in [
        "institution_name",
        "legal_name",
        "institution_type",
        "country",
    ]:
        if institutions[column].isna().any():
            raise ValueError(
                f"{column} contains null values."
            )

        empty_mask = (
            institutions[column]
            .astype(str)
            .str.strip()
            .eq("")
        )

        if empty_mask.any():
            raise ValueError(
                f"{column} contains empty values."
            )

    # -------------------------------------------------------------------------
    # Institution types
    # -------------------------------------------------------------------------

    valid_types = {
        INSTITUTION_TYPE_BANK,
        INSTITUTION_TYPE_IEDE,
    }

    invalid_types = (
        set(
            institutions[
                "institution_type"
            ].dropna()
        )
        - valid_types
    )

    if invalid_types:
        raise ValueError(
            "Invalid institution types detected: "
            + ", ".join(sorted(invalid_types))
        )

    bank_mask = (
        institutions["institution_type"]
        == INSTITUTION_TYPE_BANK
    )

    iede_mask = (
        institutions["institution_type"]
        == INSTITUTION_TYPE_IEDE
    )

    # -------------------------------------------------------------------------
    # Bank relationships
    # -------------------------------------------------------------------------

    if institutions.loc[
        bank_mask,
        "bank_id",
    ].isna().any():
        raise ValueError(
            "Every BANK institution must have a non-null bank_id."
        )

    if institutions.loc[
        iede_mask,
        "bank_id",
    ].notna().any():
        raise ValueError(
            "Electronic money issuers must not have a bank_id."
        )

    realized_bank_ids = set(
        institutions.loc[
            bank_mask,
            "bank_id",
        ]
        .astype(str)
        .str.strip()
    )

    source_bank_ids = set(
        banks["bank_id"]
        .astype(str)
        .str.strip()
    )

    if realized_bank_ids != source_bank_ids:
        missing_bank_ids = (
            source_bank_ids - realized_bank_ids
        )

        extra_bank_ids = (
            realized_bank_ids - source_bank_ids
        )

        raise ValueError(
            "Bank coverage mismatch between banks.csv "
            "and financial_institutions.\n"
            f"Missing bank IDs: {sorted(missing_bank_ids)}\n"
            f"Unexpected bank IDs: {sorted(extra_bank_ids)}"
        )

    bank_ids = (
        institutions.loc[
            bank_mask,
            "bank_id",
        ]
        .astype(str)
        .str.strip()
    )

    if bank_ids.duplicated().any():
        duplicates = (
            bank_ids[
                bank_ids.duplicated(
                    keep=False
                )
            ]
            .tolist()
        )

        raise ValueError(
            "A bank_id maps to more than one financial institution: "
            f"{duplicates}"
        )

    # -------------------------------------------------------------------------
    # Source bank country consistency
    # -------------------------------------------------------------------------

    if "operating_country" not in banks.columns:
        raise ValueError(
            "banks.csv must contain operating_country."
        )

    source_country = (
        banks[
            [
                "bank_id",
                "operating_country",
            ]
        ]
        .copy()
    )

    source_country["bank_id"] = (
        source_country["bank_id"]
        .astype(str)
        .str.strip()
    )

    source_country["operating_country"] = (
        source_country[
            "operating_country"
        ]
        .astype(str)
        .str.strip()
    )

    if (
        source_country[
            "operating_country"
        ].eq("").any()
    ):
        bad_rows = source_country.loc[
            source_country[
                "operating_country"
            ].eq(""),
            [
                "bank_id",
                "operating_country",
            ],
        ]

        raise ValueError(
            "banks.csv contains empty operating_country values:\n"
            f"{bad_rows.to_string(index=False)}"
        )

    # -------------------------------------------------------------------------
    # Electronic-money institutions
    # -------------------------------------------------------------------------

    expected_iede_ids = {
        institution["institution_id"]
        for institution
        in ELECTRONIC_MONEY_INSTITUTIONS
    }

    realized_iede_ids = set(
        institutions.loc[
            iede_mask,
            "institution_id",
        ].astype(str)
    )

    if realized_iede_ids != expected_iede_ids:
        raise ValueError(
            "Electronic-money institution realization does not match "
            "the configured BTYT institution set."
        )

    if not institutions.loc[
        iede_mask,
        "domestic_flag",
    ].all():
        raise ValueError(
            "All currently modeled electronic-money institutions "
            "must be domestic."
        )

    # -------------------------------------------------------------------------
    # Domestic flag
    # -------------------------------------------------------------------------

    expected_domestic = (
        institutions["country"]
        .astype(str)
        .str.casefold()
        .eq(
            COUNTRY_URUGUAY.casefold()
        )
    )

    actual_domestic = (
        institutions[
            "domestic_flag"
        ].astype(bool)
    )

    if not expected_domestic.equals(
        actual_domestic
    ):
        inconsistent_rows = (
            institutions.loc[
                expected_domestic
                != actual_domestic,
                [
                    "institution_id",
                    "institution_name",
                    "country",
                    "domestic_flag",
                ],
            ]
        )

        raise ValueError(
            "domestic_flag is inconsistent with country:\n"
            f"{inconsistent_rows.to_string(index=False)}"
        )

    # -------------------------------------------------------------------------
    # Temporal fields
    # -------------------------------------------------------------------------

    for column in [
        "active_from",
        "active_to",
    ]:
        non_null = (
            institutions[column]
            .dropna()
        )

        if not non_null.empty:
            parsed = pd.to_datetime(
                non_null,
                errors="coerce",
            )

            if parsed.isna().any():
                raise ValueError(
                    f"{column} contains invalid dates."
                )

    both_dates = (
        institutions[
            "active_from"
        ].notna()
        & institutions[
            "active_to"
        ].notna()
    )

    if both_dates.any():
        active_from = pd.to_datetime(
            institutions.loc[
                both_dates,
                "active_from",
            ]
        )

        active_to = pd.to_datetime(
            institutions.loc[
                both_dates,
                "active_to",
            ]
        )

        if (
            active_to
            < active_from
        ).any():
            raise ValueError(
                "active_to cannot precede active_from."
            )


# =============================================================================
# SUMMARY
# =============================================================================

def print_summary(
    institutions: pd.DataFrame,
    banks_path: Path,
) -> None:
    bank_mask = (
        institutions["institution_type"]
        == INSTITUTION_TYPE_BANK
    )

    iede_mask = (
        institutions["institution_type"]
        == INSTITUTION_TYPE_IEDE
    )

    bank_count = int(
        bank_mask.sum()
    )

    iede_count = int(
        iede_mask.sum()
    )

    domestic_count = int(
        institutions[
            "domestic_flag"
        ].sum()
    )

    international_count = (
        len(institutions)
        - domestic_count
    )

    domestic_bank_count = int(
        (
            bank_mask
            & institutions[
                "domestic_flag"
            ]
        ).sum()
    )

    international_bank_count = int(
        (
            bank_mask
            & ~institutions[
                "domestic_flag"
            ]
        ).sum()
    )

    print("=" * 84)
    print(
        "BTYT FINANCIAL INSTITUTIONS"
    )
    print("=" * 84)

    print(
        f"Bank source:            "
        f"{banks_path}"
    )

    print(
        f"Output:                 "
        f"{OUTPUT_PATH}"
    )

    print()

    print(
        f"Institutions:           "
        f"{len(institutions):,}"
    )

    print(
        f"Banks:                  "
        f"{bank_count:,}"
    )

    print(
        f"  Domestic banks:       "
        f"{domestic_bank_count:,}"
    )

    print(
        f"  International banks:  "
        f"{international_bank_count:,}"
    )

    print(
        f"Electronic money:       "
        f"{iede_count:,}"
    )

    print(
        f"Domestic total:         "
        f"{domestic_count:,}"
    )

    print(
        f"International total:    "
        f"{international_count:,}"
    )

    print()

    print(
        "Electronic-money institutions:"
    )

    iede = institutions.loc[
        iede_mask
    ]

    for row in iede.itertuples(
        index=False
    ):
        active_from = (
            row.active_from
            if pd.notna(row.active_from)
            else "OPEN"
        )

        active_to = (
            row.active_to
            if pd.notna(row.active_to)
            else "OPEN"
        )

        print(
            f"  "
            f"{row.institution_id:<24}"
            f"{row.institution_name:<26}"
            f"{active_from} -> {active_to}"
        )

    print()

    print(
        "International banks:"
    )

    international_banks = (
        institutions.loc[
            bank_mask
            & ~institutions[
                "domestic_flag"
            ]
        ]
    )

    if international_banks.empty:
        print("  None")
    else:
        for row in (
            international_banks
            .itertuples(index=False)
        ):
            print(
                f"  "
                f"{row.institution_id:<24}"
                f"{row.institution_name:<26}"
                f"{row.country}"
            )

    print()

    print(
        "VALIDATION: PASS"
    )

    print("=" * 84)


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    banks_path = find_banks_path()

    banks = pd.read_csv(
        banks_path,
        dtype={
            "bank_id": str,
        },
    )

    bank_institutions = (
        build_bank_institutions(
            banks
        )
    )

    electronic_money_institutions = (
        build_electronic_money_institutions()
    )

    institutions = pd.concat(
        [
            bank_institutions,
            electronic_money_institutions,
        ],
        ignore_index=True,
    )

    institutions = institutions[
        [
            "institution_id",
            "institution_name",
            "legal_name",
            "institution_type",
            "country",
            "domestic_flag",
            "bank_id",
            "active_from",
            "active_to",
        ]
    ].copy()

    validate_financial_institutions(
        institutions,
        banks,
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    institutions.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8",
    )

    print_summary(
        institutions,
        banks_path,
    )


if __name__ == "__main__":
    main()