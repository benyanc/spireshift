"""Finite restartable experience-budget comparison; no automatic promotion or scaling."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games
from spireshift.engine_qualification import _sha_file, load_engine_qualification_config
from spireshift.engine_run import _run_inputs
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_experience_execute import execute
from spireshift.native_experience_inputs import load
from spireshift.native_experience_plan import plan, request, summarize
from spireshift.native_structured_comparison import failures


def reserve(task: dict[str, Any], cfg: dict[str, Any]) -> int:
    control = cfg["stage"] == "short_control"
    if task["kind"] == "collect":
        return ((len(task["seeds"]) + 1) // 2) * (
            45 if control else cfg["episode_wall_seconds"]
        ) + 25
    return (
        (60 if control else 140)
        if task["kind"] == "evaluate"
        else (25 if control else 300)
        if task["kind"] == "fit"
        else 20
    )


def launch(root: Path, context: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    cfg = context["config"]
    if _running_games() or not Path(cfg["node"]).is_file():
        raise ValueError("Close STS2 before new experience chunks; completed evidence stays saved")
    q = load_engine_qualification_config(root / cfg["qualification"])
    inputs = _run_inputs(q, root / cfg["native_inputs"]["path"])
    if (
        q.config_id != cfg["qualification_id"]
        or manifest_identifier(inputs["recipe"]) != cfg["native_inputs"]["id"]
        or inputs["objective"] != context["score"].evaluation_objective.as_dict()
    ):
        raise ValueError("Frozen engine, native inputs or full-run objective changed")
    return q, inputs


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
        raise ValueError("Use a finite positive unit bound")
    context = load(root, path, require_control=not status_only)
    cfg, seeds = context["config"], context["seeds"]
    journal = ChunkJournal(root, cfg)
    tasks = plan(cfg, seeds)
    planned = cfg["rounds"] * sum(cfg["batch_sizes"].values()) * 2 + cfg["evaluation_worlds"] * 6
    final = journal.workspace / "report.json"
    if final.exists():
        cached = identified(final)
        if cached["config_id"] != journal.config_id:
            raise ValueError("Preserve a completed experience experiment under its recipe")
        check_sources(root, cached["sources"])
        return cached
    if status_only:
        return {
            "status": "experience_comparison_plan_only",
            "planned_games": planned,
            "planned_units": len(tasks),
            "games_launched": 0,
            "optimizer_steps": 0,
        }
    deadline = (
        started + min(cfg["session_limits"]["wall_seconds"], 240 if offline_only else 900) - 10
    )
    done: dict[str, dict[str, Any]] = {}
    sources = dict(context["sources"])
    native, new, stopped = None, 0, False
    with journal.lock():
        for task in tasks:
            req = request(task, done)
            saved = journal.completed(task["key"], req)
            if saved is None:
                if (
                    (max_units is not None and new >= max_units)
                    or (offline_only and task["kind"] in {"collect", "evaluate"})
                    or deadline - time.monotonic() < reserve(task, cfg)
                ):
                    break
                if task["kind"] in {"collect", "evaluate"}:
                    if not done["policy-checks"]["passed"]:
                        raise ValueError("Policy checks must pass before new experience")
                    if native is None:
                        native = launch(root, context)
                    elif _running_games():
                        raise ValueError("STS2 appeared between closed experience chunks")
                execute(root, context, journal, task, req, done, deadline - 5, native)
                saved = journal.completed(task["key"], req)
                if saved is None:
                    raise ValueError("Experience unit did not seal")
                new += 1
            done[task["key"]] = saved["result"]
            sources.update(saved["sources"])
            receipt = journal.path(task["key"]) / "done.json"
            sources[str(receipt.relative_to(root))] = _sha_file(receipt)
            failed, groups = failures(done)
            stopped = failed > 0 if cfg["stage"] == "short_control" else any(n > 2 for n in groups)
            if stopped:
                break
        check_sources(root, sources)
        complete = len(done) == len(tasks) and not stopped
        control = cfg["stage"] == "short_control"
        body = {
            "schema_version": "native-experience-budget-comparison-v1",
            "config_id": journal.config_id,
            "recipe_path": str(path.relative_to(root)),
            "status": "native_experience_control_complete"
            if complete and control
            else "native_experience_comparison_complete"
            if complete
            else "stopped_at_failure_allowance"
            if stopped
            else "paused_between_sealed_units",
            "planned_games": planned,
            "planned_units": len(tasks),
            "completed_units": len(done),
            "new_units_this_session": new,
            "games_recorded": sum(r["games_recorded"] for r in done.values()),
            "failed_games": failures(done)[0],
            "summary": summarize(cfg, seeds, done),
            "final_states": [
                r for r in done.values() if r["kind"] == "fit" and r["round"] == cfg["rounds"]
            ],
            "optimizer_steps_this_experiment": sum(
                r.get("new_optimizer_steps", 0) for r in done.values()
            ),
            "original_weights_and_all_Adam_moments_unchanged": True,
            "new_initial_environment_metadata_only_numeric_weights_and_Adam_exact": True,
            "all_current_legal_families_learnable": True,
            "credit_predictor_unchanged": True,
            "evaluation_behavior": "greedy_combat_sampled_noncombat_v1",
            "checkpoint_selection": "all_finals_before_evaluation_no_selection",
            "training_treatment": (
                "four_times_fresh_games_per_update_round_not_equal_training_compute"
            ),
            "data_variety_alone_causally_isolated": False,
            "full_run_objective": context["score"].evaluation_objective.as_dict(),
            "training_spec_id": context["score"].spec_id,
            "sources": sources,
            "session_wall_seconds": time.monotonic() - started,
            "game_apps_created": 0,
            "checkpoint_promoted": False,
            "base_readiness_passed": False,
            "adaptive_controller_allowed": False,
            "automatic_training_follows": False,
        }
        result = {**body, "report_id": manifest_identifier(body)}
        index = len(list((journal.workspace / "sessions").glob("session-*.json"))) + 1
        atomic_json(journal.workspace / f"sessions/session-{index:03d}.json", result)
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
        print(json.dumps({k: v for k, v in result.items() if k != "sources"}, indent=2))
        return int(result["status"] == "stopped_at_failure_allowance")
    except (OSError, ValueError, KeyError, TimeoutError) as error:
        print(json.dumps({"status": "stopped_preserving_experience_evidence", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
