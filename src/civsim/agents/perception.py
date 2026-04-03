from __future__ import annotations

from .model import Percept


def build_percept(agent, world, agents_by_id, perception_radius: int) -> Percept:
    nearby = set(world.grid.neighbors(agent.patch_id))
    nearby.add(agent.patch_id)
    if perception_radius > 1:
        frontier = list(nearby)
        for _ in range(perception_radius - 1):
            for patch_id in list(frontier):
                nearby.update(world.grid.neighbors(patch_id))
            frontier = list(nearby)
    nearby_patches = sorted(nearby)

    nearby_agents: list[int] = []
    nearby_kin: list[int] = []
    for patch_id in nearby_patches:
        for other_id in world.occupancy.get(patch_id, []):
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
    for patch_id in nearby_patches:
        score = float(world.danger[patch_id] + world.movement_cost[patch_id] * 0.1)
        if score < safest_score:
            safest = patch_id
            safest_score = score

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
    )
