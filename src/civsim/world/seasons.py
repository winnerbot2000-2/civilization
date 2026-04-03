from __future__ import annotations

import numpy as np

from ..core.clock import SimulationClock
from ..core.config import WorldConfig


def season_food_multiplier(clock: SimulationClock, config: WorldConfig) -> float:
    if clock.season_name == "good":
        return config.good_season_food_multiplier
    return config.bad_season_food_multiplier


def regrowth_rate(clock: SimulationClock, config: WorldConfig) -> float:
    if clock.season_name == "good":
        return config.food_regrowth_good
    return config.food_regrowth_bad


def apply_daily_world_update(food: np.ndarray, food_capacity: np.ndarray, clock: SimulationClock, config: WorldConfig) -> None:
    rate = regrowth_rate(clock, config)
    mult = season_food_multiplier(clock, config)
    target_capacity = food_capacity * mult
    if clock.season_name == "bad":
        food *= 1.0 - config.bad_season_food_decay
    food += (target_capacity - food) * rate
    np.clip(food, 0.0, food_capacity * max(config.good_season_food_multiplier, 1.0), out=food)
