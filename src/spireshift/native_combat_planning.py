"""Finite native combat shooting followed by matched, CPU-charged full-run replay."""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file, load_engine_qualification_config
from spireshift.engine_run import _run_inputs
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.full_run_experience import atomic_json
from spireshift.native_combat_planning_branch import branch
from spireshift.native_combat_planning_config import load
from spireshift.native_combat_planning_data import (
    SEARCH_CPU_CAP,
    cpu_allowance,
    evaluation_tasks,
    search_tasks,
    select_plan,
    summarize,
)
from spireshift.native_combat_planning_policy import CONTRACT, validate_fight
from spireshift.native_combat_teacher_data import INFORMATION
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_turn_teacher_config import load_models
from spireshift.training_objective import load_training_score_spec


def receipt(
    store: ChunkJournal, task: dict[str, Any], sources: dict[str, str]
) -> dict[str, Any] | None:
    saved = store.completed(task["key"], {**task, "scope": INFORMATION, "contract": CONTRACT})
    if saved is None:
        return None
    sources.update(saved["sources"])
    sources[str((store.path(task["key"]) / "done.json").relative_to(store.root))] = _sha_file(
        store.path(task["key"]) / "done.json"
    )
    return dict(saved["result"])


def frozen_selection(
    store: ChunkJournal,
    roots: list[dict[str, Any]],
    items: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    completed: dict[str, dict[str, Any]],
    sources: dict[str, str],
    *,
    write: bool = True,
) -> dict[str, Any]:
    if set(completed) != {t["key"] for t in tasks}:
        raise ValueError("Resolve every combat search attempt before any selected-plan evaluation")
    by_id = {r["root_id"]: r for r in roots}
    groups = []
    for item in items:
        rows = [completed[t["key"]] for t in tasks if t["item_key"] == item["key"]]
        cost = sum(v.get("execution_cpu_seconds", 0.0) for v in rows)
        if not math.isfinite(cost) or cost < 0:
            raise ValueError("Invalid sealed search CPU accounting")
        clean = (
            all(
                v["status"] == "terminal"
                and v["root_reached"]
                and v["combat_complete"]
                and v["native_audit_valid"]
                for v in rows
            )
            and cost <= SEARCH_CPU_CAP
        )
        proposals = []
        if clean:
            turn = identified(store.root / item["turn_plan_path"], "plan_id")
            for sample, v in enumerate(rows):
                plan = identified(store.root / v["plan_path"], "plan_id")
                validate_fight(plan, by_id[item["root_id"]], turn)
                if (
                    plan["plan_id"] != v["plan_id"]
                    or plan["exit"] != v["exit"]
                    or v["sample"] != sample
                ):
                    raise ValueError("Search result differs from its sealed public encounter exit")
                proposals.append(
                    {
                        "sample": sample,
                        "plan_id": plan["plan_id"],
                        "path": v["plan_path"],
                        "combat_survived": plan["exit"]["combat_survived"],
                        "exit_hp": plan["exit"]["exit_hp"],
                    }
                )
        groups.append(
            {
                "item_key": item["key"],
                "blocked": not clean,
                "planning_cpu_seconds": cost,
                "selected": select_plan(proposals) if clean else None,
            }
        )
    body = {
        "schema_version": "native-combat-selection-freeze-v1",
        "config_id": store.config_id,
        "groups": groups,
        "selection_uses_full_run_outcomes": False,
        "planning_cost_charged_to_each_evaluation_without_amortization": True,
        "search_receipts": {
            t["key"]: sources[str((store.path(t["key"]) / "done.json").relative_to(store.root))]
            for t in tasks
        },
    }
    result = {**body, "report_id": manifest_identifier(body)}
    path = store.workspace / "selection.json"
    if path.exists():
        if identified(path) != result:
            raise ValueError(
                "Frozen combat selection, ranking inputs or all-candidate costs changed"
            )
    elif write:
        atomic_json(path, result)
    else:
        raise ValueError("Saved-only verification cannot create missing combat selection")
    sources[str(path.relative_to(store.root))] = _sha_file(path)
    return result


def budget_task(
    task: dict[str, Any], completed: dict[str, dict[str, Any]], budget: float
) -> dict[str, Any]:
    spent = (
        sum(
            v.get("execution_cpu_seconds", 0.0)
            for v in completed.values()
            if v["stage"] == "search" and v["item_key"] == task["item_key"]
        )
        if task["stage"] == "search"
        else task.get("planning_cpu_seconds", 0.0)
    )
    try:
        allowance = cpu_allowance(spent, budget, task["stage"] == "search")
    except ValueError:
        if not math.isfinite(spent) or spent < 0 or budget < SEARCH_CPU_CAP:
            raise
        allowance = 0.0
    return {**task, "cpu_allowance": allowance}


