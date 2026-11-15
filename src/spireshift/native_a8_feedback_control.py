"""Short native controls for the confirmation and ending contracts."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.native_a8_feedback_host import FeedbackWorker
from spireshift.native_a8_rescue_game import receipt
from spireshift.native_compatibility_contract import verified
from spireshift.native_flow_live_v12 import append
from spireshift.native_shared_transport import JsonLines
from spireshift.native_win3_control import scripted_verification
from spireshift.native_win4_game import write

MECHANICS = "docs/evidence/native-a8-own-mechanics-v1.json"
END_KEYS = ("native_game_over", "native_victory_room", "native_player_dead")


def check_endings(root: Path, node: str, mechanics: dict[str, Any]) -> dict[str, Any]:
    saved = verified(root, mechanics["architect"]["matched_saving_disabled_diagnostic"])
    match = identified(saved)
    raw = json.loads(saved.with_name("native-check.json").read_text())
    (identity,) = (v["engine_identity"] for v in raw["stages"] if "engine_identity" in v)
    if (
        match["status"] != "benchmark_victory_endpoint_verified"
        or not raw["checks"]["native_explicit_victory"]
        or match["natural_start_evaluation_wins"] != 0
        or {k: identity[k] for k in END_KEYS} != mechanics["architect"]["native_flags"]
    ):
        raise ValueError("Require the exact saved victory identity")
    path = verified(root, mechanics["study"]["report"])
    study = identified(path)
    cases = [{k: identity[k] for k in END_KEYS}]
    for key, game in study["games"].items():
        episode = identified(path.parent / "chunks" / key / "report.json")
        if episode["report_id"] != game["episode_report_id"] or game["outcome"] != "loss":
            raise ValueError("Saved loss identity differs")
        old = episode["native_ending"]["private_final_identity"]
        cases.append({k: old[k] for k in END_KEYS})
    code = """
import assert from "node:assert/strict";
import {checkNativeEnding} from "./scripts/engine-native-ending-v1.mjs";
const cases = JSON.parse(process.argv[1]);
for (const [index, identity] of cases.entries()) {
  const victory = index === 0;
  const ending = {status: "candidate_terminal", victory};
  assert.equal(checkNativeEnding(ending, identity), true);
  assert.throws(() => checkNativeEnding({...ending, victory: !victory}, identity), /disagrees/);
}
console.log(cases.length);
"""
    count = int(
        subprocess.check_output(
            [node, "--input-type=module", "-e", code, json.dumps(cases)],
            text=True,
            cwd=root,
            timeout=20,
        )
    )
    if count != 73:
        raise ValueError("Require one saved victory and all 72 verified losses")
    return {"saved_correct_endings_accepted": count, "flipped_labels_rejected": count}


def trial(ctx: dict[str, Any], target: Path, seed: str, deadline: float) -> dict[str, Any]:
    root = ctx["qualification"].root
    target.mkdir()
    native = FeedbackWorker(ctx, target / "worker", control=True)
    converter = None
    trace = target / "scripted-public.jsonl.gz"
    frame: dict[str, Any] = {}
    delivered = 0

    def observe(result: dict[str, Any]) -> dict[str, Any]:
        assert converter is not None
        return converter.project(result["snapshot"], result["reads"], None, deadline)

    def take(label: str) -> None:
        nonlocal frame, delivered
        assert converter is not None
        (index,) = (
            i
            for i, candidate in enumerate(frame["public_input"]["candidates"])
            if candidate["label"] == label
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
            raise ValueError("Modal controls must have a delivered native successor")
        ack = receipt(frame, choice, "native", result["snapshot"]["snapshot_id"])
        converter.commit(choice, ack, deadline)
        append(trace, {"kind": "policy_choice", "choice": choice, "receipt": ack})
        frame = observe(result)
        delivered += 1

    def modal() -> None:
        public = frame["public_input"]
        menu = {(a["verb"], a["label"]) for a in public["candidates"]}
        event = public["context"]["interaction"]["content"]["context"]
        if (
            menu != {("confirm", "Yes"), ("cancel", "No")}
            or event["event_id"] != "ABANDON_RUN_CONFIRMATION"
            or frame["terminal"]
        ):
            raise ValueError("Require two bound modal choices on the live run")

    try:
        converter = JsonLines(
            root,
            [ctx["node"], str(root / "scripts/engine-shared-input-v16.mjs")],
            target / "converter.log",
        )
        native.request("mount", seed=seed)
        frame = observe(native.request("trial_fixture"))
        take("Reject")
        parent = frame["public_input"]
        if "Discard Fire Potion" not in {a["label"] for a in parent["candidates"]}:
            raise ValueError("The Trial control must exercise modal precedence over the belt")
        take("Double Down")
        modal()
        first_popup = frame["binding_id"]
        take("No")
        restored = frame["public_input"]
        if (
            frame["terminal"]
            or restored["context"]["interaction"]["content"]["context"]["event_id"] != "TRIAL"
            or restored["context"]["persistent"] != parent["context"]["persistent"]
            or restored["context"]["reads"] != parent["context"]["reads"]
            or [a["label"] for a in restored["candidates"]]
            != [a["label"] for a in parent["candidates"]]
        ):
            raise ValueError("Cancel did not restore the exact live Trial menu and player state")
        take("Double Down")
        modal()
        if frame["binding_id"] == first_popup:
            raise ValueError("The reopened confirmation reused a stale binding")
        take("Yes")
        append(trace, {"kind": "final_observation", "frame": frame})
        if not frame["terminal"] or frame["ending"]["victory"] is not False:
            raise ValueError("Confirmed abandon did not reach a terminal loss")
        ending = native.request("ending")
        identity = ending["private_final_identity"]
        if (
            ending["native_ending_evidence_agrees"] is not True
            or identity["native_abandoned"] is not True
            or identity["native_victory_room"] is not False
            or identity["pending_abandon_confirmation"] is not False
        ):
            raise ValueError("Require actual native abandonment and a settled modal")
        shutdown = native.close()
        converter.close()
    finally:
        if converter is not None:
            converter.stop()
        native.stop()

    verified_deliveries = scripted_verification(ctx, target, deadline)
    if delivered != 5 or verified_deliveries != delivered or shutdown["clean_exit"] is not True:
        raise ValueError("Incomplete live confirmation control")
    return write(
        target / "report.json",
        {
            "status": "native_confirmation_control_verified",
            "native_deliveries": delivered,
            "cancel_restored_event": True,
            "confirm_native_abandoned": True,
            "native_outcome": "loss",
            "clean_worker_shutdown": True,
            "diagnostic_only": True,
            "optimizer_updates": 0,
        },
    )
