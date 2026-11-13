"""Run only the frozen bounded representation comparison; resume saved units."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", action="store_true")
    parser.add_argument("--offline-only", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--max-units", type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    stage = "control" if args.control else "comparison"
    recipe = f"configs/native-structured/sts2-v0.111.0-a8-{stage}-v1.json"
    cfg = json.loads((root / recipe).read_text())
    command = [
        "uv",
        "run",
        "--no-sync",
        "python",
        "-m",
        "spireshift.native_structured_comparison",
        recipe,
    ]
    for flag in ("status", "offline_only"):
        if getattr(args, flag):
            command.append("--" + flag.replace("_", "-"))
    if args.max_units is not None:
        command.extend(["--max-units", str(args.max_units)])
    if args.status or (root / cfg["workspace"] / "report.json").exists():
        print("Plan/saved-result verification only; no new games or fitting.", flush=True)
        return subprocess.call(command, cwd=root)
    limits = dict(cfg["session_limits"])
    if args.offline_only:
        limits.update(wall_seconds=240, cpu_seconds=480)
    print(
        "Short native integration control: 12 training attempts and 8 frozen checks. "
        if args.control
        else "Finite structured-input comparison: 384 training attempts, "
        "then 256 fresh evaluation attempts. ",
        end="",
        flush=True,
    )
    print(
        "Both original players and complete Adam states stay read-only. "
        "The two added-input arms have equal size and exact matched starting behavior. "
        "Unchanged-input training supplies a separate capacity control. "
        "Saved chunks resume; uncertain work stops without retry. No app copies. "
        f"This session: {limits['wall_seconds'] // 60} minutes, two workers, 4 GB memory. "
        "Close STS2. No promotion, adaptive controller or next experiment follows.",
        flush=True,
    )
    started = time.monotonic()
    while True:
        index = 1
        mode = stage + ("-offline" if args.offline_only else "")
        template = f"artifacts/resources/native-structured-{mode}-v1-{{}}.json"
        while (root / template.format(index)).exists():
            index += 1
        code = subprocess.call(
            [
                "uv",
                "run",
                "--no-sync",
                "spireshift",
                "resources",
                "run",
                "--kind",
                "training",
                "--report",
                template.format(index),
                "--artifact-root",
                cfg["workspace"],
                "--workers",
                "2",
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
        if (
            code
            or args.control
            or args.offline_only
            or args.max_units is not None
            or (root / cfg["workspace"] / "report.json").exists()
        ):
            return code
        if time.monotonic() - started + limits["wall_seconds"] > 3600:
            print(
                "Clean one-hour invocation boundary. Run this same command to resume.", flush=True
            )
            return 0
        print(
            "Clean session boundary. Continuing the same finite plan from saved units.", flush=True
        )


if __name__ == "__main__":
    raise SystemExit(main())
