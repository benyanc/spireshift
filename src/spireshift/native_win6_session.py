"""Owner entry point for the frozen Trial curriculum continuation."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

from spireshift.engine_native import _running_games
from spireshift.engine_qualification import _sha_file
from spireshift.native_compatibility_contract import verified
from spireshift.native_curriculum_config import THREADS
from spireshift.native_win4_game import write
from spireshift.native_win4_session import inspect_resume
from spireshift.native_win5_study import collect
from spireshift.native_win6_inputs import declaration, frozen_checks, load


def owner_main(root: Path) -> int:
    decl = declaration(root)
    parent = json.loads(verified(root, decl["parent"]).read_text())
    limits = json.loads(verified(root, parent["parent"]).read_text())["session_limits"]
    attempt = 1
    while (root / f"artifacts/resources/win-curriculum-v6-attempt-{attempt}.json").exists():
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
        f"artifacts/resources/win-curriculum-v6-attempt-{attempt}.json",
        "--artifact-root",
        str(root / decl["workspace"]),
        "--artifact-root",
        str(root / decl["launch_workspace"]),
        "--workers",
        "1",
    ]
    for flag, key in [
        ("--max-wall-seconds", "wall_seconds"),
        ("--max-cpu-seconds", "cpu_seconds"),
        ("--max-memory-bytes", "resident_memory_bytes"),
        ("--max-storage-bytes", "storage_bytes"),
    ]:
        command.extend([flag, str(limits[key])])
    command.extend(
        [
            "--",
            "uv",
            "run",
            "--no-sync",
            "python",
            "-m",
            "spireshift.native_win6_session",
            "--run",
            "--attempt",
            str(attempt),
        ]
    )
    print(
        "Import 42 verified cases and collect the 26 remaining slots, including a fresh "
        "replacement for case 43. Preserve five historical failures.\n"
        "Frozen game v0.111.0 / 41cef1ea with Trial presentation support build 59.\n"
        "Clean seals can resume with this command. An uncertain delivery stops collection.\n"
        "Collection and quality assessment only, zero optimizer updates. Allow up to 90 minutes.",
        flush=True,
    )
    return subprocess.call(command, cwd=root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    parser.add_argument("--attempt", type=int, default=1)
    args = parser.parse_args()
    root = Path.cwd()
    if _running_games():
        raise ValueError("Close STS2 before launching the native curriculum")
    if not args.run and not args.preflight:
        return owner_main(root)
    started = time.monotonic()
    context = load(root)
    sealed = inspect_resume(context)
    before = frozen_checks(context)
    if not all(before.values()):
        raise ValueError("Frozen runtime or model inputs changed")
    if args.preflight:
        print(
            json.dumps(
                {
                    "status": "preflight_verified",
                    "config_id": context["config_id"],
                    "sealed_units": sealed,
                    "reusable_seals": len(context["imports"]),
                    "optimizer_updates": 0,
                }
            )
        )
        return 0
    cfg = context["config"]
    launch = root / context["declaration"]["launch_workspace"]
    snapshot = launch / "source-at-launch"
    for name, digest in context["sources"].items():
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if _sha_file(target) != digest:
                raise ValueError("A source snapshot changed. Preserve the current launch.")
        else:
            with target.open("xb") as handle:
                handle.write((root / name).read_bytes())
    result = collect(context, started + cfg["session_limits"]["wall_seconds"] - 35)
    after = frozen_checks(context)
    if not all(after.values()):
        raise ValueError("Frozen runtime or model inputs changed during collection")
    write(
        launch / f"session-{args.attempt}.json",
        {
            "schema_version": "native-win-curriculum-session-v1",
            "status": result["status"],
            "config_id": context["config_id"],
            "checks_before": before,
            "checks_after": after,
            "result_id": result.get("report_id"),
            "optimizer_updates": 0,
            "automatic_follow_up": False,
            "wall_seconds": time.monotonic() - started,
        },
    )
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in {"sources", "evidence", "cases"}}, indent=2
        )
    )
    return 2 if result["status"] == "curriculum_quality_blocked" else 0


if __name__ == "__main__":
    for name in THREADS:
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
