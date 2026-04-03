from __future__ import annotations

from civsim.core.simulation import run_simulation
from civsim.metrics.comparisons import summarize_batch


def test_small_seed_batch_smoke(small_config) -> None:
    summaries = [run_simulation(small_config, seed=seed, days=12)[1] for seed in (7, 8, 9)]
    aggregate = summarize_batch(summaries)
    assert aggregate.runs == 3
    assert aggregate.mean_hearths > 0
    assert aggregate.mean_path_count > 0
    assert len(
        {
            (
                summary.final_population,
                summary.hearth_count,
                summary.path_count,
                round(summary.mean_trust, 3),
            )
            for summary in summaries
        }
    ) >= 2
