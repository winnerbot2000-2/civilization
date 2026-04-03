from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from math import exp


@dataclass(slots=True)
class TrailSample:
    x: float
    y: float
    strength: float


@dataclass(slots=True)
class ViewerRenderState:
    visual_positions: dict[int, tuple[float, float]] = field(default_factory=dict)
    trails: dict[int, deque[TrailSample]] = field(default_factory=dict)
    ambience_seconds: float = 0.0
    max_trail_samples: int = 10

    def update_positions(
        self,
        target_positions: dict[int, tuple[float, float]],
        dt_seconds: float,
        speed_multiplier: int | None,
        movement_enabled: bool,
        max_trail_samples: int | None = None,
        min_trail_distance_sq: float = 0.75,
    ) -> dict[int, tuple[float, float]]:
        self.ambience_seconds += max(0.0, dt_seconds)
        if max_trail_samples is not None:
            self.max_trail_samples = max(1, max_trail_samples)
        rate = self._smoothing_rate(speed_multiplier)
        blend = 1.0 if rate <= 0.0 else 1.0 - exp(-max(0.0, dt_seconds) * rate)
        blend = min(1.0, max(0.0, blend))

        live_ids = set(target_positions)
        for agent_id, target in target_positions.items():
            previous = self.visual_positions.get(agent_id, target)
            new_x = previous[0] + (target[0] - previous[0]) * blend
            new_y = previous[1] + (target[1] - previous[1]) * blend
            new_position = (new_x, new_y)
            self.visual_positions[agent_id] = new_position
            if movement_enabled:
                self._record_trail(agent_id, previous, new_position, min_trail_distance_sq)

        for agent_id in list(self.visual_positions):
            if agent_id not in live_ids:
                del self.visual_positions[agent_id]
                self.trails.pop(agent_id, None)

        self._decay_trails(dt_seconds)
        return dict(self.visual_positions)

    def _record_trail(
        self,
        agent_id: int,
        previous: tuple[float, float],
        current: tuple[float, float],
        min_trail_distance_sq: float,
    ) -> None:
        dx = current[0] - previous[0]
        dy = current[1] - previous[1]
        distance_sq = dx * dx + dy * dy
        if distance_sq < min_trail_distance_sq:
            return
        trail = self.trails.setdefault(agent_id, deque())
        trail.appendleft(TrailSample(x=current[0], y=current[1], strength=1.0))
        while len(trail) > self.max_trail_samples:
            trail.pop()

    def _decay_trails(self, dt_seconds: float) -> None:
        decay = max(0.02, dt_seconds * 1.35)
        for agent_id in list(self.trails):
            trail = self.trails[agent_id]
            kept = deque()
            for sample in trail:
                strength = sample.strength - decay
                if strength > 0.05:
                    kept.append(TrailSample(sample.x, sample.y, strength))
            if kept:
                self.trails[agent_id] = kept
            else:
                del self.trails[agent_id]

    def _smoothing_rate(self, speed_multiplier: int | None) -> float:
        if speed_multiplier is None:
            return 20.0
        if speed_multiplier >= 500:
            return 18.0
        if speed_multiplier >= 100:
            return 15.0
        if speed_multiplier >= 10:
            return 12.0
        return 9.0
