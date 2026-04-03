from __future__ import annotations

from dataclasses import dataclass

import pygame


Color = tuple[int, int, int]


@dataclass(slots=True)
class ControlButton:
    action: str
    label: str
    rect: pygame.Rect
    group: str
    active: bool = False
    accent: Color = (82, 96, 120)


def _button_width(font: pygame.font.Font, label: str, padding: int = 18) -> int:
    return max(56, font.size(label)[0] + padding)


def _append_row(
    buttons: list[ControlButton],
    font: pygame.font.Font,
    control_rect: pygame.Rect,
    y: int,
    group: str,
    specs: list[tuple[str, str, bool, Color]],
    row_height: int = 30,
    gap: int = 8,
) -> None:
    cursor_x = control_rect.x + 96
    for action, label, active, accent in specs:
        width = _button_width(font, label)
        rect = pygame.Rect(cursor_x, y, width, row_height)
        buttons.append(ControlButton(action=action, label=label, rect=rect, group=group, active=active, accent=accent))
        cursor_x += width + gap


def build_control_buttons(
    control_rect: pygame.Rect,
    font: pygame.font.Font,
    controller,
    overlays,
) -> list[ControlButton]:
    buttons: list[ControlButton] = []
    row_y = control_rect.y + 14

    main_specs = [
        ("play", "Play", not controller.paused, (62, 118, 86)),
        ("pause", "Pause", controller.paused, (110, 84, 68)),
        ("restart", "Restart", False, (92, 86, 124)),
        ("step_tick", "Step Tick", False, (86, 98, 118)),
        ("step_day", "Step Day", False, (86, 98, 118)),
        ("toggle:overlay_panel", "Overlays", overlays.overlay_panel, (92, 86, 124)),
        ("toggle:movement", "Trails", overlays.movement, (74, 108, 146)),
        ("toggle:social_links", "Social", overlays.social_links, (68, 112, 88)),
        ("toggle:camps", "Camps", overlays.camps, (128, 98, 60)),
    ]
    _append_row(buttons, font, control_rect, row_y, "Controls", main_specs)

    row_y += 38
    speed_specs: list[tuple[str, str, bool, Color]] = []
    for idx, multiplier in enumerate(controller.speed_levels):
        label = "MAX" if multiplier is None else f"{multiplier}x"
        speed_specs.append((f"speed:{idx}", label, idx == controller.speed_index, (96, 78, 132)))
    _append_row(buttons, font, control_rect, row_y, "Speed", speed_specs)

    if overlays.overlay_panel:
        row_y += 38
        overlay_specs = [
            ("toggle:needs", "Needs", overlays.needs, (112, 78, 68)),
            ("toggle:kin_links", "Kin", overlays.kin_links, (74, 110, 150)),
            ("toggle:resource_pressure", "Pressure", overlays.resource_pressure, (140, 102, 64)),
            ("toggle:remembered_good", "Good Mem", overlays.remembered_good, (66, 118, 86)),
            ("toggle:remembered_danger", "Danger Mem", overlays.remembered_danger, (142, 74, 74)),
            ("toggle:season_tint", "Season", overlays.season_tint, (90, 88, 130)),
            ("toggle:help", "Help", overlays.help, (86, 92, 104)),
        ]
        _append_row(buttons, font, control_rect, row_y, "Layers", overlay_specs)

    return buttons


def draw_control_bar(
    surface: pygame.Surface,
    control_rect: pygame.Rect,
    title: str,
    subtitle: str,
    buttons: list[ControlButton],
    title_font: pygame.font.Font,
    button_font: pygame.font.Font,
    mouse_pos: tuple[int, int],
) -> None:
    pygame.draw.rect(surface, (18, 20, 28), control_rect, border_radius=18)
    pygame.draw.rect(surface, (54, 58, 72), control_rect, 1, border_radius=18)
    surface.blit(title_font.render(title, True, (238, 242, 246)), (control_rect.x + 14, control_rect.y + 10))
    surface.blit(button_font.render(subtitle, True, (156, 164, 180)), (control_rect.x + 212, control_rect.y + 14))

    rows: dict[int, tuple[str, list[ControlButton]]] = {}
    for button in buttons:
        if button.rect.y not in rows:
            rows[button.rect.y] = (button.group, [])
        rows[button.rect.y][1].append(button)

    for row_y in sorted(rows):
        group, row_buttons = rows[row_y]
        top = min(button.rect.top for button in row_buttons) - 3
        bottom = max(button.rect.bottom for button in row_buttons) + 3
        row_rect = pygame.Rect(control_rect.x + 8, top, control_rect.width - 16, bottom - top)
        pygame.draw.rect(surface, (26, 30, 38), row_rect, border_radius=12)
        pygame.draw.rect(surface, (52, 58, 70), row_rect, 1, border_radius=12)
        label = button_font.render(group, True, (174, 180, 196))
        surface.blit(label, (control_rect.x + 18, row_rect.centery - label.get_height() // 2))

    for button in buttons:
        hovered = button.rect.collidepoint(mouse_pos)
        base = button.accent if button.active else (44, 48, 60)
        if hovered:
            base = tuple(min(255, channel + 18) for channel in base)
        border = tuple(min(255, channel + 32) for channel in base)
        pygame.draw.rect(surface, base, button.rect, border_radius=10)
        pygame.draw.rect(surface, border, button.rect, 1, border_radius=10)
        label = button_font.render(button.label, True, (246, 248, 252) if button.active else (214, 220, 230))
        label_pos = (
            button.rect.centerx - label.get_width() // 2,
            button.rect.centery - label.get_height() // 2,
        )
        surface.blit(label, label_pos)


def button_at(buttons: list[ControlButton], mouse_pos: tuple[int, int]) -> ControlButton | None:
    for button in buttons:
        if button.rect.collidepoint(mouse_pos):
            return button
    return None
