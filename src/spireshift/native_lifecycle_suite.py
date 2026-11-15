"""Run the frozen A8 action lifecycle regressions and audit their coverage."""

from __future__ import annotations

import argparse
import fcntl
import json
import time
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_feedback_session import inputs
from spireshift.native_a8_rescue_game import receipt
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_flow_verification_v12 import records
from spireshift.native_lifecycle_contract import Capture, check_chain, check_frame
from spireshift.native_lifecycle_fixtures import CLASH, END, last_native_action, stampede_case
from spireshift.native_lifecycle_worker import PROJECT, SCRIPT, LifecycleWorker, build_adapter
from spireshift.native_mechanics_evidence import audit
from spireshift.native_mixed_rest import cases
from spireshift.native_mixed_rest import verify as rest_effects
from spireshift.native_mixed_rest_session import conversion, select
from spireshift.native_systematic_selectors_v2 import CONVERTER
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_lifecycle_suite"
RECIPE = "configs/native-compatibility/sts2-v0.111.0-a8-shared-lifecycle-v1.json"
SCHEMA = "native-a8-shared-lifecycle-v1"
SHORT_SECONDS = 230
LIMITS = {
    "wall_seconds": 900,
    "cpu_seconds": 2400,
    "storage_bytes": 1_000_000_000,
    "resident_memory_bytes": 4_000_000_000,
}


def implementation(root: Path) -> dict[str, str]:
    paths = {
        "scripts/check-action-lifecycle-v1.sh",
        "src/spireshift/native_mixed_rest.py",
        "src/spireshift/native_mixed_rest_session.py",
        "src/spireshift/native_mechanics_evidence.py",
        *(
            f"src/spireshift/native_lifecycle_{part}.py"
            for part in ("contract", "fixtures", "suite", "worker")
        ),
        *(f"{PROJECT}/{name}" for name in ("StartupHook.cs", f"{PROJECT.name}.csproj")),
    }
    for script in (SCRIPT, CONVERTER):
        paths.update(f"scripts/{name}" for name in worker_helpers(root, script))
    return {name: _sha_file(root / name) for name in sorted(paths)}


def load_plan(root: Path) -> dict[str, Any]:
    cfg: dict[str, Any] = json.loads((root / RECIPE).read_text())
    check_sources(root, cfg["implementation"])
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["implementation"] != implementation(root)
        or cfg["limits"] != LIMITS
        or canonical_seed(cfg["diagnostic_seed"]) == canonical_seed(cfg["normal_seed"])
    ):
        raise ValueError("Require the frozen lifecycle suite recipe and declared diagnostic seeds")
    return cfg


def source_failure(root: Path, cfg: dict[str, Any]) -> dict[str, str]:
    raw = verified(root, cfg["failed_transcript"])
    diagnostics = verified(root, cfg["failed_diagnostics"])
    last = last_native_action(raw.parent)
    if (
        raw.name != "private-transcript.jsonl.gz"
        or diagnostics.parent != raw.parent
        or last["request"]["action"] != END
        or last["response"]["decision"] != "game_over"
        or last["response"]["player"]["hp"] != 0
        or CLASH not in diagnostics.read_text()
    ):
        raise ValueError("Saved Stampede failure does not match the native error")
    return {key: cfg[key]["sha256"] for key in ("failed_transcript", "failed_diagnostics")}


