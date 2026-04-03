from __future__ import annotations

from dataclasses import dataclass

from ..world.grid import Grid


@dataclass(slots=True)
class PatchMemoryBias:
    patch_id: int
    expected: float = 0.0
    risk: float = 0.0
    revisit: float = 0.0
    avoidance: float = 0.0
    emotional: float = 0.0


@dataclass(slots=True)
class SpatialMemoryEntry:
    kind: str
    patch_id: int
    confidence: float
    payoff: float
    risk: float
    emotional_weight: float
    revisit_bias: float
    avoidance_bias: float
    last_seen_day: int


def remember_site(
    memory: dict[tuple[str, int], SpatialMemoryEntry],
    kind: str,
    patch_id: int,
    payoff: float,
    risk: float,
    day: int,
    max_entries: int,
    emotional_impact: float = 0.0,
    revisit_delta: float = 0.0,
    avoidance_delta: float = 0.0,
) -> None:
    key = (kind, patch_id)
    entry = memory.get(key)
    emotion = max(0.0, emotional_impact)
    confidence_scale = 1.18 if kind == "water" else 1.0
    revisit_scale = 1.35 if kind == "water" else 1.0
    payoff_scale = 1.15 if kind == "water" else 1.0
    if entry is None:
        memory[key] = SpatialMemoryEntry(
            kind=kind,
            patch_id=patch_id,
            confidence=min(1.35, 0.4 + emotion * 0.18 * confidence_scale + max(0.0, payoff) * 0.08 * confidence_scale),
            payoff=payoff,
            risk=risk,
            emotional_weight=emotion,
            revisit_bias=max(0.0, revisit_delta * revisit_scale + max(0.0, payoff) * 0.2 * payoff_scale + emotion * 0.12 * confidence_scale),
            avoidance_bias=max(0.0, avoidance_delta + max(0.0, risk) * 0.25 + emotion * 0.1),
            last_seen_day=day,
        )
    else:
        entry.confidence = min(1.7, entry.confidence * 0.82 + 0.16 + emotion * 0.1 * confidence_scale)
        entry.payoff = (entry.payoff * 0.64) + (payoff * 0.36 if kind == "water" else payoff * 0.32)
        entry.risk = (entry.risk * 0.68) + (risk * 0.32)
        entry.emotional_weight = min(2.8 if kind == "water" else 2.5, entry.emotional_weight * 0.78 + emotion * 0.55)
        entry.revisit_bias = max(
            -0.5,
            min(
                3.4 if kind == "water" else 3.0,
                entry.revisit_bias * 0.75
                + revisit_delta * 0.6 * revisit_scale
                + max(0.0, payoff) * 0.18 * payoff_scale
                + emotion * 0.12 * confidence_scale
                - avoidance_delta * 0.08,
            ),
        )
        entry.avoidance_bias = max(
            0.0,
            min(
                3.0,
                entry.avoidance_bias * 0.78
                + avoidance_delta * 0.65
                + max(0.0, risk) * 0.2
                + emotion * 0.1,
            ),
        )
        entry.last_seen_day = day

    if len(memory) > max_entries:
        weakest = min(
            memory.items(),
            key=lambda item: (
                item[1].confidence
                + item[1].payoff
                + item[1].revisit_bias * 0.6
                + item[1].emotional_weight * 0.15
                - item[1].risk
                - item[1].avoidance_bias * 0.4
            ),
        )
        del memory[weakest[0]]


def decay_spatial_memory(memory: dict[tuple[str, int], SpatialMemoryEntry], decay: float) -> None:
    to_delete: list[tuple[str, int]] = []
    for key, entry in memory.items():
        local_decay = decay * (0.7 if entry.kind == "water" else 1.0)
        entry.confidence *= 1.0 - local_decay
        entry.payoff *= 1.0 - (local_decay * 0.45)
        entry.risk *= 1.0 - (decay * 0.35)
        entry.emotional_weight *= 1.0 - (local_decay * 0.25)
        entry.revisit_bias *= 1.0 - (local_decay * 0.28)
        entry.avoidance_bias *= 1.0 - (decay * 0.18)
        if (
            entry.confidence <= 0.03
            and abs(entry.payoff) <= (0.07 if entry.kind == "water" else 0.03)
            and entry.risk <= 0.03
            and entry.emotional_weight <= 0.03
            and abs(entry.revisit_bias) <= (0.06 if entry.kind == "water" else 0.03)
            and entry.avoidance_bias <= 0.04
        ):
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
    if kind == "water":
        return max(
            candidates,
            key=lambda entry: (
                entry.payoff * 0.78
                + entry.confidence * 0.82
                + entry.revisit_bias * 1.1
                + entry.emotional_weight * 0.18
                - entry.risk * 0.35
                - entry.avoidance_bias * 0.45
                - (grid.distance(current_patch, entry.patch_id) * 0.03)
            ),
        )
    return max(
        candidates,
        key=lambda entry: (
            entry.payoff * 0.7
            + entry.confidence * 0.55
            + entry.revisit_bias * 0.8
            + entry.emotional_weight * 0.15
            - entry.risk * 0.55
            - entry.avoidance_bias * 0.8
            - (grid.distance(current_patch, entry.patch_id) * 0.05)
        ),
    )


def patch_memory_bias(memory: dict[tuple[str, int], SpatialMemoryEntry], patch_id: int) -> PatchMemoryBias:
    bias = PatchMemoryBias(patch_id=patch_id)
    for entry in memory.values():
        if entry.patch_id != patch_id:
            continue
        bias.emotional = max(bias.emotional, entry.emotional_weight)
        if entry.kind == "danger":
            bias.risk = max(bias.risk, entry.risk * 0.55 + entry.avoidance_bias * 0.85)
            bias.avoidance = max(bias.avoidance, entry.avoidance_bias)
            continue
        bias.expected = max(
            bias.expected,
            entry.payoff * 0.35 + entry.confidence * 0.35 + entry.revisit_bias * 0.55,
        )
        bias.revisit = max(bias.revisit, entry.revisit_bias)
        bias.risk = max(bias.risk, entry.risk * 0.2)
    return bias
