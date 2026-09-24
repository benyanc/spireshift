from __future__ import annotations

import hashlib
import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from spireshift.bootstrap_teacher import (
    CurriculumStateSet,
    load_bootstrap_state_set_document,
    verify_bootstrap_teacher_dataset,
)
from spireshift.core.manifest import manifest_identifier
from spireshift.models import (
    _artifact_float,
    _binary_cross_entropy,
    _calibration_metrics,
    _candidate_features,
    _clip,
    _dot,
    _exact_keys,
    _finite_number,
    _integer,
    _list,
    _mapping,
    _probability,
    _quantize_artifact,
    _quantized_weights,
    _sigmoid,
    _softmax,
    _string,
    _weights_as_list,
    _weights_from_list,
    write_model_artifact,
)
from spireshift.representations import (
    ENCODER_ID,
    VECTORIZER_ID,
    CompositionalModelInput,
    model_input_from_mapping,
    vectorize_model_input,
)
from spireshift.splits import SplitManifest, SplitName

LEGACY_PRODUCTION_MODEL_TYPE = "sparse-pairwise-curriculum-multihead-v1"
LEGACY_PRODUCTION_CHECKPOINT_SCHEMA_VERSION = "production-model-checkpoint-v1"
LEGACY_PRODUCTION_REPORT_SCHEMA_VERSION = "production-model-training-report-v1"
PRODUCTION_MODEL_TYPE = "sparse-pairwise-curriculum-multihead-v2"
PRODUCTION_CHECKPOINT_SCHEMA_VERSION = "production-model-checkpoint-v2"
PRODUCTION_REPORT_SCHEMA_VERSION = "production-model-training-report-v2"
POLICY_TARGET_ID = "paired-preference-confidence-v1"
FLOOR_TARGET_ID = "candidate-maximum-floor-survival-v1"


@dataclass(frozen=True, slots=True)
class ProductionTrainingConfig:
    epochs: int = 60
    learning_rate: float = 0.005
    l2_regularization: float = 0.0001
    gradient_clip: float = 5.0
    vector_dimension: int = 4096
    interaction_dimension: int = 8192
    tactical_horizon: int = 32
    pairwise_noise_floor: float = 0.25
    calibration_bins: int = 10
    shuffle_seed: int = 0
    optimizer_id: str = "sparse-adagrad-v1"
    adagrad_epsilon: float = 1e-8
    selection_fraction: float = 0.25
    selection_salt: str = "production-base-model-selection-v1"

    def __post_init__(self) -> None:
        if self.epochs <= 0:
            raise ValueError("epochs must be positive")
        for name, value in (
            ("learning_rate", self.learning_rate),
            ("gradient_clip", self.gradient_clip),
        ):
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        if not math.isfinite(self.l2_regularization) or self.l2_regularization < 0.0:
            raise ValueError("l2_regularization must be finite and non-negative")
        if self.vector_dimension < 64 or self.interaction_dimension < 64:
            raise ValueError("model dimensions must be at least 64")
        if self.tactical_horizon <= 0:
            raise ValueError("tactical_horizon must be positive")
        if not 0.0 <= self.pairwise_noise_floor < 1.0:
            raise ValueError("pairwise_noise_floor must be in [0, 1)")
        if self.calibration_bins < 2:
            raise ValueError("calibration_bins must be at least 2")
        if self.shuffle_seed < 0:
            raise ValueError("shuffle_seed must be non-negative")
        if self.optimizer_id not in {"sparse-adagrad-v1", "legacy-sgd-v1"}:
            raise ValueError("optimizer_id is unsupported")
        if not math.isfinite(self.adagrad_epsilon) or self.adagrad_epsilon <= 0.0:
            raise ValueError("adagrad_epsilon must be finite and positive")
        if not 0.0 < self.selection_fraction < 1.0:
            raise ValueError("selection_fraction must be in (0, 1)")
        if not self.selection_salt:
            raise ValueError("selection_salt must be non-empty")

    def as_dict(self) -> dict[str, object]:
        return {
            "epochs": self.epochs,
            "learning_rate": self.learning_rate,
            "l2_regularization": self.l2_regularization,
            "gradient_clip": self.gradient_clip,
            "vector_dimension": self.vector_dimension,
            "interaction_dimension": self.interaction_dimension,
            "tactical_horizon": self.tactical_horizon,
            "pairwise_noise_floor": self.pairwise_noise_floor,
            "calibration_bins": self.calibration_bins,
            "shuffle_seed": self.shuffle_seed,
            "optimizer_id": self.optimizer_id,
            "adagrad_epsilon": self.adagrad_epsilon,
            "selection_fraction": self.selection_fraction,
            "selection_salt": self.selection_salt,
        }

    @classmethod
    def from_mapping(cls, value: object) -> ProductionTrainingConfig:
        document = _mapping(value, "production training config")
        legacy_expected = {
            "epochs",
            "learning_rate",
            "l2_regularization",
            "gradient_clip",
            "vector_dimension",
            "interaction_dimension",
            "tactical_horizon",
            "pairwise_noise_floor",
            "calibration_bins",
            "shuffle_seed",
        }
        expected = legacy_expected | {
            "optimizer_id",
            "adagrad_epsilon",
            "selection_fraction",
            "selection_salt",
        }
        fields = set(document)
        if fields != legacy_expected and fields != expected:
            raise ValueError("Production training configuration fields differ")
        legacy = fields == legacy_expected
        return cls(
            epochs=_integer(document.get("epochs"), "epochs"),
            learning_rate=_finite_number(document.get("learning_rate"), "learning_rate"),
            l2_regularization=_finite_number(
                document.get("l2_regularization"), "l2_regularization"
            ),
            gradient_clip=_finite_number(document.get("gradient_clip"), "gradient_clip"),
            vector_dimension=_integer(document.get("vector_dimension"), "vector_dimension"),
            interaction_dimension=_integer(
                document.get("interaction_dimension"), "interaction_dimension"
            ),
            tactical_horizon=_integer(document.get("tactical_horizon"), "tactical_horizon"),
            pairwise_noise_floor=_finite_number(
                document.get("pairwise_noise_floor"), "pairwise_noise_floor"
            ),
            calibration_bins=_integer(document.get("calibration_bins"), "calibration_bins"),
            shuffle_seed=_integer(document.get("shuffle_seed"), "shuffle_seed"),
            optimizer_id=(
                "legacy-sgd-v1" if legacy else _string(document.get("optimizer_id"), "optimizer_id")
            ),
            adagrad_epsilon=(
                1e-8
                if legacy
                else _finite_number(document.get("adagrad_epsilon"), "adagrad_epsilon")
            ),
            selection_fraction=(
                0.25
                if legacy
                else _finite_number(document.get("selection_fraction"), "selection_fraction")
            ),
            selection_salt=(
                "legacy-unrecorded"
                if legacy
                else _string(document.get("selection_salt"), "selection_salt")
            ),
        )


