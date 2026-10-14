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


def retired_fixture(path: Path) -> list[dict[str, Any]]:
    cases = fixture(path)
    (path / "closed.json").unlink()
    (path / "active.json").write_text("{}")
    (path / "native-process-stop.json").write_text(
        json.dumps({"process_id": 123, "exit": {"code": None, "signal": "SIGTERM"}})
    )
    (path / "retired.json").write_text(
        json.dumps(
            {
                "schema_version": "actual-engine-worker-retirement-v1",
                "controller_process_stopped": True,
                "native_process_stopped": True,
                "native_process_id": 123,
                "workspace_reusable": False,
                "failed_seed_retried": False,
            }
        )
    )
    # A mount can fail before exporting any new observation or start response.
    # The prior game's complete delivery and ending chain remains independently auditable.
    cases.append({"status": "failed", "seed": "NEXTSEED", "decisions": [{"unknown": True}]})
    return cases


def test_retired_worker_keeps_verified_prefix_and_excludes_partial_last_game(
    tmp_path: Path,
) -> None:
    result = audit_worker_experience(tmp_path, retired_fixture(tmp_path))
    assert result["valid"] and result["games"] == result["decisions"] == 1
    assert result["excluded_failed_games"] == 1 and result["worker_retired"]
    assert (tmp_path / "active.json").exists()
    assert "retired.json" in result["source_sha256"]


@pytest.mark.parametrize("change", ["live", "wrong_process", "reuse", "middle_failure", "corrupt"])
def test_retired_prefix_requires_shutdown_and_unaltered_completed_game(
    tmp_path: Path, change: str
) -> None:
    cases = retired_fixture(tmp_path)
    p = tmp_path / "retired.json"
    d = json.loads(p.read_text())
    if change == "live":
        d["native_process_stopped"] = False
    elif change == "wrong_process":
        d["native_process_id"] = 456
    elif change == "reuse":
        d["workspace_reusable"] = True
    elif change == "middle_failure":
        cases.reverse()
    else:
        cases[0]["decisions"][0]["choice"]["action_index"] = 1
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError):
        audit_worker_experience(tmp_path, cases)
