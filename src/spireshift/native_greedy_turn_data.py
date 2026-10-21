"""Finite schedules, outcome-blind plan deduplication, costs and matched draw receipts."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_combat_planning_data import SEARCH_CPU_CAP, cpu_allowance
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_turn_teacher_data import comparison_tasks, turn_lesson
from spireshift.native_turn_teacher_policy import validate_plan


def source_tasks(seeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"key": f"source-{s['id']}", "seed": s, "stage": "source"} for s in seeds]


def first_actions(root: dict[str, Any], control: bool) -> list[int | None]:
    indices = list(range(len(root["public_input"]["candidates"])))
    if control:
        # One different first action proves exact counterfactual replay in a short check.
        indices = [next(i for i in indices if i != root["reference_action"])]
    return [None, *indices]


def proposal_tasks(roots: list[dict[str, Any]], control: bool) -> list[dict[str, Any]]:
    return [
        {
            "key": f"propose-{i:03d}-" + ("greedy" if a is None else f"a-{a:02d}"),
            "stage": "proposal",
            "root_id": r["root_id"],
            "first_action": a,
            "seed": {
                "id": r["source_seed_id"],
                "seed": r["native_seed"],
                "numerical_seed": r["numerical_seed"],
            },
            "repeat": 0,
            "duplicate_control": False,
        }
        for i, r in enumerate(roots)
        for a in first_actions(r, control)
    ]


def freeze_record(
    store: ChunkJournal, name: str, body: dict[str, Any], sources: dict[str, str], *, write: bool
) -> dict[str, Any]:
    result = {**body, "report_id": manifest_identifier(body)}
    path = store.workspace / name
    if path.exists():
        if identified(path) != result:
            raise ValueError("Preserve the frozen source/plan schedule and immutable receipts")
    elif write:
        atomic_json(path, result)
    else:
        raise ValueError("Saved-only audit cannot create a missing stage freeze")
    sources[str(path.relative_to(store.root))] = _sha_file(path)
    return result


def freeze_roots(
    store: ChunkJournal,
    tasks: list[dict[str, Any]],
    completed: dict[str, dict[str, Any]],
    sources: dict[str, str],
    *,
    write: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if set(completed) != {t["key"] for t in tasks}:
        raise ValueError("Resolve every predeclared fresh source before proposing any turn")
    records, roots = [], []
    for task in tasks:
        v = completed[task["key"]]
        ready = v["status"] == "terminal" and v["root_path"] is not None
        if ready:
            r = identified(store.root / v["root_path"], "root_id")
            if (
                r["source_key"] != task["key"]
                or r["source_seed_id"] != task["seed"]["id"]
                or r["native_seed"] != task["seed"]["seed"]
                or r["numerical_seed"] != task["seed"]["numerical_seed"]
                or r["root_id"] != v["root_id"]
                or not v["inference_audit_valid"]
            ):
                raise ValueError("A fresh source root differs from its sealed natural game")
            roots.append(r)
        records.append(
            {
                "source_key": task["key"],
                "seed": task["seed"],
                "usable": ready,
                "root_path": v["root_path"] if ready else None,
                "root_id": v["root_id"] if ready else None,
                "reason": None
                if ready
                else "failed_source"
                if v["status"] != "terminal"
                else "no_eligible_public_root",
            }
        )
    body = {
        "schema_version": "native-greedy-turn-source-freeze-v1",
        "config_id": store.config_id,
        "sources": records,
        "source_receipts": {
            t["key"]: sources[str((store.path(t["key"]) / "done.json").relative_to(store.root))]
            for t in tasks
        },
        "selection_uses_final_outcomes": False,
        "no_missing_source_replacement": True,
    }
    return freeze_record(store, "source-set.json", body, sources, write=write), roots


def budget_task(task: dict[str, Any], completed: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if task["stage"] == "source":
        return {**task, "cpu_allowance": 128.0, "planning_cpu_seconds": 0.0}
    spent = (
        sum(
            v.get("execution_cpu_seconds", 0.0)
            for v in completed.values()
            if v["stage"] == "proposal" and v["root_id"] == task["root_id"]
        )
        if task["stage"] == "proposal"
        else task["planning_cpu_seconds"]
    )
    if not math.isfinite(spent) or spent < 0:
        raise ValueError("Invalid sealed proposal CPU accounting")
    try:
        allowance = cpu_allowance(spent, 128.0, task["stage"] == "proposal")
    except ValueError:
        allowance = 0.0
    return {
        **task,
        "cpu_allowance": allowance,
        "planning_cpu_seconds": 0.0 if task["stage"] == "proposal" else spent,
    }


def freeze_plans(
    store: ChunkJournal,
    roots: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    completed: dict[str, dict[str, Any]],
    sources: dict[str, str],
    control: bool,
    *,
    write: bool = True,
) -> dict[str, Any]:
    if not {t["key"] for t in tasks}.issubset(completed):
        raise ValueError("Resolve every proposal before any scored comparison")
    groups = []
    for r in roots:
        own = [t for t in tasks if t["root_id"] == r["root_id"]]
        if [t["first_action"] for t in own] != first_actions(r, control):
            raise ValueError(
                "Freeze the complete declared first-move schedule without outcome filtering"
            )
        cost = sum(completed[t["key"]].get("execution_cpu_seconds", 0.0) for t in own)
        if not math.isfinite(cost) or cost < 0:
            raise ValueError("Proposal CPU accounting must be finite and nonnegative")
        clean = cost <= SEARCH_CPU_CAP and all(
            completed[t["key"]]["status"] == "terminal" for t in own
        )
        unique: dict[str, dict[str, Any]] = {}
        if clean:
            for task in own:
                v = completed[task["key"]]
                if not all(
                    v[k]
                    for k in (
                        "root_reached",
                        "turn_complete",
                        "native_audit_valid",
                        "inference_audit_valid",
                    )
                ):
                    raise ValueError("Complete proposals need exact replay and saved-choice audits")
                p = identified(store.root / v["plan_path"], "plan_id")
                validate_plan(p, r)
                first = (
                    r["reference_action"] if task["first_action"] is None else task["first_action"]
                )
                if p["plan_id"] != v["plan_id"] or p["steps"][0]["action_index"] != first:
                    raise ValueError("A frozen proposal differs from its declared legal first move")
                if p["plan_id"] not in unique:
                    unique[p["plan_id"]] = {
                        "plan_id": p["plan_id"],
                        "path": v["plan_path"],
                        "proposal_keys": [],
                        "reference": task["first_action"] is None,
                    }
                unique[p["plan_id"]]["proposal_keys"].append(task["key"])
        groups.append(
            {
                "root_id": r["root_id"],
                "blocked": not clean,
                "candidates": list(unique.values()),
                "proposal_cpu_seconds": cost,
            }
        )
    body = {
        "schema_version": "native-greedy-turn-candidates-v1",
        "config_id": store.config_id,
        "roots": groups,
        "selection_uses_proposal_outcomes": False,
        "selection": "ordered_exact_public_trace_deduplication_only",
        "alternative_charged_all_proposal_CPU_without_amortization": True,
        "greedy_reference_proposal_CPU_charge": 0.0,
        "proposal_receipts": {
            t["key"]: sources[str((store.path(t["key"]) / "done.json").relative_to(store.root))]
            for t in tasks
        },
    }
    return freeze_record(store, "candidate-set.json", body, sources, write=write)


def scored_tasks(
    roots: list[dict[str, Any]], frozen: dict[str, Any], repeats: int, control: bool
) -> list[dict[str, Any]]:
    groups = {g["root_id"]: g for g in frozen["roots"]}
    refs = {r["root_id"]: r for r in roots}
    result = []
    for t in comparison_tasks(roots, frozen["roots"], repeats, control):
        r, group = refs[t["root_id"]], groups[t["root_id"]]
        reference = next(p["plan_id"] for p in group["candidates"] if p["reference"])
        result.append(
            {
                **t,
                "seed": {
                    "id": r["source_seed_id"],
                    "seed": r["native_seed"],
                    "numerical_seed": r["numerical_seed"],
                },
                "reference": t["plan_id"] == reference,
                "planning_cpu_seconds": 0.0
                if t["plan_id"] == reference
                else group["proposal_cpu_seconds"],
            }
        )
    return result


def lessons(
    roots: list[dict[str, Any]],
    frozen: dict[str, Any],
    completed: dict[str, dict[str, Any]],
    repeats: int,
) -> list[dict[str, Any]]:
    return [
        turn_lesson(
            r,
            g["candidates"],
            [
                v
                for v in completed.values()
                if v["stage"] == "comparison" and v["root_id"] == r["root_id"]
            ],
            repeats,
        )
        for r, g in zip(roots, frozen["roots"], strict=True)
    ]


def matched_draws(root: Path, completed: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Compare each candidate with its reference, streaming only compact RNG maps."""
    refs = {
        (v["root_id"], v["repeat"]): v
        for v in completed.values()
        if v["stage"] == "comparison"
        and v.get("reference")
        and not v["duplicate_control"]
        and v["status"] == "terminal"
    }
    pairs = shared = same = 0
    for v in completed.values():
        if (
            v["stage"] != "comparison"
            or v["status"] != "terminal"
            or v["duplicate_control"]
            or v["reference"]
        ):
            continue
        other = refs.get((v["root_id"], v["repeat"]))
        if other is None:
            continue
        maps = []
        for value in (other, v):
            receipt = identified(root / value["rng_receipt_path"])
            if receipt["report_id"] != value["rng_receipt_id"]:
                raise ValueError("Matched teacher noncombat receipt changed")
            rows = {r["draw_key"]: r for r in receipt["noncombat"]}
            if len(rows) != len(receipt["noncombat"]):
                raise ValueError("Teacher reused a noncombat sampling slot")
            maps.append(rows)
        pairs += 1
        for key in maps[0].keys() & maps[1].keys():
            a, b = maps[0][key], maps[1][key]
            if a["draw"] != b["draw"] or (
                a["effective_input_id"] == b["effective_input_id"] and a != b
            ):
                raise ValueError("Teacher noncombat matching changed at a shared public slot")
            shared += 1
            same += a["effective_input_id"] == b["effective_input_id"]
    return {
        "valid": True,
        "candidate_reference_pairs": pairs,
        "shared_noncombat_draw_keys": shared,
        "identical_public_inputs_with_identical_choices": same,
    }
