from __future__ import annotations

import math
from collections import Counter, defaultdict
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from scripts.core.paths import GENERATED_CORE_DIR
from scripts.core.rng import make_rng
from scripts.core.world import load_world


WORLD = load_world()

CURRENT_YEAR = WORLD.end_date.year
OBSERVATION_START_YEAR = WORLD.start_date.year

RNG_NAMESPACE = "accounts"
RNG_STREAM_LATENT_BASE = 100_000
RNG_STREAM_LIFECYCLE_BASE = 200_000

CUSTOMER_CHUNK_SIZE = 5_000
PARQUET_COMPRESSION = "zstd"
WRITE_COMPATIBILITY_CSV = True

CUSTOMERS_PARQUET_PATH = GENERATED_CORE_DIR / "customers.parquet"
CUSTOMERS_CSV_PATH = GENERATED_CORE_DIR / "customers.csv"
PRODUCTS_PATH = GENERATED_CORE_DIR / "products.csv"
BRANCHES_PATH = GENERATED_CORE_DIR / "branches.csv"

PARQUET_OUTPUT_PATH = GENERATED_CORE_DIR / "accounts.parquet"
CSV_OUTPUT_PATH = GENERATED_CORE_DIR / "accounts.csv"

ACCOUNT_PRODUCTS = ["P001", "P002", "P003", "P004", "P005", "P006", "P007", "P008"]

PRODUCT_META = {
    "P001": {"launch_year": 1969, "target": "BOTH"},
    "P002": {"launch_year": 1976, "target": "BOTH"},
    "P003": {"launch_year": 1969, "target": "BOTH"},
    "P004": {"launch_year": 1982, "target": "BOTH"},
    "P005": {"launch_year": 2001, "target": "INDIVIDUAL"},
    "P006": {"launch_year": 2014, "target": "INDIVIDUAL"},
    "P007": {"launch_year": 1971, "target": "BOTH"},
    "P008": {"launch_year": 1978, "target": "BOTH"},
}

BASE_UTILITY = {
    "INDIVIDUAL": {
        "P001": 1.20, "P002": 0.15, "P003": 0.00, "P004": -0.65,
        "P005": 0.55, "P006": -0.45, "P007": -0.55, "P008": -0.95,
    },
    "BUSINESS": {
        "P001": 0.55, "P002": 0.10, "P003": 1.10, "P004": 0.35,
        "P007": -0.35, "P008": -0.65,
    },
}

STRENGTH = {"WEAK": 0.18, "MODERATE": 0.42, "STRONG": 0.82}
REPEAT_PENALTY = {
    "P001": STRENGTH["MODERATE"], "P002": STRENGTH["MODERATE"],
    "P003": STRENGTH["MODERATE"], "P004": STRENGTH["MODERATE"],
    "P005": STRENGTH["STRONG"], "P006": STRENGTH["STRONG"],
    "P007": STRENGTH["WEAK"], "P008": STRENGTH["WEAK"],
}

USD_PRODUCTS = {"P002", "P004", "P008"}
FIXED_TERM_PRODUCTS = {"P007", "P008"}


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -12, 12)))


def softmax(values):
    x = np.asarray(values, dtype=float)
    x -= x.max()
    e = np.exp(x)
    return e / e.sum()


def zscore(series):
    s = pd.to_numeric(series, errors="coerce")
    if s.notna().sum() == 0:
        return pd.Series(0.0, index=s.index)
    s = s.fillna(s.median())
    sd = s.std(ddof=0)
    return (s - s.mean()) / sd if np.isfinite(sd) and sd else pd.Series(0.0, index=s.index)


def log_zscore(series):
    return zscore(np.log1p(pd.to_numeric(series, errors="coerce").clip(lower=0)))


def _normalize_id_series(series: pd.Series, width: int | None = None) -> pd.Series:
    """Normalize identifier columns loaded from CSV or Parquet."""
    normalized = (
        series.astype("string")
        .str.replace(r"\\.0$", "", regex=True)
    )
    if width is not None:
        normalized = normalized.str.zfill(width)
    return normalized


def load_inputs():
    """Load canonical BTYT inputs using centralized paths."""
    if CUSTOMERS_PARQUET_PATH.exists():
        customers_source = CUSTOMERS_PARQUET_PATH
        customers = pd.read_parquet(CUSTOMERS_PARQUET_PATH)
    elif CUSTOMERS_CSV_PATH.exists():
        customers_source = CUSTOMERS_CSV_PATH
        customers = pd.read_csv(
            CUSTOMERS_CSV_PATH,
            dtype={"customer_id": str, "primary_branch_id": str},
        )
    else:
        raise FileNotFoundError(
            "Missing canonical BTYT customers input. Expected one of:\n"
            f"- {CUSTOMERS_PARQUET_PATH}\n"
            f"- {CUSTOMERS_CSV_PATH}"
        )

    required_paths = {
        "products": PRODUCTS_PATH,
        "branches": BRANCHES_PATH,
    }
    missing_paths = [path for path in required_paths.values() if not path.exists()]
    if missing_paths:
        raise FileNotFoundError(
            "Missing canonical BTYT input file(s):\n"
            + "\n".join(str(path) for path in missing_paths)
        )

    products = pd.read_csv(PRODUCTS_PATH, dtype={"product_id": str})
    branches = pd.read_csv(
        BRANCHES_PATH,
        dtype={"branch_id": str, "parent_branch_id": str},
    )

    customers["customer_id"] = _normalize_id_series(customers["customer_id"])
    customers["primary_branch_id"] = _normalize_id_series(
        customers["primary_branch_id"],
        width=3,
    )
    branches["branch_id"] = _normalize_id_series(
        branches["branch_id"],
        width=3,
    )
    if "parent_branch_id" in branches.columns:
        branches["parent_branch_id"] = _normalize_id_series(
            branches["parent_branch_id"],
            width=3,
        )

    customers = customers.sort_values("customer_id").reset_index(drop=True)

    if len(customers) != WORLD.customer_count:
        raise ValueError(
            "Canonical customers population does not match world configuration: "
            f"expected {WORLD.customer_count:,}, found {len(customers):,} "
            f"in {customers_source}."
        )

    return customers, products, branches, customers_source


