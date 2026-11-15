"""Check saved full menus and mixed native/official action lifecycles."""

from __future__ import annotations

import argparse
import fcntl
import json
import time
from pathlib import Path
from typing import Any

from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_feedback_session import inputs
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_mechanics_evidence import audit
from spireshift.native_mixed_rest import cases, paired_cases
from spireshift.native_mixed_rest_session import BOOTSTRAP, CONNECTOR, SCRIPT, run_cases
from spireshift.native_systematic_selectors_v2 import CONVERTER
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_mixed_mechanics"
WORKSPACE = "artifacts/native-mixed-mechanics"
MODES = {"saved": 200, "native": 230, "paired": 270, "paired-extra": 180, "paired-all": 1800}


def sources(root: Path) -> dict[str, str]:
    recipe = json.loads((root / CONNECTOR).read_text())["local_build"]["build_config"]
    patch = json.loads((root / recipe).read_text())["patch"]
    names = {
        BOOTSTRAP,
        CONNECTOR,
        recipe,
        patch,
        *(
            f"src/spireshift/{name}.py"
            for name in (
                "native_combat_intent_model",
                "native_mechanics_evidence",
                "native_mixed_mechanics",
                "native_mixed_rest",
                "native_mixed_rest_session",
                "native_systematic_live_v1",
                "native_systematic_session_v1",
            )
        ),
        "scripts/check-mixed-mechanics-v1.sh",
    }
    for name in (SCRIPT, CONVERTER, "engine-systematic-official-v1.mjs"):
        names.update(f"scripts/{item}" for item in worker_helpers(root, name))
    return {name: _sha_file(root / name) for name in sorted(names)}


def execute(root: Path, mode: str, output: Path, started: float) -> dict[str, Any]:
    _, ctx, runtime, *_ = inputs(root)
    source = sources(root)
    before = frozen(root, ctx)
    profile = Path.home() / SHARED_PROFILE
    shared = _shared_snapshot(profile)
    deadline = started + MODES[mode] - 10
    result: dict[str, Any] = {}
    output.mkdir()
    status = "verified"
    try:
        if mode == "saved":
            result["coverage"] = audit(root, ctx["score"], output, deadline)
        else:
            if _running_games():
                raise ValueError("Close STS2 and wait for other native workers")
            selected = cases()
            if mode in {"paired", "paired-extra"}:
                selected = paired_cases()[5:] if mode == "paired-extra" else paired_cases()[:5]
            evidence: list[dict[str, Any]] = []
            result["rest_checks"] = evidence
            for check in run_cases(
                ctx, selected, output / "rest", deadline, paired=mode != "native"
            ):
                evidence.append(check)
    except (ValueError, KeyError, OSError, TimeoutError) as error:
        result["error"] = str(error)
        status = "blocked_preserving_evidence"
    check_sources(root, source)
    if frozen(root, ctx) != before or _shared_snapshot(profile) != shared:
        status = "blocked_preserving_evidence"
        result["isolation_error"] = "Frozen game, full states, Adam or personal profile changed"
    return write(
        output / "report.json",
        {
            "schema_version": "native-mixed-mechanics-v1",
            "status": status,
            "mode": mode,
            "native_environment_id": ctx["environment_id"],
            "game_assembly_sha256": ctx["qualification"].target["assembly_sha256"],
            "objective": ctx["score"].evaluation_objective.as_dict(),
            "runtime": runtime,
            "sources": source,
            "frozen_checks": before,
            "optimizer_updates": 0,
            "training_admission_granted": False,
            "full_game_playing_strength_evaluated": False,
            "wall_seconds": time.monotonic() - started,
            **result,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=MODES)
    parser.add_argument("--attempt", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    workspace = root / WORKSPACE
    workspace.mkdir(parents=True, exist_ok=True)
    attempt = args.attempt or time.time_ns()
    output = workspace / f"{args.mode}-{attempt}"
    if args.mode == "paired-all" and args.attempt is None:
        tracked = run_tracked_command(
            command=[
                "uv",
                "run",
                "--no-sync",
                "python",
                "-m",
                MODULE,
                args.mode,
                "--attempt",
                str(attempt),
            ],
            working_directory=root,
            experiment_kind=ExperimentKind.OTHER,
            report_path=workspace / f"resources-{attempt}.json",
            artifact_roots=[output],
            limits=ResourceLimits(
                wall_seconds=MODES[args.mode],
                cpu_seconds=3600,
                storage_bytes=4_000_000_000,
                resident_memory_bytes=4_000_000_000,
            ),
        )
        return int(tracked.exit_code or (0 if tracked.status == "completed" else 2))
    with (workspace / "session.lock").open("ab") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        report = execute(root, args.mode, output, started)
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": str(output / "report.json"),
                "report_id": report["report_id"],
                "rest_cases": len(report.get("rest_checks", [])),
                "counts": report.get("coverage", {}).get("counts"),
                "error": report.get("error"),
            }
        )
    )
    return 0 if report["status"] == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
