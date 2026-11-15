"""One fresh isolated native full-run branch with exact public prefix verification."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, save_native_episode, score_episode
from spireshift.engine_qualification import EngineQualificationConfig
from spireshift.engine_selection_audit import audit_selection_worker
from spireshift.engine_selection_worker import SCRIPT, SelectionWorker
from spireshift.full_run_experience import atomic_json
from spireshift.native_combat_teacher_data import (
    CONTRACT,
    INFORMATION,
    ReplayChooser,
    sampling_seed,
    trace_id,
)
from spireshift.native_context_cache import CachedContextModel
from spireshift.training_objective import TrainingScoreSpec


def branch(
    q: EngineQualificationConfig,
    cfg: dict[str, Any],
    inputs: dict[str, Any],
    target: Path,
    node: Path,
    root: dict[str, Any],
    action: int,
    repeat: int,
    model: CachedContextModel,
    score: TrainingScoreSpec,
    deadline: float,
    *,
    duplicate: bool = False,
) -> dict[str, Any]:
    chooser = ReplayChooser(root, action, repeat, model, score, cfg["temperature"])
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
        case.update(
            worker_workspace="worker",
            policy_contract=CONTRACT,
            teacher_experiment=True,
            privileged_fixed_world_teacher=True,
            student_inputs_public_only=True,
            ordinary_PPO_eligible=False,
        )
        scored = score_episode(case, root["source_seed_id"], score)
        if not scored["completed"]:
            case.update(
                status="failed", error=case.get("error", "Outside admitted whole-run budget")
            )
        binding = {
            "environment_id": model.actor.environment_id,
            "config_id": manifest_identifier(cfg),
            "native_seed": root["native_seed"],
            "seed_id": root["source_seed_id"],
            "partition": "train",
            "panel_purpose": "teacher_comparison_not_PPO",
            "model_id": model.model_id,
            "training_spec_id": score.spec_id,
            "policy_contract": CONTRACT,
            "information_scope": INFORMATION,
            "root_id": root["root_id"],
            "forced_root_action": action,
            "continuation_sampling_seed": sampling_seed(root["root_id"], repeat),
        }
        path = target / "episode.json"
        save_native_episode(path, case, binding)
        if case["status"] == "terminal":
            worker.close()
        else:
            worker.retire(case.get("error", "Teacher branch failed"))
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
            raise ValueError("Saved teacher branch no longer matches native delivery")
        return {
            **outcome,
            "error": error,
            "action": action,
            "repeat": repeat,
            "duplicate_control": duplicate,
            "root_reached": chooser.root_reached,
            "root_successor_kind": chooser.root_successor_kind,
            "native_audit_valid": audit["valid"],
            "trace_id": digest,
            "training_return": scored["training_return"] if scored["completed"] else None,
            "episode_path": str(path.relative_to(q.root)),
            "source_seed_replay": "planned_counterfactual_not_retry_of_uncertain_delivery",
        }
    finally:
        worker.stop()