@dataclass(frozen=True, slots=True)
class ProductionPrediction:
    policy: tuple[float, ...]
    tactical_death_risk: tuple[float, ...]
    maximum_floor_reach: dict[int, tuple[float, ...]]
    source_action_ids: tuple[str, ...]
    terminal_value: None = None


@dataclass(slots=True)
class ProductionBaseModel:
    vector_dimension: int
    interaction_dimension: int
    tactical_horizon: int
    floor_thresholds: tuple[int, ...]
    policy_weights: dict[int, float] = field(default_factory=dict)
    tactical_risk_weights: dict[int, float] = field(default_factory=dict)
    tactical_risk_bias: float = 0.0
    floor_weights: dict[int, dict[int, float]] = field(default_factory=dict)
    floor_biases: dict[int, float] = field(default_factory=dict)

    def predict(self, representation: CompositionalModelInput) -> ProductionPrediction:
        vector = vectorize_model_input(representation, dimension=self.vector_dimension)
        features = tuple(
            _candidate_features(
                vector.state,
                candidate,
                self.vector_dimension,
                self.interaction_dimension,
            )
            for candidate in vector.candidates
        )
        policy = _softmax(tuple(_dot(self.policy_weights, item) for item in features))
        risks = tuple(
            _sigmoid(self.tactical_risk_bias + _dot(self.tactical_risk_weights, item))
            for item in features
        )
        floor_reach = {
            threshold: tuple(
                _sigmoid(
                    self.floor_biases.get(threshold, 0.0)
                    + _dot(self.floor_weights.get(threshold, {}), item)
                )
                for item in features
            )
            for threshold in self.floor_thresholds
        }
        return ProductionPrediction(policy, risks, floor_reach, vector.source_action_ids)


@dataclass(frozen=True, slots=True)
class ProductionTrainingResult:
    checkpoint: dict[str, Any]
    report: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _Outcome:
    maximum_floor: int
    terminal_defeat: bool
    transitions: int


@dataclass(frozen=True, slots=True)
class _ProductionExample:
    state_id: str
    run_seed: int
    decision_type: str
    representation: CompositionalModelInput
    candidate_features: tuple[dict[int, float], ...]
    preference_matrix: tuple[tuple[float, ...], ...]
    soft_policy_target: tuple[float, ...]
    policy_target_weight: float
    stability_multiplier: float
    selected_candidate_index: int
    mean_progress_utilities: tuple[float, ...]
    outcomes: tuple[tuple[_Outcome, ...], ...]


