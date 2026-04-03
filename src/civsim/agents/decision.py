from __future__ import annotations

from dataclasses import dataclass

from ..memory.habits import habit_bias, transition_bias
from ..memory.spatial import patch_memory_bias, select_best_site
from ..social.coordination import pick_share_target, social_patch_bias


@dataclass(slots=True)
class ActionIntent:
    agent_id: int
    action: str
    target_patch: int | None = None
    target_agent_id: int | None = None
    score: float = 0.0


@dataclass(slots=True)
class NeedProfile:
    urgency: dict[str, float]
    trend: dict[str, float]
    fear: float
    attachment: float
    obligation: float
    attention_limit: int


def _positive_delta(current: float, previous: float) -> float:
    return max(0.0, current - previous)


def _clamp(value: float, low: float = 0.0, high: float = 2.0) -> float:
    return max(low, min(high, value))


def _need_profile(agent, percept, config, agents_by_id) -> NeedProfile:
    urgency = {
        "hunger": agent.hunger * (1.2 if agent.age_stage == "child" else 1.0),
        "thirst": agent.thirst,
        "fatigue": agent.fatigue,
        "safety": _clamp(agent.stress + percept.current_danger * (1.3 - agent.traits.boldness)),
        "social": agent.social_need * (1.2 if agent.age_stage == "child" else 1.0),
    }
    trend = {
        "hunger": _positive_delta(agent.hunger, agent.previous_hunger),
        "thirst": _positive_delta(agent.thirst, agent.previous_thirst),
        "fatigue": _positive_delta(agent.fatigue, agent.previous_fatigue),
        "safety": _positive_delta(agent.stress, agent.previous_stress) + max(0.0, percept.current_danger - 0.4) * 0.3,
        "social": _positive_delta(agent.social_need, agent.previous_social_need),
    }

    obligation = 0.0
    if agent.age_stage == "child":
        if percept.caregiver_patch is not None and percept.caregiver_patch != agent.patch_id:
            obligation = 1.2 + agent.traits.attachment_strength
    else:
        for child_id in agent.child_ids:
            child = agents_by_id.get(child_id)
            if child is None or not child.alive:
                continue
            need = child.hunger + child.social_need + child.stress
            if child.patch_id == agent.patch_id:
                need += 0.4
            elif child.patch_id in percept.nearby_patches:
                need += 0.15
            obligation = max(obligation, need * 0.55)

    attention_limit = max(
        2,
        min(
            len(percept.nearby_patches),
            config.decision.attention_patch_limit
            + round(agent.traits.patience + agent.traits.curiosity - (agent.stress * 1.7)),
        ),
    )

    return NeedProfile(
        urgency=urgency,
        trend=trend,
        fear=_clamp(agent.stress + percept.current_danger * (1.15 - agent.traits.boldness), 0.0, 2.5),
        attachment=_clamp(agent.traits.attachment_strength + obligation * 0.25, 0.0, 2.5),
        obligation=obligation,
        attention_limit=attention_limit,
    )


def _spatial_memory_value(agent, kind: str, patch_id: int) -> tuple[float, float, float]:
    entry = agent.spatial_memory.get((kind, patch_id))
    if entry is None:
        return 0.0, 0.15, 0.6
    expected = (
        entry.payoff * 0.3
        + entry.confidence * 0.55
        + entry.revisit_bias * 0.45
        + entry.emotional_weight * 0.08
    )
    risk = entry.risk * 0.35 + entry.avoidance_bias * 0.55
    uncertainty = max(0.0, 1.0 - entry.confidence) * max(0.45, 1.0 - entry.emotional_weight * 0.08)
    return expected, risk, uncertainty


