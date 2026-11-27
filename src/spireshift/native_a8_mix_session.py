"""Prepare matched A8 fits on copies, then compare fixed actors on fresh normal starts."""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_feedback_host, native_a8_own_experience
from spireshift import native_a8_practice_session as practice
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_feedback_host import FeedbackWorker
from spireshift.native_a8_feedback_session import LIMITS, copied_state, inputs
from spireshift.native_a8_mix_data import practice_index
from spireshift.native_a8_mix_fit import (
    ARMS,
    AUXILIARY_BATCH,
    AUXILIARY_WEIGHT,
    PRACTICE_PER_BATCH,
    fit,
)
from spireshift.native_a8_own_training import FAILURES, SCOPE, State
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_paired_report import summarize
from spireshift.native_a8_tactical_session import boundary, frozen
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS, execution_runtime
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_a8_mix_session"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-matched-practice-fitting-v2.json"
WRAPPER = "scripts/compare-a8-practice-fitting-v2.sh"
WORKER = "engine-a8-mixed-practice-worker-v1.mjs"
PROJECTION = "native_a8_mixed_practice_verified_v1"
AREA = "artifacts/native-a8-matched-practice"
SCHEMA = "native-a8-matched-practice-fitting-v2"
PREPARED = "matched_practice_fits_frozen"
COMPLETE = "matched_practice_development_complete"
PRACTICE_EVIDENCE = "docs/evidence/native-a8-practice-continuation-v1.json"
SHORT_LIMITS = {**LIMITS, "wall_seconds": 270, "cpu_seconds": 480}
PREFIX_CHOICES = 4
FITTING_EPOCHS = 2
DEVELOPMENT = [f"SP1RESH1FTA8MX1D{i:03d}" for i in range(1, 13)]
PREFIX_SEED = "SP1RESH1FTA8MX1P001"
ENDING_SEED = "SP1RESH1FTA8MX1C001"


@dataclass
class Study:
    root: Path
    cfg: dict[str, Any]
    ctx: dict[str, Any]
    runtime: dict[str, Any]
    source: ChunkJournal
    source_report: dict[str, Any]
    bank: dict[str, Any]
    originals: dict[int, State]


class MixWorker(FeedbackWorker):
    def __init__(self, ctx: dict[str, Any], target: Path) -> None:
        with patch.multiple(native_a8_feedback_host, SCRIPT=WORKER, PROJECTION=PROJECTION):
            super().__init__(ctx, target)


def implementation(root: Path) -> dict[str, str]:
    paths = {WRAPPER, *(f"scripts/{name}" for name in worker_helpers(root, WORKER))}
    paths.update(f"src/spireshift/native_a8_mix_{name}.py" for name in ("data", "fit", "session"))
    return {name: _sha_file(root / name) for name in sorted(paths)}


def admit(root: Path) -> Study:
    cfg = json.loads((root / RECIPE).read_text())
    feedback, _, _, source, report = inputs(root)
    old, ctx, runtime, originals, prep_id = practice.load_inputs(root)
    practice.require_control(root, old, prep_id)
    evidence = identified(verified(root, cfg["practice_evidence"]))
    bank = practice_index(root, old, ctx, originals, prep_id, evidence)
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["environment_id"] != ctx["environment_id"]
        or cfg["objective"] != feedback["objective"]
        or cfg["game_limits"] != feedback["game_limits"]
        or cfg["policy_contract"] != feedback["policy_contract"]
        or cfg["practice_evidence"]["path"] != PRACTICE_EVIDENCE
        or cfg["source_training_report_id"] != report["report_id"]
        or cfg["practice_bank_id"] != bank["report_id"]
        or cfg["fitting_epochs"] != FITTING_EPOCHS
        or cfg["auxiliary"]
        != {
            "weight": AUXILIARY_WEIGHT,
            "batch": AUXILIARY_BATCH,
            "prepared_in_mixed": PRACTICE_PER_BATCH,
        }
        or cfg["development"] != DEVELOPMENT
        or cfg["prefix_seed"] != PREFIX_SEED
        or cfg["ending_seed"] != ENDING_SEED
        or cfg["implementation"] != implementation(root)
    ):
        raise ValueError("Require the exact scoped practice fitting recipe")

    curriculum = json.loads(verified(root, ctx["config"]["parent_recipe"]).read_text())
    history = json.loads(verified(root, curriculum["seed_history"]).read_text())
    used = set(history["canonical_prior_seeds"])
    used.update(curriculum["plan"]["reserved_evaluation_seeds"])
    used.update(ctx["paired_panel"]["worlds"])
    used.update([*feedback["development"], feedback["trial_seed"], feedback["prefix_seed"]])
    for scope in ("study", "control"):
        data = source.recipe[scope]
        used.update(task["seed"] for task in data["training"])
        used.update(data["development"] + data["reload"])
    used.update(entry["seed"] for entry in bank["entries"].values())
    for cases in ctx["practice_cases"].values():
        used.update(seed for case in cases for seed in case["seed_pool"])
    seeds = [*cfg["development"], cfg["prefix_seed"], cfg["ending_seed"]]
    if (
        len(seeds) != len(set(seeds))
        or used.intersection(seeds)
        or any(canonical_seed(seed) != seed for seed in seeds)
    ):
        raise ValueError("Controls, training and development must use disjoint worlds")
    return Study(root, cfg, ctx, runtime, source, report, bank, originals)


