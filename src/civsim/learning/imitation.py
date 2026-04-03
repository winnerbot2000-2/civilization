from __future__ import annotations

from collections.abc import Iterable

from .skills import improve_skill


def apply_imitation(
    observer,
    visible_agents: Iterable,
    recent_actions: dict[int, tuple[str, bool]],
    imitation_rate: float,
    child_bonus: float,
) -> None:
    bonus = child_bonus if observer.age_stage == "child" else 0.0
    best_model = None
    best_weight = -999.0
    for other in visible_agents:
        action = recent_actions.get(other.agent_id)
        if action is None or not action[1]:
            continue
        weight = other.skills.foraging + other.skills.navigation + other.skills.caregiving
        edge = observer.social_memory.get(other.agent_id)
        if edge is not None:
            weight += edge.attachment + max(0.0, edge.trust)
            if edge.kin:
                weight += 0.5
        if other.agent_id == observer.caregiver_id:
            weight += 0.8
        if weight > best_weight:
            best_weight = weight
            best_model = (other, action[0])
    if best_model is None:
        return
    _, action_name = best_model
    if action_name in {"forage", "take_food_from_site"}:
        improve_skill(observer.skills, "foraging", imitation_rate + bonus)
    elif action_name in {"move_local", "move_to_known_site", "follow_caregiver", "explore"}:
        improve_skill(observer.skills, "navigation", imitation_rate + bonus)
    elif action_name in {"care_for_child", "share_food"}:
        improve_skill(observer.skills, "caregiving", imitation_rate + bonus)
