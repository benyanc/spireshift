from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from spireshift.engine_potion_queue_checks import match_saved_choice
from spireshift.engine_worker_qualification import worker_script


def prefix() -> dict[str, Any]:
    return {
        "public_input": {
            "context": {"interaction": {"kind": "card_selection"}, "energy": 2},
            "candidates": [
                {"verb": "activate", "subject": {"definition_id": "HEART_OF_IRON"}},
                {"verb": "confirm", "cards": [3]},
            ],
        },
        "choice": {"action_index": 0},
    }


def test_prefix_rebinds_by_complete_public_candidate_not_old_transport_index() -> None:
    saved = prefix()
    current = deepcopy(saved["public_input"])
    current["candidates"].reverse()
    assert match_saved_choice({"model_input": current}, saved) == 1


@pytest.mark.parametrize("change", ["context", "candidate", "ambiguous"])
def test_prefix_refuses_changed_world_menu_or_ambiguous_binding(change: str) -> None:
    saved = prefix()
    current = deepcopy(saved["public_input"])
    if change == "context":
        current["context"]["energy"] = 7
    elif change == "candidate":
        current["candidates"][0]["subject"]["definition_id"] = "OTHER"
    else:
        saved["public_input"]["candidates"].append(deepcopy(current["candidates"][0]))
        current["candidates"].append(deepcopy(current["candidates"][0]))
    with pytest.raises(ValueError):
        match_saved_choice({"model_input": current}, saved)


def test_private_queue_and_mechanics_controls_cannot_become_production_workers() -> None:
    assert worker_script({"worker_script": "engine-native-worker-v9.mjs"}).endswith("v9.mjs")
    for script in ("engine-potion-queue-worker-v1.mjs", "engine-mechanics-worker-v4.mjs"):
        with pytest.raises(ValueError, match="Unqualified"):
            worker_script({"worker_script": script})
