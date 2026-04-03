from __future__ import annotations

from dataclasses import dataclass, field

from ..events.trace import trace_tags
from ..events.types import EventRecord
from ..materials.stores import store_food, take_food
from ..materials.traces import record_path_use
from ..memory.episodic import Episode, record_episode
from ..memory.social import remember_social
from ..memory.spatial import remember_site
from ..social.coordination import pick_share_target


@dataclass(slots=True)
class ActionOutcome:
    agent_id: int
    action: str
    success: bool
    patch_id: int
    previous_action: str | None = None
    target_patch: int | None = None
    target_agent_id: int | None = None
    notes: list[str] = field(default_factory=list)
    outcome_score: float = 0.0


def _clamp_needs(agent) -> None:
    agent.hunger = max(0.0, min(2.0, agent.hunger))
    agent.thirst = max(0.0, min(2.0, agent.thirst))
    agent.fatigue = max(0.0, min(2.0, agent.fatigue))
    agent.stress = max(0.0, min(2.0, agent.stress))
    agent.social_need = max(0.0, min(2.0, agent.social_need))


def _effective_shelter(world, patch_id: int, camp_bonus: float) -> float:
    site = world.site_markers.get(patch_id)
    hearth_bonus = site.hearth_intensity * camp_bonus if site is not None else 0.0
    return float(world.shelter[patch_id]) + hearth_bonus


def _step_toward(world, source: int, target: int) -> int:
    neighbors = world.grid.neighbors(source)
    if not neighbors:
        return source
    return min(neighbors, key=lambda patch_id: world.grid.distance(patch_id, target) + world.movement_cost[patch_id] * 0.2)


def _emit_trust_threshold_event(state, clock, source_agent_id: int, target_agent_id: int, before_trust: float, after_trust: float, patch_id: int) -> None:
    if before_trust < 0.35 <= after_trust:
        state.event_bus.emit(
            EventRecord(
                tick=clock.tick,
                day=clock.day,
                kind="trust_bond_formed",
                agent_id=source_agent_id,
                other_agent_id=target_agent_id,
                patch_id=patch_id,
                trace=trace_tags(reason="positive_social_memory", season=clock.season_name),
            )
        )
    elif before_trust > -0.15 and after_trust <= -0.15:
        state.event_bus.emit(
            EventRecord(
                tick=clock.tick,
                day=clock.day,
                kind="trust_bond_collapsed",
                agent_id=source_agent_id,
                other_agent_id=target_agent_id,
                patch_id=patch_id,
                trace=trace_tags(reason="harm_or_theft", season=clock.season_name),
            )
        )


