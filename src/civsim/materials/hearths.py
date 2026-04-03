from __future__ import annotations

from ..events.types import EventRecord


def strengthen_hearths(world, agents, clock, config, event_bus) -> None:
    occupants_by_patch: dict[int, list] = {}
    for agent in agents:
        if not agent.alive or agent.current_action not in {"rest", "shelter_at_site", "stay_with_kin", "care_for_child"}:
            continue
        occupants_by_patch.setdefault(agent.patch_id, []).append(agent)
    for patch_id, patch_agents in occupants_by_patch.items():
        if len(patch_agents) < config.hearth_creation_threshold:
            continue
        site = world.ensure_site(patch_id)
        before = site.hearth_intensity
        site.hearth_intensity = min(3.0, site.hearth_intensity + config.hearth_strength_gain)
        site.last_used_day = clock.day
        site.visit_count += len(patch_agents)
        if before < 0.2 <= site.hearth_intensity:
            event_bus.emit(EventRecord(tick=clock.tick, day=clock.day, kind="hearth_formed", patch_id=patch_id))


def decay_hearths(world, decay: float) -> None:
    to_delete: list[int] = []
    for patch_id, site in world.site_markers.items():
        site.hearth_intensity *= 1.0 - decay
        if site.hearth_intensity < 0.02 and site.communal_food < 0.02:
            to_delete.append(patch_id)
    for patch_id in to_delete:
        del world.site_markers[patch_id]
