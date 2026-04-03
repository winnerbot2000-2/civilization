from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TransferEvent:
    source_agent_id: int
    target_agent_id: int
    amount: float
    kind: str
