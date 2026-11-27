"""Match the semantic operand-free rest exit across its two exported labels."""

from __future__ import annotations

from spireshift.native_selector_lifecycle_trace import Match
from spireshift.native_selector_lifecycle_trace import label as raw_label


def control_label(expected: str) -> Match:
    if expected != "Proceed to map":
        return raw_label(expected)
    # Raw snapshots export close/Leave rest site. The canonical learner menu
    # exports activate/Proceed to map. Match the exact qualified binding, never
    # send a textual command or select a substitute action.
    return lambda raw, candidate: (
        raw["verb"] == "close"
        and raw["subject_referent_id"] is None
        and not raw["arguments"]
        and candidate["verb"] == "activate"
        and candidate["label"] == expected
    )
