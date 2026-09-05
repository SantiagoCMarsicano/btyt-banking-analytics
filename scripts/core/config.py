import json

from scripts.core.paths import WORLD_CONFIG_PATH


REQUIRED_TOP_LEVEL_KEYS = {
    "world",
    "population",
    "observation_period",
    "execution",
    "data_reliability",
}


def validate_world_config(config: dict) -> None:
    """Validate the canonical BTYT world configuration."""
    missing_keys = REQUIRED_TOP_LEVEL_KEYS - config.keys()

    if missing_keys:
        missing = ", ".join(sorted(missing_keys))
        raise ValueError(
            f"World configuration is missing required sections: {missing}"
        )

    if config["population"]["customers"] <= 0:
        raise ValueError("Customer population must be greater than zero.")

    if config["execution"]["mode"] not in {"production", "development"}:
        raise ValueError(
            "Execution mode must be either 'production' or 'development'."
        )

    if config["data_reliability"]["mode"] not in {"clean", "imperfect"}:
        raise ValueError(
            "Data reliability mode must be either 'clean' or 'imperfect'."
        )

    if config["data_reliability"]["level"] not in {
        "light",
        "realistic",
        "stress",
    }:
        raise ValueError(
            "Data reliability level must be 'light', 'realistic', or 'stress'."
        )


def load_world_config() -> dict:
    """Load and validate the canonical BTYT world configuration."""
    if not WORLD_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"World configuration file not found: {WORLD_CONFIG_PATH}"
        )

    with WORLD_CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = json.load(file)

    validate_world_config(config)

    return config