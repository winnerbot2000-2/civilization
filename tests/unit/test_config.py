from __future__ import annotations

from pathlib import Path

from civsim.core.config import load_config, override_agent_counts


def test_load_base_config() -> None:
    config = load_config(Path("configs/base.toml"))
    assert config.world.width == 32
    assert config.world.ticks_per_day == 4
    assert config.agents.initial_population == 84
    assert config.memory.max_spatial_entries == 16


def test_override_agent_counts_rebalances_total_population() -> None:
    config = load_config(Path("configs/base.toml"))
    override_agent_counts(config, total_agents=20)
    assert config.agents.initial_population + config.agents.initial_children == 20
    assert config.agents.initial_population >= 1
    assert config.agents.initial_children >= 0
