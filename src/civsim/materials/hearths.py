from __future__ import annotations

from ..events.types import EventRecord


def _hearth_patch(world, patch_id: int) -> int:
    candidates = (patch_id, *world.grid.neighbor_tuple(patch_id))
    best_patch = patch_id
    best_score = -999.0
    for candidate in candidates:
        local_patches = (candidate, *world.grid.neighbor_tuple(candidate))
        water_access = max(
            float(world.water[candidate]) * 0.82,
            sum(float(world.water[neighbor]) for neighbor in local_patches) / len(local_patches),
        )
        score = (
            float(world.shelter[candidate]) * 0.55
            + water_access * 0.22
            - max(0.0, float(world.water[candidate]) - 0.54) * 0.8
            - float(world.danger[candidate]) * 0.3
        )
        if score > best_score:
            best_patch = candidate
            best_score = score
    return best_patch


def strengthen_hearths(world, agents, clock, config, event_bus) -> None:
    occupants_by_patch: dict[int, list] = {}
    for agent in agents:
        if not agent.alive or agent.current_action not in {"rest", "shelter_at_site", "stay_with_kin", "care_for_child"}:
            continue
        occupants_by_patch.setdefault(agent.patch_id, []).append(agent)
    for patch_id, patch_agents in occupants_by_patch.items():
        if len(patch_agents) < config.hearth_creation_threshold:
            continue
        hearth_patch = _hearth_patch(world, patch_id)
        site = world.ensure_site(hearth_patch)
        before = site.hearth_intensity
        previous_visits = site.visit_count
        site.hearth_intensity = min(3.0, site.hearth_intensity + config.hearth_strength_gain)
        site.last_used_day = clock.day
        site.visit_count += len(patch_agents)
        if before < 0.2 <= site.hearth_intensity:
            event_bus.emit(EventRecord(tick=clock.tick, day=clock.day, kind="hearth_formed", patch_id=hearth_patch))
        elif before >= 0.2 and (previous_visits // 12) < (site.visit_count // 12):
            event_bus.emit(EventRecord(tick=clock.tick, day=clock.day, kind="camp_reused", patch_id=hearth_patch))


def decay_hearths(world, decay: float) -> None:
    to_delete: list[int] = []
    for patch_id, site in world.site_markers.items():
        site.hearth_intensity *= 1.0 - decay
        if site.hearth_intensity < 0.02 and site.communal_food < 0.02:
            to_delete.append(patch_id)
    for patch_id in to_delete:
        del world.site_markers[patch_id]
