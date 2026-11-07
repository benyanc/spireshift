"""Launch one finite natural-teacher stage; never follow it with another experiment."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", action="store_true")
    parser.add_argument("--phase", choices=("collect", "curriculum"), default="collect")
    parser.add_argument("--one", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    name = "control" if args.control else "comparison"
    recipe = f"configs/native-natural/sts2-v0.111.0-a8-{name}-v1.json"
    cfg = json.loads((root / recipe).read_text())
    workspace = cfg["workspace"] + ("/teacher" if args.phase == "collect" else "/curriculum")
    report_path = root / workspace / "report.json"
    if report_path.exists():
        print(
            "This stage is complete. Verifying and displaying saved evidence; no new work follows.",
            flush=True,
        )
    elif args.phase == "collect":
        print(
            "Collecting natural multi-turn lessons on TRAIN worlds. No model fitting follows.",
            flush=True,
        )
    else:
        print(
            "Fitting teacher/reference copies, then withheld fights and fresh games. "
            "Originals stay intact.",
            flush=True,
        )
    print(
        "One worker; shared frozen game/runtime/cache, no app copies. "
        "Re-run the same command after a clean pause.",
        flush=True,
    )
    env = dict(os.environ)
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "MKL_NUM_THREADS",
    ):
        env[name] = "1"
    started = time.monotonic()
    for _ in range(3):
        prefix = f"natural-combat-{'control' if args.control else 'comparison'}-{args.phase}-v1"
        index = 1
        while (root / f"artifacts/resources/{prefix}-{index}.json").exists():
            index += 1
        limits = cfg["session_limits"]
        command = [
            "uv",
            "run",
            "--no-sync",
            "spireshift",
            "resources",
            "run",
            "--kind",
            "teacher_generation" if args.phase == "collect" else "training",
            "--report",
            f"artifacts/resources/{prefix}-{index}.json",
            "--artifact-root",
            workspace,
            "--workers",
            "1",
        ]
        for option, key in (
            ("--max-wall-seconds", "wall_seconds"),
            ("--max-cpu-seconds", "cpu_seconds"),
            ("--max-memory-bytes", "resident_memory_bytes"),
            ("--max-storage-bytes", "storage_bytes"),
        ):
            command += [option, str(limits[key])]
        command += [
            "--",
            "uv",
            "run",
            "--no-sync",
            "python",
            "-m",
            "spireshift.native_natural_study",
            recipe,
            "--phase",
            args.phase,
        ]
        if args.one:
            command += ["--max-units", "1"]
        result = subprocess.run(command, cwd=root, env=env, check=False)
        if result.returncode:
            return result.returncode
        if report_path.exists():
            print("Finite stage finished. Share its summary; no next stage follows.")
            return 0
        if args.control or args.one or time.monotonic() - started >= 1800:
            print("Clean session boundary. Re-run the same command to resume saved units.")
            return 0
    print("Clean invocation boundary. Re-run the same command to continue this finite stage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