def run(root: Path, path: Path, node: Path, *, status_only: bool = False) -> dict[str, Any]:
    cfg, corpus, roots, items, baseline, sources = load(root, path)
    store = ChunkJournal(root, cfg)
    control = cfg["stage"] == "short_control"
    search = search_tasks(items)
    upper = len(search) + len(items) * cfg["repeats"] + (2 * len(roots) if control else 0)
    final = store.workspace / "report.json"
    if final.exists():
        saved = identified(final)
        if (
            saved["config_id"] != store.config_id
            or saved["status"] != "native_bounded_combat_comparison_complete"
        ):
            raise ValueError("Preserve the saved combat comparison from its original recipe")
        check_sources(root, saved["sources"])
        return saved
    if status_only:
        return {
            "status": "bounded_combat_planning_plan_only",
            "source_worlds": len(roots),
            "initial_turns": len(items),
            "reused_baseline_branches": len(baseline),
            "search_attempts": len(search),
            "native_attempt_upper_bound": upper,
            "new_games": 0,
            "optimizer_steps": 0,
        }
    if node != Path(cfg["node"]) or not node.is_file() or _running_games():
        raise ValueError("Close STS2 and use the frozen runtime before this isolated comparison")
    q = load_engine_qualification_config(root / cfg["qualification"])
    inputs = _run_inputs(q, root / cfg["native_inputs"]["path"])
    score = load_training_score_spec(root / corpus["training_spec"]["path"])
    if (
        q.config_id != cfg["qualification_id"]
        or manifest_identifier(inputs["recipe"]) != cfg["native_inputs"]["id"]
        or inputs["objective"] != score.evaluation_objective.as_dict()
    ):
        raise ValueError(
            "Preserve the exact native environment and terminal-victory compute objective"
        )
    models = load_models(root, corpus)
    by_id, by_item = {r["root_id"]: r for r in roots}, {i["key"]: i for i in items}
    if any(models[r["numerical_seed"]].model_id != r["continuation_model_id"] for r in roots):
        raise ValueError("Preserve both exact original continuation players")
    profile = Path.home() / "Library/Application Support/SlayTheSpire2"
    before = _shared_snapshot(profile)
    started = time.monotonic()
    deadline = started + cfg["session_limits"]["wall_seconds"] - 10
    completed: dict[str, dict[str, Any]] = {}
    blocked: set[str] = set()

    def collect(tasks: list[dict[str, Any]]) -> bool:
        for position, bare in enumerate(tasks, 1):
            task = budget_task(bare, completed, score.evaluation_objective.whole_run_budget)
            value = receipt(store, task, sources)
            if value is None:
                if deadline - time.monotonic() < 130:
                    return False
                request = {**task, "scope": INFORMATION, "contract": CONTRACT}
                target = store.begin(task["key"], request)
                item, r = by_item[task["item_key"]], by_id[task["root_id"]]
                if task["item_key"] in blocked or task["cpu_allowance"] <= 0:
                    value = {
                        "status": "not_attempted_blocked_or_budget",
                        "stage": task["stage"],
                        "item_key": item["key"],
                        "root_id": r["root_id"],
                        "sample": task["sample"],
                        "repeat": task["repeat"],
                        "duplicate": task["duplicate"],
                        "root_reached": False,
                        "combat_complete": False,
                        "native_audit_valid": False,
                        "execution_cpu_seconds": 0.0,
                    }
                else:
                    value = branch(
                        q,
                        cfg,
                        inputs,
                        target,
                        node,
                        r,
                        item,
                        task,
                        models[r["numerical_seed"]],
                        score,
                        deadline,
                    )
                store.commit(task["key"], request, value)
                value = receipt(store, task, sources)
                if value is None:
                    raise ValueError("A completed native combat attempt lost its immutable receipt")
                print(
                    f"Combat {task['stage']}: {position}/{len(tasks)} saved; "
                    f"{value['status']}; optimizer updates 0.",
                    flush=True,
                )
            completed[task["key"]] = value
            if value["status"] == "terminal" and not all(
                value[k] for k in ("root_reached", "combat_complete", "native_audit_valid")
            ):
                raise ValueError(
                    "A terminal combat attempt lacks exact plan replay or native delivery evidence"
                )
            if value["status"] != "terminal":
                blocked.add(task["item_key"])
                if value["status"] == "failed" and not value["root_reached"]:
                    raise ValueError(
                        "Source prefix did not reproduce; preserve its receipt "
                        "before another attempt"
                    )
        return True

    with store.lock():
        complete = collect(search)
        freeze = None
        evaluations = []
        if complete:
            freeze = frozen_selection(store, roots, items, search, completed, sources)
            evaluations = evaluation_tasks(items, freeze["groups"], cfg["repeats"], control)
            complete = collect(evaluations)
        checks = immutable_checks(q, inputs)
        checks["account_profile_unchanged"] = _shared_snapshot(profile) == before
        check_sources(root, sources)
        if not all(checks.values()):
            raise ValueError(
                "Combat planning changed shared native inputs, runtimes or account profile"
            )
        duplicate_checks, baseline_checks = [], []
        for task in evaluations:
            if task["key"] not in completed:
                continue
            value = completed[task["key"]]
            if task["stage"] == "baseline":
                old = baseline[f"{task['item_key']}-r00"]
                equal = value["status"] == "terminal" and value["trace_id"] == old["trace_id"]
                if value["status"] == "terminal" and not equal:
                    raise ValueError(
                        "Fresh baseline control differs from the exact reused baseline trace"
                    )
                baseline_checks.append(equal)
            elif task["duplicate"]:
                original = completed.get(f"evaluate-{task['item_key']}-r00")
                equal = (
                    original is not None
                    and value["status"] == original["status"] == "terminal"
                    and value["trace_id"] == original["trace_id"]
                )
                if original and value["status"] == original["status"] == "terminal" and not equal:
                    raise ValueError("Repeated selected combat plan changed its full public trace")
                duplicate_checks.append(equal)
        summary = summarize(roots, items, baseline, completed, cfg["repeats"]) if complete else None
        values = list(completed.values())
        body = {
            "schema_version": "native-bounded-combat-comparison-v1",
            "recipe_path": str(path.relative_to(root)),
            "config_id": store.config_id,
            "status": "native_bounded_combat_comparison_complete"
            if complete
            else "paused_between_combat_planning_attempts",
            "completed_units": len(completed),
            "native_attempt_upper_bound": upper,
            "native_attempts": sum(
                v["status"] != "not_attempted_blocked_or_budget" for v in values
            ),
            "failed_branches": sum(v["status"] == "failed" for v in values),
            "skipped_branches": sum(
                v["status"] == "not_attempted_blocked_or_budget" for v in values
            ),
            "blocked_initial_turns": sum(g["blocked"] for g in freeze["groups"])
            if freeze
            else None,
            "initial_turns": len(items),
            "source_worlds": len(roots),
            "reused_baseline_branches": len(baseline),
            "all_searches_frozen_before_evaluation": freeze is not None,
            "selection_uses_full_run_outcomes": False,
            "planning_cost_charged_without_amortization": True,
            "selection_id": freeze["report_id"] if freeze else None,
            "summary": summary,
            "baseline_control_traces_match": all(baseline_checks) if baseline_checks else None,
            "duplicate_selected_traces_match": all(duplicate_checks) if duplicate_checks else None,
            "full_states_unchanged": True,
            "checks": checks,
            "sources": sources,
            "information_scope": INFORMATION,
            "privileged_fixed_world_teacher": True,
            "public_belief_search_eligible": False,
            "ordinary_PPO_eligible": False,
            "coarse_credit_baseline_changed": False,
            "learner_HP_rewards_added": False,
            "production_optimizer_steps": 0,
            "checkpoint_promoted": False,
            "adaptive_controller_allowed": False,
            "game_apps_created": 0,
            "automatic_training_follows": False,
            "session_wall_seconds": time.monotonic() - started,
        }
        result = {**body, "report_id": manifest_identifier(body)}
        if complete:
            atomic_json(final, result)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        result = run(root, root / args.recipe, args.node, status_only=args.status)
        print(
            json.dumps(
                {k: v for k, v in result.items() if k not in {"sources", "summary"}}, indent=2
            )
        )
        if result.get("summary"):
            print(
                json.dumps(
                    {
                        k: v
                        for k, v in result["summary"].items()
                        if k not in {"cases", "turn_feedback"}
                    },
                    indent=2,
                )
            )
        return int(
            bool(
                result.get("failed_branches")
                or result.get("skipped_branches")
                or result.get("blocked_initial_turns")
            )
        )
    except (ValueError, KeyError, OSError, TimeoutError) as error:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
