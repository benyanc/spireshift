"""Run the declared finite teaching test; originals and completed chunks stay sealed."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", action="store_true")
    parser.add_argument("--one-session", action="store_true")
    parser.add_argument("--max-units", type=int)
    args = parser.parse_args()
    if args.max_units is not None and args.max_units < 1:
        parser.error("--max-units must be positive")
    root = Path(__file__).resolve().parents[1]
    name = "control" if args.control else "comparison"
    recipe = f"configs/native-teaching/sts2-v0.111.0-a8-{name}-v1.json"
    cfg = json.loads((root / recipe).read_text())
    if (root / cfg["workspace"] / "report.json").exists():
        print(
            "Saved test is complete; verifying its result without new fitting or games.", flush=True
        )
    print(
        "Teaching copies from two saved fitting fights, then comparing final players.", flush=True
    )
    print(
        "Original weights/Adam stay intact. One worker; shared frozen inputs; no app copies.",
        flush=True,
    )
    print(
        "Short control: six fresh games and three fitting-fight checks. Close STS2."
        if args.control
        else "Main: 192 fresh full games plus 36 fitting/held-out fight checks. Close STS2.",
        flush=True,
    )
    print(
        "Completed units resume exactly; fixed final epochs; no further experiment follows.",
        flush=True,
    )
    env = dict(os.environ)
    for key in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "MKL_NUM_THREADS",
    ):
        env[key] = "1"
    sessions = 1 if args.control or args.one_session or args.max_units else 3
    for _ in range(sessions):
        index = 1
        prefix = f"native-plan-teaching-{name}-v1"
        while (root / f"artifacts/resources/{prefix}-{index}.json").exists():
            index += 1
        command = [
            "uv",
            "run",
            "--no-sync",
            "spireshift",
            "resources",
            "run",
            "--kind",
            "training",
            "--report",
            f"artifacts/resources/{prefix}-{index}.json",
            "--artifact-root",
            cfg["workspace"],
            "--workers",
            "1",
        ]
        for option, key in (
            ("--max-wall-seconds", "wall_seconds"),
            ("--max-cpu-seconds", "cpu_seconds"),
            ("--max-memory-bytes", "resident_memory_bytes"),
            ("--max-storage-bytes", "storage_bytes"),
        ):
            command += [option, str(cfg["session_limits"][key])]
        command += [
            "--",
            "uv",
            "run",
            "--no-sync",
            "python",
            "-m",
            "spireshift.native_teaching_study",
            recipe,
        ]
        if args.max_units is not None:
            command += ["--max-units", str(args.max_units)]
        result = subprocess.run(command, cwd=root, env=env, check=False)
        if result.returncode:
            return result.returncode
        if (root / cfg["workspace"] / "report.json").exists():
            print("Finite teaching test complete. Share the result; no next stage follows.")
            return 0
    print("Clean session boundary. Run this same command again to resume saved units.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
