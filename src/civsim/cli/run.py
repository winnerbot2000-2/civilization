from __future__ import annotations

import argparse
from pathlib import Path

from ..core.config import load_config
from ..core.simulation import export_run, run_simulation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a single CivSim simulation.")
    parser.add_argument("--config", default="configs/base.toml", help="Path to the TOML config.")
    parser.add_argument("--seed", type=int, default=None, help="Override the config seed.")
    parser.add_argument("--days", type=int, default=None, help="Override the config duration in days.")
    parser.add_argument("--output", default=None, help="Optional output directory.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(args.config)
    seed = args.seed if args.seed is not None else config.run.seed
    days = args.days if args.days is not None else config.run.days
    state, summary = run_simulation(config, seed=seed, days=days)
    out_dir = args.output or f"outputs/run_seed{seed}_days{days}"
    export_path = export_run(state, summary, Path(out_dir))
    print(f"run exported to {export_path}")
    print(f"final_population={summary.final_population} hearths={summary.hearth_count} paths={summary.path_count} child_survival={summary.child_survival_rate:.3f}")


if __name__ == "__main__":
    main()
