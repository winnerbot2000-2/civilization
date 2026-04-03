from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SiteMarker:
    patch_id: int
    hearth_intensity: float = 0.0
    communal_food: float = 0.0
    last_used_day: int = 0
    visit_count: int = 0


@dataclass(slots=True)
class PathTrace:
    edge: tuple[int, int]
    strength: float = 0.0
    use_count: int = 0
    last_used_day: int = 0
