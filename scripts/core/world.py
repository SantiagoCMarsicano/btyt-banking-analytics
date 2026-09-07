from dataclasses import dataclass
from datetime import date

from scripts.core.config import load_world_config
from scripts.core.rng import make_rng


POPULATION_RNG_NAMESPACE = "world.population"
POPULATION_RNG_STREAM = 0


@dataclass(frozen=True)
class WorldConfig:
    name: str
    seed: int
    customer_count: int
    start_date: date
    end_date: date
    execution_mode: str
    smoke_customers: int
    data_reliability_mode: str
    data_reliability_level: str

    def __post_init__(self) -> None:
        """Validate relationships between world-level settings."""
        if self.seed < 0:
            raise ValueError(
                "World seed must be greater than or equal to zero."
            )

        if self.customer_count <= 0:
            raise ValueError(
                "Customer population must be greater than zero."
            )

        if self.start_date > self.end_date:
            raise ValueError(
                "World start_date must be earlier than or equal to end_date."
            )

        if self.smoke_customers <= 0:
            raise ValueError(
                "Smoke-test customer count must be greater than zero."
            )

        if self.smoke_customers > self.customer_count:
            raise ValueError(
                "Smoke-test customer count cannot exceed total customer count."
            )


def resolve_customer_count(config: dict) -> int:
    """Resolve the canonical customer population from the world configuration."""
    population = config["population"]

    if "customers" in population:
        return int(population["customers"])

    customers_min = int(population["customers_min"])
    customers_max = int(population["customers_max"])
    world_seed = int(config["world"]["seed"])

    rng = make_rng(
        world_seed=world_seed,
        namespace=POPULATION_RNG_NAMESPACE,
        stream=POPULATION_RNG_STREAM,
    )

    return int(rng.integers(customers_min, customers_max + 1))


def load_world() -> WorldConfig:
    """Load the canonical BTYT world as a typed configuration object."""
    config = load_world_config()

    return WorldConfig(
        name=config["world"]["name"],
        seed=int(config["world"]["seed"]),
        customer_count=resolve_customer_count(config),
        start_date=date.fromisoformat(
            config["observation_period"]["start_date"]
        ),
        end_date=date.fromisoformat(
            config["observation_period"]["end_date"]
        ),
        execution_mode=config["execution"]["mode"],
        smoke_customers=int(config["execution"]["smoke_customers"]),
        data_reliability_mode=config["data_reliability"]["mode"],
        data_reliability_level=config["data_reliability"]["level"],
    )
