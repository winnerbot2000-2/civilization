# Viewer

The CivSim viewer is a pygame-based live debugger for the headless simulation.
It consumes the existing `SimulationState` by repeatedly calling `run_tick`
through a small controller layer. Rendering never writes simulation logic.

## Launch

```powershell
pip install -e .[dev,viewer]
python -m civsim.cli.view --config configs/base.toml --seed 42
```

Useful options:

```powershell
python -m civsim.cli.view --config configs/base.toml --seed 42 --paused
python -m civsim.cli.view --config configs/base.toml --seed 42 --days 180
python -m civsim.cli.view --config configs/base.toml --seed 42 --max-frames 120
```

## Controls

- `Space`: play / pause
- `T`: step one tick
- `Y`: step one day
- `R`: restart current seed
- `,` and `.`: previous / next seed
- `[` and `]`: slower / faster simulation rate
- `1`: terrain / movement-cost overlay
- `2`: water overlay
- `3`: food overlay
- `4`: danger overlay
- `5`: shelter overlay
- `6`: camp / hearth overlay
- `7`: path overlay
- `8`: agent need / stress overlay
- `9`: social link and trust overlay for selected agent
- `G`: remembered good sites for selected agent
- `X`: remembered danger sites for selected agent
- `H`: toggle help
- left click: select agent

## Notes

- The viewer is intended for debugging and validation, not gameplay.
- The simulation remains deterministic for a given seed and stepping sequence.
- The viewer can be replaced later because rendering and control are isolated in
  `civsim.viewer`.
