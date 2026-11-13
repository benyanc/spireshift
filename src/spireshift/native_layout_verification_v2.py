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
from spireshift.native_layout_inputs_v4 import load
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
        [cfg["node"], str(root / "scripts/engine-shared-input-v6.mjs")],
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
            choice_seen = False
            for row in records(directory / "live-public.jsonl.gz"):
                if row["kind"] == "policy_input":
                    frame = converter.project(row["snapshot"], row["reads"], None, deadline)
                    if frame != row["frame"]:
                        raise ValueError(
                            "Official shared input differs from complete source observation"
                        )
                    if not frame["terminal"]:
                        choice = policy.choose(frame)
                        choice_seen = False
                elif row["kind"] == "policy_choice":
                    saved_choice = {k: v for k, v in row["choice"].items() if k != "command"}
                    if (
                        row["choice"].get("command") != "choose"
                        or choice is None
                        or not same(choice, saved_choice)
                    ):
                        raise ValueError("Official frozen checkpoint choice/probability changed")
                    choice_seen = True
                elif row["kind"] == "receipt" and choice is not None and frame is not None:
                    if not choice_seen:
                        raise ValueError(
                            "Official gameplay receipt preceded its frozen checkpoint choice"
                        )
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
