"""Reconstruct saved combat proposals, tactical selection, CPU charges and every choice."""

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
from spireshift.native_combat_planning import budget_task, frozen_selection, receipt
from spireshift.native_combat_planning_branch import binding
from spireshift.native_combat_planning_config import load
from spireshift.native_combat_planning_data import evaluation_tasks, search_tasks, summarize
from spireshift.native_combat_planning_policy import CONTRACT, FightChooser
from spireshift.native_combat_teacher_data import trace_id
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_turn_teacher_config import load_models
from spireshift.training_objective import TrainingScoreSpec, load_training_score_spec


def reconstruct(
    case: dict[str, Any],
    r: dict[str, Any],
    turn: dict[str, Any],
    task: dict[str, Any],
    model: CachedContextModel,
    score: TrainingScoreSpec,
    plan: dict[str, Any],
) -> int:
    if (
        case["status"] != "terminal"
        or case["seed"] != r["native_seed"]
        or case.get("policy_contract") != CONTRACT
        or case.get("ordinary_PPO_eligible") is not False
        or case.get("privileged_fixed_world_teacher") is not True
        or case.get("student_inputs_public_only") is not True
        or case.get("native_ending_evidence_agrees") is not True
        or case.get("privileged_fixture") is not False
        or case.get("recovered") is not False
    ):
        raise ValueError("Saved combat audit requires clean, explicitly privileged counterfactuals")
    chooser = FightChooser(
        r,
        turn,
        model,
        score,
        mode=task["stage"],
        sample=task["sample"],
        repeat=task["repeat"],
        plan=plan if task["stage"] == "evaluation" else None,
    )
    for row in case["decisions"]:
        expected, actual = chooser(row["public_input"]), row["choice"]
        if set(expected) != set(actual):
            raise ValueError("Saved combat behavior fields differ")
        for key, value in expected.items():
            match = (
                type(actual[key]) in (int, float)
                and math.isclose(value, actual[key], rel_tol=0, abs_tol=1e-10)
                if type(value) is float
                else type(value) is type(actual[key]) and value == actual[key]
            )
            if not match:
                raise ValueError(f"Saved combat choice or probability changed: {key}")
    chooser.finish(case)
    if chooser.plan != plan or not chooser.prefix.root_reached:
        raise ValueError("Saved combat plan or encounter boundary does not reconstruct")
    return len(case["decisions"])


def audit(root: Path, path: Path, deadline: float) -> dict[str, Any]:
    cfg, corpus, roots, items, baseline, sources = load(root, path)
    store = ChunkJournal(root, cfg)
    report = identified(store.workspace / "report.json")
    if (
        report["status"] != "native_bounded_combat_comparison_complete"
        or report["config_id"] != store.config_id
        or report["failed_branches"]
        or report["skipped_branches"]
        or report["blocked_initial_turns"]
    ):
        raise ValueError("Require the clean complete combat comparison denominator")
    check_sources(root, report["sources"])
    score = load_training_score_spec(root / corpus["training_spec"]["path"])
    models = load_models(root, corpus)
    by_id, by_item = {r["root_id"]: r for r in roots}, {i["key"]: i for i in items}
    completed: dict[str, dict[str, Any]] = {}
    decisions = 0

    def verify(tasks: list[dict[str, Any]]) -> None:
        nonlocal decisions
        for bare in tasks:
            if time.monotonic() >= deadline:
                raise TimeoutError("Saved combat audit reached its finite cap; no game starts")
            task = budget_task(bare, completed, score.evaluation_objective.whole_run_budget)
            value = receipt(store, task, sources)
            if value is None or value["status"] != "terminal":
                raise ValueError("Missing clean combat receipt")
            r, item = by_id[task["root_id"]], by_item[task["item_key"]]
            model = models[r["numerical_seed"]]
            turn = identified(root / item["turn_plan_path"], "plan_id")
            plan = identified(root / value["plan_path"], "plan_id")
            case = read_native_episode(
                root / value["episode_path"], binding(cfg, r, task, model, score)
            )
            decisions += reconstruct(case, r, turn, task, model, score, plan)
            charge = task.get("planning_cpu_seconds", 0.0)
            if (
                case["planning_cpu_seconds"] != charge
                or case["cpu_seconds"] != case["execution_cpu_seconds"] + charge
                or not 0 <= case["execution_cpu_seconds"] <= task["cpu_allowance"]
                or not 0 <= case["cpu_seconds"] <= score.evaluation_objective.whole_run_budget
                or plan["plan_id"] != value["plan_id"]
                or plan["exit"] != value["exit"]
                or trace_id(case) != value["trace_id"]
                or any(
                    case[k] != value[k]
                    for k in (
                        "status",
                        "victory",
                        "maximum_floor",
                        "completed_acts",
                        "execution_cpu_seconds",
                        "planning_cpu_seconds",
                        "cpu_seconds",
                    )
                )
                or score_episode(case, r["source_seed_id"], score)["training_return"]
                != value["training_return"]
            ):
                raise ValueError(
                    "Saved combat score, ending, selected plan or total CPU charge changed"
                )
            del case
            if (
                task["stage"] == "baseline"
                and value["trace_id"] != baseline[f"{item['key']}-r00"]["trace_id"]
            ):
                raise ValueError("Baseline replay differs from the reused original trace")
            if (
                task["duplicate"]
                and value["trace_id"] != completed[f"evaluate-{item['key']}-r00"]["trace_id"]
            ):
                raise ValueError("Repeated selected combat plan changed its exact trace")
            completed[task["key"]] = value

    search = search_tasks(items)
    verify(search)
    frozen = frozen_selection(store, roots, items, search, completed, sources, write=False)
    evaluations = evaluation_tasks(
        items, frozen["groups"], cfg["repeats"], cfg["stage"] == "short_control"
    )
    verify(evaluations)
    if (
        len(completed) != report["completed_units"]
        or summarize(roots, items, baseline, completed, cfg["repeats"]) != report["summary"]
    ):
        raise ValueError("Combat comparison uncertainty, denominator or tables changed")
    check_sources(root, sources)
    body = {
        "schema_version": "native-bounded-combat-audit-v1",
        "source_report_id": report["report_id"],
        "auditor_sha256": _sha_file(Path(__file__)),
        "branch_receipts_verified": len(completed),
        "public_decisions_reconstructed": decisions,
        "all_choices_reconstructed": True,
        "combat_plans_and_selection_reconstructed": True,
        "planning_cost_charged_without_amortization": True,
        "full_states_unchanged": True,
        "native_journal_bytes_verified": True,
        "native_delivery_semantically_reaudited": False,
        "new_games": 0,
        "optimizer_steps": 0,
        "ordinary_PPO_eligible": False,
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
        result = audit(root, root / args.recipe, time.monotonic() + args.max_wall_seconds)
        atomic_json(args.output, result)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, KeyError, OSError, TimeoutError) as error:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
