from __future__ import annotations

import pygame

from civsim.viewer.controller import ViewerController
from civsim.viewer.pygame_viewer import OverlayState
from civsim.viewer.ui import build_control_buttons


def test_viewer_ui_builds_speed_and_control_buttons(small_config) -> None:
    pygame.init()
    try:
        font = pygame.font.SysFont("consolas", 14, bold=True)
        controller = ViewerController(base_config=small_config, seed=31)
        overlays = OverlayState()
        buttons = build_control_buttons(pygame.Rect(0, 0, 1200, 120), font, controller, overlays)
        labels = {button.label for button in buttons}
        assert {"Play", "Pause", "Restart", "Step Tick", "Step Day", "1x", "500x", "Trails", "Social", "Camps"} <= labels
    finally:
        pygame.quit()


def test_viewer_ui_overlay_panel_adds_debug_buttons(small_config) -> None:
    pygame.init()
    try:
        font = pygame.font.SysFont("consolas", 14, bold=True)
        controller = ViewerController(base_config=small_config, seed=32)
        overlays = OverlayState(overlay_panel=True)
        buttons = build_control_buttons(pygame.Rect(0, 0, 1200, 120), font, controller, overlays)
        labels = {button.label for button in buttons}
        assert {"Needs", "Kin", "Pressure", "Good Mem", "Danger Mem"} <= labels
    finally:
        pygame.quit()
