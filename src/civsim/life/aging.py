from __future__ import annotations

from ..core.config import LifeConfig


def age_stage_for_days(age_days: int, config: LifeConfig) -> str:
    if age_days < config.child_stage_days:
        return "child"
    if age_days >= config.elder_stage_days:
        return "elder"
    return "adult"


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
