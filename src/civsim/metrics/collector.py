from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MetricSample:
    day: int
    living_agents: int
    living_children: int
    hearth_count: int
    sharing_events: int
    mean_trust: float
    mean_co_residence: float
    remembered_sites: float
    path_count: int


@dataclass(slots=True)
class BatchSummary:
    runs: int
    mean_final_population: float
    mean_child_survival: float
    mean_hearths: float
    mean_path_count: float


@dataclass(slots=True)
class MetricsCollector:
    samples: list[MetricSample] = field(default_factory=list)
    action_counts: dict[str, int] = field(default_factory=dict)
    sharing_events: int = 0

    def record_action(self, action: str) -> None:
        self.action_counts[action] = self.action_counts.get(action, 0) + 1
        if action in {"share_food", "care_for_child"}:
            self.sharing_events += 1

    def sample(self, state, day: int) -> None:
        living = [agent for agent in state.agents if agent.alive]
        children = [agent for agent in living if agent.age_stage == "child"]
        edges = [edge for agent in living for edge in agent.social_memory.values()]
        remembered_sites = sum(len(agent.spatial_memory) for agent in living) / max(1, len(living))
        self.samples.append(
            MetricSample(
                day=day,
                living_agents=len(living),
                living_children=len(children),
                hearth_count=sum(1 for site in state.world.site_markers.values() if site.hearth_intensity > 0.2),
                sharing_events=self.sharing_events,
                mean_trust=(sum(edge.trust for edge in edges) / len(edges)) if edges else 0.0,
                mean_co_residence=(sum(edge.co_residence_score for edge in edges) / len(edges)) if edges else 0.0,
                remembered_sites=remembered_sites,
                path_count=len(state.world.path_traces),
            )
        )
