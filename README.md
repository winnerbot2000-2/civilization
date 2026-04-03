# CivSim

CivSim is a deterministic, headless proto-society simulation foundation for
emergent human-like development. It models a small seasonal world, bounded
agents, memory-guided decisions, dependent children, sparse social ties, and
persistent site traces such as hearths and paths.

The current version is intentionally narrow. It does not implement tribes,
cities, formal trade, religion, war, government, farming, or civilization
stages. Instead, it provides the primitive systems that can later allow those
patterns to emerge.

## Quick Start

Create a virtual environment, install the package, and run a short simulation:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
python -m civsim.cli.run --config configs/base.toml --seed 42 --days 180
python -m civsim.cli.inspect --run outputs/run_seed42_days180
```

To launch the live 2D debug viewer:

```powershell
pip install -e .[dev,viewer]
python -m civsim.cli.view --config configs/base.toml --seed 42
```

For the easiest "just open the app and run it" path, use the launcher:

```powershell
python launch_civsim.py
```

On Windows you can also just double-click:

```text
Launch_CivSim.bat
```

The launcher opens the live viewer, runs the simulation to the configured day
limit, closes automatically when the run is finished, exports the run to
`outputs/`, and writes a detailed end-of-run report for you. If you want it to
open the report automatically afterward, add `--open-report`.
You can also start smaller worlds directly from the launcher, for example:

```powershell
python launch_civsim.py --agents 20
python launch_civsim.py --agents 10
python launch_civsim.py --agents 20 --children 2
python launch_civsim.py --agents 20 --open-report
```

The viewer keeps rendering separate from simulation stepping. It supports
interactive pause/step control, stylized live 2D agent rendering, and
accelerated speeds from `1x` to `500x` plus `MAX` without trying to draw every
internal tick. The live window now includes visible on-screen controls so the
viewer can be driven mainly through buttons rather than memorizing keybinds,
and the map is rendered as a terrain-like surface rather than an obvious tile grid.

Run a small batch:

```powershell
python -m civsim.cli.batch --config configs/base.toml --seeds 5 --days 180
```

## Project Focus

- deterministic runtime with named RNG streams
- array-backed world layers with sparse site/path overlays
- agents with bounded perception and noisy priority-based action choice
- minimal layered memory and simple learning
- parent-child dependency, kin sociality, and camp persistence
- batch metrics and event logging for validation
- optional pygame-based live viewer for debugging and visual inspection

See [docs/architecture.md](docs/architecture.md) for the system structure and
[docs/tuning.md](docs/tuning.md) for parameter guidance. Viewer controls and
launch notes are in [docs/viewer.md](docs/viewer.md). Each exported run now
also includes `report.md` and `report.txt` alongside the usual summary, event,
metric, and snapshot files.
