"""Finite saved-TRAIN diagnostic. Default owner launch finishes four restartable cohorts."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", action="store_true")
    parser.add_argument("--one", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    name = "control" if args.control else "first-round"
    recipe = f"configs/native-controls/experience-diagnostics-{name}-v1.json"
    cfg = json.loads((root / recipe).read_text())
    limits, started = cfg["session_limits"], time.monotonic()
    env = dict(os.environ)
    for key in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "MKL_NUM_THREADS",
    ):
        env[key] = "1"
    print(
        "Inspecting only four sealed first-round TRAIN updates. Reconstruct saved "
        "behavior and restore existing value coefficients; no games, baseline refits "
        "or optimizer steps. Preserve the running experiment and all full states. "
        "One cohort per four-minute / 2 GB / 100 MB session; completed reports resume. "
        "Default owner launch finishes this finite plan within a 15-minute boundary. "
        "No evaluation data, teaching labels or automatic training follow.",
        flush=True,
    )
    for _ in range(1 if args.one else 4):
        if time.monotonic() - started > 660:
            print("Clean launch boundary. Re-run the same command to continue saved diagnostics.")
            return 0
        attempt = 1
        while (
            root / f"artifacts/resources/native-experience-diagnostics-{name}-v1-{attempt}.json"
        ).exists():
            attempt += 1
        code = subprocess.call(
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
                f"artifacts/resources/native-experience-diagnostics-{name}-v1-{attempt}.json",
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
                "spireshift.native_experience_diagnostics",
                recipe,
            ],
            cwd=root,
            env=env,
        )
        if code:
            return code
        if (root / cfg["workspace"] / "report.json").is_file():
            print("All four saved-data diagnostics complete. No games or training follow.")
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
