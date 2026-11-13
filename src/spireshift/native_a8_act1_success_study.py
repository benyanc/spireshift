"""Fit copies on verified Act 1 clears and compare from fresh A8 starts."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

from spireshift import native_a8_act1_success_bank as bank
from spireshift import native_a8_head_grid_resume as grid
from spireshift import native_a8_head_study as heads
from spireshift import native_a8_later_merchant_resume as later
from spireshift import native_a8_later_training as original
from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_ppo_math import Adam
from spireshift.native_a8_archive_batch import known_seeds
from spireshift.native_a8_archive_fit_inputs import encode_answer
from spireshift.native_a8_archive_fit_session import ERRORS
from spireshift.native_a8_bank_fit import (
    ACTOR_RATE,
    GRADIENT_CLIP,
    TEMPERATURE,
    Worlds,
    batch,
    metrics,
    world_schedule,
)
from spireshift.native_a8_bank_fit import update as imitation_update
from spireshift.native_a8_head_study import CleanPause, Saved
from spireshift.native_a8_own_training import SCOPE
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_flow_verification_v12 import records
from spireshift.native_policy_updates import SETTINGS
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command
from spireshift.training_objective import TrainingScoreSpec

MODULE = "spireshift.native_a8_act1_success_study"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-act1-success-replay-v1.json"
WRAPPER = "scripts/train-a8-act1-success-replay-v1.sh"
SCHEMA = "native-a8-act1-success-replay-v1"
COMPLETE = "act1_success_replay_development_complete"
CONTROL = "act1_success_replay_control_verified"
LIMITS = {**original.LIMITS, "wall_seconds": 3600, "storage_bytes": 4_000_000_000}
CONTROL_SECONDS = 255
UPDATES = 256
CONTROL_UPDATES = 2


def implementation(root: Path) -> dict[str, str]:
    names = (
        WRAPPER,
        "src/spireshift/native_a8_act1_success_bank.py",
        "src/spireshift/native_a8_act1_success_study.py",
        "src/spireshift/native_a8_archive_fit_inputs.py",
        "src/spireshift/native_a8_bank_fit.py",
    )
    return {name: _sha_file(root / name) for name in names}


def declaration() -> dict[str, Any]:
    prefix = "SP1RESH1FTA8AS1"
    return {
        "development": [f"{prefix}E{i:03}" for i in range(1, 33)],
        "controls": [f"{prefix}C001"],
        "updates_per_copy": UPDATES,
        "actor_learning_rate": ACTOR_RATE,
        "gradient_clip": GRADIENT_CLIP,
        "temperature": TEMPERATURE,
    }


def load_bank(study: later.Study, completed: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    root = study.recovery.root
    path = verified(root, cfg["bank"])
    proof = identified(path)
    worlds = proof["worlds"]
    if (
        proof["schema_version"] != "native-a8-act1-success-replay-bank-v1"
        or proof["status"] != bank.STATUS
        or proof["source_result_id"] != completed["report_id"]
        or identified(verified(root, cfg["comparison"])) != completed
        or proof["starting_states"] != {str(p): study.parents[p][1] for p in PLAYERS}
        or proof["frozen_checks"] != completed["frozen_checks"]
        or proof["partitions"] != bank.partitions(worlds)
        or proof["counts_by_boss"] != dict(Counter(w["act1_boss"] for w in worlds.values()))
        or proof["optimizer_updates"] != 0
        or proof["game_launches"] != 0
    ):
        raise ValueError("The saved normal-start Act 1 bank or its ownership differs")
    for seed, row in worlds.items():
        label = verified(root, row["labels"])
        seal = identified(verified(root, row["source"]))
        if (
            seed != row["seed"]
            or label.parent != path.parent
            or seal["report_id"] != row["seal_id"]
            or seal["key"] != row["key"]
            or seal["result"]["task"]["seed"] != seed
            or seal["result"]["task"]["partition"] != "train"
            or seal["result"]["task"].get("start_act", 1) != 1
            or seal["result"]["completed_acts"] < 1
        ):
            raise ValueError("The replay bank contains an unqualified training prefix")
    base = study.recovery.original.source.study.base
    used = known_seeds(base) | set(worlds) | {grid.EXCLUDED, grid.REPLACEMENT, grid.PREFIX_SEED}
    used.update(grid.CONTROL_SEEDS)
    historical = heads.world_schedule()
    for seeds in historical.values():
        used.update(seeds)
    for world in [
        *(w for group in study.worlds["training"] for w in group),
        *study.worlds["development"],
        *study.worlds["controls"],
        study.worlds["reload"],
    ]:
        if "seed" in world:
            used.add(world["seed"])
        else:
            used.update(world["case"]["seed_pool"])
    seeds = cfg["plan"]["development"] + cfg["plan"]["controls"]
    if (
        len(seeds) != len(set(seeds))
        or used.intersection(seeds)
        or proof["environment_id"] != cfg["environment_id"]
        or proof["objective"] != cfg["objective"]
        or cfg["environment_id"] != study.cfg["environment_id"]
        or ObjectiveSpec.from_mapping(cfg["objective"]) != study.ctx["score"].evaluation_objective
        or cfg["score_id"] != study.ctx["score"].spec_id
        or SETTINGS["temperature"] != TEMPERATURE
    ):
        raise ValueError("Require disjoint normal starts and the frozen evaluation objective")
    return proof


def dataset(
    root: Path,
    proof: dict[str, Any],
    partition: str,
    saved: Saved,
    score: TrainingScoreSpec,
    deadline: float,
    *,
    short: bool,
) -> Worlds:
    result: Worlds = {}
    seeds = proof["partitions"][partition]
    for seed in seeds[:4] if short else seeds:
        world = proof["worlds"][seed]
        labels = []
        path = verified(root, world["labels"])
        for raw in records(path):
            if time.monotonic() >= deadline:
                raise TimeoutError("Act 1 replay encoding reached the time limit")
            labels.append(encode_answer(raw, saved[0].model, score))
            if short and len(labels) == 8:
                break
        expected = (
            min(8, world["choice_bearing_answers"]) if short else world["choice_bearing_answers"]
        )
        if not labels or len(labels) != expected:
            raise ValueError("Act 1 replay decisions differ from the sealed bank")
        result[seed] = tuple(labels)
    return result


class Session(later.Session):
    def __init__(
        self,
        study: later.Study,
        cfg: dict[str, Any],
        proof: dict[str, Any],
        control: bool,
        deadline: float,
    ) -> None:
        super().__init__(study, deadline)
        self.store = ChunkJournal(
            study.recovery.root,
            {**cfg, "workspace": cfg["control_workspace"]} if control else cfg,
        )
        self.ctx["execution_id"] = self.store.config_id
        self.proof, self.short = proof, control
        self.game_seals: dict[str, str] = {}
        keys = cfg["plan"]["controls" if control else "development"]
        self.fresh = [
            {"key": f"success-{i:03}", "seed": seed, "act": 1, "archived": None}
            for i, seed in enumerate(keys, 1)
        ]
        self.later = original.Study(
            study.recovery,
            study.cfg,
            study.ctx,
            {**study.worlds, "development": self.fresh},
            study.parents,
            study.checkpoint_sources,
            study.bank,
        )
        self.check_frozen = study.unchanged

    def fit_replay(self, p: int, training: Worlds, holdout: Worlds) -> Saved:
        parent = self.later.parents[p]
        updates = CONTROL_UPDATES if self.short else UPDATES
        schedule = world_schedule(training, updates, self.proof["report_id"])
        if not self.short and any(
            len(set(indices)) != len(training[seed]) for seed, indices in schedule.items()
        ):
            raise ValueError("The declared fit must visit every admitted training answer")
        request = {
            "parent_state_id": parent[1],
            "bank_id": self.proof["report_id"],
            "updates": updates,
            "schedule_id": manifest_identifier(schedule),
        }

        def train_copy(target: Path) -> dict[str, Any]:
            before = parent[0]
            model = before.model
            actor, value = before.actor_adam, before.value_adam
            size = model.actor.parameter_count
            combined = Adam(actor.steps, actor.first + value.first, actor.second + value.second)
            for i in range(updates):
                if time.monotonic() >= self.deadline - 15:
                    raise TimeoutError("Preserve the incomplete offline fit")
                updated, combined, _ = imitation_update(
                    model, combined, batch(training, schedule, i)
                )
                if not isinstance(updated, type(before.model)):
                    raise ValueError("Imitation must preserve the shared-head model")
                model = updated
            # The existing imitation kernel sets the critic learning rate to
            # zero. Keep its frozen moments and clock in the fitted copy too.
            state = replace(
                before,
                model=model,
                actor_adam=Adam(combined.steps, combined.first[:size], combined.second[:size]),
            )
            if (
                state.model.actor == before.model.actor
                or state.model.value_weights != before.model.value_weights
                or state.value_adam != before.value_adam
                or state.actor_adam.steps != before.actor_adam.steps + updates
            ):
                raise ValueError("The replay fit must change only the copied actor and its Adam")
            return {
                "states": self.persist(target, {"shared": state}),
                "optimizer_updates": updates,
                "reference_holdout": metrics(before.model, holdout)["all"],
                "fitted_holdout": metrics(state.model, holdout)["all"],
            }

        key = f"fit-p{p}"
        seal = self.unit(key, request, 25 if self.short else 150, train_copy)
        result = seal["result"]
        state = self.checkpoint(key, "shared", result["states"]["shared"])
        if (
            result["optimizer_updates"] != updates
            or state[0].actor_adam.steps != parent[0].actor_adam.steps + updates
            or state[0].value_adam != parent[0].value_adam
            or state[0].model.value_weights != parent[0].model.value_weights
        ):
            raise ValueError("Reloaded copy has different weights or optimizer clocks")
        self.training.append({"player": p, "seal_id": seal["report_id"], **result})
        print(f"Player {p}: sealed {updates} Act 1 replay updates", flush=True)
        return state

    def compare(self, states: dict[int, Saved]) -> None:
        for i, world in enumerate(self.fresh, 1):
            for p in PLAYERS:
                for arm in original.ARMS if (i + p) % 2 else original.ARMS[::-1]:
                    task = original.evaluation_task(
                        world, p, arm, "control" if self.short else "development"
                    )
                    self.active_evaluation = task
                    state = self.later.parents[p] if arm == "original" else states[p]
                    row = self.game(task, state)
                    self.matched_start(task, row)
                    self.game_seals[task["key"]] = row["seal_id"]
                    self.evaluation_rows[task["seed"], p, arm] = row
            if not self.short and i % 8 == 0:
                print(f"Fresh normal-start A8 evaluation: {i}/{len(self.fresh)} worlds", flush=True)


def run(
    study: later.Study,
    cfg: dict[str, Any],
    proof: dict[str, Any],
    attempt: int,
    *,
    control: bool,
    deadline: float,
) -> dict[str, Any]:
    session = Session(study, cfg, proof, control, deadline)
    final = session.store.workspace / "report.json"
    complete = CONTROL if control else COMPLETE
    with session.store.lock():
        if final.exists():
            saved = identified(final)
            if saved["config_id"] != session.store.config_id or saved["status"] != complete:
                raise ValueError("The saved result belongs to another replay comparison")
            return saved
        status, stop = complete, None
        states: dict[int, Saved] = {}
        try:
            sets = [
                dataset(
                    session.study.root,
                    proof,
                    partition,
                    study.parents[2],
                    study.ctx["score"],
                    deadline - 20,
                    short=control,
                )
                for partition in ("fit", "fit_holdout")
            ]
            for p in PLAYERS:
                states[p] = session.fit_replay(p, sets[0], sets[1])
            session.check_frozen(session.profile)
            session.compare(states)
            if control and (
                session.games_seen != 4
                or any(
                    row["outcome"] not in {"win", "loss"}
                    for row in session.evaluation_rows.values()
                )
            ):
                raise ValueError("Short checks require four matched games with native endings")
        except CleanPause as exc:
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
        session.check_frozen(session.profile)
        verified(session.study.root, cfg["bank"])
        verified(session.study.root, cfg["comparison"])
        check_sources(session.study.root, cfg["implementation"])
        target = (
            final if status == complete else session.store.workspace / f"session-{attempt}.json"
        )
        return write(
            target,
            {
                "schema_version": SCHEMA,
                "status": status,
                "config_id": session.store.config_id,
                "bank_id": proof["report_id"],
                "objective": cfg["objective"],
                "starting_states": {str(p): study.parents[p][1] for p in PLAYERS},
                "final_states": {str(p): state[1] for p, state in states.items()},
                "game_seals": session.game_seals,
                "fits": session.training,
                "verified_games": session.games_seen,
                "copied_optimizer_updates": sum(
                    row["optimizer_updates"] for row in session.training
                ),
                "original_optimizer_updates": 0,
                "normal_start_evaluation": session.summary(),
                "frozen_checks": proof["frozen_checks"],
                "stop": stop,
                **SCOPE,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--execute", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the launcher with the frozen numerical settings")
        cfg = json.loads((root / RECIPE).read_text())
        if (
            cfg["schema_version"] != SCHEMA
            or cfg["implementation"] != implementation(root)
            or cfg["limits"] != LIMITS
            or cfg["plan"] != declaration()
            or cfg["workspace"] != f"{bank.AREA}/study-v1"
            or cfg["control_workspace"] != f"{bank.AREA}/control-v1"
        ):
            raise ValueError("Require the pinned Act 1 success replay comparison")
        if args.check or args.preflight or args.execute is not None:
            with bank.completed_study(root) as (study, completed):
                proof = load_bank(study, completed, cfg)
                control_store = ChunkJournal(root, {**cfg, "workspace": cfg["control_workspace"]})
                if not args.check:
                    control = identified(control_store.workspace / "report.json")
                    # Reconstruct only sealed requests. A zero deadline prevents
                    # the control verifier from launching a missing game.
                    control_session = Session(study, cfg, proof, True, 0)
                    if (
                        control["status"] != CONTROL
                        or control["config_id"] != control_store.config_id
                        or control["bank_id"] != proof["report_id"]
                        or control["verified_games"] != 4
                        or sorted(row["player"] for row in control["fits"]) != list(PLAYERS)
                        or control["copied_optimizer_updates"] != CONTROL_UPDATES * len(PLAYERS)
                        or control["frozen_checks"] != proof["frozen_checks"]
                    ):
                        raise ValueError("Require the exact short fit and fresh native controls")
                    control_states = {}
                    for row in control["fits"]:
                        key = f"fit-p{row['player']}"
                        request = json.loads((control_store.path(key) / "active.json").read_text())[
                            "request"
                        ]
                        seal = control_store.completed(key, request)
                        if (
                            seal is None
                            or seal["report_id"] != row["seal_id"]
                            or {
                                "player": row["player"],
                                "seal_id": row["seal_id"],
                                **seal["result"],
                            }
                            != row
                        ):
                            raise ValueError("The saved control fit differs")
                        state = control_session.checkpoint(key, "shared", row["states"]["shared"])
                        if state[1] != control["final_states"][str(row["player"])]:
                            raise ValueError("The control checkpoint differs")
                        control_states[row["player"]] = state
                    control_session.compare(control_states)
                    if (
                        control_session.game_seals != control["game_seals"]
                        or control_session.summary() != control["normal_start_evaluation"]
                    ):
                        raise ValueError("The saved control games differ")
                if args.preflight:
                    print(
                        json.dumps(
                            {
                                "status": "act1_success_replay_ready",
                                "bank_id": proof["report_id"],
                                "control_id": control["report_id"],
                                "worlds_by_partition": {
                                    name: len(seeds) for name, seeds in proof["partitions"].items()
                                },
                                "fresh_evaluation_games": len(cfg["plan"]["development"]) * 4,
                                "frozen_checks": proof["frozen_checks"],
                            }
                        )
                    )
                    return 0
                if _running_games():
                    raise ValueError("Close STS2 and wait for any other native worker")
                result = run(
                    study,
                    cfg,
                    proof,
                    args.execute or time.time_ns(),
                    control=args.check,
                    deadline=started
                    + (CONTROL_SECONDS if args.check else LIMITS["wall_seconds"] - 45),
                )
                print(json.dumps(result))
                return 0 if result["status"] in {COMPLETE, CONTROL, "paused"} else 2
        store = ChunkJournal(root, cfg)
        attempt = time.time_ns()
        print(
            "Fit two checkpoint copies on verified Act 1 clears and compare fresh A8 games.",
            flush=True,
        )
        tracked = run_tracked_command(
            command=["uv", "run", "--no-sync", "python", "-m", MODULE, "--execute", str(attempt)],
            working_directory=root,
            experiment_kind=ExperimentKind.TRAINING,
            report_path=store.workspace / f"resources-{attempt}.json",
            artifact_roots=[store.workspace],
            limits=ResourceLimits(**cfg["limits"]),
            poll_interval_seconds=8,
        )
        print(json.dumps(tracked.report))
        return 0 if tracked.exit_code == 0 and tracked.report["cap"] is None else 2
    except ERRORS as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc), **SCOPE}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
