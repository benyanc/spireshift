"""One resumable finite 2x2 teacher comparison; no fitting or next experiment."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", action="store_true")
    parser.add_argument("--max-units", type=int)
    parser.add_argument("--one-session", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    name = "control" if args.control else "comparison"
    recipe = f"configs/native-coordinated/sts2-v0.111.0-a8-{name}-v1.json"
    cfg = json.loads((root / recipe).read_text())
    print("Comparing single-change and coordinated plans at turn-one/turn-two starts.", flush=True)
    print(
        "One worker, shared frozen inputs, no app copies or optimizer updates. Close STS2.",
        flush=True,
    )
    print("Saved units resume exactly. No student training or next experiment follows.", flush=True)
    env = dict(os.environ)
    for variable in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "MKL_NUM_THREADS",
    ):
        env[variable] = "1"
    sessions = 1 if args.control or args.max_units or args.one_session else 3
    for _ in range(sessions):
        prefix = f"coordinated-teacher-{name}-v1"
        i = 1
        while (root / f"artifacts/resources/{prefix}-{i}.json").exists():
            i += 1
        command = [
            "uv",
            "run",
            "--no-sync",
            "spireshift",
            "resources",
            "run",
            "--kind",
            "teacher_generation",
            "--report",
            f"artifacts/resources/{prefix}-{i}.json",
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
            "spireshift.native_coordinated_study",
            recipe,
        ]
        if args.max_units is not None:
            command += ["--max-units", str(args.max_units)]
        result = subprocess.run(command, cwd=root, env=env, check=False)
        if result.returncode:
            return result.returncode
        if (root / cfg["workspace"] / "report.json").exists():
            print("Finite teacher comparison complete. Share the result; no next stage follows.")
            return 0
    print("Clean session boundary. Run this same command again to resume saved units.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
