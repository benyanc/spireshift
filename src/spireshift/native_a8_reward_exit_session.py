"""Recover one saved world and continue only the untouched ordinary-lethal pairs."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_ordinary_policy import REASON
from spireshift.native_a8_ordinary_session import (
    ARMS,
    WORLD_RESERVE,
    load,
    require_short,
    saved_check,
)
from spireshift.native_a8_rescue_curriculum import first_change
from spireshift.native_a8_rescue_game import TRACE
from spireshift.native_a8_rescue_inputs import CONTROL_LIMITS, SESSION_LIMITS
from spireshift.native_a8_rescue_session import NO_UPDATES
from spireshift.native_a8_reward_exit_episode import play
from spireshift.native_a8_reward_exit_recovery import previous_attempt, recover, saved_regressions
from spireshift.native_a8_tactical_session import boundary, frozen
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-act1-ordinary-lethal-continuation-v1.json"
MODULE = "spireshift.native_a8_reward_exit_session"
RECOVERY_KEY = "saved-world-recovery"


def pair(
    ctx: dict[str, Any], case: dict[str, Any], target: Path, deadline: float
) -> dict[str, Any]:
    rows = {arm: play(ctx, case, arm, target / arm, deadline) for arm in ARMS}
    if rows["tactical"]["initial_public_input_id"] != rows["ordinary"]["initial_public_input_id"]:
        raise ValueError("Both planners must start on the same public menu")
    outcomes = {arm: row["outcome"] for arm, row in rows.items()}
    changed = first_change(target / "tactical" / TRACE, target / "ordinary" / TRACE)
    if changed is not None and changed["reason"] != REASON:
        raise ValueError("First planner difference lacks an ordinary-fight lethal intervention")
    if "capped" not in outcomes.values() and len(set(outcomes.values())) > 1 and changed is None:
        raise ValueError("Different outcomes require a verified same-menu intervention")
    confirmed = outcomes == {"tactical": "act1_loss", "ordinary": "act1_clear"}
    if confirmed:
        confirmation = play(ctx, case, "ordinary", target / "confirmation", deadline)
        if (
            confirmation["outcome"] != "act1_clear"
            or confirmation["semantic_trajectory_sha256"]
            != rows["ordinary"]["semantic_trajectory_sha256"]
        ):
            raise ValueError("The fresh ordinary-fight rescue did not reproduce")
        rows["confirmation"] = confirmation
    return {
        "case": case,
        "episodes": rows,
        "outcomes": outcomes,
        "first_change": changed,
        "confirmed_rescue": confirmed,
    }


def control_store(root: Path, cfg: dict[str, Any]) -> ChunkJournal:
    return ChunkJournal(root, {**cfg, "workspace": cfg["control_workspace"]})


def short_check(
    root: Path,
    ctx: dict[str, Any],
    cfg: dict[str, Any],
    previous: ChunkJournal,
    attempt: dict[str, Any],
    resources: dict[str, Any],
    interrupted: dict[str, Any],
    deadline: float,
) -> dict[str, Any]:
    store = control_store(root, cfg)
    smoke = cfg["smoke"]
    if smoke["seed"] in {c["seed"] for c in [previous.recipe["smoke"], *previous.recipe["worlds"]]}:
        raise ValueError("Use a disjoint fresh start for the shared evaluator smoke check")
    with store.lock():
        before, profile = frozen(root, ctx), _shared_snapshot(Path.home() / SHARED_PROFILE)
        request = {"source": interrupted, "attempt": attempt["report_id"]}
        output = store.begin(RECOVERY_KEY, request)
        recovery = recover(
            ctx,
            interrupted,
            previous.path(interrupted["key"]),
            output,
            attempt,
            resources,
            deadline,
        )
        regressions = saved_regressions(root, ctx, cfg)
        boundary(root, ctx, before, profile)
        recovered = store.commit(
            RECOVERY_KEY, request, {**recovery, "saved_regressions": regressions}
        )
        hp = recovery["episodes"]["ordinary"]["final_hp"]
        print(f"Saved {interrupted['key']} Act 2 entry at {hp} HP", flush=True)
        target = store.begin(smoke["key"], smoke)
        result = pair(ctx, smoke, target, deadline)
        boundary(root, ctx, before, profile)
        check_sources(root, cfg["implementation"])
        sealed = store.commit(smoke["key"], smoke, result)
        return write(
            store.workspace / "report.json",
            {
                "schema_version": "native-a8-boss-reward-exit-short-v1",
                "status": (
                    "boss_reward_exit_short_verified"
                    if "capped" not in result["outcomes"].values()
                    else "boss_reward_exit_short_incomplete"
                ),
                "config_id": store.config_id,
                "execution_id": ctx["reward_exit_execution_id"],
                "recovery_proof_id": recovered["report_id"],
                "smoke_seal_id": sealed["report_id"],
                "smoke_outcomes": result["outcomes"],
                "smoke_native_deliveries": sum(
                    e["verified_native_deliveries"] for e in result["episodes"].values()
                ),
                "saved_regressions": regressions,
                "frozen_checks": before,
                "shared_profile_unchanged": True,
                **NO_UPDATES,
            },
        )


def require_control(
    root: Path, ctx: dict[str, Any], cfg: dict[str, Any], request: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    store, smoke = control_store(root, cfg), cfg["smoke"]
    report = identified(store.workspace / "report.json")
    resources = identified(root / cfg["control_resource"])
    recovered = store.completed(RECOVERY_KEY, request)
    sealed = store.completed(smoke["key"], smoke)
    if (
        report["status"] != "boss_reward_exit_short_verified"
        or report["config_id"] != store.config_id
        or report["execution_id"] != ctx["reward_exit_execution_id"]
        or report["frozen_checks"] != frozen(root, ctx)
        or recovered is None
        or recovered["report_id"] != report["recovery_proof_id"]
        or recovered["result"]["source_chunk_id"] != cfg["interrupted_chunk_id"]
        or sealed is None
        or sealed["report_id"] != report["smoke_seal_id"]
        or resources["exit_code"] != 0
        or resources["status"] != "completed"
        or resources["cap"] is not None
        or resources["command"] != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--control"]
        or resources["artifacts"]["roots"] != [str(store.workspace)]
    ):
        raise ValueError(
            "The exact passing shared reward exit and saved recovery checks are required"
        )
    return report, recovered


def run(
    root: Path,
    ctx: dict[str, Any],
    cfg: dict[str, Any],
    previous: ChunkJournal,
    attempt: dict[str, Any],
    remaining: list[dict[str, Any]],
    short: dict[str, Any],
    recovered: dict[str, Any],
    attempt_number: int,
    deadline: float,
) -> dict[str, Any]:
    store = ChunkJournal(root, cfg)
    with store.lock():
        before, profile = frozen(root, ctx), _shared_snapshot(Path.home() / SHARED_PROFILE)
        rows, seals, stop = [], {}, None
        for case in remaining:
            key = case["key"]
            try:
                seal = store.completed(key, case)
                if seal is None:
                    if time.monotonic() + WORLD_RESERVE > deadline:
                        stop = {"world": key, "reason": "wall_reserve"}
                        break
                    result = pair(ctx, case, store.begin(key, case), deadline)
                    boundary(root, ctx, before, profile)
                    check_sources(root, cfg["implementation"])
                    seal = store.commit(key, case, result)
            except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
                stop = {"world": key, "reason": "unsealed_world", "error": str(exc)}
                break
            rows.append(seal["result"])
            seals[key] = seal["report_id"]
            print(f"{key} {rows[-1]['outcomes']}", flush=True)
        boundary(root, ctx, before, profile)
        check_sources(root, cfg["implementation"])
        previous_attempt(root, ctx, cfg, previous)
        counts = {arm: Counter(r["outcomes"][arm] for r in rows) for arm in ARMS}
        complete = (
            stop is None
            and len(rows) == len(remaining)
            and not any(c["capped"] for c in counts.values())
        )
        saved = recovered["result"]
        return write(
            store.workspace / f"attempt-{attempt_number}.json",
            {
                "schema_version": "native-a8-ordinary-lethal-continuation-v1",
                "status": "ordinary_lethal_continuation_complete"
                if complete
                else "ordinary_lethal_continuation_incomplete",
                "config_id": store.config_id,
                "execution_id": ctx["reward_exit_execution_id"],
                "short_check_id": short["report_id"],
                "objective": previous.recipe["objective"],
                "original_planned_worlds": attempt["planned_worlds"],
                "original_seals": attempt["seals"],
                "original_interruption": attempt["stop"],
                "saved_diagnostic": {
                    "world": saved["case"]["key"],
                    "recovery_proof_id": recovered["report_id"],
                    "tactical_outcome": saved["episodes"]["tactical"]["natural_outcome"],
                    "ordinary_outcome": saved["episodes"]["ordinary"]["natural_outcome"],
                    "ordinary_hp": saved["episodes"]["ordinary"]["final_hp"],
                    "included_in_confirmed_rescues": False,
                },
                "new_planned_worlds": len(remaining),
                "new_seals": seals,
                "new_unstarted_worlds": [
                    c["key"] for c in remaining if not store.path(c["key"]).exists()
                ],
                "new_unsealed_worlds": [
                    c["key"]
                    for c in remaining
                    if store.path(c["key"]).exists() and c["key"] not in seals
                ],
                "sealed_pair_outcomes": {
                    arm: {
                        k: attempt["outcomes_by_arm"][arm][k] + count[k]
                        for k in ("act1_clear", "act1_loss", "capped")
                    }
                    for arm, count in counts.items()
                },
                "confirmed_rescues": [
                    *attempt["confirmed_rescues"],
                    *(r["case"]["key"] for r in rows if r["confirmed_rescue"]),
                ],
                "new_changed_worlds": [r["case"]["key"] for r in rows if r["first_change"]],
                "new_ordinary_lethal_deliveries": sum(
                    r["episodes"]["ordinary"]["tactical_deliveries"].get(REASON, 0) for r in rows
                ),
                "new_verified_native_deliveries": sum(
                    e["verified_native_deliveries"] for r in rows for e in r["episodes"].values()
                ),
                "frozen_checks": before,
                "shared_profile_unchanged": True,
                "stop": stop,
                "lessons_admitted": 0,
                **NO_UPDATES,
            },
        )


def execute(
    root: Path, cfg: dict[str, Any], mode: str, attempt_number: int, deadline: float
) -> dict[str, Any]:
    check_sources(root, cfg["implementation"])
    previous_config = json.loads(verified(root, cfg["previous_recipe"]).read_text())
    ctx = load(root, previous_config)
    require_short(root, ctx, saved_check(root, ctx))
    previous = ChunkJournal(root, previous_config)
    ctx["reward_exit_execution_id"] = ChunkJournal(root, cfg).config_id
    with (previous.workspace / "session.lock").open("rb") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("The original comparison still owns its evidence") from exc
        attempt, resources, interrupted, remaining = previous_attempt(root, ctx, cfg, previous)
        if mode != "preflight" and _running_games():
            raise ValueError("Close STS2 and wait for any other native worker")
        if mode == "control":
            return short_check(root, ctx, cfg, previous, attempt, resources, interrupted, deadline)
        request = {"source": interrupted, "attempt": attempt["report_id"]}
        short, recovered = require_control(root, ctx, cfg, request)
        if mode == "preflight":
            return {
                "status": "ordinary_lethal_continuation_ready",
                "previous_attempt_id": attempt["report_id"],
                "saved_recovery_proof_id": recovered["report_id"],
                "short_check_id": short["report_id"],
                "remaining_worlds": [case["key"] for case in remaining],
                **NO_UPDATES,
            }
        return run(
            root, ctx, cfg, previous, attempt, remaining, short, recovered, attempt_number, deadline
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    for mode in ("preflight", "short", "control", "run"):
        modes.add_argument(f"--{mode}", dest="mode", action="store_const", const=mode)
    parser.add_argument("--attempt", type=int)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the pinned single-thread continuation launcher")
        cfg = json.loads((root / RECIPE).read_text())
        if args.mode in (None, "short"):
            short = args.mode == "short"
            attempt = time.time_ns()
            if not short:
                print(
                    "Nine previously unstarted worlds, ordinary-008 through ordinary-016. "
                    "Allow about 4–8 minutes. The world 7 recovery stays diagnostic. "
                    "Close STS2 before running. Zero optimizer updates.",
                    flush=True,
                )
            resources = run_tracked_command(
                command=[
                    "uv",
                    "run",
                    "--no-sync",
                    "python",
                    "-m",
                    MODULE,
                    *(["--control"] if short else ["--run", "--attempt", str(attempt)]),
                ],
                experiment_kind=ExperimentKind.OTHER,
                report_path=root
                / (
                    cfg["control_resource"] if short else f"{cfg['resource_prefix']}-{attempt}.json"
                ),
                artifact_roots=[root / cfg["control_workspace" if short else "workspace"]],
                working_directory=root,
                limits=ResourceLimits(**(CONTROL_LIMITS if short else SESSION_LIMITS)),
            )
            print(json.dumps(resources.report, indent=2))
            return 0 if resources.exit_code == 0 and resources.status == "completed" else 2
        if args.mode == "run" and (args.attempt is None or args.attempt < 1):
            raise ValueError("Use the tracked owner launcher for the nine-world continuation")
        limits = CONTROL_LIMITS if args.mode == "control" else SESSION_LIMITS
        result = execute(
            root, cfg, args.mode, args.attempt or 0, started + limits["wall_seconds"] - 20
        )
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(
            json.dumps({"status": "stopped_preserving_evidence", "error": str(exc), **NO_UPDATES})
        )
        return 2
    print(json.dumps(result))
    return (
        0
        if result["status"]
        in {
            "boss_reward_exit_short_verified",
            "ordinary_lethal_continuation_ready",
            "ordinary_lethal_continuation_complete",
        }
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
