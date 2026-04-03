from __future__ import annotations

from .model import Percept


def build_percept(agent, world, agents_by_id, perception_radius: int) -> Percept:
    nearby_patches = world.grid.patches_within_radius(agent.patch_id, perception_radius)

    nearby_agents: list[int] = []
    nearby_kin: list[int] = []
    for patch_id in nearby_patches:
        for other_id in world.occupancy.get(patch_id, ()):
            if other_id == agent.agent_id:
                continue
            nearby_agents.append(other_id)
            if other_id in agent.parent_ids or other_id in agent.child_ids:
                nearby_kin.append(other_id)

    caregiver_patch = None
    if agent.caregiver_id is not None and agent.caregiver_id in agents_by_id:
        caregiver_patch = agents_by_id[agent.caregiver_id].patch_id

    safest = None
    safest_score = 999.0
    best_visible_water_patch = None
    best_visible_water_score = -999.0
    best_visible_water_value = 0.0
    for patch_id in nearby_patches:
        score = float(world.danger[patch_id] + world.movement_cost[patch_id] * 0.1)
        if score < safest_score:
            safest = patch_id
            safest_score = score
        water_value = float(world.water[patch_id])
        water_score = water_value * 1.2 - float(world.danger[patch_id]) * 0.18 - float(world.movement_cost[patch_id]) * 0.04
        if water_score > best_visible_water_score:
            best_visible_water_patch = patch_id
            best_visible_water_score = water_score
            best_visible_water_value = water_value

    return Percept(
        current_patch=agent.patch_id,
        current_water=float(world.water[agent.patch_id]),
        current_food=float(world.food[agent.patch_id]),
        current_shelter=float(world.shelter[agent.patch_id]),
        current_danger=float(world.danger[agent.patch_id]),
        nearby_patches=nearby_patches,
        nearby_agents=nearby_agents,
        nearby_kin=nearby_kin,
        caregiver_patch=caregiver_patch,
        best_neighbor_for_safety=safest,
        best_visible_water_patch=best_visible_water_patch,
        best_visible_water_value=best_visible_water_value,
    )
