"""Build an immutable situation bank from historical TRAIN games; no games or learning."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", action="store_true")
    parser.add_argument("--max-new-games", type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    name = "control" if args.control else "completed-train"
    recipe = f"configs/native-situation-bank/sts2-v0.111.0-a8-{name}-v1.json"
    cfg = json.loads((root / recipe).read_text())
    limits = cfg["session_limits"]
    command = ["uv", "run", "--no-sync", "python", "-m", "spireshift.native_situation_bank", recipe]
    if args.max_new_games is not None:
        command.extend(["--max-new-games", str(args.max_new_games)])
    attempt = 1
    while (root / f"artifacts/resources/native-situation-bank-{name}-v1-{attempt}.json").exists():
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
        "Indexing completed historical TRAIN games only. No live experiment reads, "
        "game attempts, model fitting or app copies. Four-minute / 1 GB RAM / 250 MB "
        "output cap; each completed game is sealed and reused on a clean rerun. "
        "Roots retain original public menus and separate replay references; no action "
        "is labelled correct. No automatic teacher collection or training follows.",
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
            f"artifacts/resources/native-situation-bank-{name}-v1-{attempt}.json",
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
        env=env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
