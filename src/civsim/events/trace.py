from __future__ import annotations

from .types import TraceTag


def trace_tags(**kwargs: str | int | float | None) -> list[TraceTag]:
    tags: list[TraceTag] = []
    for key, value in kwargs.items():
        if value is None:
            continue
        tags.append(TraceTag(key=key, value=str(value)))
    return tags
