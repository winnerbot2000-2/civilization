from __future__ import annotations

from civsim.memory.spatial import decay_spatial_memory, remember_site


def test_spatial_memory_decay_prunes_weak_entries() -> None:
    memory = {}
    remember_site(memory, "water", 10, payoff=0.8, risk=0.1, day=0, max_entries=4)
    for _ in range(200):
        decay_spatial_memory(memory, 0.01)
    assert memory == {}