def _local_patch_salience(agent, patch_id: int, world, profile: NeedProfile, percept, agents_by_id, social_config) -> float:
    occupants = world.occupancy.get(patch_id, [])
    social_bias = social_patch_bias(agent, occupants, agents_by_id, social_config)
    social_pull = (
        social_bias.affinity * (0.18 + profile.urgency["social"] * 0.2 + profile.attachment * 0.06)
        + social_bias.kin_presence * social_config.kin_preference_bias * 0.08
        + social_bias.familiar_presence * social_config.familiar_preference_bias * 0.08
    )
    social_risk = social_bias.avoidance * (0.3 + profile.fear * 0.08)
    memory_bias = patch_memory_bias(agent.spatial_memory, patch_id)
    return (
        world.water[patch_id] * profile.urgency["thirst"] * 0.9
        + world.food[patch_id] * profile.urgency["hunger"] * 0.8
        + world.shelter[patch_id] * profile.urgency["fatigue"] * 0.55
        - world.danger[patch_id] * profile.urgency["safety"] * (1.1 - agent.traits.boldness * 0.4)
        + memory_bias.expected * 0.45
        + memory_bias.revisit * 0.4
        - memory_bias.risk * 0.6
        - memory_bias.avoidance * 0.75
        + social_pull
        - social_risk
    )


def _focused_patches(agent, percept, world, profile: NeedProfile, agents_by_id, social_config, rng) -> list[int]:
    if len(percept.nearby_patches) <= profile.attention_limit:
        return percept.nearby_patches
    current_patch = agent.patch_id
    others = [patch_id for patch_id in percept.nearby_patches if patch_id != current_patch]
    ranked = sorted(
        others,
        key=lambda patch_id: _local_patch_salience(agent, patch_id, world, profile, percept, agents_by_id, social_config),
        reverse=True,
    )
    chosen = ranked[: max(1, profile.attention_limit - 1)]
    remainder = ranked[max(1, profile.attention_limit - 1) :]
    if remainder and agent.traits.curiosity > 0.45 and rng.random() < agent.traits.curiosity:
        chosen[-1] = remainder[rng.randrange(len(remainder))]
    return [current_patch, *chosen]


def _inertia_bonus(agent, action: str, target_patch: int | None, config, profile: NeedProfile) -> float:
    if agent.current_action != action:
        return 0.0
    streak_scale = min(3.0, max(1.0, float(agent.action_streak)))
    bonus = config.decision.inertia_bonus * streak_scale
    if action in {"move_local", "move_to_known_site", "follow_caregiver", "avoid_danger"} and agent.current_target_patch != target_patch:
        bonus *= 0.35
    urgency_pressure = max(profile.urgency.values()) + max(profile.trend.values())
    return bonus * max(0.25, 1.0 - urgency_pressure * 0.18)


def _personality_bias(agent, action: str) -> float:
    if action in {"explore", "move_local", "move_to_known_site"}:
        return agent.traits.curiosity * 0.25 + agent.traits.boldness * 0.12 - agent.traits.patience * 0.05
    if action in {"share_food", "stay_with_kin", "care_for_child", "follow_caregiver"}:
        return agent.traits.sociability * 0.22 + agent.traits.attachment_strength * 0.28
    if action in {"rest", "shelter_at_site", "wait"}:
        return agent.traits.patience * 0.22 - agent.traits.boldness * 0.05
    if action == "avoid_danger":
        return (1.0 - agent.traits.boldness) * 0.28
    return 0.0


def _emotional_bias(agent, action: str, profile: NeedProfile) -> float:
    if action in {"avoid_danger", "rest", "shelter_at_site", "follow_caregiver", "wait"}:
        return profile.fear * 0.28 + profile.attachment * (0.16 if action == "follow_caregiver" else 0.0)
    if action in {"explore", "move_local", "move_to_known_site"}:
        return -profile.fear * 0.22
    if action in {"share_food", "care_for_child", "stay_with_kin"}:
        return profile.attachment * 0.22 - profile.fear * 0.05
    return 0.0


