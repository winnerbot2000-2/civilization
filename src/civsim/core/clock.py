from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SimulationClock:
    ticks_per_day: int
    season_length_days: int
    tick: int = 0

    @property
    def day(self) -> int:
        return self.tick // self.ticks_per_day

    @property
    def tick_in_day(self) -> int:
        return self.tick % self.ticks_per_day

    @property
    def is_night(self) -> bool:
        return self.tick_in_day == self.ticks_per_day - 1

    @property
    def season_index(self) -> int:
        return (self.day // self.season_length_days) % 2

    @property
    def season_name(self) -> str:
        return "good" if self.season_index == 0 else "bad"

    @property
    def year(self) -> int:
        days_per_year = self.season_length_days * 2
        return self.day // days_per_year

    @property
    def new_day(self) -> bool:
        return self.tick_in_day == 0

    def advance(self) -> None:
        self.tick += 1