def validate_inputs(customers, products, branches):
    required = {
        "customer_id", "customer_type", "birth_year", "residence_department",
        "residence_locality", "primary_branch_id", "registration_year",
        "customer_status", "closing_year", "employment_status", "monthly_income",
        "business_sector", "company_size", "foundation_year", "annual_revenue",
    }
    missing = required - set(customers.columns)
    if missing:
        raise ValueError(f"customers input missing columns: {sorted(missing)}")
    if customers["customer_id"].duplicated().any():
        raise ValueError("Duplicate customer_id.")
    if set(ACCOUNT_PRODUCTS) - set(products["product_id"]):
        raise ValueError("One or more P001-P008 products are missing.")
    if branches["branch_id"].duplicated().any():
        raise ValueError("Duplicate branch_id.")
    if set(customers["primary_branch_id"].dropna()) - set(branches["branch_id"]):
        raise ValueError("Unknown primary_branch_id.")


class AccountsGenerator:
    def __init__(self, customers, branches):
        self.customers = customers.copy()
        self.branches = branches.copy()
        self.accounts = []
        self.portfolios = defaultdict(list)
        self.counter = 1
        self.rng = None
        self.prepare_signals()
        self.generate_latents()

    def _customer_stream(self, customer_id: str, base_stream: int) -> int:
        """Build a deterministic stream id from a canonical customer identifier."""
        digits = "".join(ch for ch in str(customer_id) if ch.isdigit())
        if not digits:
            raise ValueError(
                f"customer_id must contain digits for deterministic RNG: {customer_id}"
            )
        return base_stream + int(digits)

    def _make_customer_rng(
        self,
        customer_id: str,
        base_stream: int,
    ) -> np.random.Generator:
        """Create a deterministic RNG for one customer inside the accounts namespace."""
        return make_rng(
            world_seed=WORLD.seed,
            namespace=RNG_NAMESPACE,
            stream=self._customer_stream(customer_id, base_stream),
        )

    def prepare_signals(self):
        c = self.customers
        for col in ["registration_year", "birth_year", "closing_year", "foundation_year"]:
            c[col] = pd.to_numeric(c[col], errors="coerce")

        c["_tenure_z"] = log_zscore(np.maximum(0, CURRENT_YEAR - c["registration_year"]))
        c["_income_z"] = 0.0
        c["_revenue_z"] = 0.0

        ind = c["customer_type"].eq("INDIVIDUAL")
        bus = c["customer_type"].eq("BUSINESS")
        if ind.any():
            c.loc[ind, "_income_z"] = log_zscore(c.loc[ind, "monthly_income"])
        if bus.any():
            c.loc[bus, "_revenue_z"] = log_zscore(c.loc[bus, "annual_revenue"])

        dep = c["residence_department"].fillna("").str.upper()
        loc = c["residence_locality"].fillna("").str.upper()
        c["_border"] = (
            dep.isin(["ARTIGAS", "RIVERA", "CERRO LARGO", "ROCHA", "SALTO"])
            | loc.str.contains("CHUY|RIO BRANCO|RÍO BRANCO|ACEGUA|ACEGUÁ", regex=True)
        ).astype(float)
        c["_tourism"] = (
            dep.isin(["MALDONADO", "ROCHA"])
            | loc.str.contains("PUNTA DEL ESTE|PIRIAPOLIS|PIRIÁPOLIS|LA PALOMA", regex=True)
        ).astype(float)

    def generate_latents(self):
        """
        Generate persistent customer-level account affinities.

        Latent draws use a customer-specific stream so changing chunk boundaries
        does not change customer-level stochastic behavior.
        """
        c = self.customers
        bus = c["customer_type"].eq("BUSINESS")
        economic = np.where(bus, c["_revenue_z"], c["_income_z"])

        common = np.zeros(len(c), dtype=float)
        noises = np.zeros((5, len(c)), dtype=float)

        for position, customer_id in enumerate(c["customer_id"].astype(str)):
            rng = self._make_customer_rng(
                customer_id,
                RNG_STREAM_LATENT_BASE,
            )
            common[position] = rng.normal(0, 1)
            noises[:, position] = rng.normal(0, 1, 5)

        depth = STRENGTH["STRONG"] * c["_tenure_z"] + STRENGTH["MODERATE"] * economic
        c["_depth"] = np.exp(
            np.clip(
                0.30 * (depth + .25 * common + .45 * noises[0]),
                -1,
                1,
            )
        )

        usd = (
            STRENGTH["STRONG"] * economic
            + STRENGTH["MODERATE"] * c["_border"]
            + STRENGTH["WEAK"] * c["_tourism"]
            + STRENGTH["WEAK"]
            * c["employment_status"].fillna("").eq("SELF_EMPLOYED")
        )
        c["_usd"] = sigmoid(
            .70 * usd + .25 * common + .80 * noises[1]
        )

        age = CURRENT_YEAR - c["birth_year"].fillna(CURRENT_YEAR - 40)
        lifecycle = np.where(
            (age >= 35) & (age <= 70),
            .5,
            np.where(age < 25, -.5, 0),
        )
        stability = c["employment_status"].map(
            {
                "EMPLOYED": .5,
                "SELF_EMPLOYED": .1,
                "RETIRED": .4,
                "STUDENT": -.6,
                "UNEMPLOYED": -.7,
                "OTHER": 0,
            }
        ).fillna(0)
        c["_savings"] = sigmoid(
            STRENGTH["MODERATE"] * economic
            + STRENGTH["MODERATE"] * stability
            + STRENGTH["MODERATE"] * lifecycle
            + STRENGTH["WEAK"] * c["_tenure_z"]
            + .20 * common
            + noises[2]
        )

        emp = c["employment_status"].fillna("")
        trans = (
            np.where(emp.eq("SELF_EMPLOYED"), STRENGTH["STRONG"], 0)
            + np.where(emp.eq("EMPLOYED"), STRENGTH["MODERATE"], 0)
            - np.where(emp.eq("STUDENT"), STRENGTH["MODERATE"], 0)
            - np.where(emp.eq("RETIRED"), STRENGTH["MODERATE"], 0)
        )
        size = c["company_size"].fillna("").map(
            {"MICRO": -.2, "SMALL": .1, "MEDIUM": .4, "LARGE": .7}
        ).fillna(0)
        trans += bus * (
            .55
            + STRENGTH["MODERATE"] * economic
            + STRENGTH["MODERATE"] * size
        )
        c["_transactional"] = sigmoid(
            trans + .15 * common + .85 * noises[3]
        )

        age_signal = np.clip((45 - age) / 20, -1.5, 1.5)
        recent = np.clip((c["registration_year"] - 2010) / 12, -1.5, 1.5)
        c["_digital"] = sigmoid(
            STRENGTH["STRONG"] * age_signal
            + STRENGTH["MODERATE"] * recent
            + .15 * common
            + .90 * noises[4]
        )

    def participation_probability(self, row):
        tenure = max(0, OBSERVATION_START_YEAR - int(row.registration_year))
        score = 2.15 + STRENGTH["STRONG"] * math.log1p(tenure) / math.log1p(30)
        score += .75 * math.log(max(float(row._depth), 1e-6))
        if row.customer_type == "INDIVIDUAL":
            emp = {
                "EMPLOYED": .55, "SELF_EMPLOYED": .50, "RETIRED": .35,
                "OTHER": .10, "UNEMPLOYED": -.20, "STUDENT": -.45,
            }.get(str(row.employment_status), 0)
            score += STRENGTH["MODERATE"] * emp
            score += STRENGTH["MODERATE"] * float(row._income_z) * .35
        else:
            score += .35 + STRENGTH["MODERATE"] * float(row._revenue_z) * .30
        score += self.rng.normal(0, .45)
        return float(np.clip(sigmoid(score), .08, .995))

    def historical_count(self, row):
        tenure = max(0, OBSERVATION_START_YEAR - int(row.registration_year))
        mu = .30 + .85 * math.log1p(tenure) / math.log1p(25)
        mu *= float(row._depth)
        if row.customer_type == "BUSINESS":
            mu *= 2.45
        else:
            mu *= 1 + np.clip(.12 * float(row._income_z), -.20, .35)
        mu = float(np.clip(mu, .10, 3.50))
        dispersion = 1.7
        p = dispersion / (dispersion + mu)
        return min(1 + int(self.rng.negative_binomial(dispersion, p)), 10)

    def eligible_products(self, row, year):
        return [
            p for p in ACCOUNT_PRODUCTS
            if PRODUCT_META[p]["launch_year"] <= year
            and PRODUCT_META[p]["target"] in {"BOTH", row.customer_type}
        ]

    def product_utility(self, row, product, year, owned):
        u = BASE_UTILITY[row.customer_type].get(product, -10)
        usd = 2 * (float(row._usd) - .5)
        sav = 2 * (float(row._savings) - .5)
        trans = 2 * (float(row._transactional) - .5)

        if product in USD_PRODUCTS:
            u += STRENGTH["STRONG"] * usd
        if product in {"P001", "P002"}:
            u += STRENGTH["WEAK"] * sav
        if product in FIXED_TERM_PRODUCTS:
            u += STRENGTH["STRONG"] * sav
            econ = float(row._revenue_z if row.customer_type == "BUSINESS" else row._income_z)
            u += STRENGTH["MODERATE"] * np.clip(econ, -2, 2) * .35
        if product in {"P003", "P004"}:
            u += STRENGTH["STRONG"] * trans

        if row.customer_type == "INDIVIDUAL":
            emp = str(row.employment_status)
            if product == "P005":
                u += 1.25 if emp == "EMPLOYED" else (-1.40 if emp in {"STUDENT", "UNEMPLOYED", "RETIRED"} else 0)
            if product == "P006":
                age = CURRENT_YEAR - float(row.birth_year)
                if emp == "STUDENT":
                    u += 1.35
                u += .65 if age <= 28 else (-1.25 if age >= 40 else 0)
            if emp == "SELF_EMPLOYED" and product in {"P003", "P004"}:
                u += STRENGTH["MODERATE"]

        counts = Counter(owned)
        if product == "P002" and counts["P001"]:
            u += STRENGTH["WEAK"] * math.log1p(counts["P001"])
        if product == "P007" and counts["P001"]:
            u += STRENGTH["WEAK"] * math.log1p(counts["P001"])
        if product == "P008" and counts["P002"]:
            u += STRENGTH["MODERATE"] * math.log1p(counts["P002"])
        if product == "P004" and counts["P003"]:
            u += STRENGTH["MODERATE"] * math.log1p(counts["P003"])
        if row.customer_type == "BUSINESS" and product == "P002" and counts["P003"]:
            u += STRENGTH["WEAK"] * math.log1p(counts["P003"])
        if product == "P001" and counts["P005"]:
            u -= STRENGTH["WEAK"] * math.log1p(counts["P005"])
        if counts[product]:
            u -= REPEAT_PENALTY[product] * math.log1p(counts[product])

        years_since_launch = year - PRODUCT_META[product]["launch_year"]
        if years_since_launch < 3:
            u -= STRENGTH["WEAK"] * (3 - years_since_launch) / 3

        return u + self.rng.normal(0, .25)

    def choose_product(self, row, year, owned):
        products = self.eligible_products(row, year)
        if not products:
            return None
        probs = softmax([self.product_utility(row, p, year, owned) for p in products])
        return str(self.rng.choice(products, p=probs))

    def choose_historical_year(self, row, slot, product):
        low = max(int(row.registration_year), PRODUCT_META[product]["launch_year"])

        # A customer relationship that ended before 2021 cannot acquire
        # an account after its own closing year.
        upper = OBSERVATION_START_YEAR - 1
        if str(row.customer_status) == "CLOSED" and pd.notna(row.closing_year):
            upper = min(upper, int(row.closing_year))

        if low > upper:
            return None
        if low == upper:
            return low

        frac = self.rng.beta(1.25, 3.8) if slot == 0 else self.rng.beta(1.6, 2.1)
        return int(np.clip(low + round(frac * (upper - low)), low, upper))

    def branch_open(self, b, year):
        opening = int(float(b["opening_year"]))
        closing = pd.to_numeric(pd.Series([b.get("closing_year")]), errors="coerce").iloc[0]
        return opening <= year and (pd.isna(closing) or year <= int(closing))

    def choose_branch(self, row, year):
        mask = self.branches.apply(lambda b: self.branch_open(b, year), axis=1)
        candidates = self.branches[mask]
        if candidates.empty:
            raise RuntimeError(f"No branch open in {year}.")

        primary = str(row.primary_branch_id).zfill(3)
        primary_ok = primary in set(candidates["branch_id"])
        same_dep = candidates[
            candidates["department"].fillna("").str.upper()
            == str(row.residence_department).upper()
        ]
        same_dep = same_dep[same_dep["branch_id"] != primary]

        categories, weights = [], []
        if primary_ok:
            categories.append("PRIMARY"); weights.append(5.0)
        if not same_dep.empty:
            categories.append("SAME_DEPARTMENT"); weights.append(2.0)
        categories.append("OTHER"); weights.append(.7)

        weights = np.array(weights) / np.sum(weights)
        category = self.rng.choice(categories, p=weights)

        if category == "PRIMARY":
            return primary
        if category == "SAME_DEPARTMENT":
            return str(self.rng.choice(same_dep["branch_id"]))

        excluded = set(same_dep["branch_id"])
        if primary_ok:
            excluded.add(primary)
        other = candidates[~candidates["branch_id"].isin(excluded)]
        if other.empty:
            other = candidates
        return str(self.rng.choice(other["branch_id"]))

    def choose_channel(self, row, year):
        """
        Smooth channel adoption model.

        Customer digital affinity is persistent, while technology availability
        evolves gradually through calendar time. This avoids artificial jumps
        from hard year cutoffs.
        """
        digital_affinity = 2 * (float(row._digital) - .5)

        digital_tech = sigmoid((year - 2018.8) / 2.6)
        remote_tech = sigmoid((year - 2011.5) / 3.3)

        branch_score = 2.55 - 2.28 * digital_tech - .30 * remote_tech
        digital_score = -4.42 + 5.25 * digital_tech
        remote_score = -2.20 + 2.30 * remote_tech - .34 * digital_tech

        digital_score += STRENGTH["STRONG"] * digital_affinity
        remote_score += STRENGTH["WEAK"] * digital_affinity

        scores = {
            "BRANCH": branch_score,
            "DIGITAL": digital_score,
            "REMOTE_ASSISTED": remote_score,
        }

        channels = list(scores)
        probs = softmax([scores[c] for c in channels])
        return str(self.rng.choice(channels, p=probs))

    def survival_probability(self, row, product, opening_year, owned):
        age = OBSERVATION_START_YEAR - opening_year
        score = 1.55 - .045 * age
        if product in {"P001", "P002", "P003", "P004", "P005"}:
            score += .35
        if product == "P006":
            score -= .35
        if product in FIXED_TERM_PRODUCTS:
            score -= .85
        score += .30 * math.log(max(float(row._depth), 1e-6))
        count = Counter(owned)[product]
        if count > 1 and product not in FIXED_TERM_PRODUCTS:
            score -= STRENGTH["WEAK"] * math.log1p(count - 1)
        return float(np.clip(sigmoid(score + self.rng.normal(0, .45)), .04, .985))

    def historical_closing_year(self, row, opening_year):
        upper = OBSERVATION_START_YEAR - 1
        if str(row.customer_status) == "CLOSED" and pd.notna(row.closing_year):
            upper = min(upper, int(row.closing_year))
        upper = max(opening_year, upper)
        if upper == opening_year:
            return opening_year
        frac = self.rng.beta(2.0, 1.8)
        return opening_year + int(round(frac * (upper - opening_year)))

    def add_account(self, row, product, branch, opening_year, channel, status="ACTIVE", closing_year=np.nan):
        account = {
            "account_id": f"A{self.counter:07d}",
            "customer_id": row.customer_id,
            "product_id": product,
            "branch_id": branch,
            "opening_year": int(opening_year),
            "account_status": status,
            "closing_year": closing_year,
            "opening_channel": channel,
        }
        self.counter += 1
        self.accounts.append(account)
        self.portfolios[row.customer_id].append(account)

    def generate_pre_observation_for_customer(self, row):
        """Generate historical account relationships before the observation window."""
        if int(row.registration_year) > OBSERVATION_START_YEAR - 1:
            return

        if self.rng.random() >= self.participation_probability(row):
            return

        n_accounts = self.historical_count(row)
        owned, provisional = [], []

        for slot in range(n_accounts):
            low = int(row.registration_year)
            upper = OBSERVATION_START_YEAR - 1

            if str(row.customer_status) == "CLOSED" and pd.notna(row.closing_year):
                upper = min(upper, int(row.closing_year))

            if low > upper:
                continue

            frac = (
                self.rng.beta(1.25, 3.8)
                if slot == 0
                else self.rng.beta(1.6, 2.1)
            )
            candidate_year = int(
                np.clip(
                    low + round(frac * (upper - low)),
                    low,
                    upper,
                )
            )

            product = self.choose_product(
                row,
                candidate_year,
                owned,
            )
            if product is None:
                continue

            opening_year = self.choose_historical_year(
                row,
                slot,
                product,
            )
            if opening_year is None:
                continue

            product = self.choose_product(
                row,
                opening_year,
                owned,
            )
            if product is None:
                continue

            branch = self.choose_branch(row, opening_year)
            channel = self.choose_channel(row, opening_year)
            owned.append(product)
            provisional.append(
                (product, branch, opening_year, channel)
            )

        for product, branch, opening_year, channel in provisional:
            forced_closed = (
                str(row.customer_status) == "CLOSED"
                and pd.notna(row.closing_year)
                and int(row.closing_year) <= OBSERVATION_START_YEAR - 1
            )

            survives = False if forced_closed else (
                self.rng.random()
                < self.survival_probability(
                    row,
                    product,
                    opening_year,
                    owned,
                )
            )

            if survives:
                self.add_account(
                    row,
                    product,
                    branch,
                    opening_year,
                    channel,
                )
            else:
                closing_year = self.historical_closing_year(
                    row,
                    opening_year,
                )
                self.add_account(
                    row,
                    product,
                    branch,
                    opening_year,
                    channel,
                    "CLOSED",
                    closing_year,
                )

    def active_accounts(self, customer_id, year):
        result = []
        for account in self.portfolios.get(customer_id, []):
            if account["opening_year"] > year:
                continue
            if (
                pd.isna(account["closing_year"])
                or int(account["closing_year"]) > year
            ):
                result.append(account)
        return result

    def annual_open_probability(self, row, year):
        if int(row.registration_year) > year:
            return 0
        if (
            str(row.customer_status) == "CLOSED"
            and pd.notna(row.closing_year)
            and int(row.closing_year) < year
        ):
            return 0

        n_active = len(
            self.active_accounts(
                row.customer_id,
                year,
            )
        )
        score = (
            -2.00
            + .45
            * math.log(
                max(float(row._depth), 1e-6)
            )
        )

        since_registration = year - int(row.registration_year)
        if since_registration == 0:
            score += 2.35
        elif since_registration == 1:
            score += 1.00

        score -= .28 * math.log1p(n_active)
        if n_active == 0:
            score += .80

        return float(
            np.clip(
                sigmoid(
                    score
                    + self.rng.normal(0, .35)
                ),
                .01,
                .90,
            )
        )

    def annual_close_probability(self, row, account, year):
        age = year - int(account["opening_year"])
        score = -3.75 + .032 * age
        product = account["product_id"]

        if product == "P006":
            score += .25
        if product in FIXED_TERM_PRODUCTS:
            score += 1.10

        active = self.active_accounts(
            row.customer_id,
            year,
        )
        same = sum(
            account_["product_id"] == product
            for account_ in active
        )
        if (
            same > 1
            and product not in FIXED_TERM_PRODUCTS
        ):
            score += (
                STRENGTH["WEAK"]
                * math.log1p(same - 1)
            )

        score -= .25 * math.log(
            max(float(row._depth), 1e-6)
        )
        return float(
            np.clip(
                sigmoid(
                    score
                    + self.rng.normal(0, .35)
                ),
                .005,
                .65,
            )
        )

    def generate_observed_period_for_customer(self, row):
        """Generate account openings and closures during the observation window."""
        for year in range(
            OBSERVATION_START_YEAR,
            CURRENT_YEAR + 1,
        ):
            if int(row.registration_year) > year:
                continue
            if (
                str(row.customer_status) == "CLOSED"
                and pd.notna(row.closing_year)
                and int(row.closing_year) < year
            ):
                continue

            if (
                self.rng.random()
                < self.annual_open_probability(
                    row,
                    year,
                )
            ):
                owned = [
                    account["product_id"]
                    for account in self.portfolios.get(
                        row.customer_id,
                        [],
                    )
                    if account["opening_year"] <= year
                ]
                product = self.choose_product(
                    row,
                    year,
                    owned,
                )

                if product:
                    self.add_account(
                        row,
                        product,
                        self.choose_branch(
                            row,
                            year,
                        ),
                        year,
                        self.choose_channel(
                            row,
                            year,
                        ),
                    )

                    second = (
                        .10 * float(row._depth)
                    )
                    second /= (
                        1
                        + .20
                        * len(
                            self.active_accounts(
                                row.customer_id,
                                year,
                            )
                        )
                    )

                    if self.rng.random() < min(
                        second,
                        .20,
                    ):
                        owned = [
                            account["product_id"]
                            for account in self.portfolios.get(
                                row.customer_id,
                                [],
                            )
                            if account["opening_year"] <= year
                        ]
                        product2 = self.choose_product(
                            row,
                            year,
                            owned,
                        )
                        if product2:
                            self.add_account(
                                row,
                                product2,
                                self.choose_branch(
                                    row,
                                    year,
                                ),
                                year,
                                self.choose_channel(
                                    row,
                                    year,
                                ),
                            )

            for account in list(
                self.active_accounts(
                    row.customer_id,
                    year,
                )
            ):
                if not pd.isna(
                    account["closing_year"]
                ):
                    continue

                forced = (
                    str(row.customer_status) == "CLOSED"
                    and pd.notna(row.closing_year)
                    and int(row.closing_year) == year
                )
                close = (
                    forced
                    or self.rng.random()
                    < self.annual_close_probability(
                        row,
                        account,
                        year,
                    )
                )

                if close:
                    account["account_status"] = "CLOSED"
                    account["closing_year"] = year

    def final_zero_account_rescue_for_customer(self, row):
        """
        Apply the final probabilistic participation opportunity to one customer.

        The rescue is only available to customers that are active at the end of
        the observation window. Closed customers must never finish the world
        with a newly created active account.
        """
        if self.portfolios.get(row.customer_id):
            return

        if str(row.customer_status) == "CLOSED":
            return

        if int(row.registration_year) > CURRENT_YEAR:
            return

        p_rescue = 0.34
        if self.rng.random() >= p_rescue:
            return

        product = self.choose_product(
            row,
            CURRENT_YEAR,
            [],
        )
        if product is None:
            return

        self.add_account(
            row=row,
            product=product,
            branch=self.choose_branch(
                row,
                CURRENT_YEAR,
            ),
            opening_year=CURRENT_YEAR,
            channel=self.choose_channel(
                row,
                CURRENT_YEAR,
            ),
            status="ACTIVE",
            closing_year=np.nan,
        )

    def generate_customer_lifecycle(self, row):
        """
        Generate the complete account history for one customer.

        A customer-specific lifecycle RNG makes output invariant to customer
        chunk boundaries while preserving within-customer stochastic ordering.
        """
        self.rng = self._make_customer_rng(
            row.customer_id,
            RNG_STREAM_LIFECYCLE_BASE,
        )
        self.generate_pre_observation_for_customer(row)
        self.generate_observed_period_for_customer(row)
        self.final_zero_account_rescue_for_customer(row)
        self.rng = None

    def pop_customer_accounts(self, customer_id: str) -> list[dict]:
        """Detach one customer's completed account history from in-memory state."""
        accounts = self.portfolios.pop(
            customer_id,
            [],
        )
        if accounts:
            del self.accounts[-len(accounts):]
        return accounts

    def process_chunk(
        self,
        customers_chunk: pd.DataFrame,
    ) -> pd.DataFrame:
        """Generate complete account histories for one customer chunk."""
        required_latents = {
            "_depth",
            "_usd",
            "_savings",
            "_transactional",
            "_digital",
        }
        missing_latents = required_latents - set(customers_chunk.columns)
        if missing_latents:
            raise RuntimeError(
                "Customer chunk is missing prepared account latent variables: "
                f"{sorted(missing_latents)}"
            )

        chunk_accounts = []

        for record in customers_chunk.to_dict("records"):
            row = SimpleNamespace(**record)
            self.generate_customer_lifecycle(row)
            chunk_accounts.extend(
                self.pop_customer_accounts(
                    row.customer_id
                )
            )

        return accounts_to_dataframe(
            chunk_accounts
        )

    def dataframe(self):
        return accounts_to_dataframe(self.accounts)


