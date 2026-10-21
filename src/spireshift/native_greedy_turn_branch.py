"""One fresh source or CPU-charged frozen-turn episode; sealed/audited before commit."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, save_native_episode, score_episode
from spireshift.engine_learning import identified
from spireshift.engine_qualification import EngineQualificationConfig
from spireshift.engine_selection_audit import audit_selection_worker
from spireshift.engine_selection_worker import SCRIPT, SelectionWorker
from spireshift.full_run_experience import atomic_json
from spireshift.native_combat_teacher_data import INFORMATION, trace_id
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_greedy_turn_policy import (
    CONTRACT,
    GreedyTurnChooser,
    SourceChooser,
    continuation_seed,
    reconstruct,
)
from spireshift.native_turn_teacher_policy import validate_plan
from spireshift.training_objective import TrainingScoreSpec


def binding(
    cfg: dict[str, Any], task: dict[str, Any], model: CachedContextModel, score: TrainingScoreSpec
) -> dict[str, Any]:
    return {
        "environment_id": model.actor.environment_id,
        "config_id": manifest_identifier(cfg),
        "native_seed": task["seed"]["seed"],
        "seed_id": task["seed"]["id"],
        "partition": "control" if cfg["stage"] == "short_control" else "train",
        "panel_purpose": "fresh_greedy_complete_turn_teacher_not_PPO",
        "model_id": model.model_id,
        "training_spec_id": score.spec_id,
        "policy_contract": CONTRACT,
        "information_scope": INFORMATION,
        "task": task,
        "continuation_seed": continuation_seed(task["root_id"], task["repeat"])
        if task["stage"] != "source"
        else task["seed"]["seed"],
    }


def branch(
    q: EngineQualificationConfig,
    cfg: dict[str, Any],
    inputs: dict[str, Any],
    target: Path,
    node: Path,
    task: dict[str, Any],
    model: CachedContextModel,
    score: TrainingScoreSpec,
    r: dict[str, Any] | None,
    deadline: float,
) -> dict[str, Any]:
    source, proposal = task["stage"] == "source", task["stage"] == "proposal"
    plan = (
        identified(q.root / task["plan_path"], "plan_id") if task["stage"] == "comparison" else None
    )
    if plan is not None:
        if r is None or plan["plan_id"] != task["plan_id"]:
            raise ValueError("A scored turn differs from its frozen public plan")
        validate_plan(plan, r)
    root_path, plan_path = target / "root.json", target / "turn-plan.json"
    chooser: SourceChooser | GreedyTurnChooser = (
        SourceChooser(task["seed"], model, score, lambda v: atomic_json(root_path, v))
        if source
        else GreedyTurnChooser(
            r if r is not None else {},
            model,
            score,
            first_action=task["first_action"],
            repeat=task["repeat"],
            plan=plan,
            on_plan=(lambda v: atomic_json(plan_path, v)) if proposal else None,
        )
    )
    worker = SelectionWorker(
        q, inputs, target / "worker", node, cfg["helpers_sha256"], script=SCRIPT
    )
    try:
        atomic_json(worker.workspace / "selection-verifier.json", {"node": str(node)})
        case = worker.episode(
            task["seed"]["seed"],
            maximum_decisions=cfg["maximum_decisions"],
            wall_seconds=min(cfg["episode_wall_seconds"], deadline - time.monotonic() - 15),
            cpu_seconds=task["cpu_allowance"],
            chooser=chooser,
        )
        if isinstance(chooser, GreedyTurnChooser):
            try:
                chooser.finish(case)
            except ValueError as problem:
                case.update(status="failed", error=str(problem))
        execution, charge = case["cpu_seconds"], task["planning_cpu_seconds"]
        case.update(
            worker_workspace="worker",
            policy_contract=CONTRACT,
            teacher_experiment=True,
            privileged_fixed_world_teacher=not source,
            student_inputs_public_only=True,
            ordinary_PPO_eligible=False,
            execution_cpu_seconds=execution,
            planning_cpu_seconds=charge,
            cpu_seconds=execution + charge,
        )
        if case["seed"] != task["seed"]["seed"]:
            raise ValueError("Native teacher did not use its exact canonical training seed")
        scored = score_episode(case, task["seed"]["id"], score)
        complete = source or (isinstance(chooser, GreedyTurnChooser) and chooser.turn_complete)
        if not scored["completed"] or not complete or not 0 <= execution <= task["cpu_allowance"]:
            case.update(
                status="failed",
                error=case.get("error") or "Incomplete or over-budget complete turn",
            )
        path, bound = target / "episode.json", binding(cfg, task, model, score)
        save_native_episode(path, case, bound)
        if case["status"] == "terminal":
            worker.close()
        else:
            worker.retire(case["error"])
        digest = trace_id(case)
        outcome = {
            k: case[k]
            for k in ("status", "victory", "maximum_floor", "completed_acts", "cpu_seconds")
        }
        error = case.get("error")
        del case
        native = audit_selection_worker(worker.workspace, [path], deadline=deadline)
        atomic_json(target / "native-audit.json", native)
        saved = read_native_episode(path, bound)
        if trace_id(saved) != digest:
            raise ValueError("Saved teacher episode differs from its native delivery trace")
        actual_root = chooser.root if isinstance(chooser, SourceChooser) else r
        actual_plan = chooser.plan if isinstance(chooser, GreedyTurnChooser) else None
        rng_id = None
        if outcome["status"] == "terminal":
            if not native["valid"]:
                raise ValueError("Clean teacher ending failed its native delivery audit")
            checked = reconstruct(saved, task, model, score, actual_root, actual_plan)
            body = {"schema_version": "native-greedy-turn-choice-receipt-v1", **checked}
            rng = {**body, "report_id": manifest_identifier(body)}
            atomic_json(target / "rng-receipt.json", rng)
            rng_id = rng["report_id"]
        del saved
        if source and actual_root is not None and identified(root_path, "root_id") != actual_root:
            raise ValueError("Source root changed after being sealed before later outcomes")
        if proposal and actual_plan is not None and identified(plan_path, "plan_id") != actual_plan:
            raise ValueError("Proposed turn changed after being sealed at its native boundary")
        return {
            **outcome,
            "error": error,
            "stage": task["stage"],
            "seed_id": task["seed"]["id"],
            "numerical_seed": task["seed"]["numerical_seed"],
            "root_id": actual_root["root_id"] if actual_root is not None else task.get("root_id"),
            "root_path": str(root_path.relative_to(q.root))
            if source and actual_root is not None
            else None,
            "root_reached": actual_root is not None
            if source
            else isinstance(chooser, GreedyTurnChooser) and chooser.root_reached,
            "turn_complete": complete,
            "native_audit_valid": native["valid"],
            "inference_audit_valid": rng_id is not None,
            "trace_id": digest,
            "execution_cpu_seconds": execution,
            "planning_cpu_seconds": charge,
            "training_return": scored["training_return"]
            if outcome["status"] == "terminal"
            else None,
            "episode_path": str(path.relative_to(q.root)),
            "rng_receipt_path": str((target / "rng-receipt.json").relative_to(q.root))
            if rng_id
            else None,
            "rng_receipt_id": rng_id,
            "plan_id": task["plan_id"]
            if task["stage"] == "comparison"
            else actual_plan["plan_id"]
            if actual_plan is not None
            else None,
            "plan_path": str(plan_path.relative_to(q.root))
            if proposal and actual_plan is not None
            else task.get("plan_path"),
            "repeat": task.get("repeat"),
            "duplicate_control": task.get("duplicate_control", False),
            "reference": task.get("reference", False),
            "turn_decisions": len(actual_plan["steps"]) if actual_plan else 0,
            "proposal_outcome_used_for_candidate_selection": False,
        }
    finally:
        worker.stop()
