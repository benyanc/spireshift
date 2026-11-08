"""Admit complete model-sampled native games and group their atomic answers."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from spireshift import native_win4_game
from spireshift.core.manifest import manifest_identifier
from spireshift.native_a8_boss_game import worker
from spireshift.native_a8_own_policy import CONTRACT, OwnPolicy
from spireshift.native_a8_own_ppo import Decision, Factor
from spireshift.native_a8_paired_report import diagnostics
from spireshift.native_a8_rescue_game import TRACE, decisions, receipt
from spireshift.native_compact_training import PackedRow
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_flow_verification_v12 import records
from spireshift.native_structured_model import encode
from spireshift.native_value_credit import ValueRun, public_value_features
from spireshift.native_win4_plan import PLAN, AnswerPolicy
from spireshift.training_objective import (
    RunStatus,
    TrainingOutcome,
    TrainingScoreSpec,
    score_training_outcome,
)

FrameChoice = tuple[dict[str, Any], dict[str, Any]]


def groups(directory: Path, model_id: str) -> Iterator[list[FrameChoice]]:
    """Stream a journal already reconstructed from raw inputs and native receipts."""
    raw = records(directory / "worker/public-observations.jsonl.gz")
    pending: list[FrameChoice] = []
    successor = None
    for (_, frame, delivered), row in zip(decisions(directory / TRACE), raw, strict=True):
        snapshot = row["snapshot"]
        snapshot_id = frame["observation"]["snapshot_id"]
        if snapshot["snapshot_id"] != snapshot_id or (
            successor is not None and successor != snapshot_id
        ):
            raise ValueError("Observed native successor differs from the delivery receipt")
        if delivered is None:
            if pending:
                raise ValueError("An incomplete answer supplies no native decision")
            continue

        menu, actions = snapshot["bound_actions"], frame["actions"]
        native = menu["actions"]
        if (
            menu["status"] != "complete"
            or menu["total_count"] != len(native)
            or sorted(a["raw_index"] for a in actions) != list(range(len(native)))
            or any(
                a["bound_action_id"] != native[a["raw_index"]]["bound_action_id"] for a in actions
            )
        ):
            raise ValueError("Every advertised native binding must reach the model")

        public, choice, ack = frame["public_input"], delivered["choice"], delivered["receipt"]
        index, logp = choice["action_index"], choice["log_probability"]
        domain, successor = ack["delivery_domain"], ack["successor_snapshot_id"]
        if (
            choice["policy_contract"] != CONTRACT
            or choice["model_id"] != model_id
            or choice["behavior"] != "sampled_softmax"
            or choice["draw_used"] is not True
            or choice["navigation_only"] is not False
            or choice.get("intervention") is not None
            or choice["optimizer_updates"] != 0
            or choice["effective_input_id"] != choice["public_input_id"]
            or len(actions) != len(public["candidates"])
            or type(index) is not int
            or not 0 <= index < len(actions)
            or choice["effective_action_index"] != index
            or not math.isfinite(logp)
            or logp > 0
            or not successor
            or choice["bound_action_id"] != actions[index]["bound_action_id"]
            or ack != receipt(frame, choice, domain, successor)
        ):
            raise ValueError("Experience requires an exact full-menu sample and delivered binding")

        answer = choice.get("answer_plan")
        if answer is None:
            if pending or domain != "native":
                raise ValueError("A local factor cannot become standalone experience")
            yield [(frame, choice)]
            continue

        origin = pending[0][0] if pending else frame
        verb = public["candidates"][index]["verb"]
        complete = verb in {"confirm", "cancel"}
        if (
            verb not in {"select", "confirm", "cancel"}
            or answer["contract"] != PLAN
            or answer["factor_index"] != len(pending)
            or answer["answer_id"]
            != manifest_identifier({"atomic_answer_origin": origin["binding_id"]})
            or answer["standalone_game_decision"] is not False
            or answer["complete"] is not complete
            or domain != ("native" if complete else "local_answer_factor")
        ):
            raise ValueError("Conditional factors must lead to one exact native answer")
        pending.append((frame, choice))
        joint = math.fsum(c["log_probability"] for _, c in pending)
        if not math.isclose(
            answer["joint_behavior_log_probability"], joint, rel_tol=0, abs_tol=1e-10
        ):
            raise ValueError("Joint behavior probability differs from the conditional factors")
        if complete:
            yield pending
            pending = []


def policy(
    context: dict[str, Any], start: dict[str, Any], variant: str, model: CachedContextModel
) -> AnswerPolicy:
    if (
        variant != "own_policy"
        or start["kind"] != "natural_training"
        or start["save_path"] is not None
    ):
        raise ValueError("Full-run experience requires fresh normal starts and model-only play")
    return AnswerPolicy(OwnPolicy(model, context["score"], start["seed"]))


def play(
    context: dict[str, Any],
    task: dict[str, Any],
    target: Path,
    model: CachedContextModel,
    deadline: float,
) -> dict[str, Any]:
    start = native_win4_game.write(
        target / "start.json",
        {
            "scenario": task,
            "seed": task["seed"],
            "kind": "natural_training",
            "status": "ready",
            "save_path": None,
            "evaluation_eligible": task["partition"] == "development",
            "setup_worlds": [],
        },
    )
    # Both execution and independent replay use the new policy. The historical
    # worker, converter and episode verifier are pinned by earlier experiments.
    with patch.multiple(native_win4_game, policy=policy, worker=worker):
        episode = native_win4_game.episode(
            context, start, "own_policy", target, deadline, model=model
        )

    total = local = 0
    for group in groups(target, model.model_id):
        total += 1
        local += len(group) - 1
    if (
        total != episode["actual_deliveries_independently_verified"]
        or local != episode["local_answer_factors"]
        or episode["model_id"] != model.model_id
    ):
        raise ValueError("Native deliveries or their behavior checkpoint differ")
    ending = episode["native_ending"]
    if episode["status"] == "complete" and (
        episode["native_terminal"] is not True
        or not ending
        or ending["native_ending_evidence_agrees"] is not True
        or ending["private_final_identity"]["seed"] != task["seed"]
    ):
        raise ValueError("Complete normal starts require an exact native ending")
    cpu = ending["usage"]["native_cpu_seconds"] if ending else None
    capped = episode["status"] == "capped" or (
        cpu is not None and cpu > context["score"].evaluation_objective.whole_run_budget
    )
    won = episode["full_run_win"] and not capped
    outcome = "capped" if capped else "win" if won else "loss"
    return {
        "task": task,
        "policy_contract": CONTRACT,
        "outcome": outcome,
        "model_id": model.model_id,
        "episode_report_id": episode["report_id"],
        "initial_public_input_id": episode["initial_public_input_id"],
        "native_cpu_seconds": cpu,
        "native_decisions": total,
        "local_answer_factors": local,
        **diagnostics(target / TRACE, won),
    }


def samples(
    directory: Path,
    result: dict[str, Any],
    model: CachedContextModel,
    score: TrainingScoreSpec,
    partition: str,
    round_index: int,
) -> tuple[list[Decision], ValueRun, Counter[str]]:
    task = result["task"]
    if (
        partition not in {"train", "control"}
        or task["partition"] != partition
        or task["round"] != round_index
        or result["policy_contract"] != CONTRACT
        or result["model_id"] != model.model_id
        or result["outcome"] not in {"win", "loss"}
    ):
        raise ValueError("Reject held-out, incomplete or foreign-policy experience")
    outcome = TrainingOutcome(
        task["seed_id"],
        RunStatus.VICTORY if result["outcome"] == "win" else RunStatus.LOSS,
        result["completed_acts"],
        result["maximum_floor"],
        result["native_decisions"],
        result["native_cpu_seconds"],
    )
    scored = score_training_outcome(score, outcome)
    if not scored["completed"]:
        raise ValueError("A capped game supplies no PPO experience")
    target = scored["training_return"]
    features, potentials, behavior_values, choices = [], [], [], []
    grouped: list[Decision] = []
    families: Counter[str] = Counter()
    for group in groups(directory, model.model_id):
        factors, states = [], []
        for frame, choice in group:
            rows, state = encode(frame["public_input"], model, score)
            packed = tuple(cast(dict[int, float], PackedRow(row)) for row in rows)
            factors.append(Factor(packed, choice["action_index"]))
            states.append(state)
        frame, first_choice = group[0]
        value_features, potential = public_value_features(frame["public_input"], score)
        features.append(value_features)
        potentials.append(potential)
        behavior_values.append(first_choice["value"])
        choices.append(max(len(f.rows) for f in factors))
        families[frame["source_family"]] += 1
        logp = math.fsum(choice["log_probability"] for _, choice in group)
        grouped.append(Decision(tuple(factors), states[0], logp, target, 0.0))
    if len(grouped) != result["native_decisions"]:
        raise ValueError("Training requires exactly one sample per delivered native decision")
    return (
        grouped,
        ValueRun(
            task["seed_id"],
            round_index,
            target,
            tuple(features),
            tuple(potentials),
            tuple(behavior_values),
            tuple(choices),
        ),
        families,
    )
