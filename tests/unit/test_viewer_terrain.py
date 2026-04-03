from __future__ import annotations

import pygame

from civsim.core.simulation import initialize_simulation
from civsim.viewer.controller import ViewerController
from civsim.viewer.pygame_viewer import (
    OverlayState,
    VisualProfile,
    _build_terrain_surface,
    _cached_terrain_surface,
    _terrain_profile_for_patch,
)
from civsim.viewer.render_state import ViewerRenderState


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


def test_build_terrain_surface_blends_adjacent_patch_boundary(small_config) -> None:
    pygame.init()
    try:
        controller = ViewerController(base_config=small_config, seed=73)
        world = controller.state.world
        left_patch = world.grid.patch_id(0, 0)
        right_patch = world.grid.patch_id(1, 0)

        world.water[left_patch] = 0.88
        world.danger[left_patch] = 0.04
        world.shelter[left_patch] = 0.16
        world.food_capacity[left_patch] = 2.2
        world.movement_cost[left_patch] = float(world.movement_cost.min())

        world.water[right_patch] = 0.02
        world.danger[right_patch] = 0.82
        world.shelter[right_patch] = 0.08
        world.food_capacity[right_patch] = 1.0
        world.movement_cost[right_patch] = float(world.movement_cost.max())

        visual_profile = VisualProfile(
            trail_samples=5,
            trail_distance_sq=1.8,
            glow_scale=0.8,
            bob_scale=0.5,
            panel_alpha=224,
            terrain_scale=6,
        )
        terrain = _build_terrain_surface(controller, OverlayState(), visual_profile)
        detail_scale = max(visual_profile.terrain_scale * 2, 8)
        left_color = terrain.get_at((detail_scale // 3, detail_scale // 2))[:3]
        boundary_color = terrain.get_at((detail_scale, detail_scale // 2))[:3]
        right_color = terrain.get_at((detail_scale + detail_scale // 2, detail_scale // 2))[:3]

        assert boundary_color != left_color
        assert boundary_color != right_color
    finally:
        pygame.quit()


def test_cached_terrain_surface_reuses_scaled_result_when_inputs_match(small_config) -> None:
    pygame.init()
    try:
        controller = ViewerController(base_config=small_config, seed=74)
        overlays = OverlayState()
        render_state = ViewerRenderState()
        visual_profile = VisualProfile(
            trail_samples=5,
            trail_distance_sq=1.8,
            glow_scale=0.8,
            bob_scale=0.5,
            panel_alpha=224,
            terrain_scale=6,
        )

        first = _cached_terrain_surface(controller, overlays, render_state, visual_profile, (320, 192))
        second = _cached_terrain_surface(controller, overlays, render_state, visual_profile, (320, 192))

        assert first is second
    finally:
        pygame.quit()
