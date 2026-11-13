"""Reconstruct every scripted choice, actual receipt and final successor from raw streams."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.native_e2e_contract import difference_paths
from spireshift.native_flow_verification_v12 import (
    records,
    same,
    verify_atomic_completion,
    verify_bundle_completion,
    verify_reward_guidance,
)
from spireshift.native_shared_transport import JsonLines
from spireshift.native_shop_live import ScriptedPolicy


def verify_host(
    root: Path,
    context: dict[str, Any],
    case: dict[str, Any],
    host: str,
    directory: Path,
    output: Path,
    deadline: float,
) -> int:
    cfg = context["config"]
    policy = ScriptedPolicy(case["instructions"])
    converter = JsonLines(
        root,
        [cfg["node"], str(root / "scripts/engine-shared-input-v16.mjs")],
        output / f"{case['key']}-{host}.log",
    )
    try:
        if host == "native":
            observations = iter(records(directory / "worker/public-observations.jsonl.gz"))
            receipts = iter(records(directory / "worker/public-receipts.jsonl.gz"))
            frame = choice = None
            for row in records(directory / "shared-public.jsonl.gz"):
                if row["kind"] == "policy_input":
                    raw = next(observations)
                    frame = converter.project(raw["snapshot"], raw["reads"], None, deadline)
                    if difference_paths(frame, row["frame"]):
                        raise ValueError(
                            "Native shared input differs from complete source observation"
                        )
                    if not frame["terminal"]:
                        choice = policy.choose(frame)
                elif row["kind"] == "policy_choice":
                    if choice is None or frame is None or not same(choice, row["choice"]):
                        raise ValueError("Native frozen checkpoint choice/probability changed")
                    receipt = next(receipts)
                    action = frame["actions"][choice["action_index"]]
                    if (
                        receipt["snapshot_id"] != frame["observation"]["snapshot_id"]
                        or receipt["action"]["bound_action_id"] != action["bound_action_id"]
                        or receipt["delivery"] != "delivered"
                        or receipt["successor_snapshot_id"]
                        != row["receipt"]["successor_snapshot_id"]
                    ):
                        raise ValueError(
                            "Native actual delivery does not match the checkpoint choice"
                        )
                    policy.acknowledge(row["receipt"])
                    converter.commit(choice, row["receipt"], deadline)
                    choice = None
                elif row["kind"] == "diagnostic_successor":
                    raw = next(observations)
                    final = converter.project(raw["snapshot"], raw["reads"], None, deadline)
                    if difference_paths(final, row["frame"]):
                        raise ValueError("Native final successor differs from raw observation")
                    policy.observe_successor(final)
            if next(observations, None) is not None or next(receipts, None) is not None:
                raise ValueError("Extra unverified native observation or delivery")
        else:
            frame = choice = None
            raw_snapshot = None
            choice_seen = False
            atomic_complete = False
            pack_successor = None
            proceed_successor = None
            reward_ui_receipts: list[dict[str, Any]] = []
            for row in records(directory / "live-public.jsonl.gz"):
                if row["kind"] == "policy_input":
                    raw_snapshot = row["snapshot"]
                    frame = converter.project(row["snapshot"], row["reads"], None, deadline)
                    if difference_paths(frame, row["frame"]):
                        raise ValueError(
                            "Official shared input differs from complete source observation"
                        )
                    if not frame["terminal"]:
                        choice = policy.choose(frame)
                        choice_seen = False
                        atomic_complete = False
                        pack_successor = None
                        proceed_successor = None
                        reward_ui_receipts = []
                elif row["kind"] == "policy_choice":
                    saved_choice = {k: v for k, v in row["choice"].items() if k != "command"}
                    if (
                        row["choice"].get("command") != "choose"
                        or choice is None
                        or not same(choice, saved_choice)
                    ):
                        raise ValueError("Official frozen checkpoint choice/probability changed")
                    choice_seen = True
                elif row["kind"] == "atomic_selection_completion":
                    if not choice_seen or choice is None or frame is None or atomic_complete:
                        raise ValueError("Unowned or duplicate selection completion")
                    if raw_snapshot is None:
                        raise ValueError("Missing source selection snapshot")
                    verify_atomic_completion(row, frame, choice, raw_snapshot)
                    atomic_complete = True
                elif row["kind"] == "bundle_selection_completion":
                    if (
                        not choice_seen
                        or choice is None
                        or frame is None
                        or raw_snapshot is None
                        or pack_successor is not None
                    ):
                        raise ValueError("Unowned or duplicate pack completion")
                    pack_successor = verify_bundle_completion(row, frame, choice, raw_snapshot)
                elif row["kind"] == "reward_ui_receipt":
                    if not choice_seen or choice is None or len(reward_ui_receipts) >= 4:
                        raise ValueError("Unowned reward UI delivery")
                    reward_ui_receipts.append(row)
                elif row["kind"] == "reward_proceed_completion":
                    if (
                        not choice_seen
                        or choice is None
                        or frame is None
                        or raw_snapshot is None
                        or proceed_successor is not None
                    ):
                        raise ValueError("Unowned or duplicate reward completion")
                    proof = row["proof"]
                    after = proof["successor_snapshot"]
                    action = raw_snapshot["bound_actions"]["actions"][
                        frame["actions"][choice["action_index"]]["raw_index"]
                    ]
                    verify_reward_guidance(raw_snapshot, action, proof, reward_ui_receipts)
                    if (
                        proof["root_snapshot_id"] != raw_snapshot["snapshot_id"]
                        or proof["root_bound_action_id"] != choice["bound_action_id"]
                        or raw_snapshot["interaction"]["kind"] != "reward_claim"
                        or raw_snapshot["interaction"]["content"]["surface"].get("can_proceed")
                        is not True
                        or action["verb"] != "activate"
                        or action.get("subject_referent_id") is not None
                        or action["arguments"]
                        or action["label"]
                        not in {
                            "Proceed",
                            "Skip remaining rewards and continue",
                            "Continue from rewards",
                        }
                        or after["session"]["runtime_instance_id"]
                        != raw_snapshot["session"]["runtime_instance_id"]
                        or after["interaction"]["kind"] in {"reward_claim", "tutorial", "no_action"}
                        or after["snapshot_id"] == raw_snapshot["snapshot_id"]
                        or after["interaction"]["interaction_id"]
                        == raw_snapshot["interaction"]["interaction_id"]
                        or after["completeness"]["status"] != "complete"
                    ):
                        raise ValueError("Reward Continue has no verified owner departure")
                    proceed_successor = after["snapshot_id"]
                elif row["kind"] == "receipt" and choice is not None and frame is not None:
                    if not choice_seen:
                        raise ValueError(
                            "Official gameplay receipt preceded its frozen checkpoint choice"
                        )
                    if (
                        frame["public_input"]["context"]["interaction"]["content"]["surface"].get(
                            "selection_contract"
                        )
                        == "atomic_public_card_choice_v1"
                        and frame["public_input"]["candidates"][choice["action_index"]]["verb"]
                        in {"confirm", "cancel"}
                        and not atomic_complete
                    ):
                        raise ValueError("Selection receipt has no verified UI completion")
                    if (
                        frame["source_family"] == "card_bundle_selection"
                        and frame["public_input"]["context"]["interaction"]["content"][
                            "surface"
                        ].get("selection_contract")
                        == "committed_public_bundle_choice_v1"
                        and (
                            pack_successor is None
                            or pack_successor != row.get("semantic_successor_snapshot_id")
                        )
                    ):
                        raise ValueError("Pack action has no complete semantic delivery")
                    candidate = frame["public_input"]["candidates"][choice["action_index"]]
                    if (
                        frame["source_family"] == "reward_claim"
                        and candidate["verb"] == "activate"
                        and candidate["subject"] is None
                        and candidate["label"]
                        in {
                            "Proceed",
                            "Skip remaining rewards and continue",
                            "Continue from rewards",
                        }
                        and (
                            not proceed_successor
                            or proceed_successor != row.get("semantic_successor_snapshot_id")
                        )
                    ):
                        raise ValueError("Reward receipt preceded owner departure")
                    receipt = row["receipt"]
                    if (
                        row["before_snapshot_id"] != frame["observation"]["snapshot_id"]
                        or row["action"]["bound_action_id"] != choice["bound_action_id"]
                        or receipt["action"]["bound_action_id"] != choice["bound_action_id"]
                    ):
                        raise ValueError("Official delivery targeted a different current action")
                    ack = {
                        "binding_id": frame["binding_id"],
                        "delivery": receipt["delivery"],
                        "bound_action_id": choice["bound_action_id"],
                        "runtime_instance_id": receipt["attribution"]["runtime_instance_id"],
                        "before_snapshot_id": row["before_snapshot_id"],
                        "successor_snapshot_id": pack_successor
                        or proceed_successor
                        or receipt.get("successor", {}).get("snapshot_id"),
                    }
                    policy.acknowledge(ack)
                    converter.commit(choice, ack, deadline)
                    choice = None
                elif row["kind"] == "diagnostic_successor":
                    final = converter.project(row["snapshot"], row["reads"], None, deadline)
                    if difference_paths(final, row["frame"]):
                        raise ValueError("Official final successor differs from raw observation")
                    policy.observe_successor(final)
        summary = identified(directory / "report.json")
        expected_count = (
            summary["policy_decisions"]
            if host == "native"
            else summary["probe"]["policy_decisions"]
        )
        if (
            policy._fixture_pending is not None
            or policy.decisions != expected_count
            or not 0 < expected_count <= len(case["instructions"])
            or expected_count > cfg["maximum_decisions"]
            or not policy.done
            or len(policy.frames) != expected_count + 1
        ):
            raise ValueError("Incomplete declared shop effect or unacknowledged choice")
        converter.close()
        if host == "official":
            from spireshift.native_shop_verification import verify_shop_proofs

            verify_shop_proofs(root, cfg["node"], directory, output, deadline)
        return policy.decisions
    finally:
        converter.stop()