ACCOUNT_COLUMNS = [
    "account_id",
    "customer_id",
    "product_id",
    "branch_id",
    "opening_year",
    "account_status",
    "closing_year",
    "opening_channel",
]


def accounts_to_dataframe(
    records: list[dict],
) -> pd.DataFrame:
    """Convert generated account records to the canonical dataframe schema."""
    df = pd.DataFrame(
        records,
        columns=ACCOUNT_COLUMNS,
    )
    if not df.empty:
        df["closing_year"] = pd.array(
            df["closing_year"],
            dtype="Int64",
        )
    return df


def write_accounts_parquet(
    generator: AccountsGenerator,
) -> int:
    """
    Generate accounts by customer chunks and write Parquet incrementally.

    Chunking uses generator.customers because that dataframe contains the
    prepared global signals and customer-level latent variables.
    """
    PARQUET_OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if PARQUET_OUTPUT_PATH.exists():
        PARQUET_OUTPUT_PATH.unlink()

    customers = generator.customers
    writer = None
    total_accounts = 0
    total_chunks = math.ceil(
        len(customers) / CUSTOMER_CHUNK_SIZE
    )

    try:
        for chunk_number, start in enumerate(
            range(
                0,
                len(customers),
                CUSTOMER_CHUNK_SIZE,
            ),
            start=1,
        ):
            stop = min(
                start + CUSTOMER_CHUNK_SIZE,
                len(customers),
            )
            customers_chunk = customers.iloc[
                start:stop
            ]

            chunk_df = generator.process_chunk(
                customers_chunk
            )

            if not chunk_df.empty:
                table = pa.Table.from_pandas(
                    chunk_df,
                    preserve_index=False,
                )

                if writer is None:
                    writer = pq.ParquetWriter(
                        PARQUET_OUTPUT_PATH,
                        table.schema,
                        compression=PARQUET_COMPRESSION,
                    )

                writer.write_table(table)
                total_accounts += len(chunk_df)

            print(
                f"Processed chunk {chunk_number:,}/{total_chunks:,} "
                f"| customers {start + 1:,}-{stop:,} "
                f"| accounts {len(chunk_df):,} "
                f"| cumulative {total_accounts:,}"
            )

    finally:
        if writer is not None:
            writer.close()

    if writer is None:
        raise RuntimeError(
            "Accounts generator produced zero rows; "
            "no Parquet file was created."
        )

    return total_accounts



