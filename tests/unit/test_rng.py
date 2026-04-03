from __future__ import annotations

from civsim.core.rng import SeedRegistry


def test_named_rng_streams_are_deterministic() -> None:
    first = SeedRegistry(11)
    second = SeedRegistry(11)
    assert first.python("agents").random() == second.python("agents").random()
    assert first.numpy("world").integers(0, 10) == second.numpy("world").integers(0, 10)
    assert first.python("agents").random() != first.python("world").random()
