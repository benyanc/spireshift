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
from spireshift.native_atomic_inputs import load
from spireshift.native_compatibility_inputs import check_sources
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
        [cfg["node"], str(root / "scripts/engine-shared-input-v8.mjs")],
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
                        "successor_snapshot_id": receipt.get("successor", {}).get("snapshot_id"),
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
