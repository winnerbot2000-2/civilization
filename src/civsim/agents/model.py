from __future__ import annotations

from dataclasses import dataclass, field

from ..learning.skills import SkillProfile
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


def create_initial_agents(config, world, rng) -> list[AgentState]:
    agents: list[AgentState] = []
    good_patches = [idx for idx, water in enumerate(world.water) if water > 0.35]
    patch_pool = good_patches or list(range(world.grid.size))
    cluster_count = max(6, min(len(patch_pool), max(6, config.initial_population // 16)))
    cluster_sites = rng.sample(patch_pool, k=cluster_count) if len(patch_pool) >= cluster_count else patch_pool
    for agent_id in range(config.initial_population):
        home_patch = cluster_sites[agent_id % len(cluster_sites)]
        local_options = [home_patch, *world.grid.neighbors(home_patch)]
        patch_id = rng.choice(local_options)
        agents.append(
            AgentState(
                agent_id=agent_id,
                sex="female" if rng.random() < 0.5 else "male",
                age_days=rng.randint(120, 800),
                age_stage="adult",
                patch_id=patch_id,
                hunger=rng.uniform(0.1, 0.4),
                thirst=rng.uniform(0.1, 0.4),
                fatigue=rng.uniform(0.0, 0.3),
                stress=rng.uniform(0.0, 0.2),
                social_need=rng.uniform(0.1, 0.4),
                reproductive_ready=True,
                fertility_cooldown=rng.randint(0, 60),
                pregnancy_days_remaining=None,
                alive=True,
                carried_food=config.starting_food,
                traits=_random_traits(rng),
                skills=SkillProfile(
                    foraging=rng.uniform(0.1, 0.5),
                    navigation=rng.uniform(0.1, 0.5),
                    caregiving=rng.uniform(0.1, 0.5),
                ),
            )
        )
    return agents
