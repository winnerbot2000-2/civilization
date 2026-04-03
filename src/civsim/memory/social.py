from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SocialMemoryEdge:
    other_agent_id: int
    trust: float = 0.0
    reciprocity: float = 0.0
    attachment: float = 0.0
    harm: float = 0.0
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
) -> SocialMemoryEdge:
    edge = edges.get(other_agent_id)
    if edge is None:
        edge = SocialMemoryEdge(other_agent_id=other_agent_id)
        edges[other_agent_id] = edge
    edge.trust = max(-1.0, min(1.0, edge.trust + trust_delta))
    edge.reciprocity = max(-2.0, min(2.0, edge.reciprocity + reciprocity_delta))
    edge.attachment = max(0.0, min(2.0, edge.attachment + attachment_delta))
    edge.harm = max(0.0, min(2.0, edge.harm + harm_delta))
    edge.co_residence_score = max(0.0, min(4.0, edge.co_residence_score + co_residence_delta))
    if kin is not None:
        edge.kin = kin
    edge.last_interaction_day = day
    return edge


def decay_social_memory(edges: dict[int, SocialMemoryEdge], decay: float) -> None:
    to_delete: list[int] = []
    for other_id, edge in edges.items():
        edge.trust *= 1.0 - decay
        edge.reciprocity *= 1.0 - decay
        edge.attachment *= 1.0 - decay * 0.5
        edge.co_residence_score *= 1.0 - decay * 0.5
        edge.harm *= 1.0 - decay * 0.25
        if abs(edge.trust) < 0.02 and edge.attachment < 0.02 and edge.harm < 0.02 and not edge.kin:
            to_delete.append(other_id)
    for other_id in to_delete:
        del edges[other_id]
