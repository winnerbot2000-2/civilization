"""Persistent material traces."""

from .hearths import decay_hearths, strengthen_hearths
from .stores import store_food, take_food
from .traces import decay_paths, record_path_use

__all__ = [
    "decay_hearths",
    "strengthen_hearths",
    "store_food",
    "take_food",
    "decay_paths",
    "record_path_use",
]
