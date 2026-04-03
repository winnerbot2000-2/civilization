"""Lifecycle systems."""

from .aging import age_mobility_factor, age_stage_for_days, age_work_factor, daily_lifecycle_update
from .development import inherit_traits
from .reproduction import attempt_conception, resolve_births

__all__ = [
    "age_mobility_factor",
    "age_stage_for_days",
    "age_work_factor",
    "daily_lifecycle_update",
    "inherit_traits",
    "attempt_conception",
    "resolve_births",
]
