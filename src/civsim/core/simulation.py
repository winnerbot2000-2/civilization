from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from ..agents.actions import resolve_intents
from ..agents.decision import generate_action_intent
from ..agents.model import AgentState, Traits, create_initial_agents
from ..agents.perception import build_percept
from ..analysis.detectors import detect_camps, detect_clusters
from ..events.bus import EventBus
from ..events.types import EventRecord
from ..learning.imitation import apply_imitation
from ..learning.reinforcement import apply_reinforcement
from ..learning.skills import SkillProfile, improve_skill
from ..life.aging import age_stage_for_days, daily_lifecycle_update
from ..life.reproduction import attempt_conception, resolve_births
from ..materials.hearths import decay_hearths, strengthen_hearths
from ..materials.traces import decay_paths
from ..memory.habits import decay_habits
from ..memory.social import decay_social_memory, remember_social
from ..memory.spatial import decay_spatial_memory, remember_site
from ..metrics.collector import MetricsCollector
from ..social.relationships import update_co_residence
from ..world.layers import generate_world
from ..world.seasons import apply_daily_world_update
from .clock import SimulationClock
from .config import SimulationConfig
from .rng import SeedRegistry


@dataclass(slots=True)
class RunSummary:
    seed: int
    days: int
    final_population: int
    child_survival_rate: float
    hearth_count: int
    path_count: int
    mean_trust: float
    mean_remembered_sites: float
    sharing_events: int


@dataclass(slots=True)
class SimulationState:
    config: SimulationConfig
    rng: SeedRegistry
    clock: SimulationClock
    world: object
    agents: list[AgentState]
    agents_by_id: dict[int, AgentState]
    event_bus: EventBus
    metrics: MetricsCollector
    birth_count: int = 0
    child_count_total: int = 0
    child_death_count: int = 0

    def create_agent(
        self,
        agent_id: int,
        patch_id: int,
        sex: str,
        age_days: int,
        trait_overrides: dict[str, float] | None = None,
        caregiver_id: int | None = None,
        parent_ids: tuple[int, ...] = (),
    ) -> AgentState:
        rng = self.rng.python(f"agent:{agent_id}")
        traits_payload = trait_overrides or {
            "boldness": rng.uniform(0.2, 0.8),
            "sociability": rng.uniform(0.2, 0.8),
            "patience": rng.uniform(0.2, 0.8),
            "curiosity": rng.uniform(0.2, 0.8),
            "aggression": rng.uniform(0.1, 0.7),
            "attachment_strength": rng.uniform(0.2, 0.9),
        }
        return AgentState(
            agent_id=agent_id,
            sex=sex,
            age_days=age_days,
            age_stage=age_stage_for_days(age_days, self.config.life),
            patch_id=patch_id,
            hunger=0.2,
            thirst=0.2,
            fatigue=0.1,
            stress=0.0,
            social_need=0.1,
            previous_hunger=0.2,
            previous_thirst=0.2,
            previous_fatigue=0.1,
            previous_stress=0.0,
            previous_social_need=0.1,
            reproductive_ready=True,
            fertility_cooldown=0,
            pregnancy_days_remaining=None,
            alive=True,
            carried_food=0.2,
            traits=Traits(**traits_payload),
            skills=SkillProfile(),
            parent_ids=parent_ids,
            caregiver_id=caregiver_id,
        )


