from __future__ import annotations

from dataclasses import dataclass, field

from ..core.config import LifeConfig
from ..learning.skills import SkillProfile
from ..life.aging import age_stage_for_days
from ..memory.episodic import Episode
from ..memory.habits import HabitBias
from ..memory.social import SocialMemoryEdge
from ..memory.spatial import SpatialMemoryEntry


@dataclass(slots=True)
class Traits:
    boldness: float
    sociability: float
    patience: float
    curiosity: float
    aggression: float
    attachment_strength: float


@dataclass(slots=True)
class Percept:
    current_patch: int
    current_water: float
    current_food: float
    current_shelter: float
    current_danger: float
    nearby_patches: list[int]
    nearby_agents: list[int]
    nearby_kin: list[int]
    caregiver_patch: int | None
    best_neighbor_for_safety: int | None
    best_visible_water_patch: int | None
    best_visible_water_value: float


@dataclass(slots=True)
class AgentState:
    agent_id: int
    sex: str
    age_days: int
    age_stage: str
    patch_id: int
    hunger: float
    thirst: float
    fatigue: float
    stress: float
    social_need: float
    previous_hunger: float
    previous_thirst: float
    previous_fatigue: float
    previous_stress: float
    previous_social_need: float
    reproductive_ready: bool
    fertility_cooldown: int
    pregnancy_days_remaining: int | None
    alive: bool
    carried_food: float
    traits: Traits
    skills: SkillProfile
    parent_ids: tuple[int, ...] = field(default_factory=tuple)
    child_ids: list[int] = field(default_factory=list)
    caregiver_id: int | None = None
    partner_id: int | None = None
    current_target_patch: int | None = None
    current_action: str = "idle"
    action_streak: int = 0
    last_patch_id: int | None = None
    spatial_memory: dict[tuple[str, int], SpatialMemoryEntry] = field(default_factory=dict)
    episodes: list[Episode] = field(default_factory=list)
    social_memory: dict[int, SocialMemoryEdge] = field(default_factory=dict)
    habits: dict[str, HabitBias] = field(default_factory=dict)


def _random_traits(rng) -> Traits:
    return Traits(
        boldness=rng.uniform(0.2, 0.8),
        sociability=rng.uniform(0.2, 0.8),
        patience=rng.uniform(0.2, 0.8),
        curiosity=rng.uniform(0.2, 0.8),
        aggression=rng.uniform(0.1, 0.7),
        attachment_strength=rng.uniform(0.2, 0.9),
    )


def _normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    low = min(values)
    high = max(values)
    span = high - low
    if span <= 1e-9:
        return [0.5 for _ in values]
    return [(value - low) / span for value in values]


def _local_water_access(world, patch_id: int) -> float:
    local_patches = (patch_id, *world.grid.neighbor_tuple(patch_id))
    return max(
        float(world.water[patch_id]) * 0.88,
        sum(float(world.water[neighbor]) for neighbor in local_patches) / len(local_patches),
    )


def _spawn_quality_scores(world) -> list[float]:
    food_capacity = [float(value) for value in world.food_capacity]
    movement_cost = [float(value) for value in world.movement_cost]
    food_norm = _normalize(food_capacity)
    movement_norm = _normalize(movement_cost)
    qualities: list[float] = []
    for patch_id in range(world.grid.size):
        local_patches = (patch_id, *world.grid.neighbor_tuple(patch_id))
        local_water = _local_water_access(world, patch_id)
        local_food = sum(food_norm[neighbor] for neighbor in local_patches) / len(local_patches)
        local_shelter = sum(float(world.shelter[neighbor]) for neighbor in local_patches) / len(local_patches)
        local_danger = sum(float(world.danger[neighbor]) for neighbor in local_patches) / len(local_patches)
        local_movement = sum(movement_norm[neighbor] for neighbor in local_patches) / len(local_patches)
        direct_wetness = max(0.0, float(world.water[patch_id]) - 0.62)
        qualities.append(
            local_water * 0.46
            + local_food * 0.24
            + local_shelter * 0.14
            + food_norm[patch_id] * 0.18
            + float(world.shelter[patch_id]) * 0.1
            - float(world.danger[patch_id]) * 0.22
            - local_danger * 0.16
            - movement_norm[patch_id] * 0.08
            - local_movement * 0.06
            - direct_wetness * 0.48
        )
    return _normalize(qualities)


