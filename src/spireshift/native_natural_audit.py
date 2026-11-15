"""Audit a deliberately bounded encounter without relabelling it a complete game."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from spireshift.engine_experience_stream import records
from spireshift.engine_run import _verify_saved_observation
from spireshift.native_relic_observation import verify


def audit(
    workspace: Path, actions: list[dict[str, Any]], node: Path, deadline: float
) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    ui = subprocess.run(
        [str(node), str(root / "scripts/verify-selection-cursor-v1.mjs"), str(workspace)],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    observations = iter(records(workspace / "public-observations.jsonl.gz", deadline))
    deliveries = iter(records(workspace / "public-receipts.jsonl.gz", deadline))
    current = next(observations)
    runtime = current["snapshot"]["session"]["runtime_instance_id"]
    _verify_saved_observation(current, runtime)
    for index, action in enumerate(actions):
        successor, delivery = next(observations), next(deliveries)
        _verify_saved_observation(successor, runtime)
        assert current["index"] == delivery["index"] == index
        assert successor["index"] == index + 1
        assert current["model_input"] == action["public_input"]
        assert delivery["delivery"] == "delivered"
        assert delivery["snapshot_id"] == current["snapshot"]["snapshot_id"]
        assert delivery["successor_snapshot_id"] == successor["snapshot"]["snapshot_id"]
        assert (
            delivery["action"]
            == current["snapshot"]["bound_actions"]["actions"][action["action_index"]]
        )
        current = successor
    if next(observations, None) is not None or next(deliveries, None) is not None:
        raise ValueError("Bounded encounter has unbound native delivery records")
    closed = json.loads((workspace / "closed.json").read_text())
    if not closed["clean_exit"] or closed["runtime_errors"] or (workspace / "active.json").exists():
        raise ValueError("An encounter worker was not closed and verified")
    return {
        "valid": True,
        "delivered_actions": len(actions),
        "selection_ui": json.loads(ui.stdout),
        "ordered_counters": verify(workspace, deadline),
        "complete_game_admission": False,
    }
