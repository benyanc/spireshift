"""Owner-run finite two-player training continuation; safe clean-session resumption."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import runpy
import subprocess
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import load_engine_qualification_config
from spireshift.native_shop_continuation import COMPLETE, CONTROL, load_continuation, maximum_plan


def run_budgeted(
    root: Path, cfg: dict[str, Any], command: list[str], *, one_session: bool = False
) -> int:
    workspace = root / cfg["workspace"]
    deadline = time.monotonic() + cfg["invocation_wall_seconds"]
    next_resource = runpy.run_path(str(root / "scripts/optimizer-learning-v1.py"))["next_resource"]
    while True:
        if (workspace / "report.json").exists():
            print(
                "Finite continuation complete. Verifying saved results; no more training follows.",
                flush=True,
            )
            return subprocess.call([*command, "--status"], cwd=root)
        wall = min(cfg["session_limits"]["wall_seconds"], int(deadline - time.monotonic()) - 20)
        if wall < (150 if cfg["stage"] == "short_bridge_control" else 340):
            print(
                "Clean pause at the invocation cap. Re-run the same command to resume.", flush=True
            )
            return 0
        resource = next_resource(root, workspace.name + "-session")
        previous = set((workspace / "sessions").glob("session-*.json"))
        limits = cfg["session_limits"]
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
        resources = identified(resource)
        if code or resources["status"] != "completed" or resources["exit_code"] != 0:
            print(
                "Stopped on a failed/capped session; evidence is preserved. No automatic retry.",
                flush=True,
            )
            return code or 1
        new = set((workspace / "sessions").glob("session-*.json")) - previous
        if len(new) != 1:
            raise ValueError("One session must create exactly one new sealed progress receipt")
        result = identified(new.pop())
        if result["config_id"] != manifest_identifier(cfg):
            raise ValueError("Progress belongs to another continuation recipe")
        if result["status"] in {COMPLETE, CONTROL}:
            return subprocess.call([*command, "--status"], cwd=root)
        if (
            result["status"] != "paused_between_committed_chunks"
            or result["new_units_this_session"] < 1
        ):
            raise ValueError("No verified new progress; stop instead of looping")
        if one_session or cfg["stage"] == "short_bridge_control":
            print("Clean session saved. The same command resumes this finite plan.", flush=True)
            return 0
        print("Clean session boundary. Continuing the same bounded experiment.", flush=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--status", action="store_true")
    p.add_argument("--plan", action="store_true")
    p.add_argument("--control", action="store_true")
    p.add_argument("--one-session", action="store_true")
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    qualification = "configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json"
    recipe = (
        "configs/native-controls/shop-continuation-control-v1.json"
        if a.control
        else ("configs/native-learning/sts2-v0.111.0-a8-shop-continuation-v1.json")
    )
    q = load_engine_qualification_config(root / qualification)
    cfg, _, seeds, _ = load_continuation(q, root / recipe)
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
        "spireshift.native_shop_continuation",
        qualification,
        recipe,
        "--node",
        node,
    ]
    if a.plan:
        tasks = maximum_plan(cfg, seeds)
        print(
            json.dumps(
                {
                    "config_id": manifest_identifier(cfg),
                    "workspace": cfg["workspace"],
                    "players": cfg["players"],
                    "maximum_units": len(tasks),
                    "maximum_game_attempts": sum(len(t.get("seeds", [])) for t in tasks),
                    "first_fit_round": next(t["round"] for t in tasks if t["kind"] == "fit"),
                    "games_launched": 0,
                    "optimizer_steps": 0,
                },
                indent=2,
            )
        )
        return 0
    if a.status or (root / cfg["workspace"] / "report.json").exists():
        return subprocess.call([*command, "--status"], cwd=root)
    lock = root / "artifacts/validation/native-shop-continuation-v1-launch.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another invocation owns this continuation") from exc
        runpy.run_path(str(root / "scripts/optimizer-learning-v1.py"))["ensure_checked"](root)
        print(
            "Continuing both saved round-35 players with full Adam state, from round 36.",
            flush=True,
        )
        print(
            "Standard recipe: 32 games/batch, three passes; "
            "two shared-input workers, no app copies.",
            flush=True,
        )
        if not a.control:
            print(
                "At most 416 fresh TRAIN games/player; milestones 1248/1376/1536 total games.",
                flush=True,
            )
            print(
                "Stop both at a development plateau or the horizon; "
                "retain current states, then open the separate holdout.",
                flush=True,
            )
            print(
                "Maximum 1,344 attempts including evaluation. "
                "Expected 1–2 hours; three-hour invocation cap.",
                flush=True,
            )
            print(
                "Clean 15-minute sessions resume automatically, "
                "with 4 GB RAM / 4 GB generated-output caps.",
                flush=True,
            )
        print(
            "Close STS2. Clean reruns reuse completed games, fits and Adam state; "
            "failed/capped sessions stop.",
            flush=True,
        )
        return run_budgeted(root, cfg, command, one_session=a.one_session)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, TimeoutError) as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}, indent=2))
        raise SystemExit(1) from exc
