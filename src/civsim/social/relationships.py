from __future__ import annotations

from ..memory.social import SocialMemoryEdge, remember_social

RelationshipEdge = SocialMemoryEdge


def update_co_residence(agents_by_id: dict[int, object], occupants: list[int], day: int, gain: float) -> None:
    for idx, agent_id in enumerate(occupants):
        agent = agents_by_id[agent_id]
        for other_id in occupants[idx + 1 :]:
            other = agents_by_id[other_id]
            kin = other_id in agent.parent_ids or other_id in agent.child_ids or agent_id in other.parent_ids or agent_id in other.child_ids
            trust_gain = gain * 0.15 if not kin else gain * 0.2
            remember_social(agent.social_memory, other_id, day, trust_delta=trust_gain, attachment_delta=gain, co_residence_delta=gain, kin=kin)
            remember_social(other.social_memory, agent_id, day, trust_delta=trust_gain, attachment_delta=gain, co_residence_delta=gain, kin=kin)
