from __future__ import annotations

import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from collections import defaultdict
from dataclasses import dataclass
from math import cos, sin, tau

import pygame

from ..analysis.detectors import detect_camps
from ..social.coordination import social_patch_bias
from .controller import ViewerController
from .view_model import build_metrics_snapshot, recent_event_lines, selected_agent_lines


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
    needs: bool = False
    social_links: bool = False
    remembered_good: bool = False
    remembered_danger: bool = False
    help: bool = True


def _blend(base: Color, overlay: Color, alpha: float) -> Color:
    alpha = max(0.0, min(1.0, alpha))
    return tuple(int(base[idx] * (1.0 - alpha) + overlay[idx] * alpha) for idx in range(3))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _normalize(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return _clamp((value - low) / (high - low), 0.0, 1.0)


def _age_color(agent) -> Color:
    if agent.age_stage == "child":
        return (255, 220, 120)
    if agent.age_stage == "elder":
        return (190, 170, 225)
    return (235, 240, 245)


def _path_color(strength: float) -> Color:
    intensity = int(110 + min(145, strength * 220))
    return (intensity, 130, 60)


def _agent_offsets(count: int, radius: float) -> list[tuple[float, float]]:
    if count <= 1:
        return [(0.0, 0.0)]
    offsets: list[tuple[float, float]] = []
    ring_radius = max(2.0, radius)
    for idx in range(count):
        angle = (idx / count) * tau
        offsets.append((cos(angle) * ring_radius, sin(angle) * ring_radius))
    return offsets


def _format_ratio(value: float) -> str:
    return f"{value:.2f}"


def _build_patch_agent_positions(controller: ViewerController, map_rect: pygame.Rect, cell_size: int) -> tuple[dict[int, tuple[float, float]], dict[int, pygame.Rect]]:
    positions: dict[int, tuple[float, float]] = {}
    hitboxes: dict[int, pygame.Rect] = {}
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
            pos = (center_x + dx, center_y + dy)
            positions[agent_id] = pos
            hitboxes[agent_id] = pygame.Rect(int(pos[0] - radius - 3), int(pos[1] - radius - 3), int(radius * 2 + 6), int(radius * 2 + 6))
    return positions, hitboxes


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


def _draw_world(
    surface: pygame.Surface,
    controller: ViewerController,
    overlays: OverlayState,
    map_rect: pygame.Rect,
    cell_size: int,
) -> None:
    state = controller.state
    world = state.world
    camps = {camp.patch_id: camp for camp in detect_camps(world)}
    movement_min = float(world.movement_cost.min())
    movement_max = float(world.movement_cost.max())
    food_capacity_max = float(world.food_capacity.max())

    for patch_id in range(world.grid.size):
        gx, gy = world.grid.coords(patch_id)
        rect = pygame.Rect(map_rect.left + gx * cell_size, map_rect.top + gy * cell_size, cell_size, cell_size)
        movement_value = _normalize(float(world.movement_cost[patch_id]), movement_min, movement_max)
        terrain_color = (90, 90, 90)
        if overlays.terrain:
            shade = int(155 - movement_value * 90)
            terrain_color = (shade, shade, shade)
        color = terrain_color

        if overlays.shelter:
            shelter = float(world.shelter[patch_id])
            color = _blend(color, (190, 170, 130), shelter * 0.35)
        if overlays.water:
            water = float(world.water[patch_id])
            color = _blend(color, (60, 135, 225), water * 0.8)
        if overlays.food:
            food = _normalize(float(world.food[patch_id]), 0.0, food_capacity_max)
            color = _blend(color, (65, 170, 70), food * 0.45)
        if overlays.danger:
            danger = float(world.danger[patch_id])
            color = _blend(color, (190, 50, 50), danger * 0.55)

        pygame.draw.rect(surface, color, rect)
        pygame.draw.rect(surface, (32, 32, 38), rect, 1)

        if overlays.camps and patch_id in camps:
            camp = camps[patch_id]
            border = int(1 + min(3, camp.hearth_intensity * 1.2))
            pygame.draw.rect(surface, (250, 190, 80), rect, border)
            if camp.communal_food > 0.15:
                size = max(3, cell_size // 5)
                cache_rect = pygame.Rect(rect.right - size - 2, rect.top + 2, size, size)
                pygame.draw.rect(surface, (170, 110, 55), cache_rect)

    if overlays.paths:
        for path in world.path_traces.values():
            if path.strength < 0.04:
                continue
            a, b = path.edge
            color = _path_color(path.strength)
            start = _patch_center(world.grid, a, map_rect, cell_size)
            end = _patch_center(world.grid, b, map_rect, cell_size)
            width = 1 + int(min(3, path.strength * 3.0))
            pygame.draw.line(surface, color, start, end, width)


def _draw_selected_memory_overlays(
    surface: pygame.Surface,
    controller: ViewerController,
    overlays: OverlayState,
    map_rect: pygame.Rect,
    cell_size: int,
) -> None:
    if controller.selected_agent_id is None or controller.selected_agent_id not in controller.state.agents_by_id:
        return
    agent = controller.state.agents_by_id[controller.selected_agent_id]
    for entry in agent.spatial_memory.values():
        center = _patch_center(controller.state.world.grid, entry.patch_id, map_rect, cell_size)
        radius = max(4, int(cell_size * 0.18))
        if overlays.remembered_good and entry.kind in {"water", "food", "shelter"}:
            if entry.kind == "water":
                color = (70, 170, 255)
            elif entry.kind == "food":
                color = (70, 220, 100)
            else:
                color = (235, 210, 145)
            width = 1 + int(min(3, max(0.0, entry.revisit_bias) * 0.8))
            pygame.draw.circle(surface, color, (int(center[0]), int(center[1])), radius + width + 2, width)
        if overlays.remembered_danger and (entry.kind == "danger" or entry.avoidance_bias > 0.25):
            danger_color = (255, 95, 95)
            offset = radius + 2
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
        if positive_strength <= 0.1 and negative_strength <= 0.12:
            continue
        if edge.kin:
            color = (90, 185, 255)
            width = 2
        elif negative_strength > positive_strength:
            color = (235, 85, 85)
            width = 1 + int(min(3, negative_strength * 1.5))
        else:
            color = (95, 215, 110)
            width = 1 + int(min(3, positive_strength * 1.3))
        pygame.draw.line(surface, color, start, end, width)


def _draw_agents(
    surface: pygame.Surface,
    controller: ViewerController,
    overlays: OverlayState,
    map_rect: pygame.Rect,
    cell_size: int,
    positions: dict[int, tuple[float, float]],
) -> None:
    state = controller.state
    radius = max(3, int(cell_size * 0.22))
    for agent in state.agents:
        if not agent.alive:
            continue
        pos = positions.get(agent.agent_id)
        if pos is None:
            continue
        color = _age_color(agent)
        if overlays.needs:
            stress_tint = _clamp(agent.stress / 2.0, 0.0, 1.0)
            color = _blend(color, (230, 80, 80), stress_tint * 0.7)
        pygame.draw.circle(surface, color, (int(pos[0]), int(pos[1])), radius)

        if agent.agent_id == controller.selected_agent_id:
            pygame.draw.circle(surface, (255, 255, 120), (int(pos[0]), int(pos[1])), radius + 3, 2)

        if agent.carried_food > 0.2:
            pygame.draw.circle(surface, (75, 220, 95), (int(pos[0] + radius * 0.8), int(pos[1] - radius * 0.7)), max(2, radius // 3))

        if agent.current_action in {"care_for_child", "share_food"}:
            pygame.draw.circle(surface, (70, 210, 230), (int(pos[0]), int(pos[1])), radius + 2, 1)

        if agent.current_action in {"move_local", "move_to_known_site", "follow_caregiver", "avoid_danger", "explore"} and agent.last_patch_id is not None and agent.last_patch_id != agent.patch_id:
            start = _patch_center(state.world.grid, agent.last_patch_id, map_rect, cell_size)
            pygame.draw.line(surface, (180, 180, 255), start, pos, 1)

        if overlays.needs:
            bar_width = max(2, radius // 2)
            bar_x = int(pos[0] - radius)
            bar_y = int(pos[1] - radius - 7)
            hunger_h = int(8 * _clamp(agent.hunger / 2.0, 0.0, 1.0))
            thirst_h = int(8 * _clamp(agent.thirst / 2.0, 0.0, 1.0))
            stress_h = int(8 * _clamp(agent.stress / 2.0, 0.0, 1.0))
            pygame.draw.rect(surface, (220, 140, 70), (bar_x, bar_y + (8 - hunger_h), bar_width, hunger_h))
            pygame.draw.rect(surface, (65, 150, 240), (bar_x + bar_width + 1, bar_y + (8 - thirst_h), bar_width, thirst_h))
            pygame.draw.rect(surface, (225, 75, 75), (bar_x + (bar_width + 1) * 2, bar_y + (8 - stress_h), bar_width, stress_h))


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
    best_dist = max(12, cell_size) ** 2
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
    recent_event_count: int,
) -> None:
    pygame.draw.rect(surface, (22, 24, 31), panel_rect)
    pygame.draw.rect(surface, (50, 54, 66), panel_rect, 1)
    font = pygame.font.SysFont("consolas", 15)
    small_font = pygame.font.SysFont("consolas", 13)
    title_font = pygame.font.SysFont("consolas", 18, bold=True)

    metrics = build_metrics_snapshot(controller.state, recent_event_count)
    events = recent_event_lines(controller.state, limit=12)
    selected_lines = selected_agent_lines(controller.state, controller.selected_agent_id)

    x = panel_rect.left + 12
    y = panel_rect.top + 10
    surface.blit(title_font.render("CivSim Debug Viewer", True, (235, 238, 245)), (x, y))
    y += 28

    metric_lines = [
        f"Seed {controller.seed}  day {metrics.day}  season {metrics.season}",
        f"Speed {controller.ticks_per_second} t/s  {'paused' if controller.paused else 'running'}",
        f"Population {metrics.living_population}  children {metrics.living_children}  elders {metrics.living_elders}",
        f"Camps {metrics.active_camps}  paths {metrics.path_count}",
        f"Mean co-residence {_format_ratio(metrics.mean_co_residence)}",
        f"Sharing events {metrics.sharing_events}",
        f"Child survival {_format_ratio(metrics.child_survival_rate)} ({metrics.child_survival_trend})",
        f"Site reuse {_format_ratio(metrics.site_reuse_frequency)}",
        f"Recent events {metrics.recent_event_count}",
    ]
    y = _draw_text_lines(surface, font, metric_lines, x, y, (215, 220, 228), 18)
    y += 10

    surface.blit(title_font.render("Selected Agent", True, (235, 238, 245)), (x, y))
    y += 24
    y = _draw_text_lines(surface, small_font, selected_lines, x, y, (205, 210, 220), 16, max_lines=23)
    y += 10

    surface.blit(title_font.render("Recent Events", True, (235, 238, 245)), (x, y))
    y += 24
    y = _draw_text_lines(surface, small_font, events or ["No major events yet."], x, y, (205, 210, 220), 16, max_lines=12)

    if overlays.help:
        help_lines = [
            "Controls:",
            "Space play/pause  [ ] speed",
            "T step tick  Y step day  R restart",
            ", . seed -/+  click agent to inspect",
            "1 terrain  2 water  3 food  4 danger",
            "5 shelter  6 camps  7 paths  8 needs",
            "9 social links  G good memory  X danger memory",
            "H toggle help",
        ]
        help_y = panel_rect.bottom - (len(help_lines) * 16) - 12
        _draw_text_lines(surface, small_font, help_lines, x, help_y, (170, 175, 190), 16)


def run_viewer(
    config,
    seed: int | None = None,
    max_days: int | None = None,
    start_paused: bool = False,
    max_frames: int | None = None,
) -> None:
    pygame.init()
    pygame.display.set_caption("CivSim Viewer")
    screen = pygame.display.set_mode((1500, 960), pygame.RESIZABLE)
    frame_clock = pygame.time.Clock()

    controller = ViewerController(base_config=config, seed=seed if seed is not None else config.run.seed, max_days=max_days)
    controller.set_paused(start_paused)
    overlays = OverlayState()
    running = True
    frames = 0

    while running and (max_frames is None or frames < max_frames):
        dt_seconds = frame_clock.tick(60) / 1000.0
        width, height = screen.get_size()
        panel_width = min(460, max(360, width // 3))
        margin = 10
        map_width = max(200, width - panel_width - margin * 3)
        map_height = max(200, height - margin * 2)
        cell_size = max(
            8,
            min(
                map_width // controller.state.world.grid.width,
                map_height // controller.state.world.grid.height,
            ),
        )
        rendered_map_width = cell_size * controller.state.world.grid.width
        rendered_map_height = cell_size * controller.state.world.grid.height
        map_rect = pygame.Rect(margin, margin, rendered_map_width, rendered_map_height)
        panel_rect = pygame.Rect(map_rect.right + margin, margin, width - map_rect.right - margin * 2, height - margin * 2)

        positions, _ = _build_patch_agent_positions(controller, map_rect, cell_size)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    controller.toggle_pause()
                elif event.key == pygame.K_t:
                    controller.queue_tick()
                    controller.set_paused(True)
                elif event.key == pygame.K_y:
                    controller.queue_day()
                    controller.set_paused(True)
                elif event.key == pygame.K_r:
                    controller.restart()
                    positions, _ = _build_patch_agent_positions(controller, map_rect, cell_size)
                elif event.key == pygame.K_LEFTBRACKET:
                    controller.change_speed(-1)
                elif event.key == pygame.K_RIGHTBRACKET:
                    controller.change_speed(1)
                elif event.key == pygame.K_COMMA:
                    controller.change_seed(-1)
                    positions, _ = _build_patch_agent_positions(controller, map_rect, cell_size)
                elif event.key == pygame.K_PERIOD:
                    controller.change_seed(1)
                    positions, _ = _build_patch_agent_positions(controller, map_rect, cell_size)
                elif event.key == pygame.K_1:
                    overlays.terrain = not overlays.terrain
                elif event.key == pygame.K_2:
                    overlays.water = not overlays.water
                elif event.key == pygame.K_3:
                    overlays.food = not overlays.food
                elif event.key == pygame.K_4:
                    overlays.danger = not overlays.danger
                elif event.key == pygame.K_5:
                    overlays.shelter = not overlays.shelter
                elif event.key == pygame.K_6:
                    overlays.camps = not overlays.camps
                elif event.key == pygame.K_7:
                    overlays.paths = not overlays.paths
                elif event.key == pygame.K_8:
                    overlays.needs = not overlays.needs
                elif event.key == pygame.K_9:
                    overlays.social_links = not overlays.social_links
                elif event.key == pygame.K_g:
                    overlays.remembered_good = not overlays.remembered_good
                elif event.key == pygame.K_x:
                    overlays.remembered_danger = not overlays.remembered_danger
                elif event.key == pygame.K_h:
                    overlays.help = not overlays.help
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                agent_id = _select_agent_from_click(controller, map_rect, cell_size, positions, event.pos)
                controller.select_agent(agent_id)

        controller.advance(dt_seconds)
        positions, _ = _build_patch_agent_positions(controller, map_rect, cell_size)

        screen.fill((14, 16, 21))
        _draw_world(screen, controller, overlays, map_rect, cell_size)
        _draw_selected_memory_overlays(screen, controller, overlays, map_rect, cell_size)
        if overlays.social_links:
            _draw_social_links(screen, controller, positions)
        _draw_agents(screen, controller, overlays, map_rect, cell_size, positions)
        _draw_panel(screen, controller, overlays, panel_rect, recent_event_count=min(12, len(controller.state.event_bus.records)))
        pygame.display.flip()
        frames += 1

    pygame.quit()
