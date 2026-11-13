"""Finite outcome-blind complete-turn proposals, then sealed native comparisons."""

from __future__ import annotations

import argparse
import json
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
from spireshift.native_combat_teacher_data import INFORMATION
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_turn_teacher_branch import branch
from spireshift.native_turn_teacher_config import load, load_models
from spireshift.native_turn_teacher_data import (
    comparison_tasks,
    freeze_candidates,
    proposal_tasks,
    turn_lesson,
)
from spireshift.native_turn_teacher_policy import CONTRACT, validate_plan
from spireshift.training_objective import load_training_score_spec


def receipt(
    store: ChunkJournal, task: dict[str, Any], sources: dict[str, str]
) -> dict[str, Any] | None:
    saved = store.completed(task["key"], {**task, "scope": INFORMATION, "contract": CONTRACT})
    if saved is not None:
        sources.update(saved["sources"])
        sources[str((store.path(task["key"]) / "done.json").relative_to(store.root))] = _sha_file(
            store.path(task["key"]) / "done.json"
        )
        return dict(saved["result"])
    return None


def freeze(
    store: ChunkJournal,
    roots: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    completed: dict[str, dict[str, Any]],
    blocked: set[str],
    sources: dict[str, str],
    *,
    write: bool = True,
) -> dict[str, Any]:
    if set(completed) != {t["key"] for t in tasks}:
        raise ValueError("Every proposal must be resolved before any scored continuation")
    groups = []
    for r in roots:
        proposals = []
        if r["root_id"] not in blocked:
            for t in tasks:
                if t["root_id"] != r["root_id"]:
                    continue
                v = completed[t["key"]]
                if (
                    v["status"] != "terminal"
                    or not v["turn_complete"]
                    or not v["native_audit_valid"]
                ):
                    raise ValueError("Incomplete proposals cannot become frozen turn candidates")
                plan = identified(store.root / v["plan_path"], "plan_id")
                validate_plan(plan, r)
                if plan["plan_id"] != v["plan_id"] or (
                    t["first_action"] is not None
                    and plan["steps"][0]["action_index"] != t["first_action"]
                ):
                    raise ValueError("Candidate proposal differs from its declared first action")
                if (
                    t["first_action"] is None
                    and plan["steps"][0]["action_index"] != r["reference_action"]
                ):
                    raise ValueError("The reference turn must start with the frozen greedy choice")
                proposals.append(
                    {
                        "first_action": t["first_action"],
                        "plan_id": v["plan_id"],
                        "plan_path": v["plan_path"],
                        "proposal_key": t["key"],
                    }
                )
        groups.append(
            {
                "root_id": r["root_id"],
                "blocked": r["root_id"] in blocked,
                "candidates": freeze_candidates(r, proposals) if proposals else [],
            }
        )
    body = {
        "schema_version": "native-complete-turn-candidate-set-v1",
        "config_id": store.config_id,
        "roots": groups,
        "selection_uses_proposal_outcomes": False,
        "selection": "ordered_exact_public_trace_deduplication_only",
        "proposal_receipts": {
            t["key"]: sources[str((store.path(t["key"]) / "done.json").relative_to(store.root))]
            for t in tasks
        },
    }
    result = {**body, "report_id": manifest_identifier(body)}
    path = store.workspace / "candidate-set.json"
    if path.exists():
        if identified(path) != result:
            raise ValueError("Frozen turn candidates or their proposal receipts changed")
    elif write:
        atomic_json(path, result)
    else:
        raise ValueError("Saved-only audit cannot create a missing candidate freeze")
    sources[str(path.relative_to(store.root))] = _sha_file(path)
    return result


