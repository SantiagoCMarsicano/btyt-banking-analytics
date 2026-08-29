from __future__ import annotations

"""
BTYT Banking Analytics
Deterministic branch master generator

Creates:
    data/processed/branches.csv

The 37-row branch network is intentionally fixed.
This script reproduces the canonical branch table exactly;
it does not randomly generate offices or alter the bank lore.
"""

from pathlib import Path
import pandas as pd

CURRENT_YEAR = 2026
ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "data" / "processed" / "branches.csv"

BRANCH_COLUMNS = [
    'branch_id',
    'branch_name',
    'branch_type',
    'branch_size',
    'status',
    'opening_year',
    'opening_reason',
    'closing_year',
    'closure_reason',
    'parent_branch_id',
    'department',
    'locality',
    'region',
    'latitude',
    'longitude',
]

BRANCHES = [
    {
        'branch_id': '001',
        'branch_name': 'Treinta y Tres',
        'branch_type': 'BRANCH',
        'branch_size': 'LARGE',
        'status': 'OPEN',
        'opening_year': '1969',
        'opening_reason': 'FOUNDING',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': None,
        'department': 'Treinta y Tres',
        'locality': 'Treinta y Tres',
        'region': 'EAST',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '002',
        'branch_name': 'Vergara',
        'branch_type': 'AGENCY',
        'branch_size': 'SMALL',
        'status': 'OPEN',
        'opening_year': '1974',
        'opening_reason': 'LOCAL_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': '001',
        'department': 'Treinta y Tres',
        'locality': 'Vergara',
        'region': 'EAST',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '003',
        'branch_name': 'José Pedro Varela',
        'branch_type': 'BRANCH',
        'branch_size': 'MEDIUM',
        'status': 'OPEN',
        'opening_year': '1974',
        'opening_reason': 'REGIONAL_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': None,
        'department': 'Lavalleja',
        'locality': 'José Pedro Varela',
        'region': 'EAST',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '004',
        'branch_name': 'La Charqueada',
        'branch_type': 'AGENCY',
        'branch_size': 'SMALL',
        'status': 'OPEN',
        'opening_year': '1978',
        'opening_reason': 'LOCAL_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': '001',
        'department': 'Treinta y Tres',
        'locality': 'La Charqueada',
        'region': 'EAST',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '005',
        'branch_name': 'Melo',
        'branch_type': 'BRANCH',
        'branch_size': 'LARGE',
        'status': 'OPEN',
        'opening_year': '1982',
        'opening_reason': 'REGIONAL_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': None,
        'department': 'Cerro Largo',
        'locality': 'Melo',
        'region': 'EAST',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '006',
        'branch_name': 'Cerro Chato',
        'branch_type': 'AGENCY',
        'branch_size': 'SMALL',
        'status': 'OPEN',
        'opening_year': '1983',
        'opening_reason': 'LOCAL_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': '001',
        'department': 'Treinta y Tres',
        'locality': 'Cerro Chato',
        'region': 'EAST',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '007',
        'branch_name': 'Santa Clara de Olimar',
        'branch_type': 'AGENCY',
        'branch_size': 'SMALL',
        'status': 'CLOSED',
        'opening_year': '1983',
        'opening_reason': 'LOCAL_EXPANSION',
        'closing_year': '2023',
        'closure_reason': 'NETWORK_OPTIMIZATION',
        'parent_branch_id': '001',
        'department': 'Treinta y Tres',
        'locality': 'Santa Clara de Olimar',
        'region': 'EAST',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '008',
        'branch_name': 'Rocha',
        'branch_type': 'BRANCH',
        'branch_size': 'MEDIUM',
        'status': 'OPEN',
        'opening_year': '1987',
        'opening_reason': 'REGIONAL_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': None,
        'department': 'Rocha',
        'locality': 'Rocha',
        'region': 'EAST',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '009',
        'branch_name': 'Chuy',
        'branch_type': 'AGENCY',
        'branch_size': 'SMALL',
        'status': 'OPEN',
        'opening_year': '1988',
        'opening_reason': 'BORDER_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': '008',
        'department': 'Rocha',
        'locality': 'Chuy',
        'region': 'EAST',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '010',
        'branch_name': 'Río Branco',
        'branch_type': 'AGENCY',
        'branch_size': 'SMALL',
        'status': 'OPEN',
        'opening_year': '1990',
        'opening_reason': 'BORDER_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': '005',
        'department': 'Cerro Largo',
        'locality': 'Río Branco',
        'region': 'EAST',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '011',
        'branch_name': 'Aceguá',
        'branch_type': 'AGENCY',
        'branch_size': 'SMALL',
        'status': 'OPEN',
        'opening_year': '1990',
        'opening_reason': 'BORDER_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': '005',
        'department': 'Cerro Largo',
        'locality': 'Aceguá',
        'region': 'EAST',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '012',
        'branch_name': 'Minas',
        'branch_type': 'BRANCH',
        'branch_size': 'MEDIUM',
        'status': 'OPEN',
        'opening_year': '1994',
        'opening_reason': 'REGIONAL_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': None,
        'department': 'Lavalleja',
        'locality': 'Minas',
        'region': 'EAST',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '013',
        'branch_name': 'Maldonado',
        'branch_type': 'BRANCH',
        'branch_size': 'LARGE',
        'status': 'OPEN',
        'opening_year': '1997',
        'opening_reason': 'REGIONAL_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': None,
        'department': 'Maldonado',
        'locality': 'Maldonado',
        'region': 'EAST',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '014',
        'branch_name': 'Piriápolis',
        'branch_type': 'AGENCY',
        'branch_size': 'SMALL',
        'status': 'CLOSED',
        'opening_year': '1998',
        'opening_reason': 'REGIONAL_EXPANSION',
        'closing_year': '2025',
        'closure_reason': 'POOR_PERFORMANCE',
        'parent_branch_id': '013',
        'department': 'Maldonado',
        'locality': 'Piriápolis',
        'region': 'EAST',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '015',
        'branch_name': 'Punta del Este',
        'branch_type': 'AGENCY',
        'branch_size': 'MEDIUM',
        'status': 'OPEN',
        'opening_year': '1999',
        'opening_reason': 'REGIONAL_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': '013',
        'department': 'Maldonado',
        'locality': 'Punta del Este',
        'region': 'EAST',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '016',
        'branch_name': 'La Paloma',
        'branch_type': 'AGENCY',
        'branch_size': 'SMALL',
        'status': 'OPEN',
        'opening_year': '1999',
        'opening_reason': 'REGIONAL_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': '008',
        'department': 'Rocha',
        'locality': 'La Paloma',
        'region': 'EAST',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '017',
        'branch_name': 'Montevideo Centro',
        'branch_type': 'BRANCH',
        'branch_size': 'LARGE',
        'status': 'OPEN',
        'opening_year': '2005',
        'opening_reason': 'METROPOLITAN_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': None,
        'department': 'Montevideo',
        'locality': 'Montevideo',
        'region': 'METROPOLITAN',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '018',
        'branch_name': 'Pando',
        'branch_type': 'AGENCY',
        'branch_size': 'SMALL',
        'status': 'OPEN',
        'opening_year': '2006',
        'opening_reason': 'METROPOLITAN_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': '017',
        'department': 'Canelones',
        'locality': 'Pando',
        'region': 'METROPOLITAN',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '019',
        'branch_name': 'WTC',
        'branch_type': 'AGENCY',
        'branch_size': 'MEDIUM',
        'status': 'OPEN',
        'opening_year': '2006',
        'opening_reason': 'METROPOLITAN_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': '017',
        'department': 'Montevideo',
        'locality': 'Montevideo',
        'region': 'METROPOLITAN',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '020',
        'branch_name': 'Canelones',
        'branch_type': 'BRANCH',
        'branch_size': 'MEDIUM',
        'status': 'OPEN',
        'opening_year': '2008',
        'opening_reason': 'METROPOLITAN_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': None,
        'department': 'Canelones',
        'locality': 'Canelones',
        'region': 'METROPOLITAN',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '021',
        'branch_name': 'Durazno',
        'branch_type': 'BRANCH',
        'branch_size': 'MEDIUM',
        'status': 'OPEN',
        'opening_year': '2009',
        'opening_reason': 'NATIONAL_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': None,
        'department': 'Durazno',
        'locality': 'Durazno',
        'region': 'CENTRAL',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '022',
        'branch_name': 'Rivera',
        'branch_type': 'BRANCH',
        'branch_size': 'MEDIUM',
        'status': 'OPEN',
        'opening_year': '2010',
        'opening_reason': 'NATIONAL_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': None,
        'department': 'Rivera',
        'locality': 'Rivera',
        'region': 'NORTH',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '023',
        'branch_name': 'Las Piedras',
        'branch_type': 'AGENCY',
        'branch_size': 'MEDIUM',
        'status': 'OPEN',
        'opening_year': '2010',
        'opening_reason': 'METROPOLITAN_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': '020',
        'department': 'Canelones',
        'locality': 'Las Piedras',
        'region': 'METROPOLITAN',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '024',
        'branch_name': 'Tacuarembó',
        'branch_type': 'BRANCH',
        'branch_size': 'MEDIUM',
        'status': 'OPEN',
        'opening_year': '2010',
        'opening_reason': 'NATIONAL_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': None,
        'department': 'Tacuarembó',
        'locality': 'Tacuarembó',
        'region': 'CENTRAL',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '025',
        'branch_name': 'Prado',
        'branch_type': 'AGENCY',
        'branch_size': 'SMALL',
        'status': 'OPEN',
        'opening_year': '2011',
        'opening_reason': 'METROPOLITAN_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': '017',
        'department': 'Montevideo',
        'locality': 'Montevideo',
        'region': 'METROPOLITAN',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '026',
        'branch_name': 'Carrasco',
        'branch_type': 'AGENCY',
        'branch_size': 'SMALL',
        'status': 'OPEN',
        'opening_year': '2013',
        'opening_reason': 'METROPOLITAN_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': '017',
        'department': 'Montevideo',
        'locality': 'Montevideo',
        'region': 'METROPOLITAN',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '027',
        'branch_name': 'Colonia del Sacramento',
        'branch_type': 'BRANCH',
        'branch_size': 'MEDIUM',
        'status': 'OPEN',
        'opening_year': '2014',
        'opening_reason': 'NATIONAL_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': None,
        'department': 'Colonia',
        'locality': 'Colonia del Sacramento',
        'region': 'LITTORAL',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '028',
        'branch_name': 'Ciudad de la Costa',
        'branch_type': 'AGENCY',
        'branch_size': 'SMALL',
        'status': 'OPEN',
        'opening_year': '2015',
        'opening_reason': 'METROPOLITAN_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': '017',
        'department': 'Canelones',
        'locality': 'Ciudad de la Costa',
        'region': 'METROPOLITAN',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '029',
        'branch_name': 'Florida',
        'branch_type': 'BRANCH',
        'branch_size': 'MEDIUM',
        'status': 'OPEN',
        'opening_year': '2015',
        'opening_reason': 'NATIONAL_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': None,
        'department': 'Florida',
        'locality': 'Florida',
        'region': 'CENTRAL',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '030',
        'branch_name': 'San José de Mayo',
        'branch_type': 'BRANCH',
        'branch_size': 'MEDIUM',
        'status': 'OPEN',
        'opening_year': '2016',
        'opening_reason': 'NATIONAL_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': None,
        'department': 'San José',
        'locality': 'San José de Mayo',
        'region': 'METROPOLITAN',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '031',
        'branch_name': 'Mercedes',
        'branch_type': 'BRANCH',
        'branch_size': 'MEDIUM',
        'status': 'OPEN',
        'opening_year': '2016',
        'opening_reason': 'NATIONAL_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': None,
        'department': 'Soriano',
        'locality': 'Mercedes',
        'region': 'LITTORAL',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '032',
        'branch_name': 'Salto',
        'branch_type': 'BRANCH',
        'branch_size': 'MEDIUM',
        'status': 'OPEN',
        'opening_year': '2017',
        'opening_reason': 'NATIONAL_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': None,
        'department': 'Salto',
        'locality': 'Salto',
        'region': 'NORTH',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '033',
        'branch_name': 'Trinidad',
        'branch_type': 'AGENCY',
        'branch_size': 'MEDIUM',
        'status': 'OPEN',
        'opening_year': '2017',
        'opening_reason': 'NATIONAL_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': '021',
        'department': 'Flores',
        'locality': 'Trinidad',
        'region': 'CENTRAL',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '034',
        'branch_name': 'Paysandú',
        'branch_type': 'BRANCH',
        'branch_size': 'MEDIUM',
        'status': 'OPEN',
        'opening_year': '2018',
        'opening_reason': 'NATIONAL_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': None,
        'department': 'Paysandú',
        'locality': 'Paysandú',
        'region': 'LITTORAL',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '035',
        'branch_name': 'Fray Bentos',
        'branch_type': 'BRANCH',
        'branch_size': 'MEDIUM',
        'status': 'OPEN',
        'opening_year': '2019',
        'opening_reason': 'NATIONAL_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': None,
        'department': 'Río Negro',
        'locality': 'Fray Bentos',
        'region': 'LITTORAL',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '036',
        'branch_name': 'Artigas',
        'branch_type': 'BRANCH',
        'branch_size': 'SMALL',
        'status': 'OPEN',
        'opening_year': '2019',
        'opening_reason': 'NATIONAL_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': None,
        'department': 'Artigas',
        'locality': 'Artigas',
        'region': 'NORTH',
        'latitude': None,
        'longitude': None,
    },
    {
        'branch_id': '037',
        'branch_name': 'Colón',
        'branch_type': 'AGENCY',
        'branch_size': 'SMALL',
        'status': 'OPEN',
        'opening_year': '2019',
        'opening_reason': 'METROPOLITAN_EXPANSION',
        'closing_year': None,
        'closure_reason': None,
        'parent_branch_id': '017',
        'department': 'Montevideo',
        'locality': 'Montevideo',
        'region': 'METROPOLITAN',
        'latitude': None,
        'longitude': None,
    },
]


