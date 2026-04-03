from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from .grid import Grid
from .sites import PathTrace, SiteMarker

if TYPE_CHECKING:
    from ..core.config import WorldConfig


@dataclass(slots=True)
class WorldState:
    grid: Grid
    water: np.ndarray
    food: np.ndarray
    food_capacity: np.ndarray
    shelter: np.ndarray
    danger: np.ndarray
    movement_cost: np.ndarray
    occupancy: dict[int, list[int]] = field(default_factory=dict)
    site_markers: dict[int, SiteMarker] = field(default_factory=dict)
    path_traces: dict[tuple[int, int], PathTrace] = field(default_factory=dict)

    def patch_count(self) -> int:
        return self.grid.size

    def ensure_site(self, patch_id: int) -> SiteMarker:
        site = self.site_markers.get(patch_id)
        if site is None:
            site = SiteMarker(patch_id=patch_id)
            self.site_markers[patch_id] = site
        return site


def _smooth_field(rng: np.random.Generator, shape: tuple[int, int], passes: int = 3) -> np.ndarray:
    field = rng.random(shape)
    for _ in range(passes):
        field = (
            field
            + np.roll(field, 1, axis=0)
            + np.roll(field, -1, axis=0)
            + np.roll(field, 1, axis=1)
            + np.roll(field, -1, axis=1)
        ) / 5.0
    field -= field.min()
    max_value = field.max()
    if max_value > 0:
        field /= max_value
    return field


def _source_field(rng: np.random.Generator, shape: tuple[int, int], count: int) -> np.ndarray:
    ys = rng.integers(0, shape[0], size=count)
    xs = rng.integers(0, shape[1], size=count)
    field = np.zeros(shape, dtype=float)
    yy, xx = np.indices(shape)
    for x, y in zip(xs, ys, strict=True):
        dist = np.abs(xx - x) + np.abs(yy - y)
        field += np.exp(-dist / 4.0)
    field -= field.min()
    max_value = field.max()
    if max_value > 0:
        field /= max_value
    return field


def generate_world(config: WorldConfig, rng: np.random.Generator) -> WorldState:
    shape = (config.height, config.width)
    grid = Grid(config.width, config.height)

    water_raw = _source_field(rng, shape, config.water_source_count)
    water = np.clip((water_raw - 0.12) / 0.88, 0.0, 1.0) ** config.water_access_exponent

    danger_raw = np.maximum(_source_field(rng, shape, config.danger_source_count), _smooth_field(rng, shape, 2) * 0.65)
    danger = np.clip(danger_raw, 0.0, 1.0) ** config.danger_exponent

    shelter_raw = _smooth_field(rng, shape, 4)
    shelter = np.clip(0.08 + shelter_raw * 0.92, 0.0, 1.0) ** config.shelter_exponent

    roughness = np.clip((_smooth_field(rng, shape, 3) * 0.8) + danger * 0.35 + (1.0 - shelter) * 0.15, 0.0, 1.0)
    movement_cost = config.movement_cost_min + roughness * (config.movement_cost_max - config.movement_cost_min)

    fertility = np.clip(0.12 + water * 0.72 + shelter * 0.18 - danger * 0.18 - roughness * 0.08, 0.05, 1.0)
    food_capacity = 1.0 + fertility * 3.1
    food = food_capacity.copy()

    return WorldState(
        grid=grid,
        water=water.reshape(grid.size),
        food=food.reshape(grid.size),
        food_capacity=food_capacity.reshape(grid.size),
        shelter=shelter.reshape(grid.size),
        danger=danger.reshape(grid.size),
        movement_cost=movement_cost.reshape(grid.size),
    )
