from __future__ import annotations

from dataclasses import asdict

from civsim.agents.decision import generate_action_intent
from civsim.agents.perception import build_percept
from civsim.core.simulation import initialize_simulation, refresh_occupancy, run_simulation
from civsim.memory.spatial import remember_site


def test_thirsty_agent_prefers_known_water(small_config) -> None:
    state = initialize_simulation(small_config, seed=3)
    agent = next(agent for agent in state.agents if agent.alive and agent.age_stage == "adult")
    wet_patch = max(range(state.world.grid.size), key=lambda patch_id: state.world.water[patch_id])
    dry_patch = min(range(state.world.grid.size), key=lambda patch_id: state.world.water[patch_id])
    agent.patch_id = dry_patch
    agent.thirst = 1.2
    agent.hunger = 0.2
    agent.fatigue = 0.1
    agent.spatial_memory.clear()
    remember_site(agent.spatial_memory, "water", wet_patch, payoff=1.0, risk=0.0, day=state.clock.day, max_entries=state.config.memory.max_spatial_entries)
    refresh_occupancy(state)
    percept = build_percept(agent, state.world, state.agents_by_id, state.config.agents.perception_radius)
    intent = generate_action_intent(
        agent=agent,
        percept=percept,
        world=state.world,
        agents_by_id=state.agents_by_id,
        clock=state.clock,
        config=state.config,
        rng=state.rng.python("test-decision"),
    )
    assert intent.action == "move_to_known_site"
    assert intent.target_patch == wet_patch


def test_child_follows_caregiver(small_config) -> None:
    state = initialize_simulation(small_config, seed=4)
    child = next(agent for agent in state.agents if agent.alive and agent.age_stage == "child" and agent.caregiver_id is not None)
    caregiver = state.agents_by_id[child.caregiver_id]
    neighbor = next(patch_id for patch_id in state.world.grid.neighbors(child.patch_id) if patch_id != child.patch_id)
    caregiver.patch_id = neighbor
    refresh_occupancy(state)
    percept = build_percept(child, state.world, state.agents_by_id, state.config.agents.perception_radius)
    intent = generate_action_intent(
        agent=child,
        percept=percept,
        world=state.world,
        agents_by_id=state.agents_by_id,
        clock=state.clock,
        config=state.config,
        rng=state.rng.python("test-child"),
    )
    assert intent.action == "follow_caregiver"
    assert intent.target_patch == neighbor


def test_small_run_produces_paths_hearths_and_trust(small_config) -> None:
    _, summary = run_simulation(small_config, seed=7, days=20)
    assert summary.final_population > 0
    assert summary.hearth_count > 0
    assert summary.path_count > 0
    assert summary.mean_trust > 0.0
    assert summary.sharing_events > 0


def test_same_seed_run_is_reproducible(small_config) -> None:
    _, summary_a = run_simulation(small_config, seed=9, days=12)
    _, summary_b = run_simulation(small_config, seed=9, days=12)
    assert asdict(summary_a) == asdict(summary_b)
