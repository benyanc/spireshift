"""One capped owner session: collect/qualify the varied bank, then stop for assessment."""

from __future__ import annotations

import json
import os
import runpy
import subprocess
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    recipe = "configs/native-curriculum/sts2-v0.111.0-a8-varied-v1.json"
    cfg = json.loads((root / recipe).read_text())
    workspace = Path(cfg["workspace"])
    if workspace.is_absolute() or not (root / workspace).resolve().is_relative_to(
        root / "artifacts/native-varied-teaching"
    ):
        raise ValueError("Use the pinned study workspace for all outputs and accounting")
    print(
        "Close STS2. Collecting 8 fresh fitting worlds and 4 separately withheld worlds.",
        flush=True,
    )
    print(
        "Frozen v0.111.0 / 41cef1ea; CLI56 / Connector31 / worker24 / converter16 / layout12.",
        flush=True,
    )
    print(
        "Only fitting worlds receive declared fixed-root teacher branches; "
        "outcomes stay outside student inputs.",
        flush=True,
    )
    print(
        "Allow about 10–25 minutes; one 30-minute session, 4 GB memory/storage "
        "and fixed 128-CPU-second host guard.",
        flush=True,
    )
    print(
        "Sealed units resume exactly. Unfinished/uncertain units are preserved without retry.",
        flush=True,
    )
    print(
        "The curriculum quality gate is reported, then this command stops. "
        "No fitting, evaluation or follow-up starts.",
        flush=True,
    )
    runpy.run_path(str(root / "scripts/selection-flows-session-v12.py"))["check_repository"](root)
    attempt = 1
    while (
        root / f"artifacts/resources/varied-teaching-collect-v1-attempt-{attempt}.json"
    ).exists():
        attempt += 1
    env = dict(os.environ)
    for name in [
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "MKL_NUM_THREADS",
    ]:
        env[name] = "1"
    command = [
        "uv",
        "run",
        "--no-sync",
        "spireshift",
        "resources",
        "run",
        "--kind",
        "teacher_generation",
        "--report",
        f"artifacts/resources/varied-teaching-collect-v1-attempt-{attempt}.json",
        "--artifact-root",
        str(workspace),
        "--workers",
        "1",
    ]
    for option, name in [
        ("--max-wall-seconds", "wall_seconds"),
        ("--max-cpu-seconds", "cpu_seconds"),
        ("--max-memory-bytes", "resident_memory_bytes"),
        ("--max-storage-bytes", "storage_bytes"),
    ]:
        command += [option, str(cfg["session_limits"][name])]
    command += [
        "--",
        "uv",
        "run",
        "--no-sync",
        "python",
        "-m",
        "spireshift.native_curriculum_study",
        recipe,
        "--phase",
        "collect",
    ]
    return subprocess.run(command, cwd=root, env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
