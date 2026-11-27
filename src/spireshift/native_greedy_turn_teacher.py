"""Bounded fresh sources, frozen whole-turn proposals, then greedy-continuation lessons."""

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
from spireshift.native_greedy_turn_branch import branch
from spireshift.native_greedy_turn_config import load
from spireshift.native_greedy_turn_data import (
    budget_task,
    freeze_plans,
    freeze_roots,
    lessons,
    matched_draws,
    proposal_tasks,
    scored_tasks,
    source_tasks,
)
from spireshift.native_greedy_turn_policy import CONTRACT

COMPLETE = "native_greedy_turn_teacher_complete"


def receipt(
    store: ChunkJournal, task: dict[str, Any], sources: dict[str, str]
) -> dict[str, Any] | None:
    saved = store.completed(task["key"], {**task, "scope": INFORMATION, "contract": CONTRACT})
    if saved is None:
        return None
    value = saved["result"]
    if (
        value["stage"] != task["stage"]
        or value["seed_id"] != task["seed"]["id"]
        or value["numerical_seed"] != task["seed"]["numerical_seed"]
        or (value["stage"] != "source" and value["root_id"] != task["root_id"])
        or (
            value["status"] == "terminal"
            and not all(
                value[k] for k in ("native_audit_valid", "inference_audit_valid", "turn_complete")
            )
        )
        or value["planning_cpu_seconds"] != task["planning_cpu_seconds"]
    ):
        raise ValueError("Saved teacher cell, cost or delivery/inference audit changed")
    sources.update(saved["sources"])
    sources[str((store.path(task["key"]) / "done.json").relative_to(store.root))] = _sha_file(
        store.path(task["key"]) / "done.json"
    )
    return dict(value)


def skipped(task: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "status": reason,
        "stage": task["stage"],
        "seed_id": task["seed"]["id"],
        "numerical_seed": task["seed"]["numerical_seed"],
        "root_id": task.get("root_id"),
        "plan_id": task.get("plan_id"),
        "root_reached": False,
        "turn_complete": False,
        "native_audit_valid": False,
        "inference_audit_valid": False,
        "repeat": task.get("repeat"),
        "duplicate_control": task.get("duplicate_control", False),
        "reference": task.get("reference", False),
        "execution_cpu_seconds": 0.0,
        "planning_cpu_seconds": task["planning_cpu_seconds"],
        "training_return": None,
    }


def duplicates(tasks: list[dict[str, Any]], completed: dict[str, dict[str, Any]]) -> bool | None:
    results = []
    for task in tasks:
        if not task["duplicate_control"] or task["key"] not in completed:
            continue
        other = next(
            t
            for t in tasks
            if not t["duplicate_control"]
            and t["root_id"] == task["root_id"]
            and t["plan_id"] == task["plan_id"]
            and t["repeat"] == 0
        )
        a, b = completed[task["key"]], completed[other["key"]]
        equal = a["status"] == b["status"] == "terminal" and a["trace_id"] == b["trace_id"]
        if a["status"] == b["status"] == "terminal" and not equal:
            raise ValueError("Exact greedy teacher duplicate changed its public trace")
        results.append(equal)
    return all(results) if results else None


