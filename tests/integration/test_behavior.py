from __future__ import annotations

from dataclasses import asdict
from statistics import mean

from civsim.agents.actions import resolve_intents
from civsim.agents.model import _spawn_quality_scores
from civsim.agents.decision import ActionIntent, generate_action_intent
from civsim.agents.perception import build_percept
from civsim.core.simulation import initialize_simulation, refresh_occupancy, run_simulation
from civsim.life.aging import age_stage_for_days
from civsim.memory.social import remember_social
from civsim.memory.spatial import remember_site
from civsim.social.coordination import pick_share_target


def test_thirsty_agent_prefers_known_water(small_config) -> None:
    state = initialize_simulation(small_config, seed=3)
    agent = next(agent for agent in state.agents if agent.alive and agent.age_stage == "adult")
    wet_patch = max(range(state.world.grid.size), key=lambda patch_id: state.world.water[patch_id])
    dry_patch = min(range(state.world.grid.size), key=lambda patch_id: state.world.water[patch_id])
    state.world.water[dry_patch] = 0.0
    state.world.food[dry_patch] = 0.0
    agent.patch_id = dry_patch
    agent.thirst = 1.2
    agent.previous_thirst = 0.8
    agent.hunger = 0.2
    agent.previous_hunger = 0.18
    agent.fatigue = 0.1
    agent.previous_fatigue = 0.08
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


def test_agent_avoids_neighbor_with_dangerous_memory(small_config) -> None:
    state = initialize_simulation(small_config, seed=31)
    agent = next(agent for agent in state.agents if agent.alive and agent.age_stage == "adult")
    center = state.world.grid.patch_id(5, 5)
    safe_neighbor = state.world.grid.patch_id(6, 5)
    risky_neighbor = state.world.grid.patch_id(4, 5)
    agent.patch_id = center
    for patch_id in [center, safe_neighbor, risky_neighbor]:
        state.world.water[patch_id] = 0.0
        state.world.food[patch_id] = 0.0
        state.world.shelter[patch_id] = 0.0
        state.world.danger[patch_id] = 0.0
        state.world.movement_cost[patch_id] = 1.0
    state.world.water[safe_neighbor] = 0.7
    state.world.water[risky_neighbor] = 0.75
    remember_site(
        agent.spatial_memory,
        "danger",
        risky_neighbor,
        payoff=0.0,
        risk=1.0,
        day=state.clock.day,
        max_entries=state.config.memory.max_spatial_entries,
        emotional_impact=1.2,
        avoidance_delta=1.0,
    )
    agent.thirst = 1.0
    agent.previous_thirst = 0.7
    agent.hunger = 0.2
    agent.previous_hunger = 0.2
    agent.fatigue = 0.1
    agent.previous_fatigue = 0.1
    agent.stress = 0.15
    agent.previous_stress = 0.1
    refresh_occupancy(state)
    percept = build_percept(agent, state.world, state.agents_by_id, state.config.agents.perception_radius)
    intent = generate_action_intent(
        agent=agent,
        percept=percept,
        world=state.world,
        agents_by_id=state.agents_by_id,
        clock=state.clock,
        config=state.config,
        rng=state.rng.python("test-danger-memory"),
    )
    assert intent.action in {"move_local", "move_to_known_site", "drink", "explore"}
    assert intent.target_patch != risky_neighbor


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


def test_thirsty_agent_drinks_before_socializing_on_water(small_config) -> None:
    state = initialize_simulation(small_config, seed=14)
    agent = next(agent for agent in state.agents if agent.alive and agent.age_stage == "adult")
    other = next(other for other in state.agents if other.alive and other.agent_id != agent.agent_id and other.age_stage == "adult")
    patch_id = state.world.grid.patch_id(4, 4)
    agent.patch_id = patch_id
    other.patch_id = patch_id
    state.world.water[patch_id] = 0.85
    agent.social_need = 0.9
    agent.previous_social_need = 0.6
    agent.thirst = 1.1
    agent.previous_thirst = 0.7
    refresh_occupancy(state)
    percept = build_percept(agent, state.world, state.agents_by_id, state.config.agents.perception_radius)
    intent = generate_action_intent(
        agent=agent,
        percept=percept,
        world=state.world,
        agents_by_id=state.agents_by_id,
        clock=state.clock,
        config=state.config,
        rng=state.rng.python("test-drink-override"),
    )
    assert intent.action == "drink"


