from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.representations import (
    ENCODER_ID,
    VECTORIZER_ID,
    CompositionalModelInput,
    SparseEntry,
    model_input_from_mapping,
    vectorize_model_input,
)
from spireshift.splits import SplitManifest, SplitName
from spireshift.teacher_data import verify_teacher_dataset

MODEL_TYPE = "sparse-factorized-multihead-v1"
MODEL_CHECKPOINT_SCHEMA_VERSION = "model-checkpoint-v1"
MODEL_TRAINING_REPORT_SCHEMA_VERSION = "model-training-report-v1"
ARTIFACT_FLOAT_DECIMALS = 12


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    epochs: int = 80
    learning_rate: float = 0.03
    l2_regularization: float = 0.0001
    gradient_clip: float = 5.0
    vector_dimension: int = 4096
    interaction_dimension: int = 8192
    tactical_horizon: int = 1
    calibration_bins: int = 10
    shuffle_seed: int = 0

    def __post_init__(self) -> None:
        if self.epochs <= 0:
            raise ValueError("epochs must be positive")
        if not math.isfinite(self.learning_rate) or self.learning_rate <= 0:
            raise ValueError("learning_rate must be finite and positive")
        if not math.isfinite(self.l2_regularization) or self.l2_regularization < 0:
            raise ValueError("l2_regularization must be finite and non-negative")
        if not math.isfinite(self.gradient_clip) or self.gradient_clip <= 0:
            raise ValueError("gradient_clip must be finite and positive")
        if self.vector_dimension < 64:
            raise ValueError("vector_dimension must be at least 64")
        if self.interaction_dimension < 64:
            raise ValueError("interaction_dimension must be at least 64")
        if self.tactical_horizon <= 0:
            raise ValueError("tactical_horizon must be positive")
        if self.calibration_bins < 2:
            raise ValueError("calibration_bins must be at least 2")
        if self.shuffle_seed < 0:
            raise ValueError("shuffle_seed must be non-negative")

    def as_dict(self) -> dict[str, object]:
        return {
            "epochs": self.epochs,
            "learning_rate": self.learning_rate,
            "l2_regularization": self.l2_regularization,
            "gradient_clip": self.gradient_clip,
            "vector_dimension": self.vector_dimension,
            "interaction_dimension": self.interaction_dimension,
            "tactical_horizon": self.tactical_horizon,
            "calibration_bins": self.calibration_bins,
            "shuffle_seed": self.shuffle_seed,
        }

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> TrainingConfig:
        _exact_keys(
            value,
            {
                "epochs",
                "learning_rate",
                "l2_regularization",
                "gradient_clip",
                "vector_dimension",
                "interaction_dimension",
                "tactical_horizon",
                "calibration_bins",
                "shuffle_seed",
            },
            "training_config",
        )
        return cls(
            epochs=_integer(value.get("epochs"), "training_config.epochs"),
            learning_rate=_finite_number(
                value.get("learning_rate"), "training_config.learning_rate"
            ),
            l2_regularization=_finite_number(
                value.get("l2_regularization"), "training_config.l2_regularization"
            ),
            gradient_clip=_finite_number(
                value.get("gradient_clip"), "training_config.gradient_clip"
            ),
            vector_dimension=_integer(
                value.get("vector_dimension"), "training_config.vector_dimension"
            ),
            interaction_dimension=_integer(
                value.get("interaction_dimension"), "training_config.interaction_dimension"
            ),
            tactical_horizon=_integer(
                value.get("tactical_horizon"), "training_config.tactical_horizon"
            ),
            calibration_bins=_integer(
                value.get("calibration_bins"), "training_config.calibration_bins"
            ),
            shuffle_seed=_integer(value.get("shuffle_seed"), "training_config.shuffle_seed"),
        )


@dataclass(frozen=True, slots=True)
class ModelPrediction:
    policy: tuple[float, ...]
    run_value: float
    tactical_death_risk: tuple[float, ...]
    source_action_ids: tuple[str, ...]


@dataclass(slots=True)
class SparseMultiHeadModel:
    vector_dimension: int
    interaction_dimension: int
    tactical_horizon: int
    policy_weights: dict[int, float] = field(default_factory=dict)
    run_value_weights: dict[int, float] = field(default_factory=dict)
    tactical_risk_weights: dict[int, float] = field(default_factory=dict)
    run_value_bias: float = 0.0
    tactical_risk_bias: float = 0.0

    def predict(self, representation: CompositionalModelInput) -> ModelPrediction:
        vector = vectorize_model_input(representation, dimension=self.vector_dimension)
        state_features = _state_features(vector.state)
        candidate_features = tuple(
            _candidate_features(
                vector.state,
                candidate,
                self.vector_dimension,
                self.interaction_dimension,
            )
            for candidate in vector.candidates
        )
        policy = _softmax(
            tuple(_dot(self.policy_weights, features) for features in candidate_features)
        )
        run_value = _sigmoid(self.run_value_bias + _dot(self.run_value_weights, state_features))
        risks = tuple(
            _sigmoid(self.tactical_risk_bias + _dot(self.tactical_risk_weights, features))
            for features in candidate_features
        )
        return ModelPrediction(policy, run_value, risks, vector.source_action_ids)


@dataclass(frozen=True, slots=True)
class TrainingResult:
    checkpoint: dict[str, Any]
    report: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _Example:
    record_id: str
    representation: CompositionalModelInput
    state_features: dict[int, float]
    candidate_features: tuple[dict[int, float], ...]
    policy_target: tuple[float, ...]
    candidate_values: tuple[float, ...]
    candidate_value_outcomes: tuple[tuple[float, ...], ...]
    candidate_risk_targets: tuple[float, ...]
    candidate_risk_outcomes: tuple[tuple[float, ...], ...]
    teacher_candidate_index: int

    @property
    def run_value_target(self) -> float:
        return self.candidate_values[self.teacher_candidate_index]

    @property
    def run_value_outcomes(self) -> tuple[float, ...]:
        return self.candidate_value_outcomes[self.teacher_candidate_index]


def train_initial_models(
    *,
    train_dataset: object,
    validation_dataset: object,
    split_manifest: SplitManifest,
    config: TrainingConfig,
) -> TrainingResult:
    train_document = _mapping(train_dataset, "training teacher dataset")
    validation_document = _mapping(validation_dataset, "validation teacher dataset")
    train_verification = verify_teacher_dataset(train_document, split_manifest)
    validation_verification = verify_teacher_dataset(validation_document, split_manifest)
    if not train_verification.valid:
        raise ValueError(
            "Training teacher dataset failed verification: " + "; ".join(train_verification.errors)
        )
    if not validation_verification.valid:
        raise ValueError(
            "Validation teacher dataset failed verification: "
            + "; ".join(validation_verification.errors)
        )
    if train_document.get("partition") != SplitName.TRAIN.value:
        raise ValueError("Model fitting requires a frozen train-partition dataset")
    if validation_document.get("partition") != SplitName.VALIDATION.value:
        raise ValueError("Held-out reporting requires a frozen validation-partition dataset")
    train_run_ids = {
        _string(_mapping(run, "training run").get("run_id"), "training run ID")
        for run in _list(train_document.get("runs"), "training runs")
    }
    validation_run_ids = {
        _string(_mapping(run, "validation run").get("run_id"), "validation run ID")
        for run in _list(validation_document.get("runs"), "validation runs")
    }
    if train_run_ids & validation_run_ids:
        raise ValueError("Training and validation datasets share complete runs")
    if train_document.get("ruleset") != validation_document.get("ruleset"):
        raise ValueError("Training and validation datasets use different rulesets")
    if train_document.get("objective") != validation_document.get("objective"):
        raise ValueError("Training and validation datasets use different objectives")

    train_examples = _prepare_examples(train_document, config)
    validation_examples = _prepare_examples(validation_document, config)
    if not train_examples or not validation_examples:
        raise ValueError("Training and validation datasets must contain decision records")
    model = SparseMultiHeadModel(
        vector_dimension=config.vector_dimension,
        interaction_dimension=config.interaction_dimension,
        tactical_horizon=config.tactical_horizon,
    )
    history = _fit(model, train_examples, config)
    _quantize_model(model)
    metrics = evaluate_initial_models(model, validation_examples, config.calibration_bins)

    ruleset = _mapping(train_document.get("ruleset"), "ruleset")
    objective = _mapping(train_document.get("objective"), "objective")
    checkpoint_body: dict[str, Any] = {
        "schema_version": MODEL_CHECKPOINT_SCHEMA_VERSION,
        "model_type": MODEL_TYPE,
        "representation_encoder_id": ENCODER_ID,
        "vectorizer_id": VECTORIZER_ID,
        "ruleset_manifest_id": _string(ruleset.get("manifest_id"), "ruleset manifest ID"),
        "objective_id": _string(objective.get("id"), "objective ID"),
        "split_manifest_id": split_manifest.manifest_id,
        "train_dataset_id": _string(train_document.get("dataset_id"), "train dataset ID"),
        "training_config": config.as_dict(),
        "heads": {
            "policy": {
                "target": "teacher_search_visit_distribution",
                "weights": _weights_as_list(model.policy_weights),
            },
            "run_value": {
                "target": "independent_terminal_victory_probability",
                "bias": _artifact_float(model.run_value_bias),
                "weights": _weights_as_list(model.run_value_weights),
            },
            "tactical_death_risk": {
                "target": f"independent_terminal_defeat_within_{config.tactical_horizon}_decisions",
                "bias": _artifact_float(model.tactical_risk_bias),
                "weights": _weights_as_list(model.tactical_risk_weights),
            },
        },
    }
    checkpoint = {**checkpoint_body, "model_id": manifest_identifier(checkpoint_body)}
    report_body: dict[str, Any] = {
        "schema_version": MODEL_TRAINING_REPORT_SCHEMA_VERSION,
        "model_id": checkpoint["model_id"],
        "model_type": MODEL_TYPE,
        "train_dataset_id": train_document["dataset_id"],
        "validation_dataset_id": validation_document["dataset_id"],
        "split_manifest_id": split_manifest.manifest_id,
        "training_runs": len(train_run_ids),
        "validation_runs": len(validation_run_ids),
        "training_records": len(train_examples),
        "validation_records": len(validation_examples),
        "data_provenance": {
            "train": _dataset_provenance(train_document),
            "validation": _dataset_provenance(validation_document),
        },
        "training_history": _quantize_artifact(history),
        "held_out_metrics": _quantize_artifact(metrics),
        "claim_scope": "mock_pipeline_validation",
    }
    report = {**report_body, "report_id": manifest_identifier(report_body)}
    return TrainingResult(checkpoint, report)


def model_from_checkpoint(document: object) -> SparseMultiHeadModel:
    checkpoint = _mapping(document, "model checkpoint")
    expected_keys = {
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
    }
    _exact_keys(checkpoint, expected_keys, "model checkpoint")
    if checkpoint.get("schema_version") != MODEL_CHECKPOINT_SCHEMA_VERSION:
        raise ValueError("Unsupported model-checkpoint schema")
    if checkpoint.get("model_type") != MODEL_TYPE:
        raise ValueError("Unsupported model type")
    if checkpoint.get("representation_encoder_id") != ENCODER_ID:
        raise ValueError("Unsupported model representation encoder")
    if checkpoint.get("vectorizer_id") != VECTORIZER_ID:
        raise ValueError("Unsupported model vectorizer")
    model_id = _string(checkpoint.get("model_id"), "model_id")
    body = {key: value for key, value in checkpoint.items() if key != "model_id"}
    if model_id != manifest_identifier(body):
        raise ValueError("Model checkpoint identity mismatch")
    raw_config = _mapping(checkpoint.get("training_config"), "training_config")
    config = TrainingConfig.from_mapping(raw_config)
    heads = _mapping(checkpoint.get("heads"), "heads")
    _exact_keys(heads, {"policy", "run_value", "tactical_death_risk"}, "heads")
    policy = _mapping(heads.get("policy"), "policy head")
    run_value = _mapping(heads.get("run_value"), "run-value head")
    tactical_risk = _mapping(heads.get("tactical_death_risk"), "tactical-risk head")
    _exact_keys(policy, {"target", "weights"}, "policy head")
    _exact_keys(run_value, {"target", "bias", "weights"}, "run-value head")
    _exact_keys(tactical_risk, {"target", "bias", "weights"}, "tactical-risk head")
    if policy.get("target") != "teacher_search_visit_distribution":
        raise ValueError("Unsupported policy target")
    if run_value.get("target") != "independent_terminal_victory_probability":
        raise ValueError("Unsupported run-value target")
    if tactical_risk.get("target") != (
        f"independent_terminal_defeat_within_{config.tactical_horizon}_decisions"
    ):
        raise ValueError("Unsupported tactical-risk target")
    return SparseMultiHeadModel(
        vector_dimension=config.vector_dimension,
        interaction_dimension=config.interaction_dimension,
        tactical_horizon=config.tactical_horizon,
        policy_weights=_weights_from_list(
            policy.get("weights"),
            config.vector_dimension + config.interaction_dimension,
            "policy weights",
        ),
        run_value_weights=_weights_from_list(
            run_value.get("weights"), config.vector_dimension, "run-value weights"
        ),
        tactical_risk_weights=_weights_from_list(
            tactical_risk.get("weights"),
            config.vector_dimension + config.interaction_dimension,
            "tactical-risk weights",
        ),
        run_value_bias=_finite_number(run_value.get("bias"), "run-value bias"),
        tactical_risk_bias=_finite_number(tactical_risk.get("bias"), "tactical-risk bias"),
    )


def evaluate_initial_models(
    model: SparseMultiHeadModel,
    examples: tuple[_Example, ...],
    calibration_bins: int,
) -> dict[str, Any]:
    agreements = 0
    cross_entropy = 0.0
    regrets: list[float] = []
    value_absolute_errors: list[float] = []
    value_calibration: list[tuple[float, float]] = []
    risk_calibration: list[tuple[float, float]] = []
    for example in examples:
        prediction = model.predict(example.representation)
        predicted_index = max(range(len(prediction.policy)), key=prediction.policy.__getitem__)
        agreements += int(predicted_index == example.teacher_candidate_index)
        cross_entropy += -sum(
            target * math.log(max(probability, 1e-12))
            for target, probability in zip(example.policy_target, prediction.policy, strict=True)
        )
        regrets.append(max(example.candidate_values) - example.candidate_values[predicted_index])
        value_absolute_errors.append(abs(prediction.run_value - example.run_value_target))
        value_calibration.extend(
            (prediction.run_value, outcome) for outcome in example.run_value_outcomes
        )
        for risk, outcomes in zip(
            prediction.tactical_death_risk,
            example.candidate_risk_outcomes,
            strict=True,
        ):
            risk_calibration.extend((risk, outcome) for outcome in outcomes)
    count = len(examples)
    return {
        "policy": {
            "action_agreement": agreements / count,
            "cross_entropy": cross_entropy / count,
            "mean_independent_value_regret": sum(regrets) / count,
            "p95_independent_value_regret": _percentile(regrets, 0.95),
        },
        "run_value": {
            "mean_absolute_error": sum(value_absolute_errors) / count,
            **_calibration_metrics(value_calibration, calibration_bins),
        },
        "tactical_death_risk": _calibration_metrics(risk_calibration, calibration_bins),
    }