def preparation(study: Study) -> ChunkJournal:
    return ChunkJournal(study.root, {**study.cfg, "workspace": study.cfg["preparation_workspace"]})


def fit_request(study: Study, player: int) -> dict[str, Any]:
    return {
        "player": player,
        "original_state_id": study.originals[player][2],
        "normal_source_id": study.source_report["report_id"],
        "practice_bank_id": study.bank["report_id"],
    }


def control_tasks(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "key": f"prefix-p{p}-{arm}",
            "player": p,
            "arm": arm,
            "seed": cfg["prefix_seed"],
            "partition": "reload_control",
        }
        for p in PLAYERS
        for arm in ARMS
    ] + [
        {
            "key": f"ending-p{p}-{arm}",
            "player": p,
            "arm": arm,
            "seed": cfg["ending_seed"],
            "partition": "ending_control",
        }
        for p, arm in zip(PLAYERS, ("normal", "mixed"), strict=True)
    ]


def game(
    study: Study,
    store: ChunkJournal,
    task: dict[str, Any],
    state: State,
    deadline: float,
) -> dict[str, Any]:
    limits = study.cfg["game_limits"].copy()
    if task["partition"] == "reload_control":
        limits["maximum_decisions"] = PREFIX_CHOICES
    env = {**study.ctx, "config": {"plan": limits}, "execution_id": store.config_id}
    with patch.object(native_a8_own_experience, "worker", MixWorker):
        return native_a8_own_experience.play(env, task, store.path(task["key"]), state[0], deadline)


