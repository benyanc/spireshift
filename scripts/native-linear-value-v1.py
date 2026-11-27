"""Run only the finite saved-input linear value comparison; no new game attempts."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--max-units", type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    stage = "control" if args.control else "comparison"
    recipe = f"configs/native-controls/linear-value-{stage}-v1.json"
    cfg = json.loads((root / recipe).read_text())
    command = [
        "uv",
        "run",
        "--no-sync",
        "python",
        "-m",
        "spireshift.native_linear_value_study",
        recipe,
    ]
    if args.max_units is not None:
        command.extend(["--max-units", str(args.max_units)])
    if args.preflight:
        return subprocess.call([*command, "--preflight"], cwd=root)
    limits = cfg["resource_limits"]
    attempt = 1
    report = f"artifacts/resources/native-linear-value-{stage}-v1-{{}}.json"
    while (root / report.format(attempt)).exists():
        attempt += 1
    print(
        "Comparing simple predictors using cached public inputs and complete saved TRAIN games. "
        "Choose ridge strength on inner games, refit, then score separate outer games. "
        "Existing dictionaries are frozen development schemas, not rebuilt on inner folds. "
        f"At most {limits['wall_seconds'] // 60} minutes this launch, one numerical thread, "
        "2 GB memory / 500 MB output. Completed folds are verified and reused. "
        "No game attempts, app copies, player/Adam changes or automatic next stage.",
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
            report.format(attempt),
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
