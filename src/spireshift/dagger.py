from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.agents.baseline import TerminalVictoryPolicy
from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.models import model_from_checkpoint
from spireshift.representations import ENCODER_ID, build_model_input, model_input_from_mapping
from spireshift.splits import (
    SplitManifest,
    SplitName,
    audit_dataset_index_document,
    freeze_dataset_index,
)
from spireshift.teacher_data import TeacherConfig, build_teacher_target, verify_teacher_dataset

DAGGER_ITERATION_SCHEMA_VERSION = "dagger-iteration-v1"
DAGGER_RECORD_SCHEMA_VERSION = "dagger-record-v1"
DAGGER_VERIFICATION_SCHEMA_VERSION = "dagger-verification-v1"
SELECTION_POLICY_ID = "selective-dagger-v1"
ARTIFACT_FLOAT_DECIMALS = 12
SELECTION_REASONS = (
    "teacher_disagreement",
    "rare_state",
    "confident_error",
    "high_entropy",
)


@dataclass(frozen=True, slots=True)
class DaggerConfig:
    probe_teacher: TeacherConfig = TeacherConfig(
        search_simulations=8,
        evaluation_samples_per_candidate=4,
        sampling_seed=1,
    )
    relabel_teacher: TeacherConfig = TeacherConfig(
        search_simulations=64,
        evaluation_samples_per_candidate=64,
        sampling_seed=2,
    )
    rare_state_max_fraction: float = 0.05
    high_entropy_threshold: float = 0.85
    confident_error_threshold: float = 0.8
    confident_error_regret: float = 0.1
    maximum_run_decisions: int = 4096

    def __post_init__(self) -> None:
        for name, value in (
            ("rare_state_max_fraction", self.rare_state_max_fraction),
            ("high_entropy_threshold", self.high_entropy_threshold),
            ("confident_error_threshold", self.confident_error_threshold),
            ("confident_error_regret", self.confident_error_regret),
        ):
            if not math.isfinite(value) or value < 0.0 or value > 1.0:
                raise ValueError(f"{name} must be between zero and one")
        if self.maximum_run_decisions <= 0:
            raise ValueError("maximum_run_decisions must be positive")
        if self.probe_teacher.sampling_seed == self.relabel_teacher.sampling_seed:
            raise ValueError("Probe and relabel teachers require different sampling seeds")
        if self.relabel_teacher.search_simulations < self.probe_teacher.search_simulations:
            raise ValueError("Relabel search must be at least as large as probe search")
        if (
            self.relabel_teacher.evaluation_samples_per_candidate
            < self.probe_teacher.evaluation_samples_per_candidate
        ):
            raise ValueError("Relabel evaluation must be at least as large as probe evaluation")

    def as_dict(self) -> dict[str, object]:
        return {
            "selection_policy_id": SELECTION_POLICY_ID,
            "probe_teacher": self.probe_teacher.as_dict(),
            "relabel_teacher": self.relabel_teacher.as_dict(),
            "rare_state_max_fraction": self.rare_state_max_fraction,
            "high_entropy_threshold": self.high_entropy_threshold,
            "confident_error_threshold": self.confident_error_threshold,
            "confident_error_regret": self.confident_error_regret,
            "maximum_run_decisions": self.maximum_run_decisions,
        }

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> DaggerConfig:
        _exact_keys(
            value,
            {
                "selection_policy_id",
                "probe_teacher",
                "relabel_teacher",
                "rare_state_max_fraction",
                "high_entropy_threshold",
                "confident_error_threshold",
                "confident_error_regret",
                "maximum_run_decisions",
            },
            "DAgger configuration",
        )
        if value.get("selection_policy_id") != SELECTION_POLICY_ID:
            raise ValueError("Unsupported DAgger selection policy")
        return cls(
            probe_teacher=_teacher_config_from_mapping(
                _mapping(value.get("probe_teacher"), "probe_teacher")
            ),
            relabel_teacher=_teacher_config_from_mapping(
                _mapping(value.get("relabel_teacher"), "relabel_teacher")
            ),
            rare_state_max_fraction=_probability(
                value.get("rare_state_max_fraction"), "rare_state_max_fraction"
            ),
            high_entropy_threshold=_probability(
                value.get("high_entropy_threshold"), "high_entropy_threshold"
            ),
            confident_error_threshold=_probability(
                value.get("confident_error_threshold"), "confident_error_threshold"
            ),
            confident_error_regret=_probability(
                value.get("confident_error_regret"), "confident_error_regret"
            ),
            maximum_run_decisions=_integer(
                value.get("maximum_run_decisions"), "maximum_run_decisions"
            ),
        )


