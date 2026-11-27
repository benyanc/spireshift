"""Restartable finite PPO trial; no source checkpoint is modified or auto-promoted."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_native import _running_games
from spireshift.engine_qualification import _sha_file, load_engine_qualification_config
from spireshift.engine_run import _run_inputs
from spireshift.engine_selection_worker import SCRIPT
from spireshift.engine_worker import worker_helpers
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_policy_trial_execute import execute
from spireshift.native_policy_trial_inputs import control_sources, load
from spireshift.native_policy_trial_plan import plan, request, summary


def launch(root: Path, context: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    cfg = context["config"]
    if _running_games() or not Path(cfg["node"]).is_file():
        raise ValueError("Close STS2 before new policy games; completed units remain saved")
    q = load_engine_qualification_config(root / cfg["qualification"])
    inputs = _run_inputs(q, root / cfg["native_inputs"]["path"])
    if (
        q.config_id != cfg["qualification_id"]
        or manifest_identifier(inputs["recipe"]) != cfg["native_inputs"]["id"]
        or inputs["objective"] != context["score"].evaluation_objective.as_dict()
        or worker_helpers(root, SCRIPT) != cfg["helpers_sha256"]
    ):
        raise ValueError(
            "The qualified actual-engine bridge, helpers or full-run objective changed"
        )
    return q, inputs


def reserve(task: dict[str, Any], cfg: dict[str, Any]) -> int:
    if task["kind"] == "collect":
        return ((len(task["seeds"]) + 1) // 2) * int(cfg["episode_wall_seconds"]) + 45
    return 135 if task["kind"] == "evaluate" else 45


def failures(done: dict[str, dict[str, Any]]) -> tuple[int, dict[tuple[int, int], int]]:
    groups: dict[tuple[int, int], int] = {}
    total = 0
    for r in done.values():
        if r["kind"] == "evaluate":
            total += r["status"] != "terminal"
        if r["kind"] == "collect":
            key = r["player"], r["round"]
            groups[key] = groups.get(key, 0) + r["summary"]["failed_games"]
            total += r["summary"]["failed_games"]
    return total, groups


def run(
    root: Path,
    path: Path,
    *,
    status_only: bool = False,
    offline_only: bool = False,
    max_units: int | None = None,
) -> dict[str, Any]:
    if max_units is not None and (type(max_units) is not int or max_units < 1):
        raise ValueError("Use a positive bound on newly executed units")
    started = time.monotonic()
    context = load(root, path)
    cfg, seeds = context["config"], context["seeds"]
    store = ChunkJournal(root, cfg)
    tasks = plan(cfg, seeds)
    final = store.workspace / "report.json"
    if final.exists():
        cached = identified_report(final, store.config_id)
        check_sources(root, cached["sources"])
        return cached
    if status_only:
        return {
            "status": "policy_comparison_plan_only",
            "planned_units": len(tasks),
            "training_games": cfg["rounds"] * cfg["batch_games"] * 2,
            "evaluation_games": cfg["evaluation_worlds"] * 4,
            "original_models_and_all_Adam_moments_read_only": True,
            "games_launched": 0,
            "optimizer_updates": 0,
        }
    sources = dict(context["sources"])
    if cfg["stage"] != "short_control":
        sources.update(control_sources(root, cfg))
    deadline = (
        started
        + (
            min(240, cfg["session_limits"]["wall_seconds"])
            if offline_only
            else cfg["session_limits"]["wall_seconds"]
        )
        - 10
    )
    native = None
    done: dict[str, dict[str, Any]] = {}
    new = 0
    stopped = False
    with store.lock():
        for task in tasks:
            req = request(task, done)
            saved = store.completed(task["key"], req)
            if saved is None:
                if (
                    deadline - time.monotonic() < reserve(task, cfg)
                    or (max_units is not None and new >= max_units)
                    or (offline_only and task["kind"] in {"collect", "evaluate"})
                ):
                    break
                if task["kind"] in {"collect", "evaluate"}:
                    if not done["policy-update-checks"]["passed"]:
                        raise ValueError("Pass signed-gradient/isolation checks before any games")
                    if native is None:
                        native = launch(root, context)
                    elif _running_games():
                        raise ValueError("A game appeared between closed policy chunks")
                execute(root, context, store, task, req, done, deadline - 5, native)
                saved = store.completed(task["key"], req)
                if saved is None:
                    raise ValueError("New policy unit did not seal its result")
                new += 1
            result = saved["result"]
            done[task["key"]] = result
            sources.update(saved["sources"])
            commit_path = str((store.path(task["key"]) / "done.json").relative_to(root))
            sources[commit_path] = _sha_file(root / commit_path)
            total, groups = failures(done)
            evaluation_failures = sum(
                r["kind"] == "evaluate" and r["status"] != "terminal" for r in done.values()
            )
            stopped = (
                total > 0
                if cfg["stage"] == "short_control"
                else evaluation_failures > 2 or any(n > 2 for n in groups.values())
            )
            if stopped:
                break
            if (
                result["kind"] == "evaluate"
                and sum(r["kind"] == "evaluate" for r in done.values()) % 8 == 0
            ):
                evaluated = [r for r in done.values() if r["kind"] == "evaluate"]
                clean = [r for r in evaluated if r["status"] == "terminal"]
                print(
                    f"Fresh comparison: {len(evaluated)}/{cfg['evaluation_worlds'] * 4} games; "
                    f"best floor {max((r['maximum_floor'] for r in clean), default=0)}; "
                    f"wins {sum(r['victory'] for r in clean)}; failures {evaluation_failures}.",
                    flush=True,
                )
        check_sources(root, sources)
        complete = len(done) == len(tasks) and not stopped
        control = cfg["stage"] == "short_control"
        body = {
            "schema_version": "native-policy-update-comparison-v1",
            "config_id": store.config_id,
            "recipe_path": str(path.relative_to(root)),
            "status": "native_policy_update_control_complete"
            if complete and control
            else "native_policy_update_comparison_complete"
            if complete
            else "policy_update_stopped_failure_allowance"
            if stopped
            else "paused_between_sealed_units",
            "planned_units": len(tasks),
            "completed_units": len(done),
            "new_units_this_session": new,
            "planned_games": cfg["rounds"] * cfg["batch_games"] * 2 + cfg["evaluation_worlds"] * 4,
            "games_recorded": sum(r["games_recorded"] for r in done.values()),
            "failed_games": failures(done)[0],
            "summary": summary(cfg, seeds, done),
            "policy_checks": done.get("policy-update-checks"),
            "parents": cfg["players"],
            "final_states": [
                r
                for k, r in done.items()
                if k in {f"fit-p{p}-r{cfg['rounds']:02d}" for p in (2, 3)}
            ],
            "optimizer_steps_this_experiment": sum(
                r.get("new_optimizer_steps", 0) for r in done.values()
            ),
            "original_full_states_and_Adam_unchanged": True,
            "prediction_only_optimizer_used_for_actor_updates": False,
            "ordinary_PPO_training_requires_own_fresh_sampled_games": True,
            "all_legal_decision_families_learnable": True,
            "checkpoint_selection": cfg["checkpoint_selection"],
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


def identified_report(path: Path, config_id: str) -> dict[str, Any]:
    from spireshift.engine_learning import identified

    result = identified(path)
    if result["config_id"] != config_id:
        raise ValueError("Preserve a saved result under its original exact recipe")
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
                {k: v for k, v in result.items() if k not in {"sources", "parents"}}, indent=2
            )
        )
        return 1 if result["status"] == "policy_update_stopped_failure_allowance" else 0
    except (OSError, ValueError, KeyError, TimeoutError) as error:
        print(json.dumps({"status": "stopped_preserving_policy_evidence", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
