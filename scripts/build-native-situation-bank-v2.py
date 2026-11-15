"""Reselect the immutable candidate bank with explicit public coverage; no new extraction."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    recipe = "configs/native-situation-bank/sts2-v0.111.0-a8-completed-train-v2.json"
    cfg = json.loads((root / recipe).read_text())
    limits = cfg["session_limits"]
    attempt = 1
    while (
        root / f"artifacts/resources/native-situation-bank-completed-train-v2-{attempt}.json"
    ).exists():
        attempt += 1
    env = dict(os.environ)
    for key in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "MKL_NUM_THREADS",
    ):
        env[key] = "1"
    print(
        "Selecting varied situations from the already sealed TRAIN candidate pool. "
        "Reserve available public stage/encounter/health/opportunity groups before "
        "balancing; preserve the first bank and its whole-world splits. No games, "
        "model updates, source re-extraction or live experiment reads. Four-minute "
        "/ 1 GB RAM / 25 MB output cap. No automatic teacher or training follows.",
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
            f"artifacts/resources/native-situation-bank-completed-train-v2-{attempt}.json",
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
            "uv",
            "run",
            "--no-sync",
            "python",
            "-m",
            "spireshift.native_situation_reselection",
            recipe,
        ],
        cwd=root,
        env=env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
