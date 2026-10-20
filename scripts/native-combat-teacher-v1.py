"""Owner-run finite teacher collection; no training, app copies or unbounded follow-up."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    stage = "control" if args.control else "pilot"
    recipe = f"configs/native-teacher/sts2-v0.111.0-a8-combat-{stage}-v1.json"
    cfg = json.loads((root / recipe).read_text())
    stop_at = time.monotonic() + (240 if args.control else 7200)
    print(
        "Native action comparisons from verified TRAIN prefixes; "
        "no optimizer updates or app copies.",
        flush=True,
    )
    print(
        "Each root keeps its original hidden world. Only continuation-policy samples vary.",
        flush=True,
    )
    while True:
        if time.monotonic() > stop_at:
            print("Invocation cap reached. Completed branches remain sealed; rerun this command.")
            return 0
        n = 1
        while (root / f"artifacts/resources/native-combat-teacher-{stage}-v1-{n}.json").exists():
            n += 1
        limits = cfg["session_limits"]
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
            f"artifacts/resources/native-combat-teacher-{stage}-v1-{n}.json",
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
            "uv",
            "run",
            "--no-sync",
            "python",
            "-m",
            "spireshift.native_combat_teacher",
            recipe,
            "--node",
            cfg["node"],
        ]
        status = subprocess.call(command, cwd=root)
        if status or (root / cfg["workspace"] / "report.json").exists() or args.control:
            return status
        print(
            "Clean session boundary. Continuing the same finite teacher plan from saved branches.",
            flush=True,
        )


if __name__ == "__main__":
    raise SystemExit(main())
