from __future__ import annotations

import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


# =============================================================================
# BTYT — CARDS GENERATOR
# =============================================================================
# Generates the master cards table:
#   P009 Debit Card
#   P010 Classic Credit Card
#   P011 Premium Credit Card
#
# Design:
# - Reproducible synthetic DGP.
# - Same 10,000-customer development sample used by the frozen accounts DGP.
# - Pre-2021 history is compressed inherited state.
# - 2021-2026 is modeled as explicit annual issuance / closure evolution.
# - Hard banking integrity rules are validated.
# - Behavioral shares emerge probabilistically; they are not hard quotas.
# =============================================================================

SEED = 20260827
CARD_SEED = SEED + 9009
CURRENT_YEAR = 2026
OBSERVATION_START_YEAR = 2021

DEVELOPMENT_MODE = True
DEVELOPMENT_CUSTOMERS = 10_000

ROOT = Path(__file__).resolve().parents[1]
MASTER_DIR = ROOT / "data" / "master"
GENERATED_DIR = ROOT / "data" / "generated"
INTERIM_DIR = ROOT / "data" / "interim"

CUSTOMERS_PATH = GENERATED_DIR / "customers.csv"
ACCOUNTS_PATH = GENERATED_DIR / "accounts.csv"
PRODUCTS_PATH = MASTER_DIR / "products.csv"
BRANCH_STATE_PATH = INTERIM_DIR / "branch_yearly_state.csv"
OUTPUT_PATH = GENERATED_DIR / "cards.csv"

CARD_PRODUCTS = ["P009", "P010", "P011"]
DEBIT_PRODUCT = "P009"
CREDIT_PRODUCTS = ["P010", "P011"]
DEBIT_ACCOUNT_PRODUCTS = {"P001", "P002", "P003", "P004", "P005", "P006"}

CHANNELS = ["BRANCH", "REMOTE_ASSISTED", "DIGITAL"]

PRODUCT_META = {
    "P009": {"launch_year": 1996, "target": "BOTH"},
    "P010": {"launch_year": 1993, "target": "INDIVIDUAL"},
    "P011": {"launch_year": 2008, "target": "INDIVIDUAL"},
}

# First-pass P009 product propensities. These are logits, not percentages.
DEBIT_BASE = {
    "P005": 2.80,  # Payroll
    "P003": 2.60,  # Current UYU
    "P006": 2.30,  # Youth / Student
    "P001": 2.20,  # Savings UYU
    "P004": 1.90,  # Current USD
    "P002": 1.60,  # Savings USD
}

EMPLOYMENT_CREDIT_EFFECT = {
    "EMPLOYED": 0.15,
    "SELF_EMPLOYED": 0.10,
    "STUDENT": -0.10,
    "RETIRED": -0.10,
    "UNEMPLOYED": -0.30,
    "OTHER": 0.00,
}


# =============================================================================
# Helpers
# =============================================================================

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -12, 12)))


def softmax(values):
    x = np.asarray(values, dtype=float)
    if len(x) == 1:
        return np.array([1.0])
    x = x - np.max(x)
    e = np.exp(x)
    return e / e.sum()


def zscore(series):
    s = pd.to_numeric(series, errors="coerce")
    if s.notna().sum() == 0:
        return pd.Series(0.0, index=s.index)
    s = s.fillna(s.median())
    sd = s.std(ddof=0)
    if not np.isfinite(sd) or sd == 0:
        return pd.Series(0.0, index=s.index)
    return (s - s.mean()) / sd


def log_zscore(series):
    s = pd.to_numeric(series, errors="coerce").clip(lower=0)
    return zscore(np.log1p(s))


def as_year(value):
    value = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(value) else int(value)


# =============================================================================
# Input loading
# =============================================================================

def load_inputs():
    required_paths = {
        "customers": CUSTOMERS_PATH,
        "accounts": ACCOUNTS_PATH,
        "products": PRODUCTS_PATH,
        "branch_yearly_state": BRANCH_STATE_PATH,
    }
    missing_paths = [path for path in required_paths.values() if not path.exists()]
    if missing_paths:
        raise FileNotFoundError(
            "Missing canonical BTYT input file(s):\n"
            + "\n".join(str(path) for path in missing_paths)
        )

    customers = pd.read_csv(
        CUSTOMERS_PATH,
        dtype={"customer_id": str, "primary_branch_id": str},
    )

    # EXACT development-sample logic used by the frozen accounts generator.
    if DEVELOPMENT_MODE and len(customers) > DEVELOPMENT_CUSTOMERS:
        customers = (
            customers.sample(n=DEVELOPMENT_CUSTOMERS, random_state=SEED)
            .sort_values("customer_id")
            .reset_index(drop=True)
        )

    accounts = pd.read_csv(
        ACCOUNTS_PATH,
        dtype={"account_id": str, "customer_id": str, "product_id": str, "branch_id": str},
    )

    products = pd.read_csv(PRODUCTS_PATH, dtype={"product_id": str})
    branch_state = pd.read_csv(BRANCH_STATE_PATH, dtype={"branch_id": str})
    branch_state["branch_id"] = branch_state["branch_id"].str.zfill(3)

    return customers, accounts, products, branch_state


def validate_inputs(customers, accounts, products, branch_state):
    required_customers = {
        "customer_id",
        "customer_type",
        "birth_year",
        "registration_year",
        "customer_status",
        "closing_year",
        "employment_status",
        "monthly_income",
        "annual_revenue",
        "company_size",
    }
    missing = required_customers - set(customers.columns)
    if missing:
        raise ValueError(f"customers.csv missing: {sorted(missing)}")

    required_accounts = {
        "account_id",
        "customer_id",
        "product_id",
        "opening_year",
        "account_status",
        "closing_year",
        "opening_channel",
    }
    missing = required_accounts - set(accounts.columns)
    if missing:
        raise ValueError(f"accounts.csv missing: {sorted(missing)}")

    if customers["customer_id"].duplicated().any():
        raise ValueError("Duplicate customer_id in customers.csv.")

    if accounts["account_id"].duplicated().any():
        raise ValueError("Duplicate account_id in accounts.csv.")

    customer_ids = set(customers["customer_id"])
    unknown_accounts = set(accounts["customer_id"]) - customer_ids
    if unknown_accounts:
        raise ValueError(
            "accounts.csv contains customer IDs outside the reproducible "
            f"{len(customers):,}-customer development sample. "
            f"Examples: {sorted(unknown_accounts)[:5]}"
        )

    actual = products.set_index("product_id")
    for product_id, meta in PRODUCT_META.items():
        if product_id not in actual.index:
            raise ValueError(f"{product_id} missing from products.csv.")
        launch = int(actual.loc[product_id, "launch_year"])
        target = str(actual.loc[product_id, "target_customer_type"])
        if launch != meta["launch_year"] or target != meta["target"]:
            raise ValueError(
                f"{product_id} metadata mismatch. Expected launch={meta['launch_year']}, "
                f"target={meta['target']}; got launch={launch}, target={target}."
            )

    if not accounts["product_id"].isin(
        ["P001", "P002", "P003", "P004", "P005", "P006", "P007", "P008"]
    ).all():
        raise ValueError("accounts.csv contains a non-account product.")

    state_required = {
        "branch_id", "year", "customer_pressure", "digital_substitution",
    }
    missing_state = state_required - set(branch_state.columns)
    if missing_state:
        raise ValueError(
            f"branch_yearly_state.csv missing: {sorted(missing_state)}"
        )

    if branch_state.duplicated(["branch_id", "year"]).any():
        raise ValueError("Duplicate branch_id/year in branch_yearly_state.csv.")

    branch_state["year"] = pd.to_numeric(branch_state["year"], errors="coerce")
    if branch_state["year"].isna().any():
        raise ValueError("Invalid year in branch_yearly_state.csv.")

    for col in ["customer_pressure", "digital_substitution"]:
        if pd.to_numeric(branch_state[col], errors="coerce").isna().any():
            raise ValueError(f"Invalid numeric values in branch state column: {col}")


