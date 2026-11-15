"""Evaluate the sealed round-64 heads on the untouched holdout worlds."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_head_grid_resume as previous
from spireshift import native_a8_head_policy as policy
from spireshift import native_a8_head_study as head
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_archive_fit_session import ERRORS
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_crystal_grid import GridWorker
from spireshift.native_a8_head_policy import ARMS
from spireshift.native_a8_own_training import SCOPE
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_reward_exit_recovery import chunk_evidence_id
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

RECIPE = "configs/native-learning/sts2-v0.111.0-a8-scoring-heads-holdout-resume-v1.json"
WRAPPER = "scripts/finish-a8-scoring-heads-holdout-v1.sh"
MODULE = "spireshift.native_a8_head_holdout_resume"
SCHEMA = "native-a8-scoring-heads-holdout-continuation-v1"
COMPLETE = "scoring_heads_holdout_schedule_finished"
FIRST_NEW = 71
STOPPED = "holdout-r064-070-p3-shared"
STOP_REASON = (
    "ValueError: Native worker failed: Native runtime error: [ERROR] [ERROR] "
    "Tried to pop model POWER.STAMPEDE_POWER"
)
LIMITS = {**previous.LIMITS, "wall_seconds": 7200, "storage_bytes": 8_000_000_000}
NO_UPDATES = {**SCOPE, "optimizer_updates": 0}

Rows = dict[tuple[str, int, str], dict[str, Any]]
States = dict[int, dict[str, head.Saved]]
StateRefs = dict[int, dict[str, dict[str, Any]]]


def implementation(root: Path) -> dict[str, str]:
    return {
        name: _sha_file(root / name) for name in (WRAPPER, f"src/{MODULE.replace('.', '/')}.py")
    }


def tasks(stage: str, worlds: list[str], first: int = 1) -> Iterator[dict[str, Any]]:
    for index, world in enumerate(worlds[first - 1 :], first):
        for player in PLAYERS:
            for arm in ARMS if (index + player) % 2 else ARMS[::-1]:
                yield {
                    "key": f"{stage}-r{head.ROUNDS:03d}-{index:03d}-p{player}-{arm}",
                    "round": head.ROUNDS,
                    "seed": world,
                    "player": player,
                    "arm": arm,
                    "partition": "development",
                }


def slot(task: dict[str, Any]) -> tuple[str, int, str]:
    return task["seed"], task["player"], task["arm"]


def add_game(rows: Rows, starts: dict[str, str], task: dict[str, Any], row: dict[str, Any]) -> None:
    seed = task["seed"]
    public_id = row["initial_public_input_id"]
    if starts.setdefault(seed, public_id) != public_id:
        raise ValueError("A matched evaluation world has different public starts")
    rows[slot(task)] = row


def training_lineage(
    recovery: previous.Recovery,
    inherited: previous.Inherited,
    history: ChunkJournal,
    report: dict[str, Any],
) -> tuple[StateRefs, dict[str, dict[str, int]], dict[str, str]]:
    base = recovery.report["training_rounds"]
    rounds = report["training_rounds"]
    if rounds[: len(base)] != base or len(rounds) != head.ROUNDS * len(PLAYERS):
        raise ValueError("Require all 64 sealed training rounds for each initializer")
    before = {row["player"]: row["states"] for row in base if row["round"] == previous.LAST}
    rounds_by_id = {(row["round"], row["player"]): row for row in rounds[len(base) :]}
    seeds = head.world_schedule()["train"]
    seeds[seeds.index(previous.EXCLUDED)] = previous.REPLACEMENT
    outcomes = {arm: Counter(inherited.train_outcomes[arm]) for arm in ARMS}
    checkpoints: dict[str, str] = {}
    for round_index in range(previous.LAST + 1, head.ROUNDS + 1):
        start = (round_index - 1) * head.WORLDS_PER_ROUND
        worlds = seeds[start : start + head.WORLDS_PER_ROUND]
        starts: dict[str, str] = {}
        for player in PLAYERS:
            games: dict[str, list[str]] = {arm: [] for arm in ARMS}
            for index, seed in enumerate(worlds, 1):
                for arm in ARMS:
                    task = previous.train_task(round_index, index, player, arm, seed)
                    if seed == previous.REPLACEMENT:
                        task["seed_id"] = recovery.cfg["replacement"]["seed_id"]
                    key = task["key"]
                    source = recovery.history if key in inherited.carried else history
                    row = previous.load_game(source, task, before[player][arm])
                    if starts.setdefault(seed, row["initial_public_input_id"]) != row[
                        "initial_public_input_id"
                    ] or (key in inherited.carried and row["seal_id"] != inherited.carried[key]):
                        raise ValueError("The sealed round has mismatched starts or carried games")
                    games[arm].append(row["seal_id"])
                    outcomes[arm][row["outcome"]] += 1
                    outcomes[arm]["act1_clears"] += row["completed_acts"] > 0
            fit_key = f"fit-p{player}-r{round_index:03d}"
            request = {
                "prior": {arm: before[player][arm]["state_id"] for arm in ARMS},
                "games": games,
            }
            seal = previous.header(history, fit_key, request, full=round_index == head.ROUNDS)
            fit = seal["result"]
            if {**fit, "seal_id": seal["report_id"]} != rounds_by_id[round_index, player] or any(
                fit["states"][arm]["value_steps"] - before[player][arm]["value_steps"]
                != fit["work"]["optimizer_steps_per_arm"]
                for arm in ARMS
            ):
                raise ValueError(f"The matched optimizer lineage differs at {fit_key}")
            before[player] = fit["states"]
            if round_index == head.ROUNDS:
                for arm in ARMS:
                    path = str((history.path(fit_key) / f"{arm}.json").relative_to(recovery.root))
                    checkpoints[path] = seal["sources"][path]
    return before, {arm: dict(counts) for arm, counts in outcomes.items()}, checkpoints


def saved_evaluation(
    history: ChunkJournal, stage: str, worlds: list[str], final: StateRefs
) -> Rows:
    rows: Rows = {}
    starts: dict[str, str] = {}
    interrupted = worlds[FIRST_NEW - 2] if stage == "holdout" else None
    started = set(worlds[: FIRST_NEW - 1] if interrupted else worlds)
    for task in tasks(stage, worlds):
        seed, player, arm = slot(task)
        key = task["key"]
        target = history.path(key)
        if key == STOPPED:
            active = json.loads((target / "active.json").read_text())
            request = previous.game_request(task, final[player][arm])
            if (
                active["key"] != key
                or active["config_id"] != history.config_id
                or active["request"] != request
                or active["request_id"] != manifest_identifier(request)
                or (target / "done.json").exists()
            ):
                raise ValueError("The preserved holdout failure differs")
            rows[slot(task)] = {"outcome": "failed"}
        elif seed not in started or (seed == interrupted and player == PLAYERS[-1]):
            if target.exists():
                raise ValueError("An excluded or untouched holdout cell was started")
        else:
            row = previous.load_game(history, task, final[player][arm], full=True)
            add_game(rows, starts, task, row)
    return rows


@dataclass
class Audit:
    previous_report_id: str
    control_id: str
    states: States
    checkpoint_ids: dict[str, dict[str, str]]
    checkpoint_sources: dict[str, str]
    training_outcomes: dict[str, dict[str, int]]
    progress: dict[str, Any]
    holdout_rows: Rows

    def evaluation(self, worlds: list[str], rows: Rows) -> dict[str, Any]:
        return {"checkpoint_ids": self.checkpoint_ids, **head.evaluate(worlds, rows)}


def audit(recovery: previous.Recovery, cfg: dict[str, Any], history: ChunkJournal) -> Audit:
    root = recovery.root
    inherited = previous.inspect_history(recovery.history, recovery.report)
    control_id = previous.require_control(recovery, inherited)
    report_path = verified(root, cfg["parent_report"])
    report = identified(report_path)
    resources_path = verified(root, cfg["parent_resources"])
    resources = identified(resources_path)
    attempt = resources_path.stem.removeprefix("resources-")
    if (
        verified(root, cfg["parent_recipe"]) != root / previous.RECIPE
        or report_path != history.workspace / f"session-{attempt}.json"
        or resources_path != history.workspace / f"resources-{attempt}.json"
        or json.loads((history.workspace / "config-at-launch.json").read_text()) != history.recipe
        or report["config_id"] != history.config_id
        or report["schema_version"] != previous.SCHEMA
        or report["parent_report_id"] != recovery.report["report_id"]
        or report["control_id"] != control_id
        or report["carried_games"] != inherited.carried
        or report["replacement"] != recovery.cfg["replacement"]
        or report["status"] != "stopped_preserving_evidence"
        or report["stop"]["unit"] != STOPPED
        or not report["stop"]["error"].startswith(STOP_REASON)
        or resources["status"] != "failed"
        or resources["exit_code"] != 2
        or resources["cap"] is not None
        or resources["artifacts"]["roots"] != [str(history.workspace)]
        or chunk_evidence_id(history.path(STOPPED)) != cfg["stopped_evidence_id"]
    ):
        raise ValueError("Require the exact stopped round-64 holdout evidence")
    final, outcomes, sources = training_lineage(recovery, inherited, history, report)
    worlds = head.world_schedule()
    ids = {str(p): {arm: final[p][arm]["state_id"] for arm in ARMS} for p in PLAYERS}
    session = head.Session(recovery.original, control=False, deadline=0)
    session.store = history
    states = {
        p: {
            arm: session.checkpoint(f"fit-p{p}-r{head.ROUNDS:03d}", arm, final[p][arm])
            for arm in ARMS
        }
        for p in PLAYERS
    }
    progress = saved_evaluation(history, "progress", worlds["progress"], final)
    holdout = saved_evaluation(history, "holdout", worlds["holdout"], final)
    saved = Audit(
        report["report_id"], control_id, states, ids, sources, outcomes, report["progress"], holdout
    )
    if (
        saved.progress
        != {
            **recovery.report["progress"],
            str(head.ROUNDS): saved.evaluation(worlds["progress"], progress),
        }
        or saved.evaluation(worlds["holdout"], holdout) != report["holdout"]
        or report["verified_games"] != 4694
        or len(holdout) != 279
    ):
        raise ValueError("The saved progress and holdout counts do not reconstruct")
    return saved


def unchanged(
    recovery: previous.Recovery, cfg: dict[str, Any], saved: Audit, profile: dict[str, Any]
) -> None:
    recovery.unchanged(profile)
    if json.loads((recovery.root / RECIPE).read_text()) != cfg:
        raise ValueError("The holdout continuation recipe changed")
    check_sources(recovery.root, {**cfg["implementation"], **saved.checkpoint_sources})
    for field in ("parent_recipe", "parent_report", "parent_resources"):
        verified(recovery.root, cfg[field])
    history = ChunkJournal(recovery.root, recovery.cfg)
    if chunk_evidence_id(history.path(STOPPED)) != cfg["stopped_evidence_id"]:
        raise ValueError("The preserved holdout failure changed")


def run(
    recovery: previous.Recovery, cfg: dict[str, Any], saved: Audit, attempt: int
) -> dict[str, Any]:
    session = head.Session(
        recovery.original, control=False, deadline=time.monotonic() + LIMITS["wall_seconds"] - 45
    )
    session.store = ChunkJournal(recovery.root, cfg)
    worlds = head.world_schedule()["holdout"]
    remaining = list(tasks("holdout", worlds, FIRST_NEW))
    rows = saved.holdout_rows.copy()
    starts: dict[str, str] = {}
    final = session.store.workspace / "report.json"
    with session.store.lock():
        if final.is_file():
            report = identified(final)
            if (
                report["config_id"] != session.store.config_id
                or report["parent_report_id"] != saved.previous_report_id
                or report["status"] != COMPLETE
            ):
                raise ValueError("The completed holdout belongs to a different recipe")
            return report
        status, stop = COMPLETE, None
        task: dict[str, Any] | None = None
        try:
            with patch.object(policy, "SelectorWorker", GridWorker):
                for index, task in enumerate(remaining, 1):
                    row = session.game(task, saved.states[task["player"]][task["arm"]])
                    add_game(rows, starts, task, row)
                    if index % (len(PLAYERS) * len(ARMS) * 8) == 0 or index == len(remaining):
                        print(
                            f"Remaining holdout schedule: {index}/{len(remaining)} games",
                            flush=True,
                        )
        except head.CleanPause as exc:
            status, stop = "paused", {"unit": session.active, "reason": str(exc)}
        except ERRORS as exc:
            status, stop = (
                "stopped_preserving_evidence",
                {
                    "unit": session.active,
                    "error": f"{type(exc).__name__}: {exc}",
                },
            )
            if task is not None and session.store.path(task["key"]).exists():
                rows[slot(task)] = {"outcome": "failed"}
        unchanged(recovery, cfg, saved, session.profile)
        target = (
            final if status == COMPLETE else session.store.workspace / f"session-{attempt}.json"
        )
        return write(
            target,
            {
                "schema_version": SCHEMA,
                "config_id": session.store.config_id,
                "status": status,
                "parent_report_id": saved.previous_report_id,
                "control_id": saved.control_id,
                "prior_verified_holdout_games": len(saved.holdout_rows) - 1,
                "untouched_schedule_games": len(remaining),
                "verified_schedule_games": session.games_seen,
                "preserved_failure": STOPPED,
                "preserved_unattempted": "holdout-r064-070-p3-split",
                "training_rounds_per_initializer": head.ROUNDS,
                "training_outcomes": saved.training_outcomes,
                "progress": saved.progress[str(head.ROUNDS)],
                "holdout": saved.evaluation(worlds, rows),
                "stop": stop,
                "frozen_checks": recovery.original.source.study.frozen_checks,
                **NO_UPDATES,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--execute", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the launcher with the frozen numerical thread settings")
        root = Path.cwd()
        cfg = json.loads((root / RECIPE).read_text())
        store = ChunkJournal(root, cfg)
        if (
            cfg["schema_version"] != SCHEMA
            or cfg["first_unstarted_world"] != FIRST_NEW
            or cfg["limits"] != LIMITS
            or cfg["implementation"] != implementation(root)
        ):
            raise ValueError("Require the exact holdout-only continuation")
        if args.preflight or args.execute is not None:
            recovery = previous.load(root)
            history = ChunkJournal(root, recovery.cfg)
            if store.workspace in {
                history.workspace,
                recovery.history.workspace,
                previous.control_store(recovery).workspace,
            }:
                raise ValueError("The holdout continuation needs its own workspace")
            with recovery.source_lock(), (history.workspace / "session.lock").open("rb") as lock:
                fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
                saved = audit(recovery, cfg, history)
                unchanged(recovery, cfg, saved, _shared_snapshot(Path.home() / SHARED_PROFILE))
                if args.preflight:
                    print(
                        json.dumps(
                            {
                                "status": "holdout_continuation_ready",
                                "training_rounds_per_initializer": head.ROUNDS,
                                "training_outcomes": saved.training_outcomes,
                                "checkpoint_ids": saved.checkpoint_ids,
                                "verified_holdout_games": len(saved.holdout_rows) - 1,
                                "unstarted_holdout_worlds": head.HOLDOUT_WORLDS - FIRST_NEW + 1,
                                "frozen_checks": recovery.original.source.study.frozen_checks,
                                **NO_UPDATES,
                            }
                        )
                    )
                    return 0
                if _running_games():
                    raise ValueError("Close STS2 and wait for any other native worker")
                result = run(recovery, cfg, saved, args.execute)
                print(json.dumps(result))
                return 0 if result["status"] in {COMPLETE, "paused"} else 2
        attempt = time.time_ns()
        print(
            "Evaluate the sealed round-64 checkpoints on worlds 71–128. Zero optimizer updates.",
            flush=True,
        )
        tracked = run_tracked_command(
            command=["uv", "run", "--no-sync", "python", "-m", MODULE, "--execute", str(attempt)],
            experiment_kind=ExperimentKind.BENCHMARK,
            working_directory=root,
            report_path=store.workspace / f"resources-{attempt}.json",
            artifact_roots=[store.workspace],
            limits=ResourceLimits(**LIMITS),
            poll_interval_seconds=8,
        )
        print(json.dumps(tracked.report))
        return 0 if tracked.exit_code == 0 and tracked.report["cap"] is None else 2
    except ERRORS as exc:
        print(
            json.dumps({"status": "stopped_preserving_evidence", "error": str(exc), **NO_UPDATES})
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
