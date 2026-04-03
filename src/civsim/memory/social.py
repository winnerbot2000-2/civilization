from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SocialMemoryEdge:
    other_agent_id: int
    trust: float = 0.0
    reciprocity: float = 0.0
    attachment: float = 0.0
    harm: float = 0.0
    positive_salience: float = 0.0
    negative_salience: float = 0.0
    emotional_weight: float = 0.0
    kin: bool = False
    last_interaction_day: int = 0
    co_residence_score: float = 0.0


def remember_social(
    edges: dict[int, SocialMemoryEdge],
    other_agent_id: int,
    day: int,
    trust_delta: float = 0.0,
    reciprocity_delta: float = 0.0,
    attachment_delta: float = 0.0,
    harm_delta: float = 0.0,
    kin: bool | None = None,
    co_residence_delta: float = 0.0,
    emotional_impact: float = 0.0,
) -> SocialMemoryEdge:
    edge = edges.get(other_agent_id)
    if edge is None:
        edge = SocialMemoryEdge(other_agent_id=other_agent_id)
        edges[other_agent_id] = edge
    weight = 1.0 + max(0.0, emotional_impact) * 0.35
    weighted_trust = trust_delta * weight
    weighted_harm = harm_delta * weight
    edge.trust = max(-1.5, min(1.5, edge.trust + weighted_trust - weighted_harm * 0.35))
    edge.reciprocity = max(-2.5, min(2.5, edge.reciprocity + reciprocity_delta * (0.85 + max(0.0, emotional_impact) * 0.15)))
    edge.attachment = max(0.0, min(2.5, edge.attachment + attachment_delta * weight))
    edge.harm = max(0.0, min(2.5, edge.harm + weighted_harm))
    edge.positive_salience = max(0.0, min(3.0, edge.positive_salience * 0.82 + max(0.0, weighted_trust + attachment_delta) * 0.6))
    edge.negative_salience = max(0.0, min(3.0, edge.negative_salience * 0.84 + max(0.0, weighted_harm - weighted_trust) * 0.75))
    edge.emotional_weight = max(0.0, min(3.0, edge.emotional_weight * 0.8 + max(0.0, emotional_impact) * 0.65))
    edge.co_residence_score = max(0.0, min(4.0, edge.co_residence_score + co_residence_delta))
    if kin is not None:
        edge.kin = kin
    edge.last_interaction_day = day
    return edge


def decay_social_memory(edges: dict[int, SocialMemoryEdge], decay: float) -> None:
    to_delete: list[int] = []
    for other_id, edge in edges.items():
        edge.trust *= 1.0 - decay * 0.7
        edge.reciprocity *= 1.0 - decay * 0.7
        edge.attachment *= 1.0 - decay * 0.5
        edge.co_residence_score *= 1.0 - decay * 0.5
        edge.harm *= 1.0 - decay * 0.25
        edge.positive_salience *= 1.0 - decay * 0.35
        edge.negative_salience *= 1.0 - decay * 0.28
        edge.emotional_weight *= 1.0 - decay * 0.2
        if (
            abs(edge.trust) < 0.02
            and edge.attachment < 0.02
            and edge.harm < 0.02
            and edge.positive_salience < 0.02
            and edge.negative_salience < 0.02
            and edge.emotional_weight < 0.02
            and not edge.kin
        ):
            to_delete.append(other_id)
    for other_id in to_delete:
        del edges[other_id]
