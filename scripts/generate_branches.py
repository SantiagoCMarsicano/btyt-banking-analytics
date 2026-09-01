from __future__ import annotations

"""
BTYT Banking Analytics
Dynamic branch-network generator — V2.1.0

Creates:
    data/generated/branches.csv
    data/interim/branch_yearly_state.csv

V2.1.0 redesign:
    - The 37-office network remains structurally canonical.
    - Every office belongs to an explicit structural closure-risk group.
    - Every office has an explicit neutral six-year closure-risk anchor.
    - These anchors are not final probabilities. Annual realized hazards also
      depend on persistent commercial, balance, transaction, credit, cost,
      digital, network, operational, and macro conditions.
    - The latent annual branch state is saved so downstream generators can
      reproduce the same economic deterioration in customers, accounts,
      balances, transactions, loans, cards, and campaigns.
    - Closure outcomes are stochastic: weak branches may survive and healthy
      branches may rarely close.
    - No branch is hard-coded to close.
    - Zero closures is a normal possible outcome.
    - Closure saturation strongly reduces the probability of additional
      closures after the first and second realized closure.
    - A hard safety cap prevents more than three branch closures in one world.
    - Treinta y Tres remains exceptionally protected with a neutral six-year
      structural closure probability of approximately 0.006%.

All generated outcomes are synthetic.
All code and comments are intentionally written in English.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


# =============================================================================
# PROJECT PATHS
# =============================================================================

CURRENT_YEAR = 2026
OBSERVATION_START_YEAR = 2021
YEARS = tuple(range(OBSERVATION_START_YEAR, CURRENT_YEAR + 1))

ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = ROOT / "data" / "generated"
INTERIM_DIR = ROOT / "data" / "interim"

OUTPUT_PATH = GENERATED_DIR / "branches.csv"
MACRO_PATH = GENERATED_DIR / "bank_macro_environment.csv"
STATE_PATH = INTERIM_DIR / "branch_yearly_state.csv"


# =============================================================================
# WORLD CONFIGURATION
# =============================================================================

PRODUCTION_BRANCH_WORLD_SEED = 20260901

RNG_STREAM_STATE = 101
RNG_STREAM_LOCAL_SHOCK = 202
RNG_STREAM_CLOSURE_DRAW = 303
RNG_STREAM_REASON = 404

MAX_WORLD_CLOSURES = 3

# After one closure, management becomes substantially less willing to close
# another office in the same 2021-2026 planning window. The third closure is
# possible but intentionally exceptional.
CLOSURE_SATURATION_MULTIPLIER = {
    0: 1.00,
    1: 0.32,
    2: 0.06,
    3: 0.00,
}

# These are neutral structural probabilities for the complete 2021-2026
# observation window. They are converted internally to neutral annual hazards.
# They encode relative strategic vulnerability, not predetermined outcomes.
STRUCTURAL_SIX_YEAR_CLOSURE_PROB = {
    # A — CORE
    "001": 0.00006,  # Treinta y Tres
    "017": 0.00150,  # Montevideo Centro

    # B — STRATEGIC
    "005": 0.0060,   # Melo
    "008": 0.0110,   # Rocha
    "012": 0.0120,   # Minas
    "013": 0.0060,   # Maldonado
    "015": 0.0100,   # Punta del Este
    "019": 0.0090,   # WTC
    "020": 0.0100,   # Canelones
    "022": 0.0120,   # Rivera
    "024": 0.0130,   # Tacuarembo
    "027": 0.0100,   # Colonia del Sacramento
    "031": 0.0110,   # Mercedes
    "032": 0.0080,   # Salto
    "034": 0.0090,   # Paysandu

    # C — STANDARD
    "003": 0.0280,   # Jose Pedro Varela
    "010": 0.0450,   # Rio Branco
    "018": 0.0500,   # Pando
    "021": 0.0300,   # Durazno
    "023": 0.0420,   # Las Piedras
    "025": 0.0480,   # Prado
    "026": 0.0350,   # Carrasco
    "028": 0.0450,   # Ciudad de la Costa
    "029": 0.0300,   # Florida
    "030": 0.0280,   # San Jose de Mayo
    "033": 0.0380,   # Trinidad
    "035": 0.0320,   # Fray Bentos
    "036": 0.0400,   # Artigas

    # D — VULNERABLE
    "002": 0.0750,   # Vergara
    "004": 0.0950,   # La Charqueada
    "006": 0.0900,   # Cerro Chato
    "007": 0.1200,   # Santa Clara de Olimar
    "009": 0.0850,   # Chuy
    "011": 0.1000,   # Acegua
    "014": 0.1100,   # Piriapolis
    "016": 0.0950,   # La Paloma
    "037": 0.0800,   # Colon
}

RISK_GROUP = {
    "001": "A_CORE",
    "017": "A_CORE",

    "005": "B_STRATEGIC",
    "008": "B_STRATEGIC",
    "012": "B_STRATEGIC",
    "013": "B_STRATEGIC",
    "015": "B_STRATEGIC",
    "019": "B_STRATEGIC",
    "020": "B_STRATEGIC",
    "022": "B_STRATEGIC",
    "024": "B_STRATEGIC",
    "027": "B_STRATEGIC",
    "031": "B_STRATEGIC",
    "032": "B_STRATEGIC",
    "034": "B_STRATEGIC",

    "003": "C_STANDARD",
    "010": "C_STANDARD",
    "018": "C_STANDARD",
    "021": "C_STANDARD",
    "023": "C_STANDARD",
    "025": "C_STANDARD",
    "026": "C_STANDARD",
    "028": "C_STANDARD",
    "029": "C_STANDARD",
    "030": "C_STANDARD",
    "033": "C_STANDARD",
    "035": "C_STANDARD",
    "036": "C_STANDARD",

    "002": "D_VULNERABLE",
    "004": "D_VULNERABLE",
    "006": "D_VULNERABLE",
    "007": "D_VULNERABLE",
    "009": "D_VULNERABLE",
    "011": "D_VULNERABLE",
    "014": "D_VULNERABLE",
    "016": "D_VULNERABLE",
    "037": "D_VULNERABLE",
}

# Persistent latent state parameters.
STATE_PERSISTENCE = 0.68
STATE_INNOVATION_SD = 0.42
STATE_CLIP = 2.75

# Closure-pressure coefficients. Positive values represent deterioration.
PRESSURE_WEIGHTS = {
    "customer_pressure": 0.15,
    "deposit_pressure": 0.14,
    "transaction_pressure": 0.17,
    "credit_pressure": 0.12,
    "cost_pressure": 0.15,
    "digital_substitution": 0.12,
    "network_overlap": 0.08,
    "operational_pressure": 0.07,
}

HAZARD_PRESSURE_SCALE = 0.72

# Local disruptions are uncommon and only change probabilities; they never
# mechanically close an office.
LOCAL_SHOCK_BASE_PROB = 0.010
LOCAL_SHOCK_SMALL_MULTIPLIER = 1.45
LOCAL_SHOCK_AGENCY_MULTIPLIER = 1.25
LOCAL_SHOCK_EAST_MULTIPLIER = 1.20
LOCAL_SHOCK_MAG_LOW = 0.75
LOCAL_SHOCK_MAG_HIGH = 1.70

MAX_ANNUAL_HAZARD = {
    "A_CORE": 0.0020,
    "B_STRATEGIC": 0.0120,
    "C_STANDARD": 0.0450,
    "D_VULNERABLE": 0.1000,
}


# =============================================================================
# CANONICAL STRUCTURAL NETWORK
# =============================================================================

BRANCH_COLUMNS = ['branch_id',
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
 'longitude']

BRANCHES = [{'branch_id': '001',
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
  'longitude': None},
 {'branch_id': '002',
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
  'longitude': None},
 {'branch_id': '003',
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
  'longitude': None},
 {'branch_id': '004',
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
  'longitude': None},
 {'branch_id': '005',
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
  'longitude': None},
 {'branch_id': '006',
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
  'longitude': None},
 {'branch_id': '007',
  'branch_name': 'Santa Clara de Olimar',
  'branch_type': 'AGENCY',
  'branch_size': 'SMALL',
  'status': 'OPEN',
  'opening_year': '1983',
  'opening_reason': 'LOCAL_EXPANSION',
  'closing_year': None,
  'closure_reason': None,
  'parent_branch_id': '001',
  'department': 'Treinta y Tres',
  'locality': 'Santa Clara de Olimar',
  'region': 'EAST',
  'latitude': None,
  'longitude': None},
 {'branch_id': '008',
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
  'longitude': None},
 {'branch_id': '009',
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
  'longitude': None},
 {'branch_id': '010',
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
  'longitude': None},
 {'branch_id': '011',
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
  'longitude': None},
 {'branch_id': '012',
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
  'longitude': None},
 {'branch_id': '013',
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
  'longitude': None},
 {'branch_id': '014',
  'branch_name': 'Piriápolis',
  'branch_type': 'AGENCY',
  'branch_size': 'SMALL',
  'status': 'OPEN',
  'opening_year': '1998',
  'opening_reason': 'REGIONAL_EXPANSION',
  'closing_year': None,
  'closure_reason': None,
  'parent_branch_id': '013',
  'department': 'Maldonado',
  'locality': 'Piriápolis',
  'region': 'EAST',
  'latitude': None,
  'longitude': None},
 {'branch_id': '015',
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
  'longitude': None},
 {'branch_id': '016',
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
  'longitude': None},
 {'branch_id': '017',
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
  'longitude': None},
 {'branch_id': '018',
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
  'longitude': None},
 {'branch_id': '019',
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
  'longitude': None},
 {'branch_id': '020',
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
  'longitude': None},
 {'branch_id': '021',
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
  'longitude': None},
 {'branch_id': '022',
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
  'longitude': None},
 {'branch_id': '023',
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
  'longitude': None},
 {'branch_id': '024',
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
  'longitude': None},
 {'branch_id': '025',
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
  'longitude': None},
 {'branch_id': '026',
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
  'longitude': None},
 {'branch_id': '027',
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
  'longitude': None},
 {'branch_id': '028',
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
  'longitude': None},
 {'branch_id': '029',
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
  'longitude': None},
 {'branch_id': '030',
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
  'longitude': None},
 {'branch_id': '031',
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
  'longitude': None},
 {'branch_id': '032',
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
  'longitude': None},
 {'branch_id': '033',
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
  'longitude': None},
 {'branch_id': '034',
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
  'longitude': None},
 {'branch_id': '035',
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
  'longitude': None},
 {'branch_id': '036',
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
  'longitude': None},
 {'branch_id': '037',
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
  'longitude': None}]


# =============================================================================
# RNG HELPERS
# =============================================================================

def make_rng(world_seed: int, stream: int) -> np.random.Generator:
    """Create an independent deterministic RNG stream."""
    seed_sequence = np.random.SeedSequence([int(world_seed), int(stream)])
    return np.random.default_rng(seed_sequence)


def six_year_to_annual_probability(probability: float) -> float:
    """Convert a six-year event probability into a neutral annual hazard."""
    p = float(probability)
    if not 0.0 <= p < 1.0:
        raise ValueError("Six-year closure probability must be inside [0, 1).")
    return float(1.0 - (1.0 - p) ** (1.0 / len(YEARS)))


# =============================================================================
# INPUTS
# =============================================================================

def load_macro_environment() -> pd.DataFrame:
    """Load the frozen annual banking environment."""
    if not MACRO_PATH.exists():
        raise FileNotFoundError(
            "Missing bank macro environment. Run generate_banks.py first:\n"
            f"  {MACRO_PATH}"
        )

    macro = pd.read_csv(MACRO_PATH)

    required = {
        "year",
        "macro_growth_factor",
        "credit_cycle_factor",
        "financial_stress_factor",
        "digitalization_factor",
        "systemic_shock",
        "systemic_shock_flag",
        "world_seed",
    }
    missing = required - set(macro.columns)
    if missing:
        raise ValueError(
            "bank_macro_environment.csv is missing required columns: "
            + ", ".join(sorted(missing))
        )

    macro = macro.loc[macro["year"].isin(YEARS)].copy()
    if set(macro["year"].astype(int)) != set(YEARS):
        raise ValueError("Bank macro environment must cover 2021-2026.")

    if macro["year"].duplicated().any():
        raise ValueError("Duplicate year in bank macro environment.")

    return macro.sort_values("year").reset_index(drop=True)


# =============================================================================
# STRUCTURAL MASTER
# =============================================================================

def build_structural_branches() -> pd.DataFrame:
    """Return the canonical network before stochastic closure outcomes."""
    df = pd.DataFrame(BRANCHES, columns=BRANCH_COLUMNS)

    df["branch_id"] = df["branch_id"].astype(str).str.zfill(3)
    df["parent_branch_id"] = df["parent_branch_id"].apply(
        lambda x: str(x).zfill(3)
        if pd.notna(x) and str(x) not in ("", "None")
        else None
    )
    df["opening_year"] = pd.to_numeric(df["opening_year"], errors="raise").astype(int)
    df["closing_year"] = pd.Series([pd.NA] * len(df), dtype="Int64")
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["status"] = "OPEN"
    df["closure_reason"] = None
    return df


def validate_risk_contract(structural: pd.DataFrame) -> None:
    """Validate that every canonical office has exactly one risk contract."""
    ids = set(structural["branch_id"].astype(str))

    if set(STRUCTURAL_SIX_YEAR_CLOSURE_PROB) != ids:
        raise ValueError("Structural closure-probability map does not cover exactly all branches.")

    if set(RISK_GROUP) != ids:
        raise ValueError("Risk-group map does not cover exactly all branches.")

    allowed_groups = {"A_CORE", "B_STRATEGIC", "C_STANDARD", "D_VULNERABLE"}
    if not set(RISK_GROUP.values()).issubset(allowed_groups):
        raise ValueError("Unknown branch risk group.")

    if RISK_GROUP["001"] != "A_CORE":
        raise ValueError("Treinta y Tres must remain A_CORE.")

    if not np.isclose(STRUCTURAL_SIX_YEAR_CLOSURE_PROB["001"], 0.00006):
        raise ValueError("Treinta y Tres six-year structural closure probability drifted.")


# =============================================================================
# LATENT BRANCH STATE
# =============================================================================

STATE_COLUMNS = tuple(PRESSURE_WEIGHTS)


def initial_state(
    branch_id: str,
    row: pd.Series,
    rng: np.random.Generator,
) -> dict[str, float]:
    """Draw a modest branch-specific starting condition."""
    group_shift = {
        "A_CORE": -0.30,
        "B_STRATEGIC": -0.12,
        "C_STANDARD": 0.00,
        "D_VULNERABLE": 0.12,
    }[RISK_GROUP[branch_id]]

    size_shift = {
        "LARGE": -0.12,
        "MEDIUM": 0.00,
        "SMALL": 0.10,
    }[str(row["branch_size"])]

    return {
        column: float(
            np.clip(
                rng.normal(group_shift + size_shift, 0.22),
                -STATE_CLIP,
                STATE_CLIP,
            )
        )
        for column in STATE_COLUMNS
    }


def network_overlap_anchor(row: pd.Series) -> float:
    """
    Structural overlap anchor.

    Metropolitan agencies receive more substitution pressure because nearby
    offices and digital channels can absorb activity. This is a latent driver,
    not a closure rule.
    """
    overlap = 0.0

    if str(row["branch_type"]) == "AGENCY":
        overlap += 0.20
    if str(row["region"]) == "METROPOLITAN":
        overlap += 0.35
    if str(row["branch_size"]) == "SMALL":
        overlap += 0.10

    return overlap


def local_shock_probability(row: pd.Series) -> float:
    """Return the annual probability of a synthetic local disruption."""
    p = LOCAL_SHOCK_BASE_PROB
    if str(row["branch_size"]) == "SMALL":
        p *= LOCAL_SHOCK_SMALL_MULTIPLIER
    if str(row["branch_type"]) == "AGENCY":
        p *= LOCAL_SHOCK_AGENCY_MULTIPLIER
    if str(row["region"]) == "EAST":
        p *= LOCAL_SHOCK_EAST_MULTIPLIER
    return float(np.clip(p, 0.0, 0.08))


def evolve_state(
    previous: dict[str, float],
    row: pd.Series,
    macro_row: pd.Series,
    local_shock: float,
    rng: np.random.Generator,
) -> dict[str, float]:
    """
    Evolve the annual latent branch state.

    These drivers are designed to be reused by downstream generators:
      customer_pressure      -> customer growth / attrition
      deposit_pressure       -> balances / deposit growth
      transaction_pressure   -> branch activity / transaction growth
      credit_pressure        -> loan origination / risk
      cost_pressure          -> branch profitability layer
      digital_substitution   -> channel migration / branch traffic
      network_overlap        -> nearby-office substitution
      operational_pressure   -> failures / local disruption
    """
    macro_growth = float(macro_row["macro_growth_factor"])
    credit_cycle = float(macro_row["credit_cycle_factor"])
    financial_stress = float(macro_row["financial_stress_factor"])
    digitalization = float(macro_row["digitalization_factor"])
    systemic_shock = float(macro_row["systemic_shock"])

    overlap_anchor = network_overlap_anchor(row)
    agency = 1.0 if str(row["branch_type"]) == "AGENCY" else 0.0
    small = 1.0 if str(row["branch_size"]) == "SMALL" else 0.0

    macro_targets = {
        "customer_pressure": -0.28 * macro_growth + 0.18 * financial_stress,
        "deposit_pressure": -0.22 * macro_growth + 0.22 * financial_stress,
        "transaction_pressure": (
            -0.18 * macro_growth
            + 0.18 * financial_stress
            + 0.18 * max(digitalization, 0.0) * agency
        ),
        "credit_pressure": -0.30 * credit_cycle + 0.25 * financial_stress,
        "cost_pressure": 0.22 * financial_stress + 0.10 * small,
        "digital_substitution": 0.55 * digitalization * (0.45 + 0.55 * agency),
        "network_overlap": overlap_anchor,
        "operational_pressure": 0.20 * abs(systemic_shock) + 0.90 * local_shock,
    }

    new_state = {}
    for column in STATE_COLUMNS:
        innovation = float(rng.normal(0.0, STATE_INNOVATION_SD))
        target = float(macro_targets[column])
        value = (
            STATE_PERSISTENCE * float(previous[column])
            + (1.0 - STATE_PERSISTENCE) * target
            + innovation
        )
        new_state[column] = float(np.clip(value, -STATE_CLIP, STATE_CLIP))

    return new_state


def closure_pressure_score(
    state: dict[str, float],
    macro_row: pd.Series,
    local_shock: float,
) -> float:
    """Combine observable-style latent pressures into one closure-pressure score."""
    score = sum(
        PRESSURE_WEIGHTS[column] * max(float(state[column]), -1.0)
        for column in STATE_COLUMNS
    )

    score += 0.10 * max(float(macro_row["financial_stress_factor"]), -0.5)
    score += 0.08 * abs(float(macro_row["systemic_shock"]))
    score += 0.10 * local_shock

    return float(np.clip(score, -1.50, 3.00))


# =============================================================================
# CLOSURE MODEL
# =============================================================================

def structural_annual_hazard(branch_id: str) -> float:
    """Return neutral annual hazard implied by the branch six-year anchor."""
    return six_year_to_annual_probability(
        STRUCTURAL_SIX_YEAR_CLOSURE_PROB[branch_id]
    )


def choose_closure_reason(
    state: dict[str, float],
    local_shock: float,
    rng: np.random.Generator,
) -> str:
    """
    Select a broad administrative reason from the dominant deterioration path.

    The exact latent pressures remain in branch_yearly_state.csv.
    """
    components = {
        "COMMERCIAL_CONSOLIDATION": (
            float(state["customer_pressure"])
            + float(state["deposit_pressure"])
        ) / 2.0,
        "ACTIVITY_CONSOLIDATION": float(state["transaction_pressure"]),
        "CREDIT_REVIEW": float(state["credit_pressure"]),
        "COST_OPTIMIZATION": float(state["cost_pressure"]),
        "DIGITAL_NETWORK_OPTIMIZATION": (
            float(state["digital_substitution"])
            + float(state["network_overlap"])
        ) / 2.0,
        "OPERATIONAL_RESTRUCTURING": (
            float(state["operational_pressure"]) + local_shock
        ),
    }

    ranked = sorted(components.items(), key=lambda item: item[1], reverse=True)
    top_reason, top_value = ranked[0]

    # Preserve some uncertainty when several causes are similar.
    close_candidates = [
        reason
        for reason, value in ranked[:3]
        if value >= top_value - 0.25
    ]
    return str(rng.choice(close_candidates))


def _simulate_branch_world(
    structural: pd.DataFrame,
    macro: pd.DataFrame,
    world_seed: int,
    collect_state: bool,
) -> tuple[list[dict], list[dict]]:
    """
    Core simulation using Python records rather than pandas row iteration.

    This keeps production behavior readable while making Monte Carlo auditing
    substantially faster.
    """
    rng_state = make_rng(world_seed, RNG_STREAM_STATE)
    rng_shock = make_rng(world_seed, RNG_STREAM_LOCAL_SHOCK)
    rng_close = make_rng(world_seed, RNG_STREAM_CLOSURE_DRAW)
    rng_reason = make_rng(world_seed, RNG_STREAM_REASON)

    branch_records = structural.to_dict("records")
    macro_lookup = macro.set_index("year").to_dict("index")

    states = {}
    for row_dict in branch_records:
        branch_id = str(row_dict["branch_id"])
        states[branch_id] = initial_state(
            branch_id,
            pd.Series(row_dict),
            rng_state,
        )

    closed_ids: set[str] = set()
    closure_records: list[dict] = []
    state_rows: list[dict] = []
    realized_closures = 0

    for year in YEARS:
        macro_row = pd.Series(macro_lookup[int(year)])

        for row_dict in branch_records:
            branch_id = str(row_dict["branch_id"])

            if branch_id in closed_ids:
                continue
            if int(row_dict["opening_year"]) > int(year):
                continue

            row = pd.Series(row_dict)

            shock_flag = bool(
                rng_shock.random() < local_shock_probability(row)
            )
            local_shock = (
                float(
                    rng_shock.uniform(
                        LOCAL_SHOCK_MAG_LOW,
                        LOCAL_SHOCK_MAG_HIGH,
                    )
                )
                if shock_flag
                else 0.0
            )

            state = evolve_state(
                previous=states[branch_id],
                row=row,
                macro_row=macro_row,
                local_shock=local_shock,
                rng=rng_state,
            )
            states[branch_id] = state

            pressure = closure_pressure_score(
                state=state,
                macro_row=macro_row,
                local_shock=local_shock,
            )

            neutral_hazard = structural_annual_hazard(branch_id)
            raw_hazard = neutral_hazard * np.exp(
                HAZARD_PRESSURE_SCALE * pressure
            )

            closures_before_draw = realized_closures
            saturation = CLOSURE_SATURATION_MULTIPLIER[
                min(realized_closures, MAX_WORLD_CLOSURES)
            ]

            annual_hazard = float(
                np.clip(
                    raw_hazard * saturation,
                    0.0,
                    MAX_ANNUAL_HAZARD[RISK_GROUP[branch_id]],
                )
            )

            if realized_closures >= MAX_WORLD_CLOSURES:
                annual_hazard = 0.0

            draw = float(rng_close.random())
            closed_this_year = bool(draw < annual_hazard)

            reason = None
            if closed_this_year:
                reason = choose_closure_reason(
                    state=state,
                    local_shock=local_shock,
                    rng=rng_reason,
                )
                closed_ids.add(branch_id)
                realized_closures += 1

                closure_records.append(
                    {
                        "branch_id": branch_id,
                        "closing_year": int(year),
                        "closure_reason": reason,
                        "risk_group": RISK_GROUP[branch_id],
                        "local_shock_flag": shock_flag,
                        "closure_pressure": pressure,
                    }
                )

            if collect_state:
                state_rows.append(
                    {
                        "branch_world_seed": int(world_seed),
                        "bank_world_seed": int(macro_row["world_seed"]),
                        "year": int(year),
                        "branch_id": branch_id,
                        "branch_name": str(row_dict["branch_name"]),
                        "risk_group": RISK_GROUP[branch_id],
                        "structural_six_year_closure_prob": (
                            STRUCTURAL_SIX_YEAR_CLOSURE_PROB[branch_id]
                        ),
                        "neutral_annual_hazard": neutral_hazard,
                        **state,
                        "local_shock_flag": shock_flag,
                        "local_shock_magnitude": local_shock,
                        "macro_growth_factor": float(
                            macro_row["macro_growth_factor"]
                        ),
                        "credit_cycle_factor": float(
                            macro_row["credit_cycle_factor"]
                        ),
                        "financial_stress_factor": float(
                            macro_row["financial_stress_factor"]
                        ),
                        "digitalization_factor": float(
                            macro_row["digitalization_factor"]
                        ),
                        "systemic_shock": float(
                            macro_row["systemic_shock"]
                        ),
                        "systemic_shock_flag": bool(
                            macro_row["systemic_shock_flag"]
                        ),
                        "closure_pressure": pressure,
                        "closures_before_draw": int(closures_before_draw),
                        "saturation_multiplier": saturation,
                        "annual_closure_probability": annual_hazard,
                        "closure_draw": draw,
                        "closed_this_year": closed_this_year,
                        "closure_reason": reason,
                    }
                )

    return closure_records, state_rows


def simulate_branch_closure_summary(
    structural: pd.DataFrame,
    macro: pd.DataFrame,
    world_seed: int,
) -> list[dict]:
    """Fast Monte Carlo path returning only realized closure records."""
    closures, _ = _simulate_branch_world(
        structural=structural,
        macro=macro,
        world_seed=world_seed,
        collect_state=False,
    )
    return closures


def simulate_branch_closures(
    structural: pd.DataFrame,
    macro: pd.DataFrame,
    world_seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate production branches and the full annual explanatory state."""
    closures, state_rows = _simulate_branch_world(
        structural=structural,
        macro=macro,
        world_seed=world_seed,
        collect_state=True,
    )

    df = structural.copy()
    closure_lookup = {
        str(record["branch_id"]): record
        for record in closures
    }

    for idx, row in df.iterrows():
        branch_id = str(row["branch_id"])
        closure = closure_lookup.get(branch_id)
        if closure is None:
            continue

        df.at[idx, "status"] = "CLOSED"
        df.at[idx, "closing_year"] = int(closure["closing_year"])
        df.at[idx, "closure_reason"] = str(
            closure["closure_reason"]
        )

    df["closing_year"] = pd.to_numeric(
        df["closing_year"], errors="coerce"
    ).astype("Int64")

    return df, pd.DataFrame(state_rows)


