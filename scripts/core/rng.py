import hashlib

import numpy as np


def _namespace_to_uint32(namespace: str) -> int:
    """Convert a stable namespace string into a deterministic uint32 value."""
    if not namespace:
        raise ValueError("RNG namespace cannot be empty.")

    digest = hashlib.sha256(
        namespace.encode("utf-8")
    ).digest()

    return int.from_bytes(
        digest[:4],
        byteorder="big",
        signed=False,
    )


def make_rng(
    world_seed: int,
    namespace: str,
    stream: int = 0,
) -> np.random.Generator:
    """
    Create a reproducible RNG from a world seed, namespace, and stream.

    The namespace isolates stochastic systems such as customers, banks,
    branches, or transactions. The stream isolates independent stochastic
    processes inside each system.
    """
    if world_seed < 0:
        raise ValueError(
            "World seed must be greater than or equal to zero."
        )

    if stream < 0:
        raise ValueError(
            "RNG stream must be greater than or equal to zero."
        )

    namespace_seed = _namespace_to_uint32(namespace)

    seed_sequence = np.random.SeedSequence(
        [
            world_seed,
            namespace_seed,
            stream,
        ]
    )

    return np.random.default_rng(seed_sequence)