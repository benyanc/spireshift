"""Read-only import of the completed fresh-world teacher; one episode at a time."""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, score_episode
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_combat_teacher_data import trace_id
from spireshift.native_consequence_data import CONTRACT, encode_examples, examples
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import ChunkJournal, load_state
from spireshift.native_context_reuse import check_sources
from spireshift.native_greedy_turn_branch import binding
from spireshift.native_greedy_turn_config import load as load_teacher
from spireshift.native_greedy_turn_data import (
    budget_task,
    freeze_plans,
    freeze_roots,
    lessons,
    proposal_tasks,
    scored_tasks,
    source_tasks,
)
from spireshift.native_greedy_turn_teacher import COMPLETE, receipt
from spireshift.native_turn_teacher_policy import validate_plan
from spireshift.neural_combat import _numpy
from spireshift.training_objective import TrainingScoreSpec


def prepare(
    root: Path,
    cfg: dict[str, Any],
    deadline: float,
) -> tuple[
    dict[str, Any], dict[int, CachedContextModel], dict[int, Any], TrainingScoreSpec, dict[str, str]
]:
    recipe = root / cfg["teacher_recipe"]["path"]
    if _sha_file(recipe) != cfg["teacher_recipe"]["sha256"]:
        raise ValueError("Preserve the completed teacher's exact recipe")
    teacher, seeds, models, score, sources = load_teacher(root, recipe)
    report = identified(root / cfg["teacher_report"]["path"])
    assessment = identified(root / cfg["teacher_assessment"]["path"])
    if (
        report["report_id"] != cfg["teacher_report"]["id"]
        or report["config_id"] != manifest_identifier(teacher)
        or report["status"] != COMPLETE + "_with_gaps"
        or report["native_attempts"] != 469
        or report["unavailable_source_worlds"] != 1
        or report["failed_branches"]
        or report["skipped_branches"]
        or report["blocked_source_roots"]
        or report["production_optimizer_steps"]
        or not report["original_full_states_unchanged"]
        or not all(report["checks"].values())
        or assessment["report_id"] != cfg["teacher_assessment"]["id"]
        or assessment["source_report_id"] != report["report_id"]
        or not assessment[
            "all_scored_plans_have_identical_current_fight_traces_across_eight_streams"
        ]
        or not assessment["all_scores_costs_freezes_and_lesson_tables_reconstructed"]
        or not assessment["original_eight_world_denominator_preserved"]
    ):
        raise ValueError(
            "Require the sealed, completed eight-source teacher and saved outcome audit"
        )
    check_sources(root, report["sources"])
    store = ChunkJournal(root, teacher)
    completed: dict[str, dict[str, Any]] = {}

    def verify(tasks: list[dict[str, Any]]) -> None:
        for bare in tasks:
            if time.monotonic() >= deadline:
                raise TimeoutError("Saved teacher import reached its finite cap")
            task = budget_task(bare, completed)
            value = receipt(store, task, sources)
            if value is None or value["status"] != "terminal":
                raise ValueError("Do not drop or retry a missing/failed teacher attempt")
            completed[task["key"]] = value

    verify(source_tasks(seeds))
    source_set, roots = freeze_roots(store, source_tasks(seeds), completed, sources, write=False)
    proposals = proposal_tasks(roots, False)
    verify(proposals)
    frozen = freeze_plans(store, roots, proposals, completed, sources, False, write=False)
    comparisons = scored_tasks(roots, frozen, teacher["repeats"], False)
    verify(comparisons)
    if (
        source_set["report_id"] != report["source_set_id"]
        or frozen["report_id"] != report["candidate_set_id"]
        or lessons(roots, frozen, completed, teacher["repeats"]) != report["cases"]
        or sources != report["sources"]
        or len(roots) != 7
        or len(comparisons) != 408
    ):
        raise ValueError("Completed teacher denominator, freezes, labels or source bytes differ")
    parent = json.loads((root / teacher["behavior_recipe"]["path"]).read_text())
    adams = {}
    for p in parent["players"]:
        model, adam, state_id = load_state(root / p["path"])
        if model.model_id != models[p["numerical_seed"]].model_id or state_id != p["state_id"]:
            raise ValueError("Preserve both exact player and complete Adam states")
        adams[p["numerical_seed"]] = adam
    units = []
    for r, group in zip(roots, frozen["roots"], strict=True):
        cells = []
        for candidate in group["candidates"]:
            tasks = [
                t
                for t in comparisons
                if t["root_id"] == r["root_id"] and t["plan_id"] == candidate["plan_id"]
            ]
            if [t["repeat"] for t in tasks] != list(range(8)):
                raise ValueError("Every frozen plan needs all eight declared conditional returns")
            values = [completed[t["key"]] for t in tasks]
            if any(v["training_return"] is None for v in values):
                raise ValueError("A masked/failed final outcome cannot become a consequence label")
            cells.append(
                {
                    "task": budget_task(tasks[0], completed),
                    "value": values[0],
                    "plan_path": candidate["path"],
                    "plan_id": candidate["plan_id"],
                    "mean_return": statistics.fmean(v["training_return"] for v in values),
                    "return_samples": [v["training_return"] for v in values],
                }
            )
        units.append(
            {"key": f"data-{r['source_seed_id']}", "stage": "data", "root": r, "cells": cells}
        )
    sources[cfg["teacher_report"]["path"]] = _sha_file(root / cfg["teacher_report"]["path"])
    sources[cfg["teacher_assessment"]["path"]] = _sha_file(root / cfg["teacher_assessment"]["path"])
    context = {
        "teacher_config": teacher,
        "report": report,
        "units": units,
        "source_world_denominator": source_set["sources"],
        "players": parent["players"],
    }
    return context, models, adams, score, sources


