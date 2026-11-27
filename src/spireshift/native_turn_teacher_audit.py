"""Reconstruct sealed complete-turn proposals, replay and full-run tables without games."""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, score_episode
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_combat_teacher_data import INFORMATION, trace_id
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_turn_teacher import freeze, receipt
from spireshift.native_turn_teacher_config import load, load_models
from spireshift.native_turn_teacher_data import comparison_tasks, proposal_tasks, turn_lesson
from spireshift.native_turn_teacher_policy import CONTRACT, TurnChooser, random_seed
from spireshift.training_objective import TrainingScoreSpec, load_training_score_spec


def reconstruct(
    case: dict[str, Any],
    root: dict[str, Any],
    task: dict[str, Any],
    model: CachedContextModel,
    score: TrainingScoreSpec,
    cfg: dict[str, Any],
    plan: dict[str, Any],
) -> int:
    if (
        case["status"] != "terminal"
        or case["seed"] != root["native_seed"]
        or case.get("recovered") is not False
        or case.get("privileged_fixture") is not False
        or case.get("native_ending_evidence_agrees") is not True
        or case.get("policy_contract") != CONTRACT
        or case.get("privileged_fixed_world_teacher") is not True
        or case.get("ordinary_PPO_eligible") is not False
    ):
        raise ValueError("Audit only explicitly marked clean fixed-world complete-turn branches")
    chooser = TurnChooser(
        root,
        model,
        score,
        first_action=task["first_action"],
        repeat=task["repeat"],
        temperature=cfg["temperature"],
        proposal_temperature=cfg["proposal_temperature"],
        plan=plan if task["stage"] == "comparison" else None,
    )
    for row in case["decisions"]:
        expected, saved = chooser(row["public_input"]), row["choice"]
        if set(expected) != set(saved):
            raise ValueError("Saved complete-turn choice has different behavior fields")
        for key, value in expected.items():
            other = saved[key]
            matches = (
                type(other) in (int, float) and math.isclose(value, other, rel_tol=0, abs_tol=1e-10)
                if type(value) is float
                else type(other) is type(value) and other == value
            )
            if not matches:
                raise ValueError(f"Saved complete-turn action or probability differs: {key}")
    chooser.finish(case)
    if not chooser.root_reached or not chooser.turn_complete or chooser.plan != plan:
        raise ValueError("Saved complete-turn plan or boundary did not exactly reconstruct")
    return len(case["decisions"])


def audit(root: Path, path: Path, *, deadline: float) -> dict[str, Any]:
    cfg, corpus, roots, sources = load(root, path)
    store = ChunkJournal(root, cfg)
    report = identified(store.workspace / "report.json")
    if (
        report["status"] != "native_complete_turn_teacher_complete"
        or report["config_id"] != store.config_id
        or report["failed_branches"]
        or report["skipped_branches"]
        or not report["all_turn_boundaries_replayed_exactly"]
    ):
        raise ValueError("Saved turn audit requires the complete clean branch denominator")
    check_sources(root, report["sources"])
    models = load_models(root, corpus)
    score = load_training_score_spec(root / corpus["training_spec"]["path"])
    by_id = {r["root_id"]: r for r in roots}
    completed: dict[str, dict[str, Any]] = {}
    decisions = 0

    def verify(tasks: list[dict[str, Any]]) -> None:
        nonlocal decisions
        for task in tasks:
            if time.monotonic() >= deadline:
                raise TimeoutError("Saved turn audit reached its finite cap; no game starts")
            value = receipt(store, task, sources)
            if value is None or value["status"] != "terminal":
                raise ValueError("Saved turn branch is missing or incomplete")
            r = by_id[task["root_id"]]
            plan = identified(root / value["plan_path"], "plan_id")
            model = models[r["numerical_seed"]]
            binding = {
                "environment_id": model.actor.environment_id,
                "config_id": store.config_id,
                "native_seed": r["native_seed"],
                "seed_id": r["source_seed_id"],
                "partition": "train",
                "panel_purpose": "complete_turn_teacher_not_PPO",
                "model_id": model.model_id,
                "training_spec_id": score.spec_id,
                "policy_contract": CONTRACT,
                "information_scope": INFORMATION,
                "root_id": r["root_id"],
                "turn_task": task,
                "continuation_sampling_seed": random_seed(
                    r["root_id"], "continuation", task["repeat"]
                ),
            }
            case = read_native_episode(root / value["episode_path"], binding)
            decisions += reconstruct(case, r, task, model, score, cfg, plan)
            scored = score_episode(case, r["source_seed_id"], score)
            if (
                not scored["completed"]
                or scored["training_return"] != value["training_return"]
                or value["plan_id"] != plan["plan_id"]
                or trace_id(case) != value["trace_id"]
                or any(
                    case[k] != value[k]
                    for k in ("status", "victory", "maximum_floor", "completed_acts")
                )
            ):
                raise ValueError("Saved turn branch score, ending, trace or plan differs")
            del case
            completed[task["key"]] = value

    proposals = proposal_tasks(roots)
    verify(proposals)
    frozen = freeze(store, roots, proposals, completed, set(), sources, write=False)
    comparisons = comparison_tasks(
        roots, frozen["roots"], cfg["repeats"], cfg["stage"] == "short_control"
    )
    verify(comparisons)
    tables = [
        turn_lesson(
            r,
            group["candidates"],
            [completed[t["key"]] for t in comparisons if t["root_id"] == r["root_id"]],
            cfg["repeats"],
        )
        for r, group in zip(roots, frozen["roots"], strict=True)
    ]
    if tables != report["cases"] or len(completed) != report["completed_units"]:
        raise ValueError("Saved complete-turn candidate denominator, uncertainty or tables changed")
    for task in comparisons:
        if task["duplicate_control"]:
            original = next(
                t
                for t in comparisons
                if t["root_id"] == task["root_id"]
                and t["plan_id"] == task["plan_id"]
                and t["repeat"] == 0
                and not t["duplicate_control"]
            )
            if completed[original["key"]]["trace_id"] != completed[task["key"]]["trace_id"]:
                raise ValueError("Repeated complete-turn public traces differ")
    check_sources(root, sources)
    body = {
        "schema_version": "native-complete-turn-teacher-audit-v1",
        "source_report_id": report["report_id"],
        "auditor_sha256": _sha_file(Path(__file__)),
        "branch_receipts_verified": len(completed),
        "public_decisions_reconstructed": decisions,
        "turn_boundaries_and_plans_reconstructed": True,
        "all_action_tables_exactly_reconstructed": True,
        "proposal_selection_outcome_blind": True,
        "continuation_probabilities_reconstructed": True,
        "native_journal_bytes_verified": True,
        "native_delivery_semantically_reaudited": False,
        "source_hidden_worlds": len(roots),
        "original_players_and_full_Adam_unchanged": True,
        "new_games": 0,
        "optimizer_steps": 0,
        "ordinary_PPO_eligible": False,
        "checkpoint_promoted": False,
    }
    return {**body, "report_id": manifest_identifier(body)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-wall-seconds", type=int, default=210, choices=range(1, 1801))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        result = audit(root, root / args.recipe, deadline=time.monotonic() + args.max_wall_seconds)
        atomic_json(args.output, result)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, KeyError, OSError, TimeoutError) as error:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
