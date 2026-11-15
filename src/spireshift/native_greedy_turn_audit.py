"""Saved-only reconstruction of fresh roots, complete turns and greedy continuations."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, score_episode
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_combat_teacher_data import trace_id
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_greedy_turn_branch import binding
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
from spireshift.native_greedy_turn_policy import reconstruct
from spireshift.native_greedy_turn_teacher import COMPLETE, duplicates, receipt


def audit(root: Path, path: Path, deadline: float) -> dict[str, Any]:
    cfg, seeds, models, score, sources = load(root, path)
    store = ChunkJournal(root, cfg)
    report = identified(store.workspace / "report.json")
    if (
        report["status"] != COMPLETE
        or report["config_id"] != store.config_id
        or report["failed_branches"]
        or report["skipped_branches"]
        or report["unavailable_source_worlds"]
    ):
        raise ValueError("Saved inference qualification needs the complete clean teacher schedule")
    check_sources(root, report["sources"])
    completed: dict[str, dict[str, Any]] = {}
    roots: list[dict[str, Any]] = []
    decisions = 0

    def verify(planned: list[dict[str, Any]]) -> None:
        nonlocal decisions
        by_id = {r["root_id"]: r for r in roots}
        for bare in planned:
            if time.monotonic() >= deadline:
                raise TimeoutError("Saved teacher audit reached its finite cap")
            task = budget_task(bare, completed)
            value = receipt(store, task, sources)
            if value is None or value["status"] != "terminal":
                raise ValueError("A saved teacher attempt is missing or incomplete")
            model = models[task["seed"]["numerical_seed"]]
            r = (
                identified(root / value["root_path"], "root_id")
                if task["stage"] == "source" and value["root_path"]
                else by_id.get(task.get("root_id", ""))
            )
            plan = identified(root / value["plan_path"], "plan_id") if value["plan_path"] else None
            case = read_native_episode(
                root / value["episode_path"], binding(cfg, task, model, score)
            )
            rebuilt = reconstruct(case, task, model, score, r, plan)
            rng = identified(root / value["rng_receipt_path"])
            scored = score_episode(case, task["seed"]["id"], score)
            if (
                any(rebuilt[k] != rng[k] for k in rebuilt)
                or rng["report_id"] != value["rng_receipt_id"]
                or trace_id(case) != value["trace_id"]
                or not scored["completed"]
                or scored["training_return"] != value["training_return"]
                or any(
                    case[k] != value[k]
                    for k in (
                        "status",
                        "victory",
                        "maximum_floor",
                        "completed_acts",
                        "cpu_seconds",
                        "execution_cpu_seconds",
                        "planning_cpu_seconds",
                    )
                )
                or case["cpu_seconds"]
                != case["execution_cpu_seconds"] + task["planning_cpu_seconds"]
                or not 0 <= case["execution_cpu_seconds"] <= task["cpu_allowance"]
            ):
                raise ValueError("Saved teacher choices, costs, scores or native ending changed")
            decisions += len(case["decisions"])
            del case
            completed[task["key"]] = value

    control = cfg["stage"] == "short_control"
    verify(source_tasks(seeds))
    source_set, roots = freeze_roots(store, source_tasks(seeds), completed, sources, write=False)
    proposals = proposal_tasks(roots, control)
    verify(proposals)
    frozen = freeze_plans(store, roots, proposals, completed, sources, control, write=False)
    comparisons = scored_tasks(roots, frozen, cfg["repeats"], control)
    verify(comparisons)
    tables = lessons(roots, frozen, completed, cfg["repeats"])
    matching = matched_draws(root, completed)
    if (
        tables != report["cases"]
        or matching != report["noncombat_matching"]
        or duplicates(comparisons, completed) != report["duplicate_public_traces_identical"]
        or source_set["report_id"] != report["source_set_id"]
        or frozen["report_id"] != report["candidate_set_id"]
        or len(completed) != report["completed_units"]
    ):
        raise ValueError("Saved teacher denominator, freezes, duplicates or paired tables changed")
    check_sources(root, sources)
    body = {
        "schema_version": "native-greedy-turn-teacher-audit-v1",
        "source_report_id": report["report_id"],
        "auditor_sha256": _sha_file(Path(__file__)),
        "branch_receipts_verified": len(completed),
        "public_decisions_reconstructed": decisions,
        "source_worlds": len(seeds),
        "all_choices_and_root_selection_reconstructed": True,
        "turn_boundaries_and_plans_reconstructed": True,
        "all_action_tables_exactly_reconstructed": True,
        "matched_noncombat": matching,
        "proposal_selection_outcome_blind": True,
        "continuation_probabilities_reconstructed": True,
        "all_proposal_CPU_charges_reconstructed": True,
        "native_journal_bytes_verified": True,
        "native_delivery_semantically_reaudited": False,
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
        result = audit(root, root / args.recipe, time.monotonic() + args.max_wall_seconds)
        atomic_json(args.output, result)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, KeyError, OSError, TimeoutError) as error:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
