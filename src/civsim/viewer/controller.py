from __future__ import annotations

import copy
from dataclasses import dataclass, field

from ..core.simulation import initialize_simulation, run_tick


@dataclass(slots=True)
class ViewerController:
    base_config: object
    seed: int
    max_days: int | None = None
    speed_levels: tuple[int, ...] = (0, 1, 2, 4, 8, 16, 32)
    speed_index: int = 3
    paused: bool = False
    selected_agent_id: int | None = None
    pending_steps: int = 0
    _accumulator: float = 0.0
    _config_instance: object = field(init=False, repr=False)
    state: object = field(init=False)

    def __post_init__(self) -> None:
        self.restart(self.seed)

    @property
    def ticks_per_second(self) -> int:
        return self.speed_levels[self.speed_index]

    @property
    def finished(self) -> bool:
        if not any(agent.alive for agent in self.state.agents):
            return True
        if self.max_days is None:
            return False
        return self.state.clock.day >= self.max_days

    def restart(self, seed: int | None = None) -> None:
        if seed is not None:
            self.seed = seed
        self._config_instance = copy.deepcopy(self.base_config)
        self.state = initialize_simulation(self._config_instance, seed=self.seed)
        self.pending_steps = 0
        self._accumulator = 0.0
        self.paused = False
        self.selected_agent_id = None

    def change_seed(self, delta: int) -> None:
        self.restart(max(0, self.seed + delta))

    def toggle_pause(self) -> None:
        self.paused = not self.paused

    def set_paused(self, paused: bool) -> None:
        self.paused = paused

    def change_speed(self, delta: int) -> None:
        self.speed_index = max(0, min(len(self.speed_levels) - 1, self.speed_index + delta))

    def queue_tick(self, count: int = 1) -> None:
        self.pending_steps += max(0, count)

    def queue_day(self) -> None:
        self.pending_steps += self.state.config.world.ticks_per_day

    def select_agent(self, agent_id: int | None) -> None:
        self.selected_agent_id = agent_id

    def advance(self, dt_seconds: float) -> int:
        steps_run = 0
        if self.finished:
            self.paused = True
            return 0

        if self.pending_steps > 0:
            while self.pending_steps > 0 and not self.finished:
                run_tick(self.state)
                self.pending_steps -= 1
                steps_run += 1
            return steps_run

        if self.paused or self.ticks_per_second <= 0:
            return 0

        self._accumulator += dt_seconds * self.ticks_per_second
        while self._accumulator >= 1.0 and not self.finished:
            run_tick(self.state)
            self._accumulator -= 1.0
            steps_run += 1
        return steps_run