def validate_output(accounts, customers, branches):
    errors = []

    if accounts["account_id"].duplicated().any():
        errors.append("duplicate account_id")

    if not set(accounts["customer_id"]).issubset(set(customers["customer_id"])):
        errors.append("unknown customer_id")

    if not set(accounts["branch_id"]).issubset(set(branches["branch_id"])):
        errors.append("unknown branch_id")

    if not accounts["product_id"].isin(ACCOUNT_PRODUCTS).all():
        errors.append("invalid product_id")

    if not accounts["account_status"].isin(["ACTIVE", "CLOSED"]).all():
        errors.append("invalid account_status")

    if not accounts["opening_channel"].isin(["BRANCH", "DIGITAL", "REMOTE_ASSISTED"]).all():
        errors.append("invalid opening_channel")

    if accounts.loc[accounts["account_status"] == "ACTIVE", "closing_year"].notna().any():
        errors.append("ACTIVE account has closing_year")

    if accounts.loc[accounts["account_status"] == "CLOSED", "closing_year"].isna().any():
        errors.append("CLOSED account missing closing_year")

    closed = accounts["closing_year"].notna()
    if (accounts.loc[closed, "closing_year"].astype(int) < accounts.loc[closed, "opening_year"]).any():
        errors.append("closing_year before opening_year")

    launch = accounts["product_id"].map({p: PRODUCT_META[p]["launch_year"] for p in ACCOUNT_PRODUCTS})
    if (accounts["opening_year"] < launch).any():
        errors.append("account before product launch")

    cust = customers.set_index("customer_id")
    reg = accounts["customer_id"].map(cust["registration_year"]).astype(int)
    if (accounts["opening_year"] < reg).any():
        errors.append("account before customer registration")

    ctype = accounts["customer_id"].map(cust["customer_type"])
    if (ctype.eq("BUSINESS") & accounts["product_id"].isin(["P005", "P006"])).any():
        errors.append("business owns individual-only product")

    customer_status = accounts["customer_id"].map(cust["customer_status"])
    customer_close = pd.to_numeric(accounts["customer_id"].map(cust["closing_year"]), errors="coerce")
    account_close = pd.to_numeric(accounts["closing_year"], errors="coerce")

    if (customer_status.eq("CLOSED") & accounts["account_status"].eq("ACTIVE")).any():
        errors.append("closed customer has active account")

    if (customer_status.eq("CLOSED") & account_close.notna() & customer_close.notna() & (account_close > customer_close)).any():
        errors.append("account closes after customer")

    b = branches.set_index("branch_id")
    branch_open = pd.to_numeric(accounts["branch_id"].map(b["opening_year"]), errors="coerce")
    if (accounts["opening_year"] < branch_open).any():
        errors.append("account before branch opening")

    branch_close = pd.to_numeric(accounts["branch_id"].map(b["closing_year"]), errors="coerce")
    if (branch_close.notna() & (accounts["opening_year"] > branch_close)).any():
        errors.append("account after branch closure")

    if errors:
        raise AssertionError("VALIDATION FAILED:\n- " + "\n- ".join(errors))

    print("\nVALIDATION: PASS")


