"""Read completed historical TRAIN records within a small, independent resource cap."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    recipe = "configs/native-controls/completed-training-diagnostics-v1.json"
    cfg = json.loads((root / recipe).read_text())
    command = [
        "uv",
        "run",
        "--no-sync",
        "python",
        "-m",
        "spireshift.native_training_diagnostics",
        recipe,
    ]
    if (root / cfg["workspace"] / "report.json").exists():
        print(
            "Diagnostic complete. Verifying saved results; no analysis or games follow.", flush=True
        )
        return subprocess.call(command, cwd=root)
    n = 1
    while (
        root / f"artifacts/resources/completed-training-diagnostics-v1-attempt-{n}.json"
    ).exists():
        n += 1
    report = f"artifacts/resources/completed-training-diagnostics-v1-attempt-{n}.json"
    limits = cfg["resource_limits"]
    print(
        "Inspecting 64 completed historical TRAIN games; the running experiment is untouched.",
        flush=True,
    )
    print(
        "One numerical thread; four-minute wall/CPU cap, 1 GB memory, 100 MB output. "
        "No games or policy updates.",
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
            report,
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
