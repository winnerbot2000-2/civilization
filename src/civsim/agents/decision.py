from __future__ import annotations

from dataclasses import dataclass

from ..memory.habits import habit_bias
from ..memory.spatial import select_best_site


@dataclass(slots=True)
class ActionIntent:
    agent_id: int
    action: str
    target_patch: int | None = None
    target_agent_id: int | None = None
    score: float = 0.0


def _need_urgency(agent) -> dict[str, float]:
    return {
        "hunger": agent.hunger * (1.2 if agent.age_stage == "child" else 1.0),
        "thirst": agent.thirst,
        "fatigue": agent.fatigue,
        "stress": agent.stress,
        "social": agent.social_need * (1.2 if agent.age_stage == "child" else 1.0),
    }


def generate_action_intent(agent, percept, world, agents_by_id, clock, config, rng) -> ActionIntent:
    needs = _need_urgency(agent)
    candidates: list[ActionIntent] = []

    def score(action: str, base: float, target_patch: int | None = None, target_agent_id: int | None = None, context: str | None = None) -> None:
        noisy = base + habit_bias(agent.habits, f"action:{action}") + rng.uniform(-0.08, 0.08)
        if context is not None:
            noisy += habit_bias(agent.habits, f"{action}:{context}")
        candidates.append(ActionIntent(agent_id=agent.agent_id, action=action, target_patch=target_patch, target_agent_id=target_agent_id, score=noisy))

    if not agent.alive:
        return ActionIntent(agent.agent_id, "idle", score=-999.0)

    if agent.age_stage == "child" and percept.caregiver_patch is not None and percept.caregiver_patch != agent.patch_id:
        score("follow_caregiver", 1.5 + needs["social"] + needs["stress"] + agent.traits.attachment_strength, target_patch=percept.caregiver_patch)

    if percept.current_water > 0.2:
        score("drink", needs["thirst"] * 2.8 + 0.2 + percept.current_water * 0.2, context="water")
    if percept.current_food > 0.15:
        score("forage", needs["hunger"] * 2.6 + agent.skills.foraging * 0.7 + percept.current_food * 0.15, context="food")
    if clock.is_night:
        shelter_bonus = percept.current_shelter
        site = world.site_markers.get(agent.patch_id)
        if site is not None:
            shelter_bonus += site.hearth_intensity * 0.2
        score("shelter_at_site", needs["fatigue"] * 2.8 + shelter_bonus + agent.traits.patience + 0.2)
    score("rest", needs["fatigue"] * 2.2 + percept.current_shelter * 0.5)

    if percept.current_danger > 0.55 and percept.best_neighbor_for_safety is not None:
        score("avoid_danger", needs["stress"] * 1.8 + (1.0 - agent.traits.boldness), target_patch=percept.best_neighbor_for_safety)

    if agent.age_stage == "child":
        if percept.caregiver_patch == agent.patch_id:
            score("stay_with_kin", needs["social"] * 1.2 + agent.traits.attachment_strength)
    else:
        needy_children = [agents_by_id[child_id] for child_id in agent.child_ids if child_id in agents_by_id and agents_by_id[child_id].alive and agents_by_id[child_id].patch_id == agent.patch_id]
        if needy_children and (agent.carried_food > config.social.share_amount or world.site_markers.get(agent.patch_id, None) is not None):
            child_need = max(child.hunger + child.social_need for child in needy_children)
            score("care_for_child", child_need * 1.5 + agent.skills.caregiving + agent.traits.attachment_strength, target_agent_id=needy_children[0].agent_id)

    if agent.carried_food > config.social.share_threshold and percept.nearby_agents:
        nearby_people = [agents_by_id[other_id] for other_id in percept.nearby_agents if agents_by_id[other_id].patch_id == agent.patch_id]
        if nearby_people:
            target = max(
                nearby_people,
                key=lambda other: other.hunger
                + other.social_need
                + (0.6 if other.age_stage == "child" else 0.0)
                + (0.3 if other.agent_id in agent.child_ids or other.agent_id in agent.parent_ids else 0.0),
            )
            share_drive = target.hunger + target.social_need + (0.5 if target.age_stage == "child" else 0.0)
            score("share_food", agent.traits.sociability + agent.traits.attachment_strength + agent.carried_food * 0.15 + share_drive * 0.8, target_agent_id=target.agent_id)

    site = world.site_markers.get(agent.patch_id)
    if site is not None and site.communal_food > 0.2 and agent.hunger > 0.5:
        score("take_food_from_site", needs["hunger"] * 1.7 + max(0.0, agent.traits.patience - 0.2))
    if site is not None and agent.carried_food > 1.2:
        score("store_food_at_site", agent.traits.sociability + max(0.0, agent.traits.patience - 0.1))

    if agent.thirst > 0.3:
        remembered_water = select_best_site(agent.spatial_memory, "water", agent.patch_id, world.grid)
        if remembered_water is not None and remembered_water.patch_id != agent.patch_id:
            distance = world.grid.distance(agent.patch_id, remembered_water.patch_id)
            score("move_to_known_site", needs["thirst"] * 3.0 + min(1.2, remembered_water.confidence + remembered_water.payoff * 0.25) + 0.3 - needs["fatigue"] * 0.2 - distance * 0.06, target_patch=remembered_water.patch_id, context="water")
    if agent.hunger > 0.4:
        remembered_food = select_best_site(agent.spatial_memory, "food", agent.patch_id, world.grid)
        if remembered_food is not None and remembered_food.patch_id != agent.patch_id:
            distance = world.grid.distance(agent.patch_id, remembered_food.patch_id)
            score("move_to_known_site", needs["hunger"] * 1.8 + min(1.2, remembered_food.payoff * 0.25 + remembered_food.confidence) - needs["fatigue"] * 0.3 - distance * 0.12, target_patch=remembered_food.patch_id, context="food")
    remembered_shelter = select_best_site(agent.spatial_memory, "shelter", agent.patch_id, world.grid)
    if (clock.is_night or agent.fatigue > 0.5) and remembered_shelter is not None and remembered_shelter.patch_id != agent.patch_id:
        score("move_to_known_site", needs["fatigue"] * 2.1 + remembered_shelter.payoff, target_patch=remembered_shelter.patch_id, context="shelter")

    for neighbor in percept.nearby_patches:
        if neighbor == agent.patch_id:
            continue
        local_value = float(world.water[neighbor] * 0.5 + world.food[neighbor] * 0.6 + world.shelter[neighbor] * 0.2 - world.danger[neighbor] * (1.3 - agent.traits.boldness))
        path_bias = world.path_traces.get(world.grid.ordered_edge(agent.patch_id, neighbor))
        if path_bias is not None:
            local_value += path_bias.strength * 0.08
        score("move_local", local_value + agent.skills.navigation * 0.15 - needs["fatigue"] * 0.8, target_patch=neighbor)

    score("explore", agent.traits.curiosity + max(0.0, 0.2 - needs["hunger"] - needs["thirst"] - needs["fatigue"] * 1.2))

    return max(candidates, key=lambda item: item.score)