# =============================================================================
# Generator
# =============================================================================

class CardsGenerator:
    def __init__(self, customers, accounts, branch_state):
        self.customers = customers.copy()
        self.accounts = accounts.copy()
        self.branch_state = branch_state.copy()

        # Separate stream from accounts generation: cards remain reproducible
        # without pretending to have access to hidden account-generator latents.
        self.rng = np.random.default_rng(CARD_SEED)

        self.cards = []
        self.portfolios = defaultdict(list)
        self.debit_account_used = set()
        self.counter = 1

        self.prepare_inputs()
        self.prepare_branch_state()
        self.prepare_signals()
        self.generate_card_side_latents()

        self.customer_lookup = self.customers.set_index("customer_id")
        self.account_lookup = self.accounts.set_index("account_id")
        self.accounts_by_customer = {
            customer_id: frame.copy()
            for customer_id, frame in self.accounts.groupby("customer_id", sort=False)
        }

    # -------------------------------------------------------------------------
    # Signals / latents
    # -------------------------------------------------------------------------

    def prepare_inputs(self):
        for col in ["registration_year", "birth_year", "closing_year"]:
            self.customers[col] = pd.to_numeric(self.customers[col], errors="coerce")

        for col in ["opening_year", "closing_year"]:
            self.accounts[col] = pd.to_numeric(self.accounts[col], errors="coerce")

        self.customers = self.customers.sort_values("customer_id").reset_index(drop=True)
        self.accounts = self.accounts.sort_values("account_id").reset_index(drop=True)

    def prepare_branch_state(self):
        """
        Build the 2021-2026 branch-state lookup used by the card DGP.

        Cards intentionally consume only customer pressure and digital
        substitution. Credit pressure is not used because card appetite is not
        intended to proxy credit risk.
        """
        state = self.branch_state.copy()
        state["year"] = pd.to_numeric(state["year"], errors="raise").astype(int)
        for col in ["customer_pressure", "digital_substitution"]:
            state[col] = pd.to_numeric(state[col], errors="raise").astype(float)

        self.branch_state_lookup = {
            (str(row.branch_id).zfill(3), int(row.year)): {
                "customer_pressure": float(row.customer_pressure),
                "digital_substitution": float(row.digital_substitution),
            }
            for row in state.itertuples(index=False)
        }

    def get_branch_state(self, branch_id, year):
        neutral = {
            "customer_pressure": 0.0,
            "digital_substitution": 0.0,
        }
        if year < OBSERVATION_START_YEAR or branch_id is None:
            return neutral
        return self.branch_state_lookup.get(
            (str(branch_id).zfill(3), int(year)),
            neutral,
        )

    def customer_branch_id(self, row):
        return str(row["primary_branch_id"]).zfill(3)

    def card_branch_id(self, row, product, linked_account_id=None):
        """
        Debit cards inherit the linked account branch. Credit cards use the
        customer's primary relationship branch because they have no linked
        account in the card master.
        """
        if product == DEBIT_PRODUCT and linked_account_id is not None:
            return str(
                self.account_lookup.loc[linked_account_id, "branch_id"]
            ).zfill(3)
        return self.customer_branch_id(row)

    def prepare_signals(self):
        c = self.customers

        c["_tenure_z"] = log_zscore(
            np.maximum(0, CURRENT_YEAR - c["registration_year"])
        )

        c["_income_z"] = 0.0
        individual = c["customer_type"].eq("INDIVIDUAL")
        if individual.any():
            c.loc[individual, "_income_z"] = log_zscore(
                c.loc[individual, "monthly_income"]
            )

        # Account-based relationship proxies. They use observable frozen account
        # outcomes rather than trying to recreate unavailable hidden latents.
        total_accounts = self.accounts.groupby("customer_id").size()
        active_accounts = (
            self.accounts[self.accounts["account_status"].eq("ACTIVE")]
            .groupby("customer_id")
            .size()
        )
        distinct_products = self.accounts.groupby("customer_id")["product_id"].nunique()

        digital_accounts = (
            self.accounts["opening_channel"].eq("DIGITAL").astype(int)
            .groupby(self.accounts["customer_id"])
            .sum()
        )
        remote_accounts = (
            self.accounts["opening_channel"].eq("REMOTE_ASSISTED").astype(int)
            .groupby(self.accounts["customer_id"])
            .sum()
        )

        usd_accounts = (
            self.accounts["product_id"].isin({"P002", "P004", "P008"}).astype(int)
            .groupby(self.accounts["customer_id"])
            .sum()
        )

        c["_n_accounts"] = c["customer_id"].map(total_accounts).fillna(0).astype(int)
        c["_n_active_accounts"] = c["customer_id"].map(active_accounts).fillna(0).astype(int)
        c["_n_account_products"] = c["customer_id"].map(distinct_products).fillna(0).astype(int)
        c["_n_digital_accounts"] = c["customer_id"].map(digital_accounts).fillna(0).astype(int)
        c["_n_remote_accounts"] = c["customer_id"].map(remote_accounts).fillna(0).astype(int)
        c["_n_usd_accounts"] = c["customer_id"].map(usd_accounts).fillna(0).astype(int)

        denom = c["_n_accounts"].replace(0, np.nan)
        c["_digital_account_share"] = (
            c["_n_digital_accounts"] / denom
        ).fillna(0.0)
        c["_remote_account_share"] = (
            c["_n_remote_accounts"] / denom
        ).fillna(0.0)
        c["_usd_account_share"] = (
            c["_n_usd_accounts"] / denom
        ).fillna(0.0)

        c["_account_depth_z"] = log_zscore(
            c["_n_accounts"] + 0.70 * c["_n_active_accounts"] + 0.40 * c["_n_account_products"]
        )

    def generate_card_side_latents(self):
        c = self.customers
        n = len(c)

        common = self.rng.normal(0, 1, n)
        noise_depth = self.rng.normal(0, 1, n)
        noise_digital = self.rng.normal(0, 1, n)
        noise_usd = self.rng.normal(0, 1, n)
        noise_credit = self.rng.normal(0, 1, n)

        # Relationship depth proxy:
        # tenure + actual breadth/depth of the frozen account portfolio + noise.
        depth_score = (
            0.55 * c["_tenure_z"]
            + 0.75 * c["_account_depth_z"]
            + 0.20 * common
            + 0.45 * noise_depth
        )
        c["_relationship_z"] = zscore(pd.Series(depth_score, index=c.index))
        c["_relationship_depth"] = np.exp(
            np.clip(0.28 * depth_score, -1.0, 1.0)
        )

        # Digital affinity proxy:
        # age/lifecycle + recent onboarding + actual account channel behavior.
        age = CURRENT_YEAR - c["birth_year"].fillna(CURRENT_YEAR - 40)
        age_signal = np.clip((45 - age) / 20, -1.5, 1.5)
        recent = np.clip((c["registration_year"] - 2010) / 12, -1.5, 1.5)
        channel_signal = (
            1.20 * c["_digital_account_share"]
            + 0.35 * c["_remote_account_share"]
        )
        digital_score = (
            0.72 * age_signal
            + 0.38 * recent
            + 0.80 * channel_signal
            + 0.15 * common
            + 0.85 * noise_digital
        )
        c["_digital_affinity"] = sigmoid(digital_score)
        c["_digital_z"] = zscore(c["_digital_affinity"])

        # USD affinity proxy. Primarily useful for Premium selection.
        usd_score = (
            0.50 * c["_income_z"]
            + 0.95 * c["_usd_account_share"]
            + 0.15 * common
            + 0.85 * noise_usd
        )
        c["_usd_affinity"] = sigmoid(usd_score)
        c["_usd_z"] = zscore(c["_usd_affinity"])

        # Credit appetite is preference/propensity to use credit, NOT risk.
        lifecycle = np.zeros(n, dtype=float)
        lifecycle = np.where(age < 25, -0.20, lifecycle)
        lifecycle = np.where((age >= 25) & (age <= 34), 0.15, lifecycle)
        lifecycle = np.where((age >= 35) & (age <= 49), 0.25, lifecycle)
        lifecycle = np.where((age >= 50) & (age <= 64), 0.05, lifecycle)
        lifecycle = np.where(age >= 65, -0.20, lifecycle)

        employment = (
            c["employment_status"]
            .fillna("OTHER")
            .map(EMPLOYMENT_CREDIT_EFFECT)
            .fillna(0.0)
            .to_numpy(dtype=float)
        )

        credit_score = (
            -0.15
            + 0.30 * c["_income_z"].to_numpy(dtype=float)
            + 0.38 * c["_relationship_z"].to_numpy(dtype=float)
            + 0.22 * c["_digital_z"].to_numpy(dtype=float)
            + lifecycle
            + employment
            + 0.20 * common
            + 1.00 * noise_credit
        )
        c["_credit_appetite"] = sigmoid(credit_score)
        c["_credit_appetite_centered"] = 2.0 * (c["_credit_appetite"] - 0.5)

    # -------------------------------------------------------------------------
    # Basic portfolio helpers
    # -------------------------------------------------------------------------

    def row_for_customer(self, customer_id):
        return self.customer_lookup.loc[customer_id]

    def customer_alive_in_year(self, row, year):
        if int(row["registration_year"]) > year:
            return False
        if str(row["customer_status"]) == "CLOSED":
            cy = as_year(row["closing_year"])
            if cy is not None and cy < year:
                return False
        return True

    def card_is_active_in_year(self, card, year):
        if int(card["issue_year"]) > year:
            return False
        cy = as_year(card["closing_year"])
        return cy is None or cy > year

    def active_cards(self, customer_id, year, credit_only=False, debit_only=False):
        cards = [
            c for c in self.portfolios.get(customer_id, [])
            if self.card_is_active_in_year(c, year)
        ]
        if credit_only:
            cards = [c for c in cards if c["product_id"] in CREDIT_PRODUCTS]
        if debit_only:
            cards = [c for c in cards if c["product_id"] == DEBIT_PRODUCT]
        return cards

    def historical_credit_cards(self, customer_id, year):
        return [
            c for c in self.portfolios.get(customer_id, [])
            if c["product_id"] in CREDIT_PRODUCTS and c["issue_year"] <= year
        ]

    def eligible_debit_accounts_for_customer(self, customer_id):
        frame = self.accounts_by_customer.get(customer_id)
        if frame is None:
            return self.accounts.iloc[0:0].copy()
        return frame[frame["product_id"].isin(DEBIT_ACCOUNT_PRODUCTS)].copy()

    def account_exists_in_year(self, account, year):
        if int(account["opening_year"]) > year:
            return False
        cy = as_year(account["closing_year"])
        return cy is None or cy >= year

    # -------------------------------------------------------------------------
    # Channel
    # -------------------------------------------------------------------------

    def choose_issue_channel(self, row, year, product, branch_id=None):
        if year < 2005:
            scores = {"BRANCH": 3.00, "REMOTE_ASSISTED": -2.50, "DIGITAL": -6.00}
        elif year < 2012:
            scores = {"BRANCH": 2.50, "REMOTE_ASSISTED": -0.50, "DIGITAL": -3.20}
        elif year < 2018:
            scores = {"BRANCH": 1.80, "REMOTE_ASSISTED": 0.10, "DIGITAL": -0.80}
        elif year < 2021:
            scores = {"BRANCH": 1.20, "REMOTE_ASSISTED": 0.30, "DIGITAL": 0.30}
        else:
            progress = np.clip((year - 2021) / 5.0, 0.0, 1.0)
            scores = {
                "BRANCH": 0.90 - 0.60 * progress,
                "REMOTE_ASSISTED": 0.30 - 0.10 * progress,
                "DIGITAL": 0.80 + 0.90 * progress,
            }

        digital_z = float(row["_digital_z"])
        scores["DIGITAL"] += 0.90 * digital_z
        scores["REMOTE_ASSISTED"] += 0.20 * digital_z

        if product == "P009":
            scores["BRANCH"] += 0.22
            scores["DIGITAL"] -= 0.05
        elif product == "P010":
            scores["DIGITAL"] += 0.20
        elif product == "P011":
            scores["REMOTE_ASSISTED"] += 0.25
            scores["BRANCH"] += 0.08
            scores["DIGITAL"] -= 0.08

        if year >= OBSERVATION_START_YEAR and branch_id is not None:
            state = self.get_branch_state(branch_id, year)
            substitution = np.clip(
                state["digital_substitution"], -2.5, 2.5
            )
            scores["BRANCH"] -= 0.28 * substitution
            scores["DIGITAL"] += 0.32 * substitution
            scores["REMOTE_ASSISTED"] += 0.08 * substitution

        scores = {
            k: v + self.rng.normal(0, 0.12)
            for k, v in scores.items()
        }
        probs = softmax([scores[c] for c in CHANNELS])
        return str(self.rng.choice(CHANNELS, p=probs))

    # -------------------------------------------------------------------------
    # Add / close
    # -------------------------------------------------------------------------

    def add_card(
        self,
        customer_id,
        product_id,
        issue_year,
        issue_channel,
        linked_account_id=None,
        status="ACTIVE",
        closing_year=np.nan,
    ):
        card = {
            "card_id": f"K{self.counter:07d}",
            "customer_id": customer_id,
            "product_id": product_id,
            "linked_account_id": linked_account_id,
            "issue_year": int(issue_year),
            "card_status": status,
            "closing_year": closing_year,
            "issue_channel": issue_channel,
        }
        self.counter += 1
        self.cards.append(card)
        self.portfolios[customer_id].append(card)

        if product_id == "P009":
            if linked_account_id in self.debit_account_used:
                raise RuntimeError(
                    f"Internal error: duplicate P009 relationship for {linked_account_id}"
                )
            self.debit_account_used.add(linked_account_id)

        return card

    @staticmethod
    def close_card(card, year):
        card["card_status"] = "CLOSED"
        card["closing_year"] = int(year)

    # -------------------------------------------------------------------------
    # P009 Debit
    # -------------------------------------------------------------------------

    def debit_adoption_score(self, row, account, year):
        base = DEBIT_BASE[str(account["product_id"])]

        relationship = float(row["_relationship_z"])
        digital = float(row["_digital_z"])

        existing_debit = len(
            self.active_cards(str(row.name), year, debit_only=True)
        )

        saturation = 1.30 * math.log1p(existing_debit)

        # Debit becomes more standard over time after launch.
        years_since_launch = max(0, year - PRODUCT_META["P009"]["launch_year"])
        technology = -0.95 + 1.15 * sigmoid((years_since_launch - 8.0) / 4.0)

        # Recently opened accounts are more likely to acquire debit near origination.
        lag = max(0, year - int(account["opening_year"]))
        lag_effect = 0.35 * math.exp(-lag / 3.5)

        score = (
            base
            + 0.30 * relationship
            + 0.10 * digital
            + technology
            + lag_effect
            - saturation
        )

        if year >= OBSERVATION_START_YEAR:
            state = self.get_branch_state(account["branch_id"], year)
            score += 0.10 * np.clip(
                state["digital_substitution"], -2.5, 2.5
            )
            score -= 0.08 * np.clip(
                state["customer_pressure"], -2.5, 2.5
            )

        score += self.rng.normal(0, 0.55)
        return score

    def debit_issue_probability(self, row, account, year):
        return float(np.clip(sigmoid(self.debit_adoption_score(row, account, year)), 0.02, 0.995))

    def choose_historical_debit_issue_year(self, row, account):
        low = max(
            int(row["registration_year"]),
            int(account["opening_year"]),
            PRODUCT_META["P009"]["launch_year"],
        )

        upper = 2020

        account_close = as_year(account["closing_year"])
        if account_close is not None:
            upper = min(upper, account_close)

        if str(row["customer_status"]) == "CLOSED":
            customer_close = as_year(row["closing_year"])
            if customer_close is not None:
                upper = min(upper, customer_close)

        if low > upper:
            return None

        # Most P009 relationships arise near account opening, with a smaller tail.
        max_lag = upper - low
        if max_lag == 0:
            return low

        if self.rng.random() < 0.72:
            lag = int(min(max_lag, self.rng.geometric(0.58) - 1))
        else:
            frac = self.rng.beta(1.4, 2.4)
            lag = int(round(frac * max_lag))

        return int(np.clip(low + lag, low, upper))

    def debit_survival_probability_to_2021(self, row, account, issue_year):
        age = 2021 - issue_year
        redundancy = len(
            [
                c for c in self.portfolios.get(str(row.name), [])
                if c["product_id"] == "P009" and c["issue_year"] <= 2020
            ]
        )

        score = (
            2.25
            - 0.38 * math.log1p(max(age, 0))
            + 0.28 * float(row["_relationship_z"])
            - 0.22 * math.log1p(redundancy)
            + self.rng.normal(0, 0.45)
        )
        return float(np.clip(sigmoid(score), 0.08, 0.992))

    def historical_debit_closing_year(self, row, account, issue_year):
        upper = 2020

        account_close = as_year(account["closing_year"])
        if account_close is not None:
            upper = min(upper, account_close)

        if str(row["customer_status"]) == "CLOSED":
            customer_close = as_year(row["closing_year"])
            if customer_close is not None:
                upper = min(upper, customer_close)

        upper = max(issue_year, upper)
        if upper == issue_year:
            return issue_year

        frac = self.rng.beta(2.2, 1.6)
        return issue_year + int(round(frac * (upper - issue_year)))

    def generate_pre_2021_debit(self):
        for account in self.accounts.itertuples(index=False):
            if account.product_id not in DEBIT_ACCOUNT_PRODUCTS:
                continue
            if int(account.opening_year) > 2020:
                continue

            row = self.customer_lookup.loc[account.customer_id]
            issue_year = self.choose_historical_debit_issue_year(
                row, pd.Series(account._asdict())
            )
            if issue_year is None:
                continue

            # One historical opportunity per eligible account. Probability is high,
            # but old/short-lived accounts can legitimately never receive P009.
            account_series = pd.Series(account._asdict())
            p_issue = self.debit_issue_probability(row, account_series, issue_year)
            if self.rng.random() >= p_issue:
                continue

            forced_closed = False
            account_close = as_year(account.closing_year)
            customer_close = as_year(row["closing_year"])

            if account_close is not None and account_close <= 2020:
                forced_closed = True
            if (
                str(row["customer_status"]) == "CLOSED"
                and customer_close is not None
                and customer_close <= 2020
            ):
                forced_closed = True

            survives = (
                False
                if forced_closed
                else self.rng.random()
                < self.debit_survival_probability_to_2021(
                    row, account_series, issue_year
                )
            )

            channel = self.choose_issue_channel(row, issue_year, "P009")

            if survives:
                self.add_card(
                    customer_id=account.customer_id,
                    product_id="P009",
                    linked_account_id=account.account_id,
                    issue_year=issue_year,
                    issue_channel=channel,
                )
            else:
                closing_year = self.historical_debit_closing_year(
                    row, account_series, issue_year
                )
                self.add_card(
                    customer_id=account.customer_id,
                    product_id="P009",
                    linked_account_id=account.account_id,
                    issue_year=issue_year,
                    issue_channel=channel,
                    status="CLOSED",
                    closing_year=closing_year,
                )

    # -------------------------------------------------------------------------
    # Credit appetite / P010-P011 acquisition
    # -------------------------------------------------------------------------

    def credit_base_score(self, row, year):
        appetite = float(row["_credit_appetite_centered"])
        income = float(row["_income_z"])
        relationship = float(row["_relationship_z"])

        tenure_years = max(0, year - int(row["registration_year"]))
        tenure_signal = math.log1p(tenure_years) / math.log1p(30)

        employment = EMPLOYMENT_CREDIT_EFFECT.get(
            str(row["employment_status"]), 0.0
        )

        return (
            -1.15
            + 1.45 * appetite
            + 0.40 * income
            + 0.30 * relationship
            + 0.15 * tenure_signal
            + employment
        )

    def annual_credit_issue_probability(self, row, year):
        if str(row["customer_type"]) != "INDIVIDUAL":
            return 0.0
        if year < PRODUCT_META["P010"]["launch_year"]:
            return 0.0

        customer_id = str(row.name)
        active_credit = len(self.active_cards(customer_id, year, credit_only=True))
        historical_credit = len(self.historical_credit_cards(customer_id, year))

        score = self.credit_base_score(row, year)

        # Additional credit is possible but increasingly difficult.
        score -= 1.35 * active_credit
        score -= 0.20 * max(0, historical_credit - active_credit)

        if active_credit >= 1:
            score += 0.35 * float(row["_credit_appetite_centered"])

        if year >= OBSERVATION_START_YEAR:
            state = self.get_branch_state(
                self.customer_branch_id(row), year
            )
            score -= 0.10 * np.clip(
                state["customer_pressure"], -2.5, 2.5
            )

        score += self.rng.normal(0, 0.75)
        return float(np.clip(sigmoid(score), 0.003, 0.90))

    def choose_credit_product(self, row, year):
        eligible = ["P010"]
        if year >= PRODUCT_META["P011"]["launch_year"]:
            eligible.append("P011")

        if len(eligible) == 1:
            return eligible[0]

        appetite = float(row["_credit_appetite_centered"])
        income = float(row["_income_z"])
        relationship = float(row["_relationship_z"])
        usd = float(row["_usd_z"])

        classic = (
            0.80
            + 0.45 * appetite
            + 0.15 * income
            + 0.20 * relationship
            + self.rng.normal(0, 0.70)
        )
        premium = (
            -0.65
            + 0.25 * appetite
            + 0.85 * income
            + 0.45 * relationship
            + 0.20 * usd
            + self.rng.normal(0, 0.70)
        )

        probs = softmax([classic, premium])
        return str(self.rng.choice(["P010", "P011"], p=probs))

    def historical_credit_count(self, row):
        if str(row["customer_type"]) != "INDIVIDUAL":
            return 0

        low = max(
            int(row["registration_year"]),
            PRODUCT_META["P010"]["launch_year"],
        )
        upper = 2020

        if str(row["customer_status"]) == "CLOSED":
            cy = as_year(row["closing_year"])
            if cy is not None:
                upper = min(upper, cy)

        if low > upper:
            return 0

        exposure = max(1, upper - low + 1)
        exposure_scale = min(1.0, math.log1p(exposure) / math.log1p(20))

        # Compressed "ever acquired credit by 2020" probability.
        score = (
            -0.65
            + 1.30 * float(row["_credit_appetite_centered"])
            + 0.35 * float(row["_income_z"])
            + 0.30 * float(row["_relationship_z"])
            + 0.55 * exposure_scale
            + self.rng.normal(0, 0.55)
        )
        if self.rng.random() >= sigmoid(score):
            return 0

        count = 1

        second_score = (
            -1.35
            + 0.95 * float(row["_credit_appetite_centered"])
            + 0.20 * float(row["_relationship_z"])
            + self.rng.normal(0, 0.55)
        )
        if self.rng.random() < sigmoid(second_score):
            count += 1

        third_score = (
            -2.55
            + 0.85 * float(row["_credit_appetite_centered"])
            + self.rng.normal(0, 0.55)
        )
        if count >= 2 and self.rng.random() < sigmoid(third_score):
            count += 1

        return count

    def choose_historical_credit_years(self, row, count):
        if count <= 0:
            return []

        low = max(
            int(row["registration_year"]),
            PRODUCT_META["P010"]["launch_year"],
        )
        upper = 2020

        if str(row["customer_status"]) == "CLOSED":
            cy = as_year(row["closing_year"])
            if cy is not None:
                upper = min(upper, cy)

        if low > upper:
            return []

        years = []
        floor = low
        for slot in range(count):
            if floor > upper:
                break

            if floor == upper:
                year = floor
            else:
                # First relationship tends to occur earlier; later cards can appear later.
                a, b = (1.35, 2.8) if slot == 0 else (1.7, 1.8)
                frac = self.rng.beta(a, b)
                year = floor + int(round(frac * (upper - floor)))

            year = int(np.clip(year, floor, upper))
            years.append(year)
            floor = min(upper + 1, year + 1)

        return years

    def credit_survival_probability_to_2021(self, row, product, issue_year):
        age = 2021 - issue_year
        score = (
            1.55
            - 0.34 * math.log1p(max(age, 0))
            + 0.36 * float(row["_relationship_z"])
            + 0.50 * float(row["_credit_appetite_centered"])
        )

        if product == "P011":
            score += 0.15

        score += self.rng.normal(0, 0.48)
        return float(np.clip(sigmoid(score), 0.05, 0.988))

    def historical_credit_closing_year(self, row, issue_year):
        upper = 2020
        if str(row["customer_status"]) == "CLOSED":
            cy = as_year(row["closing_year"])
            if cy is not None:
                upper = min(upper, cy)

        upper = max(issue_year, upper)
        if upper == issue_year:
            return issue_year

        frac = self.rng.beta(2.0, 1.8)
        return issue_year + int(round(frac * (upper - issue_year)))

    def generate_pre_2021_credit(self):
        for customer_id, row in self.customer_lookup.iterrows():
            if str(row["customer_type"]) != "INDIVIDUAL":
                continue
            if int(row["registration_year"]) > 2020:
                continue

            count = self.historical_credit_count(row)
            years = self.choose_historical_credit_years(row, count)

            provisional = []
            for issue_year in years:
                product = self.choose_credit_product(row, issue_year)
                channel = self.choose_issue_channel(row, issue_year, product)
                provisional.append((product, issue_year, channel))

            for product, issue_year, channel in provisional:
                customer_close = as_year(row["closing_year"])
                forced_closed = (
                    str(row["customer_status"]) == "CLOSED"
                    and customer_close is not None
                    and customer_close <= 2020
                )

                survives = (
                    False
                    if forced_closed
                    else self.rng.random()
                    < self.credit_survival_probability_to_2021(
                        row, product, issue_year
                    )
                )

                if survives:
                    self.add_card(
                        customer_id=customer_id,
                        product_id=product,
                        linked_account_id=None,
                        issue_year=issue_year,
                        issue_channel=channel,
                    )
                else:
                    cy = self.historical_credit_closing_year(row, issue_year)
                    self.add_card(
                        customer_id=customer_id,
                        product_id=product,
                        linked_account_id=None,
                        issue_year=issue_year,
                        issue_channel=channel,
                        status="CLOSED",
                        closing_year=cy,
                    )

    # -------------------------------------------------------------------------
    # 2021-2026 debit issuance
    # -------------------------------------------------------------------------

    def generate_observed_debit_issuance_for_customer(self, customer_id, row, year):
        frame = self.eligible_debit_accounts_for_customer(customer_id)
        if frame.empty:
            return

        for account in frame.itertuples(index=False):
            if account.account_id in self.debit_account_used:
                continue

            if int(account.opening_year) > year:
                continue

            account_close = as_year(account.closing_year)
            if account_close is not None and account_close < year:
                continue

            if year < PRODUCT_META["P009"]["launch_year"]:
                continue

            account_series = pd.Series(account._asdict())
            p_issue = self.debit_issue_probability(row, account_series, year)

            if self.rng.random() < p_issue:
                card = self.add_card(
                    customer_id=customer_id,
                    product_id="P009",
                    linked_account_id=account.account_id,
                    issue_year=year,
                    issue_channel=self.choose_issue_channel(
                        row, year, "P009",
                        branch_id=str(account.branch_id).zfill(3),
                    ),
                )

                # Account or customer can close in same year after card issuance.
                customer_close = as_year(row["closing_year"])
                forced_same_year = (
                    (account_close is not None and account_close == year)
                    or (
                        str(row["customer_status"]) == "CLOSED"
                        and customer_close is not None
                        and customer_close == year
                    )
                )
                if forced_same_year:
                    self.close_card(card, year)

    # -------------------------------------------------------------------------
    # 2021-2026 credit issuance
    # -------------------------------------------------------------------------

    def generate_observed_credit_issuance_for_customer(self, customer_id, row, year):
        if str(row["customer_type"]) != "INDIVIDUAL":
            return
        if year < PRODUCT_META["P010"]["launch_year"]:
            return

        if self.rng.random() >= self.annual_credit_issue_probability(row, year):
            return

        product = self.choose_credit_product(row, year)
        card = self.add_card(
            customer_id=customer_id,
            product_id=product,
            linked_account_id=None,
            issue_year=year,
            issue_channel=self.choose_issue_channel(
                row, year, product,
                branch_id=self.customer_branch_id(row),
            ),
        )

        customer_close = as_year(row["closing_year"])
        if (
            str(row["customer_status"]) == "CLOSED"
            and customer_close is not None
            and customer_close == year
        ):
            self.close_card(card, year)

    # -------------------------------------------------------------------------
    # Closure hazards
    # -------------------------------------------------------------------------

    def debit_close_probability(self, row, card, year):
        age = max(0, year - int(card["issue_year"]))
        active_debit = len(self.active_cards(card["customer_id"], year, debit_only=True))
        redundancy = max(0, active_debit - 1)

        score = (
            -3.55
            + 0.34 * math.log1p(age)
            - 0.32 * float(row["_relationship_z"])
            + 0.42 * math.log1p(redundancy)
        )

        if year >= OBSERVATION_START_YEAR:
            account = self.account_lookup.loc[card["linked_account_id"]]
            state = self.get_branch_state(account["branch_id"], year)
            score += 0.08 * np.clip(
                state["customer_pressure"], -2.5, 2.5
            )

        score += self.rng.normal(0, 0.40)
        return float(np.clip(sigmoid(score), 0.004, 0.45))

    def credit_close_probability(self, row, card, year):
        age = max(0, year - int(card["issue_year"]))
        active_credit = self.active_cards(card["customer_id"], year, credit_only=True)
        redundancy = max(0, len(active_credit) - 1)

        score = (
            -3.20
            + 0.48 * math.log1p(age)
            - 0.40 * float(row["_relationship_z"])
            - 0.55 * float(row["_credit_appetite_centered"])
            + 0.60 * math.log1p(redundancy)
        )

        if card["product_id"] == "P010":
            has_premium = any(
                c["product_id"] == "P011"
                and c["card_id"] != card["card_id"]
                and self.card_is_active_in_year(c, year)
                for c in self.portfolios.get(card["customer_id"], [])
            )
            if has_premium:
                score += 0.75

        if year >= OBSERVATION_START_YEAR:
            state = self.get_branch_state(
                self.customer_branch_id(row), year
            )
            score += 0.08 * np.clip(
                state["customer_pressure"], -2.5, 2.5
            )

        score += self.rng.normal(0, 0.45)
        return float(np.clip(sigmoid(score), 0.005, 0.55))

    def evaluate_closures_for_customer(self, customer_id, row, year):
        customer_close = as_year(row["closing_year"])

        for card in list(self.active_cards(customer_id, year)):
            if as_year(card["closing_year"]) is not None:
                continue

            forced_customer = (
                str(row["customer_status"]) == "CLOSED"
                and customer_close is not None
                and customer_close == year
            )

            if card["product_id"] == "P009":
                account = self.account_lookup.loc[card["linked_account_id"]]
                account_close = as_year(account["closing_year"])

                forced_account = (
                    account_close is not None and account_close == year
                )

                close = (
                    forced_customer
                    or forced_account
                    or self.rng.random() < self.debit_close_probability(row, card, year)
                )
            else:
                close = (
                    forced_customer
                    or self.rng.random() < self.credit_close_probability(row, card, year)
                )

            if close:
                self.close_card(card, year)

    # -------------------------------------------------------------------------
    # Main observed period
    # -------------------------------------------------------------------------

    def generate_observed_period(self):
        for year in range(OBSERVATION_START_YEAR, CURRENT_YEAR + 1):
            for customer_id, row in self.customer_lookup.iterrows():
                if not self.customer_alive_in_year(row, year):
                    continue

                self.generate_observed_debit_issuance_for_customer(
                    customer_id, row, year
                )
                self.generate_observed_credit_issuance_for_customer(
                    customer_id, row, year
                )

                # Closure after issuance permits same-year issue/close relationships.
                self.evaluate_closures_for_customer(customer_id, row, year)

    # -------------------------------------------------------------------------
    # Final structural reconciliation
    # -------------------------------------------------------------------------

    def enforce_final_lifecycle_integrity(self):
        """
        Structural, not behavioral calibration.

        Enforces only relationships that MUST be true:
        - closed customer => no active cards
        - active P009 cannot outlive a closed linked account
        - closure must not occur after customer/account closure
        """
        for card in self.cards:
            row = self.customer_lookup.loc[card["customer_id"]]
            customer_close = as_year(row["closing_year"])

            max_close = CURRENT_YEAR

            if str(row["customer_status"]) == "CLOSED" and customer_close is not None:
                max_close = min(max_close, customer_close)

            if card["product_id"] == "P009":
                account = self.account_lookup.loc[card["linked_account_id"]]
                account_close = as_year(account["closing_year"])
                if account_close is not None:
                    max_close = min(max_close, account_close)

            existing_close = as_year(card["closing_year"])

            must_close = (
                (str(row["customer_status"]) == "CLOSED" and customer_close is not None)
                or (
                    card["product_id"] == "P009"
                    and as_year(
                        self.account_lookup.loc[card["linked_account_id"], "closing_year"]
                    )
                    is not None
                )
            )

            if must_close:
                # Only adjust when structural horizon requires it.
                required_close = max(int(card["issue_year"]), max_close)
                if existing_close is None or existing_close > required_close:
                    card["card_status"] = "CLOSED"
                    card["closing_year"] = required_close

    # -------------------------------------------------------------------------
    # DataFrame
    # -------------------------------------------------------------------------

    def dataframe(self):
        columns = [
            "card_id",
            "customer_id",
            "product_id",
            "linked_account_id",
            "issue_year",
            "card_status",
            "closing_year",
            "issue_channel",
        ]
        df = pd.DataFrame(self.cards, columns=columns)
        if not df.empty:
            df["closing_year"] = pd.array(df["closing_year"], dtype="Int64")
        return df


