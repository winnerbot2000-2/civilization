from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from ..core.config import load_config
from ..core.simulation import export_run, run_simulation
from ..metrics.comparisons import summarize_batch


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a batch of CivSim seeds.")
    parser.add_argument("--config", default="configs/base.toml", help="Path to the TOML config.")
    parser.add_argument("--seeds", type=int, default=5, help="Number of sequential seeds to run.")
    parser.add_argument("--days", type=int, default=None, help="Override the config duration in days.")
    parser.add_argument("--start-seed", type=int, default=None, help="Optional starting seed.")
    parser.add_argument("--output", default="outputs/batch", help="Batch output directory.")
    parser.add_argument("--export-runs", action="store_true", help="Also export each run snapshot.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(args.config)
    base_seed = args.start_seed if args.start_seed is not None else config.run.seed
    days = args.days if args.days is not None else config.run.days
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    summaries = []
    for offset in range(args.seeds):
        seed = base_seed + offset
        state, summary = run_simulation(config, seed=seed, days=days)
        summaries.append(summary)
        if args.export_runs:
            export_run(state, summary, output_dir / f"seed_{seed}")

    batch_summary = summarize_batch(summaries)
    with (output_dir / "batch_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "runs": [asdict(summary) for summary in summaries],
                "aggregate": asdict(batch_summary),
            },
            handle,
            indent=2,
            sort_keys=True,
        )
    print(json.dumps(asdict(batch_summary), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
