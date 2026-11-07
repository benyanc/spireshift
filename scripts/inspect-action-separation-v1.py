"""One bounded saved-only inspection. Never starts a game or changes an original player."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--one-session", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    path = "configs/native-prediction/sts2-v0.111.0-a8-action-separation-v1.json"
    cfg = json.loads((root / path).read_text())
    command = [
        "uv",
        "run",
        "--no-sync",
        "python",
        "-m",
        "spireshift.native_prediction_separation",
        path,
    ]
    if args.max_cases is not None:
        command.extend(["--max-cases", str(args.max_cases)])
    print(
        "Saved records only: independent outcome fitting, then action ranking inspection. "
        "Both original players and every PPO Adam moment remain read-only. "
        "No games, app copies or policy updates. Each session: four minutes and 2 GB memory; "
        "the same finite inspection has a 30-minute invocation cap. "
        "Completed units resume on the same command; no automatic next experiment.",
        flush=True,
    )
    started = time.monotonic()
    while True:
        prefix = "artifacts/resources/native-action-separation-v1-"
        index = 1
        while (root / f"{prefix}{index}.json").exists():
            index += 1
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
                f"{prefix}{index}.json",
                "--artifact-root",
                cfg["workspace"],
                "--workers",
                "1",
                "--max-wall-seconds",
                "240",
                "--max-cpu-seconds",
                "480",
                "--max-storage-bytes",
                "1000000000",
                "--max-memory-bytes",
                "2000000000",
                "--",
                *command,
            ],
            cwd=root,
        )
        if (
            code
            or args.max_cases is not None
            or args.one_session
            or (root / cfg["workspace"] / "report.json").exists()
        ):
            return code
        if time.monotonic() - started + 240 >= 1800:
            print(
                "Finite invocation cap reached. Reuse this command for saved remaining units.",
                flush=True,
            )
            return 0
        print("Clean saved-unit boundary. Continuing the same finite inspection.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
