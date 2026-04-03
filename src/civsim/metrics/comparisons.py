from __future__ import annotations

from .collector import BatchSummary


def summarize_batch(run_summaries) -> BatchSummary:
    runs = len(run_summaries)
    if runs == 0:
        return BatchSummary(runs=0, mean_final_population=0.0, mean_child_survival=0.0, mean_hearths=0.0, mean_path_count=0.0)
    return BatchSummary(
        runs=runs,
        mean_final_population=sum(item.final_population for item in run_summaries) / runs,
        mean_child_survival=sum(item.child_survival_rate for item in run_summaries) / runs,
        mean_hearths=sum(item.hearth_count for item in run_summaries) / runs,
        mean_path_count=sum(item.path_count for item in run_summaries) / runs,
    )
