from __future__ import annotations

import argparse
import math
import os
import sys
import webbrowser
from pathlib import Path

from ..analysis.reporting import build_console_summary, write_run_report
from ..core.config import load_config, override_agent_counts
from ..core.simulation import build_summary, export_run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the CivSim viewer, then export the run and write a report on exit.")
    parser.add_argument("--config", default="configs/base.toml", help="Path to the TOML config.")
    parser.add_argument("--seed", type=int, default=None, help="Override the config seed.")
    parser.add_argument("--days", type=int, default=None, help="Run target in days before auto-pausing in the viewer.")
    parser.add_argument("--paused", action="store_true", help="Start paused.")
    parser.add_argument("--max-frames", type=int, default=None, help="Optional frame cap for smoke tests.")
    parser.add_argument("--output", default=None, help="Optional output directory.")
    parser.add_argument("--agents", type=int, default=None, help="Override the total starting agent count.")
    parser.add_argument("--children", type=int, default=None, help="Optional starting child count when overriding agents.")
    parser.add_argument(
        "--open-report",
        action="store_true",
        help="Automatically open the generated report when the run ends.",
    )
    return parser


def _open_report(path: Path) -> None:
    try:
        if hasattr(os, "startfile"):
            os.startfile(path)  # type: ignore[attr-defined]
            return
    except OSError:
        pass
    try:
        webbrowser.open(path.resolve().as_uri())
    except Exception:
        return


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(args.config)
    if args.agents is not None or args.children is not None:
        override_agent_counts(config, total_agents=args.agents, initial_children=args.children)
    try:
        from ..viewer.pygame_viewer import run_viewer
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise SystemExit(
            "The launcher requires pygame. Install it with `pip install -e .[viewer]` "
            "or `pip install -e .[dev,viewer]`."
        ) from exc

    seed = args.seed if args.seed is not None else config.run.seed
    max_days = args.days if args.days is not None else config.run.days
    state = run_viewer(
        config=config,
        seed=seed,
        max_days=max_days,
        start_paused=args.paused,
        max_frames=args.max_frames,
        auto_close_on_finish=True,
    )

    elapsed_days = max(1, math.ceil(state.clock.tick / max(1, state.config.world.ticks_per_day)))
    summary = build_summary(state, seed=seed, days=elapsed_days)
    out_dir = args.output or f"outputs/run_seed{seed}_days{elapsed_days}"
    export_path = export_run(state, summary, Path(out_dir))
    report_path = write_run_report(state, summary, export_path, config_path=args.config)
    print(build_console_summary(state, summary, export_path))
    if args.open_report:
        _open_report(report_path)


if __name__ == "__main__":
    sys.exit(main())
