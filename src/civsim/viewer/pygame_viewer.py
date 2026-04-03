from __future__ import annotations

import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from math import cos, sin, tau

import pygame

from .controller import ViewerController
from .render_state import ViewerRenderState
from .ui import button_at, build_control_buttons, draw_control_bar
from .view_model import ViewerFrameSnapshot, ViewerSnapshotCache, build_viewer_snapshot


Color = tuple[int, int, int]


@dataclass(slots=True)
class OverlayState:
    terrain: bool = True
    water: bool = True
    food: bool = True
    danger: bool = True
    shelter: bool = True
    camps: bool = True
    paths: bool = True
    movement: bool = True
    needs: bool = False
    social_links: bool = False
    kin_links: bool = False
    remembered_good: bool = False
    remembered_danger: bool = False
    resource_pressure: bool = False
    season_tint: bool = True
    overlay_panel: bool = True
    help: bool = True


@dataclass(slots=True, frozen=True)
class VisualProfile:
    trail_samples: int
    trail_distance_sq: float
    glow_scale: float
    bob_scale: float
    panel_alpha: int
    terrain_scale: int


@dataclass(slots=True, frozen=True)
class TerrainProfile:
    terrain_kind: str
    base_color: Color
    accent_color: Color
    vegetation_color: Color
    water_value: float
    fertility: float
    roughness: float
    danger: float
    shelter: float


