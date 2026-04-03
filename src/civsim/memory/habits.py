from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class HabitBias:
    key: str
    strength: float


def habit_bias(habits: dict[str, HabitBias], key: str) -> float:
    entry = habits.get(key)
    if entry is None:
        return 0.0
    return entry.strength


def reinforce_habit(habits: dict[str, HabitBias], key: str, delta: float) -> None:
    entry = habits.get(key)
    if entry is None:
        habits[key] = HabitBias(key=key, strength=delta)
    else:
        entry.strength = max(-1.0, min(2.5, entry.strength + delta))


def transition_key(previous_action: str, action: str) -> str:
    return f"sequence:{previous_action}->{action}"


def transition_bias(habits: dict[str, HabitBias], previous_action: str | None, action: str) -> float:
    if previous_action is None:
        return 0.0
    return habit_bias(habits, transition_key(previous_action, action))


def reinforce_transition(habits: dict[str, HabitBias], previous_action: str | None, action: str, delta: float) -> None:
    if previous_action is None:
        return
    reinforce_habit(habits, transition_key(previous_action, action), delta)


def decay_habits(habits: dict[str, HabitBias], decay: float) -> None:
    to_delete: list[str] = []
    for key, entry in habits.items():
        entry.strength *= 1.0 - decay
        if abs(entry.strength) < 0.02:
            to_delete.append(key)
    for key in to_delete:
        del habits[key]
