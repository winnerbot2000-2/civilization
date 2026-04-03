from __future__ import annotations

from civsim.launcher.ui import LaunchSettings, choose_launch_seed, normalize_launch_settings
from civsim.viewer.controller import ViewerController


def test_normalize_launch_settings_clamps_values(small_config) -> None:
    settings = LaunchSettings(days=0, total_agents=1, children=9, random_seed_each_run=False, fixed_seed=-4)

    normalized = normalize_launch_settings(settings, small_config)

    assert normalized.days is None
    assert normalized.total_agents >= 2
    assert normalized.children == normalized.total_agents - 1
    assert normalized.fixed_seed == 0


def test_choose_launch_seed_returns_fixed_seed_when_locked() -> None:
    settings = LaunchSettings(days=60, total_agents=20, children=2, random_seed_each_run=False, fixed_seed=31415)

    assert choose_launch_seed(settings) == 31415


def test_controller_random_restart_changes_seed_and_resets_clock(small_config, monkeypatch) -> None:
    controller = ViewerController(base_config=small_config, seed=25, randomize_on_restart=True)
    controller.set_paused(True)
    controller.queue_tick()
    controller.advance(0.0)

    monkeypatch.setattr("random.SystemRandom.randint", lambda self, a, b: 777)
    controller.restart_random()

    assert controller.seed == 777
    assert controller.state.clock.tick == 0
    assert controller.paused is True
