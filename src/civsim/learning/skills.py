from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SkillProfile:
    foraging: float = 0.0
    navigation: float = 0.0
    caregiving: float = 0.0


def improve_skill(skills: SkillProfile, name: str, amount: float) -> None:
    current = getattr(skills, name)
    setattr(skills, name, max(0.0, min(2.0, current + amount)))
