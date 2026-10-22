"""Restartable bounded full-game comparison of named versus compressed inputs."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_policy_trial import launch
from spireshift.native_structured_execute import execute
from spireshift.native_structured_inputs import load
from spireshift.native_structured_plan import plan, request, summarize


def reserve(task: dict[str, Any], cfg: dict[str, Any]) -> int:
    if task["kind"] == "collect":
        return ((len(task["seeds"]) + 1) // 2) * int(cfg["episode_wall_seconds"]) + 30
    return 140 if task["kind"] == "evaluate" else 180 if task["kind"] == "fit" else 30


def failures(done: dict[str, dict[str, Any]]) -> tuple[int, list[int]]:
    training: dict[tuple[int, str, int], int] = {}
    evaluation: dict[tuple[int, str], int] = {}
    for r in done.values():
        if r["kind"] == "collect":
            k = r["player"], r["arm"], r["round"]
            training[k] = training.get(k, 0) + r["failed_games"]
        if r["kind"] == "evaluate":
            key = r["player"], r["arm"]
            evaluation[key] = evaluation.get(key, 0) + (r["status"] != "terminal")
    values = [*training.values(), *evaluation.values()]
    return sum(values), values


def run(
    root: Path,
    path: Path,
    *,
    status_only: bool = False,
    offline_only: bool = False,
    max_units: int | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    if max_units is not None and (type(max_units) is not int or max_units < 1):
        raise ValueError("Use a positive finite unit bound")
    context = load(root, path, require_control=not status_only)
    cfg, seeds = context["config"], context["seeds"]
    store = ChunkJournal(root, cfg)
    tasks = plan(cfg, seeds)
    final = store.workspace / "report.json"
    planned = cfg["rounds"] * cfg["batch_games"] * 6 + cfg["evaluation_worlds"] * 8
    if final.exists():
        cached = identified(final)
        if cached["config_id"] != store.config_id:
            raise ValueError("Preserve the completed experiment under its original recipe")
        check_sources(root, cached["sources"])
        return cached
    if status_only:
        return {
            "status": "structured_comparison_plan_only",
            "planned_games": planned,
            "planned_units": len(tasks),
            "games_launched": 0,
            "optimizer_steps": 0,
            "original_full_states_and_Adam_read_only": True,
        }
    deadline = (
        started + min(cfg["session_limits"]["wall_seconds"], 240 if offline_only else 900) - 10
    )
    done: dict[str, dict[str, Any]] = {}
    sources = dict(context["sources"])
    native, new, stopped = None, 0, False
    with store.lock():
        for task in tasks:
            req = request(task, done)
            saved = store.completed(task["key"], req)
            if saved is None:
                if (
                    (max_units is not None and new >= max_units)
                    or (offline_only and task["kind"] in {"collect", "evaluate"})
                    or deadline - time.monotonic() < reserve(task, cfg)
                ):
                    break
                if task["kind"] in {"collect", "evaluate"}:
                    if not done["input-checks"]["passed"]:
                        raise ValueError(
                            "Pass varied-input controls before collecting any new game"
                        )
                    if native is None:
                        native = launch(root, context)
                    elif _running_games():
                        raise ValueError("Close STS2 before another isolated native batch")
                execute(root, context, store, task, req, done, deadline - 5, native)
                saved = store.completed(task["key"], req)
                if saved is None:
                    raise ValueError("New structured-input unit was not sealed")
                new += 1
            done[task["key"]] = saved["result"]
            sources.update(saved["sources"])
            receipt = store.path(task["key"]) / "done.json"
            sources[str(receipt.relative_to(root))] = _sha_file(receipt)
            failed, groups = failures(done)
            stopped = failed > 0 if cfg["stage"] == "short_control" else any(n > 2 for n in groups)
            if stopped:
                break
        check_sources(root, sources)
        complete = len(done) == len(tasks) and not stopped
        control = cfg["stage"] == "short_control"
        body = {
            "schema_version": "native-structured-input-comparison-v1",
            "config_id": store.config_id,
            "recipe_path": str(path.relative_to(root)),
            "status": "native_structured_control_complete"
            if complete and control
            else "native_structured_comparison_complete"
            if complete
            else "stopped_at_failure_allowance"
            if stopped
            else "paused_between_sealed_units",
            "planned_units": len(tasks),
            "completed_units": len(done),
            "new_units_this_session": new,
            "planned_games": planned,
            "games_recorded": sum(r["games_recorded"] for r in done.values()),
            "failed_games": failures(done)[0],
            "summary": summarize(cfg, seeds, done),
            "input_checks": done.get("input-checks"),
            "parents": cfg["players"],
            "final_states": [
                r for k, r in done.items() if k.startswith("fit-") and r["round"] == cfg["rounds"]
            ],
            "optimizer_steps_this_experiment": sum(
                r.get("new_optimizer_steps", 0) for r in done.values()
            ),
            "original_full_states_and_Adam_unchanged": True,
            "all_legal_decision_families_learnable": True,
            "ordinary_PPO_uses_own_fresh_sampled_games": True,
            "vocabulary_fit_from_saved_TRAIN_inputs_only": True,
            "vocabulary_id": context["layout"]["vocabulary_id"],
            "credit_predictor_unchanged": True,
            "hand_written_HP_rewards": False,
            "checkpoint_selection": "final_only_no_evaluation_selection",
            "evaluation_behavior": "greedy_combat_sampled_noncombat_v1",
            "full_run_objective": context["score"].evaluation_objective.as_dict(),
            "training_spec_id": context["score"].spec_id,
            "game_apps_created": 0,
            "checkpoint_promoted": False,
            "base_readiness_passed": False,
            "adaptive_controller_allowed": False,
            "automatic_training_follows": False,
            "sources": sources,
            "session_wall_seconds": time.monotonic() - started,
        }
        result = {**body, "report_id": manifest_identifier(body)}
        index = len(list((store.workspace / "sessions").glob("session-*.json"))) + 1
        atomic_json(store.workspace / f"sessions/session-{index:03d}.json", result)
        if complete or stopped:
            atomic_json(final, result)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--offline-only", action="store_true")
    parser.add_argument("--max-units", type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        result = run(
            root,
            root / args.recipe,
            status_only=args.status,
            offline_only=args.offline_only,
            max_units=args.max_units,
        )
        print(
            json.dumps(
                {k: v for k, v in result.items() if k not in {"sources", "input_checks"}}, indent=2
            )
        )
        return int(result["status"] == "stopped_at_failure_allowance")
    except (ValueError, OSError, KeyError, TimeoutError) as error:
        print(json.dumps({"status": "stopped_preserving_structured_evidence", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
