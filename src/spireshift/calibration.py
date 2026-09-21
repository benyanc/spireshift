from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.models import (
    ModelPrediction,
    SparseMultiHeadModel,
    model_from_checkpoint,
)
from spireshift.representations import CompositionalModelInput, model_input_from_mapping
from spireshift.splits import SplitManifest, SplitName
from spireshift.teacher_data import verify_teacher_dataset

CALIBRATION_SCHEMA_VERSION = "model-calibration-v1"
CALIBRATION_REPORT_SCHEMA_VERSION = "model-calibration-report-v1"
CALIBRATION_METHOD = "platt-logit-affine-v1"
SUBFOLD_METHOD = "sha256-model-salt-run-ranking-v1"
ARTIFACT_FLOAT_DECIMALS = 12


@dataclass(frozen=True, slots=True)
class CalibrationConfig:
    fit_fraction: float = 0.5
    split_salt: str = "calibration-v1"
    iterations: int = 1000
    learning_rate: float = 0.05
    l2_regularization: float = 0.001
    gradient_clip: float = 5.0
    calibration_bins: int = 10
    policy_confidence_threshold: float = 0.8
    catastrophic_regret_threshold: float = 0.1
    false_safe_risk_threshold: float = 0.2
    false_safe_observed_rate: float = 0.5

    def __post_init__(self) -> None:
        if not 0.0 < self.fit_fraction < 1.0:
            raise ValueError("fit_fraction must be strictly between zero and one")
        if not self.split_salt:
            raise ValueError("split_salt must be non-empty")
        if self.iterations <= 0:
            raise ValueError("iterations must be positive")
        if not math.isfinite(self.learning_rate) or self.learning_rate <= 0.0:
            raise ValueError("learning_rate must be finite and positive")
        if not math.isfinite(self.l2_regularization) or self.l2_regularization < 0.0:
            raise ValueError("l2_regularization must be finite and non-negative")
        if not math.isfinite(self.gradient_clip) or self.gradient_clip <= 0.0:
            raise ValueError("gradient_clip must be finite and positive")
        if self.calibration_bins < 2:
            raise ValueError("calibration_bins must be at least two")
        for name, value in (
            ("policy_confidence_threshold", self.policy_confidence_threshold),
            ("catastrophic_regret_threshold", self.catastrophic_regret_threshold),
            ("false_safe_risk_threshold", self.false_safe_risk_threshold),
            ("false_safe_observed_rate", self.false_safe_observed_rate),
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between zero and one")

    def as_dict(self) -> dict[str, object]:
        return {
            "fit_fraction": self.fit_fraction,
            "split_salt": self.split_salt,
            "iterations": self.iterations,
            "learning_rate": self.learning_rate,
            "l2_regularization": self.l2_regularization,
            "gradient_clip": self.gradient_clip,
            "calibration_bins": self.calibration_bins,
            "policy_confidence_threshold": self.policy_confidence_threshold,
            "catastrophic_regret_threshold": self.catastrophic_regret_threshold,
            "false_safe_risk_threshold": self.false_safe_risk_threshold,
            "false_safe_observed_rate": self.false_safe_observed_rate,
        }

    @classmethod
    def from_mapping(cls, value: object) -> CalibrationConfig:
        document = _mapping(value, "calibration config")
        expected = set(cls().as_dict())
        _exact_keys(document, expected, "calibration config")
        return cls(
            fit_fraction=_number(document.get("fit_fraction"), "fit_fraction"),
            split_salt=_string(document.get("split_salt"), "split_salt"),
            iterations=_integer(document.get("iterations"), "iterations"),
            learning_rate=_number(document.get("learning_rate"), "learning_rate"),
            l2_regularization=_number(document.get("l2_regularization"), "l2_regularization"),
            gradient_clip=_number(document.get("gradient_clip"), "gradient_clip"),
            calibration_bins=_integer(document.get("calibration_bins"), "calibration_bins"),
            policy_confidence_threshold=_number(
                document.get("policy_confidence_threshold"),
                "policy_confidence_threshold",
            ),
            catastrophic_regret_threshold=_number(
                document.get("catastrophic_regret_threshold"),
                "catastrophic_regret_threshold",
            ),
            false_safe_risk_threshold=_number(
                document.get("false_safe_risk_threshold"),
                "false_safe_risk_threshold",
            ),
            false_safe_observed_rate=_number(
                document.get("false_safe_observed_rate"),
                "false_safe_observed_rate",
            ),
        )


@dataclass(frozen=True, slots=True)
class ProbabilityCalibrator:
    slope: float
    intercept: float

    def apply(self, probability: float) -> float:
        probability = min(max(probability, 1e-6), 1.0 - 1e-6)
        logit = math.log(probability / (1.0 - probability))
        return _sigmoid(self.slope * logit + self.intercept)


@dataclass(frozen=True, slots=True)
class UncertaintySignals:
    normalized_policy_entropy: float
    top_two_policy_margin: float
    run_value_ambiguity: float
    selected_tactical_risk: float
    selected_tactical_risk_ambiguity: float
    maximum_tactical_risk: float
    run_value_calibration_adjustment: float
    selected_risk_calibration_adjustment: float

    def as_dict(self) -> dict[str, float]:
        return {
            "normalized_policy_entropy": self.normalized_policy_entropy,
            "top_two_policy_margin": self.top_two_policy_margin,
            "run_value_ambiguity": self.run_value_ambiguity,
            "selected_tactical_risk": self.selected_tactical_risk,
            "selected_tactical_risk_ambiguity": self.selected_tactical_risk_ambiguity,
            "maximum_tactical_risk": self.maximum_tactical_risk,
            "run_value_calibration_adjustment": self.run_value_calibration_adjustment,
            "selected_risk_calibration_adjustment": self.selected_risk_calibration_adjustment,
        }


@dataclass(frozen=True, slots=True)
class CalibratedPrediction:
    policy: tuple[float, ...]
    run_value: float
    tactical_death_risk: tuple[float, ...]
    source_action_ids: tuple[str, ...]
    selected_candidate_index: int
    uncertainty: UncertaintySignals


@dataclass(frozen=True, slots=True)
class CalibratedMultiHeadModel:
    model: SparseMultiHeadModel
    run_value_calibrator: ProbabilityCalibrator
    tactical_risk_calibrator: ProbabilityCalibrator

    def predict(self, representation: CompositionalModelInput) -> CalibratedPrediction:
        raw = self.model.predict(representation)
        selected_index = max(range(len(raw.policy)), key=raw.policy.__getitem__)
        run_value = self.run_value_calibrator.apply(raw.run_value)
        risks = tuple(
            self.tactical_risk_calibrator.apply(value) for value in raw.tactical_death_risk
        )
        selected_raw_risk = raw.tactical_death_risk[selected_index]
        selected_risk = risks[selected_index]
        entropy = _normalized_entropy(raw.policy)
        ordered_policy = sorted(raw.policy, reverse=True)
        margin = ordered_policy[0] - ordered_policy[1] if len(ordered_policy) > 1 else 1.0
        uncertainty = UncertaintySignals(
            normalized_policy_entropy=_artifact_float(entropy),
            top_two_policy_margin=_artifact_float(margin),
            run_value_ambiguity=_artifact_float(1.0 - abs(2.0 * run_value - 1.0)),
            selected_tactical_risk=_artifact_float(selected_risk),
            selected_tactical_risk_ambiguity=_artifact_float(1.0 - abs(2.0 * selected_risk - 1.0)),
            maximum_tactical_risk=_artifact_float(max(risks)),
            run_value_calibration_adjustment=_artifact_float(abs(run_value - raw.run_value)),
            selected_risk_calibration_adjustment=_artifact_float(
                abs(selected_risk - selected_raw_risk)
            ),
        )
        return CalibratedPrediction(
            policy=raw.policy,
            run_value=run_value,
            tactical_death_risk=risks,
            source_action_ids=raw.source_action_ids,
            selected_candidate_index=selected_index,
            uncertainty=uncertainty,
        )


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    calibration: dict[str, Any]
    report: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CalibrationVerification:
    valid: bool
    errors: tuple[str, ...]
    calibration_id: str | None
    report_id: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "errors": list(self.errors),
            "calibration_id": self.calibration_id,
            "report_id": self.report_id,
        }