@dataclass(slots=True)
class _OptimizerState:
    policy_accumulators: dict[int, float] = field(default_factory=dict)
    soft_accumulators: dict[int, float] = field(default_factory=dict)
    risk_accumulators: dict[int, float] = field(default_factory=dict)
    risk_bias_accumulator: float = 0.0
    floor_accumulators: dict[int, dict[int, float]] = field(default_factory=dict)
    floor_bias_accumulators: dict[int, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _SelectedEpochs:
    policy: int
    soft_baseline: int
    tactical_risk: int
    floors: dict[int, int]

    @property
    def maximum(self) -> int:
        return max(
            self.policy,
            self.soft_baseline,
            self.tactical_risk,
            *self.floors.values(),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "policy": self.policy,
            "soft_target_baseline": self.soft_baseline,
            "tactical_death_risk": self.tactical_risk,
            "maximum_floor_distribution": {
                str(threshold): epoch for threshold, epoch in sorted(self.floors.items())
            },
        }


def train_production_base_model(
    *,
    train_report_path: Path,
    validation_report_path: Path,
    split_manifest: SplitManifest,
    config: ProductionTrainingConfig,
) -> ProductionTrainingResult:
    train_report, train_state_set, train_examples = _load_curriculum_examples(
        train_report_path, split_manifest=split_manifest, config=config
    )
    validation_report, validation_state_set, validation_examples = _load_curriculum_examples(
        validation_report_path, split_manifest=split_manifest, config=config
    )
    if train_state_set.partition != SplitName.TRAIN.value:
        raise ValueError("Production fitting requires a train curriculum")
    if validation_state_set.partition != SplitName.VALIDATION.value:
        raise ValueError("Production evaluation requires a validation curriculum")
    train_seeds = {example.run_seed for example in train_examples}
    validation_seeds = {example.run_seed for example in validation_examples}
    if train_seeds & validation_seeds:
        raise ValueError("Production curricula share complete-run seeds")
    if train_state_set.ruleset_manifest_id != validation_state_set.ruleset_manifest_id:
        raise ValueError("Production curricula use different rulesets")
    if train_state_set.objective_id != validation_state_set.objective_id:
        raise ValueError("Production curricula use different objectives")
    for report, label in ((train_report, "train"), (validation_report, "validation")):
        assessment = _mapping(report.get("signal_assessment"), f"{label} signal assessment")
        if assessment.get("auxiliary_policy_signal_pass") is not True:
            raise ValueError(f"{label} curriculum did not pass its auxiliary signal gate")
        summary = _mapping(report.get("summary"), f"{label} summary")
        if _integer(summary.get("terminal_victories"), "terminal victories") != 0:
            raise ValueError(
                "This curriculum trainer only admits the predeclared all-zero terminal-value regime"
            )

    floor_thresholds = _nondegenerate_floor_thresholds(train_examples)
    if not floor_thresholds:
        raise ValueError("Training curriculum has no nondegenerate maximum-floor thresholds")
    fit_examples, selection_examples, selection_runs = _split_training_examples(
        train_examples, config
    )
    selection_model = _new_production_model(floor_thresholds, config)
    history, selected_epochs = _select_training_epochs(
        selection_model,
        fit_examples,
        selection_examples,
        config,
    )
    model = _new_production_model(floor_thresholds, config)
    soft_baseline_weights, refit_metrics = _refit_selected_epochs(
        model,
        train_examples,
        selected_epochs,
        config,
    )
    _quantize_production_model(model)
    soft_baseline_weights = _quantized_weights(soft_baseline_weights)
    held_out = _evaluate_production_model(
        model,
        validation_examples,
        config,
        soft_baseline_weights=soft_baseline_weights,
    )
    train_evidence = _pairwise_evidence(train_examples, config)
    validation_evidence = _pairwise_evidence(validation_examples, config)

    checkpoint_body: dict[str, Any] = {
        "schema_version": PRODUCTION_CHECKPOINT_SCHEMA_VERSION,
        "model_type": PRODUCTION_MODEL_TYPE,
        "representation_encoder_id": ENCODER_ID,
        "vectorizer_id": VECTORIZER_ID,
        "ruleset_manifest_id": train_state_set.ruleset_manifest_id,
        "objective_id": train_state_set.objective_id,
        "split_manifest_id": split_manifest.manifest_id,
        "train_dataset_id": train_report["dataset_id"],
        "training_config": config.as_dict(),
        "heads": {
            "policy": {
                "target": POLICY_TARGET_ID,
                "weights": _weights_as_list(model.policy_weights),
            },
            "terminal_value": {
                "status": "blocked",
                "reason": "all_zero_terminal_victory_evidence",
                "weights": [],
            },
            "tactical_death_risk": {
                "target": f"terminal_defeat_within_{config.tactical_horizon}_decisions",
                "bias": _artifact_float(model.tactical_risk_bias),
                "weights": _weights_as_list(model.tactical_risk_weights),
            },
            "maximum_floor_distribution": {
                "target": FLOOR_TARGET_ID,
                "thresholds": [
                    {
                        "floor": threshold,
                        "bias": _artifact_float(model.floor_biases[threshold]),
                        "weights": _weights_as_list(model.floor_weights[threshold]),
                    }
                    for threshold in floor_thresholds
                ],
            },
        },
    }
    checkpoint = {**checkpoint_body, "model_id": manifest_identifier(checkpoint_body)}
    report_body: dict[str, Any] = {
        "schema_version": PRODUCTION_REPORT_SCHEMA_VERSION,
        "model_id": checkpoint["model_id"],
        "model_type": PRODUCTION_MODEL_TYPE,
        "train_dataset_id": train_report["dataset_id"],
        "validation_dataset_id": validation_report["dataset_id"],
        "split_manifest_id": split_manifest.manifest_id,
        "training_runs": len(train_seeds),
        "validation_runs": len(validation_seeds),
        "training_records": len(train_examples),
        "validation_records": len(validation_examples),
        "floor_thresholds": list(floor_thresholds),
        "pairwise_evidence": {
            "train": _quantize_artifact(train_evidence),
            "validation": _quantize_artifact(validation_evidence),
        },
        "model_selection": {
            "unit": "complete_run",
            "partition": "train",
            "selection_fraction": config.selection_fraction,
            "selection_salt": config.selection_salt,
            "fit_runs": selection_runs["fit"],
            "selection_runs": selection_runs["selection"],
            "fit_records": len(fit_examples),
            "selection_records": len(selection_examples),
            "selected_epochs": selected_epochs.as_dict(),
        },
        "training_history": _quantize_artifact(history),
        "refit_metrics": _quantize_artifact(refit_metrics),
        "held_out_metrics": _quantize_artifact(held_out),
        "terminal_value_status": {
            "promoted": False,
            "reason": "all_zero_terminal_victory_evidence",
            "train_victories": train_report["summary"]["terminal_victories"],
            "validation_victories": validation_report["summary"]["terminal_victories"],
        },
        "claim_scope": "production_bootstrap_auxiliary_only",
    }
    report = {**report_body, "report_id": manifest_identifier(report_body)}
    return ProductionTrainingResult(checkpoint, report)


def production_model_from_checkpoint(value: object) -> ProductionBaseModel:
    checkpoint = _mapping(value, "production model checkpoint")
    _exact_keys(
        checkpoint,
        {
            "schema_version",
            "model_id",
            "model_type",
            "representation_encoder_id",
            "vectorizer_id",
            "ruleset_manifest_id",
            "objective_id",
            "split_manifest_id",
            "train_dataset_id",
            "training_config",
            "heads",
        },
        "production model checkpoint",
    )
    model_id = _string(checkpoint.get("model_id"), "model ID")
    body = {key: item for key, item in checkpoint.items() if key != "model_id"}
    if model_id != manifest_identifier(body):
        raise ValueError("Production model checkpoint identity mismatch")
    schema_version = checkpoint.get("schema_version")
    if schema_version not in {
        LEGACY_PRODUCTION_CHECKPOINT_SCHEMA_VERSION,
        PRODUCTION_CHECKPOINT_SCHEMA_VERSION,
    }:
        raise ValueError("Unsupported production model checkpoint schema")
    expected_model_type = (
        LEGACY_PRODUCTION_MODEL_TYPE
        if schema_version == LEGACY_PRODUCTION_CHECKPOINT_SCHEMA_VERSION
        else PRODUCTION_MODEL_TYPE
    )
    if checkpoint.get("model_type") != expected_model_type:
        raise ValueError("Unsupported production model type")
    if checkpoint.get("representation_encoder_id") != ENCODER_ID:
        raise ValueError("Unsupported production representation encoder")
    if checkpoint.get("vectorizer_id") != VECTORIZER_ID:
        raise ValueError("Unsupported production vectorizer")
    config = ProductionTrainingConfig.from_mapping(checkpoint.get("training_config"))
    heads = _mapping(checkpoint.get("heads"), "production heads")
    if set(heads) != {
        "policy",
        "terminal_value",
        "tactical_death_risk",
        "maximum_floor_distribution",
    }:
        raise ValueError("Production model heads differ")
    policy = _mapping(heads.get("policy"), "policy head")
    _exact_keys(policy, {"target", "weights"}, "policy head")
    if policy.get("target") != POLICY_TARGET_ID:
        raise ValueError("Unsupported production policy target")
    terminal = _mapping(heads.get("terminal_value"), "terminal-value head")
    if terminal != {
        "status": "blocked",
        "reason": "all_zero_terminal_victory_evidence",
        "weights": [],
    }:
        raise ValueError("Production terminal-value head is not correctly blocked")
    risk = _mapping(heads.get("tactical_death_risk"), "risk head")
    _exact_keys(risk, {"target", "bias", "weights"}, "risk head")
    if risk.get("target") != f"terminal_defeat_within_{config.tactical_horizon}_decisions":
        raise ValueError("Unsupported production risk target")
    floor = _mapping(heads.get("maximum_floor_distribution"), "floor head")
    _exact_keys(floor, {"target", "thresholds"}, "floor head")
    if floor.get("target") != FLOOR_TARGET_ID:
        raise ValueError("Unsupported production floor target")
    threshold_entries = _list(floor.get("thresholds"), "floor thresholds")
    thresholds: list[int] = []
    floor_weights: dict[int, dict[int, float]] = {}
    floor_biases: dict[int, float] = {}
    for offset, raw_entry in enumerate(threshold_entries):
        entry = _mapping(raw_entry, f"floor threshold[{offset}]")
        _exact_keys(entry, {"floor", "bias", "weights"}, f"floor threshold[{offset}]")
        threshold = _integer(entry.get("floor"), "floor threshold")
        if threshold in floor_weights or threshold <= 0:
            raise ValueError("Floor thresholds must be unique and positive")
        thresholds.append(threshold)
        floor_weights[threshold] = _weights_from_list(
            entry.get("weights"),
            config.vector_dimension + config.interaction_dimension,
            f"floor {threshold} weights",
        )
        floor_biases[threshold] = _finite_number(entry.get("bias"), "floor bias")
    if thresholds != sorted(thresholds):
        raise ValueError("Floor thresholds must be sorted")
    return ProductionBaseModel(
        vector_dimension=config.vector_dimension,
        interaction_dimension=config.interaction_dimension,
        tactical_horizon=config.tactical_horizon,
        floor_thresholds=tuple(thresholds),
        policy_weights=_weights_from_list(
            policy.get("weights"),
            config.vector_dimension + config.interaction_dimension,
            "production policy weights",
        ),
        tactical_risk_weights=_weights_from_list(
            risk.get("weights"),
            config.vector_dimension + config.interaction_dimension,
            "production risk weights",
        ),
        tactical_risk_bias=_finite_number(risk.get("bias"), "risk bias"),
        floor_weights=floor_weights,
        floor_biases=floor_biases,
    )


def load_production_model_checkpoint(path: Path) -> dict[str, Any]:
    document = _load_object(path)
    production_model_from_checkpoint(document)
    return document


def load_production_training_report(
    path: Path,
    *,
    checkpoint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = _load_object(path)
    schema_version = report.get("schema_version")
    legacy_fields = {
        "schema_version",
        "report_id",
        "model_id",
        "model_type",
        "train_dataset_id",
        "validation_dataset_id",
        "split_manifest_id",
        "training_runs",
        "validation_runs",
        "training_records",
        "validation_records",
        "floor_thresholds",
        "pairwise_evidence",
        "training_history",
        "held_out_metrics",
        "terminal_value_status",
        "claim_scope",
    }
    current_fields = legacy_fields | {"model_selection", "refit_metrics"}
    _exact_keys(
        report,
        legacy_fields
        if schema_version == LEGACY_PRODUCTION_REPORT_SCHEMA_VERSION
        else current_fields,
        "production training report",
    )
    report_id = _string(report.get("report_id"), "report ID")
    body = {key: item for key, item in report.items() if key != "report_id"}
    if report_id != manifest_identifier(body):
        raise ValueError("Production training report identity mismatch")
    if schema_version not in {
        LEGACY_PRODUCTION_REPORT_SCHEMA_VERSION,
        PRODUCTION_REPORT_SCHEMA_VERSION,
    }:
        raise ValueError("Unsupported production training report schema")
    expected_model_type = (
        LEGACY_PRODUCTION_MODEL_TYPE
        if schema_version == LEGACY_PRODUCTION_REPORT_SCHEMA_VERSION
        else PRODUCTION_MODEL_TYPE
    )
    if report.get("model_type") != expected_model_type:
        raise ValueError("Unsupported production training report model type")
    if checkpoint is not None and report.get("model_id") != checkpoint.get("model_id"):
        raise ValueError("Production report references a different checkpoint")
    return report


def write_production_model_artifact(document: dict[str, Any], path: Path, *, label: str) -> None:
    write_model_artifact(document, path, label=label)


def _load_curriculum_examples(
    report_path: Path,
    *,
    split_manifest: SplitManifest,
    config: ProductionTrainingConfig,
) -> tuple[dict[str, Any], CurriculumStateSet, tuple[_ProductionExample, ...]]:
    verification = verify_bootstrap_teacher_dataset(report_path, split_manifest=split_manifest)
    if not verification.valid:
        raise ValueError("Curriculum verification failed: " + "; ".join(verification.errors))
    report = _load_object(report_path)
    state_set = load_bootstrap_state_set_document(report.get("state_set"))
    if not isinstance(state_set, CurriculumStateSet):
        raise ValueError("Production model requires curriculum-v2 state sets")
    root = report_path.parent.resolve()
    examples: list[_ProductionExample] = []
    for raw_reference in _list(report.get("cases"), "curriculum cases"):
        reference = _mapping(raw_reference, "curriculum case")
        case = _load_object(_safe_child(root, _string(reference.get("path"), "case path")))
        if case.get("status") != "completed":
            raise ValueError("Production curriculum contains a failed case")
        record = _mapping(case.get("record"), "curriculum record")
        representation = model_input_from_mapping(record.get("model_input"))
        vector = vectorize_model_input(representation, dimension=config.vector_dimension)
        features = tuple(
            _candidate_features(
                vector.state,
                candidate,
                config.vector_dimension,
                config.interaction_dimension,
            )
            for candidate in vector.candidates
        )
        target = _mapping(record.get("target"), "curriculum target")
        raw_candidates = _list(target.get("candidates"), "target candidates")
        if len(raw_candidates) != len(features):
            raise ValueError("Curriculum target and representation candidate counts differ")
        outcomes: list[tuple[_Outcome, ...]] = []
        utilities: list[float] = []
        for index, raw_candidate in enumerate(raw_candidates):
            candidate = _mapping(raw_candidate, f"candidate[{index}]")
            if candidate.get("source_action_id") != vector.source_action_ids[index]:
                raise ValueError("Curriculum candidate action is not representation aligned")
            utilities.append(
                _finite_number(candidate.get("mean_progress_utility"), "progress utility")
            )
            candidate_outcomes = tuple(
                _outcome_from_mapping(value)
                for value in _list(candidate.get("outcomes"), "candidate outcomes")
            )
            outcomes.append(candidate_outcomes)
        raw_matrix = _list(target.get("paired_preference_matrix"), "preference matrix")
        matrix = tuple(
            tuple(_probability(value, "paired preference") for value in _list(row, "row"))
            for row in raw_matrix
        )
        if len(matrix) != len(features) or any(len(row) != len(features) for row in matrix):
            raise ValueError("Curriculum pairwise preference matrix is not candidate aligned")
        soft_target = tuple(
            _probability(value, "soft policy target")
            for value in _list(target.get("soft_policy_target"), "soft policy target")
        )
        if len(soft_target) != len(features) or not math.isclose(
            sum(soft_target), 1.0, abs_tol=1e-9
        ):
            raise ValueError("Curriculum soft policy target is not candidate aligned")
        agreement = target.get("half_split_winner_agreement")
        stability = 1.0 if agreement is True else 0.5 if agreement is False else 0.0
        selected_candidate_index = _integer(
            target.get("selected_candidate_index"), "selected candidate index"
        )
        if not 0 <= selected_candidate_index < len(features):
            raise ValueError("Curriculum selected candidate index is out of range")
        examples.append(
            _ProductionExample(
                state_id=_string(record.get("state_id"), "state ID"),
                run_seed=_integer(record.get("run_seed"), "run seed"),
                decision_type=_string(record.get("decision_type"), "decision type"),
                representation=representation,
                candidate_features=features,
                preference_matrix=matrix,
                soft_policy_target=soft_target,
                policy_target_weight=_probability(
                    target.get("policy_target_weight"), "policy target weight"
                ),
                stability_multiplier=stability,
                selected_candidate_index=selected_candidate_index,
                mean_progress_utilities=tuple(utilities),
                outcomes=tuple(outcomes),
            )
        )
    return report, state_set, tuple(examples)


def _outcome_from_mapping(value: object) -> _Outcome:
    output = _mapping(value, "curriculum outcome")
    maximum_floor = output.get("maximum_floor")
    floor = 0 if maximum_floor is None else _integer(maximum_floor, "maximum floor")
    return _Outcome(
        maximum_floor=floor,
        terminal_defeat=output.get("terminal") is True and output.get("victory") is False,
        transitions=_integer(output.get("transitions"), "outcome transitions"),
    )


def _nondegenerate_floor_thresholds(
    examples: tuple[_ProductionExample, ...],
) -> tuple[int, ...]:
    floors = sorted(
        {
            outcome.maximum_floor
            for example in examples
            for row in example.outcomes
            for outcome in row
        }
    )
    thresholds: list[int] = []
    all_outcomes = [outcome for example in examples for row in example.outcomes for outcome in row]
    for threshold in floors:
        if threshold <= 0:
            continue
        positives = sum(outcome.maximum_floor >= threshold for outcome in all_outcomes)
        if 0 < positives < len(all_outcomes):
            thresholds.append(threshold)
    return tuple(thresholds)


def _new_production_model(
    floor_thresholds: tuple[int, ...], config: ProductionTrainingConfig
) -> ProductionBaseModel:
    return ProductionBaseModel(
        vector_dimension=config.vector_dimension,
        interaction_dimension=config.interaction_dimension,
        tactical_horizon=config.tactical_horizon,
        floor_thresholds=floor_thresholds,
        floor_weights={threshold: {} for threshold in floor_thresholds},
        floor_biases={threshold: 0.0 for threshold in floor_thresholds},
    )


def _split_training_examples(
    examples: tuple[_ProductionExample, ...], config: ProductionTrainingConfig
) -> tuple[
    tuple[_ProductionExample, ...],
    tuple[_ProductionExample, ...],
    dict[str, list[int]],
]:
    seeds = sorted({example.run_seed for example in examples})
    if len(seeds) < 4:
        raise ValueError("Train-owned model selection requires at least four complete runs")
    ranked = sorted(
        seeds,
        key=lambda seed: hashlib.sha256(f"{config.selection_salt}|{seed}".encode()).hexdigest(),
    )
    selection_count = min(
        len(ranked) - 1,
        max(1, round(len(ranked) * config.selection_fraction)),
    )
    selection_seeds = set(ranked[:selection_count])
    fit = tuple(example for example in examples if example.run_seed not in selection_seeds)
    selection = tuple(example for example in examples if example.run_seed in selection_seeds)
    if not fit or not selection:
        raise ValueError("Train-owned model selection subfold is empty")
    for values, label in ((fit, "fit"), (selection, "selection")):
        evidence = _pairwise_evidence(values, config)
        if float(evidence["effective_pair_weight"]) <= 0.0:
            raise ValueError(f"Train-owned {label} subfold has no pairwise evidence")
    return (
        fit,
        selection,
        {
            "fit": sorted(set(seeds) - selection_seeds),
            "selection": sorted(selection_seeds),
        },
    )


def _select_training_epochs(
    model: ProductionBaseModel,
    fit_examples: tuple[_ProductionExample, ...],
    selection_examples: tuple[_ProductionExample, ...],
    config: ProductionTrainingConfig,
) -> tuple[list[dict[str, Any]], _SelectedEpochs]:
    soft_weights: dict[int, float] = {}
    optimizer = _new_optimizer_state(model.floor_thresholds)
    rng = random.Random(config.shuffle_seed)
    best_policy = (math.inf, 1)
    best_soft = (math.inf, 1)
    best_risk = (math.inf, 1)
    best_floors = {threshold: (math.inf, 1) for threshold in model.floor_thresholds}
    history: list[dict[str, Any]] = []
    for epoch in range(1, config.epochs + 1):
        _train_production_epoch(
            model,
            soft_weights,
            fit_examples,
            optimizer,
            config,
            rng,
        )
        fit_scores = _production_objective_scores(model, soft_weights, fit_examples, config)
        selection_scores = _production_objective_scores(
            model, soft_weights, selection_examples, config
        )
        policy_score = float(selection_scores["policy_pairwise_cross_entropy"])
        soft_score = float(selection_scores["soft_target_pairwise_cross_entropy"])
        risk_score = float(selection_scores["tactical_death_risk_brier_score"])
        if policy_score < best_policy[0]:
            best_policy = (policy_score, epoch)
        if soft_score < best_soft[0]:
            best_soft = (soft_score, epoch)
        if risk_score < best_risk[0]:
            best_risk = (risk_score, epoch)
        floor_scores = cast(dict[str, float], selection_scores["maximum_floor_brier_score"])
        for threshold in model.floor_thresholds:
            score = floor_scores[str(threshold)]
            if score < best_floors[threshold][0]:
                best_floors[threshold] = (score, epoch)
        history.append(
            {
                "epoch": epoch,
                "fit": fit_scores,
                "selection": selection_scores,
            }
        )
    return history, _SelectedEpochs(
        policy=best_policy[1],
        soft_baseline=best_soft[1],
        tactical_risk=best_risk[1],
        floors={threshold: value[1] for threshold, value in best_floors.items()},
    )


def _refit_selected_epochs(
    model: ProductionBaseModel,
    examples: tuple[_ProductionExample, ...],
    selected: _SelectedEpochs,
    config: ProductionTrainingConfig,
) -> tuple[dict[int, float], dict[str, Any]]:
    soft_weights: dict[int, float] = {}
    optimizer = _new_optimizer_state(model.floor_thresholds)
    rng = random.Random(config.shuffle_seed)
    for epoch in range(1, selected.maximum + 1):
        _train_production_epoch(
            model,
            soft_weights,
            examples,
            optimizer,
            config,
            rng,
            active_policy=epoch <= selected.policy,
            active_soft=epoch <= selected.soft_baseline,
            active_risk=epoch <= selected.tactical_risk,
            active_floors={
                threshold for threshold, limit in selected.floors.items() if epoch <= limit
            },
        )
    return soft_weights, _production_objective_scores(model, soft_weights, examples, config)


def _new_optimizer_state(floor_thresholds: tuple[int, ...]) -> _OptimizerState:
    return _OptimizerState(
        floor_accumulators={threshold: {} for threshold in floor_thresholds},
        floor_bias_accumulators={threshold: 0.0 for threshold in floor_thresholds},
    )


def _train_production_epoch(
    model: ProductionBaseModel,
    soft_weights: dict[int, float],
    examples: tuple[_ProductionExample, ...],
    optimizer: _OptimizerState,
    config: ProductionTrainingConfig,
    rng: random.Random,
    *,
    active_policy: bool = True,
    active_soft: bool = True,
    active_risk: bool = True,
    active_floors: set[int] | None = None,
) -> None:
    selected_floors = set(model.floor_thresholds) if active_floors is None else active_floors
    order = list(range(len(examples)))
    rng.shuffle(order)
    for example_index in order:
        example = examples[example_index]
        if active_policy:
            for left in range(len(example.candidate_features)):
                for right in range(left + 1, len(example.candidate_features)):
                    target = example.preference_matrix[left][right]
                    confidence = _pair_confidence(target, example, config)
                    if confidence == 0.0:
                        continue
                    left_features = example.candidate_features[left]
                    right_features = example.candidate_features[right]
                    probability = _sigmoid(
                        _dot(model.policy_weights, left_features)
                        - _dot(model.policy_weights, right_features)
                    )
                    error = confidence * (probability - target)
                    _update_production_weights(
                        model.policy_weights,
                        optimizer.policy_accumulators,
                        left_features,
                        error,
                        config,
                    )
                    _update_production_weights(
                        model.policy_weights,
                        optimizer.policy_accumulators,
                        right_features,
                        -error,
                        config,
                    )
        if active_soft and example.policy_target_weight > 0.0:
            probabilities = _softmax(
                tuple(_dot(soft_weights, features) for features in example.candidate_features)
            )
            for probability, target, features in zip(
                probabilities,
                example.soft_policy_target,
                example.candidate_features,
                strict=True,
            ):
                _update_production_weights(
                    soft_weights,
                    optimizer.soft_accumulators,
                    features,
                    example.policy_target_weight * (probability - target),
                    config,
                )
        for features, outcomes in zip(example.candidate_features, example.outcomes, strict=True):
            if active_risk:
                risk_target = sum(
                    outcome.terminal_defeat and outcome.transitions <= config.tactical_horizon
                    for outcome in outcomes
                ) / len(outcomes)
                risk_probability = _sigmoid(
                    model.tactical_risk_bias + _dot(model.tactical_risk_weights, features)
                )
                risk_error = risk_probability - risk_target
                _update_production_weights(
                    model.tactical_risk_weights,
                    optimizer.risk_accumulators,
                    features,
                    risk_error,
                    config,
                )
                model.tactical_risk_bias, optimizer.risk_bias_accumulator = _update_production_bias(
                    model.tactical_risk_bias,
                    optimizer.risk_bias_accumulator,
                    risk_error,
                    config,
                )
            for threshold in sorted(selected_floors):
                floor_target = sum(
                    outcome.maximum_floor >= threshold for outcome in outcomes
                ) / len(outcomes)
                probability = _sigmoid(
                    model.floor_biases[threshold] + _dot(model.floor_weights[threshold], features)
                )
                floor_error = probability - floor_target
                _update_production_weights(
                    model.floor_weights[threshold],
                    optimizer.floor_accumulators[threshold],
                    features,
                    floor_error,
                    config,
                )
                (
                    model.floor_biases[threshold],
                    optimizer.floor_bias_accumulators[threshold],
                ) = _update_production_bias(
                    model.floor_biases[threshold],
                    optimizer.floor_bias_accumulators[threshold],
                    floor_error,
                    config,
                )


def _production_objective_scores(
    model: ProductionBaseModel,
    soft_weights: dict[int, float],
    examples: tuple[_ProductionExample, ...],
    config: ProductionTrainingConfig,
) -> dict[str, Any]:
    pair_loss = 0.0
    soft_pair_loss = 0.0
    pair_weight = 0.0
    risk_squared_error = 0.0
    risk_samples = 0
    floor_squared_error = {threshold: 0.0 for threshold in model.floor_thresholds}
    floor_samples = {threshold: 0 for threshold in model.floor_thresholds}
    for example in examples:
        policy_scores = tuple(
            _dot(model.policy_weights, features) for features in example.candidate_features
        )
        soft_scores = tuple(_dot(soft_weights, features) for features in example.candidate_features)
        for left in range(len(policy_scores)):
            for right in range(left + 1, len(policy_scores)):
                target = example.preference_matrix[left][right]
                confidence = _pair_confidence(target, example, config)
                if confidence == 0.0:
                    continue
                pair_loss += confidence * _binary_cross_entropy(
                    _sigmoid(policy_scores[left] - policy_scores[right]), target
                )
                soft_pair_loss += confidence * _binary_cross_entropy(
                    _sigmoid(soft_scores[left] - soft_scores[right]), target
                )
                pair_weight += confidence
        for features, outcomes in zip(example.candidate_features, example.outcomes, strict=True):
            risk_probability = _sigmoid(
                model.tactical_risk_bias + _dot(model.tactical_risk_weights, features)
            )
            for outcome in outcomes:
                risk_target = float(
                    outcome.terminal_defeat and outcome.transitions <= config.tactical_horizon
                )
                risk_squared_error += (risk_probability - risk_target) ** 2
                risk_samples += 1
            for threshold in model.floor_thresholds:
                floor_probability = _sigmoid(
                    model.floor_biases[threshold] + _dot(model.floor_weights[threshold], features)
                )
                for outcome in outcomes:
                    target = float(outcome.maximum_floor >= threshold)
                    floor_squared_error[threshold] += (floor_probability - target) ** 2
                    floor_samples[threshold] += 1
    if pair_weight == 0.0 or risk_samples == 0:
        raise ValueError("Model-selection subfold lacks required outcomes")
    return {
        "policy_pairwise_cross_entropy": pair_loss / pair_weight,
        "soft_target_pairwise_cross_entropy": soft_pair_loss / pair_weight,
        "tactical_death_risk_brier_score": risk_squared_error / risk_samples,
        "maximum_floor_brier_score": {
            str(threshold): floor_squared_error[threshold] / floor_samples[threshold]
            for threshold in model.floor_thresholds
        },
    }


def _pair_confidence(
    target: float,
    example: _ProductionExample,
    config: ProductionTrainingConfig,
) -> float:
    return (
        max(0.0, abs(2.0 * target - 1.0) - config.pairwise_noise_floor)
        * example.stability_multiplier
    )


def _evaluate_production_model(
    model: ProductionBaseModel,
    examples: tuple[_ProductionExample, ...],
    config: ProductionTrainingConfig,
    *,
    soft_baseline_weights: dict[int, float],
) -> dict[str, Any]:
    pair_loss = 0.0
    pair_weight = 0.0
    pair_correct = 0
    pair_count = 0
    agreements = 0
    soft_baseline_agreements = 0
    regrets: list[float] = []
    soft_baseline_regrets: list[float] = []
    baseline_regrets: list[float] = []
    soft_baseline_pair_correct = 0
    soft_baseline_pair_loss = 0.0
    risk_pairs: list[tuple[float, float]] = []
    floor_pairs: dict[int, list[tuple[float, float]]] = {
        threshold: [] for threshold in model.floor_thresholds
    }
    by_type: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {
            "effective_pair_weight": 0.0,
            "decisive_pairs": 0,
            "correct_decisive_pairs": 0,
        }
    )
    for example in examples:
        prediction = model.predict(example.representation)
        predicted = max(range(len(prediction.policy)), key=prediction.policy.__getitem__)
        soft_baseline_scores = tuple(
            _dot(soft_baseline_weights, features) for features in example.candidate_features
        )
        soft_baseline_predicted = max(
            range(len(soft_baseline_scores)), key=soft_baseline_scores.__getitem__
        )
        agreements += int(predicted == example.selected_candidate_index)
        soft_baseline_agreements += int(soft_baseline_predicted == example.selected_candidate_index)
        best_utility = max(example.mean_progress_utilities)
        regrets.append(best_utility - example.mean_progress_utilities[predicted])
        soft_baseline_regrets.append(
            best_utility - example.mean_progress_utilities[soft_baseline_predicted]
        )
        baseline_regrets.append(best_utility - example.mean_progress_utilities[0])
        scores = [math.log(max(value, 1e-12)) for value in prediction.policy]
        for left in range(len(scores)):
            for right in range(left + 1, len(scores)):
                target = example.preference_matrix[left][right]
                confidence = (
                    max(0.0, abs(2.0 * target - 1.0) - config.pairwise_noise_floor)
                    * example.stability_multiplier
                )
                if confidence > 0.0:
                    probability = _sigmoid(scores[left] - scores[right])
                    pair_loss += confidence * _binary_cross_entropy(probability, target)
                    soft_baseline_probability = _sigmoid(
                        soft_baseline_scores[left] - soft_baseline_scores[right]
                    )
                    soft_baseline_pair_loss += confidence * _binary_cross_entropy(
                        soft_baseline_probability, target
                    )
                    pair_weight += confidence
                    type_metrics = by_type[example.decision_type]
                    type_metrics["effective_pair_weight"] = (
                        float(type_metrics["effective_pair_weight"]) + confidence
                    )
                if target <= 0.25 or target >= 0.75:
                    teacher_left = target > 0.5
                    model_left = scores[left] > scores[right]
                    pair_correct += int(teacher_left == model_left)
                    soft_baseline_left = soft_baseline_scores[left] > soft_baseline_scores[right]
                    soft_baseline_pair_correct += int(teacher_left == soft_baseline_left)
                    pair_count += 1
                    type_metrics = by_type[example.decision_type]
                    type_metrics["decisive_pairs"] = int(type_metrics["decisive_pairs"]) + 1
                    type_metrics["correct_decisive_pairs"] = int(
                        type_metrics["correct_decisive_pairs"]
                    ) + int(teacher_left == model_left)
        for candidate_index, outcomes in enumerate(example.outcomes):
            risk_probability = prediction.tactical_death_risk[candidate_index]
            risk_pairs.extend(
                (
                    risk_probability,
                    float(
                        outcome.terminal_defeat and outcome.transitions <= config.tactical_horizon
                    ),
                )
                for outcome in outcomes
            )
            for threshold in model.floor_thresholds:
                probability = prediction.maximum_floor_reach[threshold][candidate_index]
                floor_pairs[threshold].extend(
                    (probability, float(outcome.maximum_floor >= threshold)) for outcome in outcomes
                )
    typed_metrics = {}
    for decision_type, values in sorted(by_type.items()):
        decisive = int(values["decisive_pairs"])
        typed_metrics[decision_type] = {
            **values,
            "decisive_pair_accuracy": (
                int(values["correct_decisive_pairs"]) / decisive if decisive else None
            ),
        }
    if pair_weight == 0.0 or pair_count == 0:
        raise ValueError("Validation curriculum has no usable pairwise evidence")
    pairwise_cross_entropy = pair_loss / pair_weight
    pairwise_accuracy = pair_correct / pair_count
    mean_regret = sum(regrets) / len(regrets)
    source_order_regret = sum(baseline_regrets) / len(baseline_regrets)
    soft_pairwise_cross_entropy = soft_baseline_pair_loss / pair_weight
    soft_pairwise_accuracy = soft_baseline_pair_correct / pair_count
    soft_mean_regret = sum(soft_baseline_regrets) / len(soft_baseline_regrets)
    auxiliary_checks = {
        "pairwise_cross_entropy_below_uniform": pairwise_cross_entropy < math.log(2.0),
        "decisive_pair_accuracy_above_chance": pairwise_accuracy > 0.5,
        "regret_below_source_order": mean_regret < source_order_regret,
        "pairwise_cross_entropy_below_soft_target": (
            pairwise_cross_entropy < soft_pairwise_cross_entropy
        ),
    }
    return {
        "policy": {
            "hard_teacher_action_agreement": agreements / len(examples),
            "weighted_pairwise_cross_entropy": pairwise_cross_entropy,
            "effective_pair_weight": pair_weight,
            "decisive_pairs": pair_count,
            "decisive_pair_accuracy": pairwise_accuracy,
            "mean_progress_utility_regret": mean_regret,
            "source_order_mean_progress_utility_regret": source_order_regret,
            "soft_target_baseline": {
                "hard_teacher_action_agreement": soft_baseline_agreements / len(examples),
                "weighted_pairwise_cross_entropy": soft_pairwise_cross_entropy,
                "decisive_pair_accuracy": soft_pairwise_accuracy,
                "mean_progress_utility_regret": soft_mean_regret,
            },
            "auxiliary_policy_gate": {
                "passed": all(auxiliary_checks.values()),
                "checks": auxiliary_checks,
            },
            "by_decision_type": typed_metrics,
        },
        "terminal_value": {
            "status": "blocked",
            "reason": "all_zero_terminal_victory_evidence",
        },
        "tactical_death_risk": _calibration_with_baseline(risk_pairs, config.calibration_bins),
        "maximum_floor_distribution": {
            str(threshold): _calibration_with_baseline(pairs, config.calibration_bins)
            for threshold, pairs in floor_pairs.items()
        },
    }


def _pairwise_evidence(
    examples: tuple[_ProductionExample, ...],
    config: ProductionTrainingConfig,
) -> dict[str, Any]:
    by_type: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"states": 0, "pairs": 0, "decisive_pairs": 0, "effective_pair_weight": 0.0}
    )
    for example in examples:
        values = by_type[example.decision_type]
        values["states"] = int(values["states"]) + 1
        for left in range(len(example.preference_matrix)):
            for right in range(left + 1, len(example.preference_matrix)):
                target = example.preference_matrix[left][right]
                values["pairs"] = int(values["pairs"]) + 1
                values["decisive_pairs"] = int(values["decisive_pairs"]) + int(
                    target <= 0.25 or target >= 0.75
                )
                values["effective_pair_weight"] = (
                    float(values["effective_pair_weight"])
                    + max(0.0, abs(2.0 * target - 1.0) - config.pairwise_noise_floor)
                    * example.stability_multiplier
                )
    return {
        "states": len(examples),
        "pairs": sum(int(values["pairs"]) for values in by_type.values()),
        "decisive_pairs": sum(int(values["decisive_pairs"]) for values in by_type.values()),
        "effective_pair_weight": sum(
            float(values["effective_pair_weight"]) for values in by_type.values()
        ),
        "by_decision_type": dict(sorted(by_type.items())),
    }


def _quantize_production_model(model: ProductionBaseModel) -> None:
    model.policy_weights = _quantized_weights(model.policy_weights)
    model.tactical_risk_weights = _quantized_weights(model.tactical_risk_weights)
    model.tactical_risk_bias = _artifact_float(model.tactical_risk_bias)
    model.floor_weights = {
        threshold: _quantized_weights(weights) for threshold, weights in model.floor_weights.items()
    }
    model.floor_biases = {
        threshold: _artifact_float(value) for threshold, value in model.floor_biases.items()
    }


def _update_production_weights(
    weights: dict[int, float],
    accumulators: dict[int, float],
    features: dict[int, float],
    error: float,
    config: ProductionTrainingConfig,
) -> None:
    for index, value in features.items():
        current = weights.get(index, 0.0)
        gradient = _clip(
            error * value + config.l2_regularization * current,
            config.gradient_clip,
        )
        if config.optimizer_id == "legacy-sgd-v1":
            step = config.learning_rate * gradient
        else:
            accumulated = accumulators.get(index, 0.0) + gradient * gradient
            accumulators[index] = accumulated
            step = config.learning_rate * gradient / math.sqrt(accumulated + config.adagrad_epsilon)
        updated = current - step
        if abs(updated) < 1e-15:
            weights.pop(index, None)
        else:
            weights[index] = updated


def _update_production_bias(
    bias: float,
    accumulator: float,
    error: float,
    config: ProductionTrainingConfig,
) -> tuple[float, float]:
    gradient = _clip(error, config.gradient_clip)
    if config.optimizer_id == "legacy-sgd-v1":
        return bias - config.learning_rate * gradient, accumulator
    accumulated = accumulator + gradient * gradient
    step = config.learning_rate * gradient / math.sqrt(accumulated + config.adagrad_epsilon)
    return bias - step, accumulated


def _calibration_with_baseline(pairs: list[tuple[float, float]], bins: int) -> dict[str, Any]:
    metrics = _calibration_metrics(pairs, bins)
    prevalence = sum(outcome for _, outcome in pairs) / len(pairs)
    baseline_brier = prevalence * (1.0 - prevalence)
    brier = _finite_number(metrics.get("brier_score"), "Brier score")
    return {
        **metrics,
        "outcome_prevalence": prevalence,
        "constant_rate_brier_score": baseline_brier,
        "brier_skill_score": (None if baseline_brier == 0.0 else 1.0 - brier / baseline_brier),
    }


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load JSON object {path}: {error}") from error
    return _mapping(value, str(path))


def _safe_child(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if path != root and root not in path.parents:
        raise ValueError("Curriculum case path escapes the dataset root")
    return path
