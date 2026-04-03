from __future__ import annotations


def caregiver_target_patch(agent, agents_by_id: dict[int, object]) -> int | None:
    if agent.caregiver_id is None:
        return None
    caregiver = agents_by_id.get(agent.caregiver_id)
    if caregiver is None or not caregiver.alive:
        return None
    return caregiver.patch_id


def pick_share_target(agent, nearby_agents: list[object]) -> object | None:
    best = None
    best_need = 0.0
    for other in nearby_agents:
        if other.agent_id == agent.agent_id or not other.alive:
            continue
        edge = agent.social_memory.get(other.agent_id)
        is_kin = other.agent_id in agent.parent_ids or other.agent_id in agent.child_ids
        if edge is None and not is_kin and other.age_stage != "child":
            continue
        need = other.hunger + other.social_need
        if other.age_stage == "child":
            need += 0.5
        if edge is not None:
            need += max(0.0, edge.trust + edge.attachment) * 0.2
        if is_kin:
            need += 0.3
        if need > best_need:
            best = other
            best_need = need
    return best
