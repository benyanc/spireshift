"""Restartable, finite two-player/two-arm comparison from preserved round-56 states."""

from __future__ import annotations

import argparse
import json
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import (
    EngineQualificationConfig,
    _sha_file,
    load_engine_qualification_config,
)
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal, load_state
from spireshift.native_context_resume import request_for
from spireshift.native_context_reuse import check_sources
from spireshift.native_exploration_admission import load
from spireshift.native_exploration_execute import execute
from spireshift.native_exploration_plan import comparisons, panels, plan
from spireshift.training_objective import load_training_score_spec

COMPLETE = "native_rest_exploration_complete"
CONTROL = "native_rest_exploration_control_pass"


def session(
    q: EngineQualificationConfig,
    path: Path,
    node: Path,
    *,
    status_only: bool = False,
    maximum_steps: int | None = None,
    wall_seconds: int | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    cfg, parent, seeds, sources = load(q, path)
    store = ChunkJournal(q.root, cfg)
    score = load_training_score_spec(q.root / parent["training_spec"]["path"])
    wall = cfg["session_limits"]["wall_seconds"] if wall_seconds is None else wall_seconds
    if (
        not 30 <= wall <= cfg["session_limits"]["wall_seconds"]
        or maximum_steps is not None
        and maximum_steps < 1
    ):
        raise ValueError("Use the frozen finite session cap")
    deadline = started + wall - 15
    completed: dict[str, dict[str, Any]] = {}
    executed = 0
    tasks = plan(cfg, seeds)
    with nullcontext() if status_only else store.lock():
        for task in tasks:
            req = request_for(task, completed)
            receipt = store.completed(task["key"], req)
            if receipt is None:
                allowance = (
                    (60 if cfg["stage"] == "short_bridge_control" else 240)
                    if task["kind"] == "collect"
                    else 45
                    if task["kind"] == "fit"
                    else 5
                )
                if (
                    status_only
                    or maximum_steps is not None
                    and executed >= maximum_steps
                    or deadline - time.monotonic() < allowance + 15
                ):
                    break
                receipt = execute(
                    q,
                    cfg,
                    parent,
                    score,
                    node,
                    store,
                    task,
                    req,
                    completed,
                    min(deadline, time.monotonic() + allowance),
                )
                executed += 1
            result = receipt["result"]
            if task["kind"] in {"restore", "fit"}:
                model, optimizer, state_id = load_state(q.root / result["state_path"])
                if (
                    state_id != result["state_id"]
                    or model.model_id != result["model_id"]
                    or optimizer.steps != result["optimizer_steps"]
                ):
                    raise ValueError("Saved weights/Adam counter changed")
                if task["kind"] == "restore":
                    if state_id != task["player"]["state_id"]:
                        raise ValueError("Restore reset weights or Adam state")
                elif (
                    optimizer.steps
                    != completed[task["state"]]["result"]["optimizer_steps"]
                    + result["new_optimizer_steps"]
                    or result["new_optimizer_steps"] < 1
                ):
                    raise ValueError("Fit reset/skipped accumulated Adam state")
            completed[task["key"]] = receipt
            sources.update(receipt["sources"])
            receipt_path = store.path(task["key"]) / "done.json"
            sources[str(receipt_path.relative_to(q.root))] = _sha_file(receipt_path)
        done = len(completed) == len(tasks)
        holdout = panels(tasks, completed)
        original = {r["path"]: r["sha256"] for r in cfg["players"]}
        check_sources(q.root, original)
        ending = {}
        for n in (2, 3):
            for arm in cfg["arms"]:
                key = next(
                    (
                        t["key"]
                        for t in reversed(tasks)
                        if t["kind"] in {"restore", "fit"}
                        and t["numerical_seed"] == n
                        and t["arm"] == arm
                        and t["key"] in completed
                    ),
                    None,
                )
                if key:
                    ending[f"{n}-{arm['name']}"] = {**completed[key]["result"], "key": key}
        fits = [t for t in tasks if t["kind"] == "fit" and t["key"] in completed]
        rest = {}
        for arm in cfg["arms"]:
            choices: dict[str, int] = {}
            for t in fits:
                if t["arm"] != arm:
                    continue
                for k, v in completed[t["key"]]["result"]["rest_choices"].items():
                    choices[k] = choices.get(k, 0) + v
            rest[arm["name"]] = choices
        launch = store.workspace / "config-at-launch.json"
        if launch.exists():
            sources[str(launch.relative_to(q.root))] = _sha_file(launch)
        body = {
            "schema_version": "native-rest-exploration-comparison-v1",
            "recipe_path": str(path.relative_to(q.root)),
            "config_id": store.config_id,
            "status": (CONTROL if cfg["stage"] == "short_bridge_control" else COMPLETE)
            if done
            else "paused_between_committed_chunks",
            "completed_units": len(completed),
            "maximum_planned_units": len(tasks),
            "games_recorded": sum(r["result"].get("games_recorded", 0) for r in completed.values()),
            "maximum_planned_games": sum(len(t.get("seeds", [])) for t in tasks),
            "new_units_this_session": executed,
            "optimizer_steps": sum(
                r["result"].get("new_optimizer_steps", 0) for r in completed.values()
            ),
            "starting_optimizer_steps": {
                str(r["numerical_seed"]): r["optimizer_steps"] for r in cfg["players"]
            },
            "ending_states": ending,
            "rest_choices_training": rest,
            "fit_rounds": [
                {"player": t["numerical_seed"], "arm": t["arm"]["name"], "round": t["round"]}
                for t in fits
            ],
            "holdout": holdout,
            "comparisons": comparisons(holdout, seeds) if done else None,
            "initial_weights_and_all_Adam_moments_preserved": True,
            "original_states_unchanged": True,
            "training_treatment": (
                "rest_only_20_percent_uniform_policy_mixture_with_exact_on_policy_derivatives"
            ),
            "evaluation_uniform_weight": 0.0,
            "all_legal_strategic_actions_learnable": True,
            "hand_written_HP_or_upgrade_rewards": False,
            "native_candidate_unchanged": True,
            "game_apps_created": 0,
            "checkpoint_promoted": False,
            "base_readiness_passed": False,
            "adaptive_controller_allowed": False,
            "automatic_extension_follows": False,
            "sources": sources,
            "wall_seconds": time.monotonic() - started,
            "claim_scope": "finite_native_A8_paired_rest_exploration_learning_comparison",
        }
        final = store.workspace / "report.json"
        if final.exists():
            saved = identified(final)
            check_sources(q.root, saved["sources"])
            if not done or any(
                saved[k] != body[k]
                for k in (
                    "config_id",
                    "games_recorded",
                    "ending_states",
                    "comparisons",
                    "rest_choices_training",
                    "optimizer_steps",
                )
            ):
                raise ValueError("Saved exploration result no longer reconstructs")
            return saved
        result = {**body, "report_id": manifest_identifier(body)}
        if not status_only:
            check_sources(q.root, sources)
            number = len(list((store.workspace / "sessions").glob("session-*.json"))) + 1
            atomic_json(store.workspace / f"sessions/session-{number:03d}.json", result)
            if done:
                atomic_json(final, result)
        return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("qualification", type=Path)
    p.add_argument("config", type=Path)
    p.add_argument("--node", type=Path, required=True)
    p.add_argument("--status", action="store_true")
    p.add_argument("--maximum-steps", type=int)
    p.add_argument("--wall-seconds", type=int)
    a = p.parse_args()
    try:
        q = load_engine_qualification_config(a.qualification)
        r = session(
            q,
            q.root / a.config,
            a.node,
            status_only=a.status,
            maximum_steps=a.maximum_steps,
            wall_seconds=a.wall_seconds,
        )
        print(
            json.dumps(
                {
                    k: v
                    for k, v in r.items()
                    if k not in {"sources", "holdout", "fit_rounds", "ending_states"}
                },
                indent=2,
            )
        )
        return 0
    except (ValueError, OSError, TimeoutError) as e:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(e)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