def test_thirsty_agent_moves_to_visible_water_before_exploring(small_config) -> None:
    state = initialize_simulation(small_config, seed=15)
    agent = next(agent for agent in state.agents if agent.alive and agent.age_stage == "adult")
    center = state.world.grid.patch_id(5, 5)
    water_patch = state.world.grid.patch_id(5, 6)
    dry_patch = state.world.grid.patch_id(4, 5)
    agent.patch_id = center
    for patch_id in {center, water_patch, dry_patch, *state.world.grid.neighbors(center), *state.world.grid.neighbors(water_patch)}:
        state.world.water[patch_id] = 0.0
        state.world.food[patch_id] = 0.0
        state.world.danger[patch_id] = 0.0
        state.world.movement_cost[patch_id] = 1.0
    state.world.water[water_patch] = 0.9
    agent.spatial_memory.clear()
    agent.thirst = 1.0
    agent.previous_thirst = 0.6
    agent.traits.curiosity = 0.9
    refresh_occupancy(state)
    percept = build_percept(agent, state.world, state.agents_by_id, state.config.agents.perception_radius)
    intent = generate_action_intent(
        agent=agent,
        percept=percept,
        world=state.world,
        agents_by_id=state.agents_by_id,
        clock=state.clock,
        config=state.config,
        rng=state.rng.python("test-visible-water"),
    )
    assert intent.action in {"move_local", "move_to_known_site"}
    assert intent.target_patch == water_patch


def test_initial_spawn_favors_mixed_survival_quality(small_config) -> None:
    state = initialize_simulation(small_config, seed=18)
    spawn_quality = _spawn_quality_scores(state.world)
    adult_patches = [agent.patch_id for agent in state.agents if agent.alive and agent.age_stage == "adult"]
    assert adult_patches
    assert mean(spawn_quality[patch_id] for patch_id in adult_patches) > mean(spawn_quality) + 0.1


def test_seeded_children_start_provisioned_and_evenly_distributed(small_config) -> None:
    state = initialize_simulation(small_config, seed=23)
    children = [agent for agent in state.agents if agent.alive and agent.age_stage == "child"]
    assert children
    caregiver_loads: dict[int, int] = {}
    for child in children:
        assert child.carried_food >= 0.6
        assert child.hunger <= 0.2
        assert child.caregiver_id is not None
        caregiver_loads[child.caregiver_id] = caregiver_loads.get(child.caregiver_id, 0) + 1
    assert max(caregiver_loads.values()) <= 2


def test_caregiver_prioritizes_nearby_dependent_child(small_config) -> None:
    state = initialize_simulation(small_config, seed=12)
    caregiver = next(agent for agent in state.agents if agent.alive and agent.age_stage == "adult" and agent.child_ids)
    child = state.agents_by_id[caregiver.child_ids[0]]
    center = state.world.grid.patch_id(5, 5)
    child_patch = state.world.grid.patch_id(6, 5)
    caregiver.patch_id = center
    child.patch_id = child_patch
    caregiver.traits.curiosity = 0.05
    caregiver.traits.attachment_strength = 0.95
    caregiver.hunger = 0.2
    caregiver.previous_hunger = 0.18
    caregiver.thirst = 0.2
    caregiver.previous_thirst = 0.18
    caregiver.fatigue = 0.1
    caregiver.previous_fatigue = 0.1
    caregiver.social_need = 0.45
    caregiver.previous_social_need = 0.35
    child.hunger = 1.0
    child.previous_hunger = 0.7
    child.social_need = 0.9
    child.previous_social_need = 0.6
    child.stress = 0.8
    child.previous_stress = 0.45
    refresh_occupancy(state)
    percept = build_percept(caregiver, state.world, state.agents_by_id, state.config.agents.perception_radius)
    intent = generate_action_intent(
        agent=caregiver,
        percept=percept,
        world=state.world,
        agents_by_id=state.agents_by_id,
        clock=state.clock,
        config=state.config,
        rng=state.rng.python("test-caregiver-priority"),
    )
    assert intent.action == "move_local"
    assert intent.target_patch == child_patch


