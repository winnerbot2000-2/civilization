from __future__ import annotations

from civsim.core.simulation import initialize_simulation
from civsim.viewer.pygame_viewer import OverlayState, _terrain_profile_for_patch


def test_terrain_profile_marks_strong_water_as_river_or_deep_water(small_config) -> None:
    state = initialize_simulation(small_config, seed=71)
    patch_id = 0
    state.world.water[patch_id] = 0.82
    state.world.food_capacity[patch_id] = 2.0
    state.world.movement_cost[patch_id] = 1.2
    profile = _terrain_profile_for_patch(
        state.world,
        patch_id,
        state.clock.season_name,
        OverlayState(),
        float(state.world.movement_cost.min()),
        float(state.world.movement_cost.max()),
        float(state.world.food_capacity.max()),
    )
    assert profile.terrain_kind in {"river", "deep_water"}


def test_terrain_profile_distinguishes_fertile_grass_from_rough_ground(small_config) -> None:
    state = initialize_simulation(small_config, seed=72)
    lush_patch = 1
    rough_patch = 2
    state.world.water[lush_patch] = 0.24
    state.world.food_capacity[lush_patch] = float(state.world.food_capacity.max()) * 1.1
    state.world.shelter[lush_patch] = 0.4
    state.world.danger[lush_patch] = 0.05
    state.world.movement_cost[lush_patch] = float(state.world.movement_cost.min())

    state.world.water[rough_patch] = 0.04
    state.world.food_capacity[rough_patch] = 1.2
    state.world.shelter[rough_patch] = 0.18
    state.world.danger[rough_patch] = 0.18
    state.world.movement_cost[rough_patch] = float(state.world.movement_cost.max())

    movement_min = float(state.world.movement_cost.min())
    movement_max = float(state.world.movement_cost.max())
    food_capacity_max = float(state.world.food_capacity.max())
    overlays = OverlayState()

    lush_profile = _terrain_profile_for_patch(
        state.world,
        lush_patch,
        state.clock.season_name,
        overlays,
        movement_min,
        movement_max,
        food_capacity_max,
    )
    rough_profile = _terrain_profile_for_patch(
        state.world,
        rough_patch,
        state.clock.season_name,
        overlays,
        movement_min,
        movement_max,
        food_capacity_max,
    )

    assert lush_profile.terrain_kind in {"lush_grass", "grassland", "wetland"}
    assert rough_profile.terrain_kind in {"rock", "scrub", "badlands"}
