"""Sealed native experience, exact behavior verification, and whole-episode PPO targets."""

from __future__ import annotations

import gzip
import json
import math
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import NativeActorCritic, encode_public_input
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import save_episode
from spireshift.full_run_policy import FullRunModel, score_features
from spireshift.full_run_ppo_math import Sample, log_softmax
from spireshift.training_objective import (
    RunStatus,
    TrainingOutcome,
    TrainingScoreSpec,
    score_training_outcome,
)

SCHEMA = "actual-engine-on-policy-experience-v1"


def score_episode(case: dict[str, Any], seed_id: int, score: TrainingScoreSpec) -> dict[str, Any]:
    clean = case["status"] == "terminal" and case.get("native_ending_evidence_agrees") is True
    status = (
        (RunStatus.VICTORY if case["victory"] else RunStatus.LOSS) if clean else RunStatus.ERROR
    )
    outcome = TrainingOutcome(
        seed_id,
        status,
        case["completed_acts"],
        case["maximum_floor"],
        len(case["decisions"]),
        case["cpu_seconds"],
    )
    return score_training_outcome(score, outcome)


def save_native_episode(
    path: Path, case: dict[str, Any], binding: dict[str, Any]
) -> dict[str, Any]:
    body = {
        "schema_version": SCHEMA,
        "binding": binding,
        "episode": {k: v for k, v in case.items() if k != "decisions"},
        "decision_count": len(case["decisions"]),
    }
    document = {**body, "case_id": manifest_identifier(body)}
    save_episode(path, document, case["decisions"])
    return {**document, "trace_file_sha256": _sha_file(path.with_suffix(".jsonl.gz"))}


def read_native_episode(path: Path, binding: dict[str, Any]) -> dict[str, Any]:
    doc = json.loads(path.read_text())
    body = {k: v for k, v in doc.items() if k not in {"case_id", "trace_file_sha256"}}
    if (
        doc.get("schema_version") != SCHEMA
        or doc.get("binding") != binding
        or doc.get("case_id") != manifest_identifier(body)
        or doc.get("trace_file_sha256") != _sha_file(path.with_suffix(".jsonl.gz"))
    ):
        raise ValueError("Native episode source, behavior or trace bytes changed")
    with gzip.open(path.with_suffix(".jsonl.gz"), "rt") as stream:
        decisions = [json.loads(line) for line in stream]
    if len(decisions) != doc["decision_count"]:
        raise ValueError("Native decision denominator changed")
    return {**doc["episode"], "decisions": decisions}


def verified_native_samples(
    case: dict[str, Any], model: NativeActorCritic, training_return: float, temperature: float
) -> list[Sample]:
    if (
        case.get("status") != "terminal"
        or case.get("privileged_fixture") is not False
        or case.get("recovered") is not False
        or case.get("native_ending_evidence_agrees") is not True
        or not 0 <= training_return <= 1
    ):
        raise ValueError("Incomplete, recovered or privileged games cannot supply PPO targets")
    samples = []
    for decision in case["decisions"]:
        public, choice = decision["public_input"], decision["choice"]
        rows, state = encode_public_input(
            public, model.actor.dimension, model.actor.input_normalization
        )
        action = choice["action_index"]
        if (
            choice.get("model_id") != model.model_id
            or choice.get("behavior") != "sampled_softmax"
            or choice.get("temperature") != temperature
            or choice.get("public_input_id") != manifest_identifier(public)
            or type(action) is not int
            or not 0 <= action < len(rows)
        ):
            raise ValueError(
                "Native PPO sample is stale, greedy, incomplete or from another policy"
            )
        logits = score_features(cast(FullRunModel, model.actor), rows)
        expected = log_softmax(logits, temperature)[action]
        value = model.value(state)
        if not math.isclose(
            choice["log_probability"], expected, rel_tol=0, abs_tol=1e-10
        ) or not math.isclose(choice["value"], value, rel_tol=0, abs_tol=1e-10):
            raise ValueError("Saved native behavior probability/value does not reconstruct")
        samples.append(
            Sample(rows, state, action, expected, training_return, training_return - value)
        )
    return samples
