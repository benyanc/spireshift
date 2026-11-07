"""Owner-run fresh-seed comparison; no training or automatic extension follows."""

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
from spireshift.native_policy_confirmation import COMPLETE, CONTROL, load_confirmation, plan


def run_budgeted(
    root: Path, cfg: dict[str, Any], command: list[str], *, one_session: bool = False
) -> int:
    workspace = root / cfg["workspace"]
    deadline = time.monotonic() + cfg["invocation_wall_seconds"]
    next_resource = runpy.run_path(str(root / "scripts/optimizer-learning-v1.py"))["next_resource"]
    while True:
        if (workspace / "report.json").exists():
            print(
                "Comparison complete. Verifying its saved result; no new games follow.", flush=True
            )
            return subprocess.call([*command, "--status"], cwd=root)
        wall = min(cfg["session_limits"]["wall_seconds"], int(deadline - time.monotonic()) - 20)
        minimum = 150 if cfg["stage"] == "short_bridge_control" else 340
        if wall < minimum:
            print("Clean pause. Re-run the same command to resume the remaining games.", flush=True)
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
                "rollout",
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
            print(
                "Stopped on a failed/capped session. Evidence stays intact; no retry follows.",
                flush=True,
            )
            return code or 1
        receipts = set((workspace / "sessions").glob("session-*.json")) - previous
        if len(receipts) != 1:
            raise ValueError("One completed session must create exactly one new progress receipt")
        result = identified(receipts.pop())
        if result["config_id"] != manifest_identifier(cfg):
            raise ValueError("Comparison progress belongs to a different recipe")
        if result["status"] in {COMPLETE, CONTROL}:
            return subprocess.call([*command, "--status"], cwd=root)
        if (
            result["status"] != "paused_between_committed_chunks"
            or result["new_units_this_session"] < 1
        ):
            raise ValueError("No new sealed progress; preserve evidence instead of looping")
        if one_session or cfg["stage"] == "short_bridge_control":
            print("Clean session finished. The same command resumes the fixed plan.", flush=True)
            return 0
        print("Clean session boundary. Continuing the same finite comparison.", flush=True)


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
        "configs/native-controls/policy-confirmation-control-v1.json"
        if a.control
        else ("configs/native-learning/sts2-v0.111.0-a8-policy-confirmation-v1.json")
    )
    q = load_engine_qualification_config(root / qualification)
    cfg, _, seeds, _ = load_confirmation(q, root / recipe)
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
        "spireshift.native_policy_confirmation",
        qualification,
        recipe,
        "--node",
        node,
    ]
    if a.plan:
        print(
            json.dumps(
                {
                    "config_id": manifest_identifier(cfg),
                    "workspace": cfg["workspace"],
                    "players": cfg["players"],
                    "planned_games": sum(len(t["seeds"]) for t in plan(cfg, seeds)),
                    "chunks": len(plan(cfg, seeds)),
                    "games_launched": 0,
                    "optimizer_steps": 0,
                    "checkpoint_promoted": False,
                },
                indent=2,
            )
        )
        return 0
    if a.status or (root / cfg["workspace"] / "report.json").exists():
        return subprocess.call([*command, "--status"], cwd=root)
    lock = root / "artifacts/validation/native-policy-confirmation-v1-launch.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another invocation owns this comparison") from exc
        helpers = runpy.run_path(str(root / "scripts/optimizer-learning-v1.py"))
        helpers["ensure_checked"](root)
        count = sum(len(t["seeds"]) for t in plan(cfg, seeds))
        print(
            f"Frozen player comparison: {count} attempts, two workers; zero training updates.",
            flush=True,
        )
        print(
            "Each player keeps the same sampled policy, game rules and whole-run budget.",
            flush=True,
        )
        print(
            "Eight-game chunks are saved. Re-running resumes completed work; no app copies.",
            flush=True,
        )
        print(
            "Close any Steam game. A failure preserves evidence and stops automatic continuation.",
            flush=True,
        )
        if not a.control:
            print(
                f"Expected {cfg['expected_duration_minutes'][0]}–"
                f"{cfg['expected_duration_minutes'][1]} minutes; "
                "at most one hour this launch, 4 GB memory / 2 GB output.",
                flush=True,
            )
        return run_budgeted(root, cfg, command, one_session=a.one_session)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, TimeoutError) as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}, indent=2))
        raise SystemExit(1) from exc
