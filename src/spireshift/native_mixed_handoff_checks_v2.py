"""Verify normalized rest menus and their exact native field correspondence."""

from __future__ import annotations

from spireshift.native_mixed_handoff_checks_v1 import belt_controls
from spireshift.native_mixed_rest import View
from spireshift.native_selector_lifecycle_checks import surface
from spireshift.native_selector_lifecycle_trace import Trace


def rest_menu(trace: Trace, options: dict[str, bool], proceed: bool) -> None:
    raw = surface(trace.current)
    view = View.read(trace.frame)
    if raw["can_leave"] is not view.surface["can_proceed"] or {
        row["option_id"]: row["is_enabled"] for row in raw["options"]
    } != {row["option_id"]: row["enabled"] for row in view.surface["options"]}:
        raise ValueError("The raw and normalized rest permissions disagree")
    view.rest_menu(options, proceed)
    belt_controls(trace.current)