def _blend(base: Color, overlay: Color, alpha: float) -> Color:
    alpha = max(0.0, min(1.0, alpha))
    return tuple(int(base[idx] * (1.0 - alpha) + overlay[idx] * alpha) for idx in range(3))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _normalize(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return _clamp((value - low) / (high - low), 0.0, 1.0)


def _format_ratio(value: float) -> str:
    return f"{value:.2f}"


@lru_cache(maxsize=16)
def _font(size: int, bold: bool = False) -> pygame.font.Font:
    return pygame.font.SysFont("consolas", size, bold=bold)


def _age_palette(agent) -> tuple[Color, Color, Color]:
    if agent.age_stage == "child":
        return (255, 220, 126), (255, 241, 200), (84, 58, 28)
    if agent.age_stage == "elder":
        return (196, 182, 228), (238, 230, 250), (74, 60, 88)
    return (226, 236, 242), (252, 252, 255), (56, 66, 76)


def _path_color(strength: float) -> Color:
    intensity = int(110 + min(145, strength * 220))
    return (intensity, 136, 72)


def _agent_offsets(count: int, radius: float) -> list[tuple[float, float]]:
    if count <= 1:
        return [(0.0, 0.0)]
    offsets: list[tuple[float, float]] = []
    ring_radius = max(2.0, radius)
    for idx in range(count):
        angle = (idx / count) * tau
        offsets.append((cos(angle) * ring_radius, sin(angle) * ring_radius))
    return offsets


def _target_render_fps(controller: ViewerController) -> int:
    multiplier = controller.current_speed_multiplier
    living_agents = sum(1 for agent in controller.state.agents if agent.alive)
    population_penalty = 0
    if living_agents >= 300:
        population_penalty = 10
    elif living_agents >= 180:
        population_penalty = 6
    elif living_agents >= 120:
        population_penalty = 3
    if controller.paused or controller.pending_steps > 0:
        return 60
    if multiplier is None:
        return max(6, 8 - population_penalty // 2)
    if multiplier >= 500:
        return max(6, 10 - population_penalty)
    if multiplier >= 100:
        return max(8, 12 - population_penalty)
    if multiplier >= 50:
        return max(10, 18 - population_penalty)
    if multiplier >= 10:
        return max(12, 24 - population_penalty)
    if multiplier >= 5:
        return max(16, 30 - population_penalty)
    if multiplier >= 2:
        return max(22, 45 - population_penalty)
    return max(28, 60 - population_penalty)


def _visual_profile(controller: ViewerController) -> VisualProfile:
    multiplier = controller.current_speed_multiplier
    living_agents = sum(1 for agent in controller.state.agents if agent.alive)
    crowded = living_agents >= 180
    very_crowded = living_agents >= 320
    if multiplier is None:
        return VisualProfile(
            trail_samples=2 if very_crowded else 3,
            trail_distance_sq=4.8 if crowded else 4.0,
            glow_scale=0.42 if crowded else 0.5,
            bob_scale=0.15 if crowded else 0.2,
            panel_alpha=210,
            terrain_scale=4,
        )
    if multiplier >= 500:
        return VisualProfile(
            trail_samples=2 if crowded else 3,
            trail_distance_sq=4.0 if crowded else 3.2,
            glow_scale=0.35 if crowded else 0.45,
            bob_scale=0.12 if crowded else 0.25,
            panel_alpha=214,
            terrain_scale=4,
        )
    if multiplier >= 100:
        return VisualProfile(
            trail_samples=3 if crowded else 4,
            trail_distance_sq=3.0 if crowded else 2.3,
            glow_scale=0.48 if crowded else 0.6,
            bob_scale=0.22 if crowded else 0.4,
            panel_alpha=220,
            terrain_scale=5,
        )
    if multiplier >= 50:
        return VisualProfile(
            trail_samples=4 if crowded else 5,
            trail_distance_sq=2.4 if crowded else 1.8,
            glow_scale=0.58 if crowded else 0.72,
            bob_scale=0.35 if crowded else 0.55,
            panel_alpha=224,
            terrain_scale=5,
        )
    if multiplier >= 10:
        return VisualProfile(
            trail_samples=5 if crowded else 7,
            trail_distance_sq=1.8 if crowded else 1.2,
            glow_scale=0.72 if crowded else 0.9,
            bob_scale=0.55 if crowded else 0.8,
            panel_alpha=228,
            terrain_scale=6,
        )
    return VisualProfile(
        trail_samples=6 if crowded else 10,
        trail_distance_sq=1.2 if crowded else 0.75,
        glow_scale=0.82 if crowded else 1.0,
        bob_scale=0.6 if crowded else 1.0,
        panel_alpha=232,
        terrain_scale=6 if crowded else 7,
    )


def _patch_center(grid, patch_id: int, map_rect: pygame.Rect, cell_size: int) -> tuple[float, float]:
    x, y = grid.coords(patch_id)
    return (
        map_rect.left + x * cell_size + cell_size * 0.5,
        map_rect.top + y * cell_size + cell_size * 0.5,
    )


def _patch_at_position(grid, map_rect: pygame.Rect, cell_size: int, mouse_pos: tuple[int, int]) -> int | None:
    if not map_rect.collidepoint(mouse_pos):
        return None
    local_x = mouse_pos[0] - map_rect.left
    local_y = mouse_pos[1] - map_rect.top
    cell_x = int(local_x // cell_size)
    cell_y = int(local_y // cell_size)
    if not grid.in_bounds_xy(cell_x, cell_y):
        return None
    return grid.patch_id(cell_x, cell_y)


def _draw_text_lines(
    surface: pygame.Surface,
    font: pygame.font.Font,
    lines: list[str],
    x: int,
    y: int,
    color: Color,
    line_height: int,
    max_lines: int | None = None,
) -> int:
    visible = lines if max_lines is None else lines[:max_lines]
    cursor = y
    for line in visible:
        text = font.render(line, True, color)
        surface.blit(text, (x, cursor))
        cursor += line_height
    return cursor


def _draw_glow(surface: pygame.Surface, center: tuple[float, float], radius: float, color: Color, alpha: int) -> None:
    diameter = max(8, int(radius * 2.6))
    glow = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    local_center = (diameter // 2, diameter // 2)
    for idx in range(4, 0, -1):
        ring_radius = max(1, int(radius * idx / 4))
        ring_alpha = max(8, int(alpha * (idx / 4) ** 2 * 0.4))
        pygame.draw.circle(glow, (*color, ring_alpha), local_center, ring_radius)
    surface.blit(glow, (center[0] - diameter / 2, center[1] - diameter / 2))


def _draw_chip(
    surface: pygame.Surface,
    font: pygame.font.Font,
    label: str,
    x: int,
    y: int,
    bg_color: Color,
    text_color: Color = (245, 247, 250),
) -> int:
    text = font.render(label, True, text_color)
    width = text.get_width() + 16
    rect = pygame.Rect(x, y, width, text.get_height() + 8)
    pygame.draw.rect(surface, bg_color, rect, border_radius=10)
    pygame.draw.rect(surface, _blend(bg_color, (255, 255, 255), 0.18), rect, 1, border_radius=10)
    surface.blit(text, (rect.x + 8, rect.y + 4))
    return rect.right + 8


def _draw_card(surface: pygame.Surface, rect: pygame.Rect, title: str, accent: Color) -> None:
    pygame.draw.rect(surface, (24, 27, 35), rect, border_radius=14)
    pygame.draw.rect(surface, (56, 60, 74), rect, 1, border_radius=14)
    accent_rect = pygame.Rect(rect.x + 1, rect.y + 1, 6, rect.height - 2)
    pygame.draw.rect(surface, accent, accent_rect, border_radius=12)
    font = _font(17, bold=True)
    surface.blit(font.render(title, True, (236, 240, 246)), (rect.x + 14, rect.y + 10))


def _build_patch_agent_targets(
    controller: ViewerController,
    map_rect: pygame.Rect,
    cell_size: int,
) -> dict[int, tuple[float, float]]:
    positions: dict[int, tuple[float, float]] = {}
    state = controller.state
    grouped: dict[int, list[int]] = defaultdict(list)
    for agent in state.agents:
        if agent.alive:
            grouped[agent.patch_id].append(agent.agent_id)

    radius = max(2.0, cell_size * 0.18)
    for patch_id, occupants in grouped.items():
        center_x, center_y = _patch_center(state.world.grid, patch_id, map_rect, cell_size)
        offsets = _agent_offsets(len(occupants), radius)
        for idx, agent_id in enumerate(sorted(occupants)):
            dx, dy = offsets[idx]
            positions[agent_id] = (center_x + dx, center_y + dy)
    return positions


def _resource_pressure(world, patch_id: int, movement_min: float, movement_max: float) -> float:
    movement_value = _normalize(float(world.movement_cost[patch_id]), movement_min, movement_max)
    food_capacity = max(0.01, float(world.food_capacity[patch_id]))
    food_ratio = _clamp(float(world.food[patch_id]) / food_capacity, 0.0, 1.0)
    water_scarcity = 1.0 - _clamp(float(world.water[patch_id]), 0.0, 1.0)
    return _clamp(
        water_scarcity * 0.35
        + (1.0 - food_ratio) * 0.35
        + float(world.danger[patch_id]) * 0.2
        + movement_value * 0.1,
        0.0,
        1.0,
    )


def _terrain_seed_values(patch_id: int) -> tuple[float, float, float]:
    value_a = ((patch_id * 73) % 100) / 100.0
    value_b = ((patch_id * 37 + 17) % 100) / 100.0
    value_c = ((patch_id * 19 + 43) % 100) / 100.0
    return value_a, value_b, value_c


def _average_color(colors: list[Color]) -> Color:
    if not colors:
        return (0, 0, 0)
    count = len(colors)
    return tuple(sum(color[channel] for color in colors) // count for channel in range(3))


def _adjacent_profiles_for_vertex(world, profiles: list[TerrainProfile], vertex_x: int, vertex_y: int) -> list[TerrainProfile]:
    neighbors: list[TerrainProfile] = []
    for patch_y in (vertex_y - 1, vertex_y):
        if patch_y < 0 or patch_y >= world.grid.height:
            continue
        for patch_x in (vertex_x - 1, vertex_x):
            if patch_x < 0 or patch_x >= world.grid.width:
                continue
            neighbors.append(profiles[world.grid.patch_id(patch_x, patch_y)])
    return neighbors


def _build_vertex_color_surface(world, profiles: list[TerrainProfile], attribute: str) -> pygame.Surface:
    surface = pygame.Surface((world.grid.width + 1, world.grid.height + 1))
    for vertex_y in range(world.grid.height + 1):
        for vertex_x in range(world.grid.width + 1):
            local_profiles = _adjacent_profiles_for_vertex(world, profiles, vertex_x, vertex_y)
            surface.set_at(
                (vertex_x, vertex_y),
                _average_color([getattr(profile, attribute) for profile in local_profiles]),
            )
    return surface


def _terrain_relief_value(profile: TerrainProfile) -> float:
    return (
        profile.roughness * 0.55
        + profile.danger * 0.28
        + max(0.0, 0.42 - profile.shelter) * 0.18
        - profile.water_value * 0.26
        - profile.fertility * 0.14
    )


def _terrain_profile_for_patch(
    world,
    patch_id: int,
    season_name: str,
    overlays: OverlayState,
    movement_min: float,
    movement_max: float,
    food_capacity_max: float,
) -> TerrainProfile:
    water = float(world.water[patch_id]) if overlays.water else 0.0
    danger = float(world.danger[patch_id]) if overlays.danger else 0.0
    shelter = float(world.shelter[patch_id]) if overlays.shelter else 0.0
    fertility = _normalize(float(world.food_capacity[patch_id]), 1.0, food_capacity_max) if overlays.food else 0.0
    roughness = _normalize(float(world.movement_cost[patch_id]), movement_min, movement_max) if overlays.terrain else 0.0

    terrain_kind = "plain"
    base_color: Color = (108, 118, 102)
    accent_color: Color = (150, 162, 138)
    vegetation_color: Color = (104, 144, 98)

    if water > 0.74:
        terrain_kind = "deep_water"
        base_color = (28, 76, 132)
        accent_color = (72, 128, 196)
        vegetation_color = (84, 128, 128)
    elif water > 0.48:
        terrain_kind = "river"
        base_color = (42, 102, 164)
        accent_color = (108, 172, 222)
        vegetation_color = (90, 138, 132)
    elif water > 0.28 and fertility > 0.45:
        terrain_kind = "wetland"
        base_color = (74, 118, 98)
        accent_color = (124, 166, 134)
        vegetation_color = (76, 138, 104)
    elif danger > 0.62 and roughness > 0.5:
        terrain_kind = "badlands"
        base_color = (132, 88, 74)
        accent_color = (176, 124, 104)
        vegetation_color = (128, 96, 78)
    elif roughness > 0.7:
        terrain_kind = "rock"
        base_color = (102, 108, 116)
        accent_color = (150, 156, 164)
        vegetation_color = (118, 126, 120)
    elif shelter > 0.68 and danger < 0.48:
        terrain_kind = "woodland"
        base_color = (82, 110, 78)
        accent_color = (128, 160, 110)
        vegetation_color = (64, 118, 72)
    elif fertility > 0.7:
        terrain_kind = "lush_grass"
        base_color = (94, 132, 84)
        accent_color = (156, 194, 122)
        vegetation_color = (92, 168, 92)
    elif fertility > 0.45:
        terrain_kind = "grassland"
        base_color = (110, 132, 92)
        accent_color = (166, 186, 128)
        vegetation_color = (104, 162, 92)
    elif roughness > 0.42:
        terrain_kind = "scrub"
        base_color = (128, 122, 94)
        accent_color = (170, 160, 118)
        vegetation_color = (136, 148, 88)
    else:
        terrain_kind = "dry_plain"
        base_color = (142, 132, 102)
        accent_color = (186, 174, 132)
        vegetation_color = (146, 152, 94)

    if overlays.season_tint:
        season_tint = (58, 96, 78) if season_name == "good" else (90, 86, 108)
        base_color = _blend(base_color, season_tint, 0.18)
        accent_color = _blend(accent_color, season_tint, 0.12)
        vegetation_color = _blend(vegetation_color, season_tint, 0.1)
    if overlays.resource_pressure:
        pressure = _resource_pressure(world, patch_id, movement_min, movement_max)
        base_color = _blend(base_color, (198, 118, 68), pressure * 0.22)
        accent_color = _blend(accent_color, (220, 142, 90), pressure * 0.16)
    if overlays.danger and danger > 0.3:
        base_color = _blend(base_color, (170, 82, 80), danger * 0.18)

    return TerrainProfile(
        terrain_kind=terrain_kind,
        base_color=base_color,
        accent_color=accent_color,
        vegetation_color=vegetation_color,
        water_value=water,
        fertility=fertility,
        roughness=roughness,
        danger=danger,
        shelter=shelter,
    )


def _build_terrain_surface(
    controller: ViewerController,
    overlays: OverlayState,
    visual_profile: VisualProfile,
) -> pygame.Surface:
    world = controller.state.world
    detail_scale = max(visual_profile.terrain_scale * 2, 8)
    surface = pygame.Surface((world.grid.width * detail_scale, world.grid.height * detail_scale))
    detail = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    relief = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    rivers = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    movement_min = float(world.movement_cost.min())
    movement_max = float(world.movement_cost.max())
    food_capacity_max = float(world.food_capacity.max())
    profiles = [
        _terrain_profile_for_patch(
            world=world,
            patch_id=patch_id,
            season_name=controller.state.clock.season_name,
            overlays=overlays,
            movement_min=movement_min,
            movement_max=movement_max,
            food_capacity_max=food_capacity_max,
        )
        for patch_id in range(world.grid.size)
    ]
    base_scaled = pygame.transform.smoothscale(
        _build_vertex_color_surface(world, profiles, "base_color"),
        surface.get_size(),
    )
    accent_scaled = pygame.transform.smoothscale(
        _build_vertex_color_surface(world, profiles, "accent_color"),
        surface.get_size(),
    )
    vegetation_scaled = pygame.transform.smoothscale(
        _build_vertex_color_surface(world, profiles, "vegetation_color"),
        surface.get_size(),
    )
    surface.blit(base_scaled, (0, 0))
    accent_scaled.set_alpha(58)
    surface.blit(accent_scaled, (0, 0))
    vegetation_scaled.set_alpha(22 if overlays.food else 10)
    surface.blit(vegetation_scaled, (0, 0))

    for patch_id, profile in enumerate(profiles):
        gx, gy = world.grid.coords(patch_id)
        px = gx * detail_scale
        py = gy * detail_scale
        seed_a, seed_b, seed_c = _terrain_seed_values(patch_id)

        swatch_color = _blend(profile.accent_color, profile.vegetation_color, 0.16 + profile.fertility * 0.32)
        swatch_rect = pygame.Rect(
            int(px - detail_scale * (0.24 + seed_a * 0.08)),
            int(py - detail_scale * (0.18 + seed_b * 0.05)),
            int(detail_scale * (1.48 + profile.fertility * 0.16)),
            int(detail_scale * (1.22 + profile.water_value * 0.18)),
        )
        pygame.draw.ellipse(
            detail,
            (*swatch_color, int(16 + profile.fertility * 22 + profile.water_value * 16)),
            swatch_rect,
        )

        drift_rect = pygame.Rect(
            int(px + detail_scale * (-0.22 + seed_b * 0.18)),
            int(py + detail_scale * (-0.18 + seed_c * 0.16)),
            int(detail_scale * (0.92 + seed_a * 0.24)),
            int(detail_scale * (0.76 + seed_b * 0.18)),
        )
        drift_color = _blend(profile.base_color, (16, 18, 24), 0.08 + profile.roughness * 0.06)
        pygame.draw.ellipse(detail, (*drift_color, int(10 + profile.roughness * 16)), drift_rect)

        if overlays.food and profile.fertility > 0.18 and profile.water_value < 0.58:
            growth_rect = pygame.Rect(
                int(px + detail_scale * (-0.12 + seed_a * 0.12)),
                int(py + detail_scale * (-0.08 + seed_b * 0.10)),
                int(detail_scale * (0.92 + profile.fertility * 0.42)),
                int(detail_scale * (0.74 + profile.fertility * 0.28)),
            )
            growth_color = _blend(profile.vegetation_color, (214, 238, 176), 0.24)
            pygame.draw.ellipse(detail, (*growth_color, int(10 + profile.fertility * 28)), growth_rect)

        west_profile = profiles[world.grid.patch_id(max(0, gx - 1), gy)]
        east_profile = profiles[world.grid.patch_id(min(world.grid.width - 1, gx + 1), gy)]
        north_profile = profiles[world.grid.patch_id(gx, max(0, gy - 1))]
        south_profile = profiles[world.grid.patch_id(gx, min(world.grid.height - 1, gy + 1))]
        slope_x = _terrain_relief_value(east_profile) - _terrain_relief_value(west_profile)
        slope_y = _terrain_relief_value(south_profile) - _terrain_relief_value(north_profile)
        light_bias = _clamp((-slope_x * 0.72) + (-slope_y * 0.94), -1.0, 1.0)
        relief_width = max(4, int(detail_scale * (0.96 + profile.roughness * 0.34)))
        relief_height = max(4, int(detail_scale * (0.82 + profile.shelter * 0.18)))
        if light_bias > 0.02:
            highlight_rect = pygame.Rect(
                int(px - detail_scale * 0.18),
                int(py - detail_scale * 0.15),
                relief_width,
                relief_height,
            )
            pygame.draw.ellipse(
                relief,
                (246, 248, 252, int(light_bias * (14 + profile.roughness * 26 + profile.shelter * 10))),
                highlight_rect,
            )
        if light_bias < -0.02:
            shadow_rect = pygame.Rect(
                int(px + detail_scale * 0.06),
                int(py + detail_scale * 0.10),
                relief_width,
                relief_height,
            )
            pygame.draw.ellipse(
                relief,
                (18, 20, 24, int(abs(light_bias) * (12 + profile.roughness * 24 + profile.danger * 12))),
                shadow_rect,
            )

        if profile.terrain_kind in {"lush_grass", "grassland", "wetland"}:
            grass_color = _blend(profile.vegetation_color, (214, 230, 192), 0.18)
            for idx in range(4):
                blade_x = int(px + detail_scale * (0.16 + ((seed_a + idx * 0.19) % 0.72)))
                blade_y = int(py + detail_scale * (0.40 + ((seed_b + idx * 0.13) % 0.36)))
                blade_h = max(2, int(detail_scale * (0.17 + idx * 0.028)))
                pygame.draw.line(detail, (*grass_color, 54), (blade_x, blade_y), (blade_x, blade_y - blade_h), 1)
        elif profile.terrain_kind == "woodland":
            for idx in range(4):
                canopy_x = int(px + detail_scale * (0.18 + ((seed_a + idx * 0.17) % 0.64)))
                canopy_y = int(py + detail_scale * (0.22 + ((seed_b + idx * 0.19) % 0.58)))
                canopy_r = max(1, detail_scale // 5)
                pygame.draw.circle(detail, (*profile.vegetation_color, 52), (canopy_x, canopy_y), canopy_r)
                pygame.draw.circle(detail, (*_blend(profile.vegetation_color, (34, 58, 34), 0.35), 46), (canopy_x, canopy_y), max(1, canopy_r - 1))
        elif profile.terrain_kind in {"rock", "badlands", "scrub"}:
            ridge_color = _blend(profile.accent_color, (46, 42, 40), 0.32)
            pygame.draw.line(
                detail,
                (*ridge_color, 44),
                (int(px + detail_scale * 0.08), int(py + detail_scale * (0.32 + seed_a * 0.22))),
                (int(px + detail_scale * 0.94), int(py + detail_scale * (0.54 + seed_b * 0.16))),
                1,
            )
            if profile.terrain_kind == "badlands":
                pygame.draw.line(
                    detail,
                    (*_blend(ridge_color, (188, 104, 98), 0.25), 38),
                    (int(px + detail_scale * 0.22), int(py + detail_scale * 0.14)),
                    (int(px + detail_scale * 0.72), int(py + detail_scale * 0.82)),
                    1,
                )

        if overlays.danger and profile.danger > 0.15:
            radius = max(2, int(detail_scale * (0.22 + profile.danger * 0.22)))
            offset = (int(px + detail_scale * (0.50 + seed_a * 0.18)), int(py + detail_scale * (0.48 + seed_b * 0.18)))
            pygame.draw.circle(detail, (214, 78, 92, int(24 + profile.danger * 44)), offset, radius)
            slash_color = (255, 152, 150, int(14 + profile.danger * 24))
            slash_len = max(2, detail_scale // 3)
            pygame.draw.line(detail, slash_color, (offset[0] - slash_len, offset[1] - slash_len), (offset[0] + slash_len, offset[1] + slash_len), 1)
            pygame.draw.line(detail, slash_color, (offset[0] - slash_len, offset[1] + slash_len), (offset[0] + slash_len, offset[1] - slash_len), 1)
        if overlays.shelter and profile.shelter > 0.18 and profile.terrain_kind not in {"deep_water", "river"}:
            line_y = int(py + detail_scale * (0.25 + seed_c * 0.45))
            pygame.draw.line(
                detail,
                (198, 170, 122, int(16 + profile.shelter * 28)),
                (px + 1, line_y),
                (px + detail_scale - 2, line_y + (1 if seed_a > 0.5 else 0)),
                1,
            )

        if overlays.water and profile.water_value > 0.14:
            center_x = px + detail_scale * 0.5
            center_y = py + detail_scale * 0.5
            river_radius = max(2, int(detail_scale * (0.12 + profile.water_value * 0.24)))
            river_color = (46, 132, 214, int(70 + profile.water_value * 80))
            highlight = (196, 232, 255, int(14 + profile.water_value * 30))
            pygame.draw.circle(rivers, river_color, (int(center_x), int(center_y)), river_radius)
            pygame.draw.circle(rivers, highlight, (int(center_x), int(center_y)), max(1, river_radius // 2))
            shimmer_rect = pygame.Rect(
                int(center_x - river_radius * 1.1),
                int(center_y - river_radius * 0.72),
                max(2, int(river_radius * 2.2)),
                max(2, int(river_radius * 1.35)),
            )
            pygame.draw.arc(rivers, (226, 244, 255, int(12 + profile.water_value * 22)), shimmer_rect, 0.3, 2.4, 1)
            for neighbor in world.grid.neighbor_tuple(patch_id):
                if neighbor <= patch_id:
                    continue
                neighbor_profile = profiles[neighbor]
                if neighbor_profile.water_value <= 0.14:
                    continue
                nx, ny = world.grid.coords(neighbor)
                neighbor_center = (nx * detail_scale + detail_scale * 0.5, ny * detail_scale + detail_scale * 0.5)
                avg_water = (profile.water_value + neighbor_profile.water_value) * 0.5
                width = max(2, int(detail_scale * (0.08 + avg_water * 0.24)))
                pygame.draw.line(rivers, (44, 124, 206, int(64 + avg_water * 78)), (center_x, center_y), neighbor_center, width)
                pygame.draw.line(rivers, (198, 234, 255, int(10 + avg_water * 24)), (center_x, center_y), neighbor_center, max(1, width // 3))
            shore_neighbors = sum(1 for neighbor in world.grid.neighbor_tuple(patch_id) if float(world.water[neighbor]) < 0.1)
            if shore_neighbors:
                pygame.draw.circle(
                    rivers,
                    (226, 238, 214, int(10 + profile.water_value * 18)),
                    (int(center_x), int(center_y)),
                    river_radius + 1,
                    1,
                )

    surface.blit(relief, (0, 0))
    surface.blit(detail, (0, 0))
    surface.blit(rivers, (0, 0))
    return surface


def _terrain_surface_key(controller: ViewerController, overlays: OverlayState, visual_profile: VisualProfile) -> tuple[object, ...]:
    dynamic_state = controller.state.clock.tick if overlays.resource_pressure else controller.state.clock.season_name if overlays.season_tint else "static"
    return (
        controller.state.world.grid.width,
        controller.state.world.grid.height,
        visual_profile.terrain_scale,
        overlays.terrain,
        overlays.water,
        overlays.food,
        overlays.danger,
        overlays.shelter,
        overlays.season_tint,
        overlays.resource_pressure,
        dynamic_state,
    )


def _cached_terrain_surface(
    controller: ViewerController,
    overlays: OverlayState,
    render_state: ViewerRenderState,
    visual_profile: VisualProfile,
    map_size: tuple[int, int],
) -> pygame.Surface:
    terrain_key = _terrain_surface_key(controller, overlays, visual_profile)
    cache = render_state.terrain_cache
    if cache.terrain_key != terrain_key or cache.terrain_surface is None:
        cache.terrain_surface = _build_terrain_surface(controller, overlays, visual_profile)
        cache.terrain_key = terrain_key
        cache.scaled_surface = None
        cache.scaled_key = None

    scaled_key = (*terrain_key, map_size)
    if cache.scaled_key != scaled_key or cache.scaled_surface is None:
        cache.scaled_surface = pygame.transform.smoothscale(cache.terrain_surface, map_size)
        cache.scaled_key = scaled_key
    return cache.scaled_surface


def _draw_world(
    surface: pygame.Surface,
    controller: ViewerController,
    overlays: OverlayState,
    map_rect: pygame.Rect,
    cell_size: int,
    render_state: ViewerRenderState,
    ambience_seconds: float,
    visual_profile: VisualProfile,
    frame_snapshot: ViewerFrameSnapshot,
) -> None:
    state = controller.state
    world = state.world
    camps = {camp.patch_id: camp for camp in frame_snapshot.camps}
    clusters = {cluster.patch_id: cluster for cluster in frame_snapshot.clusters}
    water_hotspots = [patch_id for patch_id, value in enumerate(world.water) if float(value) > 0.64]
    danger_hotspots = [patch_id for patch_id, value in enumerate(world.danger) if float(value) > 0.58]
    terrain_scaled = _cached_terrain_surface(controller, overlays, render_state, visual_profile, map_rect.size)
    surface.blit(terrain_scaled, map_rect.topleft)
    pygame.draw.rect(surface, (24, 28, 34), map_rect, 1, border_radius=16)

    for patch_id in water_hotspots:
        center = _patch_center(world.grid, patch_id, map_rect, cell_size)
        water_value = float(world.water[patch_id])
        pulse = 0.78 + 0.22 * sin(ambience_seconds * 2.8 + patch_id * 0.19)
        _draw_glow(surface, center, cell_size * (0.26 + water_value * 0.16), (78, 162, 255), int((26 + water_value * 28) * pulse * visual_profile.glow_scale))
        if cell_size >= 11:
            ripple_rect = pygame.Rect(0, 0, int(cell_size * 0.9), int(cell_size * 0.55))
            ripple_rect.center = (int(center[0]), int(center[1]))
            pygame.draw.arc(surface, (214, 238, 255), ripple_rect, 0.3, 2.8, 1)

    for patch_id in danger_hotspots:
        center = _patch_center(world.grid, patch_id, map_rect, cell_size)
        danger_value = float(world.danger[patch_id])
        _draw_glow(surface, center, cell_size * (0.22 + danger_value * 0.18), (220, 82, 96), int((24 + danger_value * 34) * visual_profile.glow_scale))
        if cell_size >= 10:
            slash = max(3, int(cell_size * 0.18))
            pygame.draw.line(surface, (255, 152, 154), (center[0] - slash, center[1] - slash), (center[0] + slash, center[1] + slash), 1)
            pygame.draw.line(surface, (255, 152, 154), (center[0] - slash, center[1] + slash), (center[0] + slash, center[1] - slash), 1)

    for cluster in clusters.values():
        if cluster.occupants < 2:
            continue
        center = _patch_center(world.grid, cluster.patch_id, map_rect, cell_size)
        cluster_strength = min(1.0, cluster.occupants / 7.0 + cluster.kin_links * 0.06)
        _draw_glow(
            surface,
            center,
            cell_size * (0.22 + cluster_strength * 0.24),
            (176, 190, 255),
            int((26 + cluster_strength * 26) * visual_profile.glow_scale),
        )
        if cluster.occupants >= 3 and cell_size >= 10:
            pygame.draw.circle(surface, (198, 210, 248), (int(center[0]), int(center[1])), max(4, cell_size // 3), 1)

    if overlays.paths:
        for path in world.path_traces.values():
            if path.strength < 0.04:
                continue
            a, b = path.edge
            start = _patch_center(world.grid, a, map_rect, cell_size)
            end = _patch_center(world.grid, b, map_rect, cell_size)
            _draw_glow(surface, start, cell_size * 0.18, _path_color(path.strength), int(16 * visual_profile.glow_scale))
            color = _path_color(path.strength)
            width = 1 + int(min(3, path.strength * 3.0))
            pygame.draw.line(surface, color, start, end, width)

    if overlays.camps:
        for camp in camps.values():
            center = _patch_center(world.grid, camp.patch_id, map_rect, cell_size)
            pulse = 0.82 + 0.18 * sin(ambience_seconds * 3.0 + camp.patch_id * 0.27)
            glow_radius = cell_size * (0.32 + min(0.55, camp.hearth_intensity * 0.09))
            reuse_radius = cell_size * (0.22 + min(0.65, camp.visit_count * 0.01))
            _draw_glow(surface, center, reuse_radius, (124, 82, 46), int(24 * visual_profile.glow_scale))
            _draw_glow(surface, center, glow_radius, (255, 173, 92), int(50 * pulse * visual_profile.glow_scale))
            outer_radius = max(4, int(cell_size * 0.22 + min(7, camp.visit_count * 0.03)))
            inner_radius = max(2, int(cell_size * 0.14 + min(4, camp.hearth_intensity * 0.4)))
            pygame.draw.circle(surface, (94, 70, 44), (int(center[0]), int(center[1])), outer_radius + 1)
            pygame.draw.circle(surface, (242, 182, 84), (int(center[0]), int(center[1])), outer_radius, 1)
            pygame.draw.circle(surface, (255, 224, 128), (int(center[0]), int(center[1])), inner_radius)
            for ember_idx in range(3):
                ember_angle = ambience_seconds * 1.6 + camp.patch_id * 0.31 + ember_idx * 2.1
                ember_pos = (
                    center[0] + cos(ember_angle) * max(2, inner_radius * 0.8),
                    center[1] + sin(ember_angle) * max(2, inner_radius * 0.8),
                )
                pygame.draw.circle(surface, (255, 212, 120), (int(ember_pos[0]), int(ember_pos[1])), 1)
            if camp.communal_food > 0.15:
                size = max(3, cell_size // 5)
                cache_rect = pygame.Rect(int(center[0] + outer_radius * 0.45), int(center[1] - outer_radius * 0.6), size, size)
                pygame.draw.rect(surface, (168, 106, 48), cache_rect, border_radius=2)
                pygame.draw.rect(surface, (222, 184, 132), cache_rect, 1, border_radius=2)


def _draw_selected_memory_overlays(
    surface: pygame.Surface,
    controller: ViewerController,
    overlays: OverlayState,
    map_rect: pygame.Rect,
    cell_size: int,
    ambience_seconds: float,
    visual_profile: VisualProfile,
) -> None:
    if controller.selected_agent_id is None or controller.selected_agent_id not in controller.state.agents_by_id:
        return
    agent = controller.state.agents_by_id[controller.selected_agent_id]
    pulse = 0.75 + 0.25 * sin(ambience_seconds * 4.0 + agent.agent_id * 0.21)
    for entry in agent.spatial_memory.values():
        center = _patch_center(controller.state.world.grid, entry.patch_id, map_rect, cell_size)
        radius = max(5, int(cell_size * 0.2))
        if overlays.remembered_good and entry.kind in {"water", "food", "shelter"}:
            if entry.kind == "water":
                color = (80, 176, 255)
            elif entry.kind == "food":
                color = (98, 226, 120)
            else:
                color = (238, 210, 152)
            width = 1 + int(min(3, max(0.0, entry.revisit_bias) * 1.1))
            _draw_glow(surface, center, radius + 3, color, int(34 * pulse * visual_profile.glow_scale))
            pygame.draw.circle(surface, color, (int(center[0]), int(center[1])), radius + width + 2, width)
        if overlays.remembered_danger and (entry.kind == "danger" or entry.avoidance_bias > 0.25):
            danger_color = (255, 102, 102)
            offset = radius + 3
            _draw_glow(surface, center, radius + 4, danger_color, int(32 * pulse * visual_profile.glow_scale))
            pygame.draw.line(surface, danger_color, (center[0] - offset, center[1] - offset), (center[0] + offset, center[1] + offset), 2)
            pygame.draw.line(surface, danger_color, (center[0] - offset, center[1] + offset), (center[0] + offset, center[1] - offset), 2)


def _draw_social_links(
    surface: pygame.Surface,
    controller: ViewerController,
    positions: dict[int, tuple[float, float]],
) -> None:
    selected_id = controller.selected_agent_id
    if selected_id is None or selected_id not in controller.state.agents_by_id:
        return
    agent = controller.state.agents_by_id[selected_id]
    start = positions.get(agent.agent_id)
    if start is None:
        return
    for edge in sorted(
        agent.social_memory.values(),
        key=lambda entry: abs(entry.trust) + entry.attachment + entry.harm,
        reverse=True,
    )[:24]:
        other = controller.state.agents_by_id.get(edge.other_agent_id)
        if other is None or not other.alive:
            continue
        end = positions.get(other.agent_id)
        if end is None:
            continue
        positive_strength = max(0.0, edge.trust) + edge.attachment
        negative_strength = edge.harm + max(0.0, -edge.trust)
        if positive_strength <= 0.08 and negative_strength <= 0.1:
            continue
        if negative_strength > positive_strength:
            color = (240, 92, 98)
            width = 1 + int(min(3, negative_strength * 1.7))
        else:
            color = (104, 224, 130)
            width = 1 + int(min(3, positive_strength * 1.4))
        pygame.draw.line(surface, color, start, end, width)


def _draw_kin_links(
    surface: pygame.Surface,
    controller: ViewerController,
    positions: dict[int, tuple[float, float]],
) -> None:
    selected_id = controller.selected_agent_id
    if selected_id is None or selected_id not in controller.state.agents_by_id:
        return
    agent = controller.state.agents_by_id[selected_id]
    start = positions.get(agent.agent_id)
    if start is None:
        return
    for other_id in [*agent.parent_ids, *agent.child_ids]:
        other = controller.state.agents_by_id.get(other_id)
        if other is None or not other.alive:
            continue
        end = positions.get(other.agent_id)
        if end is None:
            continue
        pygame.draw.line(surface, (106, 186, 255), start, end, 2)
        _draw_glow(surface, end, 8, (106, 186, 255), 28)


def _draw_agent_trails(
    surface: pygame.Surface,
    render_state: ViewerRenderState,
    positions: dict[int, tuple[float, float]],
    visual_profile: VisualProfile,
) -> None:
    for agent_id, samples in render_state.trails.items():
        if agent_id not in positions or not samples:
            continue
        current = positions[agent_id]
        previous = current
        for sample in samples:
            alpha = int(90 * sample.strength)
            color = (150, 176, 220)
            _draw_glow(surface, (sample.x, sample.y), 5, color, max(6, int(alpha * 0.25 * visual_profile.glow_scale)))
            pygame.draw.line(surface, _blend((30, 34, 46), color, sample.strength * 0.85), previous, (sample.x, sample.y), 1)
            previous = (sample.x, sample.y)


def _draw_care_links(
    surface: pygame.Surface,
    controller: ViewerController,
    positions: dict[int, tuple[float, float]],
    visual_profile: VisualProfile,
) -> None:
    for agent in controller.state.agents:
        if not agent.alive or agent.age_stage != "child" or agent.caregiver_id is None:
            continue
        caregiver = controller.state.agents_by_id.get(agent.caregiver_id)
        if caregiver is None or not caregiver.alive:
            continue
        child_pos = positions.get(agent.agent_id)
        caregiver_pos = positions.get(caregiver.agent_id)
        if child_pos is None or caregiver_pos is None:
            continue
        dx = child_pos[0] - caregiver_pos[0]
        dy = child_pos[1] - caregiver_pos[1]
        if dx * dx + dy * dy > 1800:
            continue
        active = agent.current_action == "follow_caregiver" or caregiver.current_action == "care_for_child"
        color = (92, 220, 232) if active else (74, 156, 176)
        width = 2 if active else 1
        pygame.draw.line(surface, color, child_pos, caregiver_pos, width)
        mid = ((child_pos[0] + caregiver_pos[0]) * 0.5, (child_pos[1] + caregiver_pos[1]) * 0.5)
        _draw_glow(surface, mid, 4, color, int(20 * visual_profile.glow_scale if active else 10 * visual_profile.glow_scale))


def _draw_human_icon(
    surface: pygame.Surface,
    agent,
    pos: tuple[float, float],
    selected: bool,
    cell_size: int,
    ambience_seconds: float,
    show_needs: bool,
    visual_profile: VisualProfile,
) -> None:
    body_color, head_color, shadow_color = _age_palette(agent)
    if show_needs:
        stress_tint = _clamp(agent.stress / 2.0, 0.0, 1.0)
        body_color = _blend(body_color, (236, 92, 94), stress_tint * 0.7)

    scale = max(5.0, cell_size * 0.28)
    if agent.age_stage == "child":
        scale *= 0.72
    elif agent.age_stage == "elder":
        scale *= 0.96

    moving = agent.current_action in {"move_local", "move_to_known_site", "follow_caregiver", "avoid_danger", "explore"}
    resting = agent.current_action in {"rest", "shelter_at_site", "stay_with_kin"}
    caring = agent.current_action in {"care_for_child", "share_food"}
    phase = ambience_seconds * (7.0 if moving else 2.8) + agent.agent_id * 0.63
    bob = sin(phase) * (0.9 if moving else 0.22) * visual_profile.bob_scale
    stride = sin(phase) * (0.42 if moving else 0.06)
    lean = 0.0
    crouch = 0.0
    if moving:
        lean += 0.22 if agent.current_action in {"explore", "move_local"} else 0.12
    if resting:
        crouch += 0.22
        lean -= 0.08
    if caring:
        lean += 0.06
    if agent.age_stage == "elder":
        lean -= 0.14

    x = pos[0]
    y = pos[1] + bob
    shadow_rect = pygame.Rect(0, 0, int(scale * 1.3), max(3, int(scale * 0.42)))
    shadow_rect.center = (int(x), int(y + scale * 0.95))
    pygame.draw.ellipse(surface, _blend(shadow_color, (18, 20, 28), 0.55), shadow_rect)

    head_radius = max(2, int(scale * (0.28 if agent.age_stage == "child" else 0.23)))
    hip = (x + lean * scale * 0.5, y + scale * (0.25 + crouch * 0.2))
    neck = (x + lean * scale * 0.2, y - scale * 0.35)
    head_center = (int(neck[0]), int(neck[1] - head_radius * 1.15))
    left_foot = (x - scale * 0.22 - stride * scale * 0.28, y + scale * 0.92)
    right_foot = (x + scale * 0.22 + stride * scale * 0.28, y + scale * 0.92)
    left_hand = (x - scale * 0.28, y + scale * (0.05 if caring else -0.02))
    right_hand = (x + scale * 0.28, y + scale * (-0.12 if agent.current_action == "explore" else 0.04))
    line_width = max(1, int(scale * 0.18))
    outline_width = line_width + 2
    outline_color = (16, 18, 24)

    _draw_glow(surface, (x, y - scale * 0.04), scale * 0.58, outline_color, int(16 * visual_profile.glow_scale))
    pygame.draw.line(surface, outline_color, neck, hip, outline_width)
    pygame.draw.line(surface, outline_color, (x, y - scale * 0.12), left_hand, max(2, outline_width - 1))
    pygame.draw.line(surface, outline_color, (x, y - scale * 0.12), right_hand, max(2, outline_width - 1))
    pygame.draw.line(surface, outline_color, hip, left_foot, max(2, outline_width - 1))
    pygame.draw.line(surface, outline_color, hip, right_foot, max(2, outline_width - 1))
    shoulder_left = (x - scale * 0.18, y - scale * 0.12)
    shoulder_right = (x + scale * 0.18, y - scale * 0.12)
    pygame.draw.line(surface, outline_color, shoulder_left, shoulder_right, max(2, outline_width - 1))
    pygame.draw.circle(surface, outline_color, head_center, head_radius + 1)

    pygame.draw.line(surface, body_color, neck, hip, line_width)
    pygame.draw.line(surface, body_color, (x, y - scale * 0.12), left_hand, max(1, line_width - 1))
    pygame.draw.line(surface, body_color, (x, y - scale * 0.12), right_hand, max(1, line_width - 1))
    pygame.draw.line(surface, body_color, hip, left_foot, max(1, line_width - 1))
    pygame.draw.line(surface, body_color, hip, right_foot, max(1, line_width - 1))
    pygame.draw.line(surface, body_color, shoulder_left, shoulder_right, max(1, line_width - 1))
    pygame.draw.circle(surface, head_color, head_center, head_radius)
    pygame.draw.circle(surface, _blend(body_color, (20, 20, 20), 0.35), head_center, head_radius, 1)

    if agent.age_stage == "elder":
        cane_top = (x + scale * 0.34, y + scale * 0.08)
        cane_bottom = (x + scale * 0.40, y + scale * 0.98)
        pygame.draw.line(surface, (176, 152, 108), cane_top, cane_bottom, 1)

    if agent.carried_food > 0.2:
        satchel_rect = pygame.Rect(int(x + scale * 0.14), int(y + scale * 0.02), max(3, int(scale * 0.24)), max(3, int(scale * 0.18)))
        pygame.draw.rect(surface, (88, 222, 108), satchel_rect, border_radius=2)
        pygame.draw.rect(surface, (224, 246, 210), satchel_rect, 1, border_radius=2)

    if caring:
        _draw_glow(surface, (x, y), scale * 0.72, (88, 214, 230), int(28 * visual_profile.glow_scale))
    if agent.current_action == "explore":
        pygame.draw.circle(surface, (246, 224, 120), (int(x + scale * 0.54), int(y - scale * 0.55)), max(1, int(scale * 0.09)))
    if agent.current_action == "avoid_danger" or agent.stress > 0.95:
        ring_radius = int(scale * (0.78 + 0.08 * sin(phase * 0.7)))
        pygame.draw.circle(surface, (242, 92, 98), (int(x), int(y)), ring_radius, 1)
        pygame.draw.line(surface, (242, 92, 98), (x, y - scale * 0.95), (x, y - scale * 1.25), 2)
        pygame.draw.circle(surface, (242, 92, 98), (int(x), int(y - scale * 1.36)), max(1, int(scale * 0.06)))
    if resting:
        rest_y = y + scale * 0.82
        pygame.draw.line(surface, (146, 158, 184), (x - scale * 0.24, rest_y), (x + scale * 0.24, rest_y), 1)
        pygame.draw.arc(
            surface,
            (164, 174, 204),
            pygame.Rect(x + scale * 0.34, y - scale * 0.86, scale * 0.36, scale * 0.36),
            1.0,
            4.9,
            1,
        )
    if selected:
        _draw_glow(surface, (x, y), scale * 0.95, (255, 240, 134), int(36 * visual_profile.glow_scale))
        pygame.draw.circle(surface, (255, 243, 126), (int(x), int(y)), int(scale * 0.86), 2)

    if show_needs:
        bar_w = max(2, int(scale * 0.16))
        base_x = int(x - scale * 0.34)
        base_y = int(y - scale * 1.25)
        hunger_h = int(10 * _clamp(agent.hunger / 2.0, 0.0, 1.0))
        thirst_h = int(10 * _clamp(agent.thirst / 2.0, 0.0, 1.0))
        stress_h = int(10 * _clamp(agent.stress / 2.0, 0.0, 1.0))
        pygame.draw.rect(surface, (222, 144, 74), (base_x, base_y + (10 - hunger_h), bar_w, hunger_h))
        pygame.draw.rect(surface, (74, 152, 238), (base_x + bar_w + 1, base_y + (10 - thirst_h), bar_w, thirst_h))
        pygame.draw.rect(surface, (232, 88, 88), (base_x + (bar_w + 1) * 2, base_y + (10 - stress_h), bar_w, stress_h))


def _draw_agents(
    surface: pygame.Surface,
    controller: ViewerController,
    overlays: OverlayState,
    render_state: ViewerRenderState,
    cell_size: int,
    positions: dict[int, tuple[float, float]],
    visual_profile: VisualProfile,
) -> None:
    if overlays.movement:
        _draw_agent_trails(surface, render_state, positions, visual_profile)
    _draw_care_links(surface, controller, positions, visual_profile)
    for agent in controller.state.agents:
        if not agent.alive:
            continue
        pos = positions.get(agent.agent_id)
        if pos is None:
            continue
        _draw_human_icon(
            surface=surface,
            agent=agent,
            pos=pos,
            selected=agent.agent_id == controller.selected_agent_id,
            cell_size=cell_size,
            ambience_seconds=render_state.ambience_seconds,
            show_needs=overlays.needs,
            visual_profile=visual_profile,
        )


def _select_agent_from_click(
    controller: ViewerController,
    map_rect: pygame.Rect,
    cell_size: int,
    positions: dict[int, tuple[float, float]],
    mouse_pos: tuple[int, int],
) -> int | None:
    patch_id = _patch_at_position(controller.state.world.grid, map_rect, cell_size, mouse_pos)
    if patch_id is None:
        return None
    occupants = controller.state.world.occupancy.get(patch_id, [])
    if occupants:
        best_id = None
        best_dist = 10**9
        for agent_id in occupants:
            pos = positions.get(agent_id)
            if pos is None:
                continue
            dx = pos[0] - mouse_pos[0]
            dy = pos[1] - mouse_pos[1]
            dist = dx * dx + dy * dy
            if dist < best_dist:
                best_dist = dist
                best_id = agent_id
        return best_id
    best_id = None
    best_dist = max(14, cell_size) ** 2
    for agent_id, pos in positions.items():
        dx = pos[0] - mouse_pos[0]
        dy = pos[1] - mouse_pos[1]
        dist = dx * dx + dy * dy
        if dist < best_dist:
            best_dist = dist
            best_id = agent_id
    return best_id


def _draw_panel(
    surface: pygame.Surface,
    controller: ViewerController,
    overlays: OverlayState,
    panel_rect: pygame.Rect,
    loop_fps: float,
    render_fps_target: int,
    visual_profile: VisualProfile,
    frame_snapshot: ViewerFrameSnapshot,
) -> None:
    panel_surface = pygame.Surface((panel_rect.width, panel_rect.height), pygame.SRCALPHA)
    pygame.draw.rect(panel_surface, (18, 20, 28, visual_profile.panel_alpha), panel_surface.get_rect(), border_radius=18)
    surface.blit(panel_surface, panel_rect.topleft)
    pygame.draw.rect(surface, (54, 58, 72), panel_rect, 1, border_radius=18)
    font = _font(15)
    small_font = _font(13)
    title_font = _font(22, bold=True)

    metrics = frame_snapshot.metrics
    events = frame_snapshot.events
    selected_lines = frame_snapshot.selected_lines

    x = panel_rect.left + 14
    y = panel_rect.top + 14
    surface.blit(title_font.render("CivSim Alive Sandbox", True, (238, 241, 246)), (x, y))
    y += 34

    chip_x = x
    chip_x = _draw_chip(surface, small_font, f"seed {controller.seed}", chip_x, y, (52, 76, 116))
    chip_x = _draw_chip(surface, small_font, f"{metrics.season} season", chip_x, y, (64, 92, 78) if metrics.season == "good" else (86, 72, 112))
    chip_x = _draw_chip(surface, small_font, f"{controller.speed_label}", chip_x, y, (102, 74, 132))
    chip_x = _draw_chip(surface, small_font, "paused" if controller.paused else "running", chip_x, y, (90, 82, 62) if controller.paused else (58, 104, 84))
    if overlays.needs:
        chip_x = _draw_chip(surface, small_font, "needs", chip_x, y, (98, 72, 62))
    if overlays.social_links:
        chip_x = _draw_chip(surface, small_font, "social", chip_x, y, (66, 108, 84))
    if overlays.kin_links:
        chip_x = _draw_chip(surface, small_font, "kin", chip_x, y, (74, 108, 146))
    y += 38

    stats_rect = pygame.Rect(x, y, panel_rect.width - 28, 178)
    _draw_card(surface, stats_rect, "World State", (100, 132, 214))
    stats_lines = [
        f"tick {metrics.tick}  day {metrics.day}  phase {metrics.tick_in_day + 1}/{controller.state.config.world.ticks_per_day}",
        f"population {metrics.living_population}  children {metrics.living_children}  elders {metrics.living_elders}",
        f"camps {metrics.active_camps}  clusters {metrics.active_clusters}  paths {metrics.path_count}",
        f"site reuse {_format_ratio(metrics.site_reuse_frequency)}  co-residence {_format_ratio(metrics.mean_co_residence)}",
        f"sharing {metrics.sharing_events}  child survival {_format_ratio(metrics.child_survival_rate)} ({metrics.child_survival_trend})",
        f"recent births {metrics.recent_births}  recent deaths {metrics.recent_deaths}",
        f"loop fps {_format_ratio(loop_fps)}  draw cap {render_fps_target} fps",
        f"sim steps/frame {controller.last_steps_run}  queued {_format_ratio(controller.queued_ticks)}",
    ]
    _draw_text_lines(surface, font, stats_lines, stats_rect.x + 16, stats_rect.y + 36, (210, 216, 228), 18)
    y = stats_rect.bottom + 10

    selected_rect = pygame.Rect(x, y, panel_rect.width - 28, 290)
    _draw_card(surface, selected_rect, "Selected Individual", (114, 192, 164))
    _draw_text_lines(surface, small_font, selected_lines, selected_rect.x + 16, selected_rect.y + 36, (204, 211, 221), 16, max_lines=17)
    y = selected_rect.bottom + 10

    events_height = max(130, panel_rect.bottom - y - 74)
    events_rect = pygame.Rect(x, y, panel_rect.width - 28, events_height)
    _draw_card(surface, events_rect, "Recent Events", (214, 144, 94))
    _draw_text_lines(surface, small_font, events or ["No major events yet."], events_rect.x + 16, events_rect.y + 36, (206, 212, 221), 16, max_lines=15)

    if overlays.help:
        footer_y = panel_rect.bottom - 56
        help_lines = [
            "Use the top control bar for play, step, speed, and overlay toggles.",
            "Terrain: blue rivers/water, green fertile ground, gray-brown rough land, red danger.",
            "Keyboard shortcuts still work: Space/T/Y/R, [ ], , ., 0-9, K/P/S, G/X, H.",
            "Click any agent on the terrain to inspect it in the side panel.",
        ]
        _draw_text_lines(surface, small_font, help_lines, x, footer_y, (164, 170, 184), 16)


def _handle_button_action(button_action: str, controller: ViewerController, overlays: OverlayState) -> None:
    if button_action == "play":
        controller.set_paused(False)
        return
    if button_action == "pause":
        controller.set_paused(True)
        return
    if button_action == "restart":
        if controller.randomize_on_restart:
            controller.restart_random()
        else:
            controller.restart()
        return
    if button_action == "step_tick":
        controller.queue_tick()
        controller.set_paused(True)
        return
    if button_action == "step_day":
        controller.queue_day()
        controller.set_paused(True)
        return
    if button_action.startswith("speed:"):
        controller.set_speed_index(int(button_action.split(":", 1)[1]))
        return
    if not button_action.startswith("toggle:"):
        return
    attribute = button_action.split(":", 1)[1]
    if hasattr(overlays, attribute):
        setattr(overlays, attribute, not getattr(overlays, attribute))


def run_viewer(
    config,
    seed: int | None = None,
    max_days: int | None = None,
    start_paused: bool = False,
    max_frames: int | None = None,
    auto_close_on_finish: bool = False,
    finish_hold_seconds: float = 0.9,
    randomize_restart_seed: bool = False,
) -> object:
    pygame.init()
    pygame.display.set_caption("CivSim Alive Viewer")
    screen = pygame.display.set_mode((1560, 980), pygame.RESIZABLE)
    frame_clock = pygame.time.Clock()

    controller = ViewerController(
        base_config=config,
        seed=seed if seed is not None else config.run.seed,
        max_days=max_days,
        randomize_on_restart=randomize_restart_seed,
    )
    controller.set_paused(start_paused)
    overlays = OverlayState()
    render_state = ViewerRenderState()
    snapshot_cache = ViewerSnapshotCache()
    running = True
    frames = 0
    render_accumulator = 1.0
    finish_hold_elapsed = 0.0

    while running and (max_frames is None or frames < max_frames):
        dt_seconds = frame_clock.tick(120) / 1000.0
        visual_profile = _visual_profile(controller)
        width, height = screen.get_size()
        panel_width = min(470, max(390, width // 3))
        margin = 14
        control_height = 122 if overlays.overlay_panel else 84
        controls_rect = pygame.Rect(margin, margin, width - margin * 2, control_height)
        content_top = controls_rect.bottom + margin
        map_width = max(240, width - panel_width - margin * 3)
        map_height = max(240, height - content_top - margin)
        cell_size = max(
            8,
            min(
                map_width // controller.state.world.grid.width,
                map_height // controller.state.world.grid.height,
            ),
        )
        rendered_map_width = cell_size * controller.state.world.grid.width
        rendered_map_height = cell_size * controller.state.world.grid.height
        map_rect = pygame.Rect(margin, content_top, rendered_map_width, rendered_map_height)
        panel_rect = pygame.Rect(map_rect.right + margin, content_top, width - map_rect.right - margin * 2, height - content_top - margin)
        button_font = _font(14, bold=True)
        buttons = build_control_buttons(controls_rect, button_font, controller, overlays)

        target_positions = _build_patch_agent_targets(controller, map_rect, cell_size)
        positions = dict(render_state.visual_positions) if render_state.visual_positions else dict(target_positions)

        force_redraw = frames == 0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    controller.toggle_pause()
                    force_redraw = True
                elif event.key == pygame.K_t:
                    controller.queue_tick()
                    controller.set_paused(True)
                    force_redraw = True
                elif event.key == pygame.K_y:
                    controller.queue_day()
                    controller.set_paused(True)
                    force_redraw = True
                elif event.key == pygame.K_r:
                    if controller.randomize_on_restart:
                        controller.restart_random()
                    else:
                        controller.restart()
                    render_state = ViewerRenderState()
                    force_redraw = True
                elif event.key == pygame.K_LEFTBRACKET:
                    controller.change_speed(-1)
                    force_redraw = True
                elif event.key == pygame.K_RIGHTBRACKET:
                    controller.change_speed(1)
                    force_redraw = True
                elif event.key == pygame.K_COMMA:
                    controller.change_seed(-1)
                    render_state = ViewerRenderState()
                    force_redraw = True
                elif event.key == pygame.K_PERIOD:
                    controller.change_seed(1)
                    render_state = ViewerRenderState()
                    force_redraw = True
                elif event.key == pygame.K_0:
                    overlays.movement = not overlays.movement
                    force_redraw = True
                elif event.key == pygame.K_1:
                    overlays.terrain = not overlays.terrain
                    force_redraw = True
                elif event.key == pygame.K_2:
                    overlays.water = not overlays.water
                    force_redraw = True
                elif event.key == pygame.K_3:
                    overlays.food = not overlays.food
                    force_redraw = True
                elif event.key == pygame.K_4:
                    overlays.danger = not overlays.danger
                    force_redraw = True
                elif event.key == pygame.K_5:
                    overlays.shelter = not overlays.shelter
                    force_redraw = True
                elif event.key == pygame.K_6:
                    overlays.camps = not overlays.camps
                    force_redraw = True
                elif event.key == pygame.K_7:
                    overlays.paths = not overlays.paths
                    force_redraw = True
                elif event.key == pygame.K_8:
                    overlays.needs = not overlays.needs
                    force_redraw = True
                elif event.key == pygame.K_9:
                    overlays.social_links = not overlays.social_links
                    force_redraw = True
                elif event.key == pygame.K_k:
                    overlays.kin_links = not overlays.kin_links
                    force_redraw = True
                elif event.key == pygame.K_p:
                    overlays.resource_pressure = not overlays.resource_pressure
                    force_redraw = True
                elif event.key == pygame.K_s:
                    overlays.season_tint = not overlays.season_tint
                    force_redraw = True
                elif event.key == pygame.K_g:
                    overlays.remembered_good = not overlays.remembered_good
                    force_redraw = True
                elif event.key == pygame.K_x:
                    overlays.remembered_danger = not overlays.remembered_danger
                    force_redraw = True
                elif event.key == pygame.K_h:
                    overlays.help = not overlays.help
                    force_redraw = True
                elif event.key == pygame.K_BACKSPACE:
                    controller.select_agent(None)
                    force_redraw = True
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pressed_button = button_at(buttons, event.pos)
                if pressed_button is not None:
                    _handle_button_action(pressed_button.action, controller, overlays)
                    if pressed_button.action in {"restart"}:
                        render_state = ViewerRenderState()
                    force_redraw = True
                    continue
                agent_id = _select_agent_from_click(controller, map_rect, cell_size, positions, event.pos)
                controller.select_agent(agent_id)
                force_redraw = True

        controller.advance(dt_seconds)
        visual_profile = _visual_profile(controller)
        target_positions = _build_patch_agent_targets(controller, map_rect, cell_size)
        positions = render_state.update_positions(
            target_positions=target_positions,
            dt_seconds=dt_seconds,
            speed_multiplier=controller.current_speed_multiplier,
            movement_enabled=overlays.movement,
            max_trail_samples=visual_profile.trail_samples,
            min_trail_distance_sq=visual_profile.trail_distance_sq,
        )

        render_accumulator += dt_seconds
        render_fps_target = _target_render_fps(controller)
        render_interval = 1.0 / max(1, render_fps_target)
        should_draw = force_redraw or render_accumulator >= render_interval
        if not should_draw:
            continue

        render_accumulator = 0.0
        frame_snapshot, snapshot_cache = build_viewer_snapshot(
            controller.state,
            controller.selected_agent_id,
            snapshot_cache,
        )
        screen.fill((11, 13, 18))
        draw_control_bar(
            surface=screen,
            control_rect=controls_rect,
            title="CivSim Sandbox",
            subtitle="live artificial-life viewer",
            buttons=buttons,
            title_font=_font(22, bold=True),
            button_font=button_font,
            mouse_pos=pygame.mouse.get_pos(),
        )
        _draw_world(screen, controller, overlays, map_rect, cell_size, render_state, render_state.ambience_seconds, visual_profile, frame_snapshot)
        _draw_selected_memory_overlays(screen, controller, overlays, map_rect, cell_size, render_state.ambience_seconds, visual_profile)
        if overlays.social_links:
            _draw_social_links(screen, controller, positions)
        if overlays.kin_links:
            _draw_kin_links(screen, controller, positions)
        _draw_agents(screen, controller, overlays, render_state, cell_size, positions, visual_profile)
        _draw_panel(
            screen,
            controller,
            overlays,
            panel_rect,
            loop_fps=frame_clock.get_fps(),
            render_fps_target=render_fps_target,
            visual_profile=visual_profile,
            frame_snapshot=frame_snapshot,
        )
        pygame.display.flip()
        frames += 1

        if auto_close_on_finish and controller.finished:
            finish_hold_elapsed += dt_seconds
            if finish_hold_elapsed >= max(0.0, finish_hold_seconds):
                running = False
        else:
            finish_hold_elapsed = 0.0

    final_state = controller.state
    pygame.quit()
    return final_state
