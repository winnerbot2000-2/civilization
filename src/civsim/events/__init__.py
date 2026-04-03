"""Event logging primitives."""

from .types import EventRecord, TraceTag
from .bus import EventBus

__all__ = ["EventRecord", "TraceTag", "EventBus"]
