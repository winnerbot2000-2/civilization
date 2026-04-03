from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(slots=True)
class RunConfig:
    days: int = 365
    seed: int = 42


@dataclass(slots=True)
class WorldConfig:
    width: int = 32
    height: int = 20
    ticks_per_day: int = 4
    season_length_days: int = 60
    water_source_count: int = 5
    danger_source_count: int = 5
    water_access_exponent: float = 1.7
    danger_exponent: float = 1.35
    shelter_exponent: float = 1.25
    movement_cost_min: float = 0.85
    movement_cost_max: float = 3.4
    food_regrowth_good: float = 0.09
    food_regrowth_bad: float = 0.03
    good_season_food_multiplier: float = 1.12
    bad_season_food_multiplier: float = 0.48
    bad_season_food_decay: float = 0.03
    dry_patch_thirst_penalty: float = 0.03
    night_exposure_fatigue: float = 0.06
    night_exposure_stress: float = 0.035
    danger_fatigue_scale: float = 0.05
    danger_stress_scale: float = 0.16
    site_decay: float = 0.01
    path_decay: float = 0.005
    camp_shelter_bonus: float = 0.15


@dataclass(slots=True)
class AgentsConfig:
    initial_population: int = 120
    initial_children: int = 24
    perception_radius: int = 1
    starting_food: float = 1.2
    max_carried_food: float = 4.0
    hunger_rate: float = 0.08
    thirst_rate: float = 0.12
    fatigue_rate: float = 0.05
    social_need_rate: float = 0.03
    stress_recovery: float = 0.04
    base_food_yield: float = 0.65
    base_water_relief: float = 0.75
    rest_recovery: float = 0.18


@dataclass(slots=True)
class MemoryConfig:
    max_spatial_entries: int = 16
    max_episodes: int = 12
    spatial_decay: float = 0.004
    social_decay: float = 0.002
    habit_decay: float = 0.002
    salience_threshold: float = 0.25


@dataclass(slots=True)
class LearningConfig:
    reinforcement_rate: float = 0.12
    imitation_rate: float = 0.04
    skill_gain_rate: float = 0.02
    child_observation_bonus: float = 0.02


@dataclass(slots=True)
class DecisionConfig:
    noise_scale: float = 0.14
    attention_patch_limit: int = 4
    attention_action_limit: int = 8
    trend_weight: float = 1.1
    inertia_bonus: float = 0.28
    inertia_switch_margin: float = 0.22
    fallback_threshold: float = 0.3
    uncertainty_margin: float = 0.18


@dataclass(slots=True)
class SocialConfig:
    share_threshold: float = 1.4
    share_amount: float = 0.6
    trust_gain: float = 0.08
    trust_loss: float = 0.18
    attachment_gain: float = 0.04
    co_residence_gain: float = 0.03
    theft_stress: float = 0.12
    kin_preference_bias: float = 0.65
    familiar_preference_bias: float = 0.28
    reciprocity_bias: float = 0.24
    avoidance_bias: float = 0.48
    caregiver_priority_bias: float = 0.75


@dataclass(slots=True)
class LifeConfig:
    child_stage_days: int = 240
    elder_stage_days: int = 2400
    max_age_days: int = 3600
    gestation_days: int = 80
    fertility_cooldown_days: int = 120
    base_conception_chance: float = 0.02
    child_hunger_penalty: float = 0.02
    mutation_sigma: float = 0.08


@dataclass(slots=True)
class MaterialsConfig:
    hearth_creation_threshold: int = 2
    hearth_strength_gain: float = 0.18
    hearth_decay: float = 0.004
    site_store_capacity: float = 12.0
    path_strength_gain: float = 0.06


@dataclass(slots=True)
class MetricsConfig:
    sample_every_days: int = 1


@dataclass(slots=True)
class EventsConfig:
    record_limit: int = 200_000


@dataclass(slots=True)
class SimulationConfig:
    run: RunConfig
    world: WorldConfig
    agents: AgentsConfig
    memory: MemoryConfig
    learning: LearningConfig
    decision: DecisionConfig
    social: SocialConfig
    life: LifeConfig
    materials: MaterialsConfig
    metrics: MetricsConfig
    events: EventsConfig


def _section(data: dict, name: str, cls):
    payload = dict(data.get(name, {}))
    return cls(**payload)


def load_config(path: str | Path) -> SimulationConfig:
    with Path(path).open("rb") as handle:
        data = tomllib.load(handle)
    return SimulationConfig(
        run=_section(data, "run", RunConfig),
        world=_section(data, "world", WorldConfig),
        agents=_section(data, "agents", AgentsConfig),
        memory=_section(data, "memory", MemoryConfig),
        learning=_section(data, "learning", LearningConfig),
        decision=_section(data, "decision", DecisionConfig),
        social=_section(data, "social", SocialConfig),
        life=_section(data, "life", LifeConfig),
        materials=_section(data, "materials", MaterialsConfig),
        metrics=_section(data, "metrics", MetricsConfig),
        events=_section(data, "events", EventsConfig),
    )
