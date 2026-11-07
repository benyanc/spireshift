"""One finite fresh-seed greedy-continuation teacher; no fitting or automatic next stage."""

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
    recipe = f"configs/native-teacher/sts2-v0.111.0-a8-greedy-turn-{stage}-v1.json"
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
        "spireshift.native_greedy_turn_teacher",
        recipe,
        "--node",
        cfg["node"],
    ]
    if args.status or (root / cfg["workspace"] / "report.json").exists():
        return subprocess.call([*command, "--status"], cwd=root)
    print(
        "Fresh training worlds; one public-selected position per game. Freeze complete turns "
        "before comparing them with greedy combat and matched noncombat draws. Both exact "
        "players and every optimizer moment stay unchanged. One process, shared frozen files, "
        "no game-app copies or fitting. Close STS2. Completed attempts resume; uncertain work "
        "is preserved and never retried. No next experiment follows.",
        flush=True,
    )
    limits, stop_at = cfg["session_limits"], time.monotonic() + (240 if args.control else 7200)
    while True:
        if not args.control and time.monotonic() + limits["wall_seconds"] > stop_at:
            print("Invocation boundary; reuse this same command to resume the finite teacher.")
            return 0
        index = 1
        template = f"artifacts/resources/native-greedy-turn-teacher-{stage}-v1-{{}}.json"
        while (root / template.format(index)).exists():
            index += 1
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
                template.format(index),
                "--artifact-root",
                cfg["workspace"],
                "--workers",
                "1",
                "--max-wall-seconds",
                str(limits["wall_seconds"]),
                "--max-cpu-seconds",
                str(limits["cpu_seconds"]),
                "--max-memory-bytes",
                str(limits["resident_memory_bytes"]),
                "--max-storage-bytes",
                str(limits["storage_bytes"]),
                "--",
                *command,
            ],
            cwd=root,
        )
        if status or args.control or (root / cfg["workspace"] / "report.json").exists():
            return status
        print(
            "Clean boundary; continuing only the remaining attempts of this teacher plan.",
            flush=True,
        )


if __name__ == "__main__":
    raise SystemExit(main())
