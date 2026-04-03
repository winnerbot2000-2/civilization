from __future__ import annotations

import hashlib
import random

import numpy as np


def derive_seed(base_seed: int, stream_name: str) -> int:
    payload = f"{base_seed}:{stream_name}".encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=False)


class SeedRegistry:
    """Deterministic named random streams."""

    def __init__(self, base_seed: int):
        self.base_seed = base_seed

    def python(self, stream_name: str) -> random.Random:
        return random.Random(derive_seed(self.base_seed, stream_name))

    def numpy(self, stream_name: str) -> np.random.Generator:
        return np.random.default_rng(derive_seed(self.base_seed, stream_name))
