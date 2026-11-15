"""Fit both A8 checkpoint copies and evaluate their frozen policies on paired worlds."""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_archive_fit_inputs import (
    CONTROL_UPDATES,
    LIMITS,
    PER_WORLD,
    RECIPE,
    SCHEMA,
    SHORT_LIMITS,
    UPDATES,
    ArchiveFit,
    archive_fit,
    dataset,
)
from spireshift.native_a8_bank_fit import (
    Decision,
    Schedule,
    Worlds,
    metrics,
    update,
    world_schedule,
)
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_mix_session import PREFIX_CHOICES, game
from spireshift.native_a8_own_training import FAILURES, SCOPE, State, restored, save_checkpoint
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_paired_report import ARMS, TERMINAL, summarize
from spireshift.native_a8_tactical_session import boundary
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS, execution_runtime
from spireshift.native_structured_state import load, save
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_a8_archive_fit_session"
CONTROL_PASSED = "a8_archive_copy_fit_control_verified"
COMPLETE = "a8_archive_fit_development_complete"
INCOMPLETE = "a8_archive_fit_development_incomplete"
ERRORS = (*FAILURES, LookupError, TypeError)


def journal(study: ArchiveFit, control: bool) -> ChunkJournal:
    cfg = study.cfg
    return ChunkJournal(
        study.base.root,
        {
            **cfg,
            "workspace": cfg["control_workspace" if control else "workspace"],
            "short_control": control,
        },
    )


def resource_path(store: ChunkJournal) -> Path:
    return store.workspace.with_name(f"{store.workspace.name}-resources.json")


def check_inputs(study: ArchiveFit) -> None:
    root, ctx = study.base.root, study.base.ctx
    if json.loads((root / RECIPE).read_text()) != study.cfg:
        raise ValueError("The archive fitting recipe changed")
    check_sources(root, study.cfg["implementation"])
    for name in ("archive_result", "archive_config", "learner_input_audit"):
        verified(root, study.cfg[name])
    for ref in study.bank["coverage"]["bank"].values():
        verified(root, ref)
    adapter = ctx["confirmation_adapter"]
    if (
        _sha_file(Path(adapter["path"])) != adapter["sha256"]
        or execution_runtime(ctx["node"]) != study.base.runtime
    ):
        raise ValueError("The frozen adapter or numerical runtime changed")


def fit_batch(worlds: Worlds, schedule: Schedule, step: int) -> tuple[Decision, ...]:
    first = step * PER_WORLD
    batch = tuple(
        worlds[seed][i]
        for seed, indices in schedule.items()
        for i in indices[first : first + PER_WORLD]
    )
    if len(batch) != len(worlds) * PER_WORLD:
        raise ValueError("Each update must include the same number of answers from each world")
    return batch


def fit_request(study: ArchiveFit, player: int, updates: int) -> dict[str, Any]:
    return {
        "player": player,
        "initial_state_id": study.base.originals[player][2],
        "archive_bank_id": study.bank["report_id"],
        "learner_input_audit_id": study.audit["report_id"],
        "updates": updates,
    }


def fit_copy(
    study: ArchiveFit,
    player: int,
    target: Path,
    worlds: Worlds,
    updates: int,
    deadline: float,
) -> dict[str, Any]:
    initial = study.base.originals[player]
    path = target / "initial-state.json"
    save(path, initial[0], initial[1])
    model, adam, state_id = load(path)
    if (model.weights(), adam, state_id) != (initial[0].weights(), initial[1], initial[2]):
        raise ValueError("The initial copy changed weights or the full Adam state")
    draws = updates * PER_WORLD
    schedule = world_schedule(worlds, draws, study.bank["report_id"])
    if updates == UPDATES and any(
        len(set(indices)) != len(worlds[seed]) for seed, indices in schedule.items()
    ):
        raise ValueError("The final schedule must visit every admitted answer")
    for step in range(updates):
        if time.monotonic() >= deadline:
            raise TimeoutError("The archive fitting deadline was reached")
        model, adam, loss = update(model, adam, fit_batch(worlds, schedule, step))
        if not math.isfinite(loss):
            raise ValueError("Archive imitation loss must be finite")
    if model.model_id == initial[0].model_id or adam.steps != initial[1].steps + updates:
        raise ValueError("Fitting must update the copied actor and advance only its Adam state")
    return {
        **save_checkpoint(target, (model, adam, state_id)),
        "initial_state_id": state_id,
        "optimizer_updates": updates,
        "schedule_id": manifest_identifier(schedule),
        "draws_per_world": dict.fromkeys(schedule, draws),
        "demonstration_metrics": {
            "initial": metrics(initial[0], worlds)["all"],
            "fitted": metrics(model, worlds)["all"],
        },
    }


