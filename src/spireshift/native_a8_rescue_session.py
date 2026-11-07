"""Qualify a public-state Act 1 teacher, then collect fresh normal-start rescues."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.native_a8_rescue_checks import control
from spireshift.native_a8_rescue_curriculum import assess, play_case
from spireshift.native_a8_rescue_inputs import (
    GAME_LIMITS,
    MODULE,
    SESSION_LIMITS,
    declaration,
    freeze,
    load,
    short_check,
)
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_win4_game import write

SHARED_PROFILE = "Library/Application Support/SlayTheSpire2"
WORLD_RESERVE = 4 * (GAME_LIMITS["episode_wall_seconds"] + 20) + 40
NO_UPDATES = {
    "optimizer_updates": 0,
    "training_allowed": False,
    "promotion_allowed": False,
    "automatic_follow_up": False,
    "full_game_playing_strength_evaluated": False,
    "official_live_qualification_granted": False,
    "final_test_worlds_used": False,
}


def verify_boundary(root: Path, ctx: dict[str, Any], launch: dict[str, Any]) -> None:
    if (
        freeze(root, ctx) != launch["frozen_checks"]
        or _shared_snapshot(Path.home() / SHARED_PROFILE) != launch["shared_profile"]
        or _running_games()
    ):
        raise ValueError("Frozen inputs, native shutdown or shared profile failed verification")


def publish_bank(
    workspace: Path,
    launch: dict[str, Any],
    qualification: dict[str, Any],
    collection: list[dict[str, Any]],
) -> str:
    selected = [row for row in collection if row["label_file"]]
    bank = {
        "schema_version": "native-a8-act1-rescue-bank-v1",
        "status": "ready_for_separately_reviewed_fitting",
        "config_id": launch["config_id"],
        "environment_id": launch["environment_id"],
        "objective": launch["objective"],
        "qualification": qualification,
        "worlds": [
            {
                **row["case"],
                "lessons": row["label_file"],
                "label_count": row["targeted_label_count"],
                "total_label_weight": 1.0,
            }
            for row in selected
        ],
        "label_count": sum(row["targeted_label_count"] for row in selected),
        **NO_UPDATES,
    }
    path = workspace / "bank.json"
    if path.exists():
        existing = identified(path)
        if {k: v for k, v in existing.items() if k != "report_id"} != bank:
            raise ValueError("Preserve the existing Act 1 rescue bank")
    else:
        existing = write(path, bank)
    return str(existing["report_id"])


def run(root: Path, ctx: dict[str, Any], attempt: int, deadline: float) -> dict[str, Any]:
    cfg = ctx["config"]
    store = ChunkJournal(root, cfg)
    planned = cfg["worlds"]
    ordered = [case for phase in ("qualify", "collect") for case in planned[phase]]
    with store.lock():
        if _running_games():
            raise ValueError("Close STS2 and wait for any other native experiment to finish")
        launch = write(
            store.workspace / f"launch-{attempt}.json",
            {
                "config_id": store.config_id,
                "environment_id": ctx["environment_id"],
                "objective": cfg["objective"],
                "checkpoints": ctx["states"],
                "short_check_receipts": ctx["short_check_receipts"],
                "frozen_checks": freeze(root, ctx),
                "shared_profile": _shared_snapshot(Path.home() / SHARED_PROFILE),
                "game_limits": GAME_LIMITS,
                "session_limits": SESSION_LIMITS,
            },
        )
        if any(
            p.name not in {case["key"] for case in ordered}
            for p in (store.workspace / "chunks").glob("*")
        ):
            raise ValueError("Preserve the unexpected Act 1 evidence")
        sealed = {case["key"]: store.completed(case["key"], case) for case in ordered}
        existing = [key for key, done in sealed.items() if done is not None]
        if existing != [case["key"] for case in ordered[: len(existing)]]:
            raise ValueError("Saved Act 1 evidence does not form a sealed prefix")

        rows: dict[str, list[dict[str, Any]]] = {"qualify": [], "collect": []}
        status, stopped, bank_id = "act1_rescue_bank_blocked", None, None
        for phase in ("qualify", "collect"):
            for case in planned[phase]:
                key = case["key"]
                done = sealed[key]
                if done is None:
                    if deadline - time.monotonic() < WORLD_RESERVE:
                        status = "paused_at_clean_boundary"
                        stopped = {"case": case, "reason": "wall_reserve"}
                        break
                    target = store.begin(key, case)
                    try:
                        row = play_case(ctx, case, target, deadline)
                        done = store.commit(key, case, row)
                    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
                        status = "stopped_preserving_evidence"
                        stopped = {"case": case, "reason": "unsealed_world", "error": str(exc)}
                        break
                    print(
                        f"{key} p{case['player']}: {row['outcomes']}; "
                        f"rescue={row['strict_rescue_confirmed']}",
                        flush=True,
                    )
                rows[phase].append(done["result"])
            verify_boundary(root, ctx, launch)
            if stopped:
                break
            if not assess(phase, planned[phase], rows[phase])["passed"]:
                if phase == "qualify":
                    if any(sealed[c["key"]] is not None for c in planned["collect"]):
                        raise ValueError(
                            "Collection evidence exists without a passing qualification"
                        )
                    status = "act1_teacher_qualification_blocked"
                break
            if phase == "qualify":
                print(
                    "Act 1 teacher qualified. Beginning the declared disjoint collection worlds.",
                    flush=True,
                )
        qualification = assess("qualify", planned["qualify"], rows["qualify"])
        collection = assess("collect", planned["collect"], rows["collect"])
        if qualification["passed"] and collection["passed"] and stopped is None:
            bank_id = publish_bank(store.workspace, launch, qualification, rows["collect"])
            status = "act1_rescue_bank_admitted"
        return write(
            store.workspace / f"attempt-{attempt}.json",
            {
                "schema_version": "native-a8-act1-rescue-curriculum-result-v1",
                "status": status,
                "launch_id": launch["report_id"],
                "config_id": store.config_id,
                "environment_id": ctx["environment_id"],
                "qualification": qualification,
                "collection": collection,
                "worlds": [
                    {
                        **case,
                        "sealed": case["key"] in {r["case"]["key"] for r in rows[case["phase"]]},
                    }
                    for case in ordered
                ],
                "stop": stopped,
                "bank_id": bank_id,
                "frozen_checks": launch["frozen_checks"],
                "shared_profile_unchanged": True,
                **NO_UPDATES,
            },
        )


def tracked(
    root: Path, report: str, workspace: str, limits: dict[str, int], arguments: list[str]
) -> int:
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
        report,
        "--artifact-root",
        workspace,
        "--workers",
        "1",
    ]
    for flag, key in (
        ("--max-wall-seconds", "wall_seconds"),
        ("--max-cpu-seconds", "cpu_seconds"),
        ("--max-memory-bytes", "resident_memory_bytes"),
        ("--max-storage-bytes", "storage_bytes"),
    ):
        command.extend([flag, str(limits[key])])
    command.extend(["--", "uv", "run", "--no-sync", "python", "-m", MODULE, *arguments])
    return subprocess.call(command, cwd=root)


def prepare_control(root: Path, cfg: dict[str, Any]) -> int:
    if short_check(root, cfg) is not None:
        return 0
    print("Verifying the saved menus and three short native prefixes.", flush=True)
    return tracked(
        root,
        cfg["control_resource"],
        cfg["control_workspace"],
        cfg["control_limits"],
        ["--control"],
    )


def owner_main(root: Path, cfg: dict[str, Any]) -> int:
    if code := prepare_control(root, cfg):
        return code
    attempt = time.time_ns()
    print(
        "Close STS2. Eight fresh normal starts qualify the Act 1 teacher.\n"
        "A passing qualification opens twelve disjoint collection worlds.\n"
        "Original, update-200 and teacher on each seed. "
        "Strict rescues require a reproduced Act 2 entry.\n"
        "Frozen v0.111.0 / 41cef1ea and native support60. "
        "All four full states and Adam stay fixed.\n"
        "Expect about 15–35 minutes for both stages; 90-minute outer cap.\n"
        "Clean seals resume. Uncertain attempts are preserved without retry. "
        "Zero updates. Then stop.",
        flush=True,
    )
    return tracked(
        root,
        f"artifacts/resources/a8-act1-rescue-v1-{attempt}.json",
        cfg["workspace"],
        cfg["session_limits"],
        ["--run", "--attempt", str(attempt)],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--control", action="store_true")
    mode.add_argument("--short-only", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--run", action="store_true")
    parser.add_argument("--attempt", type=int)
    args = parser.parse_args()
    root = Path.cwd()
    try:
        if not args.preflight and _running_games():
            raise ValueError("Close STS2 before using the isolated native experiment")
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the pinned single-thread numerical settings")
        cfg = declaration(root)
        if args.short_only:
            return prepare_control(root, cfg)
        if not (args.run or args.control or args.preflight):
            return owner_main(root, cfg)
        started = time.monotonic()
        ctx = load(root, cfg, control=args.control or args.preflight)
        if args.preflight:
            receipts = short_check(root, cfg, ctx["environment_id"])
            ctx["short_check_receipts"] = receipts or {}
            print(
                json.dumps(
                    {
                        "status": "act1_rescue_owner_run_preflight_verified",
                        "environment_id": ctx["environment_id"],
                        "frozen_checks": freeze(root, ctx),
                        "short_native_check": "verified" if receipts else "pending",
                        "game_open": bool(_running_games()),
                        "main_workspace_exists": (root / cfg["workspace"]).exists(),
                        "optimizer_updates": 0,
                    }
                )
            )
            return 0
        if args.control:
            result = control(root, ctx, cfg, started + 260)
        else:
            if args.attempt is None or args.attempt < 1:
                parser.error("Use the resource-tracked owner launcher")
            result = run(root, ctx, args.attempt, started + SESSION_LIMITS["wall_seconds"] - 45)
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(
            json.dumps({"status": "stopped_preserving_evidence", "error": str(exc), **NO_UPDATES})
        )
        return 2
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "status",
                    "report_id",
                    "optimizer_updates",
                    *(("qualification", "collection", "stop", "bank_id") if args.run else ()),
                )
            }
        )
    )
    return (
        0
        if result["status"] in {"act1_rescue_short_checks_verified", "act1_rescue_bank_admitted"}
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
