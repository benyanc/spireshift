"""Owner launcher for one finite, resumable delayed-decision diagnostic."""

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
    stage = "control" if args.control else "comparison"
    recipe = f"configs/native-delayed/sts2-v0.111.0-a8-{stage}-v1.json"
    cfg = json.loads((root / recipe).read_text())
    env = dict(os.environ)
    for key in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "MKL_NUM_THREADS",
    ):
        env[key] = "1"
    limits, started = cfg["session_limits"], time.monotonic()
    print(
        "Delayed native decisions: current learned baseline versus exact current-policy "
        "baseline. Both players start from preserved full weights and Adam state. "
        "All native legal actions remain present; outcomes arrive only at the sequence end. "
        "Privileged diagnostic sequences are not ordinary full-game training or victories. "
        "One native process at a time, shared frozen inputs, no app copies. "
        "Close STS2. Completed units resume; uncertain work stops for inspection.",
        flush=True,
    )
    for _ in range(1 if args.one else 100):
        if time.monotonic() - started > 1800:
            print("Clean launch boundary. Re-run this same command to resume the finite plan.")
            return 0
        attempt = 1
        while (root / f"artifacts/resources/native-delayed-{stage}-v1-{attempt}.json").exists():
            attempt += 1
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
            f"artifacts/resources/native-delayed-{stage}-v1-{attempt}.json",
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
            "spireshift.native_delayed_study",
            recipe,
        ]
        if args.one:
            command.extend(["--max-units", "1"])
        code = subprocess.call(command, cwd=root, env=env)
        if code:
            return code
        final = root / cfg["workspace"] / "report.json"
        if final.exists():
            report = json.loads(final.read_text())
            print(
                json.dumps(
                    {
                        "status": report["status"],
                        "native_branches": report["native_branches"],
                        "optimizer_steps_on_experimental_copies": report[
                            "optimizer_steps_on_experimental_copies"
                        ],
                        "fitting_passes_by_arm": report["fitting_passes_by_arm"],
                        "report_id": report["report_id"],
                    },
                    indent=2,
                )
            )
            print("Finite diagnostic finished. No full-game training or next experiment follows.")
            return 0
    raise RuntimeError("Exceeded the finite clean-session allowance")


if __name__ == "__main__":
    raise SystemExit(main())
