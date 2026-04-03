from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from civsim.core.config import load_config
from civsim.life.aging import age_mobility_factor, age_work_factor


def test_age_factors_decline_from_late_adulthood_into_elderhood() -> None:
    config = load_config(Path("configs/base.toml")).life
    young_adult = SimpleNamespace(age_days=config.child_stage_days + 80, age_stage="adult")
    late_adult = SimpleNamespace(age_days=config.elder_stage_days - 40, age_stage="adult")
    elder = SimpleNamespace(age_days=config.max_age_days, age_stage="elder")

    assert age_mobility_factor(young_adult, config) == 1.0
    assert age_work_factor(young_adult, config) == 1.0
    assert age_mobility_factor(young_adult, config) > age_mobility_factor(late_adult, config) > age_mobility_factor(elder, config)
    assert age_work_factor(young_adult, config) > age_work_factor(late_adult, config) > age_work_factor(elder, config)