def check_saved_rest(
    ctx: dict[str, Any], report_path: Path, output: Path, deadline: float, *, all_cases: bool
) -> dict[str, Any]:
    report = identified(report_path)
    fixture_cases = {case.name: case for case in cases()}
    if (
        report["status"] != "verified"
        or report["game_assembly_sha256"] != ctx["qualification"].target["assembly_sha256"]
        or len(report["rest_checks"]) != len(fixture_cases)
        or {row["case"]["name"] for row in report["rest_checks"]} != fixture_cases.keys()
    ):
        raise ValueError("Require the exact saved native rest matrix")
    output.mkdir()
    verified_cases = []
    for expected in report["rest_checks"]:
        descriptor = expected["case"]
        name = descriptor["name"]
        if not all_cases and name != "smith-belt-cancel":
            continue
        case = replace(fixture_cases[name], seed=descriptor["seed"])
        if json.loads(json.dumps(asdict(case))) != descriptor:
            raise ValueError("The archived rest fixture differs from its declared actions")
        base = report_path.parent / "rest" / name
        if identified(base / "report.json") != expected:
            raise ValueError("Saved rest case report differs from its matrix")
        folder = base / "native"
        bridge = conversion(ctx, output / f"{name}.log")
        captures: list[Capture] = []
        choices: list[int] = []
        delivered: list[dict[str, Any]] = []
        try:
            frames = records(folder / "frames.jsonl.gz")
            observations = records(folder / "worker/public-observations.jsonl.gz")
            receipts = iter(records(folder / "worker/public-receipts.jsonl.gz"))
            for frame, raw, step in zip(frames, observations, (*case.steps, None), strict=True):
                recreated = bridge.project(raw["snapshot"], raw["reads"], None, deadline)
                if recreated != frame:
                    raise ValueError("Archived rest public input differs from its raw observation")
                captures.append((raw, recreated))
                if step is None:
                    continue
                index = select(frame, step)
                raw_receipt = next(receipts, None)
                if raw_receipt is None:
                    raise ValueError("Missing saved rest delivery receipt")
                choice = {"binding_id": frame["binding_id"], "action_index": index}
                ack = receipt(frame, choice, "native", raw_receipt["successor_snapshot_id"])
                bridge.commit(choice, ack, deadline)
                choices.append(index)
                delivered.append(raw_receipt)
            if next(receipts, None) is not None:
                raise ValueError("Unexpected extra rest delivery receipt")
            trace = check_chain(captures, choices, delivered)
            effects = rest_effects(case, [frame for _, frame in captures])
            if json.loads(json.dumps(effects)) != expected["native_effects"]:
                raise ValueError("Saved rest effects differ from the previous proof")
            bridge.close()
            verified_cases.append(
                {"case": name, "source_report_id": expected["report_id"], **trace}
            )
        finally:
            bridge.stop()
    return {"source_report_id": report["report_id"], "cases": verified_cases}


def normal_start(ctx: dict[str, Any], seed: str, output: Path, deadline: float) -> dict[str, Any]:
    output.mkdir()
    worker = LifecycleWorker(ctx, output / "worker")
    bridge = conversion(ctx, output / "converter.log")
    try:
        observed = worker.request("mount", seed=seed)
        frame = bridge.project(observed["snapshot"], observed["reads"], None, deadline)
        check_frame((observed, frame))
        if frame["terminal"] or not observed["private_start_identity"]["started_with_neow"]:
            raise ValueError("The ordinary worker did not reach a fresh playable Neow start")
        shutdown = worker.close()
        bridge.close()
        if not shutdown["clean_exit"] or shutdown["runtime_errors"]:
            raise ValueError("The ordinary worker did not exit cleanly")
        return {"owner": frame["source_family"], "legal_actions": len(frame["actions"])}
    finally:
        bridge.stop()
        worker.stop()


