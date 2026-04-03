from __future__ import annotations

from pathlib import Path

from civsim.core.config import load_config


def test_load_base_config() -> None:
    config = load_config(Path("configs/base.toml"))
    assert config.world.width == 32
    assert config.world.ticks_per_day == 4
    assert config.agents.initial_population == 120
    assert config.memory.max_spatial_entries == 16
