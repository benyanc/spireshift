"""Replay a saved public failure prefix against old/new hosts, with private queue controls.

These finite diagnostic prefixes and deliberate negative controls never become
ordinary experience, wins, or optimizer examples. No full run follows.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_coverage import _read_sealed
from spireshift.engine_experience import read_native_episode
from spireshift.engine_native import _private_path, _require_native_launch_support, _running_games
from spireshift.engine_qualification import (
    EngineQualificationConfig,
    _sha_file,
    load_engine_qualification_config,
)
from spireshift.engine_run import _run_inputs
from spireshift.engine_worker import EngineWorker, worker_helpers
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.full_run_experience import atomic_json

SCRIPT = "engine-potion-queue-worker-v1.mjs"


def verify_queue_checks(
    q: EngineQualificationConfig, reference: dict[str, Any], build_report_id: str
) -> dict[str, Any]:
    """Verify preserved diagnostic evidence without replay or relabelling it as PPO."""
    cfg = json.loads((q.root / reference["config"]).read_text())
    output = _private_path(q.root, cfg["workspace"])
    report = _read_sealed(output / "summary.json")
    if (
        report["report_id"] != reference["report_id"]
        or report["config_id"] != manifest_identifier(cfg)
        or cfg["qualification_config_id"] != q.config_id
        or cfg["repaired_build_report_id"] != build_report_id
        or cfg["legacy_build_report_id"] == build_report_id
        or report["status"] != "queue_controls_pass"
        or report["planned_cases"] != 4
        or report["completed_cases"] != 4
        or report["failed_cases"] != 0
        or report["not_attempted_cases"] != 0
        or report["training_allowed"] is not False
        or report["privileged_fixture"] is not True
        or report["full_run_attempts"] != 0
        or report["optimizer_steps"] != 0
        or report["game_apps_created"] != 0
        or _sha_file(output / "source-at-launch/engine_potion_queue_checks.py")
        != cfg["implementation_sha256"]
        or _sha_file(q.root / cfg["source_episode"]) != cfg["source_episode_sha256"]
    ):
        raise ValueError("Native queued-potion comparison is incomplete or belongs to another host")
    for ref in reference["evidence_files"]:
        if _sha_file(output / ref["path"]) != ref["sha256"]:
            raise ValueError("Saved queue qualification source/controls changed")
    expected = [(mode, i) for mode in ("legacy", "repaired") for i in (1, 2)]
    if len(report["cases"]) != len(expected):
        raise ValueError("Queue comparison case denominator changed")
    for case, (mode, i) in zip(report["cases"], expected, strict=True):
        folder = output / f"{mode}-{i}"
        if (
            json.loads((folder / "result.json").read_text()) != case
            or case["status"] != "pass"
            or case["case"] != f"{mode}-{i}"
            or case["mode"] != mode
            or case["privileged_fixture"] is not True
            or case["training_allowed"] is not False
            or case["private_before"]["pending_card_selection"] is not True
            or case["private_after"]["pending_card_selection"] is not False
        ):
            raise ValueError("Queued-potion saved case binding changed")
        for name, digest in cfg["helpers_sha256"].items():
            if _sha_file(folder / "source-at-launch" / name) != digest:
                raise ValueError("Queued-potion diagnostic helper changed")
        if mode == "repaired":
            pending = case["native_queued_discard"]
            if (
                len(pending) != 1
                or pending[0]["action_id"] is None
                or pending[0]["state"] != "WaitingForExecution"
                or case["private_after"]["pending_potion_discards"]
            ):
                raise ValueError("Native queued discard was not accepted and settled")
        elif (
            "Potion discard delivery is unknown"
            not in case["legacy_error"]["expected_legacy_error"]
        ):
            raise ValueError("Original host failure was not reproduced")
    return {"valid": True, "report_id": report["report_id"], "verified_cases": 4}


def match_saved_choice(observation: dict[str, Any], saved: dict[str, Any]) -> int:
    """Match the complete public state/menu, permitting only candidate reordering."""
    current, prior = observation["model_input"], saved["public_input"]
    old = [manifest_identifier(r) for r in prior["candidates"]]
    new = [manifest_identifier(r) for r in current["candidates"]]
    if manifest_identifier(current["context"]) != manifest_identifier(prior["context"]) or sorted(
        old
    ) != sorted(new):
        raise ValueError("Diagnostic prefix differs from its saved public state/menu")
    selected = old[saved["choice"]["action_index"]]
    matches = [i for i, candidate in enumerate(new) if candidate == selected]
    if len(matches) != 1:
        raise ValueError("Diagnostic action has no unique current public binding")
    return matches[0]


def run_queue_checks(q: EngineQualificationConfig, recipe: Path, node: Path) -> dict[str, Any]:
    cfg = json.loads(recipe.read_text())
    if (
        cfg.get("schema_version") != "native-potion-queue-checks-config-v1"
        or cfg.get("qualification_config_id") != q.config_id
        or cfg.get("implementation_sha256") != _sha_file(Path(__file__))
        or cfg.get("helpers_sha256") != worker_helpers(q.root, SCRIPT)
        or cfg.get("repeats") != 2
        or cfg.get("maximum_wall_seconds") != 180
        or cfg.get("training_allowed") is not False
    ):
        raise ValueError("Expected frozen finite queue qualification recipe")
    _require_native_launch_support()
    if _running_games():
        raise ValueError("Close the game before isolated queue checks")
    source = _private_path(q.root, cfg["source_episode"])
    if _sha_file(source) != cfg["source_episode_sha256"]:
        raise ValueError("Original failed episode changed")
    doc = json.loads(source.read_text())
    saved = read_native_episode(source, doc["binding"])
    decisions = saved["decisions"]
    if (
        saved["status"] != "failed"
        or doc["binding"]["partition"] != "train"
        or decisions[-1]["public_input"]["context"]["interaction"]["kind"] != "card_selection"
        or decisions[-1]["public_input"]["candidates"][decisions[-1]["choice"]["action_index"]][
            "verb"
        ]
        != "activate"
    ):
        raise ValueError("Queue fixture requires the original failed public card-selection prefix")
    output = _private_path(q.root, cfg["workspace"])
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "recipe.json", cfg)
    launched = output / "source-at-launch"
    launched.mkdir()
    for name in ("engine_potion_queue_checks.py", "engine_worker.py", "engine_projection_cache.py"):
        (launched / name).write_bytes((q.root / "src/spireshift" / name).read_bytes())
    results, error = [], None
    started = time.monotonic()
    for mode in ("legacy", "repaired"):
        inputs = _run_inputs(q, q.root / cfg[f"{mode}_run_config"])
        if inputs["inputs"]["build_report_id"] != cfg[f"{mode}_build_report_id"]:
            raise ValueError("Queue comparison host changed")
        for repeat in range(2):
            if error:
                break
            if time.monotonic() - started > 150:
                raise TimeoutError("Finite queue check wall cap")
            folder = output / f"{mode}-{repeat + 1}"
            worker = EngineWorker(q, inputs, folder, node, cfg["helpers_sha256"], script=SCRIPT)
            try:
                observation = worker.request("mount", seed=doc["binding"]["native_seed"])
                for saved_row in decisions[:-1]:
                    index = match_saved_choice(observation, saved_row)
                    observation = worker.request(
                        "step",
                        action_index=index,
                        snapshot_id=observation["snapshot"]["snapshot_id"],
                    )
                index = match_saved_choice(observation, decisions[-1])
                before = worker.request("inspect_queue")
                if before["identity"]["pending_card_selection"] is not True:
                    raise ValueError("The native card action is not gathering a choice")
                args = {
                    "action_index": index,
                    "snapshot_id": observation["snapshot"]["snapshot_id"],
                }
                if mode == "legacy":
                    failure = worker.request("legacy_discard", **args)
                    # Recovery here is explicitly a private negative-control fixture.
                    after = worker.request("legacy_finish_choice")
                    pending = None
                else:
                    observation = worker.request("step", **args)
                    queued = worker.request("inspect_queue")
                    pending = queued["identity"]["pending_potion_discards"]
                    potion = next(
                        p
                        for p in queued["state"]["player"]["potions"]
                        if p["id"] == "HEART_OF_IRON"
                    )
                    if (
                        len(pending) != 1
                        or pending[0]["action_id"] is None
                        or pending[0]["state"] != "WaitingForExecution"
                        or queued["identity"]["pending_card_selection"] is not True
                        or potion["can_use"] is not False
                        or potion["can_discard"] is not False
                    ):
                        raise ValueError(
                            "Queued discard acceptance/disabled-holder evidence is missing"
                        )
                    for stale in (False, True):
                        worker.request("reject_queued_discard", stale_slot=stale)
                    for _ in range(8):
                        if observation["snapshot"]["interaction"]["kind"] != "card_selection":
                            break
                        choices = [
                            i
                            for i, c in enumerate(observation["model_input"]["candidates"])
                            if c["verb"] == "confirm"
                        ]
                        if not choices:
                            raise ValueError("Native card choice has no current confirmation")
                        observation = worker.request(
                            "step",
                            action_index=choices[0],
                            snapshot_id=observation["snapshot"]["snapshot_id"],
                        )
                    after = worker.request("inspect_queue")
                    if after["identity"]["pending_potion_discards"]:
                        raise ValueError("Queued discard did not settle after the card choice")
                    failure = None
                if after["identity"]["pending_card_selection"] is not False or any(
                    p["id"] == "HEART_OF_IRON" for p in after["state"]["player"]["potions"]
                ):
                    raise ValueError("The original native potion was not removed after the choice")
                worker.close()
                if not all(immutable_checks(q, inputs).values()):
                    raise ValueError("Queue qualification changed a frozen input")
                result = {
                    "case": f"{mode}-{repeat + 1}",
                    "status": "pass",
                    "mode": mode,
                    "prefix_decisions": len(decisions) - 1,
                    "legacy_error": failure,
                    "native_queued_discard": pending,
                    "private_before": before["identity"],
                    "private_after": after["identity"],
                    "privileged_fixture": True,
                    "training_allowed": False,
                }
            except (ValueError, TimeoutError, OSError) as exc:
                error = str(exc)
                result = {"case": f"{mode}-{repeat + 1}", "status": "failed", "error": error}
            finally:
                worker.stop()
            atomic_json(folder / "result.json", result)
            results.append(result)
        if error:
            break
    body = {
        "schema_version": "native-potion-queue-checks-v1",
        "config_id": manifest_identifier(cfg),
        "status": "queue_controls_pass"
        if not error and len(results) == 4
        else "queue_controls_incomplete",
        "planned_cases": 4,
        "completed_cases": sum(r["status"] == "pass" for r in results),
        "failed_cases": sum(r["status"] != "pass" for r in results),
        "not_attempted_cases": 4 - len(results),
        "error": error,
        "cases": results,
        "wall_seconds": time.monotonic() - started,
        "games_launched": len(results),
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
        "privileged_fixture": True,
        "game_apps_created": 0,
        "claim_scope": (
            "repeated_saved_train_seed_public_prefix_old_host_error_and_native_discard_queue_only"
        ),
    }
    report = {**body, "report_id": manifest_identifier(body)}
    atomic_json(output / "summary.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("--node", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    q = load_engine_qualification_config(
        root / "configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json"
    )
    report = run_queue_checks(q, args.config, args.node)
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2))
    return int(report["status"] != "queue_controls_pass")


if __name__ == "__main__":
    raise SystemExit(main())
