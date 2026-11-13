"""Bounded paired input masking on saved games; no player fitting or new attempts."""

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
    recipe = f"configs/native-controls/matched-input-value-{stage}-v1.json"
    cfg = json.loads((root / recipe).read_text())
    command = [
        "uv",
        "run",
        "--no-sync",
        "python",
        "-m",
        "spireshift.native_matched_value_study",
        recipe,
    ]
    if args.max_units is not None:
        command.extend(["--max-units", str(args.max_units)])
    if args.preflight:
        return subprocess.call([*command, "--preflight"], cwd=root)
    limits = cfg["resource_limits"]
    attempt = 1
    while (root / f"artifacts/resources/native-matched-value-{stage}-v1-{attempt}.json").exists():
        attempt += 1
    print(
        "Comparing the same network with extra public inputs masked or enabled. "
        "Same saved games, starting arrays and fitting settings; three numerical initializers. "
        "Separate prediction-error and weight-penalty curves; fixed primary step 24. "
        f"At most {limits['wall_seconds'] // 60} minutes this launch, one numerical thread, "
        "2 GB memory and 500 MB output. Completed encoding/fitting chunks are reused. "
        "No games, saved-player/Adam updates, app copies or automatic next experiment. "
        "Rerun this same command after a clean pause.",
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
            f"artifacts/resources/native-matched-value-{stage}-v1-{attempt}.json",
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