# =============================================================================
# VALIDATION
# =============================================================================

def validate_branches(df: pd.DataFrame) -> None:
    errors = []

    if list(df.columns) != BRANCH_COLUMNS:
        errors.append("Branch output columns changed unexpectedly.")
    if len(df) != 37:
        errors.append(f"Expected 37 branches, found {len(df)}.")
    if df["branch_id"].duplicated().any():
        errors.append("Duplicate branch_id.")
    if not df["status"].isin(["OPEN", "CLOSED"]).all():
        errors.append("Invalid branch status.")

    closed = df["status"].eq("CLOSED")
    opened = ~closed

    if df.loc[closed, "closing_year"].isna().any():
        errors.append("Closed branch without closing_year.")
    if df.loc[closed, "closure_reason"].isna().any():
        errors.append("Closed branch without closure_reason.")
    if df.loc[opened, "closing_year"].notna().any():
        errors.append("Open branch with closing_year.")
    if df.loc[opened, "closure_reason"].notna().any():
        errors.append("Open branch with closure_reason.")

    if int(closed.sum()) > MAX_WORLD_CLOSURES:
        errors.append("World closure cap exceeded.")

    valid_ids = set(df["branch_id"])
    parents = set(df["parent_branch_id"].dropna())
    if not parents.issubset(valid_ids):
        errors.append("Invalid parent_branch_id foreign key.")

    if errors:
        print("\nVALIDATION: FAIL")
        for error in errors:
            print(" -", error)
        raise AssertionError("Branch validation failed.")

    print("\nVALIDATION: PASS")