def run(root: Path, path: Path, node: Path, *, status_only: bool = False) -> dict[str, Any]:
    cfg, corpus, roots, sources = load(root, path)
    store = ChunkJournal(root, cfg)
    proposals = proposal_tasks(roots)
    control = cfg["stage"] == "short_control"
    upper = len(proposals) * (1 + cfg["repeats"]) + (len(roots) if control else 0)
    final = store.workspace / "report.json"
    if final.exists():
        saved = identified(final)
        if (
            saved["config_id"] != store.config_id
            or saved["status"] != "native_complete_turn_teacher_complete"
        ):
            raise ValueError("Preserve a completed result from another complete-turn recipe")
        check_sources(root, saved["sources"])
        return saved
    if status_only:
        return {
            "status": "complete_turn_teacher_plan_only",
            "roots": len(roots),
            "planned_proposals": len(proposals),
            "native_branch_upper_bound": upper,
            "new_games": 0,
            "optimizer_steps": 0,
            "information_scope": INFORMATION,
            "proposal_outcomes_used_for_selection": False,
        }
    if node != Path(cfg["node"]) or not node.is_file() or _running_games():
        raise ValueError("Close STS2 and use the exact frozen Node runtime")
    q = load_engine_qualification_config(root / cfg["qualification"])
    if q.config_id != cfg["qualification_id"]:
        raise ValueError("The native qualification identity changed")
    inputs = _run_inputs(q, root / cfg["native_inputs"]["path"])
    score = load_training_score_spec(root / corpus["training_spec"]["path"])
    if (
        manifest_identifier(inputs["recipe"]) != cfg["native_inputs"]["id"]
        or inputs["objective"] != score.evaluation_objective.as_dict()
    ):
        raise ValueError(
            "Preserve the native host, terminal objective and whole-run compute budget"
        )
    models = load_models(root, corpus)
    if any(models[r["numerical_seed"]].model_id != r["continuation_model_id"] for r in roots):
        raise ValueError("Turn root continuation weights differ")
    profile = Path.home() / "Library/Application Support/SlayTheSpire2"
    before = _shared_snapshot(profile)
    started = time.monotonic()
    deadline = started + cfg["session_limits"]["wall_seconds"] - 10
    by_id = {r["root_id"]: r for r in roots}
    completed: dict[str, dict[str, Any]] = {}
    blocked: set[str] = set()
    comparisons: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []

    def collect(tasks: list[dict[str, Any]]) -> bool:
        for task_index, task in enumerate(tasks, 1):
            value = receipt(store, task, sources)
            if value is None:
                if deadline - time.monotonic() < 130:
                    return False
                request = {**task, "scope": INFORMATION, "contract": CONTRACT}
                target = store.begin(task["key"], request)
                r = by_id[task["root_id"]]
                value = (
                    {
                        "status": "not_attempted_root_blocked",
                        "root_id": r["root_id"],
                        "stage": task["stage"],
                        "plan_id": task.get("plan_id"),
                        "repeat": task["repeat"],
                        "duplicate_control": task["duplicate_control"],
                        "turn_complete": False,
                        "root_reached": False,
                        "native_audit_valid": False,
                    }
                    if r["root_id"] in blocked
                    else branch(
                        q,
                        cfg,
                        inputs,
                        target,
                        node,
                        r,
                        task,
                        models[r["numerical_seed"]],
                        score,
                        deadline,
                    )
                )
                store.commit(task["key"], request, value)
                value = receipt(store, task, sources)
                if value is None:
                    raise ValueError("New turn branch lost its immutable commit")
                print(
                    f"Complete-turn {task['stage']}: {task_index}/{len(tasks)} saved branches; "
                    f"{value['status']}; optimizer updates 0.",
                    flush=True,
                )
            completed[task["key"]] = value
            if value["status"] == "terminal" and not (
                value["root_reached"] and value["turn_complete"] and value["native_audit_valid"]
            ):
                raise ValueError(
                    "Terminal turn branch lacks its exact intervention or delivery audit"
                )
            if value["status"] == "failed":
                blocked.add(task["root_id"])
                if not value["root_reached"]:
                    raise ValueError(
                        "Complete-turn source prefix replay failed; preserve this attempt"
                    )
        return True

    with store.lock():
        proposals_complete = collect(proposals)
        if proposals_complete:
            frozen = freeze(store, roots, proposals, completed, blocked, sources)
            groups = frozen["roots"]
            comparisons = comparison_tasks(roots, groups, cfg["repeats"], control)
            complete = collect(comparisons)
        else:
            complete = False
        checks = immutable_checks(q, inputs)
        checks["account_profile_unchanged"] = _shared_snapshot(profile) == before
        check_sources(root, sources)
        if not all(checks.values()):
            raise ValueError("Complete-turn teacher changed shared game, runtime, SDK or account")
        cases = (
            [
                turn_lesson(
                    r,
                    group["candidates"],
                    [
                        completed[t["key"]]
                        for t in comparisons
                        if t["root_id"] == r["root_id"] and t["key"] in completed
                    ],
                    cfg["repeats"],
                )
                for r, group in zip(roots, groups, strict=True)
            ]
            if complete
            else []
        )
        duplicates = []
        for task in comparisons:
            if task["duplicate_control"] and task["key"] in completed:
                other = next(
                    t
                    for t in comparisons
                    if t["root_id"] == task["root_id"]
                    and t["plan_id"] == task["plan_id"]
                    and t["repeat"] == 0
                    and not t["duplicate_control"]
                )
                a, b = completed[task["key"]], completed[other["key"]]
                equal = a.get("status") == b.get("status") == "terminal" and a.get(
                    "trace_id"
                ) == b.get("trace_id")
                if a["status"] == b["status"] == "terminal" and not equal:
                    raise ValueError(
                        "Repeated complete turn did not reproduce the full public trace"
                    )
                duplicates.append(equal)
        values = list(completed.values())
        scored = [v for v in values if v["stage"] == "comparison" and not v["duplicate_control"]]
        body = {
            "schema_version": "native-complete-turn-teacher-v1",
            "recipe_path": str(path.relative_to(root)),
            "config_id": store.config_id,
            "status": "native_complete_turn_teacher_complete"
            if complete
            else "paused_between_complete_turn_branches",
            "completed_units": len(completed),
            "planned_proposals": len(proposals),
            "proposals_frozen": proposals_complete,
            "planned_comparison_branches": len(comparisons) if proposals_complete else None,
            "native_branch_upper_bound": upper,
            "native_attempts": sum(v["status"] != "not_attempted_root_blocked" for v in values),
            "failed_branches": sum(v["status"] == "failed" for v in values),
            "skipped_branches": sum(v["status"] == "not_attempted_root_blocked" for v in values),
            "blocked_source_roots": len(blocked),
            "distinct_source_hidden_worlds": len(roots),
            "completed_source_comparisons": sum(c["comparison_complete"] for c in cases),
            "candidate_plans": sum(len(g["candidates"]) for g in groups),
            "proposal_outcomes_used_for_selection": False,
            "all_candidates_frozen_before_scored_branches": proposals_complete,
            "policy_streams_per_plan": cfg["repeats"],
            "independent_hidden_worlds_per_root": 1,
            "duplicate_public_traces_identical": all(duplicates) if duplicates else None,
            "all_turn_boundaries_replayed_exactly": complete
            and not blocked
            and all(v["turn_complete"] for v in values),
            "full_run_wins_in_comparison_samples": sum(v.get("victory", False) for v in scored),
            "turn_decisions_in_comparison_samples": sum(v.get("turn_decisions", 0) for v in scored),
            "nested_selection_decisions_in_comparison_samples": sum(
                v.get("nested_selection_decisions", 0) for v in scored
            ),
            "information_scope": INFORMATION,
            "policy_contract": CONTRACT,
            "privileged_fixed_world_teacher": True,
            "student_inputs_public_only": True,
            "ordinary_PPO_eligible": False,
            "public_belief_search_eligible": False,
            "production_optimizer_steps": 0,
            "original_full_states_unchanged": True,
            "game_apps_created": 0,
            "checks": checks,
            "cases": cases,
            "sources": sources,
            "admitted_exploratory_preferences": sum(
                p["admitted_exploratory_preference"] for c in cases for p in c["preferences"]
            ),
            "coarse_credit_baseline_changed": False,
            "checkpoint_promoted": False,
            "adaptive_controller_allowed": False,
            "automatic_training_follows": False,
            "session_wall_seconds": time.monotonic() - started,
        }
        report = {**body, "report_id": manifest_identifier(body)}
        if complete:
            atomic_json(final, report)
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        report = run(root, root / args.recipe, args.node, status_only=args.status)
        print(
            json.dumps({k: v for k, v in report.items() if k not in {"cases", "sources"}}, indent=2)
        )
        return int(bool(report.get("failed_branches")))
    except (ValueError, KeyError, OSError, TimeoutError) as error:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
