from __future__ import annotations

import copy
from typing import Any

from spireshift.native_structured_audit import trace


def test_initial_trace_matching_ignores_comparison_model_id_but_preserves_inputs_and_actions() -> (
    None
):
    case: dict[str, Any] = {
        "decisions": [
            {"public_input": {"visible": "one"}, "choice": {"action_index": 1, "model_id": "named"}}
        ]
    }
    changed = copy.deepcopy(case)
    changed["decisions"][0]["choice"]["model_id"] = "hashed"
    assert trace(case) == trace(changed)
    changed["decisions"][0]["choice"]["action_index"] = 0
    assert trace(case) != trace(changed)
    changed = copy.deepcopy(case)
    changed["decisions"][0]["public_input"]["visible"] = "two"
    assert trace(case) != trace(changed)
