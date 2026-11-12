"""Verify the Crystal Sphere decision on saved data and fresh native fixtures."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_feedback_host
from spireshift.native_a8_feedback_host import FeedbackWorker
from spireshift.native_a8_rescue_game import receipt
from spireshift.native_flow_verification_v12 import records
from spireshift.native_shared_transport import JsonLines
from spireshift.native_systematic_selectors_v2 import CONVERTER, node

SCRIPT = "engine-a8-crystal-grid-worker-v1.mjs"
SAVED = "verify-a8-crystal-grid-saved-v1.mjs"
PROJECTION = "native_a8_crystal_grid_v1"
GRID = "Crystal Sphere — grid"


class GridWorker(FeedbackWorker):
    def __init__(self, ctx: dict[str, Any], target: Path, *, fixture: bool = False) -> None:
        self.fixture = fixture
        with patch.multiple(native_a8_feedback_host, SCRIPT=SCRIPT, PROJECTION=PROJECTION):
            super().__init__(ctx, target)

    def request(self, command: str, *, timeout: float = 20, **values: Any) -> dict[str, Any]:
        if command == "initialize":
            values["spec"] = {**values["spec"], "grid_fixture": self.fixture}
        return super().request(command, timeout=timeout, **values)


def saved_grid(ctx: dict[str, Any], worker: Path) -> dict[str, Any]:
    offer, grid = None, None
    for row in records(worker / "private-transcript.jsonl.gz"):
        response = row["response"]
        if response.get("event_id") == "CRYSTAL_SPHERE":
            if response["event_name"] == GRID:
                if row["request"] != {
                    "cmd": "action",
                    "action": "choose_option",
                    "args": {"option_index": 1},
                }:
                    raise ValueError("Require the exact native Payment Plan handoff")
                grid = response
            else:
                offer = response
    if offer is None or grid is None or grid["context"]["act"] != 2:
        raise ValueError("The saved Act 2 Crystal Sphere handoff is missing")
    identity = json.loads((worker / "identity.json").read_text())
    result: dict[str, Any] = json.loads(
        node(
            ctx,
            f"scripts/{SAVED}",
            payload={
                "offer": offer,
                "grid": grid,
                "shared_projection": identity["shared_projection"],
                "projection": ctx["native"]["projection"],
            },
        )
    )
    return result


def native_grid(
    ctx: dict[str, Any],
    target: Path,
    seed: str,
    payment: int,
    deadline: float,
    score_menu: Callable[[dict[str, Any]], dict[str, int]],
) -> dict[str, Any]:
    if payment not in (0, 1):
        raise ValueError("Require a declared Crystal Sphere payment")
    root = ctx["qualification"].root
    bridge = JsonLines(root, [ctx["node"], f"scripts/{CONVERTER}"], target / "converter.log")
    try:
        worker = GridWorker(ctx, target / "worker", fixture=True)
        try:
            current = worker.request("grid_fixture", seed=seed, timeout=25)
            frame = bridge.project(current["snapshot"], current["reads"], None, deadline)

            def take(field: str, expected: str) -> None:
                nonlocal current, frame
                actions = current["snapshot"]["bound_actions"]["actions"]
                (index,) = [
                    i
                    for i, binding in enumerate(frame["actions"])
                    if actions[binding["raw_index"]][field] == expected
                ]
                choice = {"binding_id": frame["binding_id"], "action_index": index}
                current = worker.request(
                    "step",
                    snapshot_id=frame["observation"]["snapshot_id"],
                    action_index=frame["actions"][index]["raw_index"],
                )
                if current["delivery_domain"] != "native":
                    raise ValueError("Crystal Sphere choices require actual native delivery")
                successor = current["snapshot"]["snapshot_id"]
                bridge.commit(choice, receipt(frame, choice, "native", successor), deadline)
                frame = bridge.project(current["snapshot"], current["reads"], None, deadline)

            def inventory() -> tuple[int, int]:
                context = frame["public_input"]["context"]
                gold = context["persistent"]["player"]["gold"]
                (deck,) = [
                    r["content"]["cards"] for r in context["reads"] if r["kind"] == "run_deck"
                ]
                return int(gold), sum(c["definition_id"] == "DEBT" for c in deck)

            gold, debt = inventory()
            price = 0
            if not payment:
                options = current["snapshot"]["interaction"]["content"]["surface"]["options"]
                (offer,) = [row for row in options if row["title"] == "Uncover Future"]
                match = re.fullmatch(r"Pay (\d+) Gold\. Divine 3 times\.", offer["description"])
                if match is None:
                    raise ValueError("Require the visible native Crystal Sphere gold price")
                price = int(match[1])
            take("label", "Payment Plan" if payment else "Uncover Future")
            after_gold, after_debt = inventory()
            if (after_gold, after_debt) != (gold - price, debt + payment):
                raise ValueError("The native Crystal Sphere payment did not apply")
            scored = score_menu(frame["public_input"])
            moves = []
            for index in range(6 if payment else 3):
                remaining = (6 if payment else 3) - index
                surface = current["snapshot"]["interaction"]["content"]["surface"]
                if (
                    surface.get("title") != GRID
                    or not surface["description"].startswith(f"Divinations remaining: {remaining}.")
                    or len(frame["actions"]) != 242
                ):
                    raise ValueError(
                        "Require all current tool/cell choices and native charge count"
                    )
                x, y = [(2, 2), (5, 2), (8, 2), (2, 5), (5, 5), (8, 5)][index]
                large = index % 2 == 1
                label = f"{'Big' if large else 'Small'} at ({x},{y})"
                moves.append((121 if large else 0) + 11 * x + y)
                take("label", label)

            for _ in range(20):
                labels = [c["label"] for c in frame["public_input"]["candidates"]]
                if frame["source_family"] == "event_option" and labels == ["Proceed"]:
                    break
                if time.monotonic() >= deadline or frame["source_family"] not in {
                    "reward_claim",
                    "card_reward_selection",
                }:
                    raise ValueError("Native Crystal Sphere rewards did not settle")
                actions = current["snapshot"]["bound_actions"]["actions"]
                selected = actions[
                    0
                    if frame["source_family"] == "card_reward_selection"
                    else current["default_action_index"]
                ]["bound_action_id"]
                take("bound_action_id", selected)
            else:
                raise ValueError("Crystal Sphere did not reach its native finished page")
            take("label", "Proceed")
            if frame["source_family"] != "map_navigation":
                raise ValueError("Native Crystal Sphere Proceed did not return to the map")
            worker.close()
        finally:
            worker.stop()
        bridge.close()
    finally:
        bridge.stop()
    actions = [
        row["request"]
        for row in records(target / "worker/private-transcript.jsonl.gz")
        if row["request"]["cmd"] == "action"
    ]
    expected = [
        {"cmd": "action", "action": "choose_option", "args": {"option_index": index}}
        for index in [payment, *moves]
    ]
    if actions[: len(expected)] != expected:
        raise ValueError("The current tool and coordinate did not reach the exact native binding")
    return {
        "seed": seed,
        "payment_option": payment,
        "gold_paid": gold - after_gold,
        "debt_cards_added": after_debt - debt,
        "native_tool_and_cell_indices": moves,
        "choices_per_grid": 242,
        "scored_choices_by_checkpoint": scored,
        "native_deliveries": len(actions),
        "returned_to_map": True,
        "clean_shutdown": True,
        "privileged_fixture": True,
    }
