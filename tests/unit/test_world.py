from __future__ import annotations

from civsim.core.clock import SimulationClock
from civsim.core.config import WorldConfig
from civsim.core.rng import SeedRegistry
from civsim.world.layers import generate_world
from civsim.world.seasons import apply_daily_world_update


def test_daily_world_update_regrows_food() -> None:
    config = WorldConfig(width=8, height=6)
    world = generate_world(config, SeedRegistry(5).numpy("world"))
    world.food[:] = 0.0
    clock = SimulationClock(ticks_per_day=config.ticks_per_day, season_length_days=config.season_length_days)
    apply_daily_world_update(world.food, world.food_capacity, clock, config)
    assert float(world.food.max()) > 0.0
    assert float(world.food.mean()) > 0.0