def _social_bias(agent, action: str, profile: NeedProfile) -> float:
    if action in {"care_for_child", "follow_caregiver"}:
        return profile.obligation * 0.95
    if action in {"stay_with_kin", "share_food"}:
        return profile.obligation * 0.45 + profile.urgency["social"] * 0.4
    if action == "explore" and profile.obligation > 0.5:
        return -profile.obligation * 0.35
    if action == "move_to_known_site" and profile.obligation > 0.7:
        return -profile.obligation * 0.16
    return 0.0


def _add_candidate(
    candidates: list[ActionIntent],
    *,
    agent,
    config,
    rng,
    profile: NeedProfile,
    action: str,
    urgency: float,
    trend: float,
    expected: float,
    risk: float,
    target_patch: int | None = None,
    target_agent_id: int | None = None,
    context: str | None = None,
    uncertainty: float = 0.0,
) -> None:
    score = urgency
    score += trend * config.decision.trend_weight
    score += expected
    score -= risk + uncertainty * (0.35 + (1.0 - agent.traits.patience) * 0.25)
    score += _social_bias(agent, action, profile)
    score += _personality_bias(agent, action)
    score += _emotional_bias(agent, action, profile)
    score += habit_bias(agent.habits, f"action:{action}")
    score += transition_bias(agent.habits, agent.current_action if agent.current_action != "idle" else None, action)
    if context is not None:
        score += habit_bias(agent.habits, f"{action}:{context}")
    score += _inertia_bonus(agent, action, target_patch, config, profile)
    score += rng.gauss(0.0, config.decision.noise_scale * (0.8 + agent.traits.curiosity * 0.25))
    candidates.append(
        ActionIntent(
            agent_id=agent.agent_id,
            action=action,
            target_patch=target_patch,
            target_agent_id=target_agent_id,
            score=score,
        )
    )
def _fallback_intent(agent, percept, profile: NeedProfile, clock, best_social_patch: int | None = None) -> ActionIntent:
    if agent.age_stage == "child" and percept.caregiver_patch is not None and percept.caregiver_patch != agent.patch_id:
        return ActionIntent(agent_id=agent.agent_id, action="follow_caregiver", target_patch=percept.caregiver_patch, score=profile.obligation + 0.5)
    if profile.fear > 0.8 or profile.urgency["fatigue"] > 0.75 or clock.is_night:
        return ActionIntent(agent_id=agent.agent_id, action="wait", score=profile.fear + profile.urgency["fatigue"] * 0.5)
    if profile.urgency["social"] > 0.6 and percept.nearby_kin:
        if best_social_patch is not None and best_social_patch != agent.patch_id:
            return ActionIntent(agent_id=agent.agent_id, action="move_local", target_patch=best_social_patch, score=profile.urgency["social"] + profile.attachment * 0.45)
        return ActionIntent(agent_id=agent.agent_id, action="stay_with_kin", score=profile.urgency["social"] + profile.attachment * 0.3)
    if agent.traits.curiosity > 0.45 and (profile.urgency["hunger"] + profile.urgency["thirst"]) < 0.9:
        return ActionIntent(agent_id=agent.agent_id, action="explore", score=agent.traits.curiosity)
    return ActionIntent(agent_id=agent.agent_id, action="wait", score=0.1)


def _best_social_patch(agent, percept, world, agents_by_id, social_config) -> tuple[int | None, object | None]:
    best_patch = None
    best_bias = None
    best_score = 0.0
    for patch_id in percept.nearby_patches:
        if patch_id == agent.patch_id:
            continue
        occupants = world.occupancy.get(patch_id, [])
        if not occupants:
            continue
        bias = social_patch_bias(agent, occupants, agents_by_id, social_config)
        score = (
            bias.affinity
            + bias.kin_presence * social_config.kin_preference_bias * 0.35
            + bias.familiar_presence * social_config.familiar_preference_bias * 0.28
            - bias.avoidance * 0.8
        )
        if score > best_score:
            best_patch = patch_id
            best_bias = bias
            best_score = score
    return best_patch, best_bias


