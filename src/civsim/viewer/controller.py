from __future__ import annotations

import copy
from dataclasses import dataclass, field

from ..core.simulation import initialize_simulation, run_tick


@dataclass(slots=True)
class ViewerController:
    base_config: object
    seed: int
    max_days: int | None = None
    speed_levels: tuple[int | None, ...] = (1, 2, 5, 10, 50, 100, 500, None)
    speed_index: int = 2
    paused: bool = False
    selected_agent_id: int | None = None
    pending_steps: int = 0
    max_steps_per_advance: int = 512
    step_chunk_size: int = 64
    _accumulator: float = 0.0
    _config_instance: object = field(init=False, repr=False)
    state: object = field(init=False)
    last_steps_run: int = 0

    def __post_init__(self) -> None:
        self.restart(self.seed, preserve_pause=True)

    @property
    def current_speed_multiplier(self) -> int | None:
        return self.speed_levels[self.speed_index]

    @property
    def speed_label(self) -> str:
        multiplier = self.current_speed_multiplier
        return "MAX" if multiplier is None else f"{multiplier}x"

    @property
    def base_ticks_per_second(self) -> int:
        return self.state.config.world.ticks_per_day

    @property
    def ticks_per_second(self) -> int | None:
        multiplier = self.current_speed_multiplier
        if multiplier is None:
            return None
        return self.base_ticks_per_second * multiplier

    @property
    def queued_ticks(self) -> float:
        return float(self.pending_steps) + self._accumulator

    @property
    def finished(self) -> bool:
        if not any(agent.alive for agent in self.state.agents):
            return True
        if self.max_days is None:
            return False
        return self.state.clock.day >= self.max_days

    def restart(self, seed: int | None = None, preserve_pause: bool = True) -> None:
        was_paused = self.paused if preserve_pause else False
        if seed is not None:
            self.seed = seed
        self._config_instance = copy.deepcopy(self.base_config)
        self.state = initialize_simulation(self._config_instance, seed=self.seed)
        self.pending_steps = 0
        self._accumulator = 0.0
        self.paused = was_paused
        self.selected_agent_id = None
        self.last_steps_run = 0

    def change_seed(self, delta: int) -> None:
        self.restart(max(0, self.seed + delta), preserve_pause=True)

    def toggle_pause(self) -> None:
        self.paused = not self.paused

    def set_paused(self, paused: bool) -> None:
        self.paused = paused

    def change_speed(self, delta: int) -> None:
        self.speed_index = max(0, min(len(self.speed_levels) - 1, self.speed_index + delta))

    def set_speed_index(self, index: int) -> None:
        self.speed_index = max(0, min(len(self.speed_levels) - 1, index))

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
            self.last_steps_run = 0
            return 0

        if self.pending_steps > 0:
            steps_run = self._drain_pending_steps()
            self.last_steps_run = steps_run
            return steps_run

        if self.paused:
            self.last_steps_run = 0
            return 0

        target_tps = self.ticks_per_second
        if target_tps is None:
            steps_run = self._run_steps(self.max_steps_per_advance)
            self.last_steps_run = steps_run
            return steps_run

        self._accumulator += max(0.0, dt_seconds) * target_tps
        ready_steps = int(self._accumulator)
        if ready_steps <= 0:
            self.last_steps_run = 0
            return 0

        steps_to_run = min(ready_steps, self.max_steps_per_advance)
        steps_run = self._run_steps(steps_to_run)
        self._accumulator = max(0.0, self._accumulator - steps_run)
        if steps_run < steps_to_run:
            self._accumulator = 0.0
        self.last_steps_run = steps_run
        return steps_run

    def _drain_pending_steps(self) -> int:
        steps_to_run = min(self.pending_steps, self.max_steps_per_advance)
        steps_run = self._run_steps(steps_to_run)
        self.pending_steps = max(0, self.pending_steps - steps_run)
        return steps_run

    def _run_steps(self, total_steps: int) -> int:
        steps_run = 0
        while steps_run < total_steps and not self.finished:
            remaining = total_steps - steps_run
            batch_size = min(self.step_chunk_size, remaining)
            for _ in range(batch_size):
                if self.finished:
                    break
                run_tick(self.state)
                steps_run += 1
        return steps_run
