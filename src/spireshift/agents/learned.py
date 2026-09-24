from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from spireshift.core.manifest import RulesetIdentity
from spireshift.core.types import LegalAction, Observation
from spireshift.production_models import (
    ProductionBaseModel,
    load_production_model_checkpoint,
    load_production_training_report,
    production_model_from_checkpoint,
)
from spireshift.representations import build_model_input


@dataclass(frozen=True, slots=True)
class ProductionPolicyDecision:
    representation_hash: str
    source_action_ids: tuple[str, ...]
    selected_candidate_index: int
    selected_action: LegalAction
    policy: tuple[float, ...]
    tactical_death_risk: tuple[float, ...]
    maximum_floor_reach: dict[int, tuple[float, ...]]
    inference_seconds: float


class ProductionCheckpointPolicy:
    """Candidate-aligned public-state inference for an admitted curriculum checkpoint."""

    def __init__(
        self,
        *,
        checkpoint: dict[str, object],
        training_report: dict[str, object],
        ruleset: RulesetIdentity,
    ) -> None:
        model = production_model_from_checkpoint(checkpoint)
        model_id = checkpoint.get("model_id")
        if not isinstance(model_id, str):
            raise ValueError("Production checkpoint has no model identity")
        if checkpoint.get("ruleset_manifest_id") != ruleset.manifest_id:
            raise ValueError("Production checkpoint ruleset differs from inference ruleset")
        if checkpoint.get("objective_id") != "terminal-victory-v1":
            raise ValueError("Production checkpoint objective is not terminal victory")
        if training_report.get("model_id") != model_id:
            raise ValueError("Production training report references another checkpoint")
        held_out = training_report.get("held_out_metrics")
        if not isinstance(held_out, dict):
            raise ValueError("Production training report has no held-out metrics")
        policy_metrics = held_out.get("policy")
        if not isinstance(policy_metrics, dict):
            raise ValueError("Production training report has no policy metrics")
        gate = policy_metrics.get("auxiliary_policy_gate")
        if not isinstance(gate, dict) or gate.get("passed") is not True:
            raise ValueError("Production checkpoint did not pass its auxiliary policy gate")
        self.policy_id = f"production-checkpoint-policy-v1:{model_id}"
        self.model_id = model_id
        self.ruleset = ruleset
        self._model: ProductionBaseModel = model

    @classmethod
    def from_paths(
        cls,
        checkpoint_path: Path,
        training_report_path: Path,
        *,
        ruleset: RulesetIdentity,
    ) -> ProductionCheckpointPolicy:
        checkpoint = load_production_model_checkpoint(checkpoint_path)
        report = load_production_training_report(training_report_path, checkpoint=checkpoint)
        return cls(checkpoint=checkpoint, training_report=report, ruleset=ruleset)

    def predict(
        self,
        observation: Observation,
        legal_actions: Sequence[LegalAction],
    ) -> ProductionPolicyDecision:
        actions = tuple(legal_actions)
        if not actions:
            raise ValueError("Policy cannot act without legal actions")
        started = time.perf_counter()
        representation = build_model_input(self.ruleset, observation, actions)
        prediction = self._model.predict(representation)
        inference_seconds = time.perf_counter() - started
        expected_action_ids = tuple(action.action_id for action in actions)
        if prediction.source_action_ids != expected_action_ids:
            raise RuntimeError("Production prediction is not aligned to legal candidates")
        selected_index = max(
            range(len(prediction.policy)),
            key=lambda index: (prediction.policy[index], -index),
        )
        return ProductionPolicyDecision(
            representation_hash=representation.representation_hash,
            source_action_ids=prediction.source_action_ids,
            selected_candidate_index=selected_index,
            selected_action=actions[selected_index],
            policy=prediction.policy,
            tactical_death_risk=prediction.tactical_death_risk,
            maximum_floor_reach=prediction.maximum_floor_reach,
            inference_seconds=inference_seconds,
        )

    def choose_action(
        self,
        observation: Observation,
        legal_actions: Sequence[LegalAction],
    ) -> LegalAction:
        return self.predict(observation, legal_actions).selected_action
