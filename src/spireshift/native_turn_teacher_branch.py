"""One isolated native proposal or frozen complete-turn full-run comparison."""

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
from spireshift.native_turn_teacher_policy import CONTRACT, TurnChooser, random_seed, validate_plan
from spireshift.training_objective import TrainingScoreSpec


def branch(
    q: EngineQualificationConfig,
    cfg: dict[str, Any],
    inputs: dict[str, Any],
    target: Path,
    node: Path,
    root: dict[str, Any],
    task: dict[str, Any],
    model: CachedContextModel,
    score: TrainingScoreSpec,
    deadline: float,
) -> dict[str, Any]:
    proposal = task["stage"] == "proposal"
    plan = None if proposal else identified(q.root / task["plan_path"], "plan_id")
    if plan is not None:
        validate_plan(plan, root)
        if plan["plan_id"] != task["plan_id"]:
            raise ValueError("Scored branch differs from its frozen candidate")
    plan_path = target / "turn-plan.json"
    chooser = TurnChooser(
        root,
        model,
        score,
        first_action=task["first_action"],
        repeat=task["repeat"],
        temperature=cfg["temperature"],
        proposal_temperature=cfg["proposal_temperature"],
        plan=plan,
        on_plan=lambda value: atomic_json(plan_path, value),
    )
    worker = SelectionWorker(
        q, inputs, target / "worker", node, cfg["helpers_sha256"], script=SCRIPT
    )
    try:
        atomic_json(worker.workspace / "selection-verifier.json", {"node": str(node)})
        case = worker.episode(
            root["native_seed"],
            maximum_decisions=4096,
            wall_seconds=min(60, deadline - time.monotonic() - 15),
            cpu_seconds=score.evaluation_objective.whole_run_budget,
            chooser=chooser,
        )
        try:
            chooser.finish(case)
        except ValueError as problem:
            case.update(status="failed", error=str(problem))
        case.update(
            worker_workspace="worker",
            policy_contract=CONTRACT,
            teacher_experiment=True,
            privileged_fixed_world_teacher=True,
            student_inputs_public_only=True,
            ordinary_PPO_eligible=False,
        )
        scored = score_episode(case, root["source_seed_id"], score)
        if not scored["completed"] or not chooser.turn_complete:
            case.update(
                status="failed", error=case.get("error", "Incomplete or over-budget turn branch")
            )
        binding = {
            "environment_id": model.actor.environment_id,
            "config_id": manifest_identifier(cfg),
            "native_seed": root["native_seed"],
            "seed_id": root["source_seed_id"],
            "partition": "train",
            "panel_purpose": "complete_turn_teacher_not_PPO",
            "model_id": model.model_id,
            "training_spec_id": score.spec_id,
            "policy_contract": CONTRACT,
            "information_scope": INFORMATION,
            "root_id": root["root_id"],
            "turn_task": task,
            "continuation_sampling_seed": random_seed(
                root["root_id"], "continuation", task["repeat"]
            ),
        }
        path = target / "episode.json"
        save_native_episode(path, case, binding)
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
        saved = read_native_episode(path, binding)
        if trace_id(saved) != digest:
            raise ValueError("Saved complete-turn delivery differs from the native episode")
        del saved
        if chooser.plan is not None:
            if proposal and identified(plan_path, "plan_id") != chooser.plan:
                raise ValueError("Proposal plan changed after its turn boundary was frozen")
            sequence = chooser.plan["steps"]
            stats = {
                "turn_decisions": len(sequence),
                "nested_selection_decisions": sum(
                    s["public_input"]["context"]["interaction"]["kind"] != "combat_turn"
                    for s in sequence
                ),
                "boundary_kind": chooser.plan["boundary"]["kind"],
            }
        else:
            stats = {}
        return {
            **outcome,
            "error": error,
            "stage": task["stage"],
            "root_id": root["root_id"],
            "plan_id": (chooser.plan["plan_id"] if chooser.plan else None)
            if proposal
            else task["plan_id"],
            "plan_path": str(plan_path.relative_to(q.root))
            if proposal and chooser.plan
            else task.get("plan_path"),
            "repeat": task["repeat"],
            "duplicate_control": task["duplicate_control"],
            "root_reached": chooser.root_reached,
            "turn_complete": chooser.turn_complete,
            "native_audit_valid": audit["valid"],
            "trace_id": digest,
            "training_return": scored["training_return"]
            if outcome["status"] == "terminal"
            else None,
            "episode_path": str(path.relative_to(q.root)),
            **stats,
            "proposal_outcome_used_for_candidate_selection": False,
            "source_seed_replay": "planned_counterfactual_not_retry_of_uncertain_delivery",
        }
    finally:
        worker.stop()
