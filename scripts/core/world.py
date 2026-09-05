from dataclasses import dataclass
from datetime import date

from scripts.core.config import load_world_config


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


def load_world() -> WorldConfig:
    """Load the canonical BTYT world as a typed configuration object."""
    config = load_world_config()

    return WorldConfig(
        name=config["world"]["name"],
        seed=int(config["world"]["seed"]),
        customer_count=config["population"]["customers"],
        start_date=date.fromisoformat(
            config["observation_period"]["start_date"]
        ),
        end_date=date.fromisoformat(
            config["observation_period"]["end_date"]
        ),
        execution_mode=config["execution"]["mode"],
        smoke_customers=config["execution"]["smoke_customers"],
        data_reliability_mode=config["data_reliability"]["mode"],
        data_reliability_level=config["data_reliability"]["level"],
    )