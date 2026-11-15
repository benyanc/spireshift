"""Owner-run bounded rest-exploration comparison, preserving completed chunks."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import runpy
import subprocess
import time
from pathlib import Path

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import load_engine_qualification_config
from spireshift.native_exploration_admission import load
from spireshift.native_exploration_comparison import COMPLETE, CONTROL
from spireshift.native_exploration_plan import plan


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", action="store_true")
    p.add_argument("--status", action="store_true")
    p.add_argument("--control", action="store_true")
    p.add_argument("--one-session", action="store_true")
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    qualification = "configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json"
    recipe = (
        "configs/native-controls/rest-exploration-control-v1.json"
        if a.control
        else "configs/native-learning/sts2-v0.111.0-a8-rest-exploration-v1.json"
    )
    q = load_engine_qualification_config(root / qualification)
    cfg, _, seeds, _ = load(q, root / recipe)
    node = os.environ.get(
        "SPIRESHIFT_NODE",
        "/Users/benjamin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node",
    )
    command = [
        "uv",
        "run",
        "--no-sync",
        "python",
        "-m",
        "spireshift.native_exploration_comparison",
        qualification,
        recipe,
        "--node",
        node,
    ]
    workspace = root / cfg["workspace"]
    if a.plan:
        tasks = plan(cfg, seeds)
        print(
            json.dumps(
                {
                    "config_id": manifest_identifier(cfg),
                    "workspace": cfg["workspace"],
                    "players": cfg["players"],
                    "arms": cfg["arms"],
                    "maximum_units": len(tasks),
                    "maximum_game_attempts": sum(len(t.get("seeds", [])) for t in tasks),
                    "first_fit_round": 57,
                    "games_launched": 0,
                    "optimizer_steps": 0,
                },
                indent=2,
            )
        )
        return 0
    if a.status or (workspace / "report.json").exists():
        return subprocess.call([*command, "--status"], cwd=root)
    lock = root / "artifacts/validation/rest-exploration-v1-launch.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise ValueError("Another invocation owns this comparison") from e
        runpy.run_path(str(root / "scripts/optimizer-learning-v1.py"))["ensure_checked"](root)
        print(
            "Continuing both round-56 players into two matched learning methods, "
            "keeping all weights and Adam state.",
            flush=True,
        )
        print(
            "Standard versus 20% random exploration of legal rest-site choices only. "
            "No extra upgrade or HP points. Final testing uses ordinary play.",
            flush=True,
        )
        print(
            "At most 896 attempts: 512 TRAIN and 384 paired tests; 2 workers; no app copies. "
            "Expected 30–60 minutes; 2-hour launch cap.",
            flush=True,
        )
        print(
            "Completed eight-game chunks and fits resume. A failed/capped session stops "
            "for inspection. No automatic extension follows.",
            flush=True,
        )
        deadline = time.monotonic() + cfg["invocation_wall_seconds"]
        next_resource = runpy.run_path(str(root / "scripts/optimizer-learning-v1.py"))[
            "next_resource"
        ]
        while True:
            limits = cfg["session_limits"]
            wall = min(limits["wall_seconds"], int(deadline - time.monotonic()) - 20)
            if wall < (130 if a.control else 300):
                print("Clean pause. Re-run this same command to resume.", flush=True)
                return 0
            resource = next_resource(root, workspace.name + "-session")
            before = set((workspace / "sessions").glob("session-*.json"))
            code = subprocess.call(
                [
                    "uv",
                    "run",
                    "--no-sync",
                    "spireshift",
                    "resources",
                    "run",
                    "--kind",
                    "training",
                    "--report",
                    str(resource),
                    "--artifact-root",
                    cfg["workspace"],
                    "--workers",
                    "2",
                    "--max-wall-seconds",
                    str(wall),
                    "--max-cpu-seconds",
                    str(limits["cpu_seconds"]),
                    "--max-storage-bytes",
                    str(limits["storage_bytes"]),
                    "--max-memory-bytes",
                    str(limits["resident_memory_bytes"]),
                    "--",
                    *command,
                    "--wall-seconds",
                    str(wall),
                ],
                cwd=root,
            )
            r = identified(resource)
            if code or r["status"] != "completed" or r["exit_code"] != 0:
                print("Stopped; preserve all evidence. No automatic retry.", flush=True)
                return code or 1
            new = set((workspace / "sessions").glob("session-*.json")) - before
            if len(new) != 1:
                raise ValueError("Expected exactly one committed session receipt")
            progress = identified(new.pop())
            if progress["config_id"] != manifest_identifier(cfg):
                raise ValueError("Session belongs to another frozen plan")
            if progress["status"] in {COMPLETE, CONTROL}:
                return subprocess.call([*command, "--status"], cwd=root)
            if (
                progress["status"] != "paused_between_committed_chunks"
                or not progress["new_units_this_session"]
            ):
                raise ValueError("No verified new progress; stop")
            if a.one_session or a.control:
                print("Clean session saved; re-run this same command to resume.", flush=True)
                return 0
            print("Clean session boundary; continuing the same finite comparison.", flush=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, TimeoutError) as e:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(e)}, indent=2))
        raise SystemExit(1) from e
