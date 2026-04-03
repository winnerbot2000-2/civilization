from __future__ import annotations

import argparse
import sys

from ..core.config import load_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the CivSim live 2D debug viewer.")
    parser.add_argument("--config", default="configs/base.toml", help="Path to the TOML config.")
    parser.add_argument("--seed", type=int, default=None, help="Override the config seed.")
    parser.add_argument("--days", type=int, default=None, help="Optional max days to simulate before auto-pausing.")
    parser.add_argument("--paused", action="store_true", help="Start paused.")
    parser.add_argument("--max-frames", type=int, default=None, help="Optional frame limit for smoke tests.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(args.config)
    try:
        from ..viewer.pygame_viewer import run_viewer
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise SystemExit(
            "The viewer requires pygame. Install it with `pip install -e .[viewer]` "
            "or `pip install -e .[dev,viewer]`."
        ) from exc

    seed = args.seed if args.seed is not None else config.run.seed
    max_days = args.days
    run_viewer(
        config=config,
        seed=seed,
        max_days=max_days,
        start_paused=args.paused,
        max_frames=args.max_frames,
    )


if __name__ == "__main__":
    sys.exit(main())