@dataclass(frozen=True, slots=True)
class DaggerVerification:
    valid: bool
    iteration_id: str
    runs: int
    decisions: int
    selected_for_relabel: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": DAGGER_VERIFICATION_SCHEMA_VERSION,
            "valid": self.valid,
            "iteration_id": self.iteration_id,
            "runs": self.runs,
            "decisions": self.decisions,
            "selected_for_relabel": self.selected_for_relabel,
            "errors": list(self.errors),
        }


def generate_mock_dagger_iteration(
    *,
    iteration_index: int,
    seeds: Sequence[int],
    partition: SplitName,
    split_manifest: SplitManifest,
    objective: ObjectiveSpec,
    source_checkpoint: object,
    reference_dataset: object,
    config: DaggerConfig,
    environment_factory: Callable[[], MockSpireEnvironment] = MockSpireEnvironment,
) -> dict[str, Any]:
    document = _generate_mock_dagger_iteration(
        iteration_index=iteration_index,
        seeds=seeds,
        partition=partition,
        split_manifest=split_manifest,
        objective=objective,
        source_checkpoint=source_checkpoint,
        reference_dataset=reference_dataset,
        config=config,
        environment_factory=environment_factory,
    )
    verification = verify_mock_dagger_iteration(
        document,
        split_manifest=split_manifest,
        source_checkpoint=source_checkpoint,
        reference_dataset=reference_dataset,
    )
    if not verification.valid:
        raise RuntimeError(
            "Generated DAgger iteration failed verification: " + "; ".join(verification.errors)
        )
    return document


def verify_mock_dagger_iteration(
    document: object,
    *,
    split_manifest: SplitManifest,
    source_checkpoint: object,
    reference_dataset: object,
) -> DaggerVerification:
    errors: list[str] = []
    iteration_id = ""
    run_count = 0
    decision_count = 0
    selected_count = 0
    try:
        iteration = _mapping(document, "DAgger iteration")
        _exact_keys(
            iteration,
            {
                "schema_version",
                "iteration_id",
                "iteration_index",
                "backend",
                "ruleset",
                "objective",
                "split_manifest_id",
                "partition",
                "representation_encoder_id",
                "source_model_id",
                "reference_dataset_id",
                "configuration",
                "runs",
                "records",
                "summary",
            },
            "DAgger iteration",
        )
        iteration_id = _string(iteration.get("iteration_id"), "iteration_id")
        body = {key: value for key, value in iteration.items() if key != "iteration_id"}
        if manifest_identifier(body) != iteration_id:
            errors.append("iteration identity mismatch")
        if iteration.get("schema_version") != DAGGER_ITERATION_SCHEMA_VERSION:
            errors.append("unsupported DAgger iteration schema")
        if iteration.get("backend") != "mock":
            errors.append("unsupported DAgger backend")
        if iteration.get("representation_encoder_id") != ENCODER_ID:
            errors.append("unsupported representation encoder")
        if iteration.get("split_manifest_id") != split_manifest.manifest_id:
            errors.append("DAgger iteration references a different split manifest")
        iteration_index = _integer(iteration.get("iteration_index"), "iteration_index")
        partition = SplitName(_string(iteration.get("partition"), "partition"))
        config = DaggerConfig.from_mapping(
            _mapping(iteration.get("configuration"), "configuration")
        )
        runs = _list(iteration.get("runs"), "runs")
        records = _list(iteration.get("records"), "records")
        run_count = len(runs)
        decision_count = len(records)
        selected_count = sum(
            _mapping(record, "record").get("selected_for_relabel") is True for record in records
        )
        seeds = tuple(_integer(_mapping(run, "run").get("seed"), "run seed") for run in runs)
        checkpoint = _mapping(source_checkpoint, "source checkpoint")
        reference = _mapping(reference_dataset, "reference dataset")
        if iteration.get("source_model_id") != checkpoint.get("model_id"):
            errors.append("DAgger iteration references a different source model")
        if iteration.get("reference_dataset_id") != reference.get("dataset_id"):
            errors.append("DAgger iteration references a different training dataset")
        expected = _generate_mock_dagger_iteration(
            iteration_index=iteration_index,
            seeds=seeds,
            partition=partition,
            split_manifest=split_manifest,
            objective=_objective_from_mapping(_mapping(iteration.get("objective"), "objective")),
            source_checkpoint=source_checkpoint,
            reference_dataset=reference_dataset,
            config=config,
        )
        if iteration != expected:
            errors.append("DAgger iteration failed exact deterministic regeneration")
        index_audit = audit_dataset_index_document(
            dagger_dataset_index(iteration, split_manifest), split_manifest
        )
        errors.extend(f"dataset index: {error}" for error in index_audit.errors)
    except (KeyError, TypeError, ValueError, RuntimeError) as error:
        errors.append(str(error))
    return DaggerVerification(
        valid=not errors,
        iteration_id=iteration_id,
        runs=run_count,
        decisions=decision_count,
        selected_for_relabel=selected_count,
        errors=tuple(errors),
    )


