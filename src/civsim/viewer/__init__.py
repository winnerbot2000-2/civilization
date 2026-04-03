"""Interactive 2D viewer and debugging tools for CivSim."""

from .controller import ViewerController
from .view_model import MetricsSnapshot, build_metrics_snapshot, recent_event_lines, selected_agent_lines

__all__ = [
    "ViewerController",
    "MetricsSnapshot",
    "build_metrics_snapshot",
    "recent_event_lines",
    "selected_agent_lines",
]
