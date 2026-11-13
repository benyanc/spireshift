"""One finite fresh-game behavior comparison, resuming sealed games across sessions."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--control", action="store_true")
    p.add_argument("--status", action="store_true")
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    stage = "control" if a.control else "comparison"
    recipe = f"configs/native-evaluation/sts2-v0.111.0-a8-combat-behavior-{stage}-v1.json"
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
        "spireshift.native_combat_behavior",
        recipe,
        "--node",
        cfg["node"],
    ]
    if a.status or (root / cfg["workspace"] / "report.json").exists():
        return subprocess.call([*command, "--status"], cwd=root)
    print(
        "Comparing greedy versus sampled combat on fresh complete-game seeds. Both exact players "
        "and their full optimizer states remain unchanged. Noncombat policy and room/family random "
        "draws match; differing public states can legitimately produce different choices. "
        "One isolated process, shared frozen files, no app copies or training. Close STS2. "
        "Completed games resume; uncertain games are preserved and never retried automatically.",
        flush=True,
    )
    limits = cfg["session_limits"]
    stop_at = time.monotonic() + (240 if a.control else 7200)
    while True:
        if not a.control and time.monotonic() + limits["wall_seconds"] > stop_at:
            print("Invocation boundary; run this same command to resume the finite comparison.")
            return 0
        index = 1
        template = f"artifacts/resources/native-combat-behavior-{stage}-v1-{{}}.json"
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
                "rollout",
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
        if result or a.control or (root / cfg["workspace"] / "report.json").exists():
            return result
        print("Clean boundary; continuing only the remaining planned games.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
