from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Episode:
    tick: int
    kind: str
    patch_id: int
    salience: float
    other_agent_id: int | None = None
    outcome: float = 0.0


def record_episode(episodes: list[Episode], episode: Episode, max_episodes: int) -> None:
    episodes.append(episode)
    episodes.sort(key=lambda item: item.salience, reverse=True)
    del episodes[max_episodes:]
