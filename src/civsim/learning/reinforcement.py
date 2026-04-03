from __future__ import annotations

from ..memory.habits import reinforce_habit, reinforce_transition


def apply_reinforcement(
    habits: dict,
    action: str,
    outcome_score: float,
    rate: float,
    context_key: str | None = None,
    previous_action: str | None = None,
) -> None:
    delta = outcome_score * rate
    reinforce_habit(habits, f"action:{action}", delta)
    if context_key is not None:
        reinforce_habit(habits, f"{action}:{context_key}", delta * 0.75)
    reinforce_transition(habits, previous_action, action, delta * 0.85)
