from __future__ import annotations

from dataclasses import dataclass

from ..memory.social import remember_social


@dataclass(slots=True)
class AttachmentState:
    source_id: int
    target_id: int
    strength: float


def update_attachment(agent, other_id: int, day: int, gain: float, kin: bool = False) -> None:
    remember_social(agent.social_memory, other_id, day, attachment_delta=gain, kin=kin)
