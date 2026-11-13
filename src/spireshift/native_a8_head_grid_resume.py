"""Carry the verified head-study checkpoint into the repaired native suffix."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_crystal_grid as grid
from spireshift import native_a8_head_policy as policy
from spireshift import native_a8_head_study as head
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.native_a8_archive_fit_session import ERRORS
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_head_policy import ARMS
from spireshift.native_a8_own_training import SCOPE
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_paired_report import TERMINAL
from spireshift.native_a8_reward_exit_recovery import chunk_evidence_id
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_a8_head_grid_resume"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-scoring-heads-grid-resume-v1.json"
WRAPPER = "scripts/resume-a8-scoring-heads-v1.sh"
SCHEMA = "native-a8-scoring-heads-crystal-grid-continuation-v1"
CONTROL = "native_crystal_grid_choices_verified"
LAST = 57
STOPPED = "train-r058-03-p2-split"
ERROR = "ValueError: Native worker failed: Missing native public event-option export fields"
EXCLUDED = "SP1RESH1FTA8HDT0915"
REPLACEMENT = "SP1RESH1FTA8HDT1025"
CONTROL_SEEDS = ("SP1RESH1FTA8CGC101", "SP1RESH1FTA8CGC102")
PREFIX_SEED = "SP1RESH1FTA8CGP101"
LIMITS = {**head.LIMITS, "wall_seconds": 21_600, "storage_bytes": 24_000_000_000}


def implementation(root: Path) -> dict[str, str]:
    files = {
        WRAPPER,
        f"src/{MODULE.replace('.', '/')}.py",
        "src/spireshift/native_a8_crystal_grid.py",
        *(f"scripts/{name}" for name in worker_helpers(root, grid.SCRIPT)),
        *(f"scripts/{name}" for name in worker_helpers(root, grid.SAVED)),
    }
    return {name: _sha_file(root / name) for name in sorted(files)}


def train_task(r: int, i: int, p: int, arm: str, seed: str) -> dict[str, Any]:
    return {
        "key": f"train-r{r:03d}-{i:02d}-p{p}-{arm}",
        "round": r,
        "player": p,
        "arm": arm,
        "seed": seed,
        "seed_id": (r - 1) * head.WORLDS_PER_ROUND + i,
        "partition": "train",
    }


def game_request(task: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return {"task": task, "behavior_state_id": state["state_id"], "model_id": state["model_id"]}


def header(
    history: ChunkJournal, key: str, request: dict[str, Any], *, full: bool = False
) -> dict[str, Any]:
    target = history.path(key)
    if full:
        seal = history.completed(key, request)
        if seal is None:
            raise ValueError(f"Missing carried evidence for {key}")
        return seal
    seal = identified(target / "done.json")
    if (
        seal["key"] != key
        or seal["schema_version"] != "native-context-chunk-commit-v1"
        or seal["config_id"] != history.config_id
        or seal["request_id"] != manifest_identifier(request)
    ):
        raise ValueError(f"The original seal belongs to another request: {key}")
    return seal


def load_game(
    history: ChunkJournal, task: dict[str, Any], state: dict[str, Any], *, full: bool = False
) -> dict[str, Any]:
    seal = header(history, task["key"], game_request(task, state), full=full)
    row = seal["result"]
    if (
        row["task"] != task
        or row["model_id"] != state["model_id"]
        or row["outcome"] not in TERMINAL
    ):
        raise ValueError(f"The saved terminal game differs from its task: {task['key']}")
    return {**row, "seal_id": seal["report_id"]}


def checkpoint(history: ChunkJournal, key: str, arm: str, expected: dict[str, Any]) -> head.Saved:
    state, state_id = policy.load(history.path(key) / f"{arm}.json")
    if (
        state_id != expected["state_id"]
        or state.model.arm != arm
        or state.model.model_id != expected["model_id"]
        or state.value_adam.steps != expected["value_steps"]
        or state.actor_adam.steps != expected["actor_steps"]
        or (state.combat_adam.steps if state.combat_adam else None) != expected["combat_steps"]
    ):
        raise ValueError("Round 57 checkpoint or complete optimizer state differs")
    return state, state_id


@dataclass
class Inherited:
    states: dict[int, dict[str, head.Saved]]
    carried: dict[str, str]
    train_outcomes: dict[str, dict[str, int]]
    excluded_shared: dict[str, Any]


def inspect_history(history: ChunkJournal, report: dict[str, Any]) -> Inherited:
    worlds = head.world_schedule()
    state_refs: dict[tuple[int, int], dict[str, Any]] = {}
    expected_keys = {STOPPED}
    outcomes: dict[str, Counter[str]] = {arm: Counter() for arm in ARMS}
    starts: dict[str, str] = {}
    terminal_fit = {(row["player"], row["round"]): row for row in report["training_rounds"]}
    for p in PLAYERS:
        key = f"initial-p{p}"
        initial = header(history, key, {"parent_state_id": report["starting_states"][str(p)]})
        state_refs[p, 0] = initial["result"]["states"]
        expected_keys.add(key)
    for r in range(1, LAST + 1):
        start = (r - 1) * head.WORLDS_PER_ROUND
        for p in PLAYERS:
            before = state_refs[p, r - 1]
            games: dict[str, list[str]] = {arm: [] for arm in ARMS}
            for i, seed in enumerate(worlds["train"][start : start + head.WORLDS_PER_ROUND], 1):
                for arm in ARMS:
                    task = train_task(r, i, p, arm, seed)
                    expected_keys.add(task["key"])
                    row = load_game(history, task, before[arm])
                    games[arm].append(row["seal_id"])
                    if (
                        starts.setdefault(seed, row["initial_public_input_id"])
                        != row["initial_public_input_id"]
                    ):
                        raise ValueError("Saved training starts differ across the matched worlds")
                    outcomes[arm][row["outcome"]] += 1
                    outcomes[arm]["act1_clears"] += row["completed_acts"] > 0
            key = f"fit-p{p}-r{r:03d}"
            expected_keys.add(key)
            request = {"prior": {arm: before[arm]["state_id"] for arm in ARMS}, "games": games}
            seal = header(history, key, request, full=r == LAST)
            fit = seal["result"]
            if {**fit, "seal_id": seal["report_id"]} != terminal_fit[p, r] or any(
                fit["states"][arm]["value_steps"] - before[arm]["value_steps"]
                != fit["work"]["optimizer_steps_per_arm"]
                for arm in ARMS
            ):
                raise ValueError(f"The sealed matched optimizer lineage differs: {key}")
            state_refs[p, r] = fit["states"]

    for r in (0, 16, 32, 48):
        rows = {}
        for i, seed in enumerate(worlds["progress"], 1):
            for p in PLAYERS:
                for arm in ARMS:
                    key = f"progress-r{r:03d}-{i:03d}-p{p}-{arm}"
                    expected_keys.add(key)
                    task = {
                        "key": key,
                        "round": r,
                        "player": p,
                        "arm": arm,
                        "seed": seed,
                        "partition": "development",
                    }
                    row = load_game(history, task, state_refs[p, r][arm])
                    if (
                        starts.setdefault(seed, row["initial_public_input_id"])
                        != row["initial_public_input_id"]
                    ):
                        raise ValueError("Saved progress starts differ across the matched worlds")
                    rows[seed, p, arm] = row
        ids = {str(p): {arm: state_refs[p, r][arm]["state_id"] for arm in ARMS} for p in PLAYERS}
        if report["progress"][str(r)] != {
            "checkpoint_ids": ids,
            **head.evaluate(worlds["progress"], rows),
        }:
            raise ValueError("Saved progress comparison does not reconstruct")

    states = {
        p: {
            arm: checkpoint(history, f"fit-p{p}-r{LAST:03d}", arm, state_refs[p, LAST][arm])
            for arm in ARMS
        }
        for p in PLAYERS
    }
    carried = {}
    for i in (1, 2):
        for arm in ARMS:
            seed = worlds["train"][LAST * head.WORLDS_PER_ROUND + i - 1]
            task = train_task(LAST + 1, i, 2, arm, seed)
            expected_keys.add(task["key"])
            row = load_game(history, task, state_refs[2, LAST][arm], full=True)
            if (
                starts.setdefault(seed, row["initial_public_input_id"])
                != row["initial_public_input_id"]
            ):
                raise ValueError("Saved round 58 pair starts differ")
            carried[task["key"]] = row["seal_id"]
    failed = train_task(LAST + 1, 3, 2, "split", EXCLUDED)
    shared = train_task(LAST + 1, 3, 2, "shared", EXCLUDED)
    excluded = load_game(history, shared, state_refs[2, LAST]["shared"], full=True)
    expected_keys.add(shared["key"])
    if (
        {p.name for p in (history.workspace / "chunks").iterdir()} != expected_keys
        or json.loads((history.path(STOPPED) / "active.json").read_text())["request"]
        != game_request(failed, state_refs[2, LAST]["split"])
        or (history.path(STOPPED) / "done.json").exists()
    ):
        raise ValueError("Original sealed or unstarted study cells differ")
    return Inherited(
        states, carried, {arm: dict(counts) for arm, counts in outcomes.items()}, excluded
    )


@dataclass
class Recovery:
    original: head.Study
    cfg: dict[str, Any]
    history: ChunkJournal
    report: dict[str, Any]

    @property
    def root(self) -> Path:
        return self.original.root

    @contextmanager
    def source_lock(self) -> Iterator[None]:
        with (self.history.workspace / "session.lock").open("rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            yield

    def unchanged(self, profile: dict[str, Any]) -> None:
        self.original.unchanged(profile)
        if json.loads((self.root / RECIPE).read_text()) != self.cfg:
            raise ValueError("Crystal Sphere continuation recipe changed")
        check_sources(self.root, self.cfg["implementation"])
        for key in ("parent_recipe", "parent_report", "parent_resources"):
            verified(self.root, self.cfg[key])
        if chunk_evidence_id(self.history.path(STOPPED)) != self.cfg["stopped_evidence_id"]:
            raise ValueError("The interrupted Crystal Sphere evidence changed")


def load(root: Path) -> Recovery:
    cfg = json.loads((root / RECIPE).read_text())
    original = head.load(root)
    history = original.store(False)
    proof = head.require_control(original)
    report_path = verified(root, cfg["parent_report"])
    report = identified(report_path)
    resource_path = verified(root, cfg["parent_resources"])
    resources = identified(resource_path)
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["implementation"] != implementation(root)
        or cfg["limits"] != LIMITS
        or cfg["replacement"] != {"original": EXCLUDED, "seed": REPLACEMENT, "seed_id": 1025}
        or cfg["control_seeds"] != list(CONTROL_SEEDS)
        or cfg["prefix_seed"] != PREFIX_SEED
        or len({cfg["workspace"], cfg["control_workspace"], original.cfg["workspace"]}) != 3
        or verified(root, cfg["parent_recipe"]) != root / head.RECIPE
        or report_path != history.workspace / f"session-{report['attempt']}.json"
        or resource_path != history.workspace / f"resources-{report['attempt']}.json"
        or report["status"] != "stopped_preserving_evidence"
        or report["config_id"] != history.config_id
        or report["control_id"] != proof
        or report["starting_states"] != original.cfg["starting_states"]
        or report["stop"] != {"unit": STOPPED, "error": ERROR}
        or report["verified_games"] != 3909
        or len(report["training_rounds"]) != 114
        or set(report["progress"]) != {"0", "16", "32", "48"}
        or report["holdout"] is not None
        or resources["status"] != "failed"
        or resources["exit_code"] != 2
        or resources["cap"] is not None
        or resources["artifacts"]["roots"] != [str(history.workspace)]
        or json.loads((history.workspace / "config-at-launch.json").read_text()) != history.recipe
        or chunk_evidence_id(history.path(STOPPED)) != cfg["stopped_evidence_id"]
        or head.world_schedule()["train"][914] != EXCLUDED
        or any(REPLACEMENT in seeds for seeds in head.world_schedule().values())
    ):
        raise ValueError("Require the exact original round 57 and stopped Crystal Sphere evidence")
    return Recovery(original, cfg, history, report)


class ContinuationJournal(ChunkJournal):
    """Read the two exact matched pairs from the old workspace."""

    def __init__(self, recovery: Recovery, carried: dict[str, str]) -> None:
        super().__init__(recovery.root, recovery.cfg)
        self.history = recovery.history
        self.carried = carried

    def path(self, key: str) -> Path:
        return self.history.path(key) if key in self.carried else super().path(key)

    def completed(self, key: str, request: dict[str, Any]) -> dict[str, Any] | None:
        if key in self.carried:
            seal = header(self.history, key, request, full=True)
            if seal["report_id"] != self.carried[key]:
                raise ValueError("A carried round 58 game changed")
            return seal
        return super().completed(key, request)

    def begin(self, key: str, request: dict[str, Any]) -> Path:
        if key in self.carried:
            raise ValueError("Previously sealed game is read-only")
        return super().begin(key, request)

    def commit(
        self,
        key: str,
        request: dict[str, Any],
        result: dict[str, Any],
        extra_sources: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if key in self.carried:
            raise ValueError("Previously sealed game is read-only")
        return super().commit(key, request, result, extra_sources)


class Continuation(head.Session):
    def __init__(self, recovery: Recovery, inherited: Inherited, deadline: float) -> None:
        super().__init__(recovery.original, control=False, deadline=deadline)
        self.store = ContinuationJournal(recovery, inherited.carried)
        self.training = list(recovery.report["training_rounds"])
        self.progress = dict(recovery.report["progress"])
        self.games_seen = recovery.report["verified_games"] - 5

    def game(self, task: dict[str, Any], saved: head.Saved) -> dict[str, Any]:
        if task["seed"] == REPLACEMENT:
            task = {**task, "seed_id": 1025}
        with patch.object(policy, "SelectorWorker", grid.GridWorker):
            return super().game(task, saved)


def control_store(recovery: Recovery) -> ChunkJournal:
    return ChunkJournal(
        recovery.root, {**recovery.cfg, "workspace": recovery.cfg["control_workspace"]}
    )


def verify_grid_scoring(
    recovery: Recovery, inherited: Inherited, seed: str, public: dict[str, Any]
) -> dict[str, int]:
    score = recovery.original.source.study.base.ctx["score"]
    if public["context"]["interaction"]["kind"] != "event_option":
        raise ValueError("A Crystal Sphere grid belongs to the public event owner")
    scored = {}
    for p in PLAYERS:
        for arm in ARMS:
            chooser = policy.HeadChooser(inherited.states[p][arm][0].model, score, seed)
            choice = chooser(public)
            if (
                chooser.last is None
                or len(chooser.last[0]) != 242
                or choice["scoring_head"] != ("shared" if arm == "shared" else "strategy")
                or choice["combat_owned"]
                or choice["navigation_only"]
                or choice["behavior"] != "sampled_softmax"
                or choice["effective_input_id"] != choice["public_input_id"]
                or not 0 <= choice["action_index"] < 242
            ):
                raise ValueError("A frozen head must score and sample from the full native grid")
            scored[f"p{p}-{arm}"] = len(chooser.last[0])
    return scored


def short_check(recovery: Recovery, inherited: Inherited) -> str:
    store = control_store(recovery)
    profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
    deadline = time.monotonic() + 240
    ctx = {**recovery.original.source.study.base.ctx, "execution_id": store.config_id}
    with store.lock():
        recovery.unchanged(profile)
        report_path = store.workspace / "report.json"
        if report_path.is_file():
            return require_control(recovery, inherited)
        if _running_games():
            raise ValueError("Close STS2 and wait for other native workers")
        saved = grid.saved_grid(ctx, recovery.history.path(STOPPED) / "worker")
        seals = {}
        for payment, seed in enumerate(CONTROL_SEEDS):
            key = f"payment-{payment}"
            spec = {"payment": payment, "seed": seed}
            seal = store.completed(key, spec)
            if seal is None:
                result = grid.native_grid(
                    ctx,
                    store.begin(key, spec),
                    seed,
                    payment,
                    deadline,
                    partial(verify_grid_scoring, recovery, inherited, seed),
                )
                seal = store.commit(key, spec, result)
            seals[key] = seal["report_id"]
        session = head.Session(recovery.original, control=True, deadline=deadline)
        session.store = store
        with patch.object(policy, "SelectorWorker", grid.GridWorker):
            prefixes = session.assessment("prefix", LAST, [PREFIX_SEED], inherited.states)
        recovery.unchanged(profile)
        proof = write(
            report_path,
            {
                "status": CONTROL,
                "config_id": store.config_id,
                "parent_report_id": recovery.report["report_id"],
                "saved_projection": saved,
                "sealed_controls": seals,
                "normal_start_prefixes": prefixes,
                "carried_games": inherited.carried,
                "frozen_checks": recovery.original.source.study.frozen_checks,
                "optimizer_updates": 0,
            },
        )
    return str(proof["report_id"])


def require_control(recovery: Recovery, inherited: Inherited) -> str:
    store = control_store(recovery)
    proof = identified(store.workspace / "report.json")
    if (
        proof["status"] != CONTROL
        or proof["config_id"] != store.config_id
        or proof["parent_report_id"] != recovery.report["report_id"]
        or proof["optimizer_updates"] != 0
        or proof["saved_projection"]["complete_grid_actions"] != 242
        or proof["frozen_checks"] != recovery.original.source.study.frozen_checks
        or set(proof["sealed_controls"]) != {"payment-0", "payment-1"}
        or proof["carried_games"] != inherited.carried
    ):
        raise ValueError("Require the exact saved projection and live Crystal Sphere checks")
    for payment, seed in enumerate(CONTROL_SEEDS):
        key = f"payment-{payment}"
        seal = store.completed(key, {"payment": payment, "seed": seed})
        if (
            seal is None
            or seal["report_id"] != proof["sealed_controls"][key]
            or seal["result"]["scored_choices_by_checkpoint"]
            != {f"p{p}-{arm}": 242 for p in PLAYERS for arm in ARMS}
        ):
            raise ValueError("Crystal Sphere diagnostic seal differs")
    starts = set()
    for p in PLAYERS:
        for arm in ARMS:
            prefix = proof["normal_start_prefixes"][f"p{p}-{arm}"]
            state, state_id = inherited.states[p][arm]
            task: dict[str, Any] = {
                "key": f"prefix-r{LAST:03d}-001-p{p}-{arm}",
                "round": LAST,
                "player": p,
                "arm": arm,
                "seed": PREFIX_SEED,
                "partition": "reload_control",
            }
            seal = store.completed(
                task["key"],
                game_request(task, {"state_id": state_id, "model_id": state.model.model_id}),
            )
            if (
                seal is None
                or {**seal["result"], "seal_id": seal["report_id"]} != prefix
                or (prefix["outcome"], prefix["native_decisions"])
                != ("capped", head.CONTROL_PREFIX_CHOICES)
            ):
                raise ValueError("The frozen checkpoint's native prefix seal differs")
            starts.add(prefix["initial_public_input_id"])
    if len(starts) != 1:
        raise ValueError("The four normal-start prefixes must begin on the same public menu")
    return str(proof["report_id"])


def execute(
    recovery: Recovery, inherited: Inherited, control_id: str, until: int, attempt: int
) -> dict[str, Any]:
    session = Continuation(recovery, inherited, time.monotonic() + LIMITS["wall_seconds"] - 45)
    worlds = head.world_schedule()
    worlds["train"][914] = REPLACEMENT
    final = session.store.workspace / "report.json"
    with session.store.lock():
        if final.is_file():
            result = identified(final)
            if result["config_id"] != session.store.config_id or result["control_id"] != control_id:
                raise ValueError("Completed continuation belongs to another recipe")
            return result
        status, stop = "paused", None
        try:
            recovery.unchanged(session.profile)
            states = inherited.states.copy()
            for r in range(LAST + 1, until + 1):
                first = (r - 1) * head.WORLDS_PER_ROUND
                session.train_round(
                    r, worlds["train"][first : first + head.WORLDS_PER_ROUND], states
                )
                recovery.unchanged(session.profile)
            if until == head.ROUNDS:
                session.progress[str(until)] = session.assessment(
                    "progress", until, worlds["progress"], states
                )
                session.holdout = session.assessment("holdout", until, worlds["holdout"], states)
                status = head.COMPLETE
            else:
                stop = {"reason": "requested_round_boundary", "round": until}
            recovery.unchanged(session.profile)
        except head.CleanPause as exc:
            recovery.unchanged(session.profile)
            stop = {"reason": str(exc), "next_unit": session.active}
        except ERRORS as exc:
            status = "stopped_preserving_evidence"
            stop = {"unit": session.active, "error": f"{type(exc).__name__}: {exc}"}
        body = {
            "schema_version": SCHEMA,
            "config_id": session.store.config_id,
            "status": status,
            "control_id": control_id,
            "parent_report_id": recovery.report["report_id"],
            "parent_verified_games": recovery.report["verified_games"],
            "carried_games": inherited.carried,
            "verified_games": session.games_seen,
            "replacement": recovery.cfg["replacement"],
            "original_excluded_cells": {
                "p2-shared": inherited.excluded_shared["outcome"],
                "p2-split": "failed",
                "p3-shared": "unattempted",
                "p3-split": "unattempted",
            },
            "training_rounds": session.training,
            "progress": session.progress,
            "holdout": session.holdout,
            "stop": stop,
            "frozen_checks": (
                None
                if status == "stopped_preserving_evidence"
                else recovery.original.source.study.frozen_checks
            ),
            **SCOPE,
        }
        target = (
            final
            if status == head.COMPLETE
            else session.store.workspace / f"session-{attempt}.json"
        )
        return write(target, body)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--execute", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--until-round", type=int, default=head.ROUNDS)
    args = parser.parse_args()
    if not LAST < args.until_round <= head.ROUNDS:
        parser.error(f"--until-round must be between {LAST + 1} and {head.ROUNDS}")
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the launcher with the frozen numerical thread settings")
        recovery = load(Path.cwd())
        with recovery.source_lock():
            inherited = inspect_history(recovery.history, recovery.report)
            if args.check:
                proof = short_check(recovery, inherited)
                print(
                    json.dumps(
                        {
                            "status": CONTROL,
                            "report_id": proof,
                            "prior_training_outcomes": inherited.train_outcomes,
                        }
                    )
                )
                return 0
            control_id = require_control(recovery, inherited)
            if args.preflight:
                profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
                recovery.unchanged(profile)
                print(
                    json.dumps(
                        {
                            "status": "scoring_head_suffix_ready",
                            "completed_rounds": LAST,
                            "carried_round58_games": len(inherited.carried),
                            "new_training_games": 444,
                            "new_progress_games": 64,
                            "new_holdout_games": 512,
                            "replacement_world": REPLACEMENT,
                            "control_id": control_id,
                            "frozen_checks": recovery.original.source.study.frozen_checks,
                        }
                    )
                )
                return 0
            if args.execute is not None:
                result = execute(recovery, inherited, control_id, args.until_round, args.execute)
                print(json.dumps({k: v for k, v in result.items() if k != "training_rounds"}))
                return 0 if result["status"] in {head.COMPLETE, "paused"} else 2
            if _running_games():
                raise ValueError("Close STS2 and wait for other native workers")
            store = ChunkJournal(recovery.root, recovery.cfg)
            attempt = time.time_ns()
            print("Continue from round 57 with the repaired Crystal Sphere adapter.", flush=True)
            tracked = run_tracked_command(
                command=[
                    "uv",
                    "run",
                    "--no-sync",
                    "python",
                    "-m",
                    MODULE,
                    "--execute",
                    str(attempt),
                    "--until-round",
                    str(args.until_round),
                ],
                experiment_kind=ExperimentKind.TRAINING,
                working_directory=recovery.root,
                report_path=store.workspace / f"resources-{attempt}.json",
                artifact_roots=[store.workspace],
                limits=ResourceLimits(**LIMITS),
                poll_interval_seconds=8,
            )
            print(json.dumps(tracked.report))
            return (
                tracked.exit_code
                if tracked.exit_code is not None and tracked.report["cap"] is None
                else 2
            )
    except ERRORS as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc), **SCOPE}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