def validate_state(
    branches: pd.DataFrame,
    state_df: pd.DataFrame,
) -> None:
    errors = []

    if state_df.empty:
        errors.append("branch_yearly_state.csv would be empty.")

    if not state_df["annual_closure_probability"].between(0.0, 1.0).all():
        errors.append("Invalid annual closure probability.")

    realized = state_df.loc[state_df["closed_this_year"]]
    if realized["branch_id"].duplicated().any():
        errors.append("A branch closed more than once.")

    if len(realized) > MAX_WORLD_CLOSURES:
        errors.append("State table exceeds world closure cap.")

    output_closed = set(
        branches.loc[branches["status"].eq("CLOSED"), "branch_id"].astype(str)
    )
    state_closed = set(realized["branch_id"].astype(str))
    if output_closed != state_closed:
        errors.append("branches.csv and branch_yearly_state.csv disagree.")

    if errors:
        print("STATE VALIDATION: FAIL")
        for error in errors:
            print(" -", error)
        raise AssertionError("Branch yearly-state validation failed.")

    print("STATE VALIDATION: PASS")


# =============================================================================
# REPORT
# =============================================================================

def print_report(
    branches: pd.DataFrame,
    state_df: pd.DataFrame,
    world_seed: int,
    macro: pd.DataFrame,
) -> None:
    print("\n" + "=" * 96)
    print("BTYT BRANCH NETWORK GENERATOR — V2.1.0")
    print("=" * 96)
    print(f"BRANCH_WORLD_SEED: {world_seed}")
    print(f"BANK_WORLD_SEED: {int(macro.iloc[0]['world_seed'])}")
    print(f"Branches: {len(branches)}")
    print(f"Maximum possible closures: {MAX_WORLD_CLOSURES}")

    print("\nStructural risk groups:")
    risk_table = pd.DataFrame(
        {
            "branch_id": list(RISK_GROUP),
            "risk_group": [RISK_GROUP[x] for x in RISK_GROUP],
            "six_year_prob": [
                STRUCTURAL_SIX_YEAR_CLOSURE_PROB[x] for x in RISK_GROUP
            ],
        }
    )
    group_summary = risk_table.groupby("risk_group").agg(
        branches=("branch_id", "size"),
        min_six_year_prob=("six_year_prob", "min"),
        mean_six_year_prob=("six_year_prob", "mean"),
        max_six_year_prob=("six_year_prob", "max"),
    )
    for col in [
        "min_six_year_prob",
        "mean_six_year_prob",
        "max_six_year_prob",
    ]:
        group_summary[col] = group_summary[col] * 100.0
    print(group_summary.to_string(float_format=lambda x: f"{x:.3f}%"))

    print("\nFinal status:")
    print(branches["status"].value_counts().sort_index().to_string())

    print("\nRealized closures:")
    closed = branches.loc[
        branches["status"].eq("CLOSED"),
        ["branch_id", "branch_name", "closing_year", "closure_reason"],
    ]
    if closed.empty:
        print("  none")
    else:
        print(closed.to_string(index=False))

    print("\nHighest realized annual closure probabilities:")
    cols = [
        "year",
        "branch_id",
        "branch_name",
        "risk_group",
        "annual_closure_probability",
        "closure_pressure",
        "local_shock_flag",
    ]
    high = state_df.sort_values(
        "annual_closure_probability", ascending=False
    ).head(12)[cols].copy()
    high["annual_closure_probability"] *= 100.0
    high = high.rename(
        columns={"annual_closure_probability": "closure_probability_pct"}
    )
    print(high.to_string(index=False))


# =============================================================================
# MAIN
# =============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the BTYT branch network with V2.1 dynamic closures."
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=PRODUCTION_BRANCH_WORLD_SEED,
        help="Branch-world seed.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    macro = load_macro_environment()
    structural = build_structural_branches()
    validate_risk_contract(structural)

    branches, state_df = simulate_branch_closures(
        structural=structural,
        macro=macro,
        world_seed=int(args.seed),
    )

    validate_branches(branches)
    validate_state(branches, state_df)
    print_report(branches, state_df, int(args.seed), macro)

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)

    branches.to_csv(OUTPUT_PATH, index=False)
    state_df.to_csv(STATE_PATH, index=False)

    print(f"\nSaved: {OUTPUT_PATH} {branches.shape}")
    print(f"Saved: {STATE_PATH} {state_df.shape}")


if __name__ == "__main__":
    main()
