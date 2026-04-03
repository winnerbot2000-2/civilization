from __future__ import annotations

from ..events.trace import trace_tags
from ..events.types import EventRecord
from .development import inherit_traits


def attempt_conception(agent, partner, config, clock, rng, event_bus) -> None:
    if agent.sex != "female" or agent.age_stage != "adult":
        return
    if agent.pregnancy_days_remaining is not None or agent.fertility_cooldown > 0:
        return
    if partner.sex != "male" or partner.age_stage != "adult":
        return
    if agent.patch_id != partner.patch_id:
        return
    edge = agent.social_memory.get(partner.agent_id)
    if edge is None or edge.attachment < 0.3:
        return
    if agent.hunger > 0.9 or agent.thirst > 0.9 or partner.hunger > 0.9:
        return
    if rng.random() < config.base_conception_chance:
        agent.pregnancy_days_remaining = config.gestation_days
        agent.partner_id = partner.agent_id
        event_bus.emit(
            EventRecord(
                tick=clock.tick,
                day=clock.day,
                kind="conception",
                agent_id=agent.agent_id,
                other_agent_id=partner.agent_id,
                patch_id=agent.patch_id,
                trace=trace_tags(reason="attachment", season=clock.season_name),
            )
        )


def resolve_births(state, config, clock, rng, event_bus) -> list:
    newborns = []
    next_id = max(state.agents_by_id, default=-1) + 1
    for agent in list(state.agents):
        if not agent.alive or agent.pregnancy_days_remaining != 0:
            continue
        partner = state.agents_by_id.get(agent.partner_id)
        if partner is None or not partner.alive:
            agent.pregnancy_days_remaining = None
            continue
        traits = inherit_traits(agent, partner, rng, config.mutation_sigma)
        child = state.create_agent(
            agent_id=next_id,
            patch_id=agent.patch_id,
            sex="female" if rng.random() < 0.5 else "male",
            age_days=0,
            trait_overrides=traits,
            caregiver_id=agent.agent_id,
            parent_ids=(agent.agent_id, partner.agent_id),
        )
        child.age_stage = "child"
        child.caregiver_id = agent.agent_id
        state.agents.append(child)
        state.agents_by_id[child.agent_id] = child
        agent.child_ids.append(child.agent_id)
        partner.child_ids.append(child.agent_id)
        agent.pregnancy_days_remaining = None
        agent.fertility_cooldown = config.fertility_cooldown_days
        newborns.append(child)
        event_bus.emit(
            EventRecord(
                tick=clock.tick,
                day=clock.day,
                kind="birth",
                agent_id=agent.agent_id,
                other_agent_id=child.agent_id,
                patch_id=agent.patch_id,
            )
        )
        next_id += 1
    return newborns