def test_social_need_pulls_agent_toward_kin_and_away_from_harmful_patch(small_config) -> None:
    state = initialize_simulation(small_config, seed=22)
    agent = next(agent for agent in state.agents if agent.alive and agent.age_stage == "adult")
    kin = next(other for other in state.agents if other.alive and other.agent_id != agent.agent_id and other.age_stage == "adult")
    harmful = next(
        other
        for other in state.agents
        if other.alive and other.agent_id not in {agent.agent_id, kin.agent_id} and other.age_stage == "adult"
    )
    agent.child_ids = [kin.agent_id]
    kin.parent_ids = (agent.agent_id,)
    center = state.world.grid.patch_id(7, 4)
    kin_patch = state.world.grid.patch_id(8, 4)
    harmful_patch = state.world.grid.patch_id(6, 4)
    far_patch = state.world.grid.patch_id(0, 0)
    for other in state.agents:
        if other.agent_id not in {agent.agent_id, kin.agent_id, harmful.agent_id}:
            other.patch_id = far_patch
    agent.patch_id = center
    kin.patch_id = kin_patch
    harmful.patch_id = harmful_patch
    for patch_id in [center, kin_patch, harmful_patch]:
        state.world.food[patch_id] = 0.0
        state.world.water[patch_id] = 0.0
        state.world.shelter[patch_id] = 0.05
        state.world.danger[patch_id] = 0.0
    agent.traits.curiosity = 0.05
    agent.traits.attachment_strength = 0.9
    agent.social_need = 0.95
    agent.previous_social_need = 0.55
    agent.hunger = 0.15
    agent.previous_hunger = 0.14
    agent.thirst = 0.15
    agent.previous_thirst = 0.14
    remember_social(agent.social_memory, harmful.agent_id, state.clock.day, harm_delta=0.9, trust_delta=-0.2, emotional_impact=1.0)
    refresh_occupancy(state)
    percept = build_percept(agent, state.world, state.agents_by_id, state.config.agents.perception_radius)
    intent = generate_action_intent(
        agent=agent,
        percept=percept,
        world=state.world,
        agents_by_id=state.agents_by_id,
        clock=state.clock,
        config=state.config,
        rng=state.rng.python("test-kin-preference"),
    )
    assert intent.action == "move_local"
    assert intent.target_patch == kin_patch


def test_share_target_prefers_kin_trust_and_reciprocity(small_config) -> None:
    state = initialize_simulation(small_config, seed=52)
    agent = next(agent for agent in state.agents if agent.alive and agent.age_stage == "adult")
    helper = next(
        other
        for other in state.agents
        if other.alive and other.agent_id != agent.agent_id and other.age_stage == "adult"
    )
    stranger = next(
        other
        for other in state.agents
        if other.alive and other.agent_id not in {agent.agent_id, helper.agent_id} and other.age_stage == "adult"
    )
    patch_id = state.world.grid.patch_id(4, 4)
    agent.patch_id = patch_id
    helper.patch_id = patch_id
    stranger.patch_id = patch_id
    helper.hunger = 0.8
    stranger.hunger = 0.9
    remember_social(agent.social_memory, helper.agent_id, state.clock.day, trust_delta=0.4, reciprocity_delta=-0.5, emotional_impact=0.8)
    remember_social(agent.social_memory, stranger.agent_id, state.clock.day, harm_delta=0.4, trust_delta=-0.2, emotional_impact=0.8)
    target = pick_share_target(agent, [helper, stranger], state.config.social)
    assert target is not None
    assert target.agent_id == helper.agent_id


def test_taking_scarce_shared_food_creates_distrust(small_config) -> None:
    state = initialize_simulation(small_config, seed=41)
    actor = next(agent for agent in state.agents if agent.alive and agent.age_stage == "adult")
    observer = next(
        agent
        for agent in state.agents
        if agent.alive and agent.agent_id != actor.agent_id and agent.age_stage == "adult"
    )
    patch_id = state.world.grid.patch_id(3, 3)
    actor.patch_id = patch_id
    observer.patch_id = patch_id
    observer.hunger = 1.1
    actor.hunger = 0.7
    actor.carried_food = 0.0
    actor.social_memory.clear()
    observer.social_memory.clear()
    site = state.world.ensure_site(patch_id)
    site.communal_food = 0.5
    refresh_occupancy(state)
    outcomes = resolve_intents(
        state,
        {
            actor.agent_id: ActionIntent(agent_id=actor.agent_id, action="take_food_from_site"),
            observer.agent_id: ActionIntent(agent_id=observer.agent_id, action="wait"),
        },
        state.clock,
    )
    edge = observer.social_memory.get(actor.agent_id)
    assert outcomes[actor.agent_id].success
    assert edge is not None
    assert edge.harm > 0.0
    assert edge.trust < 0.0