def run(root: Path, path: Path, node: Path, *, status_only: bool = False) -> dict[str, Any]:
    started = time.monotonic()
    cfg, seeds, models, score, sources = load(root, path)
    store = ChunkJournal(root, cfg)
    control = cfg["stage"] == "short_control"
    upper = 16 if control else 8 + 8 * 13 * 9
    final = store.workspace / "report.json"
    if final.exists():
        saved = identified(final)
        if saved["config_id"] != store.config_id or saved["status"] not in {
            COMPLETE,
            COMPLETE + "_with_gaps",
        }:
            raise ValueError("Preserve the saved teacher under its original recipe")
        check_sources(root, saved["sources"])
        return saved
    if status_only:
        return {
            "status": "greedy_turn_teacher_plan_only",
            "fresh_source_worlds": len(seeds),
            "fixed_players": 2,
            "native_attempt_upper_bound": upper,
            "continuation_streams_per_plan": cfg["repeats"],
            "new_games": 0,
            "optimizer_steps": 0,
        }
    if node != Path(cfg["node"]) or not node.is_file() or _running_games():
        raise ValueError("Close STS2 and use the pinned runtime before the isolated teacher")
    q = load_engine_qualification_config(root / cfg["qualification"])
    inputs = _run_inputs(q, root / cfg["native_inputs"]["path"])
    if (
        q.config_id != cfg["qualification_id"]
        or manifest_identifier(inputs["recipe"]) != cfg["native_inputs"]["id"]
        or inputs["objective"] != score.evaluation_objective.as_dict()
    ):
        raise ValueError("Preserve actual-engine A8 inputs and the full-run victory/CPU objective")
    profile = Path.home() / "Library/Application Support/SlayTheSpire2"
    before = _shared_snapshot(profile)
    deadline = started + cfg["session_limits"]["wall_seconds"] - 10
    completed: dict[str, dict[str, Any]] = {}
    roots: list[dict[str, Any]] = []
    blocked: set[str] = set()
    new = 0

    def collect(planned: list[dict[str, Any]]) -> bool:
        nonlocal new
        by_id = {r["root_id"]: r for r in roots}
        for index, bare in enumerate(planned, 1):
            task = budget_task(bare, completed)
            value = receipt(store, task, sources)
            if value is None:
                if deadline - time.monotonic() < 135:
                    return False
                request = {**task, "scope": INFORMATION, "contract": CONTRACT}
                target = store.begin(task["key"], request)
                value = (
                    skipped(task, "not_attempted_root_blocked")
                    if task.get("root_id") in blocked
                    else skipped(task, "not_attempted_proposal_CPU_exhausted")
                    if task["cpu_allowance"] <= 0
                    else branch(
                        q,
                        cfg,
                        inputs,
                        target,
                        node,
                        task,
                        models[task["seed"]["numerical_seed"]],
                        score,
                        by_id.get(task.get("root_id", "")),
                        deadline,
                    )
                )
                store.commit(task["key"], request, value)
                value = receipt(store, task, sources)
                if value is None:
                    raise ValueError("A new teacher attempt lost its sealed commit")
                new += 1
            completed[task["key"]] = value
            if value["status"] != "terminal" and task["stage"] != "source":
                blocked.add(task["root_id"])
                if value["status"] == "failed" and not value["root_reached"]:
                    raise ValueError(
                        "Frozen source prefix failed replay; preserve the uncertain comparison"
                    )
            if sum(v["status"] == "failed" for v in completed.values()) > (0 if control else 2):
                raise ValueError(
                    "Teacher failed-game allowance exceeded; preserve completed attempts"
                )
            if index % (1 if task["stage"] == "source" else 8) == 0 or index == len(planned):
                print(
                    f"Greedy-turn {task['stage']}: {index}/{len(planned)} saved; "
                    f"failures {sum(v['status'] == 'failed' for v in completed.values())}; "
                    "optimizer updates 0.",
                    flush=True,
                )
        return True

    with store.lock():
        source_complete = collect(source_tasks(seeds))
        source_set: dict[str, Any] | None = None
        frozen: dict[str, Any] | None = None
        proposals: list[dict[str, Any]] = []
        comparisons: list[dict[str, Any]] = []
        complete = False
        if source_complete:
            source_set, roots = freeze_roots(store, source_tasks(seeds), completed, sources)
            proposals = proposal_tasks(roots, control)
            if collect(proposals):
                frozen = freeze_plans(store, roots, proposals, completed, sources, control)
                blocked.update(g["root_id"] for g in frozen["roots"] if g["blocked"])
                comparisons = scored_tasks(roots, frozen, cfg["repeats"], control)
                complete = collect(comparisons)
        tables = (
            lessons(roots, frozen, completed, cfg["repeats"])
            if complete and frozen is not None
            else []
        )
        checks = immutable_checks(q, inputs)
        checks["account_profile_unchanged"] = _shared_snapshot(profile) == before
        check_sources(root, sources)
        if not all(checks.values()):
            raise ValueError("Teacher changed shared game inputs or the real account profile")
        matching = matched_draws(root, completed)
        duplicate = duplicates(comparisons, completed)
        values = list(completed.values())
        failed = sum(v["status"] == "failed" for v in values)
        skips = sum(v["status"].startswith("not_attempted") for v in values)
        unavailable = len(seeds) - len(roots) if source_complete else None
        gaps = bool(failed or skips or unavailable or blocked)
        body = {
            "schema_version": "native-greedy-turn-teacher-v1",
            "recipe_path": str(path.relative_to(root)),
            "config_id": store.config_id,
            "status": COMPLETE + ("_with_gaps" if gaps else "")
            if complete
            else "paused_between_greedy_teacher_attempts",
            "completed_units": len(completed),
            "new_units_this_session": new,
            "native_attempt_upper_bound": upper,
            "native_attempts": sum(not v["status"].startswith("not_attempted") for v in values),
            "planned_source_worlds": len(seeds),
            "source_stage_complete": source_complete,
            "usable_source_roots": len(roots),
            "unavailable_source_worlds": unavailable,
            "source_set_id": source_set["report_id"] if source_set else None,
            "source_world_denominator": source_set["sources"] if source_set else [],
            "candidate_set_id": frozen["report_id"] if frozen else None,
            "planned_proposals": len(proposals) if source_complete else None,
            "planned_comparison_branches": len(comparisons) if frozen else None,
            "failed_branches": failed,
            "skipped_branches": skips,
            "blocked_source_roots": len(blocked),
            "completed_source_comparisons": sum(c["comparison_complete"] for c in tables),
            "candidate_plans": sum(len(g["candidates"]) for g in frozen["roots"]) if frozen else 0,
            "duplicate_public_traces_identical": duplicate,
            "noncombat_matching": matching,
            "all_turns_frozen_before_scored_comparisons": frozen is not None,
            "source_roots_sealed_before_later_outcomes": True,
            "proposal_outcomes_used_for_selection": False,
            "policy_streams_per_plan": cfg["repeats"],
            "independent_hidden_worlds_per_root": 1,
            "continuation": "exact_greedy_combat_room_family_matched_temperature_0_8_noncombat",
            "proposal_cpu_seconds": sum(
                v.get("execution_cpu_seconds", 0.0) for v in values if v["stage"] == "proposal"
            ),
            "full_run_wins_in_comparison_samples": sum(
                v.get("victory", False)
                for v in values
                if v["stage"] == "comparison"
                and not v["duplicate_control"]
                and v["status"] == "terminal"
            ),
            "admitted_exploratory_preferences": sum(
                p["admitted_exploratory_preference"] for c in tables for p in c["preferences"]
            ),
            "information_scope": INFORMATION,
            "privileged_fixed_world_teacher": True,
            "student_inputs_public_only": True,
            "ordinary_PPO_eligible": False,
            "public_belief_search_eligible": False,
            "production_optimizer_steps": 0,
            "original_full_states_unchanged": True,
            "game_apps_created": 0,
            "checks": checks,
            "cases": tables,
            "sources": sources,
            "checkpoint_promoted": False,
            "adaptive_controller_allowed": False,
            "automatic_training_follows": False,
            "session_wall_seconds": time.monotonic() - started,
        }
        result = {**body, "report_id": manifest_identifier(body)}
        index = len(list((store.workspace / "sessions").glob("session-*.json"))) + 1
        atomic_json(store.workspace / f"sessions/session-{index:03d}.json", result)
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
            json.dumps({k: v for k, v in result.items() if k not in {"sources", "cases"}}, indent=2)
        )
        return int(result["status"] == COMPLETE + "_with_gaps")
    except (ValueError, KeyError, OSError, TimeoutError) as error:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
