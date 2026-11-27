"""Collect model-only normal starts, train checkpoint copies and compare fixed finals."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _running_games, _shared_snapshot
from spireshift.full_run_ppo_math import Adam
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_own_experience import play, samples
from spireshift.native_a8_own_ppo import Decision, update
from spireshift.native_a8_own_training_inputs import (
    CONTROL_PREFIX_CHOICES,
    MODULE,
    RECIPE,
    SCHEMA,
    admitted_context,
    declaration,
)
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_paired_report import summarize
from spireshift.native_a8_tactical_session import boundary, frozen
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS, execution_runtime
from spireshift.native_structured_state import load, save
from spireshift.native_value_credit import ValueRun, cross_fitted_predictions, prediction_metrics
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

State = tuple[CachedContextModel, Adam, str]
FAILURES = (
    ValueError,
    OSError,
    RuntimeError,
    subprocess.SubprocessError,
    StopIteration,
    ArithmeticError,
)
CONTROL_PASSED = "model_only_collect_fit_reload_verified"
SCOPE = {
    "promotion_allowed": False,
    "adaptive_controller_allowed": False,
    "automatic_follow_up": False,
    "official_live_qualification_granted": False,
    "final_test_worlds_used": False,
}


def require_control(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    store = ChunkJournal(root, {**cfg, "workspace": cfg["control_workspace"]})
    proof = identified(store.workspace / "report.json")
    resource = identified(_private_path(root, cfg["control_resource"]))
    if (
        proof["status"] != CONTROL_PASSED
        or proof["config_id"] != store.config_id
        or proof["scheduled_games"] != 6
        or len(proof["rounds"]) != len(PLAYERS)
        or set(proof["games"])
        != {
            *(task["key"] for task in cfg["control"]["training"]),
            *(f"reload-p{player}" for player in PLAYERS),
        }
        or any(r["optimizer_updates"] < 1 for r in proof["rounds"].values())
        or set(proof["seals"]) != {*proof["games"], *proof["rounds"], "initial-p2", "initial-p3"}
        or not all(proof["frozen_checks"].values())
        or proof["shared_profile_unchanged"] is not True
        or resource["status"] != "completed"
        or resource["exit_code"] != 0
        or resource["cap"] is not None
        or resource["limits"] != cfg["control_limits"]
        or resource["command"][:7]
        != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--execute-control"]
        or resource["artifacts"]["roots"] != [str(store.workspace)]
    ):
        raise ValueError("Require the exact passing collect, fit and reload short check")
    for key, seal_id in proof["seals"].items():
        request = json.loads((store.path(key) / "active.json").read_text())["request"]
        seal = store.completed(key, request)
        if seal is None or seal["report_id"] != seal_id:
            raise ValueError("The short-check seal differs")
    return proof


def restored(store: ChunkJournal, key: str, seal: dict[str, Any]) -> State:
    model, adam, state_id = load(store.path(key) / "state.json")
    result = seal["result"]
    if (
        state_id != result["state_id"]
        or model.model_id != result["model_id"]
        or adam.steps != result["optimizer_steps"]
        or manifest_identifier(adam.as_dict()) != result["optimizer_id"]
    ):
        raise ValueError("A saved full state or its Adam state differs")
    return model, adam, state_id


def save_checkpoint(target: Path, state: State) -> dict[str, Any]:
    model, adam, _ = state
    saved = save(target / "state.json", model, adam)
    return {
        "state_id": saved["state_id"],
        "model_id": model.model_id,
        "optimizer_steps": adam.steps,
        "optimizer_id": manifest_identifier(adam.as_dict()),
    }


def fit_batch(
    store: ChunkJournal,
    target: Path,
    games: list[dict[str, Any]],
    prior: State,
    ctx: dict[str, Any],
    cfg: dict[str, Any],
    plan: dict[str, Any],
    player: int,
    index: int,
) -> dict[str, Any]:
    model, adam, predecessor = prior
    runs: list[ValueRun] = []
    grouped: dict[int, list[Decision]] = {}
    outcomes: Counter[str] = Counter()
    families: Counter[str] = Counter()
    for game in games:
        task = game["task"]
        outcome = game["outcome"]
        outcomes[outcome] += 1
        if outcome == "capped":
            continue
        batch, run, counts = samples(
            store.path(task["key"]),
            game,
            model,
            ctx["score"],
            plan["training"][0]["partition"],
            index,
        )
        if run.seed in grouped:
            raise ValueError("A training world cannot be used twice in a batch")
        grouped[run.seed] = batch
        runs.append(run)
        families.update(counts)
    if len(runs) < plan["minimum_complete_games_per_batch"]:
        raise ValueError(f"Too few clean terminal training games for p{player} round {index}")
    credit = cfg["credit"]
    predictions, folds = cross_fitted_predictions(
        runs,
        credit["baseline"],
        credit["regularization"],
        min(credit["folds"], len(runs)),
        credit["fold_salt"],
    )
    training = [
        replace(d, advantage=d.target - baseline)
        for run in runs
        for d, baseline in zip(grouped[run.seed], predictions[run.seed], strict=True)
    ]
    learned, continued, work = update(
        model, adam, training, cfg["settings"], 80000 + 100 * player + index
    )
    return {
        **save_checkpoint(target, (learned, continued, predecessor)),
        "predecessor_state_id": predecessor,
        "player": player,
        "round": index,
        "optimizer_updates": continued.steps - adam.steps,
        "actor_weights_changed": model.actor.genome != learned.actor.genome,
        "scheduled_games": len(games),
        "outcomes": dict(outcomes),
        "admitted_native_decisions": len(training),
        "compound_decisions": sum(len(d.factors) > 1 for d in training),
        "native_decision_families": dict(families),
        "training_returns_by_seed_id": {str(r.seed): r.target for r in runs},
        "cross_fit": folds,
        "prediction_quality": prediction_metrics(runs, predictions),
        "work": work,
    }


def run(
    root: Path,
    ctx: dict[str, Any],
    runtime: dict[str, Any],
    cfg: dict[str, Any],
    *,
    control: bool,
    attempt: int,
    deadline: float,
) -> dict[str, Any]:
    if _running_games():
        raise ValueError("Close STS2 and wait for any other native worker")
    plan = cfg["control" if control else "study"]
    store = ChunkJournal(root, {**cfg, "workspace": cfg["control_workspace"]} if control else cfg)
    before, profile = frozen(root, ctx), _shared_snapshot(Path.home() / SHARED_PROFILE)
    seals: dict[str, str] = {}
    games: dict[str, dict[str, Any]] = {}
    rounds: dict[str, dict[str, Any]] = {}
    finals: dict[int, State] = {}
    originals: dict[int, State] = {}
    evaluation: dict[tuple[str, int, str], dict[str, Any]] = {}
    stop: dict[str, Any] | None = None
    active = "initialization"

    def check() -> None:
        if time.monotonic() >= deadline:
            raise TimeoutError("Session deadline reached. Preserve the unfinished unit")
        if json.loads((root / RECIPE).read_text()) != cfg:
            raise ValueError("Learning recipe changed during the session")
        check_sources(root, cfg["implementation"])
        boundary(root, ctx, before, profile)

    def game(task: dict[str, Any], state: State) -> dict[str, Any]:
        nonlocal active
        active = key = task["key"]
        model, _, state_id = state
        request = {"task": task, "behavior_state_id": state_id, "model_id": model.model_id}
        seal = store.completed(key, request)
        if seal is None:
            check()
            target = store.begin(key, request)
            limits = dict(cfg["game_limits"])
            if task["partition"] == "reload_control":
                limits["maximum_decisions"] = CONTROL_PREFIX_CHOICES
            game_ctx = {
                **ctx,
                "config": {"plan": limits},
                "execution_id": store.config_id,
            }
            result = play(game_ctx, task, target, model, deadline)
            check()
            seal = store.commit(key, request, result)
            print(f"{key} {result['outcome']} ({result['native_decisions']} decisions)", flush=True)
        seals[key] = seal["report_id"]
        result = dict(seal["result"])
        if result["task"] != task or result["model_id"] != model.model_id:
            raise ValueError("Sealed game is bound to a different task or behavior checkpoint")
        games[key] = result
        return result

    with store.lock():
        try:
            for player in PLAYERS:
                active = key = f"initial-p{player}"
                ref = ctx["states"][f"p{player}-original"]
                request = {"frozen_original": ref}
                seal = store.completed(key, request)
                if seal is None:
                    original = load(verified(root, ref))
                    target = store.begin(key, request)
                    state = save_checkpoint(target, original)
                    if state["state_id"] != ref["state_id"]:
                        raise ValueError("Initial copy must preserve all original weights and Adam")
                    seal = store.commit(key, request, state)
                seals[key] = seal["report_id"]
                originals[player] = restored(store, key, seal)
                current = originals[player]
                tasks = [task for task in plan["training"] if task["player"] == player]
                for index in sorted({task["round"] for task in tasks}):
                    batch = [game(task, current) for task in tasks if task["round"] == index]
                    active = key = f"fit-p{player}-r{index}"
                    request = {
                        "predecessor_state_id": current[2],
                        "training_games": [seals[row["task"]["key"]] for row in batch],
                        "settings": cfg["settings"],
                    }
                    seal = store.completed(key, request)
                    if seal is None:
                        check()
                        result = fit_batch(
                            store,
                            store.begin(key, request),
                            batch,
                            current,
                            ctx,
                            cfg,
                            plan,
                            player,
                            index,
                        )
                        check()
                        seal = store.commit(key, request, result)
                        print(f"{key} {result['optimizer_updates']} optimizer updates", flush=True)
                    seals[key] = seal["report_id"]
                    current = restored(store, key, seal)
                    rounds[key] = seal["result"]
                finals[player] = current

            if control:
                if any(
                    not r["actor_weights_changed"] or r["optimizer_updates"] < 1
                    for r in rounds.values()
                ):
                    raise ValueError("Both disposable copies must receive an actual actor update")
                for player, seed in zip(PLAYERS, plan["reload"], strict=True):
                    result = game(
                        {
                            "key": f"reload-p{player}",
                            "player": player,
                            "seed": seed,
                            "partition": "reload_control",
                        },
                        finals[player],
                    )
                    if (
                        result["outcome"] != "capped"
                        or result["native_decisions"] != CONTROL_PREFIX_CHOICES
                    ):
                        raise ValueError("Reload control must deliver its exact short prefix")
            else:
                for index, world in enumerate(plan["development"], 1):
                    for player in PLAYERS:
                        arms = ("original", "fitted")
                        if (index + player) % 2 == 0:
                            arms = arms[::-1]
                        for arm in arms:
                            task = {
                                "key": f"dev-{index:02d}-p{player}-{arm}",
                                "player": player,
                                "seed": world,
                                "arm": arm,
                                "partition": "development",
                            }
                            behavior = originals[player] if arm == "original" else finals[player]
                            try:
                                evaluation[world, player, arm] = game(task, behavior)
                            except FAILURES:
                                evaluation[world, player, arm] = {"outcome": "failed"}
                                raise
                    cells = [(world, p, arm) for p in PLAYERS for arm in ("original", "fitted")]
                    if len({evaluation[cell]["initial_public_input_id"] for cell in cells}) != 1:
                        for cell in cells:
                            evaluation[cell] = {"outcome": "failed"}
                        raise ValueError("A matched development world started with different menus")
            active = "final_verification"
            check()
            if execution_runtime(ctx["node"]) != runtime:
                raise ValueError("The pinned numerical runtime changed")
        except FAILURES as exc:
            stop = {"unit": active, "error": f"{type(exc).__name__}: {exc}"}

        training_outcomes = Counter(
            games[task["key"]]["outcome"]
            if task["key"] in games
            else "failed"
            if stop and task["key"] == stop["unit"]
            else "unattempted"
            for task in plan["training"]
        )
        scheduled_development = 4 * len(plan["development"])
        status = CONTROL_PASSED if control else "a8_model_only_training_complete"
        report = {
            "schema_version": SCHEMA,
            "status": "stopped_preserving_evidence" if stop else status,
            "config_id": store.config_id,
            "environment_id": cfg["environment_id"],
            "policy_contract": cfg["policy_contract"],
            "training_score_id": cfg["training_score_id"],
            "objective": cfg["objective"],
            "scheduled_games": len(plan["training"]) + len(plan["reload"]) + scheduled_development,
            "scheduled_training_games": len(plan["training"]),
            "training_outcomes": dict(training_outcomes),
            "scheduled_development_games": scheduled_development,
            "games": games,
            "rounds": rounds,
            "seals": seals,
            "optimizer_updates_in_sealed_rounds": sum(
                r["optimizer_updates"] for r in rounds.values()
            ),
            "final_states": {str(p): state[2] for p, state in finals.items()},
            "development": summarize(plan["development"], evaluation)
            if plan["development"]
            else None,
            "development_fitted_arm": "fixed_model_only_PPO_final",
            "stop": stop,
            "game_build_frozen": True if stop is None else None,
            "frozen_checks": before if stop is None else None,
            "shared_profile_unchanged": True if stop is None else None,
            **SCOPE,
        }
        name = "report.json" if control else f"attempt-{attempt}.json"
        return write(store.workspace / name, report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--control", action="store_true")
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--execute-control", type=int)
    modes.add_argument("--execute-study", type=int)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the pinned launcher with the fixed numerical thread settings")
        cfg = declaration(root)
        control = args.control or args.execute_control is not None
        attempt = args.execute_control if control else args.execute_study
        limits = cfg["control_limits" if control else "session_limits"]
        workspace = _private_path(root, cfg["control_workspace" if control else "workspace"])
        if args.preflight or attempt is not None:
            ctx, runtime = admitted_context(root, cfg)
            if not control:
                proof = require_control(root, cfg)
            if args.preflight:
                print(
                    json.dumps(
                        {
                            "status": "model_only_a8_training_ready",
                            "config_id": ctx["learning_config_id"],
                            "short_check_id": proof["report_id"],
                            "study_unstarted": not workspace.exists(),
                            "frozen_checks": frozen(root, ctx),
                        }
                    )
                )
                return 0
            if attempt is None or attempt < 1:
                raise ValueError("Use the resource-tracked launcher")
            result = run(
                root,
                ctx,
                runtime,
                cfg,
                control=control,
                attempt=attempt,
                deadline=started + limits["wall_seconds"] - 12,
            )
            print(
                json.dumps(
                    {
                        k: result[k]
                        for k in (
                            "status",
                            "report_id",
                            "stop",
                            "optimizer_updates_in_sealed_rounds",
                            "development",
                        )
                    }
                ),
                flush=True,
            )
            return 0 if result["stop"] is None else 2

        attempt = time.time_ns()
        if control:
            resource = cfg["control_resource"]
            if workspace.exists() or (root / resource).exists():
                raise ValueError("Preserve the existing short control and its resource receipt")
            print("Four short games, PPO on copies and two reloaded prefixes.", flush=True)
        else:
            print("Close STS2. 48 training games, then 24 matched development games.", flush=True)
            print(
                "About 15–35 minutes with a 90-minute cap. Both originals are copied.", flush=True
            )
            resource = f"{cfg['resource_prefix']}-{attempt}.json"
        mode = "--execute-control" if control else "--execute-study"
        tracked = run_tracked_command(
            command=["uv", "run", "--no-sync", "python", "-m", MODULE, mode, str(attempt)],
            experiment_kind=ExperimentKind.TRAINING,
            report_path=_private_path(root, resource),
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
