from __future__ import annotations

from civsim.viewer.controller import ViewerController


def test_controller_supports_requested_speed_multipliers(small_config) -> None:
    controller = ViewerController(base_config=small_config, seed=21)
    assert controller.speed_levels[:7] == (1, 2, 5, 10, 50, 100, 500)
    assert controller.speed_label.endswith("x")


def test_controller_batches_high_speed_steps_without_render_coupling(small_config) -> None:
    controller = ViewerController(base_config=small_config, seed=22)
    controller.speed_index = controller.speed_levels.index(500)
    controller.set_paused(False)

    steps = controller.advance(0.01)

    assert steps == 20
    assert controller.state.clock.tick == 20
    assert controller.last_steps_run == 20


def test_controller_caps_backlog_per_advance(small_config) -> None:
    controller = ViewerController(base_config=small_config, seed=23)
    controller.speed_index = controller.speed_levels.index(500)
    controller.max_steps_per_advance = 32
    controller.set_paused(False)

    steps = controller.advance(0.10)

    assert steps == 32
    assert controller.queued_ticks > 100.0


def test_controller_queue_day_runs_while_paused(small_config) -> None:
    controller = ViewerController(base_config=small_config, seed=24)
    controller.set_paused(True)
    controller.queue_day()

    steps = controller.advance(0.0)

    assert steps == controller.state.config.world.ticks_per_day
    assert controller.paused is True


def test_restart_preserves_pause_and_clears_selection(small_config) -> None:
    controller = ViewerController(base_config=small_config, seed=25)
    living_agent = next(agent for agent in controller.state.agents if agent.alive)
    controller.set_paused(True)
    controller.select_agent(living_agent.agent_id)
    controller.advance(0.01)

    controller.restart()

    assert controller.paused is True
    assert controller.selected_agent_id is None
    assert controller.state.clock.tick == 0