# =============================================================================
# Validation
# =============================================================================

def validate_output(cards, customers, accounts, products):
    errors = []

    if cards.empty:
        errors.append("cards output is empty")
        raise AssertionError("VALIDATION FAILED:\n- " + "\n- ".join(errors))

    cust = customers.set_index("customer_id")
    acct = accounts.set_index("account_id")
    prod = products.set_index("product_id")

    # 1. PK
    if cards["card_id"].isna().any():
        errors.append("NULL card_id")
    if cards["card_id"].duplicated().any():
        errors.append("duplicate card_id")
    if not cards["card_id"].str.match(r"^K\d{7}$").all():
        errors.append("invalid card_id format")

    # 2. FK / products
    if not set(cards["customer_id"]).issubset(set(customers["customer_id"])):
        errors.append("unknown customer_id")
    if not cards["product_id"].isin(CARD_PRODUCTS).all():
        errors.append("invalid product_id")

    # 3. Product target compatibility
    customer_type = cards["customer_id"].map(cust["customer_type"])
    if (
        customer_type.eq("BUSINESS")
        & cards["product_id"].isin(["P010", "P011"])
    ).any():
        errors.append("BUSINESS customer owns individual-only credit card")

    # 4. Temporal issue constraints
    launch_map = {
        p: int(prod.loc[p, "launch_year"])
        for p in CARD_PRODUCTS
    }
    launch_year = cards["product_id"].map(launch_map)
    if (cards["issue_year"] < launch_year).any():
        errors.append("card issued before product launch")

    registration = cards["customer_id"].map(cust["registration_year"]).astype(int)
    if (cards["issue_year"] < registration).any():
        errors.append("card issued before customer registration")

    if (cards["issue_year"] > CURRENT_YEAR).any():
        errors.append("issue_year after current year")

    # 5. Linked account logic
    debit = cards["product_id"].eq("P009")
    credit = cards["product_id"].isin(["P010", "P011"])

    if cards.loc[debit, "linked_account_id"].isna().any():
        errors.append("P009 missing linked_account_id")
    if cards.loc[credit, "linked_account_id"].notna().any():
        errors.append("credit card has linked_account_id")

    debit_cards = cards.loc[debit].copy()

    if not set(debit_cards["linked_account_id"]).issubset(set(accounts["account_id"])):
        errors.append("unknown linked_account_id")

    if debit_cards["linked_account_id"].duplicated().any():
        errors.append("more than one P009 relationship for same linked account")

    if not debit_cards.empty:
        linked_customer = debit_cards["linked_account_id"].map(acct["customer_id"])
        if (linked_customer != debit_cards["customer_id"]).any():
            errors.append("P009 linked account belongs to another customer")

        linked_product = debit_cards["linked_account_id"].map(acct["product_id"])
        if not linked_product.isin(DEBIT_ACCOUNT_PRODUCTS).all():
            errors.append("P009 linked to ineligible account product")

        linked_open = debit_cards["linked_account_id"].map(acct["opening_year"]).astype(int)
        if (debit_cards["issue_year"] < linked_open).any():
            errors.append("P009 issued before linked account opening")

    # 6. Status / closure
    if not cards["card_status"].isin(["ACTIVE", "CLOSED"]).all():
        errors.append("invalid card_status")

    if cards.loc[cards["card_status"].eq("ACTIVE"), "closing_year"].notna().any():
        errors.append("ACTIVE card has closing_year")

    if cards.loc[cards["card_status"].eq("CLOSED"), "closing_year"].isna().any():
        errors.append("CLOSED card missing closing_year")

    closed = cards["closing_year"].notna()
    if (
        cards.loc[closed, "closing_year"].astype(int)
        < cards.loc[closed, "issue_year"].astype(int)
    ).any():
        errors.append("closing_year before issue_year")

    if (
        pd.to_numeric(cards["closing_year"], errors="coerce")
        .dropna()
        .gt(CURRENT_YEAR)
        .any()
    ):
        errors.append("closing_year after current year")

    # 7. Closed customers
    customer_status = cards["customer_id"].map(cust["customer_status"])
    customer_close = pd.to_numeric(
        cards["customer_id"].map(cust["closing_year"]),
        errors="coerce",
    )
    card_close = pd.to_numeric(cards["closing_year"], errors="coerce")

    if (
        customer_status.eq("CLOSED")
        & cards["card_status"].eq("ACTIVE")
    ).any():
        errors.append("closed customer has active card")

    if (
        customer_status.eq("CLOSED")
        & card_close.notna()
        & customer_close.notna()
        & (card_close > customer_close)
    ).any():
        errors.append("card closes after customer")

    # 8. Debit lifecycle integrity
    if not debit_cards.empty:
        account_status = debit_cards["linked_account_id"].map(acct["account_status"])
        card_status = debit_cards["card_status"]

        if (
            account_status.eq("CLOSED")
            & card_status.eq("ACTIVE")
        ).any():
            errors.append("active P009 linked to closed account")

        debit_close = pd.to_numeric(debit_cards["closing_year"], errors="coerce")
        account_close = pd.to_numeric(
            debit_cards["linked_account_id"].map(acct["closing_year"]),
            errors="coerce",
        )

        if (
            account_close.notna()
            & debit_close.notna()
            & (debit_close > account_close)
        ).any():
            errors.append("P009 closes after linked account")

    # 9. Channel
    if not cards["issue_channel"].isin(CHANNELS).all():
        errors.append("invalid issue_channel")

    if errors:
        raise AssertionError("VALIDATION FAILED:\n- " + "\n- ".join(errors))

    print("\nVALIDATION: PASS")


