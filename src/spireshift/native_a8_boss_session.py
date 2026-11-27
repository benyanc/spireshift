"""Qualify an Act 1 boss teacher on prospectively declared normal starts."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.native_a8_boss_checks import SHARED_PROFILE, compare_teachers, control
from spireshift.native_a8_boss_game import ARMS, play
from spireshift.native_a8_boss_inputs import MODULE, declaration, freeze, load, short_check
from spireshift.native_a8_rescue_inputs import GAME_LIMITS, SESSION_LIMITS
from spireshift.native_a8_rescue_session import NO_UPDATES
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_win4_game import write

WORLD_RESERVE = 5 * (GAME_LIMITS["episode_wall_seconds"] + 20) + 40


def qualify(planned: int, gate: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {arm: Counter(row["outcomes"][arm] for row in rows) for arm in ARMS}
    rescues = [row for row in rows if row["strict_rescue_confirmed"]]
    clears = [row for row in rows if row["confirmed_clear"]]
    players = sorted({row["case"]["player"] for row in rescues})
    checks = {
        "all_worlds_sealed": len(rows) == planned,
        "no_capped_arms": all(not count["capped"] for count in counts.values()),
        "minimum_confirmed_clears": len(clears) >= gate["minimum_confirmed_clears"],
        "strict_rescues_across_both_initializers": players == gate["strict_rescue_initializers"],
        "boss_teacher_cleared_more_than_each_reference": all(
            counts["boss"]["act1_clear"] > counts[arm]["act1_clear"] for arm in ARMS[:-1]
        ),
    }
    return {
        "planned_worlds": planned,
        "sealed_worlds": len(rows),
        "outcomes_by_arm": {
            arm: {k: count[k] for k in ("act1_clear", "act1_loss", "capped")}
            for arm, count in counts.items()
        },
        "boss_encounters_reached_by_arm": {
            arm: sum(1 for row in rows if row["episodes"][arm]["actual_boss_combat_observed"])
            for arm in ARMS
        },
        "confirmed_clears": [row["case"]["key"] for row in clears],
        "strict_rescues": [row["case"]["key"] for row in rescues],
        "strict_rescue_initializers": players,
        "checks": checks,
        "passed": all(checks.values()),
    }


def play_world(
    ctx: dict[str, Any], case: dict[str, Any], target: Path, deadline: float
) -> dict[str, Any]:
    episodes = {}
    for arm in ARMS:
        episodes[arm] = play(ctx, case, arm, target / arm, deadline)
        if len({row["initial_public_input_id"] for row in episodes.values()}) != 1:
            raise ValueError("Matched arms started from different public inputs or choices")
    outcomes = {arm: episode["outcome"] for arm, episode in episodes.items()}
    change = compare_teachers(target)
    if (
        outcomes["boss"] != outcomes["survival"]
        and "capped" not in (outcomes["boss"], outcomes["survival"])
        and change is None
    ):
        raise ValueError("Different teacher outcomes lack a verified same-menu change")
    confirmed = outcomes["boss"] == "act1_clear"
    if confirmed:
        repetition = play(ctx, case, "confirmation", target / "confirmation", deadline)
        episodes["confirmation"] = repetition
        if (
            repetition["outcome"] != "act1_clear"
            or repetition["semantic_trajectory_sha256"]
            != episodes["boss"]["semantic_trajectory_sha256"]
        ):
            raise ValueError("The boss teacher clear did not reproduce from the same fresh start")
    return {
        "case": case,
        "episodes": episodes,
        "outcomes": outcomes,
        "first_different_teacher_action": change,
        "confirmed_clear": confirmed,
        "strict_rescue_confirmed": confirmed
        and all(outcomes[arm] == "act1_loss" for arm in ARMS[:-1]),
    }


def run(root: Path, ctx: dict[str, Any], attempt: int, deadline: float) -> dict[str, Any]:
    cfg = ctx["boss_config"]
    store = ChunkJournal(root, cfg)
    shared = Path.home() / SHARED_PROFILE
    with store.lock():
        if _running_games():
            raise ValueError("Close STS2 and wait for the other native process")
        frozen, profile = freeze(root, ctx), _shared_snapshot(shared)
        launch = write(
            store.workspace / f"launch-{attempt}.json",
            {
                "config_id": store.config_id,
                "frozen_build_environment_id": ctx["environment_id"],
                "execution_id": ctx["execution_id"],
                "objective": cfg["objective"],
                "checkpoints": ctx["states"],
                "frozen_checks": frozen,
                "shared_profile": profile,
                "short_check_receipts": ctx["boss_short_receipts"],
            },
        )
        planned = cfg["worlds"]
        keys = [case["key"] for case in planned]
        if {p.name for p in (store.workspace / "chunks").glob("*")} - set(keys):
            raise ValueError("Preserve unexpected boss qualification evidence")
        seals = {case["key"]: store.completed(case["key"], case) for case in planned}
        existing = [key for key, seal in seals.items() if seal is not None]
        if existing != keys[: len(existing)]:
            raise ValueError("Boss qualification seals must be a complete prefix")

        rows, stopped = [], None
        status = "act1_boss_teacher_qualification_blocked"
        for case in planned:
            key = case["key"]
            seal = seals[key]
            if seal is None:
                if deadline - time.monotonic() < WORLD_RESERVE:
                    status = "paused_at_clean_boundary"
                    stopped = {"case": case, "reason": "wall_reserve"}
                    break
                target = store.begin(key, case)
                try:
                    row = play_world(ctx, case, target, deadline)
                    seal = store.commit(key, case, row)
                except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
                    status = "stopped_preserving_evidence"
                    stopped = {"case": case, "reason": "unsealed_world", "error": str(exc)}
                    break
                print(f"{key} p{case['player']} {row['outcomes']}", flush=True)
            rows.append(seal["result"])
        if freeze(root, ctx) != frozen or _shared_snapshot(shared) != profile or _running_games():
            raise ValueError("Frozen inputs, worker exit or shared profile differs")
        result = qualify(len(planned), cfg["gate"], rows)
        if result["passed"] and stopped is None:
            status = "act1_boss_teacher_qualified"
        return write(
            store.workspace / f"attempt-{attempt}.json",
            {
                "schema_version": "native-a8-act1-boss-qualification-result-v1",
                "status": status,
                "launch_id": launch["report_id"],
                "config_id": store.config_id,
                "execution_id": ctx["execution_id"],
                "qualification": result,
                "worlds": [{**case, "sealed": i < len(rows)} for i, case in enumerate(planned)],
                "stop": stopped,
                "frozen_checks": frozen,
                "shared_profile_unchanged": True,
                "lessons_admitted": 0,
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
    return subprocess.call(
        [
            *command,
            "--",
            "uv",
            "run",
            "--no-sync",
            "python",
            "-m",
            MODULE,
            *arguments,
        ],
        cwd=root,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--control", action="store_true")
    modes.add_argument("--short-only", action="store_true")
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--run", action="store_true")
    parser.add_argument("--attempt", type=int)
    args = parser.parse_args()
    root = Path.cwd()
    started = time.monotonic()
    try:
        if not args.preflight and _running_games():
            raise ValueError("Close STS2 before the isolated native run")
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the pinned single-thread numerical settings")
        cfg = declaration(root)
        ctx = load(root, cfg)
        receipts = None if args.control else short_check(root, ctx)
        if args.preflight:
            ctx["boss_short_receipts"] = receipts or {}
            print(
                json.dumps(
                    {
                        "status": "act1_boss_preflight_verified",
                        "frozen_checks": freeze(root, ctx),
                        "short_check": "verified" if receipts else "pending",
                        "qualification_started": (root / cfg["workspace"]).exists(),
                        "optimizer_updates": 0,
                    }
                )
            )
            return 0
        if args.control:
            result = control(root, ctx, started + 260)
        elif args.short_only:
            return (
                0
                if receipts
                else tracked(
                    root,
                    cfg["control_resource"],
                    cfg["control_workspace"],
                    cfg["control_limits"],
                    ["--control"],
                )
            )
        else:
            if receipts is None:
                raise ValueError("The separate short native check must pass before qualification")
            ctx["boss_short_receipts"] = receipts
            if args.run:
                if args.attempt is None or args.attempt < 1:
                    parser.error("Use the resource-tracked owner launcher")
                result = run(root, ctx, args.attempt, started + SESSION_LIMITS["wall_seconds"] - 45)
            else:
                attempt = time.time_ns()
                print(
                    "Eight fresh normal-start Ironclad/A8 worlds with four matched arms.\n"
                    "Original, update 200, survival teacher and boss teacher.\n"
                    "The generated card-choice belt repair is active for every arm.\n"
                    "Expect about 10–25 minutes. The outer cap is 90 minutes.\n"
                    "Qualification only. Zero optimizer updates.",
                    flush=True,
                )
                return tracked(
                    root,
                    f"artifacts/resources/a8-act1-boss-v1-{attempt}.json",
                    cfg["workspace"],
                    cfg["session_limits"],
                    ["--run", "--attempt", str(attempt)],
                )
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(
            json.dumps({"status": "stopped_preserving_evidence", "error": str(exc), **NO_UPDATES})
        )
        return 2
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "status",
                    "report_id",
                    "optimizer_updates",
                    *(("qualification", "stop") if args.run else ("verified_deliveries",)),
                )
            }
        )
    )
    return (
        0
        if result["status"] in {"act1_boss_short_check_verified", "act1_boss_teacher_qualified"}
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