def audit(accounts, customers):
    print("\n" + "=" * 76)
    print("BTYT ACCOUNTS — CANONICAL WORLD AUDIT")
    print("=" * 76)
    print(f"Customers: {len(customers):,}")
    print(f"Accounts:  {len(accounts):,}")

    per_customer = accounts.groupby("customer_id").size()
    banked = len(per_customer)

    print(f"Customers with >=1 account: {banked:,} ({banked / len(customers):.2%})")
    print(f"Mean accounts per banked customer: {per_customer.mean():.2f}")
    print(f"Median: {per_customer.median():.0f}")
    print(f"P95: {per_customer.quantile(.95):.0f}")
    print(f"P99: {per_customer.quantile(.99):.0f}")
    print(f"Maximum: {per_customer.max():.0f}")

    customer_types = customers.set_index("customer_id")["customer_type"]
    customer_frame = customers[["customer_id", "customer_type"]].copy()
    counts = per_customer.rename("account_count")
    customer_frame = customer_frame.join(counts, on="customer_id")
    customer_frame["account_count"] = customer_frame["account_count"].fillna(0).astype(int)
    customer_frame["has_account"] = customer_frame["account_count"] > 0

    print("\nParticipation and depth by customer type:")
    participation = customer_frame.groupby("customer_type").agg(
        customers=("customer_id", "size"),
        banked_customers=("has_account", "sum"),
        participation_rate=("has_account", "mean"),
    )
    banked_depth = (
        customer_frame.loc[customer_frame["has_account"]]
        .groupby("customer_type")["account_count"]
        .agg(["mean", "median", "max"])
        .rename(columns={
            "mean": "mean_accounts_banked",
            "median": "median_accounts_banked",
            "max": "max_accounts_banked",
        })
    )
    participation = participation.join(banked_depth)
    participation["participation_rate"] *= 100
    print(participation.round(2).to_string())

    print("\nProduct distribution (%):")
    print(accounts["product_id"].value_counts(normalize=True).mul(100).round(2).to_string())

    print("\nFinal account status (%):")
    print(accounts["account_status"].value_counts(normalize=True).mul(100).round(2).to_string())

    inherited = accounts[
        (accounts["opening_year"] < OBSERVATION_START_YEAR)
        & (accounts["closing_year"].isna() | (accounts["closing_year"] >= OBSERVATION_START_YEAR))
    ]
    print(f"\nActive inherited relationships entering {OBSERVATION_START_YEAR}: {len(inherited):,}")

    print(f"\nObserved openings {OBSERVATION_START_YEAR}-{CURRENT_YEAR}:")
    print(
        accounts.loc[accounts["opening_year"].between(OBSERVATION_START_YEAR, CURRENT_YEAR), "opening_year"]
        .value_counts().sort_index().to_string()
    )

    print(f"\nObserved closures {OBSERVATION_START_YEAR}-{CURRENT_YEAR}:")
    print(
        accounts.loc[accounts["closing_year"].between(OBSERVATION_START_YEAR, CURRENT_YEAR), "closing_year"]
        .value_counts().sort_index().to_string()
    )

    print("\nOpening channel by year (%):")
    print(
        pd.crosstab(accounts["opening_year"], accounts["opening_channel"], normalize="index")
        .mul(100).round(1).tail(20).to_string()
    )

    temp = accounts.assign(customer_type=accounts["customer_id"].map(customer_types))

    print("\nProducts by customer type:")
    print(pd.crosstab(temp["customer_type"], temp["product_id"]).to_string())

    print("\nClosure rate by product (%):")
    closure_by_product = (
        accounts.assign(is_closed=accounts["account_status"].eq("CLOSED"))
        .groupby("product_id")["is_closed"]
        .agg(["count", "sum", "mean"])
        .rename(columns={"count": "relationships", "sum": "closed", "mean": "closure_rate"})
    )
    closure_by_product["closure_rate"] *= 100
    print(closure_by_product.round(2).to_string())

    period = pd.cut(
        accounts["opening_year"],
        bins=[
            -np.inf,
            2000,
            2010,
            OBSERVATION_START_YEAR - 1,
            CURRENT_YEAR,
        ],
        labels=[
            "<=2000",
            "2001-2010",
            f"2011-{OBSERVATION_START_YEAR - 1}",
            f"{OBSERVATION_START_YEAR}-{CURRENT_YEAR}",
        ],
    )
    closure_by_vintage = (
        accounts.assign(
            opening_period=period,
            is_closed=accounts["account_status"].eq("CLOSED"),
        )
        .groupby("opening_period", observed=True)["is_closed"]
        .agg(["count", "sum", "mean"])
        .rename(columns={"count": "relationships", "sum": "closed", "mean": "closure_rate"})
    )
    closure_by_vintage["closure_rate"] *= 100

    print("\nClosure rate by opening vintage (%):")
    print(closure_by_vintage.round(2).to_string())

    print("\nRepeated customer-product relationship counts:")
    print(
        accounts.groupby(["customer_id", "product_id"]).size()
        .value_counts().sort_index().head(10).to_string()
    )