def _seed_social_structure(state: SimulationState) -> None:
    rng = state.rng.python("initial-social")
    adults = [agent for agent in state.agents if agent.age_stage == "adult"]
    females = [agent for agent in adults if agent.sex == "female"]
    males = [agent for agent in adults if agent.sex == "male"]
    rng.shuffle(females)
    rng.shuffle(males)
    available_males = males[:]
    for female in females:
        if not available_males:
            break
        male = min(available_males, key=lambda candidate: state.world.grid.distance(female.patch_id, candidate.patch_id))
        if state.world.grid.distance(female.patch_id, male.patch_id) > 2:
            continue
        available_males.remove(male)
        female.partner_id = male.agent_id
        male.partner_id = female.agent_id
        male.patch_id = female.patch_id
        remember_social(female.social_memory, male.agent_id, 0, trust_delta=0.2, attachment_delta=0.35)
        remember_social(male.social_memory, female.agent_id, 0, trust_delta=0.2, attachment_delta=0.35)

    next_id = max(agent.agent_id for agent in state.agents) + 1
    for _ in range(min(state.config.agents.initial_children, len(adults) // 2)):
        mother = rng.choice(females or adults)
        if mother.partner_id is None:
            continue
        father = state.agents_by_id[mother.partner_id]
        child = state.create_agent(
            agent_id=next_id,
            patch_id=mother.patch_id,
            sex="female" if rng.random() < 0.5 else "male",
            age_days=rng.randint(0, max(1, state.config.life.child_stage_days - 10)),
            caregiver_id=mother.agent_id,
            parent_ids=(mother.agent_id, father.agent_id),
        )
        child.age_stage = "child"
        mother.child_ids.append(child.agent_id)
        father.child_ids.append(child.agent_id)
        remember_social(child.social_memory, mother.agent_id, 0, attachment_delta=0.7, trust_delta=0.3, kin=True)
        remember_social(child.social_memory, father.agent_id, 0, attachment_delta=0.3, trust_delta=0.2, kin=True)
        remember_social(mother.social_memory, child.agent_id, 0, attachment_delta=0.8, trust_delta=0.3, kin=True)
        remember_social(father.social_memory, child.agent_id, 0, attachment_delta=0.5, trust_delta=0.2, kin=True)
        state.agents.append(child)
        state.agents_by_id[child.agent_id] = child
        next_id += 1


def initialize_simulation(config: SimulationConfig, seed: int | None = None) -> SimulationState:
    run_seed = config.run.seed if seed is None else seed
    rng = SeedRegistry(run_seed)
    world = generate_world(config.world, rng.numpy("world"))
    agents = create_initial_agents(config.agents, config.life, world, rng.python("agents"))
    agents_by_id = {agent.agent_id: agent for agent in agents}
    state = SimulationState(
        config=config,
        rng=rng,
        clock=SimulationClock(ticks_per_day=config.world.ticks_per_day, season_length_days=config.world.season_length_days),
        world=world,
        agents=agents,
        agents_by_id=agents_by_id,
        event_bus=EventBus(config.events.record_limit),
        metrics=MetricsCollector(),
    )
    _seed_social_structure(state)
    state.child_count_total = sum(1 for agent in state.agents if agent.age_stage == "child")
    for agent in state.agents:
        _encode_local_patch_memory(state, agent)
    refresh_occupancy(state)
    return state


def refresh_occupancy(state: SimulationState) -> None:
    state.world.occupancy = {}
    for agent in state.agents:
        if agent.alive:
            state.world.occupancy.setdefault(agent.patch_id, []).append(agent.agent_id)


def decay_spatial_memory_all(state: SimulationState) -> None:
    for agent in state.agents:
        if agent.alive:
            decay_spatial_memory(agent.spatial_memory, state.config.memory.spatial_decay)


def decay_social_memory_all(state: SimulationState) -> None:
    for agent in state.agents:
        if agent.alive:
            decay_social_memory(agent.social_memory, state.config.memory.social_decay)


def decay_habits_all(state: SimulationState) -> None:
    for agent in state.agents:
        if agent.alive:
            decay_habits(agent.habits, state.config.memory.habit_decay)


def daily_pass(state: SimulationState) -> None:
    decay_spatial_memory_all(state)
    decay_social_memory_all(state)
    decay_habits_all(state)
    apply_daily_world_update(state.world.food, state.world.food_capacity, state.clock, state.config.world)
    decay_hearths(state.world, state.config.materials.hearth_decay)
    decay_paths(state.world, state.config.world.path_decay)
    for patch_agents in state.world.occupancy.values():
        if len(patch_agents) > 1:
            update_co_residence(state.agents_by_id, patch_agents, state.clock.day, state.config.social.co_residence_gain)

    for agent in list(state.agents):
        if not agent.alive:
            continue
        rng = state.rng.python(f"aging:{agent.agent_id}:{state.clock.day}")
        if not daily_lifecycle_update(agent, state.config.life, rng):
            agent.alive = False
            if agent.age_stage == "child":
                state.child_death_count += 1
            state.event_bus.emit(EventRecord(tick=state.clock.tick, day=state.clock.day, kind="death", agent_id=agent.agent_id, patch_id=agent.patch_id))

    alive_agents = [agent for agent in state.agents if agent.alive]
    for agent in alive_agents:
        if agent.age_stage == "adult" and agent.partner_id is not None:
            partner = state.agents_by_id.get(agent.partner_id)
            if partner is not None and partner.alive:
                attempt_conception(agent, partner, state.config.life, state.clock, state.rng.python(f"repro:{agent.agent_id}:{state.clock.day}"), state.event_bus)

    newborns = resolve_births(state, state.config.life, state.clock, state.rng.python(f"births:{state.clock.day}"), state.event_bus)
    state.birth_count += len(newborns)
    state.child_count_total += len(newborns)
    refresh_occupancy(state)
    if state.clock.day % state.config.metrics.sample_every_days == 0:
        state.metrics.sample(state, state.clock.day)


def run_tick(state: SimulationState) -> None:
    refresh_occupancy(state)
    intents = {}
    outcomes = {}
    for agent in state.agents:
        if not agent.alive:
            continue
        _encode_local_patch_memory(state, agent)
        percept = build_percept(agent, state.world, state.agents_by_id, state.config.agents.perception_radius)
        intent = generate_action_intent(
            agent=agent,
            percept=percept,
            world=state.world,
            agents_by_id=state.agents_by_id,
            clock=state.clock,
            config=state.config,
            rng=state.rng.python(f"decision:{agent.agent_id}:{state.clock.tick}"),
        )
        intents[agent.agent_id] = intent
    outcomes = resolve_intents(state, intents, state.clock)
    refresh_occupancy(state)

    for agent_id, outcome in outcomes.items():
        state.metrics.record_action(outcome.action)
        agent = state.agents_by_id[agent_id]
        apply_reinforcement(
            agent.habits,
            action=outcome.action,
            outcome_score=outcome.outcome_score if outcome.success else -0.2,
            rate=state.config.learning.reinforcement_rate,
            context_key=state.clock.season_name,
            previous_action=outcome.previous_action,
        )
        if outcome.action == "forage" and outcome.success:
            improve_skill(agent.skills, "foraging", state.config.learning.skill_gain_rate)
        elif outcome.action in {"move_local", "move_to_known_site", "follow_caregiver", "explore"} and outcome.success:
            improve_skill(agent.skills, "navigation", state.config.learning.skill_gain_rate)
        elif outcome.action in {"care_for_child", "share_food"} and outcome.success:
            improve_skill(agent.skills, "caregiving", state.config.learning.skill_gain_rate)

    recent_actions = {agent_id: (outcome.action, outcome.success) for agent_id, outcome in outcomes.items()}
    for agent in state.agents:
        if not agent.alive:
            continue
        visible = [state.agents_by_id[other_id] for other_id in state.world.occupancy.get(agent.patch_id, []) if other_id != agent.agent_id and state.agents_by_id[other_id].alive]
        apply_imitation(agent, visible, recent_actions, state.config.learning.imitation_rate, state.config.learning.child_observation_bonus)

    if state.clock.is_night:
        strengthen_hearths(state.world, state.agents, state.clock, state.config.materials, state.event_bus)
    if state.clock.tick_in_day == state.config.world.ticks_per_day - 1:
        daily_pass(state)
    state.clock.advance()


def _encode_local_patch_memory(state: SimulationState, agent: AgentState) -> None:
    patch_id = agent.patch_id
    if state.world.water[patch_id] > 0.25:
        remember_site(
            agent.spatial_memory,
            "water",
            patch_id,
            payoff=float(state.world.water[patch_id]),
            risk=float(state.world.danger[patch_id]),
            day=state.clock.day,
            max_entries=state.config.memory.max_spatial_entries,
            emotional_impact=agent.thirst * 0.12,
            revisit_delta=max(0.0, float(state.world.water[patch_id]) - 0.35) * 0.05,
        )
    if state.world.food[patch_id] > 0.3:
        remember_site(
            agent.spatial_memory,
            "food",
            patch_id,
            payoff=float(state.world.food[patch_id]),
            risk=float(state.world.danger[patch_id]),
            day=state.clock.day,
            max_entries=state.config.memory.max_spatial_entries,
            emotional_impact=agent.hunger * 0.1,
            revisit_delta=max(0.0, float(state.world.food[patch_id]) - 0.3) * 0.04,
        )
    shelter_payoff = float(state.world.shelter[patch_id])
    site = state.world.site_markers.get(patch_id)
    if site is not None:
        shelter_payoff += site.hearth_intensity * state.config.world.camp_shelter_bonus + min(site.communal_food, 1.0) * 0.1
    if shelter_payoff > 0.25:
        remember_site(
            agent.spatial_memory,
            "shelter",
            patch_id,
            payoff=shelter_payoff,
            risk=float(state.world.danger[patch_id]),
            day=state.clock.day,
            max_entries=state.config.memory.max_spatial_entries,
            emotional_impact=(agent.fatigue + agent.stress) * 0.08,
            revisit_delta=max(0.0, shelter_payoff - 0.25) * 0.05,
        )
    if state.world.danger[patch_id] > 0.45:
        remember_site(
            agent.spatial_memory,
            "danger",
            patch_id,
            payoff=0.0,
            risk=float(state.world.danger[patch_id]),
            day=state.clock.day,
            max_entries=state.config.memory.max_spatial_entries,
            emotional_impact=agent.stress * 0.15,
            avoidance_delta=float(state.world.danger[patch_id]) * 0.08,
        )


def run_simulation(config: SimulationConfig, seed: int | None = None, days: int | None = None) -> tuple[SimulationState, RunSummary]:
    state = initialize_simulation(config, seed=seed)
    target_days = config.run.days if days is None else days
    total_ticks = target_days * config.world.ticks_per_day
    while state.clock.tick < total_ticks and any(agent.alive for agent in state.agents):
        run_tick(state)
    summary = build_summary(state, seed or config.run.seed, target_days)
    return state, summary


def build_summary(state: SimulationState, seed: int, days: int) -> RunSummary:
    alive = [agent for agent in state.agents if agent.alive]
    edges = [edge for agent in alive for edge in agent.social_memory.values()]
    mean_remembered_sites = sum(len(agent.spatial_memory) for agent in alive) / max(1, len(alive))
    child_survival_rate = 1.0 - (state.child_death_count / max(1, state.child_count_total))
    return RunSummary(
        seed=seed,
        days=days,
        final_population=len(alive),
        child_survival_rate=max(0.0, min(1.0, child_survival_rate)),
        hearth_count=sum(1 for site in state.world.site_markers.values() if site.hearth_intensity > 0.2),
        path_count=len(state.world.path_traces),
        mean_trust=(sum(edge.trust for edge in edges) / len(edges)) if edges else 0.0,
        mean_remembered_sites=mean_remembered_sites,
        sharing_events=state.metrics.sharing_events,
    )


def export_run(state: SimulationState, summary: RunSummary, out_dir: str | Path) -> Path:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    with (out_path / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(asdict(summary), handle, indent=2, sort_keys=True)
    with (out_path / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump([asdict(sample) for sample in state.metrics.samples], handle, indent=2, sort_keys=True)
    state.event_bus.to_jsonl(out_path / "events.jsonl")

    snapshot = {
        "clock": {"tick": state.clock.tick, "day": state.clock.day, "season": state.clock.season_name},
        "world": {
            "width": state.world.grid.width,
            "height": state.world.grid.height,
            "water": [round(float(value), 3) for value in state.world.water.tolist()],
            "food": [round(float(value), 3) for value in state.world.food.tolist()],
            "shelter": [round(float(value), 3) for value in state.world.shelter.tolist()],
            "danger": [round(float(value), 3) for value in state.world.danger.tolist()],
        },
        "agents": [
            {
                "agent_id": agent.agent_id,
                "alive": agent.alive,
                "age_stage": agent.age_stage,
                "patch_id": agent.patch_id,
                "hunger": round(agent.hunger, 3),
                "thirst": round(agent.thirst, 3),
                "fatigue": round(agent.fatigue, 3),
                "stress": round(agent.stress, 3),
                "social_need": round(agent.social_need, 3),
                "carried_food": round(agent.carried_food, 3),
                "caregiver_id": agent.caregiver_id,
                "child_ids": list(agent.child_ids),
                "current_action": agent.current_action,
            }
            for agent in state.agents
        ],
        "camps": [asdict(camp) for camp in detect_camps(state.world)],
        "clusters": [asdict(cluster) for cluster in detect_clusters(state)],
    }
    with (out_path / "snapshot.json").open("w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, indent=2, sort_keys=True)
    return out_path
