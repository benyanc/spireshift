"""Bounded offline value comparison; no game launches or saved player changes."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    stage = "control" if args.control else "comparison"
    recipe = f"configs/native-controls/public-state-value-{stage}-v1.json"
    cfg = json.loads((root / recipe).read_text())
    limits = cfg["resource_limits"]
    attempt = 1
    while (root / f"artifacts/resources/native-public-value-{stage}-v1-{attempt}.json").exists():
        attempt += 1
    print(
        "Comparing value forecasts on saved TRAIN games, one fold at a time. "
        "No new games, player updates or app copies. Completed folds are verified and reused. "
        f"This launch is capped at {limits['wall_seconds'] // 60} minutes, 2 GB memory. "
        "Rerun the same command after a clean pause.",
        flush=True,
    )
    return subprocess.call(
        [
            "uv",
            "run",
            "--no-sync",
            "spireshift",
            "resources",
            "run",
            "--kind",
            "other",
            "--report",
            f"artifacts/resources/native-public-value-{stage}-v1-{attempt}.json",
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
            "spireshift.native_public_value_study",
            recipe,
        ],
        cwd=root,
    )


if __name__ == "__main__":
    raise SystemExit(main())
