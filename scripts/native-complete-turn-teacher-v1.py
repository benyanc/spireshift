"""Run one finite complete-turn teacher; no fitting or automatic next experiment."""

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
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    stage = "control" if args.control else "pilot"
    recipe = f"configs/native-teacher/sts2-v0.111.0-a8-complete-turn-{stage}-v1.json"
    cfg = json.loads((root / recipe).read_text())
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ):
        os.environ[name] = "1"
    module = [
        "uv",
        "run",
        "--no-sync",
        "python",
        "-m",
        "spireshift.native_turn_teacher",
        recipe,
        "--node",
        cfg["node"],
    ]
    if args.status or (root / cfg["workspace"] / "report.json").exists():
        return subprocess.call([*module, "--status"], cwd=root)
    limits = cfg["session_limits"]
    stop_at = time.monotonic() + (240 if args.control else 7200)
    print(
        "Complete-turn comparisons: freeze one greedy turn and one sampled turn per legal "
        "first move before scoring any candidate. Replays include native nested selections "
        "and verify every public observation through the turn boundary. One process at a time; "
        "no app copies, optimizer updates or training follows. Close any running STS2 game. "
        "Completed branches resume; uncertain or changed evidence is never replayed.",
        flush=True,
    )
    while True:
        if not args.control and time.monotonic() + limits["wall_seconds"] > stop_at:
            print("Invocation limit reached between sessions. Reuse this command to continue.")
            return 0
        attempt = 1
        report = f"artifacts/resources/native-complete-turn-teacher-{stage}-v1-{{}}.json"
        while (root / report.format(attempt)).exists():
            attempt += 1
        status = subprocess.call(
            [
                "uv",
                "run",
                "--no-sync",
                "spireshift",
                "resources",
                "run",
                "--kind",
                "teacher_generation",
                "--report",
                report.format(attempt),
                "--artifact-root",
                cfg["workspace"],
                "--workers",
                "1",
                "--max-wall-seconds",
                str(limits["wall_seconds"]),
                "--max-cpu-seconds",
                str(limits["cpu_seconds"]),
                "--max-storage-bytes",
                str(limits["storage_bytes"]),
                "--max-memory-bytes",
                str(limits["resident_memory_bytes"]),
                "--",
                *module,
            ],
            cwd=root,
        )
        if status or (root / cfg["workspace"] / "report.json").exists() or args.control:
            return status
        print(
            "Clean boundary. Continuing only the remaining branches of this finite plan.",
            flush=True,
        )


if __name__ == "__main__":
    raise SystemExit(main())
