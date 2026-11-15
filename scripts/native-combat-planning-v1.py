"""Run only the finite bounded combat-planning comparison, with clean resumption."""

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
    recipe = f"configs/native-teacher/sts2-v0.111.0-a8-bounded-combat-{stage}-v1.json"
    cfg = json.loads((root / recipe).read_text())
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ):
        os.environ[name] = "1"
    command = [
        "uv",
        "run",
        "--no-sync",
        "python",
        "-m",
        "spireshift.native_combat_planning",
        recipe,
        "--node",
        cfg["node"],
    ]
    if args.status or (root / cfg["workspace"] / "report.json").exists():
        return subprocess.call([*command, "--status"], cwd=root)
    limits = cfg["session_limits"]
    stop_at = time.monotonic() + (240 if args.control else 7200)
    print(
        "Bounded combat comparison: four proposals per initial turn, "
        "then frozen full-run comparisons. "
        "The original baseline games are reused. Fight-plan selection uses encounter survival and "
        "remaining public HP, never later floors or wins; this does not change the learner reward. "
        "Every evaluation pays the full search CPU cost without amortization "
        "inside the 128-CPU-second "
        "whole-run budget. One native process, shared frozen files, no app copies or training. "
        "Close STS2. Completed receipts resume; uncertain work is never replayed automatically.",
        flush=True,
    )
    while True:
        if not args.control and time.monotonic() + limits["wall_seconds"] > stop_at:
            print(
                "Invocation limit between sessions; use this command again "
                "to resume the same finite plan."
            )
            return 0
        index = 1
        template = f"artifacts/resources/native-bounded-combat-{stage}-v1-{{}}.json"
        while (root / template.format(index)).exists():
            index += 1
        result = subprocess.call(
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
                template.format(index),
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
                *command,
            ],
            cwd=root,
        )
        if result or args.control or (root / cfg["workspace"] / "report.json").exists():
            return result
        print(
            "Clean session boundary; continuing only the remaining planned combat comparisons.",
            flush=True,
        )


if __name__ == "__main__":
    raise SystemExit(main())
