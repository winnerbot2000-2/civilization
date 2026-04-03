from __future__ import annotations

from ..memory.social import SocialMemoryEdge, remember_social

RelationshipEdge = SocialMemoryEdge


def update_co_residence(agents_by_id: dict[int, object], occupants: list[int], day: int, gain: float) -> None:
    for idx, agent_id in enumerate(occupants):
        agent = agents_by_id[agent_id]
        for other_id in occupants[idx + 1 :]:
            other = agents_by_id[other_id]
            kin = other_id in agent.parent_ids or other_id in agent.child_ids or agent_id in other.parent_ids or agent_id in other.child_ids
            trust_gain = gain * (0.18 if not kin else 0.3)
            attachment_gain = gain * (0.7 if not kin else 1.15)
            co_residence_gain = gain * (1.0 if not kin else 1.2)
            emotional_impact = 0.2 + co_residence_gain + (0.3 if kin else 0.0)
            remember_social(
                agent.social_memory,
                other_id,
                day,
                trust_delta=trust_gain,
                attachment_delta=attachment_gain,
                co_residence_delta=co_residence_gain,
                kin=kin,
                emotional_impact=emotional_impact,
            )
            remember_social(
                other.social_memory,
                agent_id,
                day,
                trust_delta=trust_gain,
                attachment_delta=attachment_gain,
                co_residence_delta=co_residence_gain,
                kin=kin,
                emotional_impact=emotional_impact,
            )
