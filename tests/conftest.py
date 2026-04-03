from __future__ import annotations

import copy
from pathlib import Path

import pytest

from civsim.core.config import load_config


@pytest.fixture()
def small_config():
    config = load_config(Path(__file__).resolve().parents[1] / "configs" / "base.toml")
    config = copy.deepcopy(config)
    config.run.days = 20
    config.world.width = 20
    config.world.height = 12
    config.agents.initial_population = 40
    config.agents.initial_children = 8
    return config
