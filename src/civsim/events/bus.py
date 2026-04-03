from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from .types import EventRecord


class EventBus:
    def __init__(self, record_limit: int = 200_000):
        self.record_limit = record_limit
        self.records: list[EventRecord] = []

    def emit(self, record: EventRecord) -> None:
        if len(self.records) < self.record_limit:
            self.records.append(record)

    def to_jsonl(self, path: Path) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for record in self.records:
                handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")
