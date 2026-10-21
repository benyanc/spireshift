"""Run one finite consequence-learning experiment; preserve parents and sealed units."""

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
    recipe = f"configs/native-consequence/sts2-v0.111.0-a8-{stage}-v1.json"
    cfg = json.loads((root / recipe).read_text())
    command = [
        "uv",
        "run",
        "--no-sync",
        "python",
        "-m",
        "spireshift.native_consequence_study",
        recipe,
        "--node",
        cfg["node"],
    ]
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
        "Testing added combat-consequence feedback against final-run-score-only learning, "
        "with both original players retained. Related plans/repeats stay in one source-game split. "
        "Existing weights and every PPO Adam moment are copied into disposable forks; "
        "New prediction heads have separate Adam state. "
        "Health is a prediction target, not a reward. "
        + (
            "Short control: eight native checks including exact repeats. "
            if args.control
            else "Finite main plan: 63 saved-data validation fits, then 192 fresh A8 games "
            "across original/return-only/consequence players. "
        )
        + (
            "Saved-data work only this invocation; no game launches. "
            if args.offline_only
            else "Close any STS2 game. One isolated worker reuses frozen files; no app copies. "
        )
        + f"Each session: at most {limits['wall_seconds'] // 60} minutes, 2 GB memory. "
        "Sealed units resume. "
        "No checkpoint promotion, adaptive controller or further experiment follows.",
        flush=True,
    )
    started = time.monotonic()
    while True:
        index = 1
        operation = stage + ("-offline" if args.offline_only else "")
        template = f"artifacts/resources/native-combat-consequences-{operation}-v1-{{}}.json"
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
        if (
            code
            or args.control
            or args.offline_only
            or args.max_units is not None
            or (root / cfg["workspace"] / "report.json").exists()
        ):
            return code
        if time.monotonic() - started >= 7200:
            print(
                "Invocation cap reached. Sealed units remain saved; "
                "use this same command to continue.",
                flush=True,
            )
            return 0
        print(
            "Clean session boundary. Continuing the same finite plan from sealed units.", flush=True
        )


if __name__ == "__main__":
    raise SystemExit(main())
