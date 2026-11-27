"""Collect independent whole runs, fit matched copies, and test fresh A8 wins."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_own_experience
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_action_credit_audit import STATUS as AUDITED
from spireshift.native_a8_action_credit_session import inputs as action_credit_inputs
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_feedback_session import LIMITS, copied_state
from spireshift.native_a8_mix_session import PREFIX_CHOICES, Study, game, unchanged
from spireshift.native_a8_own_training import FAILURES, SCOPE, State
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_paired_report import summarize
from spireshift.native_a8_tactical_session import boundary, frozen
from spireshift.native_a8_world_credit import (
    ARMS,
    DRAWS,
    FITTED,
    SETTINGS,
    fit,
    policy,
    run_return,
)
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS, execution_runtime
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_a8_world_credit_session"
AREA = "artifacts/native-a8-world-credit"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-world-credit-v1.json"
WRAPPER = "scripts/train-a8-world-credit-v1.sh"
EVIDENCE = "docs/evidence/native-a8-action-credit-result-v1.json"
SCHEMA = "native-a8-world-credit-v1"
CONTROL_OK = "world_credit_collect_fit_reload_verified"
COMPLETE = "world_credit_development_complete"
SHORT_LIMITS = {**LIMITS, "wall_seconds": 270, "cpu_seconds": 500}
GATE = {"control": 1, "study": 4}
TERMINAL = {"win", "loss"}


def schedule(control: bool) -> dict[str, list[dict[str, Any]]]:
    tag, count = ("C", 2) if control else ("T", 8)
    training = [
        {
            "key": f"{tag.lower()}-{world:02d}-p{p}-draw-{draw}",
            "seed": f"SP1RESH1FTA8WR1{tag}{world:03d}",
            "seed_id": 99100 + 100 * p + 10 * world + draw + (1000 if control else 0),
            "player": p,
            "partition": "control" if control else "train",
            "round": 1,
            "draw": draw,
        }
        for world in range(1, count + 1)
        for p in PLAYERS
        for draw in range(DRAWS)
    ]
    evaluation = [
        {
            "key": f"{'reload' if control else 'dev'}-{world:02d}-p{p}-{arm}",
            "seed": f"SP1RESH1FTA8WR1{'P' if control else 'D'}{world:03d}",
            "player": p,
            "partition": "reload_control" if control else "development",
            "arm": arm,
        }
        for world in range(1, 2 if control else 9)
        for p in PLAYERS
        for arm in (FITTED if control else ARMS)
    ]
    return {"training": training, "evaluation": evaluation}


def implementation(root: Path) -> dict[str, str]:
    paths = (
        WRAPPER,
        "src/spireshift/native_a8_action_credit_audit.py",
        "src/spireshift/native_a8_world_credit.py",
        "src/spireshift/native_a8_world_credit_session.py",
    )
    return {name: _sha_file(root / name) for name in paths}


def inputs(root: Path) -> tuple[Study, dict[str, Any]]:
    base, pilot = action_credit_inputs(root)
    cfg = json.loads((root / RECIPE).read_text())
    evidence = identified(verified(root, cfg["assessment"]))
    verified(root, evidence["owner"])
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["environment_id"] != base.cfg["environment_id"]
        or cfg["objective"] != base.cfg["objective"]
        or cfg["score_spec_id"] != base.ctx["score"].spec_id
        or cfg["assessment"]["path"] != EVIDENCE
        or cfg["implementation"] != implementation(root)
        or cfg["control"] != schedule(True)
        or cfg["study"] != schedule(False)
        or cfg["minimum_varied_worlds"] != GATE
        or cfg["settings"] != SETTINGS
        or evidence["status"] != AUDITED
        or evidence["environment_id"] != cfg["environment_id"]
        or evidence["fitting_candidate"] is not False
        or evidence["frozen_checks"] != frozen(root, base.ctx)
    ):
        raise ValueError("Require the exact saved gate result and matched world-credit recipe")
    history = json.loads(verified(root, base.ctx["config"]["parent_recipe"]).read_text())
    used = set(
        json.loads(verified(root, history["seed_history"]).read_text())["canonical_prior_seeds"]
    )
    used.update(history["plan"]["reserved_evaluation_seeds"])
    used.update(base.ctx["paired_panel"]["worlds"])
    used.update([*base.cfg["development"], base.cfg["prefix_seed"], base.cfg["ending_seed"]])
    used.update(entry["seed"] for entry in base.bank["entries"].values())
    used.update(
        seed
        for cases in base.ctx["practice_cases"].values()
        for case in cases
        for seed in case["seed_pool"]
    )
    for stage in ("control", "study"):
        used.update(task["seed"] for task in pilot[stage])
        own = base.source.recipe[stage]
        used.update([*own["development"], *own["reload"], *(t["seed"] for t in own["training"])])
    for stage in ("control", "study"):
        for tasks in cfg[stage].values():
            seeds = {task["seed"] for task in tasks}
            if used & seeds or any(canonical_seed(seed) != seed for seed in seeds):
                raise ValueError(
                    "Training, control and development worlds must be fresh and separate"
                )
            used.update(seeds)
    return base, cfg


def journal(root: Path, cfg: dict[str, Any], control: bool) -> ChunkJournal:
    return ChunkJournal(root, {**cfg, "workspace": cfg["control_workspace"]} if control else cfg)


def tally(
    tasks: list[dict[str, Any]], rows: dict[str, dict[str, Any]], failed: str | None
) -> dict[str, int]:
    result = dict.fromkeys(("win", "loss", "capped", "failed", "unattempted"), 0)
    for task in tasks:
        key = task["key"]
        status = (
            rows[key]["outcome"] if key in rows else "failed" if key == failed else "unattempted"
        )
        result[status] += 1
    return result


def execute(
    base: Study, cfg: dict[str, Any], attempt: int, deadline: float, *, control: bool
) -> dict[str, Any]:
    store = journal(base.root, cfg, control)
    phase = "control" if control else "study"
    plan = cfg[phase]
    before, profile = frozen(base.root, base.ctx), _shared_snapshot(Path.home() / SHARED_PROFILE)
    games: dict[str, dict[str, Any]] = {}
    seals: dict[str, str] = {}
    fits: dict[str, Any] = {}
    states = {(p, "original"): state for p, state in base.originals.items()}
    initials: dict[str, str] = {}
    variety: dict[str, int] = {}
    stop = None
    key = "preflight"

    def check() -> None:
        unchanged(base, before, deadline)
        if json.loads((base.root / RECIPE).read_text()) != cfg:
            raise ValueError("World-credit recipe changed after launch")
        check_sources(base.root, cfg["implementation"])
        boundary(base.root, base.ctx, before, profile)

    def play(task: dict[str, Any], state: State) -> dict[str, Any]:
        unit = task["key"]
        request = {"task": task, "state_id": state[2]}
        seal = store.completed(unit, request)
        if seal is None:
            check()
            store.begin(unit, request)
            if task["partition"] in {"train", "control"}:
                with patch.object(native_a8_own_experience, "policy", policy):
                    result = game(base, store, task, state, deadline)
            else:
                result = game(base, store, task, state, deadline)
            check()
            seal = store.commit(unit, request, result)
            print(f"{unit} {result['outcome']} (floor {result['maximum_floor']})", flush=True)
        row: dict[str, Any] = seal["result"]
        initial = row["initial_public_input_id"]
        if (
            row["task"] != task
            or row["model_id"] != state[0].model_id
            or initials.setdefault(task["seed"], initial) != initial
        ):
            raise ValueError("Saved normal starts or checkpoint identities do not match")
        games[unit], seals[unit] = row, seal["report_id"]
        return row

    ready = False
    with store.lock():
        try:
            check()
            for task in plan["training"]:
                key = task["key"]
                play(task, base.originals[task["player"]])
            terminal = all(row["outcome"] in TERMINAL for row in games.values())
            train = {
                p: [games[t["key"]] for t in plan["training"] if t["player"] == p] for p in PLAYERS
            }
            if terminal:
                for p, rows in train.items():
                    scores: dict[str, set[float]] = defaultdict(set)
                    for row in rows:
                        scores[row["task"]["seed"]].add(run_return(row, base.ctx["score"]))
                    variety[str(p)] = sum(len(r) > 1 for r in scores.values())
                ready = all(n >= GATE[phase] for n in variety.values())
            if ready:
                for p, rows in train.items():
                    key = f"fit-p{p}"
                    original = base.originals[p]
                    request = {
                        "player": p,
                        "original_id": original[2],
                        "training_seals": [seals[row["task"]["key"]] for row in rows],
                    }
                    seal = store.completed(key, request)
                    if seal is None:
                        check()
                        result = fit(
                            store, store.begin(key, request), original, rows, base.ctx["score"], p
                        )
                        check()
                        seal = store.commit(key, request, result)
                        print(
                            f"{key} sealed {result['optimizer_updates_per_copy']} updates per copy",
                            flush=True,
                        )
                    fits[str(p)], seals[key] = seal["result"], seal["report_id"]
                    for arm in FITTED:
                        states[p, arm] = copied_state(store, p, arm, seal["result"])
                for task in plan["evaluation"]:
                    key = task["key"]
                    row = play(task, states[task["player"], task["arm"]])
                    if control and (
                        row["outcome"] != "capped" or row["native_decisions"] != PREFIX_CHOICES
                    ):
                        raise ValueError(
                            "The short reload must deliver its exact four-choice prefix"
                        )
            key = "final_verification"
            check()
            if execution_runtime(base.ctx["node"]) != base.runtime:
                raise ValueError("The numerical runtime changed")
        except FAILURES as exc:
            stop = {"unit": key, "error": f"{type(exc).__name__}: {exc}"}

        planned = {task["key"] for tasks in plan.values() for task in tasks}
        failed = key if stop and key in planned and store.path(key).exists() else None
        evaluation = plan["evaluation"]
        training_counts = tally(plan["training"], games, failed)
        evaluation_counts = tally(evaluation, games, failed)
        if stop is not None or training_counts["win"] + training_counts["loss"] != len(
            plan["training"]
        ):
            status = "world_credit_incomplete"
        elif not ready:
            status = "world_credit_variation_gate_blocked"
        elif control:
            status = CONTROL_OK
        elif evaluation_counts["win"] + evaluation_counts["loss"] == len(evaluation):
            status = COMPLETE
        else:
            status = "world_credit_incomplete"
        development = {}
        if not control:
            worlds = list(dict.fromkeys(task["seed"] for task in evaluation))
            for left, right in (
                ("pooled", "within_world"),
                ("original", "pooled"),
                ("original", "within_world"),
            ):
                paired_games = {}
                for task in evaluation:
                    arm, unit = task["arm"], task["key"]
                    if arm in (left, right) and (unit in games or unit == failed):
                        paired_games[
                            task["seed"], task["player"], "original" if arm == left else "fitted"
                        ] = games.get(unit, {"outcome": "failed"})
                development[f"{right}_minus_{left}"] = {
                    "reference_arm": left,
                    "candidate_arm": right,
                    **summarize(worlds, paired_games),
                }
        return write(
            store.workspace / f"attempt-{attempt}.json",
            {
                "schema_version": SCHEMA,
                "status": status,
                "config_id": store.config_id,
                "training": training_counts,
                "evaluation": evaluation_counts,
                "varied_worlds_by_initializer": variety,
                "minimum_varied_worlds_per_initializer": GATE[phase],
                "fits": fits,
                "seals": seals,
                "games": games,
                "development": development,
                "stop": stop,
                "optimizer_updates_on_copies": 2
                * sum(row["optimizer_updates_per_copy"] for row in fits.values()),
                "original_optimizer_updates": 0,
                "forced_action_probes_used": 0,
                "frozen_checks": before if stop is None else None,
                "shared_profile_unchanged": stop is None,
                **SCOPE,
            },
        )


def require_control(base: Study, cfg: dict[str, Any]) -> None:
    store = journal(base.root, cfg, True)
    resource = identified(_private_path(base.root, cfg["control_resource"]))
    attempt = int(resource["command"][-1])
    report = identified(store.workspace / f"attempt-{attempt}.json")
    expected = {task["key"] for tasks in cfg["control"].values() for task in tasks}
    expected.update(f"fit-p{p}" for p in PLAYERS)
    if (
        resource["status"] != "completed"
        or resource["exit_code"] != 0
        or resource["cap"] is not None
        or resource["command"]
        != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--check", str(attempt)]
        or resource["limits"] != SHORT_LIMITS
        or resource["artifacts"]["roots"] != [str(store.workspace)]
        or report["status"] != CONTROL_OK
        or report["config_id"] != store.config_id
        or report["stop"] is not None
        or set(report["seals"]) != expected
        or report["frozen_checks"] != frozen(base.root, base.ctx)
    ):
        raise ValueError("Require the exact passing world-credit collect, fit and reload control")
    for key, seal_id in report["seals"].items():
        request = json.loads((store.path(key) / "active.json").read_text())["request"]
        seal = store.completed(key, request)
        if seal is None or seal["report_id"] != seal_id:
            raise ValueError("The world-credit short check has changed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--control", action="store_true")
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--check", type=int)
    modes.add_argument("--study", type=int)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the launcher with its fixed numerical settings")
        base, cfg = inputs(root)
        if not (args.control or args.check is not None):
            require_control(base, cfg)
        if args.check is not None or args.study is not None:
            control = args.check is not None
            result = execute(
                base,
                cfg,
                args.check or args.study,
                started + (SHORT_LIMITS if control else LIMITS)["wall_seconds"] - 20,
                control=control,
            )
            print(json.dumps({k: v for k, v in result.items() if k not in {"games", "seals"}}))
            return 0 if result["status"] in {CONTROL_OK, COMPLETE} else 2
        if args.preflight:
            print(
                json.dumps({"status": CONTROL_OK, **{k: len(v) for k, v in cfg["study"].items()}})
            )
            return 0
        attempt = time.time_ns()
        workspace = journal(root, cfg, args.control).workspace
        resource = (
            _private_path(root, cfg["control_resource"])
            if args.control
            else workspace.with_name(f"{workspace.name}-{attempt}-resources.json")
        )
        if resource.exists():
            raise FileExistsError("Preserve the existing world-credit resource receipt")
        mode, limits = ("--check", SHORT_LIMITS) if args.control else ("--study", LIMITS)
        if not args.control:
            print(
                "Close STS2. 48 training games and 48 fresh evaluation games if the gate passes. "
                "Allow about 25–40 minutes.",
                flush=True,
            )
        tracked = run_tracked_command(
            command=["uv", "run", "--no-sync", "python", "-m", MODULE, mode, str(attempt)],
            experiment_kind=ExperimentKind.TRAINING,
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