def generate_action_intent(agent, percept, world, agents_by_id, clock, config, rng) -> ActionIntent:
    if not agent.alive:
        return ActionIntent(agent.agent_id, "idle", score=-999.0)

    profile = _need_profile(agent, percept, config, agents_by_id)
    focused_patches = _focused_patches(agent, percept, world, profile, agents_by_id, config.social, rng)
    candidates: list[ActionIntent] = []
    current_patch_bias = patch_memory_bias(agent.spatial_memory, agent.patch_id)
    current_social_bias = social_patch_bias(agent, world.occupancy.get(agent.patch_id, []), agents_by_id, config.social)

    current_water_expected, _, current_water_uncertainty = _spatial_memory_value(agent, "water", agent.patch_id)
    current_food_expected, current_food_risk, current_food_uncertainty = _spatial_memory_value(agent, "food", agent.patch_id)
    current_shelter_expected, current_shelter_risk, current_shelter_uncertainty = _spatial_memory_value(agent, "shelter", agent.patch_id)

    if agent.age_stage == "child" and percept.caregiver_patch is not None and percept.caregiver_patch != agent.patch_id:
        _add_candidate(
            candidates,
            agent=agent,
            config=config,
            rng=rng,
            profile=profile,
            action="follow_caregiver",
            urgency=profile.urgency["social"] + profile.urgency["safety"] * 0.25,
            trend=profile.trend["social"] + profile.trend["safety"] * 0.3,
            expected=0.9 + profile.attachment * 0.4,
            risk=max(0.0, world.danger[percept.caregiver_patch] * 0.15),
            target_patch=percept.caregiver_patch,
        )

    if percept.current_water > 0.2:
        _add_candidate(
            candidates,
            agent=agent,
            config=config,
            rng=rng,
            profile=profile,
            action="drink",
            urgency=profile.urgency["thirst"] * 1.25,
            trend=profile.trend["thirst"],
            expected=percept.current_water * 0.9
            + current_water_expected * 0.35
            + current_patch_bias.revisit * 0.12
            + current_social_bias.affinity * 0.04,
            risk=percept.current_danger * 0.08 + current_patch_bias.avoidance * 0.08 + current_social_bias.avoidance * 0.06,
            context="water",
            uncertainty=current_water_uncertainty * 0.2,
        )

    if percept.current_food > 0.15:
        _add_candidate(
            candidates,
            agent=agent,
            config=config,
            rng=rng,
            profile=profile,
            action="forage",
            urgency=profile.urgency["hunger"] * 0.92,
            trend=profile.trend["hunger"],
            expected=percept.current_food * 0.75
            + agent.skills.foraging * 0.55
            + current_food_expected * 0.3
            + current_patch_bias.revisit * 0.12
            + current_social_bias.affinity * 0.04,
            risk=percept.current_danger * 0.14
            + agent.fatigue * 0.08
            + current_food_risk * 0.25
            + current_patch_bias.avoidance * 0.08
            + current_social_bias.avoidance * 0.08
            + profile.urgency["thirst"] * 0.38
            + profile.fear * 0.18,
            context="food",
            uncertainty=current_food_uncertainty * 0.25,
        )

    if clock.is_night:
        shelter_bonus = percept.current_shelter
        site = world.site_markers.get(agent.patch_id)
        if site is not None:
            shelter_bonus += site.hearth_intensity * config.world.camp_shelter_bonus
        _add_candidate(
            candidates,
            agent=agent,
            config=config,
            rng=rng,
            profile=profile,
            action="shelter_at_site",
            urgency=profile.urgency["fatigue"] + profile.urgency["safety"] * 0.25,
            trend=profile.trend["fatigue"] + profile.trend["safety"] * 0.2,
            expected=shelter_bonus * 0.8
            + current_shelter_expected * 0.3
            + current_patch_bias.revisit * 0.1
            + current_social_bias.affinity * 0.08,
            risk=current_shelter_risk * 0.2 + current_patch_bias.avoidance * 0.08 + current_social_bias.avoidance * 0.08,
            uncertainty=current_shelter_uncertainty * 0.2,
        )

    _add_candidate(
        candidates,
        agent=agent,
        config=config,
        rng=rng,
        profile=profile,
        action="rest",
        urgency=profile.urgency["fatigue"] + profile.urgency["safety"] * 0.15,
        trend=profile.trend["fatigue"],
        expected=percept.current_shelter * 0.55
        + current_shelter_expected * 0.2
        + current_patch_bias.revisit * 0.08
        + current_social_bias.affinity * 0.05,
        risk=percept.current_danger * 0.04 + current_patch_bias.avoidance * 0.05 + current_social_bias.avoidance * 0.06,
        uncertainty=current_shelter_uncertainty * 0.1,
    )

    _add_candidate(
        candidates,
        agent=agent,
        config=config,
        rng=rng,
        profile=profile,
        action="wait",
        urgency=profile.urgency["safety"] * 0.2 + profile.urgency["fatigue"] * 0.15,
        trend=profile.trend["safety"] * 0.3,
        expected=0.08 + percept.current_shelter * 0.08 + current_social_bias.affinity * 0.04,
        risk=percept.current_danger * 0.02 + current_social_bias.avoidance * 0.05,
    )

    if percept.current_danger > 0.45 and percept.best_neighbor_for_safety is not None:
        target = percept.best_neighbor_for_safety
        _add_candidate(
            candidates,
            agent=agent,
            config=config,
            rng=rng,
            profile=profile,
            action="avoid_danger",
            urgency=profile.urgency["safety"],
            trend=profile.trend["safety"],
            expected=max(0.0, percept.current_danger - world.danger[target]) * 0.9,
            risk=world.danger[target] * 0.2 + world.movement_cost[target] * 0.08,
            target_patch=target,
        )

    if current_social_bias.affinity > 0.15 and current_social_bias.avoidance < max(0.45, current_social_bias.affinity * 0.8):
        _add_candidate(
            candidates,
            agent=agent,
            config=config,
            rng=rng,
            profile=profile,
            action="stay_with_kin",
            urgency=profile.urgency["social"] * (1.1 if agent.age_stage == "child" else 0.65) + profile.obligation * 0.15,
            trend=profile.trend["social"],
            expected=0.2
            + current_social_bias.affinity * 0.42
            + current_social_bias.kin_presence * config.social.kin_preference_bias * 0.15
            + current_social_bias.familiar_presence * config.social.familiar_preference_bias * 0.12,
            risk=0.02 + current_social_bias.avoidance * 0.12,
        )

    if agent.age_stage != "child":
        nearby_children = [
            agents_by_id[child_id]
            for child_id in agent.child_ids
            if child_id in agents_by_id
            and agents_by_id[child_id].alive
            and agents_by_id[child_id].patch_id in percept.nearby_patches
            and agents_by_id[child_id].patch_id != agent.patch_id
        ]
        if nearby_children:
            child = max(
                nearby_children,
                key=lambda entry: entry.hunger + entry.social_need + entry.stress + (0.2 if entry.patch_id != agent.patch_id else 0.0),
            )
            need = child.hunger + child.social_need + child.stress
            child_trend = max(0.0, need - (child.previous_hunger + child.previous_social_need + child.previous_stress))
            _add_candidate(
                candidates,
                agent=agent,
                config=config,
                rng=rng,
                profile=profile,
                action="move_local",
                urgency=profile.obligation * 0.9 + need * 0.35,
                trend=child_trend * 0.45 + profile.trend["social"] * 0.2,
                expected=0.7 + profile.attachment * 0.35 + config.social.caregiver_priority_bias * 0.35,
                risk=world.danger[child.patch_id] * 0.18 + world.movement_cost[child.patch_id] * 0.08,
                target_patch=child.patch_id,
                context="child",
            )

        needy_children = [
            agents_by_id[child_id]
            for child_id in agent.child_ids
            if child_id in agents_by_id and agents_by_id[child_id].alive and agents_by_id[child_id].patch_id == agent.patch_id
        ]
        if needy_children and (agent.carried_food > config.social.share_amount or world.site_markers.get(agent.patch_id, None) is not None):
            child = max(needy_children, key=lambda entry: entry.hunger + entry.social_need + entry.stress)
            need = child.hunger + child.social_need + child.stress
            _add_candidate(
                candidates,
                agent=agent,
                config=config,
                rng=rng,
                profile=profile,
                action="care_for_child",
                urgency=need * 0.7,
                trend=max(0.0, need - (child.previous_hunger + child.previous_social_need + child.previous_stress)) * 0.45,
                expected=agent.skills.caregiving * 0.55 + profile.attachment * 0.25 + 0.35,
                risk=max(0.0, 0.18 - agent.carried_food * 0.08),
                target_agent_id=child.agent_id,
            )

    best_social_patch, best_social_bias = _best_social_patch(agent, percept, world, agents_by_id, config.social)
    if best_social_patch is not None and best_social_bias is not None:
        _add_candidate(
            candidates,
            agent=agent,
            config=config,
            rng=rng,
            profile=profile,
            action="move_local",
            urgency=profile.urgency["social"] * 0.75 + profile.obligation * 0.35,
            trend=profile.trend["social"] * 0.8,
            expected=best_social_bias.affinity * 0.35
            + best_social_bias.kin_presence * config.social.kin_preference_bias * 0.18
            + best_social_bias.familiar_presence * config.social.familiar_preference_bias * 0.18,
            risk=world.danger[best_social_patch] * 0.12
            + world.movement_cost[best_social_patch] * 0.08
            + best_social_bias.avoidance * 0.3,
            target_patch=best_social_patch,
            context="social",
        )

    if agent.carried_food > config.social.share_threshold and percept.nearby_agents:
        nearby_people = [agents_by_id[other_id] for other_id in percept.nearby_agents if agents_by_id[other_id].patch_id == agent.patch_id]
        target = pick_share_target(agent, nearby_people, config.social)
        if target is not None:
            share_drive = target.hunger + target.social_need + target.stress * 0.5 + (0.55 if target.age_stage == "child" else 0.0)
            edge = agent.social_memory.get(target.agent_id)
            reciprocity_pull = max(0.0, -edge.reciprocity) * config.social.reciprocity_bias if edge is not None else 0.0
            _add_candidate(
                candidates,
                agent=agent,
                config=config,
                rng=rng,
                profile=profile,
                action="share_food",
                urgency=profile.urgency["social"] * 0.25,
                trend=profile.trend["social"] * 0.2,
                expected=agent.carried_food * 0.08
                + share_drive * 0.45
                + (max(0.0, edge.trust + edge.attachment) * 0.18 if edge is not None else 0.0)
                + reciprocity_pull
                + (config.social.kin_preference_bias * 0.18 if target.agent_id in agent.child_ids or target.agent_id in agent.parent_ids else 0.0),
                risk=max(0.0, 0.25 - agent.carried_food * 0.1)
                + (max(0.0, edge.harm - edge.trust) * 0.22 if edge is not None else 0.0),
                target_agent_id=target.agent_id,
            )

    site = world.site_markers.get(agent.patch_id)
    if site is not None and site.communal_food > 0.2 and agent.hunger > 0.5:
        _add_candidate(
            candidates,
            agent=agent,
            config=config,
            rng=rng,
            profile=profile,
            action="take_food_from_site",
            urgency=profile.urgency["hunger"],
            trend=profile.trend["hunger"],
            expected=min(1.0, site.communal_food * 0.18),
            risk=max(0.0, 0.2 - agent.traits.patience * 0.08),
        )
    if site is not None and agent.carried_food > 1.2:
        _add_candidate(
            candidates,
            agent=agent,
            config=config,
            rng=rng,
            profile=profile,
            action="store_food_at_site",
            urgency=profile.urgency["social"] * 0.12,
            trend=0.0,
            expected=agent.traits.patience * 0.18 + profile.attachment * 0.15,
            risk=max(0.0, 0.12 - site.hearth_intensity * 0.03),
        )

    if agent.thirst > 0.25:
        remembered_water = select_best_site(agent.spatial_memory, "water", agent.patch_id, world.grid)
        if remembered_water is not None and remembered_water.patch_id != agent.patch_id:
            distance = world.grid.distance(agent.patch_id, remembered_water.patch_id)
            _add_candidate(
                candidates,
                agent=agent,
                config=config,
                rng=rng,
                profile=profile,
                action="move_to_known_site",
                urgency=profile.urgency["thirst"] * 1.65,
                trend=profile.trend["thirst"],
                expected=remembered_water.payoff * 0.35
                + remembered_water.confidence * 1.0
                + remembered_water.revisit_bias * 0.45
                + remembered_water.emotional_weight * 0.08,
                risk=distance * 0.04
                + remembered_water.risk * 0.22
                + remembered_water.avoidance_bias * 0.35
                + agent.fatigue * 0.05,
                target_patch=remembered_water.patch_id,
                context="water",
                uncertainty=max(0.0, 1.0 - remembered_water.confidence) * 0.4,
            )
    if agent.hunger > 0.35:
        remembered_food = select_best_site(agent.spatial_memory, "food", agent.patch_id, world.grid)
        if remembered_food is not None and remembered_food.patch_id != agent.patch_id:
            distance = world.grid.distance(agent.patch_id, remembered_food.patch_id)
            _add_candidate(
                candidates,
                agent=agent,
                config=config,
                rng=rng,
                profile=profile,
                action="move_to_known_site",
                urgency=profile.urgency["hunger"],
                trend=profile.trend["hunger"],
                expected=remembered_food.payoff * 0.24
                + remembered_food.confidence * 0.7
                + remembered_food.revisit_bias * 0.4
                + remembered_food.emotional_weight * 0.08,
                risk=distance * 0.11
                + remembered_food.risk * 0.4
                + remembered_food.avoidance_bias * 0.45
                + agent.fatigue * 0.12,
                target_patch=remembered_food.patch_id,
                context="food",
                uncertainty=max(0.0, 1.0 - remembered_food.confidence),
            )
    remembered_shelter = select_best_site(agent.spatial_memory, "shelter", agent.patch_id, world.grid)
    if (clock.is_night or agent.fatigue > 0.45) and remembered_shelter is not None and remembered_shelter.patch_id != agent.patch_id:
        distance = world.grid.distance(agent.patch_id, remembered_shelter.patch_id)
        _add_candidate(
            candidates,
            agent=agent,
            config=config,
            rng=rng,
            profile=profile,
            action="move_to_known_site",
            urgency=profile.urgency["fatigue"] + profile.urgency["safety"] * 0.2,
            trend=profile.trend["fatigue"],
            expected=remembered_shelter.payoff * 0.28
            + remembered_shelter.confidence * 0.55
            + remembered_shelter.revisit_bias * 0.32
            + remembered_shelter.emotional_weight * 0.06,
            risk=distance * 0.08 + remembered_shelter.risk * 0.28 + remembered_shelter.avoidance_bias * 0.3,
            target_patch=remembered_shelter.patch_id,
            context="shelter",
            uncertainty=max(0.0, 1.0 - remembered_shelter.confidence),
        )

    for neighbor in focused_patches:
        if neighbor == agent.patch_id:
            continue
        path_bias = world.path_traces.get(world.grid.ordered_edge(agent.patch_id, neighbor))
        neighbor_memory = patch_memory_bias(agent.spatial_memory, neighbor)
        neighbor_social = social_patch_bias(agent, world.occupancy.get(neighbor, []), agents_by_id, config.social)
        expected = (
            world.water[neighbor] * profile.urgency["thirst"] * 0.45
            + world.food[neighbor] * profile.urgency["hunger"] * 0.4
            + world.shelter[neighbor] * profile.urgency["fatigue"] * 0.2
            + neighbor_memory.expected * 0.45
            + neighbor_memory.revisit * 0.28
            + neighbor_social.affinity * 0.18
            + neighbor_social.kin_presence * config.social.kin_preference_bias * 0.08
            + neighbor_social.familiar_presence * config.social.familiar_preference_bias * 0.08
        )
        if path_bias is not None:
            expected += path_bias.strength * 0.06
        risk = (
            world.danger[neighbor] * (0.4 + (1.0 - agent.traits.boldness) * 0.18)
            + world.movement_cost[neighbor] * 0.1
            + neighbor_memory.risk * 0.45
            + neighbor_memory.avoidance * 0.6
            + neighbor_social.avoidance * 0.4
        )
        _add_candidate(
            candidates,
            agent=agent,
            config=config,
            rng=rng,
            profile=profile,
            action="move_local",
            urgency=max(profile.urgency["hunger"], profile.urgency["thirst"], profile.urgency["social"] * 0.35),
            trend=max(profile.trend["hunger"], profile.trend["thirst"], profile.trend["safety"] * 0.5),
            expected=expected + agent.skills.navigation * 0.16,
            risk=risk + profile.urgency["fatigue"] * 0.12,
            target_patch=neighbor,
        )

    explore_uncertainty = max(0.0, 1.0 - (len(agent.spatial_memory) / max(1, config.memory.max_spatial_entries)))
    _add_candidate(
        candidates,
        agent=agent,
        config=config,
        rng=rng,
        profile=profile,
        action="explore",
        urgency=agent.traits.curiosity * 0.35,
        trend=0.0,
        expected=agent.traits.curiosity * 0.45 + explore_uncertainty * 0.3,
        risk=profile.fear * 0.28 + profile.urgency["hunger"] * 0.24 + profile.urgency["thirst"] * 0.24 + profile.urgency["fatigue"] * 0.16,
        uncertainty=explore_uncertainty * 0.15,
    )

    ranked = sorted(candidates, key=lambda item: item.score, reverse=True)
    considered = ranked[: config.decision.attention_action_limit]
    if not considered:
        return _fallback_intent(agent, percept, profile, clock, best_social_patch=best_social_patch)

    top = considered[0]
    second = considered[1] if len(considered) > 1 else None
    current_candidate = next(
        (
            candidate
            for candidate in considered
            if candidate.action == agent.current_action
            and candidate.target_patch == agent.current_target_patch
        ),
        None,
    )
    if current_candidate is not None and top.action != current_candidate.action:
        if top.score - current_candidate.score < config.decision.inertia_switch_margin:
            return current_candidate

    critical_pressure = max(
        profile.urgency["thirst"],
        profile.urgency["hunger"],
        profile.urgency["safety"],
        profile.obligation,
    )
    if critical_pressure > 0.9 and top.action in {
        "move_to_known_site",
        "drink",
        "forage",
        "avoid_danger",
        "follow_caregiver",
        "care_for_child",
    }:
        return top

    if top.score < config.decision.fallback_threshold:
        return _fallback_intent(agent, percept, profile, clock, best_social_patch=best_social_patch)
    if second is not None and (top.score - second.score) < config.decision.uncertainty_margin:
        return _fallback_intent(agent, percept, profile, clock, best_social_patch=best_social_patch)
    return top
