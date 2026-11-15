"""Check complete menus, bound deliveries and successors for lifecycle fixtures."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

Capture = tuple[dict[str, Any], dict[str, Any]]


def check_frame(capture: Capture) -> None:
    observation, frame = capture
    snapshot = observation["snapshot"]
    interaction = snapshot["interaction"]
    bound = snapshot["bound_actions"]
    menu = bound["actions"]
    reads = observation["reads"]
    snapshot_id = snapshot["snapshot_id"]
    runtime = snapshot["session"]["runtime_instance_id"]
    if (
        snapshot["completeness"]["status"] != "complete"
        or snapshot["completeness"]["missing"]
        or bound["status"] != "complete"
        or bound["total_count"] != bound["materialized_count"]
        or bound["total_count"] != len(menu)
        or frame["observation"]
        != {
            "runtime_instance_id": runtime,
            "snapshot_id": snapshot_id,
            "interaction_id": interaction["interaction_id"],
        }
        or len({action["bound_action_id"] for action in menu}) != len(menu)
        or any(action["interaction_id"] != interaction["interaction_id"] for action in menu)
        or sorted((action["raw_index"], action["bound_action_id"]) for action in frame["actions"])
        != [(i, action["bound_action_id"]) for i, action in enumerate(menu)]
        or len(frame["public_input"]["candidates"]) != len(menu)
    ):
        raise ValueError("Incomplete or misbound public decision menu")
    read_ids = [row["read_id"] for row in reads]
    if (
        len(set(read_ids)) != len(read_ids)
        or set(read_ids) != {descriptor["read_id"] for descriptor in snapshot["reads"]}
        or any(
            row["expected_snapshot_id"] != snapshot_id
            or row["observed_snapshot_id"] != snapshot_id
            or row["session"]["runtime_instance_id"] != runtime
            or row["completeness"]["status"] != "complete"
            or row["completeness"]["missing"]
            for row in reads
        )
    ):
        raise ValueError("Incomplete or stale public read")
    if frame["terminal"]:
        if menu or interaction["kind"] != "game_over" or interaction["stage"] != "complete":
            raise ValueError("Native terminal observation retains gameplay actions or is unsettled")
    elif not menu or snapshot["status"] != "interactive":
        raise ValueError("Playable successor is not ready")


def check_chain(
    captures: Sequence[Capture], choices: Sequence[int], receipts: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    if not captures or len(captures) != len(choices) + 1:
        raise ValueError("Require one final observation and both ends of every delivery")
    for capture in captures:
        check_frame(capture)
    owners = [frame["public_input"]["context"]["interaction"]["kind"] for _, frame in captures]
    for (before, frame), (after, next_frame), i, receipt in zip(
        captures[:-1], captures[1:], choices, receipts, strict=True
    ):
        start, successor = before["snapshot"], after["snapshot"]
        if type(i) is not int or not 0 <= i < len(frame["actions"]):
            raise ValueError("Selected action is outside its current menu")
        bound = frame["actions"][i]
        if (
            frame["terminal"]
            or receipt["delivery"] != "delivered"
            or receipt["reason_code"] is not None
            or receipt["snapshot_id"] != start["snapshot_id"]
            or receipt["action"] != start["bound_actions"]["actions"][bound["raw_index"]]
            or receipt["successor_snapshot_id"] != successor["snapshot_id"]
            or successor["sequence"] <= start["sequence"]
            or successor["snapshot_id"] == start["snapshot_id"]
            or next_frame["observation"]["runtime_instance_id"]
            != frame["observation"]["runtime_instance_id"]
        ):
            raise ValueError("Delivery does not own this action and its fresh successor")
    return {
        "delivered_actions": len(choices),
        "observations": len(captures),
        "owners": owners,
        "handoffs": [
            [source, target] for source, target in zip(owners[:-1], owners[1:], strict=True)
        ],
        "terminal": captures[-1][1]["terminal"],
    }
