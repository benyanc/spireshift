"""Fresh natural-ending pairs after event facts and retained shop-task qualification."""

from __future__ import annotations

import argparse
import json
import runpy
import time
from pathlib import Path
from typing import Any

import psutil

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_chest_worker import ChestWorker
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games
from spireshift.engine_qualification import _sha_file
from spireshift.engine_working_app import preflight_working_app
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_e2e_contract import compare_observations
from spireshift.native_flow_live_v12 import append
from spireshift.native_flow_verification_v12 import records
from spireshift.native_live_inputs import prepare
from spireshift.native_live_policy import LivePolicy
from spireshift.native_shared_transport import JsonLines
from spireshift.native_shop_ending_session import official_prefix
from spireshift.native_shop_inputs import load
from spireshift.native_shop_verification import verify_host


def process_cpu_seconds() -> float:
    value = psutil.Process().cpu_times()
    return value.user + value.system


def converter_cpu_seconds(converter: JsonLines) -> float:
    value = psutil.Process(converter.child.pid).cpu_times()
    return value.user + value.system


def native_run(
    ctx: dict[str, Any], case: dict[str, Any], directory: Path, policy: LivePolicy, deadline: float
) -> dict[str, Any]:
    root, cfg = ctx["qualification"].root, ctx["config"]
    directory.mkdir(parents=True, exist_ok=False)
    worker = ChestWorker(
        ctx["qualification"],
        ctx["native"],
        directory / "worker",
        Path(cfg["node"]),
        ctx["native_helpers"],
    )
    converter = JsonLines(
        root,
        [cfg["node"], str(root / "scripts/engine-shared-input-v16.mjs")],
        directory / "converter.log",
    )
    started_cpu = process_cpu_seconds()
    gameplay_cpu = 0.0
    ending = None
    error = None
    shutdown: dict[str, Any] = {"clean_exit": False}
    try:
        current = worker.request(
            "mount", seed=case["seed"], timeout=min(25, deadline - time.monotonic())
        )
        for _ in range(cfg["maximum_decisions"] + 1):
            frame = converter.project(current["snapshot"], current["reads"], None, deadline)
            gameplay_cpu = (
                worker.cpu_seconds()
                + converter_cpu_seconds(converter)
                + process_cpu_seconds()
                - started_cpu
            )
            runtime_capped = time.monotonic() >= deadline - 50 or gameplay_cpu > 128
            capped = policy.decisions >= cfg["maximum_decisions"] or runtime_capped
            append(
                directory / "shared-public.jsonl.gz",
                {
                    "kind": "final_observation"
                    if capped and not frame["terminal"]
                    else "policy_input",
                    "frame": frame,
                },
            )
            if frame["terminal"]:
                ending = frame["ending"]
                if runtime_capped:
                    error = "Native ending observed after the declared runtime/compute guard"
                break
            if capped:
                error = "Declared choice/time/compute guard reached before a genuine ending"
                break
            choice = policy.choose(frame)
            binding = frame["actions"][choice["action_index"]]
            successor = worker.request(
                "step",
                snapshot_id=current["snapshot"]["snapshot_id"],
                action_index=binding["raw_index"],
                timeout=min(20, deadline - time.monotonic()),
            )
            receipt = {
                "binding_id": frame["binding_id"],
                "delivery": "delivered",
                "bound_action_id": binding["bound_action_id"],
                "runtime_instance_id": frame["observation"]["runtime_instance_id"],
                "before_snapshot_id": frame["observation"]["snapshot_id"],
                "successor_snapshot_id": successor["snapshot"]["snapshot_id"],
            }
            policy.acknowledge(receipt)
            converter.commit(choice, receipt, deadline)
            append(
                directory / "shared-public.jsonl.gz",
                {"kind": "policy_choice", "choice": choice, "receipt": receipt},
            )
            current = successor
        shutdown = worker.close()
        converter.close()
    except (ValueError, OSError, TimeoutError) as failure:
        error = str(failure)
    finally:
        converter.stop()
        worker.stop()
    result = {
        "status": "native_natural_ending_pass"
        if ending is not None
        and not error
        and shutdown["clean_exit"]
        and not shutdown.get("runtime_errors")
        else "native_natural_run_blocked",
        "policy_decisions": policy.decisions,
        "ending": ending,
        "error": error,
        "shutdown": shutdown,
        "optimizer_updates": 0,
        "full_game_evaluation": False,
        "policy_cpu_seconds": gameplay_cpu,
    }
    result["report_id"] = manifest_identifier(result)
    atomic_json(directory / "report.json", result)
    return result


def observations(directory: Path, host: str) -> list[dict[str, Any]]:
    name = "shared-public.jsonl.gz" if host == "native" else "live-public.jsonl.gz"
    return [
        row["frame"]
        for row in records(directory / host / name)
        if row["kind"] in {"policy_input", "final_observation"}
    ]


def preflight(root: Path, recipe: Path) -> dict[str, Any]:
    ctx = load(root, recipe)
    cfg = ctx["config"]
    if cfg["stage"] != "natural_ending_panel":
        raise ValueError("Use the separately frozen two-pair natural-ending plan")
    saved = identified(verified(root, cfg["reconciliation"]))
    check_sources(root, saved["sources"])
    check_sources(root, saved["evidence"])
    if (
        saved["status"] != "saved_reconciliation_pass"
        or saved["environment_id"] != ctx["environment"]["manifest_id"]
        or saved["current_input_and_choice_replays"] != 486
    ):
        raise ValueError("Complete the exact historical/current replay before natural runs")
    if _running_games():
        raise ValueError("Close STS2 before the natural-ending panel")
    preflight_working_app(ctx["working_app"])
    return ctx


