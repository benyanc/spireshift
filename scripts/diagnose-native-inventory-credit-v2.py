"""Resource-capped saved-training credit diagnosis; never launches games or a player optimizer."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--short", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    recipe = "configs/native-controls/inventory-credit-diagnosis-v2.json"
    cfg = json.loads((root / recipe).read_text())
    limits = cfg["session_limits"]
    wall = 240 if args.short else limits["wall_seconds"]
    command = [
        "uv",
        "run",
        "--no-sync",
        "python",
        "-m",
        "spireshift.native_inventory_credit_study",
        recipe,
        "--session-seconds",
        str(wall),
    ]
    if args.short:
        command.extend(["--max-new-cohorts", "1"])
    attempt = 1
    while (root / f"artifacts/resources/native-inventory-credit-v2-{attempt}.json").exists():
        attempt += 1
    env = dict(os.environ)
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "MKL_NUM_THREADS",
    ):
        env[name] = "1"
    print(
        "Diagnosing credit from the 384 saved TRAIN attempts; no games or player updates. "
        "Twelve separate behavior-policy cohorts, whole-game validation, explicit owned "
        "cards/upgrades/displayed costs and relic identities/counters. One fixed inventory "
        "penalty; no hyperparameter search or production predictor change. "
        f"At most {wall // 60} minutes this launch, one numerical thread, 2 GB RAM, 500 MB output. "
        "Completed cohorts resume from sealed results. Keep both saved players and all Adam state. "
        "No game app copies, new training or automatic next experiment.",
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
            f"artifacts/resources/native-inventory-credit-v2-{attempt}.json",
            "--artifact-root",
            cfg["workspace"],
            "--workers",
            "1",
            "--max-wall-seconds",
            str(wall),
            "--max-cpu-seconds",
            str(wall),
            "--max-memory-bytes",
            str(limits["resident_memory_bytes"]),
            "--max-storage-bytes",
            str(limits["storage_bytes"]),
            "--",
            *command,
        ],
        cwd=root,
        env=env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