def tasks(study: ArchiveFit, control: bool) -> list[dict[str, Any]]:
    worlds = [study.cfg["control"]["prefix_world"]] if control else study.cfg["development"]
    plan = [
        {
            "key": f"{'prefix' if control else 'world'}-{index + 1:02d}-p{p}-{arm}",
            "seed": seed,
            "player": p,
            "arm": arm,
            "partition": "reload_control" if control else "development",
        }
        for index, seed in enumerate(worlds)
        for p in PLAYERS
        for arm in (ARMS if (index + p) % 2 == 0 else ARMS[::-1])
    ]
    if control:
        plan.append(
            {
                "key": "ending-p2-fitted",
                "seed": study.cfg["control"]["ending_world"],
                "player": 2,
                "arm": "fitted",
                "partition": "ending_control",
            }
        )
    return plan


def saved_report(store: ChunkJournal) -> dict[str, Any]:
    report = identified(store.workspace / "report.json")
    if report["config_id"] != store.config_id:
        raise ValueError("The saved archive fitting report belongs to another recipe")
    for key, seal_id in report["seals"].items():
        request = json.loads((store.path(key) / "active.json").read_text())["request"]
        seal = store.completed(key, request)
        if seal is None or seal["report_id"] != seal_id:
            raise ValueError("The saved archive fitting seal changed")
    return report


def require_control(study: ArchiveFit) -> str:
    store = journal(study, True)
    proof = saved_report(store)
    resources = identified(resource_path(store))
    if (
        proof["status"] != CONTROL_PASSED
        or proof["stop"] is not None
        or proof["frozen_checks"] != study.frozen_checks
        or proof["copied_optimizer_updates"] != CONTROL_UPDATES * len(PLAYERS)
        or set(proof["seals"])
        != {*(f"fit-p{p}" for p in PLAYERS), *(t["key"] for t in tasks(study, True))}
        or resources["status"] != "completed"
        or resources["exit_code"] != 0
        or resources["cap"] is not None
        or resources["limits"] != SHORT_LIMITS
        or resources["command"]
        != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--execute", "control"]
        or resources["artifacts"]["roots"] != [str(store.workspace)]
    ):
        raise ValueError("Require the passing archive copy, reload and native control")
    return str(proof["report_id"])


def development_result(
    study: ArchiveFit, outcomes: dict[tuple[str, int, str], dict[str, Any]]
) -> dict[str, Any]:
    result = summarize(study.cfg["development"], outcomes)
    result["verified_act1_clears"] = {
        str(player): {
            arm: sum(
                outcomes.get((seed, player, arm), {}).get("completed_acts", 0) >= 1
                for seed in study.cfg["development"]
            )
            for arm in ARMS
        }
        for player in PLAYERS
    }
    return result


