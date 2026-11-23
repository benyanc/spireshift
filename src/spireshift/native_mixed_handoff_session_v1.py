"""Paired mixed handoff diagnostics on the exact frozen native and official hosts."""

from __future__ import annotations

import argparse
import fcntl
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _running_games
from spireshift.engine_qualification import _sha_file
from spireshift.engine_working_app import preflight_working_app
from spireshift.full_run_experience import atomic_json
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_verification_v12 import records
from spireshift.native_mixed_handoff_cases_v1 import run_case
from spireshift.native_mixed_handoff_inputs_v1 import MODULE, SCHEMA, context, load
from spireshift.native_mixed_handoff_worker_v1 import MixedWorker
from spireshift.native_selector_paired_contract import PairedPolicy, audit
from spireshift.native_selector_paired_session import evidence, pair
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command


def native_cases(
    ctx: dict[str, Any], cfg: dict[str, Any], area: Path, deadline: float
) -> dict[str, Any]:
    root = ctx["qualification"].root
    seal = area / "report.json"
    if seal.exists():
        result = identified(seal)
        if result["status"] != "native_controls_verified" or result[
            "config_id"
        ] != manifest_identifier(cfg):
            raise ValueError("Preserve the incomplete native mixed handoff preparation")
        check_sources(root, result["sources"])
        return result
    area.mkdir()
    rows, stop = [], None
    for case in cfg["cases"]:
        directory = area / case["key"]
        directory.mkdir()
        try:
            preparation = MixedWorker(ctx, directory / "preparation")
            try:
                result = preparation.request("prepare", case=case)
                shutdown = preparation.close()
                if not shutdown["clean_exit"] or shutdown["runtime_errors"]:
                    raise ValueError("Mixed fixture preparation did not stop cleanly")
            finally:
                preparation.stop()
            save = directory / "shared-fixture.save"
            atomic_json(save, result["save"])
            effects = run_case(ctx, case, save, directory, deadline)
            rows.append(
                write(
                    directory / "report.json",
                    {
                        "status": "verified",
                        "case": case,
                        "fixture_save": {
                            "path": str(save.relative_to(root)),
                            "sha256": _sha_file(save),
                        },
                        "fixture_source_sha256": result["original_save_sha256"],
                        **effects,
                    },
                )
            )
            print(f"Native {case['key']}: verified", flush=True)
        except (ValueError, KeyError, OSError, TimeoutError, StopIteration) as error:
            stop = {"case": case["key"], "error": f"{type(error).__name__}: {error}"}
            write(directory / "failure.json", stop)
            break
    return write(
        seal,
        {
            "schema_version": SCHEMA,
            "status": "native_controls_verified" if stop is None else "blocked_preserving_evidence",
            "config_id": manifest_identifier(cfg),
            "cases": rows,
            "stop": stop,
            "sources": evidence(root, area),
            "optimizer_updates": 0,
        },
    )


def saved_pair(
    ctx: dict[str, Any],
    cfg: dict[str, Any],
    native: dict[str, Any],
    directory: Path,
    deadline: float,
) -> dict[str, Any]:
    result = identified(directory / "report.json")
    if (
        result["status"] != "verified"
        or result["config_id"] != manifest_identifier(cfg)
        or result["native_case_report_id"] != native["report_id"]
    ):
        raise ValueError("Preserve an incomplete or changed official mixed handoff without retry")
    root = ctx["qualification"].root
    check_sources(root, result["sources"])
    source = root / cfg["workspace"] / "native" / native["case"]["key"]
    policy = PairedPolicy(
        list(records(source / "frames.jsonl.gz")),
        [row["choice"]["action_index"] for row in records(source / "choices.jsonl.gz")],
    )
    policy.frames = [
        row["frame"]
        for row in records(directory / "official/live-public.jsonl.gz")
        if row["kind"] in {"policy_input", "diagnostic_successor"}
    ]
    proof = audit(ctx, directory / "official", policy, deadline)
    if (
        proof != result["paired"]
        or not all(result["official"]["checks"].values())
        or not result["official"]["working_app"]["restored"]
    ):
        raise ValueError("The saved official handoff lacks its exact raw proof and clean reset")
    return result


def run(root: Path, cfg: dict[str, Any], area: Path, mode: str) -> dict[str, Any]:
    started = time.monotonic()
    deadline = (
        started + (cfg["limits"] if mode == "full" else cfg["short_limits"])["wall_seconds"] - 15
    )
    ctx = context(root)
    if (
        ctx["environment_id"] != cfg["environment_id"]
        or ctx["working_app"].config_id != cfg["working_app_config_id"]
    ):
        raise ValueError("The frozen environment or shared working app policy changed")
    before = frozen(root, ctx)
    if _running_games():
        raise ValueError("Close STS2 before the mixed handoff diagnostics")
    preflight_working_app(ctx["working_app"])
    native = native_cases(ctx, cfg, area / "native", deadline)
    rows, stop = [], native["stop"]
    if mode != "native" and stop is None:
        wanted = (
            set(cfg["short_case_keys"])
            if mode == "short"
            else {case["key"] for case in cfg["cases"]}
        )
        for row in native["cases"]:
            if row["case"]["key"] not in wanted:
                continue
            directory = area / "pairs" / row["case"]["key"]
            directory.parent.mkdir(exist_ok=True)
            try:
                result = (
                    saved_pair(ctx, cfg, row, directory, deadline)
                    if (directory / "report.json").exists()
                    else pair(ctx, cfg, row, directory, min(deadline, time.monotonic() + 180))
                )
                rows.append(result)
                print(f"Paired {row['case']['key']}: {result['status']}", flush=True)
                if result["status"] != "verified":
                    stop = {
                        "case": row["case"]["key"],
                        "reason": "public_input_or_lifecycle_mismatch",
                    }
                    break
            except (ValueError, KeyError, OSError, TimeoutError, SystemError) as error:
                stop = {"case": row["case"]["key"], "error": f"{type(error).__name__}: {error}"}
                if directory.exists():
                    write(directory / f"assessment-stop-{time.time_ns()}.json", stop)
                break
    check_sources(root, cfg["implementation"])
    if frozen(root, ctx) != before:
        raise ValueError("Frozen build, runtime, checkpoints or Adam changed")
    success = {
        "native": "native_controls_verified",
        "short": "short_controls_verified",
        "full": "mixed_handoffs_verified",
    }[mode]
    return write(
        area / f"{mode}-result-{time.time_ns()}.json",
        {
            "schema_version": SCHEMA,
            "status": success if stop is None else "blocked_preserving_evidence",
            "mode": mode,
            "config_id": manifest_identifier(cfg),
            "environment_id": ctx["environment_id"],
            "native_report_id": native["report_id"],
            "planned_pairs": len(cfg["cases"]),
            "verified_pairs": len([row for row in rows if row["status"] == "verified"]),
            "pairs": rows,
            "stop": stop,
            "frozen_checks": before,
            "optimizer_updates": 0,
            "training_allowed": False,
            "official_live_qualification_granted": False,
            "full_game_playing_strength_evaluated": False,
            "automatic_follow_up": False,
            "wall_seconds": time.monotonic() - started,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("native", "short", "full"), nargs="?", default="full")
    parser.add_argument("--execute", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path.cwd()
    cfg = load(root)
    area = _private_path(root, cfg["workspace"])
    area.mkdir(parents=True, exist_ok=True)
    if args.execute is None:
        attempt = time.time_ns()
        tracked = run_tracked_command(
            command=[
                "uv",
                "run",
                "--no-sync",
                "python",
                "-B",
                "-m",
                MODULE,
                args.mode,
                "--execute",
                str(attempt),
            ],
            working_directory=root,
            experiment_kind=ExperimentKind.OTHER,
            report_path=area / f"{args.mode}-resources-{attempt}.json",
            artifact_roots=[area],
            limits=ResourceLimits(
                **(cfg["limits"] if args.mode == "full" else cfg["short_limits"])
            ),
        )
        print(json.dumps(tracked.report))
        return 0 if tracked.exit_code == 0 and tracked.report["cap"] is None else 2
    with (area / "session.lock").open("ab") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            result = run(root, cfg, area, args.mode)
        except (ValueError, KeyError, OSError, TimeoutError, SystemError) as error:
            print(
                json.dumps(
                    {
                        "status": "stopped_preserving_evidence",
                        "error": str(error),
                        "optimizer_updates": 0,
                        "automatic_follow_up": False,
                    }
                )
            )
            return 2
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "status",
                    "mode",
                    "planned_pairs",
                    "verified_pairs",
                    "stop",
                    "report_id",
                )
            }
        )
    )
    return 0 if result["stop"] is None else 2


if __name__ == "__main__":
    raise SystemExit(main())
