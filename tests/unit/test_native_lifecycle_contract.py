from __future__ import annotations

from typing import Any

import pytest

from spireshift.native_lifecycle_contract import Capture, check_chain, check_frame


def capture(sequence: int, owner: str, *, terminal: bool = False) -> Capture:
    snapshot_id = f"snapshot-{sequence}"
    interaction_id = f"interaction-{sequence}"
    verbs = [] if terminal else ["confirm", "cancel"]
    actions = [
        {"bound_action_id": f"{snapshot_id}-{verb}", "interaction_id": interaction_id, "verb": verb}
        for verb in verbs
    ]
    complete: dict[str, Any] = {"status": "complete", "missing": []}
    return (
        {
            "snapshot": {
                "snapshot_id": snapshot_id,
                "sequence": sequence,
                "status": "observed" if terminal else "interactive",
                "interaction": {
                    "kind": owner,
                    "interaction_id": interaction_id,
                    "stage": "complete" if terminal else "choosing",
                },
                "session": {"runtime_instance_id": "worker-1"},
                "completeness": complete,
                "bound_actions": {
                    "status": "complete",
                    "total_count": len(actions),
                    "materialized_count": len(actions),
                    "actions": actions,
                },
                "reads": [{"read_id": "deck-read"}],
            },
            "reads": [
                {
                    "read_id": "deck-read",
                    "expected_snapshot_id": snapshot_id,
                    "observed_snapshot_id": snapshot_id,
                    "session": {"runtime_instance_id": "worker-1"},
                    "completeness": complete,
                }
            ],
        },
        {
            "observation": {
                "runtime_instance_id": "worker-1",
                "snapshot_id": snapshot_id,
                "interaction_id": interaction_id,
            },
            "actions": [
                {"raw_index": i, "bound_action_id": action["bound_action_id"]}
                for i, action in enumerate(actions)
            ],
            "public_input": {
                "candidates": [{"verb": verb} for verb in verbs],
                "context": {"interaction": {"kind": owner}},
            },
            "terminal": terminal,
        },
    )


def delivered(before: Capture, after: Capture, pick: int) -> dict[str, Any]:
    return {
        "snapshot_id": before[0]["snapshot"]["snapshot_id"],
        "successor_snapshot_id": after[0]["snapshot"]["snapshot_id"],
        "action": before[0]["snapshot"]["bound_actions"]["actions"][pick],
        "delivery": "delivered",
        "reason_code": None,
    }


def test_one_contract_checks_child_return_and_terminal_handoffs() -> None:
    frames = [
        capture(1, "card_selection"),
        capture(2, "combat_turn"),
        capture(3, "game_over", terminal=True),
    ]
    receipts = [delivered(frames[0], frames[1], 1), delivered(frames[1], frames[2], 0)]
    result = check_chain(frames, [1, 0], receipts)
    assert result["handoffs"] == [["card_selection", "combat_turn"], ["combat_turn", "game_over"]]
    assert result["terminal"] and result["delivered_actions"] == 2


def test_source_menu_requires_the_cancel_binding_and_current_snapshot_reads() -> None:
    raw, frame = capture(1, "card_selection")
    frame["actions"].pop()
    frame["public_input"]["candidates"].pop()
    with pytest.raises(ValueError, match="public decision menu"):
        check_frame((raw, frame))

    raw, frame = capture(1, "card_selection")
    raw["reads"][0]["observed_snapshot_id"] = "stale"
    with pytest.raises(ValueError, match="stale public read"):
        check_frame((raw, frame))


@pytest.mark.parametrize("mutate", ["wrong_control", "wrong_successor", "uncertain"])
def test_wrong_or_uncertain_deliveries_cannot_seal(mutate: str) -> None:
    before, after = capture(1, "rest_site"), capture(2, "map_navigation")
    receipt = delivered(before, after, 0)
    if mutate == "wrong_control":
        receipt["action"] = delivered(before, after, 1)["action"]
    elif mutate == "wrong_successor":
        receipt["successor_snapshot_id"] = before[0]["snapshot"]["snapshot_id"]
    else:
        receipt["delivery"] = "unknown"
    with pytest.raises(ValueError, match="fresh successor"):
        check_chain([before, after], [0], [receipt])


def test_terminal_labels_cannot_hide_current_actions() -> None:
    raw, frame = capture(1, "game_over")
    frame["terminal"] = True
    with pytest.raises(ValueError, match="retains gameplay actions"):
        check_frame((raw, frame))