def write_model_artifact(document: dict[str, Any], path: Path, *, label: str) -> None:
    encoded = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise FileExistsError(f"Refusing to replace immutable {label}: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded, encoding="utf-8", newline="\n")


def load_model_checkpoint(path: Path) -> dict[str, Any]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load model checkpoint {path}: {error}") from error
    document = _mapping(value, "model checkpoint")
    model_from_checkpoint(document)
    return document


def load_training_report(
    path: Path,
    *,
    checkpoint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load model training report {path}: {error}") from error
    report = _mapping(value, "model training report")
    report_id = _string(report.get("report_id"), "report_id")
    body = {key: item for key, item in report.items() if key != "report_id"}
    if report_id != manifest_identifier(body):
        raise ValueError("Model training report identity mismatch")
    if report.get("schema_version") != MODEL_TRAINING_REPORT_SCHEMA_VERSION:
        raise ValueError("Unsupported model-training-report schema")
    if report.get("model_type") != MODEL_TYPE:
        raise ValueError("Unsupported model type in training report")
    if checkpoint is not None and report.get("model_id") != checkpoint.get("model_id"):
        raise ValueError("Training report references a different model checkpoint")
    return report


def _prepare_examples(document: dict[str, Any], config: TrainingConfig) -> tuple[_Example, ...]:
    examples: list[_Example] = []
    for offset, raw_record in enumerate(_list(document.get("records"), "teacher records")):
        record = _mapping(raw_record, f"teacher records[{offset}]")
        representation = model_input_from_mapping(record.get("model_input"))
        vector = vectorize_model_input(representation, dimension=config.vector_dimension)
        state_features = _state_features(vector.state)
        candidate_features = tuple(
            _candidate_features(
                vector.state,
                candidate,
                config.vector_dimension,
                config.interaction_dimension,
            )
            for candidate in vector.candidates
        )
        target = _mapping(record.get("teacher_target"), "teacher target")
        raw_candidates = _list(target.get("candidates"), "teacher candidates")
        if len(raw_candidates) != len(candidate_features):
            raise ValueError("Teacher and model candidate counts differ")
        policy_target: list[float] = []
        candidate_values: list[float] = []
        value_outcomes: list[tuple[float, ...]] = []
        risk_targets: list[float] = []
        risk_outcomes: list[tuple[float, ...]] = []
        for candidate_index, raw_candidate in enumerate(raw_candidates):
            candidate = _mapping(raw_candidate, f"teacher candidate[{candidate_index}]")
            if candidate.get("source_action_id") != vector.source_action_ids[candidate_index]:
                raise ValueError("Teacher candidate action is not representation aligned")
            search = _mapping(candidate.get("search"), "candidate search")
            evaluation = _mapping(
                candidate.get("independent_evaluation"), "candidate independent evaluation"
            )
            policy_target.append(_probability(search.get("visit_probability"), "visit probability"))
            candidate_values.append(
                _probability(evaluation.get("terminal_value"), "terminal value")
            )
            outcomes = tuple(
                _probability(_mapping(item, "evaluation outcome").get("terminal_reward"), "reward")
                for item in _list(evaluation.get("outcomes"), "evaluation outcomes")
            )
            value_outcomes.append(outcomes)
            candidate_risk_outcomes = tuple(
                float(
                    _mapping(item, "evaluation outcome").get("terminal_victory") is False
                    and _integer(
                        _mapping(item, "evaluation outcome").get("decisions"),
                        "outcome decisions",
                    )
                    <= config.tactical_horizon
                )
                for item in _list(evaluation.get("outcomes"), "evaluation outcomes")
            )
            risk_outcomes.append(candidate_risk_outcomes)
            risk_targets.append(sum(candidate_risk_outcomes) / len(candidate_risk_outcomes))
        target_total = sum(policy_target)
        if not math.isclose(target_total, 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("Teacher visit distribution must sum to one")
        examples.append(
            _Example(
                record_id=_string(record.get("record_id"), "record ID"),
                representation=representation,
                state_features=state_features,
                candidate_features=candidate_features,
                policy_target=tuple(policy_target),
                candidate_values=tuple(candidate_values),
                candidate_value_outcomes=tuple(value_outcomes),
                candidate_risk_targets=tuple(risk_targets),
                candidate_risk_outcomes=tuple(risk_outcomes),
                teacher_candidate_index=_integer(
                    target.get("selected_candidate_index"), "teacher candidate index"
                ),
            )
        )
    return tuple(examples)


def _dataset_provenance(document: dict[str, Any]) -> dict[str, object]:
    return {
        "dataset_id": document["dataset_id"],
        "partition": document["partition"],
        "teacher_id": document["teacher_id"],
        "configuration": document["configuration"],
        "seeds": [
            _mapping(run, "teacher run")["seed"]
            for run in _list(document.get("runs"), "teacher runs")
        ],
    }


def _fit(
    model: SparseMultiHeadModel,
    examples: tuple[_Example, ...],
    config: TrainingConfig,
) -> list[dict[str, float | int]]:
    rng = random.Random(config.shuffle_seed)
    order = list(range(len(examples)))
    history: list[dict[str, float | int]] = []
    for epoch in range(config.epochs):
        rng.shuffle(order)
        policy_loss = 0.0
        value_loss = 0.0
        risk_loss = 0.0
        risk_count = 0
        for example_index in order:
            example = examples[example_index]
            scores = tuple(
                _dot(model.policy_weights, features) for features in example.candidate_features
            )
            probabilities = _softmax(scores)
            policy_loss += -sum(
                target * math.log(max(probability, 1e-12))
                for target, probability in zip(example.policy_target, probabilities, strict=True)
            )
            for features, probability, target in zip(
                example.candidate_features,
                probabilities,
                example.policy_target,
                strict=True,
            ):
                _update_weights(
                    model.policy_weights,
                    features,
                    probability - target,
                    config,
                )

            value_probability = _sigmoid(
                model.run_value_bias + _dot(model.run_value_weights, example.state_features)
            )
            value_loss += _binary_cross_entropy(value_probability, example.run_value_target)
            value_error = value_probability - example.run_value_target
            _update_weights(
                model.run_value_weights,
                example.state_features,
                value_error,
                config,
            )
            model.run_value_bias -= config.learning_rate * _clip(value_error, config.gradient_clip)

            for features, target in zip(
                example.candidate_features,
                example.candidate_risk_targets,
                strict=True,
            ):
                risk_probability = _sigmoid(
                    model.tactical_risk_bias + _dot(model.tactical_risk_weights, features)
                )
                risk_loss += _binary_cross_entropy(risk_probability, target)
                risk_error = risk_probability - target
                _update_weights(
                    model.tactical_risk_weights,
                    features,
                    risk_error,
                    config,
                )
                model.tactical_risk_bias -= config.learning_rate * _clip(
                    risk_error, config.gradient_clip
                )
                risk_count += 1
        history.append(
            {
                "epoch": epoch + 1,
                "policy_cross_entropy": policy_loss / len(examples),
                "run_value_cross_entropy": value_loss / len(examples),
                "tactical_risk_cross_entropy": risk_loss / risk_count,
            }
        )
    return history


def _state_features(entries: tuple[SparseEntry, ...]) -> dict[int, float]:
    return {entry.index: _scale(entry.value) for entry in entries if entry.value != 0.0}


def _candidate_features(
    state: tuple[SparseEntry, ...],
    candidate: tuple[SparseEntry, ...],
    vector_dimension: int,
    interaction_dimension: int,
) -> dict[int, float]:
    result = {entry.index: _scale(entry.value) for entry in candidate if entry.value != 0.0}
    for state_entry in state:
        state_value = _scale(state_entry.value)
        for candidate_entry in candidate:
            index = vector_dimension + (
                (state_entry.index * 2_654_435_761 + candidate_entry.index * 2_246_822_519)
                % interaction_dimension
            )
            result[index] = result.get(index, 0.0) + state_value * _scale(candidate_entry.value)
    return {index: value for index, value in result.items() if value != 0.0}


def _scale(value: float) -> float:
    return math.copysign(math.log1p(abs(value)), value)


def _dot(weights: dict[int, float], features: dict[int, float]) -> float:
    return sum(weights.get(index, 0.0) * value for index, value in features.items())


def _update_weights(
    weights: dict[int, float],
    features: dict[int, float],
    error: float,
    config: TrainingConfig,
) -> None:
    for index, value in features.items():
        current = weights.get(index, 0.0)
        gradient = error * value + config.l2_regularization * current
        updated = current - config.learning_rate * _clip(gradient, config.gradient_clip)
        if abs(updated) < 1e-15:
            weights.pop(index, None)
        else:
            weights[index] = updated


def _softmax(scores: tuple[float, ...]) -> tuple[float, ...]:
    if not scores:
        raise ValueError("Policy prediction requires at least one candidate")
    maximum = max(scores)
    exponentials = [math.exp(score - maximum) for score in scores]
    total = sum(exponentials)
    return tuple(value / total for value in exponentials)


def _sigmoid(value: float) -> float:
    if value >= 0:
        inverse = math.exp(-value)
        return 1.0 / (1.0 + inverse)
    exponential = math.exp(value)
    return exponential / (1.0 + exponential)


def _binary_cross_entropy(probability: float, target: float) -> float:
    bounded = min(max(probability, 1e-12), 1.0 - 1e-12)
    return -(target * math.log(bounded) + (1.0 - target) * math.log(1.0 - bounded))


def _calibration_metrics(
    pairs: list[tuple[float, float]], bins: int
) -> dict[str, float | int | list[dict[str, float | int]]]:
    if not pairs:
        raise ValueError("Calibration requires at least one outcome")
    grouped: list[list[tuple[float, float]]] = [[] for _ in range(bins)]
    for probability, outcome in pairs:
        grouped[min(int(probability * bins), bins - 1)].append((probability, outcome))
    total = len(pairs)
    ece = 0.0
    calibration: list[dict[str, float | int]] = []
    for index, values in enumerate(grouped):
        if not values:
            continue
        confidence = sum(value[0] for value in values) / len(values)
        frequency = sum(value[1] for value in values) / len(values)
        ece += len(values) / total * abs(confidence - frequency)
        calibration.append(
            {
                "bin": index,
                "count": len(values),
                "mean_prediction": confidence,
                "observed_frequency": frequency,
            }
        )
    return {
        "samples": total,
        "brier_score": sum((probability - outcome) ** 2 for probability, outcome in pairs) / total,
        "expected_calibration_error": ece,
        "calibration_bins": calibration,
    }


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(probability * len(ordered)) - 1)
    return ordered[index]


def _weights_as_list(weights: dict[int, float]) -> list[dict[str, float | int]]:
    result: list[dict[str, float | int]] = []
    for index, value in sorted(weights.items()):
        artifact_value = _artifact_float(value)
        if artifact_value != 0.0:
            result.append({"index": index, "value": artifact_value})
    return result


def _weights_from_list(value: object, dimension: int, label: str) -> dict[int, float]:
    weights: dict[int, float] = {}
    for offset, raw_entry in enumerate(_list(value, label)):
        entry = _mapping(raw_entry, f"{label}[{offset}]")
        _exact_keys(entry, {"index", "value"}, f"{label}[{offset}]")
        index = _integer(entry.get("index"), f"{label}[{offset}].index")
        if index < 0 or index >= dimension:
            raise ValueError(f"{label}[{offset}].index is outside the model dimension")
        if index in weights:
            raise ValueError(f"{label} contains duplicate indexes")
        weights[index] = _finite_number(entry.get("value"), f"{label}[{offset}].value")
    return weights


def _clip(value: float, limit: float) -> float:
    return min(max(value, -limit), limit)


def _quantize_model(model: SparseMultiHeadModel) -> None:
    model.policy_weights = _quantized_weights(model.policy_weights)
    model.run_value_weights = _quantized_weights(model.run_value_weights)
    model.tactical_risk_weights = _quantized_weights(model.tactical_risk_weights)
    model.run_value_bias = _artifact_float(model.run_value_bias)
    model.tactical_risk_bias = _artifact_float(model.tactical_risk_bias)


def _quantized_weights(weights: dict[int, float]) -> dict[int, float]:
    return {
        index: artifact_value
        for index, value in weights.items()
        if (artifact_value := _artifact_float(value)) != 0.0
    }


def _quantize_artifact(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, int | str):
        return value
    if isinstance(value, float):
        return _artifact_float(value)
    if isinstance(value, list):
        return [_quantize_artifact(item) for item in value]
    if isinstance(value, tuple):
        return [_quantize_artifact(item) for item in value]
    if isinstance(value, dict):
        return {key: _quantize_artifact(item) for key, item in value.items()}
    raise TypeError(f"Unsupported artifact value type: {type(value).__name__}")


def _artifact_float(value: float) -> float:
    rounded = round(value, ARTIFACT_FLOAT_DECIMALS)
    return 0.0 if rounded == 0.0 else rounded


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    return value


def _finite_number(value: object, label: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _probability(value: object, label: str) -> float:
    result = _finite_number(value, label)
    if result < 0.0 or result > 1.0:
        raise ValueError(f"{label} must be between zero and one")
    return result


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError(
            f"{label} fields differ: missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )
