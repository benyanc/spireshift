"""One isolated native combat proposal, selected replay or baseline control."""

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
from spireshift.native_combat_planning_policy import CONTRACT, FightChooser
from spireshift.native_combat_teacher_data import INFORMATION, trace_id
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_turn_teacher_policy import random_seed
from spireshift.training_objective import TrainingScoreSpec


def binding(
    cfg: dict[str, Any],
    r: dict[str, Any],
    task: dict[str, Any],
    model: CachedContextModel,
    score: TrainingScoreSpec,
) -> dict[str, Any]:
    return {
        "environment_id": model.actor.environment_id,
        "config_id": manifest_identifier(cfg),
        "native_seed": r["native_seed"],
        "seed_id": r["source_seed_id"],
        "partition": "train",
        "panel_purpose": "bounded_combat_planning_not_PPO",
        "model_id": model.model_id,
        "training_spec_id": score.spec_id,
        "policy_contract": CONTRACT,
        "information_scope": INFORMATION,
        "root_id": r["root_id"],
        "combat_task": task,
        "continuation_sampling_seed": random_seed(r["root_id"], "continuation", task["repeat"]),
    }


def branch(
    q: EngineQualificationConfig,
    cfg: dict[str, Any],
    inputs: dict[str, Any],
    target: Path,
    node: Path,
    r: dict[str, Any],
    item: dict[str, Any],
    task: dict[str, Any],
    model: CachedContextModel,
    score: TrainingScoreSpec,
    deadline: float,
) -> dict[str, Any]:
    turn = identified(q.root / item["turn_plan_path"], "plan_id")
    if turn["plan_id"] != item["turn_plan_id"]:
        raise ValueError("The original frozen initial turn changed")
    plan = (
        identified(q.root / task["selected"]["path"], "plan_id")
        if task["stage"] == "evaluation"
        else None
    )
    if plan is not None and plan["plan_id"] != task["selected"]["plan_id"]:
        raise ValueError("The selected combat remainder changed")
    plan_path = target / "fight-plan.json"
    chooser = FightChooser(
        r,
        turn,
        model,
        score,
        mode=task["stage"],
        sample=task["sample"],
        repeat=task["repeat"],
        plan=plan,
        on_plan=lambda p: atomic_json(plan_path, p) if plan is None else None,
    )
    worker = SelectionWorker(
        q, inputs, target / "worker", node, cfg["helpers_sha256"], script=SCRIPT
    )
    try:
        atomic_json(worker.workspace / "selection-verifier.json", {"node": str(node)})
        case = worker.episode(
            r["native_seed"],
            maximum_decisions=4096,
            wall_seconds=min(60, deadline - time.monotonic() - 15),
            cpu_seconds=task["cpu_allowance"],
            chooser=chooser,
        )
        try:
            chooser.finish(case)
        except ValueError as problem:
            case.update(status="failed", error=str(problem))
        execution = case["cpu_seconds"]
        charge = task.get("planning_cpu_seconds", 0.0)
        case.update(
            worker_workspace="worker",
            policy_contract=CONTRACT,
            teacher_experiment=True,
            privileged_fixed_world_teacher=True,
            student_inputs_public_only=True,
            ordinary_PPO_eligible=False,
            execution_cpu_seconds=execution,
            planning_cpu_seconds=charge,
            cpu_seconds=execution + charge,
        )
        scored = score_episode(case, r["source_seed_id"], score)
        if not scored["completed"] or chooser.plan is None:
            case.update(
                status="failed", error=case.get("error", "Incomplete or over-budget combat plan")
            )
        path = target / "episode.json"
        bound = binding(cfg, r, task, model, score)
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
        audit = audit_selection_worker(worker.workspace, [path], deadline=deadline)
        atomic_json(target / "native-audit.json", audit)
        saved = read_native_episode(path, bound)
        if trace_id(saved) != digest:
            raise ValueError("Saved combat branch differs from its audited native trace")
        del saved
        if (
            chooser.plan is not None
            and plan is None
            and identified(plan_path, "plan_id") != chooser.plan
        ):
            raise ValueError("Combat proposal changed after the encounter boundary was sealed")
        return {
            **outcome,
            "error": error,
            "stage": task["stage"],
            "item_key": item["key"],
            "root_id": r["root_id"],
            "initial_turn_id": turn["plan_id"],
            "sample": task["sample"],
            "repeat": task["repeat"],
            "duplicate": task["duplicate"],
            "root_reached": chooser.prefix.root_reached,
            "combat_complete": chooser.plan is not None,
            "exit": chooser.plan["exit"] if chooser.plan else None,
            "plan_id": chooser.plan["plan_id"] if chooser.plan else None,
            "plan_path": task["selected"]["path"]
            if plan is not None
            else str(plan_path.relative_to(q.root))
            if chooser.plan
            else None,
            "native_audit_valid": audit["valid"],
            "trace_id": digest,
            "execution_cpu_seconds": execution,
            "planning_cpu_seconds": charge,
            "training_return": scored["training_return"]
            if outcome["status"] == "terminal"
            else None,
            "episode_path": str(path.relative_to(q.root)),
            "full_run_return_used_for_combat_selection": False,
            "source_seed_replay": "planned_counterfactual_not_uncertain_delivery_retry",
        }
    finally:
        worker.stop()