# =============================================================================
# Audit
# =============================================================================

def audit(cards, customers, accounts, generator):
    print("\n" + "=" * 84)
    print("BTYT CARDS — DEVELOPMENT AUDIT")
    print("=" * 84)

    print(f"Customers in development universe: {len(customers):,}")
    print(f"Frozen accounts:                  {len(accounts):,}")
    print(f"Cards generated:                  {len(cards):,}")

    per_holder = cards.groupby("customer_id").size()
    holders = len(per_holder)
    print(f"\nCustomers with >=1 card: {holders:,} ({holders / len(customers):.2%})")
    if holders:
        print(f"Mean cards per cardholder: {per_holder.mean():.2f}")
        print(f"Median cards per cardholder: {per_holder.median():.0f}")
        print(f"P95 cards per cardholder: {per_holder.quantile(.95):.0f}")
        print(f"Maximum cards per cardholder: {per_holder.max():.0f}")

    active_cards = cards[cards["card_status"].eq("ACTIVE")]
    active_holders = active_cards["customer_id"].nunique()
    print(
        f"Customers with >=1 ACTIVE card: {active_holders:,} "
        f"({active_holders / len(customers):.2%})"
    )

    print("\nCards by product:")
    print(cards["product_id"].value_counts().sort_index().to_string())

    print("\nCards by status (%):")
    print(
        cards["card_status"]
        .value_counts(normalize=True)
        .mul(100)
        .round(2)
        .to_string()
    )

    # Debit coverage among customers with an ACTIVE eligible account.
    eligible_active_accounts = accounts[
        accounts["product_id"].isin(DEBIT_ACCOUNT_PRODUCTS)
        & accounts["account_status"].eq("ACTIVE")
    ]
    eligible_customers = set(eligible_active_accounts["customer_id"])

    active_debit_customers = set(
        cards.loc[
            cards["product_id"].eq("P009")
            & cards["card_status"].eq("ACTIVE"),
            "customer_id",
        ]
    )

    if eligible_customers:
        covered = len(eligible_customers & active_debit_customers)
        print(
            "\nCustomers with ACTIVE eligible account and ACTIVE debit: "
            f"{covered:,}/{len(eligible_customers):,} "
            f"({covered / len(eligible_customers):.2%})"
        )

    # Credit portfolio
    credit = cards[cards["product_id"].isin(CREDIT_PRODUCTS)]
    active_credit = credit[credit["card_status"].eq("ACTIVE")]

    credit_holders = credit["customer_id"].nunique()
    active_credit_holders = active_credit["customer_id"].nunique()
    print(
        f"\nCustomers with any credit-card history: {credit_holders:,} "
        f"({credit_holders / len(customers):.2%})"
    )
    print(
        f"Customers with ACTIVE credit card:      {active_credit_holders:,} "
        f"({active_credit_holders / len(customers):.2%})"
    )

    classic_holders = set(
        active_credit.loc[active_credit["product_id"].eq("P010"), "customer_id"]
    )
    premium_holders = set(
        active_credit.loc[active_credit["product_id"].eq("P011"), "customer_id"]
    )
    print(f"ACTIVE Classic holders: {len(classic_holders):,}")
    print(f"ACTIVE Premium holders: {len(premium_holders):,}")
    print(f"ACTIVE Classic + Premium coexistence: {len(classic_holders & premium_holders):,}")

    if active_credit_holders:
        credit_counts = active_credit.groupby("customer_id").size()
        buckets = pd.cut(
            credit_counts,
            bins=[0, 1, 2, 3, np.inf],
            labels=["1", "2", "3", "4+"],
        )
        print("\nACTIVE credit cards per credit-card holder:")
        print(buckets.value_counts().sort_index().to_string())

    print("\nIssuance by year:")
    print(cards["issue_year"].value_counts().sort_index().to_string())

    observed_closures = cards[
        pd.to_numeric(cards["closing_year"], errors="coerce").between(2021, 2026)
    ]
    print("\nObserved closures 2021-2026:")
    print(
        observed_closures["closing_year"]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print("\nIssue channel by year (%):")
    print(
        pd.crosstab(
            cards["issue_year"],
            cards["issue_channel"],
            normalize="index",
        )
        .mul(100)
        .round(1)
        .tail(20)
        .to_string()
    )

    print("\nIssue channel by product (%):")
    print(
        pd.crosstab(
            cards["product_id"],
            cards["issue_channel"],
            normalize="index",
        )
        .mul(100)
        .round(1)
        .to_string()
    )

    # Debit lag
    debit = cards[cards["product_id"].eq("P009")].copy()
    if not debit.empty:
        acct_open = accounts.set_index("account_id")["opening_year"]
        debit["account_opening_year"] = debit["linked_account_id"].map(acct_open)
        debit["issue_lag_years"] = debit["issue_year"] - debit["account_opening_year"]

        print("\nDebit issuance lag vs linked-account opening:")
        print(debit["issue_lag_years"].describe(percentiles=[.25, .5, .75, .9, .95]).round(2).to_string())

        linked_product = accounts.set_index("account_id")["product_id"]
        debit["linked_product"] = debit["linked_account_id"].map(linked_product)
        print("\nP009 relationships by linked account product:")
        print(debit["linked_product"].value_counts().sort_index().to_string())

    # Latent audit: never exported.
    latent = generator.customers.set_index("customer_id")
    customer_credit_active = pd.Series(
        customers["customer_id"].isin(set(active_credit["customer_id"])).to_numpy(),
        index=customers["customer_id"],
    )

    appetite = latent["_credit_appetite"]
    audit_frame = pd.DataFrame({
        "credit_appetite": appetite,
        "has_active_credit": appetite.index.isin(set(active_credit["customer_id"])),
        "income": pd.to_numeric(latent["monthly_income"], errors="coerce"),
        "relationship_z": latent["_relationship_z"],
    })

    print("\nCredit appetite distribution:")
    print(
        audit_frame["credit_appetite"]
        .describe(percentiles=[.1, .25, .5, .75, .9])
        .round(3)
        .to_string()
    )

    print("\nMean credit appetite by ACTIVE credit ownership:")
    print(
        audit_frame.groupby("has_active_credit")["credit_appetite"]
        .agg(["count", "mean", "median"])
        .round(3)
        .to_string()
    )

    ind_ids = set(
        generator.customers.loc[
            generator.customers["customer_type"].eq("INDIVIDUAL"),
            "customer_id",
        ]
    )
    classic_any = set(cards.loc[cards["product_id"].eq("P010"), "customer_id"])
    premium_any = set(cards.loc[cards["product_id"].eq("P011"), "customer_id"])

    categories = []
    for cid in generator.customers["customer_id"]:
        if cid not in ind_ids:
            categories.append("BUSINESS")
        elif cid in classic_any and cid in premium_any:
            categories.append("CLASSIC+PREMIUM")
        elif cid in premium_any:
            categories.append("PREMIUM_ONLY")
        elif cid in classic_any:
            categories.append("CLASSIC_ONLY")
        else:
            categories.append("NO_CREDIT")

    income_audit = generator.customers[["customer_id", "monthly_income"]].copy()
    income_audit["credit_portfolio"] = categories
    income_audit["monthly_income"] = pd.to_numeric(
        income_audit["monthly_income"], errors="coerce"
    )

    print("\nIncome by credit portfolio (INDIVIDUAL only):")
    temp = income_audit[income_audit["credit_portfolio"].ne("BUSINESS")]
    print(
        temp.groupby("credit_portfolio")["monthly_income"]
        .agg(["count", "median", "mean"])
        .round(0)
        .to_string()
    )

    inherited = cards[
        (cards["issue_year"] <= 2020)
        & (
            cards["closing_year"].isna()
            | (pd.to_numeric(cards["closing_year"], errors="coerce") >= 2021)
        )
    ]
    print(f"\nInherited card relationships entering 2021: {len(inherited):,}")



def audit_branch_state_integration(cards, customers, accounts, branch_state):
    """
    Audit the intentionally narrow branch-state integration in Cards.
    """
    state = branch_state.copy()
    state["branch_id"] = state["branch_id"].astype(str).str.zfill(3)
    state["year"] = pd.to_numeric(state["year"], errors="coerce").astype("Int64")

    observed = cards.loc[
        cards["issue_year"].between(OBSERVATION_START_YEAR, CURRENT_YEAR)
    ].copy()
    if observed.empty:
        return

    account_branch = accounts.set_index("account_id")["branch_id"]
    customer_branch = customers.set_index("customer_id")["primary_branch_id"]

    observed["branch_id"] = np.where(
        observed["product_id"].eq(DEBIT_PRODUCT),
        observed["linked_account_id"].map(account_branch),
        observed["customer_id"].map(customer_branch),
    )
    observed["branch_id"] = observed["branch_id"].astype(str).str.zfill(3)

    merged = observed.merge(
        state[
            [
                "branch_id", "year",
                "customer_pressure", "digital_substitution",
            ]
        ],
        left_on=["branch_id", "issue_year"],
        right_on=["branch_id", "year"],
        how="left",
        validate="many_to_one",
    )

    print("\n" + "=" * 84)
    print("BRANCH-STATE INTEGRATION AUDIT — CARDS")
    print("=" * 84)
    print(
        f"Observed card issuance linked to branch state: "
        f"{merged['year'].notna().mean():.2%}"
    )

    print("\nMean branch state at card issuance by channel:")
    print(
        merged.groupby("issue_channel")[
            ["customer_pressure", "digital_substitution"]
        ]
        .mean()
        .round(3)
        .to_string()
    )

    print("\nMean branch state at card issuance by product:")
    print(
        merged.groupby("product_id")[
            ["customer_pressure", "digital_substitution"]
        ]
        .mean()
        .round(3)
        .to_string()
    )


# =============================================================================
# Main
# =============================================================================

def main():
    print("Loading BTYT inputs...")
    customers, accounts, products, branch_state = load_inputs()
    validate_inputs(customers, accounts, products, branch_state)

    print(f"Customers loaded: {len(customers):,}")
    print(f"Accounts loaded:  {len(accounts):,}")
    print(
        f"Development mode: {DEVELOPMENT_MODE} | "
        f"Customer sample size: {DEVELOPMENT_CUSTOMERS:,}"
    )

    generator = CardsGenerator(customers, accounts, branch_state)

    print("\nGenerating compressed pre-2021 debit-card state...")
    generator.generate_pre_2021_debit()

    print("Generating compressed pre-2021 credit-card state...")
    generator.generate_pre_2021_credit()

    print("Generating detailed 2021-2026 card evolution...")
    generator.generate_observed_period()

    print("Enforcing final structural lifecycle integrity...")
    generator.enforce_final_lifecycle_integrity()

    cards = generator.dataframe()

    validate_output(cards, customers, accounts, products)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cards.to_csv(OUTPUT_PATH, index=False)

    audit(cards, customers, accounts, generator)
    audit_branch_state_integration(
        cards, customers, accounts, branch_state
    )

    print(f"\nSaved: {OUTPUT_PATH}")
    print(f"Shape: {cards.shape}")


if __name__ == "__main__":
    main()
