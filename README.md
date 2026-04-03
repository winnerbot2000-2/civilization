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

See [docs/architecture.md](docs/architecture.md) for the system structure and
[docs/tuning.md](docs/tuning.md) for parameter guidance.
