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


def _step_toward(world, source: int, target: int) -> int:
    neighbors = world.grid.neighbors(source)
    if not neighbors:
        return source
    return min(neighbors, key=lambda patch_id: world.grid.distance(patch_id, target) + world.movement_cost[patch_id] * 0.2)


def resolve_intents(state, intents, clock) -> dict[int, ActionOutcome]:
    outcomes: dict[int, ActionOutcome] = {}
    world = state.world
    cfg_agents = state.config.agents
    for agent_id in sorted(intents):
        agent = state.agents_by_id[agent_id]
        if not agent.alive:
            continue
        intent = intents[agent_id]
        agent.current_action = intent.action
        agent.last_patch_id = agent.patch_id
        outcome = ActionOutcome(agent_id=agent_id, action=intent.action, success=False, patch_id=agent.patch_id, target_patch=intent.target_patch, target_agent_id=intent.target_agent_id)

        if intent.action == "drink":
            if world.water[agent.patch_id] > 0.2:
                agent.thirst -= cfg_agents.base_water_relief * (1.0 + world.water[agent.patch_id] * 0.25)
                outcome.success = True
                outcome.outcome_score = 0.8
                remember_site(agent.spatial_memory, "water", agent.patch_id, payoff=float(world.water[agent.patch_id]), risk=float(world.danger[agent.patch_id]), day=clock.day, max_entries=state.config.memory.max_spatial_entries)
        elif intent.action == "forage":
            available = float(world.food[agent.patch_id])
            if available > 0.02:
                gained = min(available, cfg_agents.base_food_yield * (1.0 + agent.skills.foraging * 0.4))
                world.food[agent.patch_id] -= gained
                agent.carried_food = min(cfg_agents.max_carried_food, agent.carried_food + gained)
                agent.hunger -= gained * 0.25
                outcome.success = gained > 0.0
                outcome.outcome_score = gained
                remember_site(agent.spatial_memory, "food", agent.patch_id, payoff=gained, risk=float(world.danger[agent.patch_id]), day=clock.day, max_entries=state.config.memory.max_spatial_entries)
        elif intent.action in {"move_local", "move_to_known_site", "follow_caregiver", "avoid_danger"}:
            target = intent.target_patch if intent.target_patch is not None else agent.patch_id
            if target != agent.patch_id and target not in world.grid.neighbors(agent.patch_id):
                target = _step_toward(world, agent.patch_id, target)
            if target != agent.patch_id:
                old_patch = agent.patch_id
                agent.patch_id = target
                agent.fatigue += 0.02 * float(world.movement_cost[target])
                record_path_use(world, world.grid.ordered_edge(old_patch, target), clock.day, state.config.materials.path_strength_gain)
                outcome.success = True
                outcome.target_patch = target
                outcome.patch_id = target
                outcome.outcome_score = 0.25
        elif intent.action == "rest":
            agent.fatigue -= cfg_agents.rest_recovery * (1.0 + world.shelter[agent.patch_id] * 0.3)
            outcome.success = True
            outcome.outcome_score = 0.3
        elif intent.action == "explore":
            neighbors = world.grid.neighbors(agent.patch_id)
            if neighbors:
                unexplored = [patch for patch in neighbors if ("food", patch) not in agent.spatial_memory and ("water", patch) not in agent.spatial_memory]
                target = state.rng.python(f"explore:{agent.agent_id}:{clock.tick}").choice(unexplored or neighbors)
                old_patch = agent.patch_id
                agent.patch_id = target
                agent.fatigue += 0.025 * float(world.movement_cost[target])
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
                target = pick_share_target(agent, others_here)
            if target is not None and agent.carried_food > 0.2:
                amount = min(state.config.social.share_amount, agent.carried_food)
                agent.carried_food -= amount
                target.carried_food += amount
                target.hunger -= amount * 0.2
                remember_social(agent.social_memory, target.agent_id, clock.day, trust_delta=state.config.social.trust_gain, reciprocity_delta=0.1)
                remember_social(target.social_memory, agent.agent_id, clock.day, trust_delta=state.config.social.trust_gain, reciprocity_delta=-0.1)
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
                remember_social(agent.social_memory, child.agent_id, clock.day, attachment_delta=state.config.social.attachment_gain, trust_delta=0.03, kin=True)
                remember_social(child.social_memory, agent.agent_id, clock.day, attachment_delta=state.config.social.attachment_gain, trust_delta=0.03, kin=True)
                outcome.success = True
                outcome.target_agent_id = child.agent_id
                outcome.outcome_score = 0.6
        elif intent.action == "stay_with_kin":
            agent.social_need -= 0.1
            agent.stress -= 0.05
            outcome.success = True
            outcome.outcome_score = 0.25
        elif intent.action == "take_food_from_site":
            site = world.site_markers.get(agent.patch_id)
            if site is not None:
                taken = take_food(site, min(state.config.social.share_amount, cfg_agents.max_carried_food - agent.carried_food))
                agent.carried_food += taken
                agent.hunger -= taken * 0.15
                outcome.success = taken > 0.0
                outcome.outcome_score = taken
        elif intent.action == "store_food_at_site":
            site = world.ensure_site(agent.patch_id)
            stored = store_food(site, max(0.0, agent.carried_food - 0.8), state.config.materials.site_store_capacity)
            agent.carried_food -= stored
            outcome.success = stored > 0.0
            outcome.outcome_score = stored * 0.4
        elif intent.action == "shelter_at_site":
            site = world.site_markers.get(agent.patch_id)
            shelter_bonus = float(world.shelter[agent.patch_id]) + (site.hearth_intensity * 0.2 if site else 0.0)
            agent.fatigue -= cfg_agents.rest_recovery * (1.1 + shelter_bonus)
            remember_site(agent.spatial_memory, "shelter", agent.patch_id, payoff=shelter_bonus, risk=float(world.danger[agent.patch_id]), day=clock.day, max_entries=state.config.memory.max_spatial_entries)
            outcome.success = True
            outcome.outcome_score = 0.35 + shelter_bonus * 0.1

        agent.hunger += cfg_agents.hunger_rate + (state.config.life.child_hunger_penalty if agent.age_stage == "child" else 0.0)
        agent.thirst += cfg_agents.thirst_rate
        agent.fatigue += cfg_agents.fatigue_rate
        agent.social_need += cfg_agents.social_need_rate
        agent.stress = max(0.0, agent.stress - cfg_agents.stress_recovery)
        if agent.carried_food > 0.05 and agent.hunger > 0.4:
            consumed = min(agent.carried_food, 0.35)
            agent.carried_food -= consumed
            agent.hunger -= consumed * 0.6
        if world.danger[agent.patch_id] > 0.7:
            agent.stress += float(world.danger[agent.patch_id]) * 0.08
            remember_site(agent.spatial_memory, "danger", agent.patch_id, payoff=0.0, risk=float(world.danger[agent.patch_id]), day=clock.day, max_entries=state.config.memory.max_spatial_entries)

        _clamp_needs(agent)
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
