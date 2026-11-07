"""One finite later-turn teacher plan; collection never changes a player or starts training."""

from __future__ import annotations

import argparse
import json
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
    recipe = f"configs/native-teacher/sts2-v0.111.0-a8-later-combat-{stage}-v2.json"
    cfg = json.loads((root / recipe).read_text())
    module = [
        "uv",
        "run",
        "--no-sync",
        "python",
        "-m",
        "spireshift.native_later_teacher",
        recipe,
        "--node",
        cfg["node"],
    ]
    if args.status:
        return subprocess.call([*module, "--status"], cwd=root)
    limits = cfg["session_limits"]
    stop_at = time.monotonic() + (240 if args.control else 7200)
    print(
        "Comparing every offered action at later combat positions with visible incoming attacks. "
        "Exact saved prefixes, unchanged players and whole-run score. "
        "One isolated process at a time; shared game files, zero app copies or optimizer updates. "
        "Policy streams vary inside one original hidden world per position. "
        "Complete branches are sealed and reused. No training or next experiment follows.",
        flush=True,
    )
    while True:
        if not args.control and time.monotonic() + limits["wall_seconds"] > stop_at:
            print("Invocation limit reached between sessions. Reuse this command to continue.")
            return 0
        attempt = 1
        report = f"artifacts/resources/native-later-combat-teacher-{stage}-v2-{{}}.json"
        while (root / report.format(attempt)).exists():
            attempt += 1
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
        ]
        status = subprocess.call(command, cwd=root)
        if status or (root / cfg["workspace"] / "report.json").exists() or args.control:
            return status
        print("Clean session boundary. Continuing the same finite saved branch plan.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