def main():
    print("=" * 76)
    print("BTYT ACCOUNTS GENERATOR")
    print("=" * 76)
    print(f"World: {WORLD.name}")
    print(f"World seed: {WORLD.seed}")
    print(f"RNG namespace: {RNG_NAMESPACE}")
    print(
        "Observation period: "
        f"{OBSERVATION_START_YEAR}-{CURRENT_YEAR}"
    )
    print(f"Configured customers: {WORLD.customer_count:,}")
    print(f"Chunk size: {CUSTOMER_CHUNK_SIZE:,} customers")
    print(f"Parquet compression: {PARQUET_COMPRESSION}")

    print("\nLoading BTYT inputs...")
    customers, products, branches, customers_source = load_inputs()
    validate_inputs(
        customers,
        products,
        branches,
    )

    print(f"Customer source: {customers_source}")
    print(f"Customers loaded: {len(customers):,}")
    print("\nGenerating account histories by customer chunk...")

    generator = AccountsGenerator(
        customers,
        branches,
    )
    generated_rows = write_accounts_parquet(
        generator,
    )

    print("\nReading canonical accounts Parquet for validation...")
    accounts = pd.read_parquet(
        PARQUET_OUTPUT_PATH
    )
    accounts["account_id"] = (
        accounts["account_id"]
        .astype("string")
    )
    accounts["customer_id"] = (
        accounts["customer_id"]
        .astype("string")
    )
    accounts["product_id"] = (
        accounts["product_id"]
        .astype("string")
    )
    accounts["branch_id"] = _normalize_id_series(
        accounts["branch_id"],
        width=3,
    )
    accounts["closing_year"] = pd.array(
        accounts["closing_year"],
        dtype="Int64",
    )

    if len(accounts) != generated_rows:
        raise AssertionError(
            "Parquet row count does not match generated row count: "
            f"{len(accounts):,} != {generated_rows:,}"
        )

    validate_output(
        accounts,
        customers,
        branches,
    )

    if WRITE_COMPATIBILITY_CSV:
        accounts.to_csv(
            CSV_OUTPUT_PATH,
            index=False,
        )

    audit(
        accounts,
        customers,
    )

    parquet_mb = (
        PARQUET_OUTPUT_PATH.stat().st_size
        / (1024 ** 2)
    )

    print(f"\nSaved canonical Parquet: {PARQUET_OUTPUT_PATH}")
    print(f"Parquet size: {parquet_mb:.2f} MB")
    if WRITE_COMPATIBILITY_CSV:
        csv_mb = (
            CSV_OUTPUT_PATH.stat().st_size
            / (1024 ** 2)
        )
        print(f"Saved compatibility CSV: {CSV_OUTPUT_PATH}")
        print(f"CSV size: {csv_mb:.2f} MB")
    print(f"Shape: {accounts.shape}")


if __name__ == "__main__":
    main()