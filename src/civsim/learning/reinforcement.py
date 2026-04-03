from __future__ import annotations

from ..memory.habits import reinforce_habit


def apply_reinforcement(habits: dict, action: str, outcome_score: float, rate: float, context_key: str | None = None) -> None:
    reinforce_habit(habits, f"action:{action}", outcome_score * rate)
    if context_key is not None:
        reinforce_habit(habits, f"{action}:{context_key}", outcome_score * rate * 0.75)
