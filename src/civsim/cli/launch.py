from __future__ import annotations

import argparse
import copy
import math
import os
import sys
import webbrowser
from pathlib import Path

from ..analysis.reporting import build_console_summary, write_run_report
from ..core.config import load_config, override_agent_counts
from ..core.simulation import build_summary, export_run
from ..launcher.ui import LaunchSettings, choose_launch_seed, normalize_launch_settings, show_finish_popup, show_launcher_menu


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the CivSim app-style viewer with a simple menu and end-of-run flow.")
    parser.add_argument("--config", default="configs/base.toml", help="Path to the TOML config.")
    parser.add_argument("--seed", type=int, default=None, help="Optional fixed seed for one-shot or menu startup.")
    parser.add_argument("--days", type=int, default=None, help="Optional run cap in days. Use 0 or omit to run until extinction.")
    parser.add_argument("--paused", action="store_true", help="Start paused.")
    parser.add_argument("--max-frames", type=int, default=None, help="Optional frame cap for smoke tests.")
    parser.add_argument("--output", default=None, help="Optional output directory for one-shot mode.")
    parser.add_argument("--agents", type=int, default=None, help="Override the total starting agent count.")
    parser.add_argument("--children", type=int, default=None, help="Optional starting child count when overriding agents.")
    parser.add_argument("--open-report", action="store_true", help="Automatically open the generated report when a run ends.")
    parser.add_argument(
        "--no-menu",
        action="store_true",
        help="Bypass the launcher menu and run a single viewer session with the supplied arguments.",
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


def _session_settings_from_args(config, args) -> LaunchSettings:
    default_total = config.agents.initial_population + config.agents.initial_children
    total_agents = args.agents if args.agents is not None else default_total
    children = args.children if args.children is not None else config.agents.initial_children
    random_seed_each_run = args.seed is None
    return normalize_launch_settings(
        LaunchSettings(
            days=args.days,
            total_agents=total_agents,
            children=children,
            start_paused=args.paused,
            open_report=args.open_report,
            random_seed_each_run=random_seed_each_run,
            fixed_seed=args.seed,
        ),
        config,
    )


def _format_finish_popup(summary, seed: int, elapsed_days: int) -> str:
    return "\n".join(
        [
            f"seed: {seed}",
            f"days: {elapsed_days}",
            f"final population: {summary.final_population}",
            f"child survival: {summary.child_survival_rate:.3f}",
            f"hearths: {summary.hearth_count}",
            f"paths: {summary.path_count}",
            f"sharing events: {summary.sharing_events}",
        ]
    )


def _format_menu_summary(summary, seed: int, elapsed_days: int, export_path: Path) -> str:
    return "\n".join(
        [
            f"Last run seed {seed}  |  days survived {elapsed_days}",
            f"Population {summary.final_population}  |  child survival {summary.child_survival_rate:.3f}",
            f"Hearths {summary.hearth_count}  |  paths {summary.path_count}  |  sharing {summary.sharing_events}",
            f"Saved to {export_path}",
        ]
    )


def _run_viewer_session(base_config, args, settings: LaunchSettings, seed: int):
    try:
        from ..viewer.pygame_viewer import run_viewer
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise SystemExit(
            "The launcher requires pygame. Install it with `pip install -e .[viewer]` "
            "or `pip install -e .[dev,viewer]`."
        ) from exc

    run_config = copy.deepcopy(base_config)
    override_agent_counts(run_config, total_agents=settings.total_agents, initial_children=settings.children)
    state = run_viewer(
        config=run_config,
        seed=seed,
        max_days=settings.days,
        start_paused=settings.start_paused,
        max_frames=args.max_frames,
        auto_close_on_finish=True,
        randomize_restart_seed=True,
    )
    elapsed_days = max(1, math.ceil(state.clock.tick / max(1, state.config.world.ticks_per_day)))
    summary = build_summary(state, seed=seed, days=elapsed_days)
    out_dir = args.output or f"outputs/run_seed{seed}_days{elapsed_days}"
    export_path = export_run(state, summary, Path(out_dir))
    report_path = write_run_report(state, summary, export_path, config_path=args.config)
    print(build_console_summary(state, summary, export_path))
    if settings.open_report:
        _open_report(report_path)
    finished = (settings.days is not None and state.clock.day >= settings.days) or not any(agent.alive for agent in state.agents)
    return state, summary, export_path, report_path, elapsed_days, finished


def _run_one_shot(base_config, args) -> None:
    settings = _session_settings_from_args(base_config, args)
    seed = choose_launch_seed(settings)
    _run_viewer_session(base_config, args, settings, seed)


def _run_menu_loop(base_config, args) -> None:
    settings = _session_settings_from_args(base_config, args)
    last_seed: int | None = None
    last_summary: str | None = None

    while True:
        menu_result = show_launcher_menu(
            config=base_config,
            initial_settings=settings,
            last_seed=last_seed,
            last_summary=last_summary,
        )
        if menu_result.action != "launch" or menu_result.settings is None:
            return

        settings = menu_result.settings
        rerun = True
        while rerun:
            seed = choose_launch_seed(settings)
            last_seed = seed
            _, summary, export_path, _, elapsed_days, finished = _run_viewer_session(base_config, args, settings, seed)
            last_summary = _format_menu_summary(summary, seed, elapsed_days, export_path)

            if not finished:
                rerun = False
                break

            finish_action = show_finish_popup(summary_text=_format_finish_popup(summary, seed, elapsed_days))
            if finish_action == "run_again":
                continue
            if finish_action == "menu":
                rerun = False
                break
            return


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    base_config = load_config(args.config)
    if args.no_menu or args.max_frames is not None:
        _run_one_shot(base_config, args)
        return
    _run_menu_loop(base_config, args)


if __name__ == "__main__":
    sys.exit(main())
