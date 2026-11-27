"""Run only the finite policy-update comparison; resume sealed work on re-entry."""

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
    recipe = f"configs/native-policy/sts2-v0.111.0-a8-policy-updates-{stage}-v1.json"
    cfg = json.loads((root / recipe).read_text())
    command = ["uv", "run", "--no-sync", "python", "-m", "spireshift.native_policy_trial", recipe]
    if args.offline_only:
        command.append("--offline-only")
    if args.max_units is not None:
        command.extend(["--max-units", str(args.max_units)])
    if args.status:
        return subprocess.call([*command, "--status"], cwd=root)
    limits = dict(cfg["session_limits"])
    if args.offline_only:
        limits.update(wall_seconds=240, cpu_seconds=480)
    print(
        "Short bridge control: four sampled training games and four frozen-player checks. "
        if args.control
        else "Finite A8 policy comparison: 128 sampled training games (two rounds per player), "
        "then 128 fresh original-versus-updated games. ",
        end="",
        flush=True,
    )
    print(
        "Original weights and every Adam moment remain read-only. "
        "Copies continue saved optimizer state. "
        "No actor-score regression or health reward. No game-app copies. "
        + ("Saved checks/imports only; no game launch. " if args.offline_only else "Close STS2. ")
        + f"Session cap: {limits['wall_seconds'] // 60} minutes, 4 GB memory. "
        "Completed chunks resume. No promotion, adaptive controller or next experiment follows.",
        flush=True,
    )
    started = time.monotonic()
    while True:
        mode = stage + ("-offline" if args.offline_only else "")
        template = f"artifacts/resources/native-policy-updates-{mode}-v1-{{}}.json"
        index = 1
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
        # Do not begin a session that could exceed the one-hour invocation cap.
        if time.monotonic() - started + limits["wall_seconds"] > 3600:
            print(
                "Clean pause at invocation cap. Run this same command to resume saved units.",
                flush=True,
            )
            return 0
        print(
            "Clean session boundary. Continuing the same finite comparison from sealed units.",
            flush=True,
        )


if __name__ == "__main__":
    raise SystemExit(main())
