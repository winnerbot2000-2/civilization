from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SocialPatchBias:
    affinity: float = 0.0
    avoidance: float = 0.0
    kin_presence: float = 0.0
    familiar_presence: float = 0.0


def caregiver_target_patch(agent, agents_by_id: dict[int, object]) -> int | None:
    if agent.caregiver_id is None:
        return None
    caregiver = agents_by_id.get(agent.caregiver_id)
    if caregiver is None or not caregiver.alive:
        return None
    return caregiver.patch_id


def is_kin(agent, other) -> bool:
    return other.agent_id in agent.parent_ids or other.agent_id in agent.child_ids


def relationship_bias(agent, other, social_config) -> tuple[float, float, bool, bool]:
    edge = agent.social_memory.get(other.agent_id)
    kin = is_kin(agent, other)
    familiar = False
    affinity = 0.0
    avoidance = 0.0

    if kin:
        affinity += social_config.kin_preference_bias
    if other.agent_id == agent.caregiver_id:
        affinity += social_config.caregiver_priority_bias * 1.2
    if other.agent_id in agent.child_ids:
        affinity += social_config.caregiver_priority_bias * 1.35
    if other.agent_id in agent.parent_ids:
        affinity += social_config.kin_preference_bias * 0.55

    if edge is not None:
        familiar = edge.co_residence_score > 0.08 or edge.attachment > 0.08 or abs(edge.trust) > 0.05
        affinity += max(0.0, edge.trust) * 0.35
        affinity += edge.attachment * 0.38
        affinity += edge.co_residence_score * social_config.familiar_preference_bias * 0.22
        affinity += max(0.0, -edge.reciprocity) * social_config.reciprocity_bias
        affinity += edge.positive_salience * 0.05
        avoidance += edge.harm * social_config.avoidance_bias
        avoidance += edge.negative_salience * social_config.avoidance_bias * 0.3
        avoidance += max(0.0, -edge.trust) * 0.2

    return affinity, avoidance, kin, familiar


def social_patch_bias(agent, occupants: list[int], agents_by_id: dict[int, object], social_config) -> SocialPatchBias:
    bias = SocialPatchBias()
    top_affinity = 0.0
    second_affinity = 0.0
    third_affinity = 0.0
    top_avoidance = 0.0
    second_avoidance = 0.0
    for other_id in occupants:
        if other_id == agent.agent_id:
            continue
        other = agents_by_id.get(other_id)
        if other is None or not other.alive:
            continue
        edge = agent.social_memory.get(other.agent_id)
        kin = is_kin(agent, other)
        familiar = False
        affinity = 0.0
        avoidance = 0.0
        if kin:
            affinity += social_config.kin_preference_bias
        if other.agent_id == agent.caregiver_id:
            affinity += social_config.caregiver_priority_bias * 1.2
        if other.agent_id in agent.child_ids:
            affinity += social_config.caregiver_priority_bias * 1.35
        if other.agent_id in agent.parent_ids:
            affinity += social_config.kin_preference_bias * 0.55
        if edge is not None:
            familiar = edge.co_residence_score > 0.08 or edge.attachment > 0.08 or abs(edge.trust) > 0.05
            affinity += max(0.0, edge.trust) * 0.35
            affinity += edge.attachment * 0.38
            affinity += edge.co_residence_score * social_config.familiar_preference_bias * 0.22
            affinity += max(0.0, -edge.reciprocity) * social_config.reciprocity_bias
            affinity += edge.positive_salience * 0.05
            avoidance += edge.harm * social_config.avoidance_bias
            avoidance += edge.negative_salience * social_config.avoidance_bias * 0.3
            avoidance += max(0.0, -edge.trust) * 0.2
        if kin:
            bias.kin_presence += 1.0
        if familiar:
            bias.familiar_presence += 1.0
        if affinity > 0.0:
            if affinity >= top_affinity:
                third_affinity = second_affinity
                second_affinity = top_affinity
                top_affinity = affinity
            elif affinity >= second_affinity:
                third_affinity = second_affinity
                second_affinity = affinity
            elif affinity > third_affinity:
                third_affinity = affinity
        if avoidance > 0.0:
            if avoidance >= top_avoidance:
                second_avoidance = top_avoidance
                top_avoidance = avoidance
            elif avoidance > second_avoidance:
                second_avoidance = avoidance
    bias.affinity = top_affinity + (second_affinity + third_affinity) * 0.55
    bias.avoidance = top_avoidance + second_avoidance * 0.35
    return bias


def pick_share_target(agent, nearby_agents: list[object], social_config) -> object | None:
    best = None
    best_need = -999.0
    for other in nearby_agents:
        if other.agent_id == agent.agent_id or not other.alive:
            continue
        edge = agent.social_memory.get(other.agent_id)
        kin = is_kin(agent, other)
        if edge is None and not kin and other.age_stage != "child":
            continue

        need = other.hunger + other.social_need + other.stress * 0.45
        if other.age_stage == "child":
            need += 0.5
        if kin:
            need += social_config.kin_preference_bias * 0.65
        if edge is not None:
            need += max(0.0, edge.trust + edge.attachment) * 0.3
            need += edge.co_residence_score * social_config.familiar_preference_bias * 0.22
            need += max(0.0, -edge.reciprocity) * social_config.reciprocity_bias * 0.95
            need += edge.positive_salience * 0.08
            need -= edge.harm * social_config.avoidance_bias * 0.5
            need -= edge.negative_salience * 0.12
        if need > best_need:
            best = other
            best_need = need
    return best
