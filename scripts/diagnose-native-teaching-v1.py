"""Inspect only the explicitly selected completed teaching result; never resume it."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main", action="store_true", help="Require the main test's final report")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    name = "comparison" if args.main else "control"
    recipe = f"configs/native-teaching-diagnostics/sts2-v0.111.0-a8-{name}-v1.json"
    cfg = json.loads((root / recipe).read_text())
    print(
        "Diagnosing completed saved teaching records; no games, fitting or optimizer updates.",
        flush=True,
    )
    print(
        "The selected source must be complete. Running/partial results are not followed.",
        flush=True,
    )
    prefix = f"native-teaching-diagnosis-{name}-v1"
    index = 1
    while (root / f"artifacts/resources/{prefix}-{index}.json").exists():
        index += 1
    command = [
        "uv",
        "run",
        "--no-sync",
        "spireshift",
        "resources",
        "run",
        "--kind",
        "other",
        "--report",
        f"artifacts/resources/{prefix}-{index}.json",
        "--artifact-root",
        cfg["workspace"],
        "--workers",
        "1",
    ]
    for option, key in (
        ("--max-wall-seconds", "wall_seconds"),
        ("--max-cpu-seconds", "cpu_seconds"),
        ("--max-memory-bytes", "resident_memory_bytes"),
        ("--max-storage-bytes", "storage_bytes"),
    ):
        command += [option, str(cfg["session_limits"][key])]
    command += [
        "--",
        "uv",
        "run",
        "--no-sync",
        "python",
        "-m",
        "spireshift.native_teaching_diagnostic_report",
        recipe,
    ]
    env = dict(os.environ)
    for key in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ):
        env[key] = "1"
    return subprocess.run(command, cwd=root, env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
