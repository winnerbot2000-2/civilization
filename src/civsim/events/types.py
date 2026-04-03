from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TraceTag:
    key: str
    value: str


@dataclass(slots=True)
class EventRecord:
    tick: int
    day: int
    kind: str
    agent_id: int | None = None
    other_agent_id: int | None = None
    patch_id: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    trace: list[TraceTag] = field(default_factory=list)
