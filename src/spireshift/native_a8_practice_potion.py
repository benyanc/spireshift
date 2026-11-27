"""Saved and live controls for combat-targeted potions under card selection."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_practice_session as previous
from spireshift import native_win4_game
from spireshift.native_a8_rescue_game import receipt
from spireshift.native_flow_live_v12 import append
from spireshift.native_flow_verification_v12 import records
from spireshift.native_shared_transport import JsonLines
from spireshift.native_win3_control import scripted_verification
from spireshift.native_win4_game import write

SCRIPT = "engine-a8-practice-worker-v2.mjs"
CONTRACT = "native_a8_model_owned_practice_v2"
REGRESSION = "scripts/verify-combat-selector-belt-saved-v1.mjs"
CONTROL_CHOICES = ("use", "discard")


class PracticeWorker(previous.PracticeWorker):
    def __init__(self, ctx: dict[str, Any], target: Path, *, control: bool = False) -> None:
        self.belt_control = control
        with patch.multiple(previous, SCRIPT=SCRIPT, CONTRACT=CONTRACT):
            super().__init__(ctx, target)
        if self.identity.get("projection_contract") != CONTRACT:
            raise ValueError("Unexpected prepared practice worker")

    def request(self, command: str, *, timeout: float = 20, **values: Any) -> dict[str, Any]:
        if command == "initialize":
            values["spec"] = {**values["spec"], "selector_belt_control": self.belt_control}
        return super().request(command, timeout=timeout, **values)


def saved_selector(
    ctx: dict[str, Any], failed: Path, output: Path, deadline: float
) -> dict[str, Any]:
    root = ctx["qualification"].root
    raw = records(failed / "worker/private-transcript.jsonl.gz")
    state, request = None, None
    for row in raw:
        if row["response"].get("type") == "decision":
            state, request = row["response"], row["request"]
    if state is None or request is None or request.get("action") != "play_card":
        raise ValueError("Missing saved native successor of the interrupted delivery")
    (last_receipt,) = (
        row for row in records(failed / "worker/public-receipts.jsonl.gz") if row["index"] == 48
    )
    if (
        state["decision"] != "card_select"
        or state["context"]["act"] != 3
        or state["context"]["floor"] != 5
        or state["selection_owner"] != {"kind": "combat"}
        or last_receipt["delivery"] != "delivered"
        or not last_receipt["action"]["label"].startswith("Play Headbutt")
    ):
        raise ValueError("The interrupted Headbutt successor differs")
    identity = json.loads((failed / "worker/identity.json").read_text())
    result = subprocess.run(
        [ctx["node"], str(root / REGRESSION)],
        input=json.dumps(
            {
                "state": state,
                "shared_projection": identity["shared_projection"],
                "projection": ctx["native"]["projection"],
            }
        ),
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    proof = json.loads(result.stdout)
    converter = JsonLines(
        root,
        [ctx["node"], str(root / "scripts/engine-shared-input-v16.mjs")],
        output / "saved-converter.log",
    )
    try:
        frame = converter.project(proof.pop("snapshot"), proof.pop("reads"), None, deadline)
        if frame["source_family"] != "card_selection" or len(frame["actions"]) != 4:
            raise ValueError("The exact saved selector did not reach the public learner")
        converter.close()
    finally:
        converter.stop()
    return {**proof, "saved_headbutt_delivery_index": 48, "saved_selector_executed": False}


def live_selector(
    ctx: dict[str, Any], target: Path, case: dict[str, Any], operation: str, deadline: float
) -> dict[str, Any]:
    root = ctx["qualification"].root
    target.mkdir()
    setup = target / "setup"
    setup.mkdir()
    start = native_win4_game.prepare(ctx, case, setup, deadline)
    if start["status"] != "ready" or operation not in CONTROL_CHOICES:
        raise ValueError("Require a declared fresh selector diagnostic")
    native = PracticeWorker(ctx, target / "worker", control=True)
    converter = None
    trace = target / "scripted-public.jsonl.gz"
    frame: dict[str, Any] = {}
    count = 0

    def observe(row: dict[str, Any]) -> dict[str, Any]:
        assert converter is not None
        return converter.project(row["snapshot"], row["reads"], None, deadline)

    def take(prefix: str) -> None:
        nonlocal frame, count
        assert converter is not None
        index = next(
            i
            for i, candidate in enumerate(frame["public_input"]["candidates"])
            if candidate["label"].startswith(prefix)
        )
        binding = frame["actions"][index]
        choice = {
            "action_index": index,
            "binding_id": frame["binding_id"],
            "bound_action_id": binding["bound_action_id"],
        }
        append(trace, {"kind": "policy_input", "frame": frame})
        result = native.request(
            "step",
            snapshot_id=frame["observation"]["snapshot_id"],
            action_index=binding["raw_index"],
        )
        if result["delivery_domain"] != "native":
            raise ValueError("Diagnostic actions must deliver to the native owner")
        ack = receipt(frame, choice, "native", result["snapshot"]["snapshot_id"])
        converter.commit(choice, ack, deadline)
        append(trace, {"kind": "policy_choice", "choice": choice, "receipt": ack})
        frame = observe(result)
        count += 1

    def facts() -> tuple[int, list[tuple[str, int]], int, list[str]]:
        ctx_public = frame["public_input"]["context"]
        player = ctx_public["persistent"]["player"]
        combat = ctx_public["interaction"]["content"]["context"]
        health = player["hp"] + combat["player"]["block"]
        enemies = sorted((e["definition_id"], e["hp"] + e["block"]) for e in combat["enemies"])
        labels = [a["label"] for a in frame["public_input"]["candidates"]]
        return health, enemies, len(player["potions"]), labels

    try:
        converter = JsonLines(
            root,
            [ctx["node"], str(root / "scripts/engine-shared-input-v16.mjs")],
            target / "converter.log",
        )
        native.request(
            "load",
            seed=start["seed"],
            save_json=(root / start["save_path"]).read_text(),
            timeout=25,
        )
        frame = observe(native.request("belt_fixture", timeout=25))
        take("Play Defend")
        take("Play Defend")
        take("Play Headbutt")
        if frame["source_family"] != "card_selection":
            raise ValueError("The native Headbutt must open its actual card selector")
        hp, enemies, slots, labels = facts()
        if slots != 1 or not {"Use Foul Potion", "Discard Foul Potion"}.issubset(labels):
            raise ValueError("Native use and discard must both reach the selector")
        take("Use Foul Potion" if operation == "use" else "Discard Foul Potion")
        if frame["source_family"] != "card_selection":
            raise ValueError("The queued operation must retain the exact card owner")
        queued_hp, queued_enemies, queued_slots, queued_labels = facts()
        if (queued_hp, queued_enemies, queued_slots) != (hp, enemies, slots) or {
            "Use Foul Potion",
            "Discard Foul Potion",
        }.intersection(queued_labels):
            raise ValueError("The accepted potion may not be resubmitted before it settles")
        take("Confirm Defend")
        end_hp, end_enemies, end_slots, _ = facts()
        delta = 12 if operation == "use" else 0
        if (
            end_slots != 0
            or end_hp != hp - delta
            or end_enemies != sorted((kind, health - delta) for kind, health in enemies)
        ):
            raise ValueError("The exact native potion effect or removal differs after selection")
        append(trace, {"kind": "final_observation", "frame": frame})
        shutdown = native.close()
        converter.close()
    finally:
        if converter is not None:
            converter.stop()
        native.stop()
    if count != 5 or scripted_verification(ctx, target, deadline) != count:
        raise ValueError("Incomplete native potion decision and delivery proof")
    if shutdown["clean_exit"] is not True or shutdown.get("runtime_errors"):
        raise ValueError("Native potion diagnostic did not shut down cleanly")
    return write(
        target / "report.json",
        {
            "status": "combat_selector_potion_verified",
            "operation": operation,
            "seed": start["seed"],
            "native_deliveries": count,
            "queued_once": True,
            "native_removed_after_card_answer": True,
            "native_damage_per_target": delta,
            "opponents": len(enemies),
            "clean_worker_shutdown": True,
            "optimizer_updates": 0,
            "diagnostic_only": True,
        },
    )
