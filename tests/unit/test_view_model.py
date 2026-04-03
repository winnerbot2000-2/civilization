from __future__ import annotations

from civsim.core.simulation import initialize_simulation
from civsim.events.types import EventRecord
from civsim.viewer.view_model import build_metrics_snapshot, recent_event_lines, selected_agent_lines


def test_view_model_metrics_snapshot_has_expected_fields(small_config) -> None:
    state = initialize_simulation(small_config, seed=13)
    snapshot = build_metrics_snapshot(state, recent_event_count=3)
    assert snapshot.living_population > 0
    assert snapshot.season in {"good", "bad"}
    assert snapshot.recent_event_count == 3
    assert 0 <= snapshot.tick_in_day < state.config.world.ticks_per_day
    assert snapshot.active_clusters >= 0


def test_view_model_recent_event_lines_formats_known_events(small_config) -> None:
    state = initialize_simulation(small_config, seed=14)
    state.event_bus.emit(EventRecord(tick=0, day=0, kind="birth", patch_id=10))
    state.event_bus.emit(EventRecord(tick=1, day=0, kind="trust_bond_formed", agent_id=1, other_agent_id=2, patch_id=10))
    lines = recent_event_lines(state, limit=5)
    assert any("birth" in line for line in lines)
    assert any("trust formed" in line for line in lines)


def test_view_model_recent_event_lines_compresses_repeated_events(small_config) -> None:
    state = initialize_simulation(small_config, seed=140)
    for tick in range(3):
        state.event_bus.emit(EventRecord(tick=tick, day=0, kind="action_share_food", agent_id=1, other_agent_id=2, patch_id=10))
    lines = recent_event_lines(state, limit=5)
    assert any("x3" in line for line in lines)


def test_selected_agent_lines_include_memories_and_social_ties(small_config) -> None:
    state = initialize_simulation(small_config, seed=15)
    agent = next(agent for agent in state.agents if agent.alive)
    lines = selected_agent_lines(state, agent.agent_id)
    assert any(f"Agent {agent.agent_id}" in line for line in lines)
    assert any("Recent site memories:" in line for line in lines)
    assert any("Social ties:" in line for line in lines)
