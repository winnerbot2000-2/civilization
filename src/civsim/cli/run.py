from __future__ import annotations

import argparse
from pathlib import Path

from ..analysis.reporting import build_console_summary, write_run_report
from ..core.config import load_config, override_agent_counts
from ..core.simulation import export_run, run_simulation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a single CivSim simulation.")
    parser.add_argument("--config", default="configs/base.toml", help="Path to the TOML config.")
    parser.add_argument("--seed", type=int, default=None, help="Override the config seed.")
    parser.add_argument("--days", type=int, default=None, help="Override the config duration in days.")
    parser.add_argument("--output", default=None, help="Optional output directory.")
    parser.add_argument("--agents", type=int, default=None, help="Override the total starting agent count.")
    parser.add_argument("--children", type=int, default=None, help="Optional starting child count when overriding agents.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(args.config)
    if args.agents is not None or args.children is not None:
        override_agent_counts(config, total_agents=args.agents, initial_children=args.children)
    seed = args.seed if args.seed is not None else config.run.seed
    days = args.days if args.days is not None else config.run.days
    state, summary = run_simulation(config, seed=seed, days=days)
    out_dir = args.output or f"outputs/run_seed{seed}_days{days}"
    export_path = export_run(state, summary, Path(out_dir))
    write_run_report(state, summary, export_path, config_path=args.config)
    print(build_console_summary(state, summary, export_path))


if __name__ == "__main__":
    main()