def unchanged(study: Study, before: dict[str, Any], deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise TimeoutError("Session reached its deadline. Preserve unfinished evidence.")
    if (
        json.loads((study.root / RECIPE).read_text()) != study.cfg
        or frozen(study.root, study.ctx) != before
    ):
        raise ValueError("Frozen recipe, build or original states changed")
    check_sources(study.root, study.cfg["implementation"])


def prepare(study: Study, deadline: float) -> dict[str, Any]:
    store = preparation(study)
    before = frozen(study.root, study.ctx)
    fits, seals = {}, {}
    states: dict[tuple[int, str], State] = {}
    with store.lock():
        for player in PLAYERS:
            key = f"fit-p{player}"
            request = fit_request(study, player)
            seal = store.completed(key, request)
            if seal is None:
                unchanged(study, before, deadline)
                result = fit(
                    study.root,
                    study.source,
                    study.source_report,
                    study.bank,
                    study.ctx,
                    player,
                    study.originals[player],
                    store.begin(key, request),
                    deadline,
                    study.cfg["fitting_epochs"],
                )
                unchanged(study, before, deadline)
                seal = store.commit(key, request, result)
                print(
                    f"p{player} sealed {result['matched_optimizer_updates_per_arm']} updates "
                    f"per fitted copy, {result['prepared_draws_in_mixed_arm']} prepared draws.",
                    flush=True,
                )
            fits[str(player)] = seal["report_id"]
            for arm in ARMS:
                states[player, arm] = copied_state(store, player, arm, seal["result"])

        profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
        boundary(study.root, study.ctx, before, profile)
        initials: dict[str, str] = {}
        for task in control_tasks(study.cfg):
            key = task["key"]
            state = states[task["player"], task["arm"]]
            request = {"task": task, "state_id": state[2]}
            seal = store.completed(key, request)
            if seal is None:
                unchanged(study, before, deadline)
                store.begin(key, request)
                row = game(study, store, task, state, deadline)
                prefix = task["partition"] == "reload_control"
                if (
                    prefix
                    and (row["outcome"] != "capped" or row["native_decisions"] != PREFIX_CHOICES)
                    or not prefix
                    and row["outcome"] not in {"win", "loss"}
                ):
                    raise ValueError("Reload control did not reach its exact declared endpoint")
                boundary(study.root, study.ctx, before, profile)
                seal = store.commit(key, request, row)
            result = seal["result"]
            if (
                initials.setdefault(task["seed"], result["initial_public_input_id"])
                != result["initial_public_input_id"]
            ):
                raise ValueError("The native control starts are not matched")
            seals[key] = seal["report_id"]
            print(f"{key} verified {result['native_decisions']} delivered decisions", flush=True)
        unchanged(study, before, deadline)
        if execution_runtime(study.ctx["node"]) != study.runtime:
            raise ValueError("The pinned numerical runtime changed")
        return write(
            store.workspace / "report.json",
            {
                "schema_version": SCHEMA,
                "status": PREPARED,
                "config_id": store.config_id,
                "practice_bank_id": study.bank["report_id"],
                "fits": fits,
                "controls": seals,
                "frozen_checks": before,
                "shared_profile_unchanged": True,
                "development_games": 0,
                **SCOPE,
            },
        )


def require_prepared(study: Study) -> tuple[dict[str, Any], dict[tuple[int, str], State]]:
    store = preparation(study)
    proof = identified(store.workspace / "report.json")
    resource = identified(_private_path(study.root, study.cfg["preparation_resource"]))
    if (
        proof["status"] != PREPARED
        or proof["config_id"] != store.config_id
        or proof["practice_bank_id"] != study.bank["report_id"]
        or proof["development_games"] != 0
        or not all(proof["frozen_checks"].values())
        or proof["shared_profile_unchanged"] is not True
        or resource["status"] != "completed"
        or resource["cap"] is not None
        or resource["exit_code"] != 0
        or resource["limits"] != SHORT_LIMITS
        or resource["command"][:7]
        != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--execute-preparation"]
        or resource["artifacts"]["roots"] != [str(store.workspace)]
    ):
        raise ValueError("Require the successful matched fitting and native reload checks")
    states = {}
    for player in PLAYERS:
        key = f"fit-p{player}"
        seal = store.completed(key, fit_request(study, player))
        if seal is None or seal["report_id"] != proof["fits"][str(player)]:
            raise ValueError("Missing exact sealed fitting state")
        for arm in ARMS:
            states[player, arm] = copied_state(store, player, arm, seal["result"])
    for task in control_tasks(study.cfg):
        state = states[task["player"], task["arm"]]
        seal = store.completed(task["key"], {"task": task, "state_id": state[2]})
        if seal is None or seal["report_id"] != proof["controls"][task["key"]]:
            raise ValueError("Missing exact native reload or ending control")
    return proof, states


def tasks(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for index, seed in enumerate(cfg["development"], 1):
        for player in PLAYERS:
            rotation = (index + player) % len(ARMS)
            for arm in ARMS[rotation:] + ARMS[:rotation]:
                result.append(
                    {
                        "key": f"dev-{index:02d}-p{player}-{arm}",
                        "seed": seed,
                        "player": player,
                        "arm": arm,
                        "partition": "development",
                    }
                )
    return result


def compare(study: Study, attempt: int, deadline: float) -> dict[str, Any]:
    proof, states = require_prepared(study)
    store = ChunkJournal(study.root, study.cfg)
    before, profile = frozen(study.root, study.ctx), _shared_snapshot(Path.home() / SHARED_PROFILE)
    outcomes: dict[tuple[str, int, str], dict[str, Any]] = {}
    games: dict[str, Any] = {}
    initials: dict[str, str] = {}
    stop = None
    key = "preflight"

    def check() -> None:
        unchanged(study, before, deadline)
        boundary(study.root, study.ctx, before, profile)

    with store.lock():
        try:
            for task in tasks(study.cfg):
                key, seed, p, arm = (task[name] for name in ("key", "seed", "player", "arm"))
                state = states[p, arm]
                request = {"task": task, "state_id": state[2], "preparation_id": proof["report_id"]}
                seal = store.completed(key, request)
                if seal is None:
                    check()
                    store.begin(key, request)
                    try:
                        row = game(study, store, task, state, deadline)
                    except FAILURES as exc:
                        # Keep the failed cell and partial evidence. Only a verified isolated
                        # shutdown and frozen shared inputs allow independent worlds to proceed.
                        row = {
                            "task": task,
                            "model_id": state[0].model_id,
                            "outcome": "failed",
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    check()
                else:
                    row = seal["result"]
                initial = row.get("initial_public_input_id")
                if (
                    row["task"] != task
                    or row["model_id"] != state[0].model_id
                    or row["outcome"] != "failed"
                    and (not initial or initials.setdefault(seed, initial) != initial)
                ):
                    raise ValueError("Matched evaluation world or checkpoint differs")
                if seal is None:
                    seal = store.commit(key, request, row)
                    floor = row.get("maximum_floor")
                    print(
                        f"{key} {row['outcome']}" + (f" (floor {floor})" if floor else ""),
                        flush=True,
                    )
                games[key] = {"seal_id": seal["report_id"], **row}
                outcomes[seed, p, arm] = row
            key = "final_verification"
            check()
            if (
                require_prepared(study)[0] != proof
                or execution_runtime(study.ctx["node"]) != study.runtime
            ):
                raise ValueError("Frozen comparison checkpoints or numerical runtime changed")
        except FAILURES as exc:
            stop = {"unit": key, "error": f"{type(exc).__name__}: {exc}"}
            for task in tasks(study.cfg):
                if task["key"] == key and (store.workspace / "chunks" / key).exists():
                    outcomes[task["seed"], task["player"], task["arm"]] = {"outcome": "failed"}

        paired = {}
        for left, right in (("normal", "mixed"), ("original", "normal"), ("original", "mixed")):
            paired[f"{right}_minus_{left}"] = {
                "reference_arm": left,
                "candidate_arm": right,
                **summarize(
                    study.cfg["development"],
                    {
                        (seed, p, "original" if arm == left else "fitted"): row
                        for (seed, p, arm), row in outcomes.items()
                        if arm in (left, right)
                    },
                ),
            }
        terminal_games = sum(row["outcome"] in {"win", "loss"} for row in outcomes.values())
        planned_games = len(tasks(study.cfg))
        status = (
            COMPLETE
            if stop is None and terminal_games == planned_games
            else "matched_practice_development_incomplete"
        )
        return write(
            store.workspace / f"attempt-{attempt}.json",
            {
                "schema_version": SCHEMA,
                "status": status,
                "config_id": store.config_id,
                "preparation_id": proof["report_id"],
                "planned_worlds": study.cfg["development"],
                "planned_games": planned_games,
                "terminal_games": terminal_games,
                "games": games,
                "development": paired,
                "stop": stop,
                "optimizer_updates": 0,
                "frozen_checks": before if stop is None else None,
                **SCOPE,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--prepare", action="store_true")
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--execute-preparation", type=int)
    modes.add_argument("--execute-study", type=int)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the launcher with its fixed numerical settings")
        study = admit(root)
        if args.preflight:
            proof, _ = require_prepared(study)
            print(
                json.dumps(
                    {
                        "status": PREPARED,
                        "preparation_id": proof["report_id"],
                        "games": len(tasks(study.cfg)),
                        "frozen_checks": frozen(root, study.ctx),
                    }
                )
            )
            return 0
        if args.execute_preparation:
            result = prepare(study, started + SHORT_LIMITS["wall_seconds"] - 15)
            print(json.dumps(result), flush=True)
            return 0
        if args.execute_study:
            result = compare(study, args.execute_study, started + LIMITS["wall_seconds"] - 20)
            print(json.dumps({k: v for k, v in result.items() if k != "games"}), flush=True)
            return 0 if result["status"] == COMPLETE else 2
        attempt = time.time_ns()
        if args.prepare:
            workspace = preparation(study).workspace
            resource = _private_path(root, study.cfg["preparation_resource"])
            if resource.exists():
                raise FileExistsError("Preserve the existing preparation resource receipt")
            mode, limits = "--execute-preparation", SHORT_LIMITS
        else:
            require_prepared(study)
            workspace = _private_path(root, study.cfg["workspace"])
            resource = workspace.with_name(f"{workspace.name}-{attempt}-resources.json")
            mode, limits = "--execute-study", LIMITS
            print(
                "Close STS2. 72 normal-start A8 games on 12 fresh matched worlds. "
                "Allow about 15–30 minutes. Zero optimizer updates.",
                flush=True,
            )
        tracked = run_tracked_command(
            command=["uv", "run", "--no-sync", "python", "-m", MODULE, mode, str(attempt)],
            experiment_kind=ExperimentKind.TRAINING if args.prepare else ExperimentKind.OTHER,
            report_path=resource,
            artifact_roots=[workspace],
            working_directory=root,
            limits=ResourceLimits(**limits),
        )
        print(json.dumps(tracked.report, indent=2))
        return 0 if tracked.exit_code == 0 and tracked.status == "completed" else 2
    except FAILURES as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