@dataclass(frozen=True, slots=True)
class _Decision:
    record_id: str
    run_id: str
    decision_index: int
    representation: CompositionalModelInput
    prediction: ModelPrediction
    teacher_candidate_index: int
    candidate_values: tuple[float, ...]
    candidate_value_outcomes: tuple[tuple[float, ...], ...]
    candidate_risk_outcomes: tuple[tuple[float, ...], ...]


def calibrate_model(
    *,
    checkpoint: object,
    validation_dataset: object,
    split_manifest: SplitManifest,
    config: CalibrationConfig | None = None,
) -> CalibrationResult:
    config = config or CalibrationConfig()
    checkpoint_document = _mapping(checkpoint, "model checkpoint")
    model = model_from_checkpoint(checkpoint_document)
    dataset = _validate_inputs(checkpoint_document, validation_dataset, split_manifest)
    fit_run_ids, audit_run_ids = calibration_subfolds(
        dataset,
        model_id=_string(checkpoint_document.get("model_id"), "model_id"),
        fit_fraction=config.fit_fraction,
        salt=config.split_salt,
    )
    decisions = _prepare_decisions(dataset, model, model.tactical_horizon)
    fit_decisions = tuple(decision for decision in decisions if decision.run_id in fit_run_ids)
    audit_decisions = tuple(decision for decision in decisions if decision.run_id in audit_run_ids)
    if not fit_decisions or not audit_decisions:
        raise ValueError("Calibration fit and audit subfolds must both contain decisions")

    value_fit_pairs = _value_pairs(fit_decisions)
    risk_fit_pairs = _risk_pairs(fit_decisions)
    value_calibrator = _fit_platt(value_fit_pairs, config)
    risk_calibrator = _fit_platt(risk_fit_pairs, config)
    calibrated_model = CalibratedMultiHeadModel(model, value_calibrator, risk_calibrator)

    ruleset = _mapping(dataset.get("ruleset"), "validation ruleset")
    objective = _mapping(dataset.get("objective"), "validation objective")
    calibration_body: dict[str, Any] = {
        "schema_version": CALIBRATION_SCHEMA_VERSION,
        "method": CALIBRATION_METHOD,
        "model_id": checkpoint_document["model_id"],
        "validation_dataset_id": dataset["dataset_id"],
        "split_manifest_id": split_manifest.manifest_id,
        "ruleset_manifest_id": ruleset["manifest_id"],
        "objective_id": objective["id"],
        "configuration": config.as_dict(),
        "subfold": {
            "method": SUBFOLD_METHOD,
            "fit_run_ids": sorted(fit_run_ids),
            "audit_run_ids": sorted(audit_run_ids),
        },
        "heads": {
            "run_value": {
                "slope": _artifact_float(value_calibrator.slope),
                "intercept": _artifact_float(value_calibrator.intercept),
                "fit_samples": len(value_fit_pairs),
                "fit_positive_rate": _artifact_float(
                    _mean(outcome for _, outcome in value_fit_pairs)
                ),
            },
            "tactical_death_risk": {
                "slope": _artifact_float(risk_calibrator.slope),
                "intercept": _artifact_float(risk_calibrator.intercept),
                "fit_samples": len(risk_fit_pairs),
                "fit_positive_rate": _artifact_float(
                    _mean(outcome for _, outcome in risk_fit_pairs)
                ),
            },
        },
        "claim_scope": "mock_pipeline_validation",
    }
    calibration = {
        **calibration_body,
        "calibration_id": manifest_identifier(calibration_body),
    }
    report = _build_report(
        calibration=calibration,
        calibrated_model=calibrated_model,
        audit_decisions=audit_decisions,
        config=config,
    )
    return CalibrationResult(calibration, report)


