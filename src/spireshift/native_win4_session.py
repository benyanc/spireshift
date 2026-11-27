"""Owner entry point for a finite all-act curriculum collection, then stop."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_win4_game import write
from spireshift.native_win4_inputs import RECIPE, binding, frozen_checks, load
from spireshift.native_win4_study import collect


def inspect_resume(context: dict[str, Any]) -> int:
    root, cfg = context["qualification"].root, context["config"]
    base = root / cfg["workspace"]
    if not base.exists():
        return 0
    config_path = base / "config-at-launch.json"
    if not config_path.exists() or json.loads(config_path.read_text()) != cfg:
        raise ValueError("Existing curriculum workspace has different declared inputs; preserve it")
    count = 0
    for chunk in (base / "chunks").glob("*"):
        if not chunk.is_dir() or not (chunk / "done.json").is_file():
            raise FileExistsError("Preserve an unfinished curriculum unit; no automatic replay")
        saved = identified(chunk / "done.json")
        check_sources(root, saved["sources"])
        count += 1
    return count


def preflight(root: Path) -> dict[str, Any]:
    context = load(root, root / RECIPE)
    checks = frozen_checks(context)
    sealed = inspect_resume(context)
    return {
        "valid": True,
        "launch_binding_id": binding(context["config"]),
        "environment_id": context["environment"]["manifest_id"],
        "checks": checks,
        "planned_fit_cases": len(context["config"]["plan"]["fit"]),
        "planned_heldout_cases": len(context["config"]["plan"]["heldout"]),
        "sealed_units": sealed,
        "new_games": 0,
        "optimizer_updates": 0,
        "official_live_qualification_granted": False,
        "automatic_follow_up": False,
    }


def owner_main(root: Path) -> int:
    cfg = json.loads((root / RECIPE).read_text())
    # Full runtime/guard validation takes place inside the resource-tracked child.
    # Reject an unfinished unit before doing a repository check or starting a game.
    inspect_resume({"qualification": type("Root", (), {"root": root})(), "config": cfg})
    if _running_games():
        raise ValueError("Close STS2 before native curriculum collection")
    output = root / cfg["workspace"]
    launch = root / "artifacts/native-win-curriculum/launch-v4"
    attempt = 1
    while (root / f"artifacts/resources/win-curriculum-v4-attempt-{attempt}.json").exists():
        attempt += 1
    command = [
        "uv",
        "run",
        "--no-sync",
        "spireshift",
        "resources",
        "run",
        "--kind",
        "other",
        "--report",
        f"artifacts/resources/win-curriculum-v4-attempt-{attempt}.json",
        "--artifact-root",
        str(output),
        "--artifact-root",
        str(launch),
        "--workers",
        "1",
    ]
    for option, name in [
        ("--max-wall-seconds", "wall_seconds"),
        ("--max-cpu-seconds", "cpu_seconds"),
        ("--max-memory-bytes", "resident_memory_bytes"),
        ("--max-storage-bytes", "storage_bytes"),
    ]:
        command += [option, str(cfg["session_limits"][name])]
    command += [
        "--",
        "uv",
        "run",
        "--no-sync",
        "python",
        "-m",
        "spireshift.native_win4_session",
        "--run",
        "--attempt",
        str(attempt),
    ]
    print(
        "Reuse thirty-one verified complete cases without games. "
        "Preserve three failed worlds and their denominators; one fresh case-32 replacement. "
        "Old markers stay untouched.",
        flush=True,
    )
    print(
        "Frozen v0.111.0 / 41cef1ea; CLI source56 / support build57 / worker24 / "
        "converter16 / compact ordered-answer plan1. "
        "Original full weights and Adam unchanged.",
        flush=True,
    )
    print(
        "Collect 56 fitting and 12 held-out curriculum cases "
        "across all acts, twelve bosses and normal starts.",
        flush=True,
    )
    print(
        "Prepared-state successes are training only. "
        "Exact native receipts and fresh teacher confirmations are required.",
        flush=True,
    )
    print(
        "Allow roughly 45–90 minutes per invocation; "
        "90-minute session cap, one worker, 4 GB memory/output.",
        flush=True,
    )
    print(
        "Clean seals resume with this command. "
        "Incomplete/uncertain units are preserved without retry.",
        flush=True,
    )
    print(
        "Stop after the curriculum quality report: "
        "zero main optimizer updates, no base training or evaluation follows.",
        flush=True,
    )
    return subprocess.call(command, cwd=root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--attempt", type=int, default=1)
    args = parser.parse_args()
    root = Path.cwd()
    if args.preflight:
        print(json.dumps(preflight(root)))
        return 0
    if not args.run:
        return owner_main(root)
    started = time.monotonic()
    context = load(root, root / RECIPE)
    inspect_resume(context)
    if _running_games():
        raise ValueError("Close STS2; the new scope starts no official application")
    before = frozen_checks(context)
    cfg = context["config"]
    launch = root / "artifacts/native-win-curriculum/launch-v4"
    launch.mkdir(parents=True, exist_ok=True)
    snapshot = launch / "source-at-launch"
    for name, digest in context["sources"].items():
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            from spireshift.engine_qualification import _sha_file

            if _sha_file(target) != digest:
                raise ValueError("Preserve changed curriculum source snapshot")
        else:
            with target.open("xb") as handle:
                handle.write((root / name).read_bytes())
    outcome = collect(context, started + cfg["session_limits"]["wall_seconds"] - 35)
    after = frozen_checks(context)
    write(
        launch / f"session-{args.attempt}.json",
        {
            "schema_version": "native-win-curriculum-session-v1",
            "status": outcome["status"],
            "config_id": context["config_id"],
            "checks_before": before,
            "checks_after": after,
            "result_id": outcome.get("report_id"),
            "optimizer_updates": 0,
            "automatic_follow_up": False,
            "wall_seconds": time.monotonic() - started,
        },
    )
    print(
        json.dumps(
            {k: v for k, v in outcome.items() if k not in {"sources", "evidence", "cases"}},
            indent=2,
        )
    )
    return 2 if outcome["status"] == "curriculum_quality_blocked" else 0


if __name__ == "__main__":
    for name in [
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "MKL_NUM_THREADS",
    ]:
        os.environ[name] = "1"
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TimeoutError) as exc:
        print(
            json.dumps(
                {
                    "status": "stopped_preserving_evidence",
                    "error": str(exc),
                    "optimizer_updates": 0,
                    "automatic_follow_up": False,
                }
            )
        )
        raise SystemExit(2) from exc