def test_small_run_produces_paths_hearths_and_trust(small_config) -> None:
    _, summary = run_simulation(small_config, seed=10, days=20)
    assert summary.final_population > 0
    assert summary.hearth_count > 0
    assert summary.path_count > 0
    assert summary.mean_trust > 0.0
    assert summary.mean_remembered_sites > 0.0


def test_inertia_reduces_unrealistic_action_switching(small_config) -> None:
    state = initialize_simulation(small_config, seed=6)
    agent = next(agent for agent in state.agents if agent.alive and agent.age_stage == "adult")
    state.world.food[agent.patch_id] = 0.0
    state.world.water[agent.patch_id] = 0.0
    state.world.shelter[agent.patch_id] = 0.5
    agent.current_action = "rest"
    agent.current_target_patch = None
    agent.action_streak = 4
    agent.traits.curiosity = 0.05
    agent.hunger = 0.25
    agent.previous_hunger = 0.23
    agent.thirst = 0.2
    agent.previous_thirst = 0.18
    agent.fatigue = 0.55
    agent.previous_fatigue = 0.5
    refresh_occupancy(state)
    percept = build_percept(agent, state.world, state.agents_by_id, state.config.agents.perception_radius)
    intent = generate_action_intent(
        agent=agent,
        percept=percept,
        world=state.world,
        agents_by_id=state.agents_by_id,
        clock=state.clock,
        config=state.config,
        rng=state.rng.python("test-inertia"),
    )
    assert intent.action in {"rest", "shelter_at_site", "wait"}


def test_uncertain_high_stress_agent_falls_back_to_wait(small_config) -> None:
    state = initialize_simulation(small_config, seed=10)
    agent = next(agent for agent in state.agents if agent.alive and agent.age_stage == "adult")
    for patch_id in [agent.patch_id, *state.world.grid.neighbors(agent.patch_id)]:
        state.world.food[patch_id] = 0.0
        state.world.water[patch_id] = 0.0
        state.world.shelter[patch_id] = 0.05
    agent.hunger = 0.15
    agent.previous_hunger = 0.14
    agent.thirst = 0.15
    agent.previous_thirst = 0.14
    agent.fatigue = 0.2
    agent.previous_fatigue = 0.18
    agent.stress = 1.1
    agent.previous_stress = 0.7
    agent.social_need = 0.2
    agent.previous_social_need = 0.18
    agent.spatial_memory.clear()
    state.config.decision.fallback_threshold = 5.0
    refresh_occupancy(state)
    percept = build_percept(agent, state.world, state.agents_by_id, state.config.agents.perception_radius)
    intent = generate_action_intent(
        agent=agent,
        percept=percept,
        world=state.world,
        agents_by_id=state.agents_by_id,
        clock=state.clock,
        config=state.config,
        rng=state.rng.python("test-fallback"),
    )
    assert intent.action in {"wait", "avoid_danger"}


def test_same_seed_run_is_reproducible(small_config) -> None:
    _, summary_a = run_simulation(small_config, seed=9, days=12)
    _, summary_b = run_simulation(small_config, seed=9, days=12)
    assert asdict(summary_a) == asdict(summary_b)


def test_older_agent_pays_higher_movement_fatigue_cost(small_config) -> None:
    state = initialize_simulation(small_config, seed=27)
    adults = [agent for agent in state.agents if agent.alive and agent.age_stage == "adult"]
    young = adults[0]
    older = adults[1]
    center = state.world.grid.patch_id(5, 5)
    target = state.world.grid.patch_id(6, 5)
    young.patch_id = center
    older.patch_id = center
    young.age_days = state.config.life.child_stage_days + 40
    older.age_days = state.config.life.max_age_days
    young.age_stage = age_stage_for_days(young.age_days, state.config.life)
    older.age_stage = age_stage_for_days(older.age_days, state.config.life)
    state.world.movement_cost[target] = 2.2
    refresh_occupancy(state)

    young_start = young.fatigue
    older_start = older.fatigue
    resolve_intents(
        state,
        {
            young.agent_id: ActionIntent(agent_id=young.agent_id, action="move_local", target_patch=target),
            older.agent_id: ActionIntent(agent_id=older.agent_id, action="move_local", target_patch=target),
        },
        state.clock,
    )

    assert older.fatigue - older_start > young.fatigue - young_start