def build_branches() -> pd.DataFrame:
    df = pd.DataFrame(BRANCHES, columns=BRANCH_COLUMNS)

    # Preserve branch IDs and parent IDs as 3-character strings.
    df["branch_id"] = df["branch_id"].astype(str).str.zfill(3)
    df["parent_branch_id"] = df["parent_branch_id"].apply(
        lambda x: str(x).zfill(3) if pd.notna(x) and x not in ("", "None") else None
    )

    # Numeric year fields.
    df["opening_year"] = pd.to_numeric(df["opening_year"], errors="raise").astype(int)
    df["closing_year"] = pd.to_numeric(df["closing_year"], errors="coerce").astype("Int64")

    # Coordinates remain intentionally blank because the canonical source table leaves them blank.
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    return df


def validate_branches(df: pd.DataFrame) -> None:
    errors = []

    if list(df.columns) != BRANCH_COLUMNS:
        errors.append(f"Column mismatch: {list(df.columns)}")

    if len(df) != 37:
        errors.append(f"Expected 37 branches, found {len(df)}")

    expected_ids = [f"{i:03d}" for i in range(1, 38)]
    if df["branch_id"].tolist() != expected_ids:
        errors.append("branch_id sequence must be exactly 001-037 in canonical order.")

    if df["branch_id"].duplicated().any():
        errors.append("Duplicate branch_id values.")

    if not df["branch_type"].isin(["BRANCH", "AGENCY"]).all():
        errors.append("Invalid branch_type.")

    if not df["branch_size"].isin(["SMALL", "MEDIUM", "LARGE"]).all():
        errors.append("Invalid branch_size.")

    if not df["status"].isin(["OPEN", "CLOSED"]).all():
        errors.append("Invalid status.")

    if (df["opening_year"] > CURRENT_YEAR).any():
        errors.append("opening_year after 2026.")

    closed = df["status"].eq("CLOSED")
    opened = df["status"].eq("OPEN")

    if df.loc[closed, "closing_year"].isna().any():
        errors.append("CLOSED branch without closing_year.")

    if df.loc[closed, "closure_reason"].isna().any():
        errors.append("CLOSED branch without closure_reason.")

    if df.loc[opened, "closing_year"].notna().any():
        errors.append("OPEN branch with closing_year.")

    if df.loc[opened, "closure_reason"].notna().any():
        errors.append("OPEN branch with closure_reason.")

    closed_rows = df.loc[closed]
    if not closed_rows.empty:
        bad = closed_rows["closing_year"].astype(int) < closed_rows["opening_year"]
        if bad.any():
            errors.append("closing_year before opening_year.")

    valid_ids = set(df["branch_id"])
    parents = df["parent_branch_id"].dropna()
    if not set(parents).issubset(valid_ids):
        errors.append("Invalid parent_branch_id foreign key.")

    self_parent = df["parent_branch_id"].eq(df["branch_id"])
    if self_parent.any():
        errors.append("A branch cannot be its own parent.")

    # Canonical hierarchy: BRANCH rows have no parent; AGENCY rows have one.
    if df.loc[df["branch_type"].eq("BRANCH"), "parent_branch_id"].notna().any():
        errors.append("BRANCH row with parent_branch_id.")
    if df.loc[df["branch_type"].eq("AGENCY"), "parent_branch_id"].isna().any():
        errors.append("AGENCY row without parent_branch_id.")

    if errors:
        print("\nVALIDATION: FAIL")
        for error in errors:
            print(" -", error)
        raise AssertionError("Branch validation failed.")

    print("\nVALIDATION: PASS")


def audit(df: pd.DataFrame) -> None:
    print("\n" + "=" * 72)
    print("BTYT BRANCHES AUDIT")
    print("=" * 72)
    print(f"\nBranches: {len(df)}")
    print("\nBranch type:")
    print(df["branch_type"].value_counts().sort_index())
    print("\nBranch size:")
    print(df["branch_size"].value_counts().sort_index())
    print("\nStatus:")
    print(df["status"].value_counts().sort_index())
    print("\nRegion:")
    print(df["region"].value_counts().sort_index())
    print("\nClosed branches:")
    print(df.loc[df["status"].eq("CLOSED"), ["branch_id", "branch_name", "closing_year", "closure_reason"]].to_string(index=False))


def main() -> None:
    branches = build_branches()
    validate_branches(branches)
    audit(branches)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    branches.to_csv(OUTPUT_PATH, index=False)

    print(f"\nSaved: {OUTPUT_PATH}")
    print(f"Shape: {branches.shape}")


if __name__ == "__main__":
    main()
