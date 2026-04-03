# Viewer

The CivSim viewer is a pygame-based live artificial-life sandbox and debugger
for the headless simulation. It sits on top of the existing
`SimulationState` and repeatedly advances the sim through the controller layer.
Rendering never mutates simulation logic.

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

- The primary controls are now visible on-screen buttons in the top control bar.
- `Space`: play / pause
- `T`: step one tick
- `Y`: step one day
- `R`: restart current seed
- `,` and `.`: previous / next seed
- `[` and `]`: slower / faster simulation rate through `1x`, `2x`, `5x`, `10x`, `50x`, `100x`, `500x`, and `MAX`
- `Backspace`: clear the selected agent
- `0`: movement / intent trail overlay
- `1`: terrain / movement-cost overlay
- `2`: water overlay
- `3`: food overlay
- `4`: danger overlay
- `5`: shelter overlay
- `6`: camp / hearth overlay
- `7`: path overlay
- `8`: agent need / stress overlay
- `9`: social link and trust overlay for selected agent
- `K`: kin-link overlay for selected agent
- `P`: resource-pressure overlay
- `S`: season tint overlay
- `G`: remembered good sites for selected agent
- `X`: remembered danger sites for selected agent
- `H`: toggle help
- left click: select agent

Visible buttons cover:
- play / pause / restart
- step tick / step day
- speed selection from `1x` through `500x` and `MAX`
- overlay controls for trails, social links, camps, and advanced debug overlays
- grouped rows for transport, speed, and layers so the control bar reads more
  like an analysis tool than a keyboard cheat sheet

## Time Scaling

- `1x` means the viewer targets roughly one simulated day per real second.
- The controller converts the selected multiplier into target ticks per second
  using the configured `ticks_per_day`.
- Simulation stepping is batched. At high speed, the controller advances many
  internal ticks between rendered frames.
- Rendering is throttled separately from simulation speed. The UI loop stays
  responsive, but the map redraw frequency drops at very high speed so the
  viewer does not waste time drawing every internal tick.
- `MAX` mode removes the fixed speed target and simply advances as many ticks as
  the controller's per-frame batch budget allows.

## Visual Notes

- The internal world is still patch-based, but the viewer now renders a small
  terrain surface per patch region and smooth-scales it up, which reduces the
  obvious grid look while preserving exact simulation positions.
- Terrain color now comes from a smoothed base field with layered feature
  accents for water, food, danger, and shelter, so adjacent patches visually
  blend into a landscape-like surface instead of reading as obvious boxes.
- Camps are rendered as warm reuse scars and hearth rings rather than square
  cell borders, which makes recurring places easier to read as lived-in terrain.
- Agents are rendered as tiny human-like stick silhouettes rather than plain
  dots, with different scale and posture for children, adults, and elders.
- Children use larger-head/smaller-body proportions, adults use the neutral
  stance, and elders are more stooped with a visible walking stick.
- Carrying food, resting, stress, danger, caregiving, and exploration all add
  small viewer-only cues so behavior is readable without inventing game rules.
- Visual interpolation, light bobbing, camp glows, cluster halos, and optional
  movement trails are viewer-only effects. They do not alter simulation state.
- The panel shows world state, selected-agent inspection, and a condensed event
  feed designed to remain readable even when the sim is running at high speed.
- At very high speed, the viewer automatically reduces purely visual detail
  such as trail density and glow strength to keep controls responsive while the
  simulation continues stepping in batches underneath.

## Notes

- The viewer is intended for debugging and validation, not gameplay.
- The simulation remains deterministic for a given seed and stepping sequence.
- The viewer can be replaced later because rendering and control are isolated in
  `civsim.viewer`.
