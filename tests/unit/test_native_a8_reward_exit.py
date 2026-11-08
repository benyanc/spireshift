from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import pytest

from spireshift.native_a8_rescue_game import receipt
from spireshift.native_a8_reward_exit import verify_exit


def frame(act: int, kind: str, snapshot: str) -> dict[str, Any]:
    return {
        "binding_id": "menu",
        "observation": {"runtime_instance_id": "native-worker-42", "snapshot_id": snapshot},
        "actions": [{"bound_action_id": "offered-action"}],
        "terminal": False,
        "public_input": {
            "candidates": [{"label": "Localized button caption"}],
            "context": {
                "persistent": {"run": {"act": act, "floor": 16}, "player": {"hp": 10}},
                "interaction": {
                    "kind": kind,
                    "content": {"context": {"reward_kind": "room_rewards"}},
                },
            },
        },
    }


def save(directory: Path, name: str, rows: list[dict[str, Any]]) -> None:
    with gzip.open(directory / f"{name}.jsonl.gz", "wt") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


@pytest.mark.parametrize(
    ("owner", "fault"),
    [
        ("reward_set", None),
        ("combat_rewards_complete", None),
        ("reward_set", "card_skip"),
        ("reward_set", "nonboss"),
        ("reward_set", "stale_room"),
        ("reward_set", "same_act"),
        ("reward_set", "unavailable"),
        ("reward_set", "local"),
        ("reward_set", "undelivered"),
        ("reward_set", "wrong_successor"),
        ("reward_set", "different_runtime"),
        ("reward_set", "zero_hp"),
        ("reward_set", "extra_action"),
    ],
)
def test_boss_reward_exit_requires_native_room_and_bound_act2(
    tmp_path: Path, owner: str, fault: str | None
) -> None:
    before = frame(1, "reward_claim", "rewards")
    after = frame(2, "map_navigation", "map")
    choice = {"action_index": 0}
    accepted = receipt(before, choice, "native", "map")
    actual = {
        "episode": 1,
        "index": 1,
        "snapshot_id": "rewards",
        "action": {"bound_action_id": "offered-action"},
        "delivery": "delivered",
        "successor_snapshot_id": "map",
    }
    domain = {
        "index": 1,
        "before_snapshot_id": "rewards",
        "action_id": "offered-action",
        "successor_snapshot_id": "map",
        "delivery_domain": "native",
    }
    metrics = {
        "request": {"cmd": "process_metrics"},
        "response": {"type": "process_metrics", "process_id": 42},
    }
    source = {
        "type": "decision",
        "decision": owner,
        "is_boss": fault != "nonboss",
        "room_ref": "boss-room",
        "context": {"act": 1, "total_floor": 16},
        "player": {"hp": 10},
        **(
            {"is_terminal": True, "can_proceed": fault != "unavailable"}
            if owner == "reward_set"
            else {}
        ),
    }
    proceed = {
        "request": {
            "cmd": "action",
            "action": "skip_card_reward" if fault == "card_skip" else "proceed",
            "args": {"room_ref": "stale" if fault == "stale_room" else "boss-room"},
        },
        "response": {
            "type": "decision",
            "decision": "map_select",
            "context": {"act": 1 if fault == "same_act" else 2, "total_floor": 16},
            "player": {"hp": 10},
        },
    }
    tape: list[dict[str, Any]] = [
        metrics,
        {"request": {"cmd": "start_run"}, "response": {"type": "decision"}},
        metrics,
        {"request": {"cmd": "action", "action": "end_turn"}, "response": source},
        metrics,
        proceed,
        {"request": {"cmd": "get_map"}, "response": {"type": "map"}},
        metrics,
    ]
    if fault == "local":
        domain["delivery_domain"] = accepted["delivery_domain"] = "local_answer_factor"
    elif fault == "undelivered":
        actual["delivery"] = "unknown"
    elif fault == "wrong_successor":
        actual["successor_snapshot_id"] = "stale"
    elif fault == "different_runtime":
        after["observation"]["runtime_instance_id"] = "native-worker-99"
    elif fault == "zero_hp":
        after["public_input"]["context"]["persistent"]["player"]["hp"] = 0
    elif fault == "extra_action":
        tape.extend([proceed, metrics])

    save(tmp_path, "public-receipts", [actual])
    save(tmp_path, "answer-plan-deliveries", [domain])
    save(tmp_path, "private-transcript", tape)
    if fault is None:
        proof = verify_exit(tmp_path, before, choice, accepted, after, 2)
        assert (proof["native_reward_owner"], proof["operation"], proof["hp"]) == (
            owner,
            "proceed",
            10,
        )
    else:
        with pytest.raises(ValueError, match="native|Native|Act 2"):
            verify_exit(tmp_path, before, choice, accepted, after, 2)
