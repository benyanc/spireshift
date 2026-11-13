from __future__ import annotations

import gzip
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_complete_subset_and_public_boundary_contract_in_node() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node not installed")
    result = subprocess.run(
        [node, "--test", "scripts/engine-selection-cursor-v1.test.mjs"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("tamper", [False, True])
def test_streamed_cursor_replay_rejects_changed_local_delivery(
    tmp_path: Path, tamper: bool
) -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node not installed")
    state = {
        "type": "decision",
        "decision": "card_select",
        "selection_ref": "PRIVATE",
        "cards": [{"index": i, "name": f"Card {i}"} for i in range(21)],
        "min_select": 5,
        "max_select": 5,
        "cancelable": False,
        "require_manual_confirmation": False,
        "unpowered_previews": False,
        "pretend_cards_can_be_played": False,
        "selection_preferences_complete": True,
    }
    request = {
        "cmd": "action",
        "action": "selection_cursor_add",
        "args": {"selection_ref": "PRIVATE", "prefix": "", "index": 20},
    }
    response = {
        **state,
        "selection_ui": {"protocol": "public_ordered_card_subset_cursor_v1", "selected": [20]},
    }
    ui = {"request": request, "local": True, "response": response, "before": [], "after": [20]}
    private = [
        {"request": {"cmd": "observe"}, "response": state},
        {
            "request": request,
            "response": {**response, "max_select": 6} if tamper else response,
            "transport": "local_selection_ui",
        },
    ]
    for name, rows in [
        ("private-transcript.jsonl.gz", private),
        ("selection-cursor.jsonl.gz", [ui]),
    ]:
        with gzip.open(tmp_path / name, "wt") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
    r = subprocess.run(
        [node, "scripts/verify-selection-cursor-v1.mjs", str(tmp_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=20,
    )
    if tamper:
        assert r.returncode != 0
    else:
        assert r.returncode == 0, r.stderr
