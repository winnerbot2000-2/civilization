from __future__ import annotations

from ..core.config import LifeConfig


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def age_stage_for_days(age_days: int, config: LifeConfig) -> str:
    if age_days < config.child_stage_days:
        return "child"
    if age_days >= config.elder_stage_days:
        return "elder"
    return "adult"


def elder_progress(age_days: int, config: LifeConfig) -> float:
    if age_days <= config.elder_stage_days:
        return 0.0
    span = max(1, config.max_age_days - config.elder_stage_days)
    return _clamp((age_days - config.elder_stage_days) / span)


def slowdown_progress(age_days: int, config: LifeConfig) -> float:
    adult_span = max(1, config.elder_stage_days - config.child_stage_days)
    slowdown_start = config.child_stage_days + int(adult_span * 0.35)
    if age_days <= slowdown_start:
        return 0.0
    span = max(1, config.max_age_days - slowdown_start)
    return _clamp((age_days - slowdown_start) / span)


def age_mobility_factor(agent, config: LifeConfig) -> float:
    progress = slowdown_progress(agent.age_days, config)
    return 1.0 - progress * (1.0 - config.elder_mobility_floor)


def age_work_factor(agent, config: LifeConfig) -> float:
    progress = slowdown_progress(agent.age_days, config)
    return 1.0 - progress * (1.0 - config.elder_work_floor)


def daily_lifecycle_update(agent, config: LifeConfig, rng) -> bool:
    agent.age_days += 1
    agent.age_stage = age_stage_for_days(agent.age_days, config)
    if agent.fertility_cooldown > 0:
        agent.fertility_cooldown -= 1
    if agent.pregnancy_days_remaining is not None:
        agent.pregnancy_days_remaining -= 1
    if agent.age_days > config.max_age_days:
        return False
    if agent.hunger >= 2.0 or agent.thirst >= 2.0 or agent.fatigue >= 2.2:
        return False
    if agent.age_stage == "elder":
        death_risk = max(0.0, (agent.age_days - config.elder_stage_days) / max(1, config.max_age_days - config.elder_stage_days))
        if rng.random() < death_risk * 0.005:
            return False
    return True