def calibration_subfolds(
    validation_dataset: object,
    *,
    model_id: str,
    fit_fraction: float,
    salt: str,
) -> tuple[frozenset[str], frozenset[str]]:
    if not 0.0 < fit_fraction < 1.0:
        raise ValueError("fit_fraction must be strictly between zero and one")
    dataset = _mapping(validation_dataset, "validation dataset")
    run_ids = [
        _string(_mapping(run, "validation run").get("run_id"), "run_id")
        for run in _list(dataset.get("runs"), "validation runs")
    ]
    if len(run_ids) < 2:
        raise ValueError("Calibration requires at least two complete validation runs")
    if len(run_ids) != len(set(run_ids)):
        raise ValueError("Validation run IDs must be unique")
    ranked = sorted(
        run_ids,
        key=lambda run_id: (
            hashlib.sha256(f"{model_id}\0{salt}\0{run_id}".encode()).hexdigest(),
            run_id,
        ),
    )
    fit_count = min(len(ranked) - 1, max(1, int(len(ranked) * fit_fraction)))
    return frozenset(ranked[:fit_count]), frozenset(ranked[fit_count:])


def calibrated_model_from_artifacts(
    checkpoint: object, calibration: object
) -> CalibratedMultiHeadModel:
    checkpoint_document = _mapping(checkpoint, "model checkpoint")
    model = model_from_checkpoint(checkpoint_document)
    calibration_document = validate_calibration_artifact(
        calibration, checkpoint=checkpoint_document
    )
    heads = _mapping(calibration_document.get("heads"), "calibration heads")
    value = _mapping(heads.get("run_value"), "run-value calibration")
    risk = _mapping(heads.get("tactical_death_risk"), "risk calibration")
    return CalibratedMultiHeadModel(
        model=model,
        run_value_calibrator=ProbabilityCalibrator(
            _number(value.get("slope"), "run-value slope"),
            _number(value.get("intercept"), "run-value intercept"),
        ),
        tactical_risk_calibrator=ProbabilityCalibrator(
            _number(risk.get("slope"), "risk slope"),
            _number(risk.get("intercept"), "risk intercept"),
        ),
    )