def run(study: ArchiveFit, control: bool, deadline: float) -> dict[str, Any]:
    if _running_games():
        raise ValueError("Close STS2 and wait for the other native worker")
    control_id = None if control else require_control(study)
    base, store = study.base, journal(study, control)
    before = study.frozen_checks
    profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
    plan = tasks(study, control)
    updates = CONTROL_UPDATES if control else UPDATES
    fits: dict[str, Any] = {}
    games: dict[str, Any] = {}
    outcomes: dict[tuple[str, int, str], dict[str, Any]] = {}
    initials: dict[str, str] = {}
    states: dict[tuple[int, str], State] = {(p, "original"): base.originals[p] for p in PLAYERS}
    seals: dict[str, str] = {}
    stop = None
    task = None
    key = "fitting_data"
    with store.lock():
        if (store.workspace / "report.json").exists():
            return saved_report(store)
        try:
            check_inputs(study)
            worlds = dataset(study, deadline)
            for p in PLAYERS:
                key = f"fit-p{p}"
                request = fit_request(study, p, updates)
                seal = store.completed(key, request)
                if seal is None:
                    row = fit_copy(study, p, store.begin(key, request), worlds, updates, deadline)
                    boundary(base.root, base.ctx, before, profile)
                    seal = store.commit(key, request, row)
                states[p, "fitted"] = restored(store, key, seal)
                seals[key], fits[str(p)] = seal["report_id"], seal["result"]
                print(f"Player {p} copy sealed after {updates} updates", flush=True)
            if fits["2"]["schedule_id"] != fits["3"]["schedule_id"]:
                raise ValueError("Both copies must use the exact same world schedule")

            for task in plan:
                key, seed, p, arm = (task[k] for k in ("key", "seed", "player", "arm"))
                state = states[p, arm]
                request = {"task": task, "state_id": state[2], "control_id": control_id}
                seal = store.completed(key, request)
                if seal is None:
                    if time.monotonic() >= deadline - 40:
                        raise TimeoutError(
                            "Preserve the remaining worlds without starting another game"
                        )
                    store.begin(key, request)
                    row = game(base, store, task, state, deadline)
                    boundary(base.root, base.ctx, before, profile)
                else:
                    row = seal["result"]
                initial = row["initial_public_input_id"]
                if (
                    row["task"] != task
                    or row["model_id"] != state[0].model_id
                    or row["outcome"] not in {*TERMINAL, "capped"}
                    or not initial
                    or initials.setdefault(seed, initial) != initial
                ):
                    raise ValueError(
                        "The normal start, frozen policy or matched initial menu differs"
                    )
                if control:
                    prefix = task["partition"] == "reload_control"
                    if (
                        prefix
                        and (row["outcome"], row["native_decisions"]) != ("capped", PREFIX_CHOICES)
                    ) or (not prefix and row["outcome"] not in TERMINAL):
                        raise ValueError("The short control did not reach its declared endpoint")
                if seal is None:
                    seal = store.commit(key, request, row)
                    print(f"{key} {row['outcome']} at floor {row['maximum_floor']}", flush=True)
                seals[key], games[key] = seal["report_id"], row
                outcomes[seed, p, arm] = row
            task, key = None, "final_verification"
            check_inputs(study)
            boundary(base.root, base.ctx, before, profile)
            for p in PLAYERS:
                fit_key = f"fit-p{p}"
                seal = store.completed(fit_key, fit_request(study, p, updates))
                if seal is None or seals[fit_key] != seal["report_id"]:
                    raise ValueError("The fitted checkpoint changed during evaluation")
        except ERRORS as exc:
            stop = {"unit": key, "error": f"{type(exc).__name__}: {exc}"}
            if task is not None and store.path(key).exists() and key not in games:
                outcomes[task["seed"], task["player"], task["arm"]] = {"outcome": "failed"}

        terminals = sum(row["outcome"] in TERMINAL for row in outcomes.values())
        complete = stop is None and (control or terminals == len(plan))
        return write(
            store.workspace / "report.json",
            {
                "schema_version": SCHEMA,
                "status": (CONTROL_PASSED if control else COMPLETE) if complete else INCOMPLETE,
                "config_id": store.config_id,
                "archive_bank_id": study.bank["report_id"],
                "control_id": control_id,
                "objective": study.cfg["objective"],
                "planned_games": len(plan),
                "terminal_games": terminals,
                "fits": fits,
                "games": games,
                "seals": seals,
                "development": None if control else development_result(study, outcomes),
                "stop": stop,
                "copied_optimizer_updates": sum(row["optimizer_updates"] for row in fits.values()),
                "original_optimizer_updates": 0,
                "evaluation_optimizer_updates": 0,
                "frozen_checks": before if stop is None else None,
                "shared_profile_unchanged": True if stop is None else None,
                **SCOPE,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--control", action="store_true", help="Fit disposable copies and check native reloads"
    )
    mode.add_argument("--execute", choices=("control", "study"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the launcher with its fixed numerical settings")
        study = archive_fit(root)
        control = args.control or args.execute == "control"
        store = journal(study, control)
        limits = SHORT_LIMITS if control else LIMITS
        result_path = store.workspace / "report.json"
        if args.execute:
            result = run(study, control, started + limits["wall_seconds"] - 15)
        elif result_path.is_file():
            result = saved_report(store)
        else:
            if not control:
                require_control(study)
                print(
                    "Close STS2. Fit two checkpoint copies, then compare 48 fresh A8 games. "
                    "Allow about 12 to 25 minutes.",
                    flush=True,
                )
            if _running_games():
                raise ValueError("Close STS2 and wait for the other native worker")
            tracked = run_tracked_command(
                command=[
                    "uv",
                    "run",
                    "--no-sync",
                    "python",
                    "-m",
                    MODULE,
                    "--execute",
                    "control" if control else "study",
                ],
                experiment_kind=ExperimentKind.TRAINING,
                report_path=resource_path(store),
                artifact_roots=[store.workspace],
                working_directory=root,
                limits=ResourceLimits(**limits),
            )
            print(json.dumps(tracked.report), flush=True)
            return 2 if tracked.exit_code is None else tracked.exit_code
        print(
            json.dumps({k: v for k, v in result.items() if k not in {"games", "seals"}}), flush=True
        )
        return 0 if result["status"] in {CONTROL_PASSED, COMPLETE} else 2
    except ERRORS as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
