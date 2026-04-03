from __future__ import annotations


def record_path_use(world, edge: tuple[int, int], day: int, gain: float) -> None:
    trace = world.path_traces.get(edge)
    if trace is None:
        from ..world.sites import PathTrace

        trace = PathTrace(edge=edge)
        world.path_traces[edge] = trace
    trace.strength = min(4.0, trace.strength + gain)
    trace.use_count += 1
    trace.last_used_day = day


def decay_paths(world, decay: float) -> None:
    to_delete: list[tuple[int, int]] = []
    for edge, trace in world.path_traces.items():
        trace.strength *= 1.0 - decay
        if trace.strength < 0.02:
            to_delete.append(edge)
    for edge in to_delete:
        del world.path_traces[edge]
