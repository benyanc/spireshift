"""Exact observed-prefix plans with up to three changed choices, then greedy play."""

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
from spireshift.native_coordinated_data import CONTRACT, LIMITS
from spireshift.native_natural_audit import audit
from spireshift.native_natural_data import ending, resources
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
    replay: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plan = task.get("plan")
    if plan is not None and (
        manifest_identifier({k: v for k, v in plan.items() if k != "plan_id"}) != plan["plan_id"]
        or not 1 <= len(plan["edits"]) <= 3
        or len(plan["forced"]) > LIMITS["maximum_actions"]
    ):
        raise ValueError("Preserve the exact observed coordinated proposal")
    started, thread = time.monotonic(), time.thread_time()
    worker = RelicWorker(q, inputs, target / "worker", Path(cfg["node"]), cfg["helpers_sha256"])
    actions: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    reached, turns = False, set()
    status, outcome, error = "complete", None, None
    chooser = Chooser(model, score, root["world"], False)

    def request(command: str, **values: Any) -> dict[str, Any]:
        remaining = min(started + 60, deadline - 20) - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Coordinated whole-path cap includes the saved opening")
        return worker.request(command, timeout=min(20, remaining), **values)

    try:
        current = request("mount", seed=root["world"])
        for saved in root["prefix"]:
            if time.monotonic() > min(started + 60, deadline - 20) or worker.cpu_seconds() > 128:
                raise TimeoutError("Coordinated root prefix reached its finite cap")
            if manifest_identifier(current["model_input"]) != saved["public_input_id"]:
                raise ValueError("Coordinated source prefix mismatch; preserve evidence")
            actions.append(
                {"public_input": current["model_input"], "action_index": saved["action_index"]}
            )
            current = request(
                "step",
                snapshot_id=current["snapshot"]["snapshot_id"],
                action_index=saved["action_index"],
            )
        if current["model_input"] != root["public_input"]:
            raise ValueError("Coordinated root prefix differs from exact public input")
        reached = True
        while True:
            public = current["model_input"]
            outcome = ending(root["public_input"], public)
            if outcome is not None:
                break
            if public["context"]["interaction"]["kind"] == "combat_turn":
                turns.add(round_number(public))
            if (
                len(steps) >= LIMITS["maximum_actions"]
                or len(turns) > LIMITS["maximum_rounds"]
                or time.monotonic() - started > 60
                or time.monotonic() > deadline - 20
                or worker.cpu_seconds() + time.thread_time() - thread
                > score.evaluation_objective.whole_run_budget
            ):
                status = "capped"
                break
            choice = chooser(public)
            assert chooser.last is not None
            encoded, _, effective, forced = chooser.last
            if forced or effective != public or not choice["combat_owned"]:
                raise ValueError("Coordinated search cannot prune or leave combat ownership")
            logs = log_softmax(score_features(cast(Any, model.actor), encoded), 0.8)
            action, index = choice["action_index"], len(steps)
            sequence = replay["steps"] if replay is not None else plan["forced"] if plan else []
            if index < len(sequence):
                expected = sequence[index]
                if expected["public_input_id"] != manifest_identifier(public):
                    raise ValueError("Coordinated observed plan prefix mismatch")
                action = expected["action_index"]
            elif replay is not None:
                raise ValueError("Coordinated confirmation has extra public actions")
            if not 0 <= action < len(public["candidates"]):
                raise ValueError("Coordinated plan selected an unadvertised action")
            row = {
                "public_input": public,
                "public_input_id": manifest_identifier(public),
                "action_index": action,
                "log_probabilities": list(logs),
            }
            steps.append(row)
            actions.append(row)
            current = request(
                "step", snapshot_id=current["snapshot"]["snapshot_id"], action_index=action
            )
        if status == "complete" and plan and len(steps) < len(plan["forced"]):
            raise ValueError("Coordinated observed plan prefix ended before its forced edits")
        if replay is not None and (
            status != "complete" or steps != replay["steps"] or outcome != replay["outcome"]
        ):
            raise ValueError("Coordinated confirmation did not reproduce its full trace")
        end = resources(current["model_input"])
        native = request("ending") if current["facts"]["terminal"] else None
        worker.close()
        checked = audit(worker.workspace, actions, Path(cfg["node"]), deadline)
    except (ValueError, TimeoutError, OSError) as problem:
        worker.retire(str(problem))
        if not isinstance(problem, TimeoutError) and (
            not reached or "prefix" in str(problem) or "confirmation" in str(problem)
        ):
            raise
        status = "capped" if isinstance(problem, TimeoutError) else "failed"
        outcome, end, checked, native = None, None, None, None
        error = str(problem)
    finally:
        worker.stop()
    edits = replay["edits"] if replay else plan["edits"] if plan else []
    executed = [e for e in edits if e["decision"] < len(steps)]
    edited_rounds = set()
    current_round = round_number(root["public_input"])
    for i, s in enumerate(steps):
        if s["public_input"]["context"]["interaction"]["kind"] == "combat_turn":
            current_round = round_number(s["public_input"])
        if any(e["decision"] == i for e in executed):
            edited_rounds.add(current_round)
    body = {
        "schema_version": "coordinated-native-fight-v1",
        "contract": CONTRACT,
        "root_id": root["root_id"],
        "partition": root["partition"],
        "entry": root["entry"],
        "candidate": task.get("candidate", 0),
        "arm": task.get("arm", "reference"),
        "edits": edits,
        "executed_edits": len(executed),
        "edited_rounds": sorted(edited_rounds),
        "plan_id": plan["plan_id"] if plan else None,
        "status": status,
        "outcome": outcome,
        "resources": end,
        "steps": steps,
        "public_rounds": len(turns),
        "choice_decisions": sum(len(s["public_input"]["candidates"]) > 1 for s in steps),
        "native_audit": checked,
        "DEBUG_native_ending": native,
        "model_id": model.model_id,
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
