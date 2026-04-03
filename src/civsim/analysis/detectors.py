from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CampRecord:
    patch_id: int
    hearth_intensity: float
    communal_food: float
    visit_count: int


@dataclass(slots=True)
class ClusterRecord:
    patch_id: int
    occupants: int
    kin_links: int


def detect_camps(world) -> list[CampRecord]:
    camps: list[CampRecord] = []
    for patch_id, site in world.site_markers.items():
        if site.hearth_intensity > 0.2 or site.communal_food > 0.2:
            camps.append(
                CampRecord(
                    patch_id=patch_id,
                    hearth_intensity=site.hearth_intensity,
                    communal_food=site.communal_food,
                    visit_count=site.visit_count,
                )
            )
    camps.sort(key=lambda item: item.hearth_intensity + item.communal_food, reverse=True)
    return camps


def detect_clusters(state) -> list[ClusterRecord]:
    clusters: list[ClusterRecord] = []
    for patch_id, occupants in state.world.occupancy.items():
        if len(occupants) < 2:
            continue
        kin_links = 0
        for agent_id in occupants:
            agent = state.agents_by_id[agent_id]
            for other_id in occupants:
                if other_id in agent.parent_ids or other_id in agent.child_ids:
                    kin_links += 1
        clusters.append(ClusterRecord(patch_id=patch_id, occupants=len(occupants), kin_links=kin_links))
    clusters.sort(key=lambda item: (item.occupants, item.kin_links), reverse=True)
    return clusters
