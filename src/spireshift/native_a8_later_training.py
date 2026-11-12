"""Train shared heads on verified later acts and evaluate on fresh normal starts."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_head_grid_resume as prior
from spireshift import native_a8_head_policy as policy
from spireshift import native_a8_head_study as head
from spireshift import native_a8_later_start as prepared
from spireshift import native_a8_later_training_plan as plan
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_archive_fit_session import ERRORS
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_crystal_grid import GridWorker
from spireshift.native_a8_head_holdout_resume import training_lineage
from spireshift.native_a8_own_training import SCOPE
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_paired_report import summarize
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_a8_later_training"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-shared-later-act-v1.json"
WRAPPER = "scripts/train-a8-shared-later-acts-v1.sh"
SCHEMA = "native-a8-shared-later-act-training-v1"
CONTROL = "later_act_collect_fit_reload_verified"
COMPLETE = "later_act_training_and_normal_start_evaluation_complete"
LIMITS = {**head.LIMITS, "wall_seconds": 21_600, "storage_bytes": 24_000_000_000}
SHORT_SECONDS = 260
ARMS = ("original", "fitted")


def implementation(root: Path) -> dict[str, str]:
    files = {
        WRAPPER,
        "scripts/engine-win-curriculum-save-v1.mjs",
        "src/spireshift/native_win4_worker.py",
        "src/spireshift/native_a8_head_holdout_resume.py",
        *(
            f"src/spireshift/native_a8_{part}.py"
            for part in ("later_start", "later_training", "later_training_plan")
        ),
        *prepared.setup_helpers(root),
        *(str(path.relative_to(root)) for path in (root / prepared.PROJECT).glob("*.*")),
    }
    return {name: _sha_file(root / name) for name in sorted(files)}


@dataclass
class Study:
    recovery: prior.Recovery
    cfg: dict[str, Any]
    ctx: dict[str, Any]
    worlds: dict[str, Any]
    parents: dict[int, head.Saved]
    checkpoint_sources: dict[str, str]
    bank: dict[str, Any]

    def store(self, control: bool) -> ChunkJournal:
        recipe = {**self.cfg, "workspace": self.cfg["control_workspace"]} if control else self.cfg
        return ChunkJournal(self.recovery.root, recipe)

    def unchanged(self, profile: dict[str, Any]) -> None:
        root = self.recovery.root
        self.recovery.unchanged(profile)
        if json.loads((root / RECIPE).read_text()) != self.cfg:
            raise ValueError("The later-act experiment recipe changed")
        check_sources(root, {**self.cfg["implementation"], **self.checkpoint_sources})
        verified(root, self.cfg["parent_report"])
        verified(root, self.cfg["load_adapter"])


def admit(
    root: Path, recovery: prior.Recovery, history: ChunkJournal, cfg: dict[str, Any]
) -> Study:
    original = recovery.original
    base = original.source.study.base
    inherited = prior.inspect_history(recovery.history, recovery.report)
    control_id = prior.require_control(recovery, inherited)
    report_path = verified(root, cfg["parent_report"])
    report = identified(report_path)
    if (
        report_path.parent != history.workspace
        or report["config_id"] != history.config_id
        or report["control_id"] != control_id
        or report["parent_report_id"] != recovery.report["report_id"]
        or report["replacement"] != recovery.cfg["replacement"]
        or report["carried_games"] != inherited.carried
        or json.loads((history.workspace / "config-at-launch.json").read_text()) != history.recipe
    ):
        raise ValueError("Require the frozen completed round-64 training lineage")
    final, _, sources = training_lineage(recovery, inherited, history, report)
    verifier = head.Session(original, control=False, deadline=0)
    verifier.store = history
    parents = {
        p: verifier.checkpoint(f"fit-p{p}-r{head.ROUNDS:03d}", "shared", final[p]["shared"])
        for p in PLAYERS
    }
    worlds = plan.schedule(recovery, cfg["control_revision"])
    adapter = identified(verified(root, cfg["load_adapter"]))
    if (
        adapter["status"] != "prepared_start_adapter_built"
        or len(adapter["builds"]) != 2
        or adapter["builds"][0]["sha256"] != adapter["builds"][1]["sha256"]
        or cfg["starting_states"] != {str(p): parents[p][1] for p in PLAYERS}
        or cfg["environment_id"] != base.ctx["environment_id"]
        or cfg["objective"] != original.cfg["objective"]
        or cfg["training_score_id"] != base.ctx["score"].spec_id
        or cfg["schedule_id"] != manifest_identifier(worlds)
    ):
        raise ValueError("The plan, frozen shared heads or saved-start adapter differ")
    check_sources(root, adapter["sources"])
    paths = [verified(root, ref) for ref in adapter["builds"]]
    sources.update(
        {
            str(path.relative_to(root)): ref["sha256"]
            for path, ref in zip(paths, adapter["builds"], strict=True)
        }
    )
    ctx = {
        **base.ctx,
        "prepared_start_adapter": {
            "path": str(paths[0]),
            "sha256": adapter["builds"][0]["sha256"],
        },
    }
    study = Study(recovery, cfg, ctx, worlds, parents, sources, base.bank["entries"])
    protected = {
        history.workspace,
        recovery.history.workspace,
        prior.control_store(recovery).workspace,
    }
    if any(
        study.store(control).workspace.is_relative_to(path)
        for control in (False, True)
        for path in protected
    ):
        raise ValueError("Use separate private workspaces for the new experiment")
    return study


class Session(head.Session):
    def __init__(self, study: Study, control: bool, deadline: float) -> None:
        super().__init__(study.recovery.original, control=control, deadline=deadline)
        self.later = study
        self.store = study.store(control)
        self.ctx = {
            **study.ctx,
            "execution_id": self.store.config_id,
            "config": {"plan": self.study.cfg["game_limits"]},
        }
        self.evaluation_rows: dict[tuple[str, int, str], dict[str, Any]] = {}
        self.active_evaluation: dict[str, Any] | None = None
        self.starts: dict[str, str] = {}

    def copy_parent(self, p: int) -> head.Saved:
        parent, state_id = self.later.parents[p]
        key = f"copy-p{p}"
        seal = self.unit(
            key,
            {"parent_state_id": state_id},
            5,
            lambda target: {"states": self.persist(target, {"shared": parent})},
        )
        state = self.checkpoint(key, "shared", seal["result"]["states"]["shared"])
        if state != (parent, state_id):
            raise ValueError("A training copy must start with the exact shared weights and Adam")
        return state

    def materialize(self, world: dict[str, Any]) -> dict[str, Any]:
        if world["archived"] is not None:
            source = self.later.bank[world["archived"]]
            case = identified(self.later.recovery.root / source["source_chunk"] / "start.json")[
                "scenario"
            ]
        else:
            source, case = None, world["case"]
        seal = self.unit(
            f"{world['key']}-start",
            {"world": world},
            35 if self.control else 100,
            lambda target: prepared.materialize(self.ctx, case, target, self.deadline, source),
        )
        start: dict[str, Any] = seal["result"]
        if (
            start["scenario"] != case
            or start["kind"] != prepared.KIND
            or start["evaluation_eligible"] is not False
            or start["seed"] not in case["seed_pool"]
            or (source is not None and start["seed"] != world["seed"])
        ):
            raise ValueError("The sealed save belongs to a different training world")
        return start

    def game(self, task: dict[str, Any], saved: head.Saved) -> dict[str, Any]:
        if task["start_act"] != 1:
            raise ValueError("Only normal starts enter the normal-game path")
        with patch.object(policy, "SelectorWorker", GridWorker):
            return super().game(task, saved)

    def play_saved(
        self, task: dict[str, Any], start: dict[str, Any], saved: head.Saved
    ) -> dict[str, Any]:
        state, state_id = saved
        seal = self.unit(
            task["key"],
            {
                "task": task,
                "setup_id": start["report_id"],
                "behavior_state_id": state_id,
                "model_id": state.model.model_id,
            },
            35 if self.control else self.study.cfg["game_limits"]["episode_wall_seconds"] + 30,
            lambda target: prepared.play(self.ctx, task, start, target, state, self.deadline),
        )
        row = seal["result"]
        if (row["task"], row["setup_id"], row["model_id"]) != (
            task,
            start["report_id"],
            state.model.model_id,
        ):
            raise ValueError("A sealed prepared game has different input provenance")
        self.games_seen += 1
        return {**row, "seal_id": seal["report_id"]}

    def matched_start(self, task: dict[str, Any], row: dict[str, Any]) -> None:
        public_id = row["initial_public_input_id"]
        if self.starts.setdefault(task["seed"], public_id) != public_id:
            raise ValueError("A matched later-act study world has a different public start")

    def train(self, players: tuple[int, ...]) -> dict[int, head.Saved]:
        states = {p: self.copy_parent(p) for p in players}
        rounds = [self.later.worlds["controls"]] if self.control else self.later.worlds["training"]
        for index, worlds in enumerate(rounds, 1):
            starts = {w["key"]: self.materialize(w) for w in worlds if w["act"] > 1}
            for p in players:
                games = []
                for world in worlds:
                    start = starts.get(world["key"])
                    seed = world["seed"] if start is None else start["seed"]
                    task = plan.training_task(world, p, index, seed, self.control)
                    row = (
                        self.game(task, states[p])
                        if start is None
                        else self.play_saved(task, start, states[p])
                    )
                    self.matched_start(task, row)
                    games.append((self.store.path(task["key"]), row))
                states[p] = self.fit_round(p, index, games, states[p])
            self.later.unchanged(self.profile)
        return states

    def fit_round(
        self, p: int, index: int, games: list[tuple[Path, dict[str, Any]]], current: head.Saved
    ) -> head.Saved:
        key = f"fit-p{p}-r{index:02d}"

        def collect(target: Path) -> dict[str, Any]:
            fitted, work = plan.fit(current[0], games, self.ctx["score"], self.study.cfg, p, index)
            return {"states": self.persist(target, {"shared": fitted}), "work": work}

        seal = self.unit(
            key,
            {"parent_state_id": current[1], "games": [row["seal_id"] for _, row in games]},
            15 if self.control else head.FIT_RESERVE,
            collect,
        )
        result = seal["result"]
        saved = self.checkpoint(key, "shared", result["states"]["shared"])
        steps = result["work"]["optimizer_steps"]
        if (
            saved[0].actor_adam.steps - current[0].actor_adam.steps != steps
            or saved[0].value_adam.steps - current[0].value_adam.steps != steps
            or (self.control and (steps < 1 or saved[0].model.actor == current[0].model.actor))
        ):
            raise ValueError("The sealed shared-head optimizer transition differs")
        self.training.append({"round": index, "player": p, "seal_id": seal["report_id"], **result})
        print(f"Round {index}, player {p}: {steps} shared-head updates", flush=True)
        return saved

    def evaluate(self, states: dict[int, head.Saved]) -> dict[str, Any]:
        if self.control:
            world = self.later.worlds["reload"]
            rows = {}
            for arm, state in zip(ARMS, (self.later.parents[2], states[2]), strict=True):
                task = evaluation_task(world, 2, arm, "reload_control")
                row = self.game(task, state)
                self.matched_start(task, row)
                if (row["outcome"], row["native_decisions"]) != (
                    "capped",
                    head.CONTROL_PREFIX_CHOICES,
                ):
                    raise ValueError("The reloaded shared head needs an exact fresh normal prefix")
                rows[arm] = row
            return rows
        for index, world in enumerate(self.later.worlds["development"], 1):
            for p in PLAYERS:
                for arm in ARMS if (index + p) % 2 else ARMS[::-1]:
                    task = evaluation_task(world, p, arm, "development")
                    self.active_evaluation = task
                    state = self.later.parents[p] if arm == "original" else states[p]
                    row = self.game(task, state)
                    self.matched_start(task, row)
                    self.evaluation_rows[world["seed"], p, arm] = row
            if index % 8 == 0:
                print(
                    f"Fresh normal-start A8 evaluation: {index}/{plan.EVALUATION_WORLDS} worlds",
                    flush=True,
                )
        return self.summary()

    def summary(self) -> dict[str, Any]:
        worlds = [w["seed"] for w in self.later.worlds["development"]]
        report = summarize(worlds, self.evaluation_rows)
        for p in PLAYERS:
            for arm in ARMS:
                rows = [
                    r
                    for (_, player, name), r in self.evaluation_rows.items()
                    if (player, name) == (p, arm) and r["outcome"] in plan.TERMINAL
                ]
                report["by_initializer"][str(p)]["arms"][arm].update(
                    act1_clears=sum(r["completed_acts"] >= 1 for r in rows),
                    act2_clears=sum(r["completed_acts"] >= 2 for r in rows),
                )
        return report


def evaluation_task(world: dict[str, Any], player: int, arm: str, partition: str) -> dict[str, Any]:
    if world["act"] != 1 or world["archived"] is not None:
        raise ValueError("A fresh normal-start evaluation cannot use a prepared world")
    return {
        "key": f"{world['key']}-p{player}-{arm}",
        "start_act": 1,
        "arm": "shared",
        "comparison_arm": arm,
        "player": player,
        "round": plan.ROUNDS,
        "seed": world["seed"],
        "partition": partition,
    }


def require_control(study: Study) -> str:
    store = study.store(True)
    proof = identified(store.workspace / "report.json")
    worlds = study.worlds["controls"]
    reload = study.worlds["reload"]["key"]
    expected_seals = {
        "copy-p2",
        "fit-p2-r01",
        "saved-start-grid",
        *(f"{world['key']}-p2" for world in worlds),
        *(f"{world['key']}-start" for world in worlds if world["act"] > 1),
        *(f"{reload}-p2-{arm}" for arm in ARMS),
    }
    if (
        proof["status"] != CONTROL
        or proof["config_id"] != store.config_id
        or proof["disposable_optimizer_updates"] < 1
        or proof["grid"]["native_grid_bindings"] != 242
        or set(proof["prefixes"]) != set(ARMS)
        or set(proof["seals"]) != expected_seals
    ):
        raise ValueError("Require sealed later-act collection, fit, reload and grid controls")
    for key, expected in proof["seals"].items():
        request = json.loads((store.path(key) / "active.json").read_text())["request"]
        seal = store.completed(key, request)
        if seal is None or seal["report_id"] != expected:
            raise ValueError(f"Later-act short control changed: {key}")
    return str(proof["report_id"])


def check(study: Study, deadline: float) -> str:
    session = Session(study, True, deadline)
    with session.store.lock():
        target = session.store.workspace / "report.json"
        if target.exists():
            return require_control(study)
        states = session.train((2,))
        prefixes = session.evaluate(states)
        world = next(
            w for w in study.worlds["controls"] if w.get("case", {}).get("entry") == "preboss"
        )
        start = session.materialize(world)
        seal = session.unit(
            "saved-start-grid",
            {"setup_id": start["report_id"]},
            25,
            lambda target: prepared.crystal_control(session.ctx, start, target, deadline),
        )
        study.unchanged(session.profile)
        write(
            target,
            {
                "schema_version": SCHEMA,
                "status": CONTROL,
                "config_id": session.store.config_id,
                "grid": seal["result"],
                "prefixes": prefixes,
                "seals": session.seals,
                "training": session.training,
                "disposable_optimizer_updates": session.training[0]["work"]["optimizer_steps"],
                "short_session_seconds": time.monotonic() - (deadline - SHORT_SECONDS),
                "frozen_checks": study.recovery.original.source.study.frozen_checks,
                **SCOPE,
            },
        )
        return require_control(study)


def run(study: Study, control_id: str, attempt: int, deadline: float) -> dict[str, Any]:
    session = Session(study, False, deadline)
    final = session.store.workspace / "report.json"
    with session.store.lock():
        if final.exists():
            result = identified(final)
            if (result["config_id"], result["control_id"], result["status"]) != (
                session.store.config_id,
                control_id,
                COMPLETE,
            ):
                raise ValueError("The saved later-act experiment belongs to a different plan")
            return result
        status, stop = COMPLETE, None
        finalists: dict[str, str] = {}
        try:
            states = session.train(PLAYERS)
            finalists = {str(p): state_id for p, (_, state_id) in states.items()}
            session.evaluate(states)
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
            task = session.active_evaluation
            if task is not None and session.store.path(task["key"]).exists():
                session.evaluation_rows[task["seed"], task["player"], task["comparison_arm"]] = {
                    "outcome": "failed"
                }
        study.unchanged(session.profile)
        target = (
            final if status == COMPLETE else session.store.workspace / f"session-{attempt}.json"
        )
        return write(
            target,
            {
                "schema_version": SCHEMA,
                "config_id": session.store.config_id,
                "status": status,
                "control_id": control_id,
                "starting_states": study.cfg["starting_states"],
                "final_checkpoint_ids": finalists,
                "verified_games": session.games_seen,
                "optimizer_updates": sum(r["work"]["optimizer_steps"] for r in session.training),
                "training": session.training,
                "normal_start_evaluation": session.summary(),
                "stop": stop,
                "frozen_checks": study.recovery.original.source.study.frozen_checks,
                **SCOPE,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the launcher with the pinned numerical thread settings")
        cfg = json.loads((root / RECIPE).read_text())
        if (
            cfg["schema_version"] != SCHEMA
            or cfg["limits"] != LIMITS
            or cfg["workspace"] == cfg["control_workspace"]
            or cfg["implementation"] != implementation(root)
        ):
            raise ValueError("Require the exact later-act training recipe and sources")
        if args.check or args.preflight or args.execute is not None:
            recovery = prior.load(root)
            history = ChunkJournal(root, recovery.cfg)
            with recovery.source_lock(), (history.workspace / "session.lock").open("rb") as lock:
                fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
                study = admit(root, recovery, history, cfg)
                study.unchanged(_shared_snapshot(Path.home() / SHARED_PROFILE))
                if args.check:
                    if _running_games():
                        raise ValueError("Close STS2 and wait for any other native worker")
                    proof = check(study, started + SHORT_SECONDS)
                    print(json.dumps({"status": CONTROL, "report_id": proof}))
                    return 0
                control_id = require_control(study)
                if args.preflight:
                    print(
                        json.dumps(
                            {
                                "status": "shared_later_act_training_ready",
                                "control_id": control_id,
                                "training_rounds_per_initializer": plan.ROUNDS,
                                "training_games": sum(map(len, study.worlds["training"]))
                                * len(PLAYERS),
                                "normal_start_evaluation_games": plan.EVALUATION_WORLDS
                                * len(PLAYERS)
                                * 2,
                                "frozen_checks": study.recovery.original.source.study.frozen_checks,
                            }
                        )
                    )
                    return 0
                if _running_games():
                    raise ValueError("Close STS2 and wait for any other native worker")
                result = run(study, control_id, args.execute, started + LIMITS["wall_seconds"] - 45)
                print(
                    json.dumps({key: value for key, value in result.items() if key != "training"})
                )
                return 0 if result["status"] in {COMPLETE, "paused"} else 2
        attempt = time.time_ns()
        store = ChunkJournal(root, cfg)
        print(
            "Train shared heads from normal starts and verified Act 2 and Act 3 saves.", flush=True
        )
        tracked = run_tracked_command(
            command=["uv", "run", "--no-sync", "python", "-m", MODULE, "--execute", str(attempt)],
            experiment_kind=ExperimentKind.TRAINING,
            working_directory=root,
            report_path=store.workspace / f"resources-{attempt}.json",
            artifact_roots=[store.workspace],
            limits=ResourceLimits(**LIMITS),
            poll_interval_seconds=8,
        )
        print(json.dumps(tracked.report))
        return 0 if tracked.exit_code == 0 and tracked.report["cap"] is None else 2
    except ERRORS as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc), **SCOPE}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
