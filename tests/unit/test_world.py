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


def test_bad_season_food_pressure_is_stronger_than_good_season() -> None:
    config = WorldConfig(width=8, height=6)
    world_good = generate_world(config, SeedRegistry(7).numpy("world-good"))
    world_bad = generate_world(config, SeedRegistry(7).numpy("world-good"))
    world_good.food[:] = world_good.food_capacity
    world_bad.food[:] = world_bad.food_capacity

    good_clock = SimulationClock(ticks_per_day=config.ticks_per_day, season_length_days=config.season_length_days, tick=0)
    bad_clock = SimulationClock(
        ticks_per_day=config.ticks_per_day,
        season_length_days=config.season_length_days,
        tick=config.season_length_days * config.ticks_per_day,
    )

    for _ in range(10):
        apply_daily_world_update(world_good.food, world_good.food_capacity, good_clock, config)
        apply_daily_world_update(world_bad.food, world_bad.food_capacity, bad_clock, config)
        good_clock.tick += config.ticks_per_day
        bad_clock.tick += config.ticks_per_day

    assert float(world_bad.food.mean()) < float(world_good.food.mean())
    assert float(world_bad.food.mean()) < float(world_bad.food_capacity.mean()) * 0.75


def test_world_generation_produces_stronger_terrain_and_water_contrast() -> None:
    config = WorldConfig(width=12, height=8)
    world = generate_world(config, SeedRegistry(9).numpy("world"))
    assert float(world.water.max()) - float(world.water.min()) > 0.75
    assert float(world.movement_cost.max()) - float(world.movement_cost.min()) > 1.5
    assert float(world.danger.max()) > 0.75
