from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import pytest

from spireshift.engine_experience_audit import audit_worker_experience


def fixture(path: Path, mutation: str = "") -> list[dict[str, Any]]:
    action = {
        "bound_action_id": "advertised",
        "verb": "end_turn",
        "interaction_id": "current",
        "arguments": [],
    }
    snapshot: dict[str, Any] = {
        "session": {"runtime_instance_id": "fixture"},
        "completeness": {"status": "complete"},
        "information_policy": {"includes_hidden_information": False},
        "status": "interactive",
        "persistent": {"content": {"run": {"ascension": 8}}},
        "interaction": {"interaction_id": "current", "kind": "combat_turn"},
        "snapshot_id": "before",
        "bound_actions": {
            "status": "complete",
            "total_count": 1,
            "materialized_count": 1,
            "actions": [action],
        },
    }
    terminal = {
        **snapshot,
        "snapshot_id": "after",
        "status": "observed",
        "interaction": {"kind": "game_over"},
        "bound_actions": {
            "status": "complete",
            "total_count": 0,
            "materialized_count": 0,
            "actions": [],
        },
    }
    end = {"native_game_over": True, "native_player_dead": True, "native_victory_room": False}
    public = {"visible": "player-only"}
    seed = "SP1RESH1FTA8TEST001"
    observations = [
        {
            "episode": 1,
            "index": 0,
            "snapshot": snapshot,
            "reads": [],
            "model_input": public,
            "public_key": "visible",
        },
        {
            "episode": 1,
            "index": 1,
            "snapshot": terminal,
            "reads": [],
            "facts": {"terminal": True, "victory": False},
        },
    ]
    receipts: list[dict[str, Any]] = [
        {
            "episode": 1,
            "index": 0,
            "snapshot_id": "before",
            "action": dict(action),
            "delivery": "delivered",
            "successor_snapshot_id": "after",
        }
    ]
    raw = [
        {
            "request": {
                "cmd": "start_run",
                "seed": seed,
                "ascension": 8,
                "character": "Ironclad",
                "content_policy": "native_benchmark_full_v1",
            },
            "response": {},
        },
        {"request": {"cmd": "run_identity"}, "response": end},
        {"request": {"cmd": "quit"}, "response": {}},
    ]
    if mutation == "different_target":
        receipts[0]["action"]["bound_action_id"] = "not-advertised"
    elif mutation == "unknown":
        receipts[0]["delivery"] = "unknown"
    elif mutation == "broken_successor":
        receipts[0]["successor_snapshot_id"] = "other-state"
    elif mutation == "hidden":
        snapshot["persistent"]["content"]["seed"] = "secret"
    elif mutation == "fixture":
        raw.append({"request": {"cmd": "debug"}, "response": {}})
    elif mutation == "missing":
        receipts.clear()
    for name, rows in (
        ("private-transcript", raw),
        ("public-observations", observations),
        ("public-receipts", receipts),
    ):
        with gzip.open(path / f"{name}.jsonl.gz", "wt") as stream:
            stream.write("".join(json.dumps(row) + "\n" for row in rows))
    (path / "closed.json").write_text(json.dumps({"clean_exit": True, "episodes": 1}))
    return [
        {
            "status": "terminal",
            "privileged_fixture": False,
            "recovered": False,
            "seed": seed,
            "victory": False,
            "native_ending_evidence_agrees": True,
            "private_final_identity": end,
            "decisions": [
                {"public_input": public, "public_key": "visible", "choice": {"action_index": 0}}
            ],
        }
    ]


def test_saved_deliveries_reconstruct_without_launching_games(tmp_path: Path) -> None:
    result = audit_worker_experience(tmp_path, fixture(tmp_path))
    assert result["valid"] and result["games"] == result["decisions"] == 1
    assert result["games_replayed"] == 0


@pytest.mark.parametrize(
    "change", ["different_target", "unknown", "broken_successor", "hidden", "fixture", "missing"]
)
def test_unadvertised_uncertain_private_or_incomplete_experience_fails(
    tmp_path: Path, change: str
) -> None:
    cases = fixture(tmp_path, change)
    with pytest.raises(ValueError):
        audit_worker_experience(tmp_path, cases)


def test_interrupted_worker_marker_blocks_experience_admission(tmp_path: Path) -> None:
    cases = fixture(tmp_path)
    (tmp_path / "active.json").write_text("{}")
    with pytest.raises(ValueError, match="cleanly"):
        audit_worker_experience(tmp_path, cases)
