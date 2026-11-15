"""Rebuild delivered checkpoint choices from sealed public observations; no games."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_inputs_v4 import load
from spireshift.native_live_policy import LivePolicy
from spireshift.native_shared_transport import JsonLines
from spireshift.native_structured_state import load as load_state


def records(path: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt") as file:
        for line in file:
            value: dict[str, Any] = json.loads(line)
            yield value


def same(expected: Any, saved: Any) -> bool:
    if isinstance(expected, dict) and isinstance(saved, dict):
        return expected.keys() == saved.keys() and all(
            same(v, saved[k]) for k, v in expected.items()
        )
    if isinstance(expected, float):
        # JSON has one number type: the Node bridge writes Python's 0.0 as 0.
        # Allow that spelling only for continuous fields; booleans and discrete
        # action/ownership fields retain their exact types below.
        return type(saved) in (int, float) and math.isclose(
            expected, saved, abs_tol=1e-11, rel_tol=0
        )
    if isinstance(expected, list) and isinstance(saved, list):
        return len(expected) == len(saved) and all(
            same(a, b) for a, b in zip(expected, saved, strict=True)
        )
    return type(expected) is type(saved) and expected == saved


def verify_reward_guidance(
    root: dict[str, Any],
    action: dict[str, Any],
    proof: dict[str, Any],
    journal: list[dict[str, Any]],
) -> None:
    runtime = root["session"]["runtime_instance_id"]
    steps = proof.get("ui_steps")
    initial = proof.get("initial_receipt", {})
    if (
        proof.get("semantic_contract") != "reward_proceed_with_guidance_v1"
        or initial.get("delivery") != "delivered"
        or initial.get("action", {}).get("bound_action_id") != action["bound_action_id"]
        or initial.get("attribution", {}).get("runtime_instance_id") != runtime
        or not isinstance(steps, list)
        or len(steps) > 4
        or len(steps) != len(journal)
    ):
        raise ValueError("Unverified reward guidance trace")
    warning = confirmed = False
    for step, recorded in zip(steps, journal, strict=True):
        snapshot, control, receipt = (step[k] for k in ("snapshot", "action", "receipt"))
        menu = snapshot["bound_actions"]
        if (
            snapshot["session"]["runtime_instance_id"] != runtime
            or menu["status"] != "complete"
            or menu["total_count"] != menu["materialized_count"]
            or menu["total_count"] != len(menu["actions"])
            or control not in menu["actions"]
            or receipt["delivery"] != "delivered"
            or receipt["attribution"]["runtime_instance_id"] != runtime
            or receipt["action"]["bound_action_id"] != control["bound_action_id"]
            or recorded["ui_kind"] != step["kind"]
            or recorded["before_snapshot_id"] != snapshot["snapshot_id"]
            or not same(recorded["action"], control)
            or not same(recorded["receipt"], receipt)
        ):
            raise ValueError("Reward guidance differs from its actual delivered UI receipt")
        if step["kind"] == "tutorial":
            surface = snapshot["interaction"]["content"]["surface"]
            if (
                snapshot["interaction"]["kind"] != "tutorial"
                or surface["stage"] != "confirmation"
                or control["verb"] != "activate"
                or control.get("subject_referent_id") is not None
                or control["arguments"]
                or not any(
                    o["semantic_id"] == "dismiss_tutorial"
                    and o["enabled"] is True
                    and o["label"] == control["label"]
                    for o in surface["options"]
                )
            ):
                raise ValueError("Reward tutorial acknowledgement attempted gameplay")
            if surface["tutorial_id"] == "combat_reward_ftue":
                if warning or confirmed:
                    raise ValueError("Repeated reward warning")
                warning = True
        elif step["kind"] == "confirmation":
            if (
                not warning
                or confirmed
                or snapshot["interaction"]["kind"] != "reward_claim"
                or snapshot["interaction"]["interaction_id"]
                != root["interaction"]["interaction_id"]
                or root["interaction"]["content"]["surface"].get("proceed_skips_remaining_rewards")
                is not True
                or not root["interaction"]["content"]["surface"].get("rewards")
                or not same(root["persistent"], snapshot["persistent"])
                or not same(root["interaction"]["content"], snapshot["interaction"]["content"])
                or not same(root["referents"], snapshot["referents"])
                or not same(root["bound_actions"], snapshot["bound_actions"])
                or not same(action, control)
            ):
                raise ValueError("Reward confirmation changed the original state or control")
            confirmed = True
        else:
            raise ValueError("Unknown reward UI step")


def verify_atomic_completion(
    row: dict[str, Any],
    frame: dict[str, Any],
    choice: dict[str, Any],
    snapshot: dict[str, Any],
) -> None:
    """Completion evidence belongs to this macro, not a previous UI transaction."""
    binding = frame["actions"][choice["action_index"]]
    action = snapshot["bound_actions"]["actions"][binding["raw_index"]]
    proof = row["proof"]
    chosen = [a["referent_id"] for a in action.get("arguments", []) if a["role"] == "selected_card"]
    cancel = action["verb"] == "cancel"
    steps = proof["steps"]
    if (
        row["root_bound_action_id"] != choice["bound_action_id"]
        or row["root_snapshot_id"] != frame["observation"]["snapshot_id"]
        or proof["root_snapshot_id"] != row["root_snapshot_id"]
        or proof["status"] != ("canceled" if cancel else "committed")
        or proof["game_committed"] is not (not cancel)
        or proof["chosen_card_ids"] != chosen
        or not proof["request_id"]
        or not steps
        or len(steps) > len(chosen) + 3
        or any(
            s["accepted"] is not True
            or not s["candidate_id"]
            or s["kind"] not in {"select", "preview", "confirm", "cancel"}
            for s in steps
        )
        or [s["card_id"] for s in steps if s["kind"] == "select"] != chosen
        or (
            steps[-1]["kind"] != ("cancel" if cancel else "confirm")
            and not (
                not cancel
                and steps[-1]["kind"] == "select"
                and proof.get("automatic_commit_allowed") is True
                and proof.get("maximum_selection") == len(chosen)
            )
        )
    ):
        raise ValueError("Unverified committed card choice; preserve all evidence")


def verify_bundle_completion(
    row: dict[str, Any], frame: dict[str, Any], choice: dict[str, Any], snapshot: dict[str, Any]
) -> str:
    proof = row["proof"]
    action = snapshot["bound_actions"]["actions"][
        frame["actions"][choice["action_index"]]["raw_index"]
    ]
    pack = next(
        b
        for b in snapshot["interaction"]["content"]["surface"]["bundles"]
        if b["entity_id"] == action["subject_referent_id"]
    )
    preview = proof["preview_snapshot"]
    surface = preview["interaction"]["content"]["surface"]
    confirm, receipt = proof["confirm_action"], proof["confirm_receipt"]
    runtime = snapshot["session"]["runtime_instance_id"]
    if (
        proof["contract"] != "committed_public_bundle_choice_v1"
        or proof["game_committed"] is not True
        or proof["root_snapshot_id"] != snapshot["snapshot_id"]
        or proof["root_bound_action_id"] != choice["bound_action_id"]
        or proof["selected_bundle_entity_id"] != pack["entity_id"]
        or preview["session"]["runtime_instance_id"] != runtime
        or preview["interaction"]["interaction_id"] != snapshot["interaction"]["interaction_id"]
        or surface["stage"] != "preview"
        or surface["selected_bundle_entity_id"] != pack["entity_id"]
        or surface["bundles"] != [pack]
        or surface["can_confirm"] is not True
        or confirm not in preview["bound_actions"]["actions"]
        or confirm["verb"] != "confirm"
        or confirm["subject_referent_id"] != pack["entity_id"]
        or receipt["delivery"] != "delivered"
        or receipt["action"]["bound_action_id"] != confirm["bound_action_id"]
        or receipt["attribution"]["runtime_instance_id"] != runtime
        or not proof["successor_snapshot_id"]
        or proof["successor_snapshot_id"] == preview["snapshot_id"]
    ):
        raise ValueError("Pack preview/confirmation does not prove the selected committed choice")
    return str(proof["successor_snapshot_id"])


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
    model, _, _ = load_state(root / cfg["workspace"] / f"imports/player-{case['player']}.json")
    policy = LivePolicy(model, context["score"], case["seed"])
    converter = JsonLines(
        root,
        [cfg["node"], str(root / "scripts/engine-shared-input-v12.mjs")],
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
                    if frame != row["frame"]:
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
                    if frame != row["frame"]:
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
        summary = identified(directory / "report.json")
        expected_count = (
            summary["policy_decisions"]
            if host == "native"
            else summary["probe"]["policy_decisions"]
        )
        if (
            policy.pending is not None
            or policy.decisions != expected_count
            or not 0 < expected_count <= cfg["maximum_decisions"]
            or (
                expected_count < cfg["maximum_decisions"]
                and (frame is None or frame.get("terminal") is not True)
            )
        ):
            raise ValueError("Incomplete saved prefix or unacknowledged checkpoint choice")
        converter.close()
        return policy.decisions
    finally:
        converter.stop()


def audit(root: Path, recipe: Path, output: Path) -> dict[str, Any]:
    started = time.monotonic()
    context = load(root, recipe)
    cfg = context["config"]
    report = identified(root / cfg["workspace"] / "report.json")
    check_sources(root, report["sources"])
    check_sources(root, report["evidence"])
    if output.exists():
        raise FileExistsError("Preserve the saved live adapter verification result")
    output.mkdir(parents=True)
    results = []
    for case in cfg["cases"]:
        for host in ("native", "official"):
            count = verify_host(
                root,
                context,
                case,
                host,
                root / cfg["workspace"] / case["key"] / host,
                output,
                started + 120,
            )
            results.append({"key": case["key"], "host": host, "verified_decisions": count})
    check_sources(root, report["sources"])
    check_sources(root, report["evidence"])
    body = {
        "schema_version": "native-live-checkpoint-verification-v1",
        "source_report_id": report["report_id"],
        "valid": True,
        "cases": results,
        "games_launched": 0,
        "optimizer_updates": 0,
        "full_input_equivalence_granted": False,
        "original_weights_and_all_Adam_unchanged": True,
        "verifier_sha256": _sha_file(Path(__file__)),
        "wall_seconds": time.monotonic() - started,
    }
    body["report_id"] = manifest_identifier(body)
    atomic_json(output / "report.json", body)
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(audit(Path.cwd(), args.recipe.resolve(), args.output.resolve()), indent=2))
        return 0
    except (ValueError, OSError, StopIteration, TimeoutError) as error:
        print(json.dumps({"valid": False, "error": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
