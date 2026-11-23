"""Strict paired inputs and reconstruction of actual official selector receipts."""

from __future__ import annotations

import time
from contextlib import suppress
from pathlib import Path
from typing import Any

from spireshift.native_a8_rescue_game import receipt
from spireshift.native_atomic_verification_v2 import verify_atomic_completion
from spireshift.native_flow_verification_v12 import records
from spireshift.native_lifecycle_contract import check_frame
from spireshift.native_mixed_rest_session import conversion
from spireshift.native_systematic_live_v1 import compare_frames


class PairedPolicy:
    def __init__(self, frames: list[dict[str, Any]], choices: list[int]) -> None:
        if len(frames) != len(choices) + 1:
            raise ValueError("Missing native final successor")
        self.expected = frames
        self.choices = choices
        self.frames: list[dict[str, Any]] = []
        self.decisions = 0
        self.pending: tuple[dict[str, Any], dict[str, Any]] | None = None
        self.difference: dict[str, Any] | None = None

    def compare(self, frame: dict[str, Any]) -> None:
        comparison = compare_frames([self.expected[self.decisions]], [frame])
        if not comparison["equal"]:
            self.difference = {"decision": self.decisions, **comparison}
            raise ValueError(f"Native/official public input differs at choice {self.decisions}")

    def choose(self, frame: dict[str, Any]) -> dict[str, Any]:
        if self.pending is not None or self.decisions >= len(self.choices):
            raise ValueError("Unowned or undeclared official choice")
        self.compare(frame)
        index = self.choices[self.decisions]
        choice = {
            "binding_id": frame["binding_id"],
            "action_index": index,
            "bound_action_id": frame["actions"][index]["bound_action_id"],
            "optimizer_updates": 0,
            "privileged_fixture": True,
        }
        self.pending = frame, choice
        self.frames.append(frame)
        return choice

    def acknowledge(self, acknowledgement: dict[str, Any]) -> None:
        if self.pending is None:
            raise ValueError("No owned official delivery")
        frame, choice = self.pending
        if (
            acknowledgement.get("delivery") != "delivered"
            or acknowledgement.get("binding_id") != frame["binding_id"]
            or acknowledgement.get("bound_action_id") != choice["bound_action_id"]
            or acknowledgement.get("runtime_instance_id")
            != frame["observation"]["runtime_instance_id"]
            or acknowledgement.get("before_snapshot_id") != frame["observation"]["snapshot_id"]
            or not acknowledgement.get("successor_snapshot_id")
        ):
            raise ValueError("Uncertain or misbound official delivery")
        self.pending = None
        self.decisions += 1

    def observe_successor(self, frame: dict[str, Any]) -> None:
        if self.pending is not None or self.decisions != len(self.choices):
            raise ValueError("Incomplete official choice chain")
        # Let the client's finally request clean shutdown even when this last
        # observation differs. The coordinator rejects the pair after shutdown.
        with suppress(ValueError):
            self.compare(frame)
        self.frames.append(frame)


def audit(
    ctx: dict[str, Any], directory: Path, policy: PairedPolicy, deadline: float
) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    delivered: dict[str, list[dict[str, Any]]] = {}
    completions: dict[str, dict[str, Any]] = {}
    local: dict[str, dict[str, Any]] = {}
    for row in records(directory / "live-public.jsonl.gz"):
        kind = row["kind"]
        if kind in {"policy_input", "diagnostic_successor"}:
            observations.append(row)
        elif kind == "receipt":
            delivered.setdefault(row["before_snapshot_id"], []).append(row)
        elif kind in {"atomic_selection_completion", "local_answer_factor_completion"}:
            target = completions if kind == "atomic_selection_completion" else local
            if row["root_snapshot_id"] in target:
                raise ValueError("Duplicate selection completion")
            target[row["root_snapshot_id"]] = row
    if len(observations) != len(policy.expected) or len(policy.frames) != len(observations):
        raise ValueError("Incomplete official raw observations")
    bridge = conversion(ctx, directory / f"saved-audit-converter-{time.time_ns()}.log")
    frames = []
    previous = None
    try:
        for number, row in enumerate(observations):
            snapshot = row["snapshot"]
            if previous is not None:
                before, choice, domain = previous
                bridge.commit(
                    choice, receipt(before, choice, domain, snapshot["snapshot_id"]), deadline
                )
            frame = bridge.project(snapshot, row["reads"], None, deadline)
            check_frame(({"snapshot": snapshot, "reads": row["reads"]}, frame))
            if frame != policy.frames[number]:
                raise ValueError("Saved public reads do not reconstruct the live offered frame")
            frames.append(frame)
            if number == len(policy.choices):
                break
            index = policy.choices[number]
            binding = frame["actions"][index]
            action = snapshot["bound_actions"]["actions"][binding["raw_index"]]
            (actual,) = delivered[snapshot["snapshot_id"]]
            sdk = actual["receipt"]
            if (
                actual["action"] != action
                or sdk["delivery"] != "delivered"
                or sdk["action"]["bound_action_id"] != action["bound_action_id"]
                or sdk["action"]["verb"] != action["verb"]
                or sdk["action"].get("subject_referent_id") != action.get("subject_referent_id")
                or sdk["action"]["arguments"] != action["arguments"]
                or sdk["attribution"]["runtime_instance_id"]
                != frame["observation"]["runtime_instance_id"]
            ):
                raise ValueError("Saved SDK receipt does not own the chosen current action")
            format_ = snapshot["interaction"]["content"]["surface"].get("selection_contract")
            domain = (
                "local_answer_factor"
                if format_ == "factorized_ordered_card_answer_v1" and action["verb"] == "select"
                else "native"
            )
            if domain == "local_answer_factor":
                proof = local.pop(snapshot["snapshot_id"])
                if (
                    proof["root_bound_action_id"] != action["bound_action_id"]
                    or proof["proof"]["steps"]
                    or proof["proof"]["request_id"] != sdk["request_id"]
                    or proof["proof"]["game_committed"] is not False
                    or proof["proof"]["native_selected_card_ids"]
                ):
                    raise ValueError("A local factor delivered game inputs")
            elif format_ in {
                "atomic_public_card_choice_v1",
                "factorized_ordered_card_answer_v1",
            } and action["verb"] in {"confirm", "cancel"}:
                proof = completions.pop(snapshot["snapshot_id"])
                verify_atomic_completion(
                    proof,
                    frame,
                    {"action_index": index, "bound_action_id": action["bound_action_id"]},
                    snapshot,
                )
                if proof["proof"]["request_id"] != sdk["request_id"]:
                    raise ValueError("Selection completion belongs to another SDK request")
            previous = frame, {"binding_id": frame["binding_id"], "action_index": index}, domain
        bridge.close()
    finally:
        bridge.stop()
    if local or completions:
        raise ValueError("Unowned extra selector completions")
    comparison = compare_frames(policy.expected, frames)
    if not comparison["equal"]:
        raise ValueError("The saved full public input comparison differs")
    return {
        **comparison,
        "actual_sdk_deliveries_verified": len(policy.choices),
        "all_public_reads_reconstructed": True,
    }
