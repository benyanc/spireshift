"""Use a current native observation when shop exit opens the map."""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_feedback_host, native_a8_later_start
from spireshift.native_a8_feedback_host import FeedbackWorker
from spireshift.native_a8_head_policy import HeadState
from spireshift.native_flow_verification_v12 import records
from spireshift.native_systematic_selectors_v2 import node
from spireshift.native_win4_game import write

SCRIPT = "engine-a8-merchant-map-worker-v1.mjs"
SAVED = "verify-a8-merchant-map-saved-v1.mjs"
NORMAL = "native_a8_merchant_map_normal_v1"
PREPARED = "native_a8_merchant_map_prepared_v1"
CONTROL = "native_a8_merchant_map_control_verified"


class MerchantMapWorker(FeedbackWorker):
    def __init__(
        self, ctx: dict[str, Any], target: Path, *, prepared: bool = False, diagnostic: bool = False
    ) -> None:
        self.prepared_adapter = ctx["prepared_start_adapter"] if prepared else None
        self.diagnostic = diagnostic
        projection = PREPARED if prepared else NORMAL
        with patch.multiple(native_a8_feedback_host, SCRIPT=SCRIPT, PROJECTION=projection):
            super().__init__(ctx, target)

    def request(self, command: str, *, timeout: float = 20, **values: Any) -> dict[str, Any]:
        if command == "initialize":
            values["spec"] = {
                **values["spec"],
                "prepared_start_adapter": self.prepared_adapter,
                "merchant_map_diagnostic": self.diagnostic,
            }
        return super().request(command, timeout=timeout, **values)


class PreparedWorker(MerchantMapWorker):
    def __init__(self, ctx: dict[str, Any], target: Path) -> None:
        super().__init__(ctx, target, prepared=True)


def play_saved(
    ctx: dict[str, Any],
    task: dict[str, Any],
    start: dict[str, Any],
    target: Path,
    state: HeadState,
    deadline: float,
) -> dict[str, Any]:
    with patch.object(native_a8_later_start, "PreparedWorker", PreparedWorker):
        return native_a8_later_start.play(ctx, task, start, target, state, deadline)


def saved_control(ctx: dict[str, Any], target: Path) -> dict[str, Any]:
    worker = target / "worker"
    tail: deque[dict[str, Any]] = deque(maxlen=4)
    map_read: dict[str, Any] = {}
    for row in records(worker / "private-transcript.jsonl.gz"):
        if row["request"]["cmd"] == "action":
            tail.append(row)
        if row["request"]["cmd"] == "get_map":
            map_read = row["response"]
    if [row["request"]["action"] for row in tail] != [
        "select_map_node",
        "open_shop",
        "close_shop",
        "leave_shop",
    ] or map_read.get("type") != "map":
        raise ValueError("The saved merchant exit differs")
    identity = json.loads((worker / "identity.json").read_text())
    result: dict[str, Any] = json.loads(
        node(
            ctx,
            f"scripts/{SAVED}",
            payload={
                "states": list(tail),
                "map": map_read,
                "shared_projection": identity["shared_projection"],
                "projection": ctx["native"]["projection"],
            },
        )
    )
    return result


def _step(worker: MerchantMapWorker, current: dict[str, Any], label: str) -> dict[str, Any]:
    snapshot = current["snapshot"]
    (index,) = [
        index
        for index, action in enumerate(snapshot["bound_actions"]["actions"])
        if action["label"] == label
    ]
    result = worker.request("step", snapshot_id=snapshot["snapshot_id"], action_index=index)
    if result["delivery_domain"] != "native":
        raise ValueError("Merchant or map action did not reach the native game")
    return result


def native_control(
    ctx: dict[str, Any], target: Path, merchant: str, seed: str, use: bool
) -> dict[str, Any]:
    worker = MerchantMapWorker(ctx, target / "worker", diagnostic=True)
    try:
        worker.request("mount", seed=seed, timeout=25)
        current = worker.request("merchant_fixture", merchant=merchant)
        before = current["snapshot"]["persistent"]["content"]["player"]
        current = _step(worker, current, "Open shop inventory")
        if _has_foul_use(current):
            raise ValueError("The merchant target must be unavailable in inventory")
        current = _step(worker, current, "Close shop inventory")
        if not _has_foul_use(current):
            raise ValueError("Closing inventory must restore the merchant target")
        if use:
            current = _step(worker, current, "Use Foul Potion on Merchant")
            after = current["snapshot"]["persistent"]["content"]["player"]
            expected = (
                current["snapshot"]["interaction"]["kind"] == "combat_turn"
                and after["gold"] == before["gold"]
                if merchant == "fake"
                else after["gold"] == before["gold"] + 100
            )
            if not expected or any(p["definition_id"] == "FOUL_POTION" for p in after["potions"]):
                raise ValueError("The merchant potion effect did not complete")
        else:
            current = _step(worker, current, "Leave shop and open map")
            actions = current["snapshot"]["bound_actions"]["actions"]
            labels = [a["label"] for a in actions]
            if (
                current["snapshot"]["interaction"]["kind"] != "map_navigation"
                or not any(label.startswith("Choose ") for label in labels)
                or "Discard Foul Potion" not in labels
                or not any(label.startswith("Use Blood Potion") for label in labels)
                or _has_foul_use(current)
            ):
                raise ValueError("The map must retain its current legal choices and belt controls")
            current = _step(worker, current, "Discard Foul Potion")
            after = current["snapshot"]["persistent"]["content"]["player"]
            if current["snapshot"]["interaction"]["kind"] != "map_navigation" or any(
                p["definition_id"] == "FOUL_POTION" for p in after["potions"]
            ):
                raise ValueError("The map must retain the native discard effect")
        stopped = worker.close()
    finally:
        worker.stop()
    if stopped["clean_exit"] is not True or stopped.get("runtime_errors"):
        raise ValueError("The disposable native control did not shut down cleanly")
    rows = records(target / "worker/private-transcript.jsonl.gz")
    last: dict[str, Any] = {}
    exits = observations = 0
    for row in rows:
        action = row["request"].get("action")
        if action == "leave_shop":
            exits += 1
        if row["request"]["cmd"] == "observe":
            observations += 1
            if last.get("request", {}).get("action") != "leave_shop":
                raise ValueError("The refresh must immediately follow the single native exit")
            previous = last["response"]
            current = row["response"]
            if (
                previous["choices"] != current["choices"]
                or previous["decision"] != current["decision"]
                or previous["decision"] != "map_select"
            ):
                raise ValueError("The native refresh changed map ownership or choices")
        last = row
    if (exits, observations) != ((0, 0) if use else (1, 1)):
        raise ValueError("A native exit must be delivered once before its read-only refresh")
    return write(
        target / "report.json",
        {
            "merchant": merchant,
            "seed": seed,
            "used_potion": use,
            "native_exit_commands": exits,
            "native_observations": observations,
            "native_effect_verified": True,
            "clean_exit": True,
        },
    )


def _has_foul_use(current: dict[str, Any]) -> bool:
    return any(
        row["label"] == "Use Foul Potion on Merchant"
        for row in current["snapshot"]["bound_actions"]["actions"]
    )