def resolve_intents(state, intents, clock) -> dict[int, ActionOutcome]:
    outcomes: dict[int, ActionOutcome] = {}
    world = state.world
    cfg_agents = state.config.agents
    for agent_id in sorted(intents):
        agent = state.agents_by_id[agent_id]
        if not agent.alive:
            continue
        intent = intents[agent_id]
        previous_action = agent.current_action
        previous_target_patch = agent.current_target_patch
        start_hunger = agent.hunger
        start_thirst = agent.thirst
        start_fatigue = agent.fatigue
        start_stress = agent.stress
        start_social_need = agent.social_need
        agent.current_action = intent.action
        agent.current_target_patch = intent.target_patch
        if previous_action == intent.action and previous_target_patch == intent.target_patch:
            agent.action_streak += 1
        else:
            agent.action_streak = 1
        agent.last_patch_id = agent.patch_id
        outcome = ActionOutcome(
            agent_id=agent_id,
            action=intent.action,
            success=False,
            patch_id=agent.patch_id,
            previous_action=previous_action if previous_action != "idle" else None,
            target_patch=intent.target_patch,
            target_agent_id=intent.target_agent_id,
        )

        if intent.action == "drink":
            if world.water[agent.patch_id] > 0.2:
                agent.thirst -= cfg_agents.base_water_relief * (1.0 + world.water[agent.patch_id] * 0.25)
                outcome.success = True
                outcome.outcome_score = 0.8
                relief = max(0.0, start_thirst - agent.thirst)
                remember_site(
                    agent.spatial_memory,
                    "water",
                    agent.patch_id,
                    payoff=float(world.water[agent.patch_id]),
                    risk=float(world.danger[agent.patch_id]),
                    day=clock.day,
                    max_entries=state.config.memory.max_spatial_entries,
                    emotional_impact=start_thirst * 0.55 + relief * 0.45,
                    revisit_delta=relief * 0.9,
                )
        elif intent.action == "forage":
            available = float(world.food[agent.patch_id])
            if available > 0.02:
                gained = min(available, cfg_agents.base_food_yield * (1.0 + agent.skills.foraging * 0.4))
                world.food[agent.patch_id] -= gained
                agent.carried_food = min(cfg_agents.max_carried_food, agent.carried_food + gained)
                agent.hunger -= gained * 0.25
                outcome.success = gained > 0.0
                outcome.outcome_score = gained
                relief = max(0.0, start_hunger - agent.hunger)
                remember_site(
                    agent.spatial_memory,
                    "food",
                    agent.patch_id,
                    payoff=gained,
                    risk=float(world.danger[agent.patch_id]),
                    day=clock.day,
                    max_entries=state.config.memory.max_spatial_entries,
                    emotional_impact=start_hunger * 0.35 + gained * 0.45 + relief * 0.2,
                    revisit_delta=max(0.0, gained * 0.6 + relief * 0.35),
                )
        elif intent.action in {"move_local", "move_to_known_site", "follow_caregiver", "avoid_danger"}:
            target = intent.target_patch if intent.target_patch is not None else agent.patch_id
            if target != agent.patch_id and target not in world.grid.neighbors(agent.patch_id):
                target = _step_toward(world, agent.patch_id, target)
            if target != agent.patch_id:
                old_patch = agent.patch_id
                agent.patch_id = target
                agent.fatigue += 0.035 * float(world.movement_cost[target])
                record_path_use(world, world.grid.ordered_edge(old_patch, target), clock.day, state.config.materials.path_strength_gain)
                outcome.success = True
                outcome.target_patch = target
                outcome.patch_id = target
                outcome.outcome_score = 0.25
                patch_danger = float(world.danger[target])
                if intent.action == "avoid_danger" and patch_danger < float(world.danger[old_patch]):
                    remember_site(
                        agent.spatial_memory,
                        "danger",
                        old_patch,
                        payoff=0.0,
                        risk=float(world.danger[old_patch]),
                        day=clock.day,
                        max_entries=state.config.memory.max_spatial_entries,
                        emotional_impact=max(start_stress, float(world.danger[old_patch])),
                        avoidance_delta=max(0.0, float(world.danger[old_patch]) - patch_danger) * 1.2,
                    )
        elif intent.action == "rest":
            shelter_factor = 0.45 + _effective_shelter(world, agent.patch_id, state.config.world.camp_shelter_bonus) * 0.8
            agent.fatigue -= cfg_agents.rest_recovery * shelter_factor
            outcome.success = True
            outcome.outcome_score = 0.3
        elif intent.action == "wait":
            shelter_factor = 0.25 + _effective_shelter(world, agent.patch_id, state.config.world.camp_shelter_bonus) * 0.25
            agent.fatigue -= cfg_agents.rest_recovery * shelter_factor
            agent.stress -= cfg_agents.stress_recovery * 0.75
            outcome.success = True
            outcome.outcome_score = 0.12
        elif intent.action == "explore":
            neighbors = world.grid.neighbors(agent.patch_id)
            if neighbors:
                unexplored = [patch for patch in neighbors if ("food", patch) not in agent.spatial_memory and ("water", patch) not in agent.spatial_memory]
                target = state.rng.python(f"explore:{agent.agent_id}:{clock.tick}").choice(unexplored or neighbors)
                old_patch = agent.patch_id
                agent.patch_id = target
                agent.fatigue += 0.045 * float(world.movement_cost[target])
                record_path_use(world, world.grid.ordered_edge(old_patch, target), clock.day, state.config.materials.path_strength_gain * 0.5)
                outcome.success = True
                outcome.target_patch = target
                outcome.patch_id = target
                outcome.outcome_score = 0.15
        elif intent.action == "share_food":
            others_here = [state.agents_by_id[other_id] for other_id in world.occupancy.get(agent.patch_id, []) if other_id != agent.agent_id]
            target = None
            if intent.target_agent_id is not None:
                other = state.agents_by_id.get(intent.target_agent_id)
                if other is not None and other.patch_id == agent.patch_id:
                    target = other
            if target is None:
                target = pick_share_target(agent, others_here, state.config.social)
            if target is not None and agent.carried_food > 0.2:
                amount = min(state.config.social.share_amount, agent.carried_food)
                agent.carried_food -= amount
                target.carried_food += amount
                target.hunger -= amount * 0.2
                social_salience = amount + target.hunger + (0.45 if target.age_stage == "child" else 0.0)
                is_kin = target.agent_id in agent.child_ids or target.agent_id in agent.parent_ids
                before_agent_trust = agent.social_memory.get(target.agent_id).trust if target.agent_id in agent.social_memory else 0.0
                before_target_trust = target.social_memory.get(agent.agent_id).trust if agent.agent_id in target.social_memory else 0.0
                remember_social(
                    agent.social_memory,
                    target.agent_id,
                    clock.day,
                    trust_delta=state.config.social.trust_gain,
                    reciprocity_delta=0.1,
                    attachment_delta=state.config.social.attachment_gain * (0.9 if is_kin else 0.25),
                    kin=is_kin,
                    emotional_impact=social_salience,
                )
                remember_social(
                    target.social_memory,
                    agent.agent_id,
                    clock.day,
                    trust_delta=state.config.social.trust_gain,
                    reciprocity_delta=-0.1,
                    attachment_delta=state.config.social.attachment_gain * (0.8 if is_kin else 0.2),
                    kin=is_kin,
                    emotional_impact=social_salience,
                )
                _emit_trust_threshold_event(state, clock, agent.agent_id, target.agent_id, before_agent_trust, agent.social_memory[target.agent_id].trust, agent.patch_id)
                _emit_trust_threshold_event(state, clock, target.agent_id, agent.agent_id, before_target_trust, target.social_memory[agent.agent_id].trust, target.patch_id)
                outcome.success = True
                outcome.target_agent_id = target.agent_id
                outcome.outcome_score = amount
        elif intent.action == "care_for_child":
            child = state.agents_by_id.get(intent.target_agent_id or -1)
            if child is not None and child.patch_id == agent.patch_id:
                if agent.carried_food > 0.1:
                    amount = min(state.config.social.share_amount, agent.carried_food)
                    agent.carried_food -= amount
                    child.carried_food += amount
                    child.hunger -= amount * 0.35
                child.social_need -= 0.2 * (1.0 + agent.skills.caregiving * 0.5)
                child.stress -= 0.1
                social_salience = child.hunger + child.social_need + child.stress + 0.6
                remember_social(
                    agent.social_memory,
                    child.agent_id,
                    clock.day,
                    attachment_delta=state.config.social.attachment_gain,
                    trust_delta=0.03,
                    kin=True,
                    emotional_impact=social_salience,
                )
                remember_social(
                    child.social_memory,
                    agent.agent_id,
                    clock.day,
                    attachment_delta=state.config.social.attachment_gain,
                    trust_delta=0.03,
                    kin=True,
                    emotional_impact=social_salience,
                )
                outcome.success = True
                outcome.target_agent_id = child.agent_id
                outcome.outcome_score = 0.6
        elif intent.action == "stay_with_kin":
            agent.social_need -= 0.1
            agent.stress -= 0.05
            others_here = [
                state.agents_by_id[other_id]
                for other_id in world.occupancy.get(agent.patch_id, [])
                if other_id != agent.agent_id and state.agents_by_id[other_id].alive
            ]
            for other in others_here:
                edge = agent.social_memory.get(other.agent_id)
                is_kin = other.agent_id in agent.child_ids or other.agent_id in agent.parent_ids
                if not is_kin and edge is None:
                    continue
                remember_social(
                    agent.social_memory,
                    other.agent_id,
                    clock.day,
                    trust_delta=0.015,
                    attachment_delta=0.01 + (0.02 if is_kin else 0.0),
                    co_residence_delta=0.015,
                    kin=is_kin if is_kin else None,
                    emotional_impact=0.18 + (0.12 if is_kin else 0.0),
                )
                remember_social(
                    other.social_memory,
                    agent.agent_id,
                    clock.day,
                    trust_delta=0.015,
                    attachment_delta=0.01 + (0.02 if is_kin else 0.0),
                    co_residence_delta=0.015,
                    kin=is_kin if is_kin else None,
                    emotional_impact=0.18 + (0.12 if is_kin else 0.0),
                )
            outcome.success = True
            outcome.outcome_score = 0.25
        elif intent.action == "take_food_from_site":
            site = world.site_markers.get(agent.patch_id)
            if site is not None:
                food_before = site.communal_food
                taken = take_food(site, min(state.config.social.share_amount, cfg_agents.max_carried_food - agent.carried_food))
                agent.carried_food += taken
                agent.hunger -= taken * 0.15
                outcome.success = taken > 0.0
                outcome.outcome_score = taken
                others_here = [
                    state.agents_by_id[other_id]
                    for other_id in world.occupancy.get(agent.patch_id, [])
                    if other_id != agent.agent_id and state.agents_by_id[other_id].alive
                ]
                if taken > 0.0 and others_here:
                    scarcity = max(
                        0.0,
                        max(other.hunger + (0.35 if other.age_stage == "child" else 0.0) for other in others_here) * 0.5
                        + max(0.0, 1.0 - food_before) * 0.4,
                    )
                    if scarcity > 0.45:
                        for other in others_here:
                            before_trust = other.social_memory.get(agent.agent_id).trust if agent.agent_id in other.social_memory else 0.0
                            remember_social(
                                other.social_memory,
                                agent.agent_id,
                                clock.day,
                                harm_delta=state.config.social.trust_loss * 0.55,
                                trust_delta=-state.config.social.trust_loss * 0.25,
                                emotional_impact=scarcity + other.hunger,
                            )
                            _emit_trust_threshold_event(state, clock, other.agent_id, agent.agent_id, before_trust, other.social_memory[agent.agent_id].trust, other.patch_id)
                            other.stress += state.config.social.theft_stress * scarcity
        elif intent.action == "store_food_at_site":
            site = world.ensure_site(agent.patch_id)
            stored = store_food(site, max(0.0, agent.carried_food - 0.8), state.config.materials.site_store_capacity)
            agent.carried_food -= stored
            outcome.success = stored > 0.0
            outcome.outcome_score = stored * 0.4
        elif intent.action == "shelter_at_site":
            shelter_bonus = _effective_shelter(world, agent.patch_id, state.config.world.camp_shelter_bonus)
            agent.fatigue -= cfg_agents.rest_recovery * (0.95 + shelter_bonus * 1.1)
            relief = max(0.0, start_fatigue - agent.fatigue)
            remember_site(
                agent.spatial_memory,
                "shelter",
                agent.patch_id,
                payoff=shelter_bonus,
                risk=float(world.danger[agent.patch_id]),
                day=clock.day,
                max_entries=state.config.memory.max_spatial_entries,
                emotional_impact=start_fatigue * 0.4 + relief * 0.4 + max(0.0, start_stress - agent.stress) * 0.2,
                revisit_delta=relief * 0.8 + shelter_bonus * 0.12,
            )
            outcome.success = True
            outcome.outcome_score = 0.35 + shelter_bonus * 0.1

        agent.hunger += cfg_agents.hunger_rate + (state.config.life.child_hunger_penalty if agent.age_stage == "child" else 0.0)
        dry_penalty = max(0.0, (0.25 - float(world.water[agent.patch_id])) / 0.25) * state.config.world.dry_patch_thirst_penalty
        agent.thirst += cfg_agents.thirst_rate + dry_penalty
        agent.fatigue += cfg_agents.fatigue_rate
        agent.social_need += cfg_agents.social_need_rate
        agent.stress = max(0.0, agent.stress - cfg_agents.stress_recovery)
        if agent.carried_food > 0.05 and agent.hunger > 0.4:
            consumed = min(agent.carried_food, 0.35)
            agent.carried_food -= consumed
            agent.hunger -= consumed * 0.6
        effective_shelter = _effective_shelter(world, agent.patch_id, state.config.world.camp_shelter_bonus)
        if clock.is_night:
            exposure = max(0.0, 0.55 - effective_shelter)
            agent.fatigue += exposure * state.config.world.night_exposure_fatigue
            agent.stress += exposure * state.config.world.night_exposure_stress

        patch_danger = float(world.danger[agent.patch_id])
        if patch_danger > 0.55:
            agent.fatigue += patch_danger * state.config.world.danger_fatigue_scale
            agent.stress += patch_danger * state.config.world.danger_stress_scale
            remember_site(
                agent.spatial_memory,
                "danger",
                agent.patch_id,
                payoff=0.0,
                risk=patch_danger,
                day=clock.day,
                max_entries=state.config.memory.max_spatial_entries,
                emotional_impact=agent.stress + patch_danger * 0.55,
                avoidance_delta=patch_danger * 0.95,
            )

        _clamp_needs(agent)
        agent.previous_hunger = start_hunger
        agent.previous_thirst = start_thirst
        agent.previous_fatigue = start_fatigue
        agent.previous_stress = start_stress
        agent.previous_social_need = start_social_need
        outcomes[agent_id] = outcome

        salience = abs(outcome.outcome_score) + (0.35 if not outcome.success else 0.0)
        if salience >= state.config.memory.salience_threshold:
            record_episode(
                agent.episodes,
                Episode(
                    tick=clock.tick,
                    kind=outcome.action,
                    patch_id=agent.patch_id,
                    salience=salience,
                    other_agent_id=outcome.target_agent_id,
                    outcome=outcome.outcome_score,
                ),
                state.config.memory.max_episodes,
            )
        if outcome.success:
            state.event_bus.emit(
                EventRecord(
                    tick=clock.tick,
                    day=clock.day,
                    kind=f"action_{outcome.action}",
                    agent_id=agent.agent_id,
                    other_agent_id=outcome.target_agent_id,
                    patch_id=agent.patch_id,
                    payload={"score": round(outcome.outcome_score, 3)},
                    trace=trace_tags(season=clock.season_name),
                )
            )
    return outcomes