def encode_world(
    root: Path,
    context: dict[str, Any],
    unit: dict[str, Any],
    model: CachedContextModel,
    score: TrainingScoreSpec,
    directory: Path,
    deadline: float,
) -> dict[str, Any]:
    np = _numpy()
    chunks, summaries = [], []
    provenance: list[dict[str, Any]] = []
    r = unit["root"]
    for cell in unit["cells"]:
        if time.monotonic() >= deadline:
            raise TimeoutError("One-world consequence extraction reached its finite cap")
        value = cell["value"]
        plan = identified(root / cell["plan_path"], "plan_id")
        validate_plan(plan, r)
        case = read_native_episode(
            root / value["episode_path"],
            binding(context["teacher_config"], cell["task"], model, score),
        )
        if (
            trace_id(case) != value["trace_id"]
            or score_episode(case, r["source_seed_id"], score)["training_return"]
            != value["training_return"]
        ):
            raise ValueError(
                "A chosen saved episode no longer binds its public trace and final return"
            )
        start = len(r["prefix"])
        for i, step in enumerate(plan["steps"], start):
            if (
                case["decisions"][i]["public_input"] != step["public_input"]
                or case["decisions"][i]["choice"]["action_index"] != step["action_index"]
            ):
                raise ValueError("Consequence labels differ from the exact frozen native turn")
        values, summary = examples(case, r, cell["plan_id"], cell["mean_return"])
        chunks.append(encode_examples(values, model, score))
        summaries.append(summary)
        provenance.extend({k: v for k, v in x.items() if k != "public_input"} for x in values)
        del values, case
    arrays = {name: np.concatenate([c[name] for c in chunks], axis=0) for name in chunks[0]}
    with (directory / "encoded.npz").open("xb") as stream:
        np.savez_compressed(stream, **arrays)
    atomic_json(
        directory / "labels-and-provenance.json",
        {
            "contract": CONTRACT,
            "source_seed_id": r["source_seed_id"],
            "examples": provenance,
            "current_public_inputs_only": True,
            "future_observations_are_labels_only": True,
            "one_episode_per_plan_decoded": True,
            "return_streams_averaged_not_repeated_as_combat_data": 8,
        },
    )
    return {
        "source_seed_id": r["source_seed_id"],
        "numerical_seed": r["numerical_seed"],
        "plans": len(chunks),
        "combat_decisions": len(arrays["owners"]),
        "plan_summaries": summaries,
        "valid_target_counts": arrays["mask"].sum(axis=0).tolist(),
        "encoded_sha256": _sha_file(directory / "encoded.npz"),
        "labels_sha256": _sha_file(directory / "labels-and-provenance.json"),
        "scope": "fixed_world_recorded_continuations_not_optimal_action_or_PPO_targets",
    }


def combine(paths: list[Path]) -> dict[str, Any]:
    np = _numpy()
    arrays = []
    for path in paths:
        with np.load(path / "encoded.npz", allow_pickle=False) as saved:
            arrays.append({k: saved[k] for k in saved.files})
    if not arrays:
        raise ValueError("No source worlds available for consequence fitting")
    return {k: np.concatenate([a[k] for a in arrays], axis=0) for k in arrays[0]}


def partition(arrays: dict[str, Any], mask: Any) -> dict[str, Any]:
    return {k: v[mask] for k, v in arrays.items()}
