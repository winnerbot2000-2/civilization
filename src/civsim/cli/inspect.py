from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect a CivSim run output.")
    parser.add_argument("--run", required=True, help="Run output directory.")
    return parser


def _symbol_for_patch(index: int, world: dict, camp_patches: set[int], occupied: set[int]) -> str:
    if index in occupied:
        return "A"
    if index in camp_patches:
        return "H"
    water = world["water"][index]
    food = world["food"][index]
    danger = world["danger"][index]
    if water > 0.7:
        return "W"
    if danger > 0.7:
        return "!"
    if food > 3.0:
        return "f"
    return "."


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run_dir = Path(args.run)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    snapshot = json.loads((run_dir / "snapshot.json").read_text(encoding="utf-8"))
    world = snapshot["world"]
    width = world["width"]
    height = world["height"]
    camp_patches = {camp["patch_id"] for camp in snapshot["camps"]}
    occupied = {agent["patch_id"] for agent in snapshot["agents"] if agent["alive"]}

    print("Summary")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print("\nMap")
    for y in range(height):
        row = []
        for x in range(width):
            patch_id = y * width + x
            row.append(_symbol_for_patch(patch_id, world, camp_patches, occupied))
        print("".join(row))

    print("\nTop camps")
    for camp in snapshot["camps"][:5]:
        print(f"  patch={camp['patch_id']} hearth={camp['hearth_intensity']:.2f} store={camp['communal_food']:.2f} visits={camp['visit_count']}")


if __name__ == "__main__":
    main()