def validate_calibration_artifact(
    calibration: object, *, checkpoint: dict[str, Any] | None = None
) -> dict[str, Any]:
    document = _mapping(calibration, "model calibration")
    expected = {
        "schema_version",
        "calibration_id",
        "method",
        "model_id",
        "validation_dataset_id",
        "split_manifest_id",
        "ruleset_manifest_id",
        "objective_id",
        "configuration",
        "subfold",
        "heads",
        "claim_scope",
    }
    _exact_keys(document, expected, "model calibration")
    if document.get("schema_version") != CALIBRATION_SCHEMA_VERSION:
        raise ValueError("Unsupported model-calibration schema")
    if document.get("method") != CALIBRATION_METHOD:
        raise ValueError("Unsupported calibration method")
    calibration_id = _string(document.get("calibration_id"), "calibration_id")
    body = {key: value for key, value in document.items() if key != "calibration_id"}
    if calibration_id != manifest_identifier(body):
        raise ValueError("Model calibration identity mismatch")
    if checkpoint is not None and document.get("model_id") != checkpoint.get("model_id"):
        raise ValueError("Model calibration references a different checkpoint")
    CalibrationConfig.from_mapping(document.get("configuration"))
    subfold = _mapping(document.get("subfold"), "calibration subfold")
    _exact_keys(subfold, {"method", "fit_run_ids", "audit_run_ids"}, "calibration subfold")
    if subfold.get("method") != SUBFOLD_METHOD:
        raise ValueError("Unsupported calibration subfold method")
    fit_ids = _string_list(subfold.get("fit_run_ids"), "fit_run_ids")
    audit_ids = _string_list(subfold.get("audit_run_ids"), "audit_run_ids")
    if fit_ids != sorted(set(fit_ids)) or audit_ids != sorted(set(audit_ids)):
        raise ValueError("Calibration subfold run IDs must be sorted and unique")
    if not fit_ids or not audit_ids or set(fit_ids) & set(audit_ids):
        raise ValueError("Calibration fit and audit subfolds must be non-empty and disjoint")
    heads = _mapping(document.get("heads"), "calibration heads")
    _exact_keys(heads, {"run_value", "tactical_death_risk"}, "calibration heads")
    for name in ("run_value", "tactical_death_risk"):
        head = _mapping(heads.get(name), f"{name} calibration")
        _exact_keys(
            head,
            {"slope", "intercept", "fit_samples", "fit_positive_rate"},
            f"{name} calibration",
        )
        _number(head.get("slope"), f"{name} slope")
        _number(head.get("intercept"), f"{name} intercept")
        if _integer(head.get("fit_samples"), f"{name} fit_samples") <= 0:
            raise ValueError(f"{name} fit_samples must be positive")
        _probability(head.get("fit_positive_rate"), f"{name} fit_positive_rate")
    return document


def validate_calibration_report(
    report: object, *, calibration: dict[str, Any] | None = None
) -> dict[str, Any]:
    document = _mapping(report, "calibration report")
    if document.get("schema_version") != CALIBRATION_REPORT_SCHEMA_VERSION:
        raise ValueError("Unsupported model-calibration-report schema")
    report_id = _string(document.get("report_id"), "report_id")
    body = {key: value for key, value in document.items() if key != "report_id"}
    if report_id != manifest_identifier(body):
        raise ValueError("Model calibration report identity mismatch")
    if calibration is not None and document.get("calibration_id") != calibration.get(
        "calibration_id"
    ):
        raise ValueError("Calibration report references a different calibration artifact")
    return document


def load_calibration_artifact(
    path: Path, *, checkpoint: dict[str, Any] | None = None
) -> dict[str, Any]:
    return validate_calibration_artifact(
        _load_json(path, "model calibration"), checkpoint=checkpoint
    )