def run(
    root: Path, cfg: dict[str, Any], mode: str, output: Path, deadline: float
) -> dict[str, Any]:
    _, ctx, runtime, *_ = inputs(root)
    before = frozen(root, ctx)
    shared = Path.home() / SHARED_PROFILE
    profile = _shared_snapshot(shared) if mode != "saved" and not _running_games() else None
    inventory = identified(verified(root, cfg["coverage_inventory"]))
    assembly = ctx["qualification"].target["assembly_sha256"]
    if inventory["game_assembly_sha256"] != assembly:
        raise ValueError("Coverage inventory belongs to another game build")
    cases_run: dict[str, Any] = {}
    results: dict[str, Any] = {
        "saved_failure": source_failure(root, cfg),
        "combat_cases": cases_run,
    }
    error = None
    try:
        results["saved_rest"] = check_saved_rest(
            ctx,
            verified(root, cfg["rest_matrix"]),
            output / "rest",
            min(deadline, time.monotonic() + 70),
            all_cases=mode != "short",
        )
        if mode != "saved":
            adapter = build_adapter(
                root, ctx["native"]["candidate"], output / "adapter", cfg["compiler"]
            )
            results["adapter"] = {**adapter, "two_independent_builds_exact": True}
            ctx = {
                **ctx,
                "lifecycle_adapter": adapter,
                "execution_id": manifest_identifier(
                    {
                        "parent": ctx["execution_id"],
                        "suite": cfg,
                        "adapter_sha256": adapter["sha256"],
                    }
                ),
            }
            for case in cfg["combat_cases"]:
                if time.monotonic() + 20 > deadline:
                    raise TimeoutError("Insufficient time for a whole combat control")
                result = stampede_case(
                    ctx, case, cfg["diagnostic_seed"], output / case["key"], deadline
                )
                cases_run[case["key"]] = result
                print(f"{case['key']} {result['status']}", flush=True)
            results["ordinary_start"] = normal_start(
                ctx, cfg["normal_seed"], output / "normal-start", deadline
            )
        if mode == "full":
            sample = output / "saved-learner"
            sample.mkdir()
            results["saved_learner_inputs"] = audit(root, ctx["score"], sample, deadline)
    except (ValueError, OSError, KeyError, TimeoutError) as failure:
        error = str(failure)
    check_sources(root, cfg["implementation"])
    if frozen(root, ctx) != before or profile is not None and _shared_snapshot(shared) != profile:
        error = "Frozen build, checkpoints, Adam or personal profile changed"
    checked = (*results.get("saved_rest", {}).get("cases", []), *cases_run.values())
    handoffs = Counter(tuple(pair) for case in checked for pair in case.get("handoffs", []))
    verified_stampede = all(
        cases_run.get(case["key"], {}).get("status")
        == ("expected_cleanup_failure_reproduced" if case.get("baseline") else "verified")
        for case in cfg["combat_cases"]
    )
    return write(
        output / "report.json",
        {
            "schema_version": SCHEMA,
            "status": "verified" if error is None else "blocked_preserving_evidence",
            "mode": mode,
            "config_id": manifest_identifier(cfg),
            "environment_id": ctx["environment_id"],
            "game_assembly_sha256": assembly,
            "runtime": runtime,
            "frozen_checks": before,
            "personal_profile_before_after_checked": profile is not None,
            "coverage_inventory_id": inventory["report_id"],
            "verified_native_handoffs": [
                {"before": before_owner, "after": after_owner, "deliveries": count}
                for (before_owner, after_owner), count in sorted(handoffs.items())
            ],
            "native_stampede_branches_verified": verified_stampede,
            "remaining_inventory_rows": [
                gap["id"]
                for family in inventory["families"]
                for gap in family["gaps"]
                if gap["id"] != "phase-stampede" or not verified_stampede
            ],
            "error": error,
            "optimizer_updates": 0,
            "training_allowed": False,
            "official_live_qualification_granted": False,
            **results,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", choices=("short", "saved", "full"), default="short")
    parser.add_argument("--execute", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path.cwd()
    cfg = load_plan(root)
    workspace = _private_path(root, cfg["workspace"])
    workspace.mkdir(parents=True, exist_ok=True)
    attempt = args.execute or time.time_ns()
    output = workspace / f"{args.mode}-{attempt}"
    if args.mode == "full" and args.execute is None:
        tracked = run_tracked_command(
            command=[
                "uv",
                "run",
                "--no-sync",
                "python",
                "-B",
                "-m",
                MODULE,
                "full",
                "--execute",
                str(attempt),
            ],
            working_directory=root,
            experiment_kind=ExperimentKind.OTHER,
            report_path=workspace / f"resources-{attempt}.json",
            artifact_roots=[output],
            limits=ResourceLimits(**cfg["limits"]),
        )
        print(json.dumps(tracked.report))
        return 0 if tracked.exit_code == 0 and tracked.report["cap"] is None else 2
    with (workspace / "session.lock").open("ab") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        output.mkdir()
        bound = cfg["limits"]["wall_seconds"] - 15 if args.mode == "full" else SHORT_SECONDS
        report = run(root, cfg, args.mode, output, time.monotonic() + bound)
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": str(output / "report.json"),
                "report_id": report["report_id"],
                "native_stampede_branches_verified": report["native_stampede_branches_verified"],
                "error": report["error"],
            }
        )
    )
    return 0 if report["status"] == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
