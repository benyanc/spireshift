"""Verify an Act 1 boss reward exit at the delivered native boundary."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from spireshift.native_a8_rescue_game import public_state, receipt
from spireshift.native_flow_verification_v12 import records


def check_delivery(
    actual: dict[str, Any], domain: dict[str, Any], accepted: dict[str, Any], index: int
) -> None:
    if (
        actual["episode"] != 1
        or actual["index"] != index
        or domain["index"] != index
        or actual["delivery"] != "delivered"
        or actual["snapshot_id"] != accepted["before_snapshot_id"]
        or actual["action"]["bound_action_id"] != accepted["bound_action_id"]
        or actual["successor_snapshot_id"] != accepted["successor_snapshot_id"]
        or domain["before_snapshot_id"] != accepted["before_snapshot_id"]
        or domain["action_id"] != accepted["bound_action_id"]
        or domain["successor_snapshot_id"] != accepted["successor_snapshot_id"]
        or domain["delivery_domain"] != accepted["delivery_domain"]
    ):
        raise ValueError("Native delivery does not bind the recorded action and successor")


def native_tail(
    rows: Iterable[dict[str, Any]], index: int, runtime_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Align the last two private decisions to the frozen worker's observation indices."""
    tail: deque[dict[str, Any]] = deque(maxlen=2)
    pending = None
    observations = 0
    started = closed = False
    for row in rows:
        cmd = row["request"]["cmd"]
        if closed:
            raise ValueError("Native evidence continues after shutdown")
        if cmd == "start_run":
            if started or row.get("transport") is not None:
                raise ValueError("Expected one native fresh start in the reward-exit evidence")
            started, pending = True, row
        elif cmd == "action":
            if not started or observations == 0 or pending is not None:
                raise ValueError("Expected one transport action per native observation")
            pending = row
        elif cmd == "process_metrics" and started:
            # The worker emits this read once after each mounted or delivered observation.
            if (
                pending is None
                or pending["response"]["type"] != "decision"
                or f"native-worker-{row['response']['process_id']}" != runtime_id
            ):
                raise ValueError("Native decision and observation boundaries differ")
            tail.append(pending)
            observations += 1
            pending = None
        elif cmd == "quit":
            if not started or pending is not None:
                raise ValueError("Native worker quit before observing its successor")
            closed = True
        elif cmd not in {"get_map", "process_metrics", "run_identity", "runtime_identity"}:
            raise ValueError("Unexpected transport command in the reward-exit evidence")
    if index < 1 or observations != index + 1 or pending is not None or len(tail) != 2:
        raise ValueError("Native transition does not align with the delivered successor index")
    if tail[0].get("transport") is not None:
        raise ValueError("The source reward owner must be a native decision")
    return tail[0]["response"], tail[1]


def verify_exit(
    worker: Path,
    before: dict[str, Any],
    choice: dict[str, Any],
    accepted: dict[str, Any],
    after: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    run, player, owner = public_state(before)
    successor, survivor, next_owner = public_state(after)
    runtime_id = before["observation"]["runtime_instance_id"]
    if (
        run["act"] != 1
        or before["terminal"]
        or owner["kind"] != "reward_claim"
        or owner["content"]["context"]["reward_kind"] != "room_rewards"
        or successor["act"] != 2
        or next_owner["kind"] != "map_navigation"
        or after["terminal"]
        or survivor["hp"] <= 0
        or after["observation"]["runtime_instance_id"] != runtime_id
        or accepted != receipt(before, choice, "native", after["observation"]["snapshot_id"])
    ):
        raise ValueError("Act 2 requires a delivered room reward exit and a living player")

    actual = deque(records(worker / "public-receipts.jsonl.gz"), maxlen=1)
    domains = deque(records(worker / "answer-plan-deliveries.jsonl.gz"), maxlen=1)
    if not actual or not domains:
        raise ValueError("Missing bound receipt for the boss reward exit")
    check_delivery(actual[0], domains[0], accepted, index - 1)

    source, transition = native_tail(
        records(worker / "private-transcript.jsonl.gz"), index, runtime_id
    )
    request, state = transition["request"], transition["response"]
    room = source.get("room_ref")
    if (
        source["decision"] not in {"reward_set", "combat_rewards_complete"}
        or source.get("is_boss") is not True
        or (
            source["decision"] == "reward_set"
            and (source.get("is_terminal") is not True or source.get("can_proceed") is not True)
        )
        or not isinstance(room, str)
        or not room
        or source["context"]["act"] != 1
        or source["context"]["total_floor"] != run["floor"]
        or source["player"]["hp"] != player["hp"]
        or transition.get("transport") is not None
        or request != {"cmd": "action", "action": "proceed", "args": {"room_ref": room}}
        or state["decision"] != "map_select"
        or state["context"]["act"] != 2
        or state["context"]["total_floor"] != successor["floor"]
        or state["player"]["hp"] != survivor["hp"]
    ):
        raise ValueError("Act 2 requires native proceed from the current Act 1 boss rewards")
    return {
        "operation": "proceed",
        "native_reward_owner": source["decision"],
        "room_ref": room,
        "receipt_index": index - 1,
        "receipt": accepted,
        "act": 2,
        "hp": survivor["hp"],
    }
