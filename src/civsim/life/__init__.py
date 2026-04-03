"""Lifecycle systems."""

from .aging import age_stage_for_days, daily_lifecycle_update
from .development import inherit_traits
from .reproduction import attempt_conception, resolve_births

__all__ = [
    "age_stage_for_days",
    "daily_lifecycle_update",
    "inherit_traits",
    "attempt_conception",
    "resolve_births",
]
