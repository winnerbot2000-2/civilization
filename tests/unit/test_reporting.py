from __future__ import annotations

from civsim.analysis.reporting import build_run_report, simulated_days
from civsim.core.simulation import build_summary, initialize_simulation, run_tick


def test_reporting_builds_markdown_with_core_sections(small_config) -> None:
    state = initialize_simulation(small_config, seed=31)
    for _ in range(8):
        run_tick(state)
    summary = build_summary(state, seed=31, days=simulated_days(state))
    report = build_run_report(state, summary, config_path="configs/base.toml")
    assert "# CivSim Run Report" in report
    assert "## Overview" in report
    assert "## Timeline Samples" in report
    assert "## Action Totals" in report
    assert "## Top Camps" in report
