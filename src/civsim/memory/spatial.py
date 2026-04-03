from __future__ import annotations

from dataclasses import dataclass

from ..world.grid import Grid


@dataclass(slots=True)
class SpatialMemoryEntry:
    kind: str
    patch_id: int
    confidence: float
    payoff: float
    risk: float
    last_seen_day: int


def remember_site(
    memory: dict[tuple[str, int], SpatialMemoryEntry],
    kind: str,
    patch_id: int,
    payoff: float,
    risk: float,
    day: int,
    max_entries: int,
) -> None:
    key = (kind, patch_id)
    entry = memory.get(key)
    if entry is None:
        memory[key] = SpatialMemoryEntry(
            kind=kind,
            patch_id=patch_id,
            confidence=0.5,
            payoff=payoff,
            risk=risk,
            last_seen_day=day,
        )
    else:
        entry.confidence = min(1.0, entry.confidence + 0.2)
        entry.payoff = (entry.payoff * 0.6) + (payoff * 0.4)
        entry.risk = (entry.risk * 0.6) + (risk * 0.4)
        entry.last_seen_day = day

    if len(memory) > max_entries:
        weakest = min(memory.items(), key=lambda item: item[1].confidence + item[1].payoff - item[1].risk)
        del memory[weakest[0]]


def decay_spatial_memory(memory: dict[tuple[str, int], SpatialMemoryEntry], decay: float) -> None:
    to_delete: list[tuple[str, int]] = []
    for key, entry in memory.items():
        entry.confidence -= decay
        if entry.confidence <= 0.05:
            to_delete.append(key)
    for key in to_delete:
        del memory[key]


def select_best_site(
    memory: dict[tuple[str, int], SpatialMemoryEntry],
    kind: str,
    current_patch: int,
    grid: Grid,
) -> SpatialMemoryEntry | None:
    candidates = [entry for entry in memory.values() if entry.kind == kind]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda entry: (entry.payoff + entry.confidence) - entry.risk - (grid.distance(current_patch, entry.patch_id) * 0.05),
    )
