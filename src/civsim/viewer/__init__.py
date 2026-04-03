"""Interactive 2D viewer and debugging tools for CivSim."""

from .controller import ViewerController
from .render_state import ViewerRenderState
from .view_model import (
    MetricsSnapshot,
    ViewerFrameSnapshot,
    ViewerSnapshotCache,
    build_metrics_snapshot,
    build_viewer_snapshot,
    recent_event_lines,
    selected_agent_lines,
)

__all__ = [
    "ViewerController",
    "ViewerRenderState",
    "MetricsSnapshot",
    "ViewerFrameSnapshot",
    "ViewerSnapshotCache",
    "build_metrics_snapshot",
    "build_viewer_snapshot",
    "recent_event_lines",
    "selected_agent_lines",
]
