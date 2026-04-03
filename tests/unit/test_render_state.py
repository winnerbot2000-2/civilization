from __future__ import annotations

from civsim.viewer.render_state import ViewerRenderState


def test_render_state_interpolates_toward_targets() -> None:
    render_state = ViewerRenderState()
    positions = render_state.update_positions({1: (10.0, 10.0)}, dt_seconds=0.1, speed_multiplier=1, movement_enabled=True)
    assert positions[1] == (10.0, 10.0)

    positions = render_state.update_positions({1: (20.0, 10.0)}, dt_seconds=0.1, speed_multiplier=1, movement_enabled=True)
    assert 10.0 < positions[1][0] < 20.0
    assert 1 in render_state.trails


def test_render_state_prunes_removed_agents() -> None:
    render_state = ViewerRenderState()
    render_state.update_positions({1: (10.0, 10.0)}, dt_seconds=0.1, speed_multiplier=10, movement_enabled=True)
    render_state.update_positions({}, dt_seconds=0.1, speed_multiplier=10, movement_enabled=True)
    assert 1 not in render_state.visual_positions


def test_render_state_respects_trail_limits() -> None:
    render_state = ViewerRenderState()
    for idx in range(6):
        render_state.update_positions(
            {1: (float(idx * 5), 10.0)},
            dt_seconds=0.1,
            speed_multiplier=100,
            movement_enabled=True,
            max_trail_samples=3,
            min_trail_distance_sq=0.1,
        )
    assert len(render_state.trails[1]) <= 3