def load_dagger_iteration(path: Path) -> dict[str, Any]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load DAgger iteration {path}: {error}") from error
    return _mapping(value, "DAgger iteration")


def write_dagger_iteration(document: dict[str, Any], path: Path) -> None:
    encoded = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise FileExistsError(f"Refusing to replace immutable DAgger iteration: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded, encoding="utf-8", newline="\n")


def selected_relabel_records(document: object) -> tuple[dict[str, Any], ...]:
    iteration = _mapping(document, "DAgger iteration")
    result: list[dict[str, Any]] = []
    for offset, raw_record in enumerate(_list(iteration.get("records"), "records")):
        record = _mapping(raw_record, f"records[{offset}]")
        if record.get("selected_for_relabel") is not True:
            continue
        target = record.get("relabel_target")
        if not isinstance(target, dict):
            raise ValueError("Selected DAgger record is missing its relabel target")
        result.append(record)
    return tuple(result)


def dagger_dataset_index(
    document: object,
    split_manifest: SplitManifest,
) -> dict[str, Any]:
    iteration = _mapping(document, "DAgger iteration")
    runs = _list(iteration.get("runs"), "DAgger runs")
    records = _list(iteration.get("records"), "DAgger records")
    specification = {
        "schema_version": "dataset-index-v1",
        "dataset_id": _string(iteration.get("iteration_id"), "iteration_id"),
        "split_manifest_id": _string(iteration.get("split_manifest_id"), "split_manifest_id"),
        "ruleset_manifest_id": _mapping(iteration.get("ruleset"), "ruleset").get("manifest_id"),
        "runs": [
            {
                "run_id": run["run_id"],
                "seed": run["seed"],
                "split": run["split"],
                "terminal": run["terminal"],
                "record_ids": run["record_ids"],
                "encounter_ids": run["encounter_ids"],
            }
            for raw_run in runs
            for run in [_mapping(raw_run, "DAgger run")]
        ],
        "records": [
            {
                "record_id": record["record_id"],
                "run_id": record["run_id"],
                "encounter_id": record["encounter_id"],
                "decision_index": record["decision_index"],
            }
            for raw_record in records
            for record in [_mapping(raw_record, "DAgger record")]
        ],
    }
    return freeze_dataset_index(specification, split_manifest)


def _generate_mock_dagger_iteration(
    *,
    iteration_index: int,
    seeds: Sequence[int],
    partition: SplitName,
    split_manifest: SplitManifest,
    objective: ObjectiveSpec,
    source_checkpoint: object,
    reference_dataset: object,
    config: DaggerConfig,
    environment_factory: Callable[[], MockSpireEnvironment] = MockSpireEnvironment,
) -> dict[str, Any]:
    if iteration_index < 0:
        raise ValueError("iteration_index must be non-negative")
    if partition is not SplitName.TRAIN:
        raise ValueError("DAgger collection is restricted to the frozen train partition")
    canonical_seeds = tuple(seeds)
    if not canonical_seeds:
        raise ValueError("At least one DAgger collection seed is required")
    if len(canonical_seeds) != len(set(canonical_seeds)):
        raise ValueError("DAgger collection seeds must be unique")
    for seed in canonical_seeds:
        if split_manifest.split_for_seed(seed) is not partition:
            raise ValueError(f"Seed {seed} is not in the frozen {partition.value} partition")
    if split_manifest.ruleset_manifest_id != MockSpireEnvironment.ruleset.manifest_id:
        raise ValueError("Split manifest and mock DAgger rulesets differ")
    if split_manifest.objective_id != objective.objective_id:
        raise ValueError("Split manifest and DAgger objective differ")

    checkpoint = _mapping(source_checkpoint, "source checkpoint")
    model = model_from_checkpoint(checkpoint)
    if checkpoint.get("ruleset_manifest_id") != split_manifest.ruleset_manifest_id:
        raise ValueError("Source model and DAgger rulesets differ")
    if checkpoint.get("objective_id") != objective.objective_id:
        raise ValueError("Source model and DAgger objectives differ")
    if checkpoint.get("split_manifest_id") != split_manifest.manifest_id:
        raise ValueError("Source model and DAgger split manifests differ")

    reference = _mapping(reference_dataset, "reference dataset")
    reference_verification = verify_teacher_dataset(reference, split_manifest)
    if not reference_verification.valid:
        raise ValueError(
            "Reference teacher dataset failed verification: "
            + "; ".join(reference_verification.errors)
        )
    if reference.get("partition") != SplitName.TRAIN.value:
        raise ValueError("DAgger reference data must use the frozen train partition")
    if reference.get("objective") != objective.as_dict():
        raise ValueError("Reference dataset and DAgger objective contracts differ")
    if checkpoint.get("train_dataset_id") != reference.get("dataset_id"):
        raise ValueError("Source model was not trained from the reference teacher dataset")
    reference_seeds = {
        _integer(_mapping(run, "reference run").get("seed"), "reference seed")
        for run in _list(reference.get("runs"), "reference runs")
    }
    reused_seeds = reference_seeds.intersection(canonical_seeds)
    if reused_seeds:
        raise ValueError(
            "DAgger collection seeds must be new train runs: "
            + ", ".join(str(seed) for seed in sorted(reused_seeds))
        )
    reference_counts = Counter(
        model_input_from_mapping(
            _mapping(record, "reference record").get("model_input")
        ).model_feature_digest()
        for record in _list(reference.get("records"), "reference records")
    )
    reference_total = sum(reference_counts.values())
    if reference_total <= 0:
        raise ValueError("DAgger reference dataset contains no decisions")

    runs: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    reason_counts = {reason: 0 for reason in SELECTION_REASONS}
    victories = 0
    candidate_count = 0
    selected_candidate_count = 0
    for run_seed in canonical_seeds:
        environment = environment_factory()
        observation = environment.reset(run_seed)
        run_id = f"dagger-{iteration_index}-{partition.value}-seed-{run_seed}"
        drafts: list[dict[str, Any]] = []
        decision_index = 0
        victory = False
        while not bool(observation.public_state["terminal"]):
            legal_actions = tuple(environment.legal_actions())
            representation = build_model_input(environment.ruleset, observation, legal_actions)
            prediction = model.predict(representation)
            student_index = max(range(len(prediction.policy)), key=prediction.policy.__getitem__)
            student_action = legal_actions[student_index]
            confidence = prediction.policy[student_index]
            entropy = _normalized_entropy(prediction.policy)
            state_signature = representation.model_feature_digest()
            reference_matches = reference_counts[state_signature]
            reference_fraction = reference_matches / reference_total
            probe_target = build_teacher_target(
                environment=environment,
                observation=observation,
                legal_actions=legal_actions,
                continuation_policy=TerminalVictoryPolicy(),
                config=config.probe_teacher,
                run_seed=run_seed,
                decision_index=decision_index,
            )
            probe_regret = _target_regret(probe_target.as_dict(), student_index)
            probe_disagreement = probe_target.selected_candidate_index != student_index
            probe_confident_error = (
                confidence >= config.confident_error_threshold
                and probe_regret >= config.confident_error_regret
            )
            reasons: list[str] = []
            if probe_disagreement:
                reasons.append("teacher_disagreement")
            if reference_fraction <= config.rare_state_max_fraction:
                reasons.append("rare_state")
            if probe_confident_error:
                reasons.append("confident_error")
            if entropy >= config.high_entropy_threshold:
                reasons.append("high_entropy")
            for reason in reasons:
                reason_counts[reason] += 1
            relabel_target = None
            relabel_disagreement: bool | None = None
            relabel_regret: float | None = None
            relabel_confident_error: bool | None = None
            if reasons:
                relabel_target_object = build_teacher_target(
                    environment=environment,
                    observation=observation,
                    legal_actions=legal_actions,
                    continuation_policy=TerminalVictoryPolicy(),
                    config=config.relabel_teacher,
                    run_seed=run_seed,
                    decision_index=decision_index,
                )
                relabel_target = relabel_target_object.as_dict()
                relabel_disagreement = (
                    relabel_target_object.selected_candidate_index != student_index
                )
                relabel_regret = _target_regret(relabel_target, student_index)
                relabel_confident_error = (
                    confidence >= config.confident_error_threshold
                    and relabel_regret >= config.confident_error_regret
                )
                selected_candidate_count += len(legal_actions)
            transition = environment.step(student_action)
            encounter_id = f"{run_id}-{decision_index}-{observation.decision_type.value}"
            drafts.append(
                {
                    "schema_version": DAGGER_RECORD_SCHEMA_VERSION,
                    "run_id": run_id,
                    "encounter_id": encounter_id,
                    "decision_index": decision_index,
                    "model_input": representation.as_dict(),
                    "state_signature": state_signature,
                    "student_prediction": {
                        "policy": [_artifact_float(value) for value in prediction.policy],
                        "run_value": _artifact_float(prediction.run_value),
                        "tactical_death_risk": [
                            _artifact_float(value) for value in prediction.tactical_death_risk
                        ],
                        "selected_candidate_index": student_index,
                        "selected_action_id": student_action.action_id,
                        "confidence": _artifact_float(confidence),
                        "normalized_entropy": _artifact_float(entropy),
                    },
                    "reference_frequency": {
                        "matching_records": reference_matches,
                        "total_records": reference_total,
                        "fraction": _artifact_float(reference_fraction),
                    },
                    "probe_teacher_target": probe_target.as_dict(),
                    "selection_reasons": reasons,
                    "selected_for_relabel": bool(reasons),
                    "relabel_target": relabel_target,
                    "diagnostics": {
                        "probe_teacher_disagreement": probe_disagreement,
                        "probe_independent_value_regret": _artifact_float(probe_regret),
                        "probe_confident_error": probe_confident_error,
                        "relabel_teacher_disagreement": relabel_disagreement,
                        "relabel_independent_value_regret": (
                            None if relabel_regret is None else _artifact_float(relabel_regret)
                        ),
                        "relabel_confident_error": relabel_confident_error,
                    },
                    "observed_transition": {
                        "selected_action_id": student_action.action_id,
                        "next_state_hash": transition.next_observation.state_hash,
                        "terminal": transition.terminal,
                        "victory": transition.victory,
                        "reward": transition.reward,
                    },
                }
            )
            candidate_count += len(legal_actions)
            observation = transition.next_observation
            victory = transition.victory
            decision_index += 1
            if decision_index > config.maximum_run_decisions:
                raise RuntimeError("DAgger trajectory exceeded maximum_run_decisions")

        victories += int(victory)
        record_ids: list[str] = []
        encounter_ids: list[str] = []
        for draft in drafts:
            record_body = {**draft, "run_terminal_victory": victory}
            record = {**record_body, "record_id": manifest_identifier(record_body)}
            records.append(record)
            record_ids.append(cast(str, record["record_id"]))
            encounter_ids.append(cast(str, record["encounter_id"]))
        runs.append(
            {
                "run_id": run_id,
                "seed": run_seed,
                "split": partition.value,
                "terminal": True,
                "victory": victory,
                "record_ids": record_ids,
                "encounter_ids": encounter_ids,
            }
        )

    selected_count = sum(record["selected_for_relabel"] is True for record in records)
    body: dict[str, Any] = {
        "schema_version": DAGGER_ITERATION_SCHEMA_VERSION,
        "iteration_index": iteration_index,
        "backend": "mock",
        "ruleset": MockSpireEnvironment.ruleset.as_dict(),
        "objective": objective.as_dict(),
        "split_manifest_id": split_manifest.manifest_id,
        "partition": partition.value,
        "representation_encoder_id": ENCODER_ID,
        "source_model_id": checkpoint["model_id"],
        "reference_dataset_id": reference["dataset_id"],
        "configuration": config.as_dict(),
        "runs": runs,
        "records": records,
        "summary": {
            "runs": len(runs),
            "decisions": len(records),
            "candidates": candidate_count,
            "victories": victories,
            "defeats": len(runs) - victories,
            "selected_for_relabel": selected_count,
            "relabels_avoided": len(records) - selected_count,
            "selection_reason_counts": reason_counts,
            "probe_search_simulations": len(records) * config.probe_teacher.search_simulations,
            "probe_evaluation_simulations": candidate_count
            * config.probe_teacher.evaluation_samples_per_candidate,
            "relabel_search_simulations": selected_count
            * config.relabel_teacher.search_simulations,
            "relabel_evaluation_simulations": selected_candidate_count
            * config.relabel_teacher.evaluation_samples_per_candidate,
        },
    }
    return {**body, "iteration_id": manifest_identifier(body)}


def _target_regret(target: dict[str, object], candidate_index: int) -> float:
    candidates = _list(target.get("candidates"), "teacher candidates")
    values = [
        _probability(
            _mapping(
                _mapping(candidate, "candidate").get("independent_evaluation"),
                "evaluation",
            ).get("terminal_value"),
            "candidate terminal value",
        )
        for candidate in candidates
    ]
    if candidate_index < 0 or candidate_index >= len(values):
        raise ValueError("Student candidate index is outside the teacher target")
    return max(values) - values[candidate_index]


def _normalized_entropy(policy: Sequence[float]) -> float:
    if len(policy) <= 1:
        return 0.0
    return -sum(value * math.log(max(value, 1e-12)) for value in policy) / math.log(len(policy))


def _teacher_config_from_mapping(value: dict[str, Any]) -> TeacherConfig:
    _exact_keys(
        value,
        {
            "search_simulations",
            "evaluation_samples_per_candidate",
            "exploration_constant",
            "sampling_seed",
            "maximum_rollout_steps",
        },
        "teacher configuration",
    )
    return TeacherConfig(
        search_simulations=_integer(value.get("search_simulations"), "search_simulations"),
        evaluation_samples_per_candidate=_integer(
            value.get("evaluation_samples_per_candidate"),
            "evaluation_samples_per_candidate",
        ),
        exploration_constant=_number(value.get("exploration_constant"), "exploration_constant"),
        sampling_seed=_integer(value.get("sampling_seed"), "sampling_seed"),
        maximum_rollout_steps=_integer(value.get("maximum_rollout_steps"), "maximum_rollout_steps"),
    )


def _objective_from_mapping(value: dict[str, Any]) -> ObjectiveSpec:
    _exact_keys(
        value,
        {
            "id",
            "primary",
            "constraint",
            "whole_run_budget",
            "auxiliary",
            "auxiliary_reward_allowed",
        },
        "objective",
    )
    auxiliary = _list(value.get("auxiliary"), "objective auxiliary")
    if any(not isinstance(item, str) for item in auxiliary):
        raise ValueError("objective auxiliary values must be strings")
    allowed = value.get("auxiliary_reward_allowed")
    if not isinstance(allowed, bool):
        raise ValueError("objective auxiliary_reward_allowed must be boolean")
    return ObjectiveSpec(
        objective_id=_string(value.get("id"), "objective ID"),
        primary=_string(value.get("primary"), "objective primary"),
        constraint=_string(value.get("constraint"), "objective constraint"),
        whole_run_budget=_integer(value.get("whole_run_budget"), "whole_run_budget"),
        auxiliary=tuple(cast(list[str], auxiliary)),
        auxiliary_reward_allowed=allowed,
    )


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
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _number(value: object, label: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _probability(value: object, label: str) -> float:
    result = _number(value, label)
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
