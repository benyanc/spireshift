"""Compare full public menus, effects and handoffs on two frozen execution hosts."""

from __future__ import annotations

import argparse
import fcntl
import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_selector_lifecycle_cases, native_systematic_session_v1
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _running_games
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_verification_v12 import records
from spireshift.native_selector_official_reset import reset
from spireshift.native_selector_paired_contract import PairedPolicy, audit
from spireshift.native_selector_paired_inputs import MODULE, SCHEMA, context, load
from spireshift.native_selector_paired_worker import PairedWorker
from spireshift.native_shared_transport import JsonLines
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command


def evidence(root: Path, directory: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): _sha_file(p) for p in sorted(directory.rglob("*")) if p.is_file()
    }


def native_cases(
    ctx: dict[str, Any], cfg: dict[str, Any], area: Path, deadline: float
) -> dict[str, Any]:
    root = ctx["qualification"].root
    seal = area / "report.json"
    if seal.exists():
        report = identified(seal)
        if report["status"] != "native_controls_verified" or report[
            "config_id"
        ] != manifest_identifier(cfg):
            raise ValueError("Preserve the previous incomplete native preparation")
        check_sources(root, report["sources"])
        return report
    area.mkdir()
    rows = []
    stop = None
    for case in cfg["cases"]:
        directory = area / case["key"]
        directory.mkdir()
        try:
            preparation = PairedWorker(ctx, directory / "shared-preparation")
            try:
                fixture = preparation.request(
                    "prepare",
                    seed=case["seed"],
                    count=case.get("count", 3),
                    reward=case["kind"].startswith("reward"),
                )
                shutdown = preparation.close()
                if not shutdown["clean_exit"] or shutdown["runtime_errors"]:
                    raise ValueError("Shared fixture preparation did not exit cleanly")
            finally:
                preparation.stop()
            save = directory / "shared-fixture.save"
            atomic_json(save, fixture["save"])
            runner = (
                native_selector_lifecycle_cases.reward_case
                if case["kind"].startswith("reward")
                else native_selector_lifecycle_cases.shop_case
            )
            with patch.object(native_selector_lifecycle_cases, "OwnerWorker", PairedWorker):
                result = runner({**ctx, "selector_fixture_save": save}, case, directory, deadline)
            rows.append(
                write(
                    directory / "report.json",
                    {
                        "case": case,
                        "status": "verified",
                        "fixture_save": {
                            "path": str(save.relative_to(root)),
                            "sha256": _sha_file(save),
                        },
                        **result,
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


class OfficialClient(JsonLines):
    def __init__(self, root: Path, command: list[str], log: Path) -> None:
        expected = str(root / "scripts/engine-systematic-official-v1.mjs")
        if len(command) != 2 or command[1] != expected:
            raise ValueError("Unexpected official launch client")
        super().__init__(
            root, [command[0], str(root / "scripts/engine-selector-official-v1.mjs")], log
        )


def pair(
    ctx: dict[str, Any], cfg: dict[str, Any], row: dict[str, Any], area: Path, deadline: float
) -> dict[str, Any]:
    root = ctx["qualification"].root
    case = row["case"]
    source = root / cfg["workspace"] / "native" / case["key"]
    frames = list(records(source / "frames.jsonl.gz"))
    choices = [item["choice"]["action_index"] for item in records(source / "choices.jsonl.gz")]
    policy = PairedPolicy(frames, choices)
    current = {
        **ctx,
        "config": {**ctx["config"], "node": ctx["node"], "maximum_decisions": len(choices)},
    }
    area.mkdir()
    with patch.object(native_systematic_session_v1, "JsonLines", OfficialClient):
        official = native_systematic_session_v1.official_prefix(
            current,
            {
                "seed": case["seed"],
                "family": frames[0]["source_family"],
                "fixture_save": row["fixture_save"],
            },
            area / "official",
            policy,
            deadline,
        )
    result: dict[str, Any] = {
        "config_id": manifest_identifier(cfg),
        "native_case_report_id": row["report_id"],
        "case": case,
        "official": official,
        "native_effects": {
            key: value
            for key, value in row.items()
            if key not in {"case", "report_id", "fixture_save", "status"}
        },
    }
    if official["status"] != "official_prefix_pass" or policy.difference is not None:
        return write(
            area / "report.json",
            {
                **result,
                "status": "blocked_preserving_evidence",
                "difference": policy.difference,
                "sources": evidence(root, area),
            },
        )
    result["paired"] = audit(ctx, area / "official", policy, deadline)
    return write(
        area / "report.json",
        {**result, "status": "verified", "sources": evidence(root, area), "optimizer_updates": 0},
    )


def run(root: Path, cfg: dict[str, Any], area: Path, mode: str) -> dict[str, Any]:
    started = time.monotonic()
    ctx = context(root)
    before = frozen(root, ctx)
    limit = 240 if mode in {"native", "short"} else cfg["limits"]["wall_seconds"]
    deadline = started + limit - 15
    if mode != "native" and _running_games():
        raise ValueError("Close STS2 before the official/native comparison")
    native = native_cases(ctx, cfg, area / "native", deadline)
    rows, stop = [], native["stop"]
    if mode != "native" and stop is None:
        reset(ctx, cfg["inspected_reset"], area / "inspected-reset")
        for row in native["cases"][:2] if mode == "short" else native["cases"]:
            case = row["case"]
            directory = area / "pairs" / case["key"]
            directory.parent.mkdir(exist_ok=True)
            try:
                if (directory / "report.json").exists():
                    result = identified(directory / "report.json")
                    if (
                        result["status"] != "verified"
                        or result.get("config_id") != manifest_identifier(cfg)
                        or result.get("native_case_report_id") != row["report_id"]
                    ):
                        raise ValueError(
                            "Preserve the incomplete official comparison without retry"
                        )
                    check_sources(root, result["sources"])
                    native_source = area / "native" / case["key"]
                    saved_policy = PairedPolicy(
                        list(records(native_source / "frames.jsonl.gz")),
                        [
                            item["choice"]["action_index"]
                            for item in records(native_source / "choices.jsonl.gz")
                        ],
                    )
                    saved_policy.frames = [
                        entry["frame"]
                        for entry in records(directory / "official/live-public.jsonl.gz")
                        if entry["kind"] in {"policy_input", "diagnostic_successor"}
                    ]
                    audit(ctx, directory / "official", saved_policy, deadline)
                else:
                    result = pair(ctx, cfg, row, directory, min(deadline, time.monotonic() + 145))
                rows.append(result)
                print(f"Paired {case['key']}: {result['status']}", flush=True)
                if result["status"] != "verified":
                    stop = {"case": case["key"], "reason": "public_input_or_lifecycle_mismatch"}
                    break
            except (ValueError, KeyError, OSError, TimeoutError) as error:
                stop = {"case": case["key"], "error": f"{type(error).__name__}: {error}"}
                if directory.exists():
                    write(directory / f"assessment-stop-{time.time_ns()}.json", stop)
                break
    check_sources(root, cfg["implementation"])
    if frozen(root, ctx) != before:
        raise ValueError("The frozen game, runtime, original states or Adam changed")
    return write(
        area / f"{mode}-result-{time.time_ns()}.json",
        {
            "schema_version": SCHEMA,
            "status": "verified" if stop is None else "blocked_preserving_evidence",
            "mode": mode,
            "config_id": manifest_identifier(cfg),
            "environment_id": ctx["environment_id"],
            "native_report_id": native["report_id"],
            "planned_pairs": len(cfg["cases"]),
            "verified_pairs": sum(row["status"] == "verified" for row in rows),
            "pairs": rows,
            "frozen_checks": before,
            "optimizer_updates": 0,
            "training_allowed": False,
            "official_live_qualification_granted": False,
            "full_game_playing_strength_evaluated": False,
            "automatic_follow_up": False,
            "stop": stop,
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
    if args.mode == "full" and args.execute is None:
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
                "full",
                "--execute",
                str(attempt),
            ],
            working_directory=root,
            experiment_kind=ExperimentKind.OTHER,
            report_path=area / f"resources-{attempt}.json",
            artifact_roots=[area],
            limits=ResourceLimits(**cfg["limits"]),
        )
        print(json.dumps(tracked.report))
        return 0 if tracked.exit_code == 0 and tracked.report["cap"] is None else 2
    with (area / "session.lock").open("ab") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            result = run(root, cfg, area, args.mode)
        except (ValueError, KeyError, OSError, TimeoutError) as error:
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
            {key: result[key] for key in ("status", "mode", "verified_pairs", "stop", "report_id")}
        )
    )
    return 0 if result["status"] == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