def run(root: Path, recipe: Path) -> dict[str, Any]:
    ctx = preflight(root, recipe)
    cfg = ctx["config"]
    output = root / cfg["workspace"]
    if (output / "report.json").exists():
        saved = identified(output / "report.json")
        if saved["config_id"] != manifest_identifier(cfg):
            raise ValueError("Preserve another end-to-end result")
        check_sources(root, saved["sources"])
        check_sources(root, saved["evidence"])
        return saved
    if (output / "active.json").exists():
        raise ValueError("Preserve the interrupted panel; no automatic restart or seed retry")
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(
        output / "active.json", {"config_id": manifest_identifier(cfg), "training_allowed": False}
    )
    for name in cfg["implementation"]:
        destination = output / "source-at-launch" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((root / name).read_bytes())
    atomic_json(output / "source-at-launch/recipe.json", cfg)
    imported = prepare(root, ctx)
    original = {
        p: (manifest_identifier(m.as_dict()), manifest_identifier(a.as_dict()))
        for p, (m, a, _) in imported.items()
    }
    started = time.monotonic()
    cases = []
    for case in cfg["cases"]:
        directory = output / case["key"]
        directory.mkdir(exist_ok=False)
        atomic_json(directory / "active.json", {"case": case})
        model = imported[case["player"]][0]
        deadline = time.monotonic() + cfg["maximum_pair_wall_seconds"]
        native = native_run(
            ctx, case, directory / "native", LivePolicy(model, ctx["score"], case["seed"]), deadline
        )
        if not native["shutdown"]["clean_exit"]:
            raise ValueError("Native shutdown unverified; preserve case and stop")
        official = None
        if native["status"] == "native_natural_ending_pass":
            official = official_prefix(
                ctx,
                case,
                directory / "official",
                LivePolicy(model, ctx["score"], case["seed"]),
                deadline,
            )
        verified_counts = {}
        errors = {}
        comparison = {"complete_workflow_equal": False}
        verification = directory / "verification"
        verification.mkdir()
        for host, completed in (
            ("native", native["status"] == "native_natural_ending_pass"),
            ("official", official is not None and official["status"] == "official_prefix_pass"),
        ):
            if completed:
                try:
                    verified_counts[host] = verify_host(
                        root,
                        ctx,
                        case,
                        host,
                        directory / host,
                        verification,
                        time.monotonic() + 120,
                    )
                except (ValueError, KeyError, StopIteration) as error:
                    errors[host] = str(error)
        if official is not None:
            comparison = compare_observations(
                observations(directory, "native"), observations(directory, "official")
            )
        clean = native["shutdown"]["clean_exit"] and (
            official is None or all(official["checks"].values())
        )
        passed = (
            comparison["complete_workflow_equal"]
            and not errors
            and set(verified_counts) == {"native", "official"}
            and clean
        )
        result = {
            "case": case,
            "status": "natural_workflow_pass" if passed else "natural_workflow_blocked",
            "native": native,
            "official": official,
            "comparison": comparison,
            "independently_verified_deliveries": verified_counts,
            "verification_errors": errors,
            "clean_reset": clean,
            "optimizer_updates": 0,
        }
        result["report_id"] = manifest_identifier(result)
        atomic_json(directory / "report.json", result)
        (directory / "active.json").rename(directory / "complete.json")
        cases.append(result)
        print(f"Natural ending pair {len(cases)}/2: {case['key']}: {result['status']}", flush=True)
        if not clean:
            raise ValueError("Unverified worker/app reset; no next case")
    after = {
        p: (manifest_identifier(m.as_dict()), manifest_identifier(a.as_dict()))
        for p, (m, a, _) in imported.items()
    }
    if original != after:
        raise ValueError("Frozen policy inference changed model or Adam state")
    check_sources(root, json.loads(verified(root, cfg["protection"]).read_text()))
    check_sources(root, ctx["sources"])
    passed = all(case["status"] == "natural_workflow_pass" for case in cases)
    report = {
        "schema_version": "native-e2e-natural-ending-result-v1",
        "config_id": manifest_identifier(cfg),
        "environment_id": ctx["environment"]["manifest_id"],
        "status": "natural_workflow_qualification_candidate"
        if passed
        else "natural_workflow_blocked",
        "workflow_qualification_candidate": passed,
        "cases": cases,
        "genuine_matching_ending_pairs": sum(c["status"] == "natural_workflow_pass" for c in cases),
        "sources": ctx["sources"],
        "evidence": {
            str(p.relative_to(root)): _sha_file(p)
            for p in output.rglob("*")
            if p.is_file() and p.name != "active.json"
        },
        "optimizer_updates": 0,
        "original_weights_and_all_Adam_unchanged": True,
        "training_allowed": False,
        "automatic_follow_up": False,
        "full_game_playing_strength_evaluated": False,
        "claim_scope": "two_frozen_players_declared_worlds_native_endings_and_summary_only",
        "wall_seconds": time.monotonic() - started,
    }
    report["report_id"] = manifest_identifier(report)
    atomic_json(output / "report.json", report)
    (output / "active.json").rename(output / "complete.json")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    root, recipe = Path.cwd(), args.recipe.resolve()
    if args.preflight:
        preflight(root, recipe)
        print(
            json.dumps({"valid": True, "planned_pairs": 2, "new_games": 0, "optimizer_updates": 0})
        )
        return 0
    preflight(root, recipe)
    checker = runpy.run_path(str(root / "scripts/selection-flows-session-v12.py"))
    checker["check_repository"](root)
    report = run(root, recipe)
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in {"sources", "evidence", "cases"}}, indent=2
        )
    )
    return 0 if report["workflow_qualification_candidate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
