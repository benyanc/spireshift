"""Natural prefix replay and bounded full-fight first-divergence rollouts."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import EngineQualificationConfig
from spireshift.engine_relic_worker import RelicWorker
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import log_softmax
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_natural_audit import audit
from spireshift.native_natural_data import CONTRACT, LIMITS, ending, resources
from spireshift.native_structured_policy import Chooser
from spireshift.native_turn_teacher_policy import round_number
from spireshift.training_objective import TrainingScoreSpec


def branch(
    q: EngineQualificationConfig,
    inputs: dict[str, Any],
    cfg: dict[str, Any],
    root: dict[str, Any],
    task: dict[str, Any],
    model: CachedContextModel,
    score: TrainingScoreSpec,
    target: Path,
    deadline: float,
    reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    started, thread = time.monotonic(), time.thread_time()
    worker = RelicWorker(q, inputs, target / "worker", Path(cfg["node"]), cfg["helpers_sha256"])
    actions: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    reached, turns = False, set()
    status, outcome, error = "complete", None, None
    chooser = Chooser(model, score, root["world"], False)
    try:
        current = worker.request("mount", seed=root["world"])
        for saved in root["prefix"]:
            if time.monotonic() > deadline - 20 or worker.cpu_seconds() > 128:
                raise TimeoutError("Natural prefix replay reached its finite cap")
            if manifest_identifier(current["model_input"]) != saved["public_input_id"]:
                raise ValueError(
                    "Natural source prefix mismatch; do not migrate or retry this root"
                )
            actions.append(
                {"public_input": current["model_input"], "action_index": saved["action_index"]}
            )
            current = worker.request(
                "step",
                snapshot_id=current["snapshot"]["snapshot_id"],
                action_index=saved["action_index"],
            )
        if current["model_input"] != root["public_input"]:
            raise ValueError("Natural source root differs from the repaired exact public input")
        reached = True
        while True:
            public = current["model_input"]
            outcome = ending(root["public_input"], public)
            if outcome is not None:
                break
            if public["context"]["interaction"]["kind"] == "combat_turn":
                turns.add(round_number(public))
            used = worker.cpu_seconds() + time.thread_time() - thread
            if (
                len(steps) >= LIMITS["maximum_actions"]
                or len(turns) > LIMITS["maximum_rounds"]
                or time.monotonic() - started > 60
                or time.monotonic() > deadline - 20
                or used > score.evaluation_objective.whole_run_budget
            ):
                status = "capped"
                break
            choice = chooser(public)
            assert chooser.last is not None
            encoded, _, effective, forced = chooser.last
            if forced or effective != public or not choice["combat_owned"]:
                raise ValueError("A natural fight cannot prune a menu or cross combat ownership")
            logs = log_softmax(score_features(cast(Any, model.actor), encoded), 0.8)
            action, index = choice["action_index"], len(steps)
            mutation = task.get("mutation")
            replay = task.get("replay", False)
            if replay or mutation is not None and index <= mutation["decision"]:
                assert reference is not None
                if (
                    index >= len(reference["steps"])
                    or reference["steps"][index]["public_input"] != public
                ):
                    raise ValueError("Frozen multi-turn proposal prefix or menu changed")
                action = reference["steps"][index]["action_index"]
                if mutation is not None and index == mutation["decision"]:
                    action = mutation["action"]
            if not 0 <= action < len(public["candidates"]):
                raise ValueError("Natural teacher chose an unadvertised action")
            row = {
                "public_input": public,
                "public_input_id": manifest_identifier(public),
                "action_index": action,
                "log_probabilities": list(logs),
            }
            steps.append(row)
            actions.append(row)
            current = worker.request(
                "step", snapshot_id=current["snapshot"]["snapshot_id"], action_index=action
            )
        if task.get("replay") and (
            reference is None or steps != reference["steps"] or outcome != reference["outcome"]
        ):
            raise ValueError("Confirmation did not reproduce the complete chosen public fight")
        end = resources(current["model_input"])
        native_ending = worker.request("ending") if current["facts"]["terminal"] else None
        worker.close()
        checked = audit(worker.workspace, actions, Path(cfg["node"]), deadline)
    except (ValueError, TimeoutError, OSError) as problem:
        worker.retire(str(problem))
        if not reached or "prefix" in str(problem) or "Confirmation" in str(problem):
            raise
        status, outcome, end, checked, native_ending = "failed", None, None, None, None
        error = str(problem)
    finally:
        worker.stop()
    body = {
        "schema_version": "natural-native-fight-v1",
        "contract": CONTRACT,
        "root_id": root["root_id"],
        "partition": root["partition"],
        "candidate": task.get("candidate", 0),
        "status": status,
        "outcome": outcome,
        "resources": end,
        "steps": steps,
        "public_rounds": len(turns),
        "choice_decisions": sum(len(s["public_input"]["candidates"]) > 1 for s in steps),
        "native_audit": checked,
        "DEBUG_native_ending": native_ending,
        "model_id": model.model_id,
        "root_reached": reached,
        "error": error,
        "cpu_seconds": worker.cpu_seconds() + time.thread_time() - thread,
        "wall_seconds": time.monotonic() - started,
        "ordinary_PPO_eligible": False,
        "privileged_fixed_world_teacher": True,
        "student_inputs_public_only": True,
        "game_apps_created": 0,
    }
    result = {**body, "fight_id": manifest_identifier(body)}
    atomic_json(target / "fight.json", result)
    return result
