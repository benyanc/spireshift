"""Owner-run finite saved-TRAIN audit; never launches native games or trains a player."""

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
    name = "control" if args.control else "audit"
    version = 2 if args.control else 1
    recipe = f"configs/native-controls/completed-learning-feedback-{name}-v{version}.json"
    cfg = json.loads((root / recipe).read_text())
    command = ["uv", "run", "--no-sync", "python", "-m", "spireshift.native_feedback_audit", recipe]
    limits = cfg["resource_limits"]
    n = 1
    while (root / f"artifacts/resources/native-learning-feedback-{name}-v1-{n}.json").exists():
        n += 1
    print(
        "Checking completed TRAIN games and disposable numerical copies; "
        "no native games or production training. Completed batches are reused.",
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
            f"artifacts/resources/native-learning-feedback-{name}-v1-{n}.json",
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


if __name__ == "__main__":
    raise SystemExit(main())