def _pick_cluster_sites(world, spawn_quality: list[float], cluster_count: int, rng) -> list[int]:
    candidates = sorted(range(world.grid.size), key=lambda patch_id: spawn_quality[patch_id], reverse=True)
    candidate_limit = max(cluster_count * 8, int(world.grid.size * 0.35))
    hydrated_candidates = [
        patch_id
        for patch_id in candidates
        if (
            _local_water_access(world, patch_id) >= 0.28
            and float(world.water[patch_id]) <= 0.88
        )
    ]
    candidate_pool = (hydrated_candidates[:candidate_limit] or candidates[:candidate_limit])
    sites: list[int] = []
    min_distance = 3
    while candidate_pool and len(sites) < cluster_count:
        ranked = sorted(
            candidate_pool,
            key=lambda patch_id: spawn_quality[patch_id] + rng.uniform(-0.08, 0.08),
            reverse=True,
        )
        chosen = None
        for patch_id in ranked:
            if all(world.grid.distance(patch_id, existing) >= min_distance for existing in sites):
                chosen = patch_id
                break
        if chosen is None:
            chosen = ranked[0]
            if min_distance > 1:
                min_distance -= 1
        sites.append(chosen)
        candidate_pool.remove(chosen)
    return sites or candidates[:cluster_count]


def create_initial_agents(config, life_config: LifeConfig, world, rng) -> list[AgentState]:
    agents: list[AgentState] = []
    spawn_quality = _spawn_quality_scores(world)
    food_capacity_norm = _normalize([float(value) for value in world.food_capacity])
    cluster_count = max(4, min(world.grid.size, max(4, config.initial_population // 16)))
    cluster_sites = _pick_cluster_sites(world, spawn_quality, cluster_count, rng)
    adult_min_age = max(1, life_config.child_stage_days)
    adult_max_age = max(adult_min_age + 1, min(800, life_config.elder_stage_days - 1))
    cluster_rotation = cluster_sites[:]
    rng.shuffle(cluster_rotation)
    for agent_id in range(config.initial_population):
        home_patch = cluster_rotation[agent_id % len(cluster_rotation)]
        local_options = [home_patch, *world.grid.neighbor_tuple(home_patch)]
        local_weights = [
            max(
                0.05,
                spawn_quality[candidate_patch]
                * (1.55 if candidate_patch == home_patch else 1.0)
                + _local_water_access(world, candidate_patch) * 0.15
                + food_capacity_norm[candidate_patch] * 0.12,
            )
            - max(0.0, float(world.water[candidate_patch]) - 0.7) * 0.22
            for candidate_patch in local_options
        ]
        patch_id = rng.choices(local_options, weights=local_weights, k=1)[0]
        age_days = rng.randint(adult_min_age, adult_max_age)
        agents.append(
            AgentState(
                agent_id=agent_id,
                sex="female" if rng.random() < 0.5 else "male",
                age_days=age_days,
                age_stage=age_stage_for_days(age_days, life_config),
                patch_id=patch_id,
                hunger=rng.uniform(0.06, 0.24),
                thirst=rng.uniform(0.06, 0.24),
                fatigue=rng.uniform(0.0, 0.18),
                stress=rng.uniform(0.0, 0.12),
                social_need=rng.uniform(0.08, 0.28),
                previous_hunger=0.0,
                previous_thirst=0.0,
                previous_fatigue=0.0,
                previous_stress=0.0,
                previous_social_need=0.0,
                reproductive_ready=True,
                fertility_cooldown=rng.randint(0, 60),
                pregnancy_days_remaining=None,
                alive=True,
                carried_food=config.starting_food,
                traits=_random_traits(rng),
                skills=SkillProfile(
                    foraging=rng.uniform(0.15, 0.55),
                    navigation=rng.uniform(0.15, 0.55),
                    caregiving=rng.uniform(0.15, 0.55),
                ),
            )
        )
        agents[-1].previous_hunger = agents[-1].hunger
        agents[-1].previous_thirst = agents[-1].thirst
        agents[-1].previous_fatigue = agents[-1].fatigue
        agents[-1].previous_stress = agents[-1].stress
        agents[-1].previous_social_need = agents[-1].social_need
    return agents
