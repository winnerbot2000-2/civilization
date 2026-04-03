from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from .detectors import detect_camps, detect_clusters


def simulated_days(state) -> int:
    ticks_per_day = max(1, state.config.world.ticks_per_day)
    return max(1, (state.clock.tick + ticks_per_day - 1) // ticks_per_day)


def _cause_proxy(agent) -> str:
    return max(
        (("hunger", agent.hunger), ("thirst", agent.thirst), ("fatigue", agent.fatigue)),
        key=lambda item: item[1],
    )[0]


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _stage_counts(agents) -> dict[str, int]:
    counts = Counter(agent.age_stage for agent in agents)
    return {"child": counts.get("child", 0), "adult": counts.get("adult", 0), "elder": counts.get("elder", 0)}


def _event_counts(state) -> Counter[str]:
    return Counter(record.kind for record in state.event_bus.records)


def _daily_event_lines(state, limit: int = 18) -> list[str]:
    daily = defaultdict(Counter)
    interesting_prefixes = ("action_share_food", "action_care_for_child", "action_follow_caregiver")
    interesting = {
        "birth",
        "death",
        "conception",
        "hearth_formed",
        "camp_reused",
        "trust_bond_formed",
        "trust_bond_collapsed",
    }
    for record in state.event_bus.records:
        if record.kind in interesting or record.kind.startswith(interesting_prefixes):
            daily[record.day][record.kind] += 1

    lines: list[str] = []
    for day in sorted(daily):
        counts = daily[day]
        parts: list[str] = []
        for kind in (
            "birth",
            "death",
            "hearth_formed",
            "camp_reused",
            "trust_bond_formed",
            "trust_bond_collapsed",
            "action_share_food",
            "action_care_for_child",
            "action_follow_caregiver",
        ):
            if counts.get(kind, 0) > 0:
                label = kind.removeprefix("action_").replace("_", " ")
                parts.append(f"{label} x{counts[kind]}")
        if parts:
            lines.append(f"- Day {day}: " + ", ".join(parts))
    return lines[:limit]


def _sample_timeline_lines(state, limit: int = 12) -> list[str]:
    samples = state.metrics.samples
    if not samples:
        return ["- No metric samples recorded."]
    if len(samples) <= limit:
        picked = samples
    else:
        step = max(1, len(samples) // limit)
        picked = samples[::step][:limit]
        if picked[-1].day != samples[-1].day:
            picked[-1] = samples[-1]
    return [
        (
            f"- Day {sample.day}: living={sample.living_agents}, children={sample.living_children}, "
            f"hearths={sample.hearth_count}, sharing={sample.sharing_events}, "
            f"remembered_sites={sample.remembered_sites:.2f}, paths={sample.path_count}"
        )
        for sample in picked
    ]


def _top_action_lines(state, limit: int = 10) -> list[str]:
    counts = sorted(state.metrics.action_counts.items(), key=lambda item: item[1], reverse=True)
    if not counts:
        return ["- No actions recorded."]
    return [f"- {action}: {count}" for action, count in counts[:limit]]


def _top_event_lines(state, limit: int = 12) -> list[str]:
    counts = _event_counts(state).most_common(limit)
    if not counts:
        return ["- No events recorded."]
    return [f"- {kind}: {count}" for kind, count in counts]


def _top_camp_lines(state, limit: int = 8) -> list[str]:
    camps = detect_camps(state.world)
    if not camps:
        return ["- No recurring camp-like sites detected."]
    return [
        f"- patch {camp.patch_id}: hearth={camp.hearth_intensity:.2f}, store={camp.communal_food:.2f}, visits={camp.visit_count}"
        for camp in camps[:limit]
    ]


def _top_cluster_lines(state, limit: int = 8) -> list[str]:
    clusters = detect_clusters(state)
    if not clusters:
        return ["- No multi-agent clusters detected at the end of the run."]
    return [
        f"- patch {cluster.patch_id}: occupants={cluster.occupants}, kin_links={cluster.kin_links}"
        for cluster in clusters[:limit]
    ]


def _survivor_lines(state, limit: int = 10) -> list[str]:
    living = [agent for agent in state.agents if agent.alive]
    if not living:
        return ["- No surviving agents."]
    ranked = sorted(
        living,
        key=lambda agent: (
            len(agent.child_ids),
            agent.skills.caregiving + agent.skills.foraging + agent.skills.navigation,
            -agent.hunger - agent.thirst - agent.fatigue,
        ),
        reverse=True,
    )
    return [
        (
            f"- agent {agent.agent_id} ({agent.age_stage}) patch={agent.patch_id} "
            f"H={agent.hunger:.2f} T={agent.thirst:.2f} F={agent.fatigue:.2f} "
            f"food={agent.carried_food:.2f} children={len(agent.child_ids)} "
            f"skills=({agent.skills.foraging:.2f}/{agent.skills.navigation:.2f}/{agent.skills.caregiving:.2f})"
        )
        for agent in ranked[:limit]
    ]


def build_run_report(state, summary, config_path: str | None = None) -> str:
    living = [agent for agent in state.agents if agent.alive]
    dead = [agent for agent in state.agents if not agent.alive]
    camps = detect_camps(state.world)
    clusters = detect_clusters(state)
    living_stage_counts = _stage_counts(living)
    dead_stage_counts = _stage_counts(dead)
    death_causes = Counter(_cause_proxy(agent) for agent in dead)
    mean_hunger = _mean([agent.hunger for agent in living])
    mean_thirst = _mean([agent.thirst for agent in living])
    mean_fatigue = _mean([agent.fatigue for agent in living])
    mean_stress = _mean([agent.stress for agent in living])
    water_memories = _mean([sum(1 for key in agent.spatial_memory if key[0] == "water") for agent in living])
    total_days = simulated_days(state)

    lines = [
        "# CivSim Run Report",
        "",
        "## Overview",
        f"- seed: {summary.seed}",
        f"- simulated days: {total_days}",
        f"- config: `{config_path or 'unknown'}`",
        f"- final population: {summary.final_population}",
        f"- child survival rate: {summary.child_survival_rate:.3f}",
        f"- hearth count: {summary.hearth_count}",
        f"- path count: {summary.path_count}",
        f"- sharing events: {summary.sharing_events}",
        f"- mean trust: {summary.mean_trust:.3f}",
        f"- mean remembered sites: {summary.mean_remembered_sites:.3f}",
        "",
        "## Population And Survival",
        f"- living children/adults/elders: {living_stage_counts['child']}/{living_stage_counts['adult']}/{living_stage_counts['elder']}",
        f"- dead children/adults/elders: {dead_stage_counts['child']}/{dead_stage_counts['adult']}/{dead_stage_counts['elder']}",
        f"- surviving camps detected: {len(camps)}",
        f"- surviving end-state clusters detected: {len(clusters)}",
        f"- living need means: hunger={mean_hunger:.3f}, thirst={mean_thirst:.3f}, fatigue={mean_fatigue:.3f}, stress={mean_stress:.3f}",
        f"- mean surviving water-memory entries: {water_memories:.2f}",
        "",
        "## Death Pressure Proxy",
    ]
    if death_causes:
        lines.extend(f"- {cause}: {count}" for cause, count in death_causes.most_common())
    else:
        lines.append("- No deaths recorded.")

    lines.extend(
        [
            "",
            "## Timeline Samples",
            *_sample_timeline_lines(state),
            "",
            "## Action Totals",
            *_top_action_lines(state),
            "",
            "## Event Totals",
            *_top_event_lines(state),
            "",
            "## Daily Highlights",
            *_daily_event_lines(state),
            "",
            "## Top Camps",
            *_top_camp_lines(state),
            "",
            "## End-State Clusters",
            *_top_cluster_lines(state),
            "",
            "## Notable Survivors",
            *_survivor_lines(state),
            "",
            "## Interpretation",
            (
                "- This report is descriptive rather than scripted. It summarizes the actual population, site, "
                "memory, action, and event traces emitted by the simulation."
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def build_console_summary(state, summary, run_dir: Path) -> str:
    dead = [agent for agent in state.agents if not agent.alive]
    death_causes = Counter(_cause_proxy(agent) for agent in dead)
    top_cause = death_causes.most_common(1)[0][0] if death_causes else "none"
    return "\n".join(
        [
            f"run exported to {run_dir}",
            (
                f"final_population={summary.final_population} hearths={summary.hearth_count} "
                f"paths={summary.path_count} child_survival={summary.child_survival_rate:.3f}"
            ),
            f"top_death_pressure={top_cause} report={run_dir / 'report.md'}",
        ]
    )


def write_run_report(state, summary, out_dir: str | Path, config_path: str | None = None) -> Path:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    report_text = build_run_report(state, summary, config_path=config_path)
    (out_path / "report.md").write_text(report_text, encoding="utf-8")
    (out_path / "report.txt").write_text(report_text, encoding="utf-8")
    return out_path / "report.md"