def load_calibration_report(
    path: Path, *, calibration: dict[str, Any] | None = None
) -> dict[str, Any]:
    return validate_calibration_report(
        _load_json(path, "model calibration report"), calibration=calibration
    )


def write_calibration_artifact(document: dict[str, Any], path: Path, *, label: str) -> None:
    encoded = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise FileExistsError(f"Refusing to replace immutable {label}: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded, encoding="utf-8", newline="\n")


def verify_calibration_artifacts(
    *,
    calibration: object,
    report: object,
    checkpoint: object,
    validation_dataset: object,
    split_manifest: SplitManifest,
) -> CalibrationVerification:
    errors: list[str] = []
    calibration_id: str | None = None
    report_id: str | None = None
    try:
        checkpoint_document = _mapping(checkpoint, "model checkpoint")
        calibration_document = validate_calibration_artifact(
            calibration, checkpoint=checkpoint_document
        )
        report_document = validate_calibration_report(report, calibration=calibration_document)
        calibration_id = _string(calibration_document.get("calibration_id"), "calibration_id")
        report_id = _string(report_document.get("report_id"), "report_id")
        regenerated = calibrate_model(
            checkpoint=checkpoint_document,
            validation_dataset=validation_dataset,
            split_manifest=split_manifest,
            config=CalibrationConfig.from_mapping(calibration_document.get("configuration")),
        )
        if regenerated.calibration != calibration_document:
            errors.append("calibration artifact differs from deterministic regeneration")
        if regenerated.report != report_document:
            errors.append("calibration report differs from deterministic regeneration")
    except (ValueError, TypeError) as error:
        errors.append(str(error))
    return CalibrationVerification(not errors, tuple(errors), calibration_id, report_id)


def _validate_inputs(
    checkpoint: dict[str, Any], validation_dataset: object, split_manifest: SplitManifest
) -> dict[str, Any]:
    model_from_checkpoint(checkpoint)
    dataset = _mapping(validation_dataset, "validation dataset")
    verification = verify_teacher_dataset(dataset, split_manifest)
    if not verification.valid:
        raise ValueError(
            "Validation teacher dataset failed verification: " + "; ".join(verification.errors)
        )
    if dataset.get("partition") != SplitName.VALIDATION.value:
        raise ValueError("Calibration requires a frozen validation-partition dataset")
    ruleset = _mapping(dataset.get("ruleset"), "validation ruleset")
    objective = _mapping(dataset.get("objective"), "validation objective")
    if checkpoint.get("split_manifest_id") != split_manifest.manifest_id:
        raise ValueError("Checkpoint references a different split manifest")
    if dataset.get("split_manifest_id") != split_manifest.manifest_id:
        raise ValueError("Validation dataset references a different split manifest")
    if checkpoint.get("ruleset_manifest_id") != ruleset.get("manifest_id"):
        raise ValueError("Checkpoint and validation dataset use different rulesets")
    if checkpoint.get("objective_id") != objective.get("id"):
        raise ValueError("Checkpoint and validation dataset use different objectives")
    return dataset


def _prepare_decisions(
    dataset: dict[str, Any], model: SparseMultiHeadModel, tactical_horizon: int
) -> tuple[_Decision, ...]:
    decisions: list[_Decision] = []
    for offset, raw_record in enumerate(_list(dataset.get("records"), "teacher records")):
        record = _mapping(raw_record, f"teacher record[{offset}]")
        representation = model_input_from_mapping(record.get("model_input"))
        prediction = model.predict(representation)
        target = _mapping(record.get("teacher_target"), "teacher target")
        candidates = _list(target.get("candidates"), "teacher candidates")
        if len(candidates) != len(prediction.source_action_ids):
            raise ValueError("Teacher and model candidate counts differ")
        values: list[float] = []
        value_outcomes: list[tuple[float, ...]] = []
        risk_outcomes: list[tuple[float, ...]] = []
        for candidate_index, raw_candidate in enumerate(candidates):
            candidate = _mapping(raw_candidate, f"teacher candidate[{candidate_index}]")
            if candidate.get("source_action_id") != prediction.source_action_ids[candidate_index]:
                raise ValueError("Teacher candidate action is not representation aligned")
            evaluation = _mapping(candidate.get("independent_evaluation"), "independent evaluation")
            outcomes = tuple(
                _mapping(item, "evaluation outcome")
                for item in _list(evaluation.get("outcomes"), "evaluation outcomes")
            )
            values.append(_probability(evaluation.get("terminal_value"), "terminal_value"))
            value_outcomes.append(
                tuple(
                    _probability(item.get("terminal_reward"), "terminal_reward")
                    for item in outcomes
                )
            )
            risk_outcomes.append(
                tuple(
                    float(
                        item.get("terminal_victory") is False
                        and _integer(item.get("decisions"), "outcome decisions") <= tactical_horizon
                    )
                    for item in outcomes
                )
            )
        teacher_index = _integer(target.get("selected_candidate_index"), "selected_candidate_index")
        if not 0 <= teacher_index < len(candidates):
            raise ValueError("Teacher candidate index is out of range")
        decisions.append(
            _Decision(
                record_id=_string(record.get("record_id"), "record_id"),
                run_id=_string(record.get("run_id"), "run_id"),
                decision_index=_integer(record.get("decision_index"), "decision_index"),
                representation=representation,
                prediction=prediction,
                teacher_candidate_index=teacher_index,
                candidate_values=tuple(values),
                candidate_value_outcomes=tuple(value_outcomes),
                candidate_risk_outcomes=tuple(risk_outcomes),
            )
        )
    return tuple(decisions)


def _value_pairs(decisions: tuple[_Decision, ...]) -> tuple[tuple[float, float], ...]:
    return tuple(
        (decision.prediction.run_value, outcome)
        for decision in decisions
        for outcome in decision.candidate_value_outcomes[decision.teacher_candidate_index]
    )


def _risk_pairs(decisions: tuple[_Decision, ...]) -> tuple[tuple[float, float], ...]:
    return tuple(
        (risk, outcome)
        for decision in decisions
        for risk, outcomes in zip(
            decision.prediction.tactical_death_risk,
            decision.candidate_risk_outcomes,
            strict=True,
        )
        for outcome in outcomes
    )


def _fit_platt(
    pairs: tuple[tuple[float, float], ...], config: CalibrationConfig
) -> ProbabilityCalibrator:
    if not pairs:
        raise ValueError("Cannot fit a probability calibrator without samples")
    logits = tuple(
        math.log(min(max(p, 1e-6), 1.0 - 1e-6) / (1.0 - min(max(p, 1e-6), 1.0 - 1e-6)))
        for p, _ in pairs
    )
    outcomes = tuple(outcome for _, outcome in pairs)
    slope = 1.0
    intercept = 0.0
    for _ in range(config.iterations):
        probabilities = tuple(_sigmoid(slope * logit + intercept) for logit in logits)
        slope_gradient = _mean(
            (probability - outcome) * logit
            for probability, outcome, logit in zip(probabilities, outcomes, logits, strict=True)
        ) + config.l2_regularization * (slope - 1.0)
        intercept_gradient = (
            _mean(
                probability - outcome
                for probability, outcome in zip(probabilities, outcomes, strict=True)
            )
            + config.l2_regularization * intercept
        )
        slope -= config.learning_rate * _clip(slope_gradient, config.gradient_clip)
        intercept -= config.learning_rate * _clip(intercept_gradient, config.gradient_clip)
        slope = min(max(slope, -20.0), 20.0)
        intercept = min(max(intercept, -20.0), 20.0)
    return ProbabilityCalibrator(_artifact_float(slope), _artifact_float(intercept))


def _build_report(
    *,
    calibration: dict[str, Any],
    calibrated_model: CalibratedMultiHeadModel,
    audit_decisions: tuple[_Decision, ...],
    config: CalibrationConfig,
) -> dict[str, Any]:
    raw_value_pairs = _value_pairs(audit_decisions)
    raw_risk_pairs = _risk_pairs(audit_decisions)
    value_pairs = tuple(
        (calibrated_model.run_value_calibrator.apply(prediction), outcome)
        for prediction, outcome in raw_value_pairs
    )
    risk_pairs = tuple(
        (calibrated_model.tactical_risk_calibrator.apply(prediction), outcome)
        for prediction, outcome in raw_risk_pairs
    )
    records: list[dict[str, Any]] = []
    regrets: list[float] = []
    agreements = 0
    high_confidence_count = 0
    catastrophic_record_ids: list[str] = []
    false_safe_record_ids: list[str] = []
    for decision in audit_decisions:
        calibrated = calibrated_model.predict(decision.representation)
        selected_index = calibrated.selected_candidate_index
        confidence = max(calibrated.policy)
        regret = max(decision.candidate_values) - decision.candidate_values[selected_index]
        empirical_risk = _mean(decision.candidate_risk_outcomes[selected_index])
        high_confidence = confidence >= config.policy_confidence_threshold
        catastrophic = high_confidence and regret >= config.catastrophic_regret_threshold
        false_safe = (
            calibrated.tactical_death_risk[selected_index] <= config.false_safe_risk_threshold
            and empirical_risk >= config.false_safe_observed_rate
        )
        high_confidence_count += int(high_confidence)
        agreements += int(selected_index == decision.teacher_candidate_index)
        regrets.append(regret)
        if catastrophic:
            catastrophic_record_ids.append(decision.record_id)
        if false_safe:
            false_safe_record_ids.append(decision.record_id)
        records.append(
            {
                "record_id": decision.record_id,
                "run_id": decision.run_id,
                "decision_index": decision.decision_index,
                "selected_action_id": calibrated.source_action_ids[selected_index],
                "teacher_action_id": calibrated.source_action_ids[decision.teacher_candidate_index],
                "policy_confidence": _artifact_float(confidence),
                "teacher_disagreement": selected_index != decision.teacher_candidate_index,
                "independent_value_regret": _artifact_float(regret),
                "selected_empirical_tactical_death_risk": _artifact_float(empirical_risk),
                "high_confidence_catastrophic_error": catastrophic,
                "false_safe_tactical_risk_error": false_safe,
                "uncertainty": calibrated.uncertainty.as_dict(),
            }
        )
    records.sort(key=lambda item: (str(item["run_id"]), int(item["decision_index"])))
    decision_count = len(audit_decisions)
    report_body: dict[str, Any] = {
        "schema_version": CALIBRATION_REPORT_SCHEMA_VERSION,
        "calibration_id": calibration["calibration_id"],
        "model_id": calibration["model_id"],
        "validation_dataset_id": calibration["validation_dataset_id"],
        "split_manifest_id": calibration["split_manifest_id"],
        "audit": {
            "run_ids": calibration["subfold"]["audit_run_ids"],
            "runs": len(calibration["subfold"]["audit_run_ids"]),
            "decisions": decision_count,
        },
        "metrics": {
            "policy": {
                "action_agreement": _artifact_float(agreements / decision_count),
                "mean_independent_value_regret": _artifact_float(_mean(regrets)),
                "p95_independent_value_regret": _artifact_float(_percentile(regrets, 0.95)),
            },
            "run_value": {
                "raw": _calibration_metrics(raw_value_pairs, config.calibration_bins),
                "calibrated": _calibration_metrics(value_pairs, config.calibration_bins),
            },
            "tactical_death_risk": {
                "raw": _calibration_metrics(raw_risk_pairs, config.calibration_bins),
                "calibrated": _calibration_metrics(risk_pairs, config.calibration_bins),
            },
        },
        "failure_analysis": {
            "thresholds": {
                "policy_confidence": config.policy_confidence_threshold,
                "catastrophic_regret": config.catastrophic_regret_threshold,
                "false_safe_predicted_risk": config.false_safe_risk_threshold,
                "false_safe_observed_risk": config.false_safe_observed_rate,
            },
            "high_confidence_decisions": high_confidence_count,
            "high_confidence_catastrophic_errors": len(catastrophic_record_ids),
            "high_confidence_catastrophic_rate": _artifact_float(
                len(catastrophic_record_ids) / high_confidence_count
                if high_confidence_count
                else 0.0
            ),
            "high_confidence_catastrophic_record_ids": sorted(catastrophic_record_ids),
            "false_safe_tactical_risk_errors": len(false_safe_record_ids),
            "false_safe_tactical_risk_rate": _artifact_float(
                len(false_safe_record_ids) / decision_count
            ),
            "false_safe_tactical_risk_record_ids": sorted(false_safe_record_ids),
        },
        "uncertainty_signal_definitions": {
            "normalized_policy_entropy": "policy entropy divided by log(candidate count)",
            "top_two_policy_margin": "largest policy probability minus second largest",
            "run_value_ambiguity": (
                "one minus distance of calibrated run value from 0.5, scaled to [0,1]"
            ),
            "selected_tactical_risk": "calibrated risk for the policy-selected action",
            "selected_tactical_risk_ambiguity": (
                "one minus distance of selected calibrated risk from 0.5, scaled to [0,1]"
            ),
            "maximum_tactical_risk": "largest calibrated candidate risk",
            "run_value_calibration_adjustment": (
                "absolute calibrated-minus-raw run-value probability"
            ),
            "selected_risk_calibration_adjustment": (
                "absolute calibrated-minus-raw selected-action risk"
            ),
        },
        "records": records,
        "claim_scope": "mock_pipeline_validation",
    }
    report_body = _quantize_artifact(report_body)
    return {**report_body, "report_id": manifest_identifier(report_body)}


def _calibration_metrics(pairs: tuple[tuple[float, float], ...], bins: int) -> dict[str, Any]:
    if not pairs:
        raise ValueError("Calibration metrics require samples")
    bucketed: list[list[tuple[float, float]]] = [[] for _ in range(bins)]
    brier = 0.0
    log_loss = 0.0
    for prediction, outcome in pairs:
        prediction = _probability(prediction, "prediction")
        outcome = _probability(outcome, "outcome")
        brier += (prediction - outcome) ** 2
        clipped = min(max(prediction, 1e-12), 1.0 - 1e-12)
        log_loss += -(outcome * math.log(clipped) + (1.0 - outcome) * math.log(1.0 - clipped))
        bucketed[min(int(prediction * bins), bins - 1)].append((prediction, outcome))
    mean_prediction = _mean(prediction for prediction, _ in pairs)
    result_bins: list[dict[str, Any]] = []
    expected_error = 0.0
    maximum_error = 0.0
    for index, bucket in enumerate(bucketed):
        if not bucket:
            continue
        bucket_prediction = _mean(prediction for prediction, _ in bucket)
        bucket_outcome = _mean(outcome for _, outcome in bucket)
        gap = abs(bucket_prediction - bucket_outcome)
        expected_error += len(bucket) / len(pairs) * gap
        maximum_error = max(maximum_error, gap)
        result_bins.append(
            {
                "lower_bound": _artifact_float(index / bins),
                "upper_bound": _artifact_float((index + 1) / bins),
                "samples": len(bucket),
                "mean_prediction": _artifact_float(bucket_prediction),
                "empirical_rate": _artifact_float(bucket_outcome),
                "absolute_gap": _artifact_float(gap),
            }
        )
    return {
        "samples": len(pairs),
        "base_rate": _artifact_float(_mean(outcome for _, outcome in pairs)),
        "mean_prediction": _artifact_float(mean_prediction),
        "brier_score": _artifact_float(brier / len(pairs)),
        "log_loss": _artifact_float(log_loss / len(pairs)),
        "expected_calibration_error": _artifact_float(expected_error),
        "maximum_calibration_error": _artifact_float(maximum_error),
        "sharpness_variance": _artifact_float(
            _mean((prediction - mean_prediction) ** 2 for prediction, _ in pairs)
        ),
        "normalized_confidence_sharpness": _artifact_float(
            _mean(abs(prediction - 0.5) * 2.0 for prediction, _ in pairs)
        ),
        "bins": result_bins,
    }


def _normalized_entropy(probabilities: tuple[float, ...]) -> float:
    if len(probabilities) <= 1:
        return 0.0
    return -sum(p * math.log(max(p, 1e-12)) for p in probabilities) / math.log(len(probabilities))


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = percentile * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _mean(values: Iterable[float]) -> float:
    materialized = tuple(values)
    if not materialized:
        raise ValueError("Cannot take the mean of an empty collection")
    return sum(materialized) / len(materialized)


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        return 1.0 / (1.0 + math.exp(-value))
    exponential = math.exp(value)
    return exponential / (1.0 + exponential)


def _clip(value: float, limit: float) -> float:
    return min(max(value, -limit), limit)


def _artifact_float(value: float) -> float:
    return round(float(value), ARTIFACT_FLOAT_DECIMALS)


def _quantize_artifact(value: Any) -> Any:
    if isinstance(value, float):
        return _artifact_float(value)
    if isinstance(value, list):
        return [_quantize_artifact(item) for item in value]
    if isinstance(value, dict):
        return {key: _quantize_artifact(item) for key, item in value.items()}
    return value


def _load_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load {label} {path}: {error}") from error


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def _string_list(value: object, label: str) -> list[str]:
    result = _list(value, label)
    if any(not isinstance(item, str) or not item for item in result):
        raise ValueError(f"{label} must contain non-empty strings")
    return result


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _probability(value: object, label: str) -> float:
    result = _number(value, label)
    if not 0.0 <= result <= 1.0:
        raise ValueError(f"{label} must be between zero and one")
    return result


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError(
            f"{label} fields differ: missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )
