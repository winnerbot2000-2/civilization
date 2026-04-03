# Architecture Overview

The codebase is organized around deterministic simulation primitives:

- `core`: configuration, RNG streams, clock, orchestrator, serialization
- `world`: patch grid, environmental layers, seasonality, occupancy, sites
- `agents`: agent state, local perception, candidate action generation,
  and intent resolution
- `memory`: spatial, episodic, social, and habit memory models
- `learning`: reinforcement, imitation, and skill gains
- `social`: sparse relationship updates, attachment, sharing, and coordination
- `life`: aging, reproduction, dependent children, and inheritance noise
- `materials`: hearths, simple site food stores, and path traces
- `events`: typed records and append-only logging
- `metrics`: daily and run-level aggregation
- `analysis`: read-only detectors for camps, clusters, and traditions
- `cli`: run, batch, and inspect tooling

The runtime updates in a fixed order so outcomes remain reproducible:

1. world season/resource update
2. occupancy refresh
3. perception
4. memory cue retrieval and action generation
5. intent resolution
6. physiology and emotional updates
7. memory encoding and learning
8. material trace updates
9. daily lifecycle pass
10. metrics and events

Derived patterns such as camps and clusters are detected analytically and do not
feed back into behavior in v1.
