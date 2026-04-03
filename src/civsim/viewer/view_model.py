from __future__ import annotations

from dataclasses import dataclass

from ..analysis.detectors import detect_camps


@dataclass(slots=True)
class MetricsSnapshot:
    day: int
    season: str
    living_population: int
    living_children: int
    living_elders: int
    active_camps: int
    mean_co_residence: float
    sharing_events: int
    child_survival_rate: float
    child_survival_trend: str
    site_reuse_frequency: float
    path_count: int
    recent_event_count: int


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def child_survival_rate(state) -> float:
    total = max(1, state.child_count_total)
    return _clamp(1.0 - (state.child_death_count / total), 0.0, 1.0)


def child_survival_trend(state) -> str:
    samples = state.metrics.samples[-5:]
    if len(samples) < 2:
        return "stable"
    start = samples[0].living_children
    end = samples[-1].living_children
    delta = end - start
    if delta >= 2:
        return "rising"
    if delta <= -2:
        return "falling"
    return "stable"


def mean_co_residence(state) -> float:
    living = [agent for agent in state.agents if agent.alive]
    edges = [edge for agent in living for edge in agent.social_memory.values()]
    if not edges:
        return 0.0
    return sum(edge.co_residence_score for edge in edges) / len(edges)


def site_reuse_frequency(state) -> float:
    camps = detect_camps(state.world)
    if not camps:
        return 0.0
    return sum(camp.visit_count for camp in camps) / len(camps)


def build_metrics_snapshot(state, recent_event_count: int) -> MetricsSnapshot:
    living = [agent for agent in state.agents if agent.alive]
    camps = detect_camps(state.world)
    return MetricsSnapshot(
        day=state.clock.day,
        season=state.clock.season_name,
        living_population=len(living),
        living_children=sum(1 for agent in living if agent.age_stage == "child"),
        living_elders=sum(1 for agent in living if agent.age_stage == "elder"),
        active_camps=len(camps),
        mean_co_residence=mean_co_residence(state),
        sharing_events=state.metrics.sharing_events,
        child_survival_rate=child_survival_rate(state),
        child_survival_trend=child_survival_trend(state),
        site_reuse_frequency=site_reuse_frequency(state),
        path_count=len(state.world.path_traces),
        recent_event_count=recent_event_count,
    )


def format_event(record) -> str:
    if record.kind == "birth":
        return f"Day {record.day}: birth near patch {record.patch_id}"
    if record.kind == "death":
        return f"Day {record.day}: death at patch {record.patch_id}"
    if record.kind == "conception":
        return f"Day {record.day}: conception pair {record.agent_id}/{record.other_agent_id}"
    if record.kind == "hearth_formed":
        return f"Day {record.day}: hearth formed at patch {record.patch_id}"
    if record.kind == "camp_reused":
        return f"Day {record.day}: camp reused at patch {record.patch_id}"
    if record.kind == "trust_bond_formed":
        return f"Day {record.day}: trust formed {record.agent_id}->{record.other_agent_id}"
    if record.kind == "trust_bond_collapsed":
        return f"Day {record.day}: trust collapsed {record.agent_id}->{record.other_agent_id}"
    if record.kind.startswith("action_"):
        action = record.kind.removeprefix("action_").replace("_", " ")
        if record.other_agent_id is not None:
            return f"Day {record.day}: {action} with {record.other_agent_id}"
        if record.patch_id is not None:
            return f"Day {record.day}: {action} at patch {record.patch_id}"
        return f"Day {record.day}: {action}"
    return f"Day {record.day}: {record.kind}"


def recent_event_lines(state, limit: int = 14) -> list[str]:
    interesting = {
        "birth",
        "death",
        "conception",
        "hearth_formed",
        "camp_reused",
        "trust_bond_formed",
        "trust_bond_collapsed",
        "action_share_food",
        "action_care_for_child",
        "action_follow_caregiver",
        "action_take_food_from_site",
    }
    records = [record for record in state.event_bus.records if record.kind in interesting or record.kind.startswith("action_")]
    return [format_event(record) for record in records[-limit:]]


def selected_agent_lines(state, agent_id: int | None, limit: int = 5) -> list[str]:
    if agent_id is None or agent_id not in state.agents_by_id:
        return ["No agent selected.", "Click an agent marker on the map."]

    agent = state.agents_by_id[agent_id]
    lines = [
        f"Agent {agent.agent_id} ({agent.age_stage}, {'alive' if agent.alive else 'dead'})",
        f"Patch {agent.patch_id}  action={agent.current_action}",
        f"H={agent.hunger:.2f} T={agent.thirst:.2f} F={agent.fatigue:.2f} S={agent.stress:.2f}",
        f"Social={agent.social_need:.2f} Food={agent.carried_food:.2f}",
        f"Traits b={agent.traits.boldness:.2f} soc={agent.traits.sociability:.2f} pat={agent.traits.patience:.2f}",
        f"Traits cur={agent.traits.curiosity:.2f} agg={agent.traits.aggression:.2f} att={agent.traits.attachment_strength:.2f}",
        f"Skills forage={agent.skills.foraging:.2f} nav={agent.skills.navigation:.2f} care={agent.skills.caregiving:.2f}",
        f"Caregiver={agent.caregiver_id}  children={len(agent.child_ids)}  parents={list(agent.parent_ids)}",
        "Recent site memories:",
    ]

    memory_entries = sorted(
        agent.spatial_memory.values(),
        key=lambda entry: entry.revisit_bias + entry.payoff + entry.avoidance_bias + entry.risk,
        reverse=True,
    )[:limit]
    if not memory_entries:
        lines.append("  none")
    else:
        for entry in memory_entries:
            lines.append(
                f"  {entry.kind}@{entry.patch_id} pay={entry.payoff:.2f} rev={entry.revisit_bias:.2f} avoid={entry.avoidance_bias:.2f}"
            )

    lines.append("Recent episodes:")
    episodes = sorted(agent.episodes, key=lambda episode: episode.salience, reverse=True)[:limit]
    if not episodes:
        lines.append("  none")
    else:
        for episode in episodes:
            lines.append(f"  {episode.kind}@{episode.patch_id} sal={episode.salience:.2f} out={episode.outcome:.2f}")

    lines.append("Social ties:")
    social_edges = sorted(
        agent.social_memory.values(),
        key=lambda edge: abs(edge.trust) + edge.attachment + edge.harm + edge.co_residence_score,
        reverse=True,
    )[:limit]
    if not social_edges:
        lines.append("  none")
    else:
        for edge in social_edges:
            lines.append(
                f"  {edge.other_agent_id} trust={edge.trust:.2f} rec={edge.reciprocity:.2f} harm={edge.harm:.2f} co={edge.co_residence_score:.2f}"
            )
    return lines
