from __future__ import annotations

import copy
import hashlib
import json
import math
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.core.types import DecisionType, LegalAction, Observation
from spireshift.models import (
    _binary_cross_entropy,
    _candidate_features,
    _dot,
    _exact_keys,
    _finite_number,
    _integer,
    _list,
    _mapping,
    _quantize_artifact,
    _quantized_weights,
    _sigmoid,
    _softmax,
    _string,
    _weights_as_list,
)
from spireshift.production_models import (
    PRODUCTION_CHECKPOINT_SCHEMA_VERSION,
    PRODUCTION_MODEL_TYPE,
    ProductionTrainingConfig,
    ProductionTrainingResult,
    _evaluate_policy_weights,
    _evangambit_action_from_id,
    _load_curriculum_examples,
    _ProductionExample,
    load_production_model_checkpoint,
    load_production_training_report,
    production_model_from_checkpoint,
)
from spireshift.representations import build_model_input, vectorize_model_input
from spireshift.splits import SplitManifest, SplitName
from spireshift.trajectory_preferences import load_trajectory_preference_collection
from spireshift.trajectory_search import TRAJECTORY_SELECTION_RANK_ORDER, TrajectorySearchConfig

CONFIG_SCHEMA = "trajectory-policy-training-config-v1"
CHECKPOINT_SCHEMA = "production-model-checkpoint-v6"
REPORT_SCHEMA = "production-model-training-report-v6"
MODEL_TYPE = "sparse-anchored-trajectory-policy-v1"
FROZEN_HEADS = ("terminal_value", "tactical_death_risk", "maximum_floor_distribution")
INPUT_FIELDS = {
    "parent_model_id",
    "parent_training_report_id",
    "collection_id",
    "search_report_id",
    "search_config_id",
    "train_dataset_id",
    "validation_dataset_id",
    "split_manifest_id",
    "ruleset_manifest_id",
}
LIMIT_FIELDS = {
    "maximum_pair_loss_increase",
    "maximum_accuracy_drop",
    "maximum_regret_increase",
    "maximum_mean_total_variation",
    "minimum_preference_loss_improvement",
}
CONFIG_FIELDS = {
    "schema_version",
    "config_id",
    "objective_id",
    "inputs",
    "epochs",
    "learning_rate",
    "anchor_strength",
    "preference_strength",
    "proximal_strength",
    "gradient_clip",
    "adagrad_epsilon",
    "selection_fraction",
    "selection_salt",
    "rank_weights",
    "limits",
}


def _identified(document: dict[str, Any], field: str) -> None:
    if document.get(field) != manifest_identifier(
        {k: v for k, v in document.items() if k != field}
    ):
        raise ValueError(f"{field} identity mismatch")


def _id(value: object, label: str) -> str:
    result = _string(value, label)
    if len(result) != 71 or not result.startswith("sha256:"):
        raise ValueError(f"{label} is not a content identifier")
    if any(character not in "0123456789abcdef" for character in result[7:]):
        raise ValueError(f"{label} is not a content identifier")
    return result


@dataclass(frozen=True, slots=True)
class TrajectoryPolicyConfig:
    document: dict[str, Any]

    @classmethod
    def from_mapping(cls, value: object) -> TrajectoryPolicyConfig:
        doc = copy.deepcopy(_mapping(value, "trajectory policy config"))
        _exact_keys(doc, CONFIG_FIELDS, "trajectory policy config")
        _identified(doc, "config_id")
        if doc["schema_version"] != CONFIG_SCHEMA or doc["objective_id"] != "terminal-victory-v1":
            raise ValueError("Unsupported trajectory policy schema or objective")
        inputs = _mapping(doc["inputs"], "trajectory policy inputs")
        _exact_keys(inputs, INPUT_FIELDS, "trajectory policy inputs")
        for key, item in inputs.items():
            _id(item, key)
        if not 1 <= _integer(doc["epochs"], "epochs") <= 200:
            raise ValueError("Trajectory policy epochs must be in [1, 200]")
        for key in (
            "learning_rate",
            "anchor_strength",
            "preference_strength",
            "proximal_strength",
            "gradient_clip",
            "adagrad_epsilon",
        ):
            if _finite_number(doc[key], key) <= 0:
                raise ValueError(f"{key} must be positive")
        if not 0 < _finite_number(doc["selection_fraction"], "selection fraction") < 1:
            raise ValueError("Selection fraction must be in (0, 1)")
        _string(doc["selection_salt"], "selection salt")
        weights = _mapping(doc["rank_weights"], "rank weights")
        _exact_keys(weights, set(TRAJECTORY_SELECTION_RANK_ORDER), "rank weights")
        for key, item in weights.items():
            if not 0 <= _finite_number(item, key) <= 1:
                raise ValueError("Rank weights must be in [0, 1]")
        if weights["victory"] != 0 or weights["distinct_public_states_on_floor"] != 0:
            raise ValueError("Victory and state-count tie-breakers cannot become auxiliary targets")
        if weights["maximum_floor"] != 1 or weights["boss_reached"] != 1:
            raise ValueError("Floor and boss advancement must keep unit weight")
        limits = _mapping(doc["limits"], "non-regression limits")
        _exact_keys(limits, LIMIT_FIELDS, "non-regression limits")
        for key, item in limits.items():
            if _finite_number(item, key) < 0:
                raise ValueError("Non-regression limits must be non-negative")
        if limits["minimum_preference_loss_improvement"] <= 0:
            raise ValueError("Preference advancement must exceed a positive frozen minimum")
        return cls(doc)

    @property
    def config_id(self) -> str:
        return str(self.document["config_id"])


def load_trajectory_policy_config(path: Path) -> TrajectoryPolicyConfig:
    return TrajectoryPolicyConfig.from_mapping(json.loads(path.read_text(encoding="utf-8")))


@dataclass(frozen=True, slots=True)
class _Preference:
    run_seed: int
    component: str
    decision_type: str
    weight: float
    preferred: dict[int, float]
    disfavored: dict[int, float]
    candidates: tuple[dict[int, float], ...]


def _features(
    record: dict[str, Any], ruleset: RulesetIdentity, config: ProductionTrainingConfig
) -> tuple[dict[int, float], ...]:
    raw = _mapping(record["source_observation"], "source observation")
    observation = Observation(
        schema_version=str(raw["schema_version"]),
        patch_id=str(raw["patch_id"]),
        decision_type=DecisionType(raw["decision_type"]),
        public_state=_mapping(raw["public_state"], "public state"),
        state_hash=str(raw["state_hash"]),
    )
    if observation.decision_type.value != record["decision_type"]:
        raise ValueError("Trajectory preference decision type is misaligned")
    actions = tuple(_action(str(item)) for item in record["candidate_action_ids"])
    # The existing representation verifies the public-state hash and rejects privileged fields.
    representation = build_model_input(ruleset, observation, actions)
    vector = vectorize_model_input(representation, dimension=config.vector_dimension)
    if vector.source_action_ids != tuple(record["candidate_action_ids"]):
        raise ValueError("Trajectory preference candidate order is misaligned")
    return tuple(
        _candidate_features(
            vector.state, candidate, config.vector_dimension, config.interaction_dimension
        )
        for candidate in vector.candidates
    )


def _action(action_id: str) -> LegalAction:
    if action_id.startswith("evangambit:"):
        return _evangambit_action_from_id(action_id)
    raise ValueError(f"Unsupported trajectory action ID: {action_id}")


def _preference_metrics(
    weights: dict[int, float], examples: tuple[_Preference, ...]
) -> dict[str, Any]:
    def metrics(values: tuple[_Preference, ...]) -> dict[str, Any]:
        counts = Counter(item.run_seed for item in values if item.weight > 0)
        numerator = denominator = 0.0
        correct = 0
        for item in values:
            margin = _dot(weights, item.preferred) - _dot(weights, item.disfavored)
            correct += int(margin > 0)
            if item.weight > 0:
                weight = item.weight / counts[item.run_seed]
                numerator += weight * _binary_cross_entropy(_sigmoid(margin), 1.0)
                denominator += weight
        return {
            "records": len(values),
            "eligible_records": sum(item.weight > 0 for item in values),
            "unique_runs": len({item.run_seed for item in values}),
            "directional_accuracy": correct / len(values) if values else None,
            "weighted_pair_loss": numerator / denominator if denominator else None,
            "effective_weight": denominator,
        }

    return {
        **metrics(examples),
        "by_rank_component": {
            component: metrics(tuple(item for item in examples if item.component == component))
            for component in sorted({item.component for item in examples})
        },
        "by_run": {
            str(seed): metrics(tuple(item for item in examples if item.run_seed == seed))
            for seed in sorted({item.run_seed for item in examples})
        },
    }


def _drift(
    weights: dict[int, float], parent: dict[int, float], examples: tuple[_ProductionExample, ...]
) -> dict[str, Any]:
    variations = []
    changed = 0
    for item in examples:
        previous = _softmax(tuple(_dot(parent, candidate) for candidate in item.candidate_features))
        current = _softmax(tuple(_dot(weights, candidate) for candidate in item.candidate_features))
        variations.append(sum(abs(a - b) for a, b in zip(previous, current, strict=True)) / 2)
        changed += int(
            max(range(len(current)), key=current.__getitem__)
            != max(range(len(previous)), key=previous.__getitem__)
        )
    return {
        "mean_total_variation": sum(variations) / len(variations),
        "maximum_total_variation": max(variations),
        "changed_actions": changed,
        "decisions": len(variations),
    }


def _safe(
    metrics: dict[str, Any], baseline: dict[str, Any], drift: dict[str, Any], limits: dict[str, Any]
) -> dict[str, bool]:
    return {
        "original_auxiliary_gate": metrics["auxiliary_policy_gate"]["passed"] is True,
        "pair_loss": metrics["weighted_pairwise_cross_entropy"]
        <= baseline["weighted_pairwise_cross_entropy"] + limits["maximum_pair_loss_increase"],
        "accuracy": metrics["decisive_pair_accuracy"]
        >= baseline["decisive_pair_accuracy"] - limits["maximum_accuracy_drop"],
        "regret": metrics["mean_progress_utility_regret"]
        <= baseline["mean_progress_utility_regret"] + limits["maximum_regret_increase"],
        "drift": drift["mean_total_variation"] <= limits["maximum_mean_total_variation"],
    }


def _gradient(
    weights: dict[int, float],
    parent: dict[int, float],
    preferences: tuple[_Preference, ...],
    anchors: tuple[_ProductionExample, ...],
    recipe: dict[str, Any],
) -> dict[int, float]:
    gradient: dict[int, float] = defaultdict(float)
    preference_counts = Counter(item.run_seed for item in preferences)
    anchor_counts = Counter(item.run_seed for item in anchors)
    for item in preferences:
        error = (
            recipe["preference_strength"]
            * item.weight
            / preference_counts[item.run_seed]
            / len(preference_counts)
            * (_sigmoid(_dot(weights, item.preferred) - _dot(weights, item.disfavored)) - 1)
        )
        for features, sign in ((item.preferred, 1), (item.disfavored, -1)):
            for index, value in features.items():
                gradient[index] += sign * error * value
    for anchor in anchors:
        previous = _softmax(tuple(_dot(parent, features) for features in anchor.candidate_features))
        current = _softmax(tuple(_dot(weights, features) for features in anchor.candidate_features))
        scale = recipe["anchor_strength"] / anchor_counts[anchor.run_seed] / len(anchor_counts)
        for features, a, b in zip(anchor.candidate_features, previous, current, strict=True):
            for index, value in features.items():
                gradient[index] += scale * (b - a) * value
    for index in set(parent) | set(weights):
        gradient[index] += recipe["proximal_strength"] * (
            weights.get(index, 0) - parent.get(index, 0)
        )
    return dict(gradient)


def _folds(seeds: set[int], recipe: dict[str, Any]) -> dict[str, list[int]]:
    if len(seeds) < 4:
        raise ValueError("Trajectory fine-tuning requires at least four complete train runs")
    ranked = sorted(
        seeds,
        key=lambda seed: hashlib.sha256(f"{recipe['selection_salt']}|{seed}".encode()).hexdigest(),
    )
    count = min(len(seeds) - 1, max(1, round(len(seeds) * recipe["selection_fraction"])))
    return {"fit": sorted(ranked[count:]), "selection": sorted(ranked[:count])}


@dataclass(frozen=True, slots=True)
class TrajectoryPolicyInputs:
    parent_checkpoint: dict[str, Any]
    parent_report: dict[str, Any]
    training_config: ProductionTrainingConfig
    collection: dict[str, Any]
    train_document: dict[str, Any]
    validation_document: dict[str, Any]
    anchors: tuple[_ProductionExample, ...]
    validation: tuple[_ProductionExample, ...]
    preferences: tuple[_Preference, ...]
    preference_records: tuple[dict[str, Any], ...]
    exclusions: dict[str, int]
    runs: dict[str, list[int]]


def load_trajectory_policy_inputs(
    *,
    parent_checkpoint_path: Path,
    parent_report_path: Path,
    collection_path: Path,
    search_report_path: Path,
    search_config: TrajectorySearchConfig,
    train_report_path: Path,
    validation_report_path: Path,
    split_manifest: SplitManifest,
    ruleset: RulesetIdentity,
    config: TrajectoryPolicyConfig,
    objective: ObjectiveSpec,
) -> TrajectoryPolicyInputs:
    """Verify and reconstruct saved training inputs without replay or optimization."""
    recipe = TrajectoryPolicyConfig.from_mapping(config.document).document
    if objective.objective_id != recipe["objective_id"]:
        raise ValueError("Trajectory policy objective differs from the frozen recipe")
    parent_checkpoint = load_production_model_checkpoint(parent_checkpoint_path)
    parent_report = load_production_training_report(
        parent_report_path, checkpoint=parent_checkpoint
    )
    training_config = ProductionTrainingConfig.from_mapping(parent_checkpoint["training_config"])
    if parent_checkpoint["heads"]["terminal_value"]["status"] != "blocked":
        raise ValueError("This auxiliary-only recipe requires a blocked terminal-value parent")
    evidence = load_trajectory_preference_collection(
        collection_path,
        search_report_path=search_report_path,
        search_config=search_config,
        split_manifest=split_manifest,
    )
    collection = evidence.document
    train_doc, train_states, anchors = _load_curriculum_examples(
        train_report_path,
        split_manifest=split_manifest,
        config=training_config,
    )
    validation_doc, validation_states, validation = _load_curriculum_examples(
        validation_report_path,
        split_manifest=split_manifest,
        config=training_config,
    )
    actual_inputs = {
        "parent_model_id": parent_checkpoint["model_id"],
        "parent_training_report_id": parent_report["report_id"],
        "collection_id": collection["collection_id"],
        "search_report_id": collection["search_report_id"],
        "search_config_id": search_config.config_id,
        "train_dataset_id": train_doc["dataset_id"],
        "validation_dataset_id": validation_doc["dataset_id"],
        "split_manifest_id": split_manifest.manifest_id,
        "ruleset_manifest_id": ruleset.manifest_id,
    }
    if recipe["inputs"] != actual_inputs:
        raise ValueError("Trajectory training input identities differ from the frozen recipe")
    if (
        collection["source_model_id"] != parent_checkpoint["model_id"]
        or collection["source_training_report_id"] != parent_report["report_id"]
        or parent_checkpoint["train_dataset_id"] != train_doc["dataset_id"]
        or parent_report["validation_dataset_id"] != validation_doc["dataset_id"]
    ):
        raise ValueError("Trajectory source model or anchor corpus differs from the parent")
    for doc in (parent_checkpoint, collection):
        if (
            doc["ruleset_manifest_id"] != ruleset.manifest_id
            or doc["split_manifest_id"] != split_manifest.manifest_id
            or doc["objective_id"] != recipe["objective_id"]
        ):
            raise ValueError("Trajectory training ruleset, split, or objective differs")
    if train_states.partition != "train" or validation_states.partition != "validation":
        raise ValueError("Trajectory anchor and validation partitions differ")
    if any(
        doc["signal_assessment"]["auxiliary_policy_signal_pass"] is not True
        for doc in (train_doc, validation_doc)
    ):
        raise ValueError("Trajectory anchor curriculum failed its signal gate")
    for items, partition in ((anchors, SplitName.TRAIN), (validation, SplitName.VALIDATION)):
        if not items or any(
            split_manifest.split_for_seed(item.run_seed) is not partition for item in items
        ):
            raise ValueError("Trajectory curricula have wrong complete-run ownership")
        if any(item.representation.ruleset_manifest_id != ruleset.manifest_id for item in items):
            raise ValueError("Trajectory anchor representation ruleset differs")
    preferences: list[_Preference] = []
    preference_records: list[dict[str, Any]] = []
    exclusions: Counter[str] = Counter()
    for component in evidence.components:
        for record in component["preferences"] + component["excluded_mutations"]:
            features = _features(record, ruleset, training_config)
            if record["label"] != "improved":
                exclusions[record["label"]] += 1
                continue
            rank_component = str(record["deciding_rank_component"])
            weight = float(recipe["rank_weights"][rank_component])
            if weight == 0:
                exclusions[rank_component] += 1
            ids = record["candidate_action_ids"]
            preference_records.append(record)
            preferences.append(
                _Preference(
                    run_seed=int(record["run_seed"]),
                    component=rank_component,
                    decision_type=str(record["decision_type"]),
                    weight=weight,
                    preferred=features[ids.index(record["preferred_action_id"])],
                    disfavored=features[ids.index(record["disfavored_action_id"])],
                    candidates=features,
                )
            )
    examples = tuple(preferences)
    eligible = tuple(item for item in examples if item.weight > 0)
    runs = _folds(
        {item.run_seed for item in anchors} | {item.run_seed for item in examples}, recipe
    )
    fit_seeds, selection_seeds = set(runs["fit"]), set(runs["selection"])
    fit = tuple(item for item in eligible if item.run_seed in fit_seeds)
    selection = tuple(item for item in eligible if item.run_seed in selection_seeds)
    fit_anchors = tuple(item for item in anchors if item.run_seed in fit_seeds)
    selection_anchors = tuple(item for item in anchors if item.run_seed in selection_seeds)
    if (
        not fit_anchors
        or not selection_anchors
        or len({item.run_seed for item in fit}) < 2
        or len({item.run_seed for item in selection}) < 2
    ):
        raise ValueError(
            "Trajectory fitting/selection subfolds need anchors and two preference runs each"
        )
    strong_selection = tuple(
        item
        for item in selection
        if item.component in {"maximum_floor", "boss_reached", "act1_cleared"}
    )
    if not strong_selection:
        raise ValueError("Trajectory selection subfold has no advancement comparisons")
    return TrajectoryPolicyInputs(
        parent_checkpoint,
        parent_report,
        training_config,
        collection,
        train_doc,
        validation_doc,
        anchors,
        validation,
        examples,
        tuple(preference_records),
        dict(sorted(exclusions.items())),
        runs,
    )


def train_trajectory_policy(
    *,
    parent_checkpoint_path: Path,
    parent_report_path: Path,
    collection_path: Path,
    search_report_path: Path,
    search_config: TrajectorySearchConfig,
    train_report_path: Path,
    validation_report_path: Path,
    split_manifest: SplitManifest,
    ruleset: RulesetIdentity,
    config: TrajectoryPolicyConfig,
    objective: ObjectiveSpec,
) -> ProductionTrainingResult:
    inputs = load_trajectory_policy_inputs(
        parent_checkpoint_path=parent_checkpoint_path,
        parent_report_path=parent_report_path,
        collection_path=collection_path,
        search_report_path=search_report_path,
        search_config=search_config,
        train_report_path=train_report_path,
        validation_report_path=validation_report_path,
        split_manifest=split_manifest,
        ruleset=ruleset,
        config=config,
        objective=objective,
    )
    recipe = config.document
    parent_checkpoint, parent_report = inputs.parent_checkpoint, inputs.parent_report
    parent_model = production_model_from_checkpoint(parent_checkpoint)
    training_config = inputs.training_config
    collection = inputs.collection
    train_doc, validation_doc = inputs.train_document, inputs.validation_document
    anchors, validation = inputs.anchors, inputs.validation
    examples, exclusions, runs = inputs.preferences, inputs.exclusions, inputs.runs
    eligible = tuple(item for item in examples if item.weight > 0)
    fit = tuple(item for item in eligible if item.run_seed in runs["fit"])
    selection = tuple(item for item in eligible if item.run_seed in runs["selection"])
    fit_anchors = tuple(item for item in anchors if item.run_seed in runs["fit"])
    selection_anchors = tuple(item for item in anchors if item.run_seed in runs["selection"])
    strong_selection = tuple(
        item
        for item in selection
        if item.component in {"maximum_floor", "boss_reached", "act1_cleared"}
    )
    baseline = dict(parent_model.policy_weights)
    soft_baseline = parent_report["held_out_metrics"]["policy"]["soft_target_baseline"]

    def policy_metrics(
        weights: dict[int, float], items: tuple[_ProductionExample, ...]
    ) -> dict[str, Any]:
        return _evaluate_policy_weights(
            weights, items, training_config, soft_baseline=soft_baseline
        )

    anchor_baseline = _quantize_artifact(policy_metrics(baseline, selection_anchors))
    validation_baseline = _quantize_artifact(policy_metrics(baseline, validation))
    preference_baseline = _quantize_artifact(_preference_metrics(baseline, selection))
    strong_baseline = _quantize_artifact(_preference_metrics(baseline, strong_selection))
    weights = dict(baseline)
    accumulators: dict[int, float] = defaultdict(float)
    best_weights = dict(baseline)
    best_loss = float(preference_baseline["weighted_pair_loss"])
    selected_epoch = 0
    history = []
    for epoch in range(1, int(recipe["epochs"]) + 1):
        gradient = _gradient(weights, baseline, fit, fit_anchors, recipe)
        norm = math.sqrt(sum(value * value for value in gradient.values()))
        scale = min(1.0, float(recipe["gradient_clip"]) / max(norm, 1e-12))
        for index in sorted(gradient):
            value = gradient[index] * scale
            accumulators[index] += value * value
            weights[index] = weights.get(index, 0.0) - recipe["learning_rate"] * value / (
                math.sqrt(accumulators[index]) + recipe["adagrad_epsilon"]
            )
        # Score exactly the quantized weights that can be saved and evaluated.
        weights = _quantized_weights(weights)
        metrics = _quantize_artifact(policy_metrics(weights, selection_anchors))
        drift = _quantize_artifact(_drift(weights, baseline, selection_anchors))
        preferences_metrics = _quantize_artifact(_preference_metrics(weights, selection))
        strong_metrics = _quantize_artifact(_preference_metrics(weights, strong_selection))
        checks = _safe(metrics, anchor_baseline, drift, recipe["limits"])
        checks["preference_advancement"] = (
            preferences_metrics["weighted_pair_loss"]
            <= preference_baseline["weighted_pair_loss"]
            - recipe["limits"]["minimum_preference_loss_improvement"]
        )
        checks["strong_advancement"] = (
            strong_metrics["weighted_pair_loss"]
            <= strong_baseline["weighted_pair_loss"]
            - recipe["limits"]["minimum_preference_loss_improvement"]
        )
        loss = float(preferences_metrics["weighted_pair_loss"])
        if all(checks.values()) and loss < best_loss:
            selected_epoch, best_loss, best_weights = epoch, loss, dict(weights)
        history.append(
            {
                "epoch": epoch,
                "policy_weights_id": manifest_identifier(_weights_as_list(weights)),
                "fit_preferences": _preference_metrics(weights, fit),
                "selection_preferences": preferences_metrics,
                "strong_selection_preferences": strong_metrics,
                "selection_policy": metrics,
                "selection_drift": drift,
                "checks": checks,
            }
        )
    validation_metrics = _quantize_artifact(policy_metrics(best_weights, validation))
    validation_drift = _quantize_artifact(_drift(best_weights, baseline, validation))
    validation_checks = _safe(
        validation_metrics, validation_baseline, validation_drift, recipe["limits"]
    )
    candidate_eligible = selected_epoch > 0 and all(validation_checks.values())
    frozen = {key: manifest_identifier(parent_checkpoint["heads"][key]) for key in FROZEN_HEADS}
    binding = {
        "recipe": recipe,
        "selected_epoch": selected_epoch,
        "policy_only": True,
        "frozen_head_ids": frozen,
        "complete_run_subfolds": runs,
        "selection_rule": "minimum_preference_loss_passing_train_anchor_and_advancement_checks",
        "selection_refit": False,
    }
    body = {
        k: copy.deepcopy(v)
        for k, v in parent_checkpoint.items()
        if k
        not in {"model_id", "causal_preference_set_id", "policy_blend", "trajectory_finetuning"}
    }
    body.update(
        schema_version=CHECKPOINT_SCHEMA, model_type=MODEL_TYPE, trajectory_finetuning=binding
    )
    body["heads"]["policy"]["weights"] = _weights_as_list(best_weights)
    checkpoint = {**body, "model_id": manifest_identifier(body)}
    held_out = copy.deepcopy(parent_report["held_out_metrics"])
    held_out["policy"] = validation_metrics
    report_body = {
        "schema_version": REPORT_SCHEMA,
        "model_type": MODEL_TYPE,
        "model_id": checkpoint["model_id"],
        "train_dataset_id": train_doc["dataset_id"],
        "validation_dataset_id": validation_doc["dataset_id"],
        "split_manifest_id": split_manifest.manifest_id,
        "training_runs": len(runs["fit"]) + len(runs["selection"]),
        "validation_runs": len({item.run_seed for item in validation}),
        "training_records": len(anchors),
        "validation_records": len(validation),
        "floor_thresholds": list(parent_model.floor_thresholds),
        "trajectory_finetuning": binding,
        "collection_summary": collection["summary"],
        "exclusions": dict(sorted(exclusions.items())),
        "eligible_preferences": len(eligible),
        "fit_preferences": len(fit),
        "selection_preferences": len(selection),
        "fit_anchor_records": len(fit_anchors),
        "selection_anchor_records": len(selection_anchors),
        "parent_selection_preferences": preference_baseline,
        "parent_strong_selection_preferences": strong_baseline,
        "parent_selection_policy": anchor_baseline,
        "parent_validation_policy": validation_baseline,
        "training_history": history,
        "held_out_metrics": held_out,
        "validation_drift": validation_drift,
        "validation_checks": validation_checks,
        "candidate_eligible": candidate_eligible,
        "status": "validation_candidate" if candidate_eligible else "rejected_or_no_update",
        "preference_diagnostics": _preference_metrics(best_weights, examples),
        "inference_diagnostics": _inference_diagnostics(checkpoint, validation),
        "terminal_value_status": copy.deepcopy(parent_report["terminal_value_status"]),
        "terminal_victory_positive_labels": 0,
        "checkpoint_promoted": False,
        "claim_scope": "anchored_train_trajectory_auxiliary_policy_candidate",
        "selection_note": (
            "Parent previously saw its anchor corpus; selection is held out only from this update. "
            "Validation is reused development evidence, not a new final test."
        ),
    }
    report_body = _quantize_artifact(report_body)
    report = {**report_body, "report_id": manifest_identifier(report_body)}
    validate_trajectory_report(report, checkpoint=checkpoint)
    return ProductionTrainingResult(checkpoint, report)


def _inference_diagnostics(
    checkpoint: dict[str, Any], examples: tuple[_ProductionExample, ...]
) -> dict[str, Any]:
    model = production_model_from_checkpoint(checkpoint)
    durations = []
    for item in examples[:8]:
        started = time.perf_counter()
        prediction = model.predict(item.representation)
        durations.append(time.perf_counter() - started)
        if prediction.source_action_ids != tuple(
            candidate.source_action_id for candidate in item.representation.candidates
        ):
            raise ValueError("Fine-tuned policy inference is not candidate aligned")
        selected = max(range(len(prediction.policy)), key=prediction.policy.__getitem__)
        if not item.representation.action_mask[selected]:
            raise ValueError("Fine-tuned policy selected an action excluded by its public mask")
    return {
        "source": "saved_public_validation_inputs_no_engine",
        "decisions": len(durations),
        "candidate_alignment_pass": True,
        "legal_selection_pass": True,
        "public_state_only": True,
        "mean_seconds": sum(durations) / len(durations),
        "maximum_seconds": max(durations),
    }


def validate_trajectory_checkpoint(checkpoint: dict[str, Any]) -> None:
    binding = _validate_binding(checkpoint.get("trajectory_finetuning"))
    recipe = binding["recipe"]
    for key in ("train_dataset_id", "split_manifest_id", "ruleset_manifest_id"):
        if checkpoint.get(key) != recipe["inputs"][key]:
            raise ValueError("Trajectory checkpoint recipe provenance differs")
    if (
        checkpoint.get("objective_id") != recipe["objective_id"]
        or checkpoint.get("model_type") != MODEL_TYPE
    ):
        raise ValueError("Trajectory checkpoint model type or objective differs")
    heads = _mapping(checkpoint.get("heads"), "heads")
    for key in FROZEN_HEADS:
        if manifest_identifier(_mapping(heads.get(key), key)) != binding["frozen_head_ids"][key]:
            raise ValueError(f"Frozen {key} head changed")
    if heads["terminal_value"].get("status") != "blocked":
        raise ValueError("Auxiliary trajectory evidence cannot promote terminal value")


def _validate_binding(value: object) -> dict[str, Any]:
    binding = _mapping(value, "trajectory fine-tuning")
    _exact_keys(
        binding,
        {
            "recipe",
            "selected_epoch",
            "policy_only",
            "frozen_head_ids",
            "complete_run_subfolds",
            "selection_rule",
            "selection_refit",
        },
        "trajectory fine-tuning",
    )
    recipe = TrajectoryPolicyConfig.from_mapping(binding["recipe"]).document
    epoch = _integer(binding["selected_epoch"], "selected epoch")
    if (
        not 0 <= epoch <= recipe["epochs"]
        or binding["policy_only"] is not True
        or binding["selection_refit"] is not False
    ):
        raise ValueError("Trajectory selection epoch, policy-only flag, or refit differs")
    if (
        binding["selection_rule"]
        != "minimum_preference_loss_passing_train_anchor_and_advancement_checks"
    ):
        raise ValueError("Unsupported trajectory policy selection rule")
    frozen = _mapping(binding["frozen_head_ids"], "frozen head IDs")
    _exact_keys(frozen, set(FROZEN_HEADS), "frozen head IDs")
    for key, item in frozen.items():
        _id(item, key)
    runs = _mapping(binding["complete_run_subfolds"], "complete-run subfolds")
    _exact_keys(runs, {"fit", "selection"}, "complete-run subfolds")
    for label, values in runs.items():
        seeds = [_integer(item, label) for item in _list(values, label)]
        if not seeds or seeds != sorted(set(seeds)) or min(seeds) < 0:
            raise ValueError("Trajectory subfold seeds are empty, duplicate, or unsorted")
    if set(runs["fit"]) & set(runs["selection"]):
        raise ValueError("Trajectory fitting/selection run subfolds overlap")
    if runs != _folds(set(runs["fit"]) | set(runs["selection"]), recipe):
        raise ValueError("Trajectory subfold assignment differs from the frozen recipe")
    return binding


def validate_trajectory_report(
    report: dict[str, Any], *, checkpoint: dict[str, Any] | None = None
) -> None:
    fields = {
        "schema_version",
        "report_id",
        "model_type",
        "model_id",
        "train_dataset_id",
        "validation_dataset_id",
        "split_manifest_id",
        "training_runs",
        "validation_runs",
        "training_records",
        "validation_records",
        "floor_thresholds",
        "trajectory_finetuning",
        "collection_summary",
        "exclusions",
        "eligible_preferences",
        "fit_preferences",
        "selection_preferences",
        "fit_anchor_records",
        "selection_anchor_records",
        "parent_selection_preferences",
        "parent_strong_selection_preferences",
        "parent_selection_policy",
        "parent_validation_policy",
        "training_history",
        "held_out_metrics",
        "validation_drift",
        "validation_checks",
        "candidate_eligible",
        "status",
        "preference_diagnostics",
        "inference_diagnostics",
        "terminal_value_status",
        "terminal_victory_positive_labels",
        "checkpoint_promoted",
        "claim_scope",
        "selection_note",
    }
    _exact_keys(report, fields, "trajectory training report")
    _identified(report, "report_id")
    binding = _validate_binding(report["trajectory_finetuning"])
    recipe = binding["recipe"]
    if report["schema_version"] != REPORT_SCHEMA or report["model_type"] != MODEL_TYPE:
        raise ValueError("Unsupported trajectory training report")
    for key in ("train_dataset_id", "validation_dataset_id", "split_manifest_id"):
        if report[key] != recipe["inputs"][key]:
            raise ValueError("Trajectory report input provenance differs")
    if checkpoint is not None:
        if (
            report["model_id"] != checkpoint["model_id"]
            or binding != checkpoint["trajectory_finetuning"]
        ):
            raise ValueError("Trajectory report and checkpoint differ")
        validate_trajectory_checkpoint(checkpoint)
    if (
        report["claim_scope"] != "anchored_train_trajectory_auxiliary_policy_candidate"
        or report["terminal_victory_positive_labels"] != 0
        or report["checkpoint_promoted"] is not False
    ):
        raise ValueError("Trajectory report exceeds auxiliary-only evidence")
    if report["terminal_value_status"].get("promoted") is not False:
        raise ValueError("Trajectory evidence cannot promote terminal value")
    if report["training_runs"] != len(binding["complete_run_subfolds"]["fit"]) + len(
        binding["complete_run_subfolds"]["selection"]
    ):
        raise ValueError("Trajectory report complete-run count differs")
    if (
        report["eligible_preferences"]
        != report["fit_preferences"] + report["selection_preferences"]
    ):
        raise ValueError("Trajectory report preference counts differ")
    if (
        report["training_records"]
        != report["fit_anchor_records"] + report["selection_anchor_records"]
    ):
        raise ValueError("Trajectory report anchor counts differ")
    history = _list(report["training_history"], "training history")
    if [item.get("epoch") for item in history] != list(range(1, recipe["epochs"] + 1)):
        raise ValueError("Trajectory training history epochs differ")
    checks = _safe(
        report["held_out_metrics"]["policy"],
        report["parent_validation_policy"],
        report["validation_drift"],
        recipe["limits"],
    )
    eligible = binding["selected_epoch"] > 0 and all(checks.values())
    if report["validation_checks"] != checks or report["candidate_eligible"] is not eligible:
        raise ValueError("Trajectory validation checks differ")
    expected_status = "validation_candidate" if eligible else "rejected_or_no_update"
    if report["status"] != expected_status:
        raise ValueError("Trajectory candidate status differs")
    if binding["selected_epoch"] and not all(
        history[binding["selected_epoch"] - 1]["checks"].values()
    ):
        raise ValueError("Selected trajectory epoch did not pass its frozen checks")
    passing: list[dict[str, Any]] = []
    for raw in history:
        item = _mapping(raw, "trajectory training epoch")
        epoch_checks = _safe(
            item["selection_policy"],
            report["parent_selection_policy"],
            item["selection_drift"],
            recipe["limits"],
        )
        minimum = recipe["limits"]["minimum_preference_loss_improvement"]
        epoch_checks["preference_advancement"] = (
            item["selection_preferences"]["weighted_pair_loss"]
            <= report["parent_selection_preferences"]["weighted_pair_loss"] - minimum
        )
        epoch_checks["strong_advancement"] = (
            item["strong_selection_preferences"]["weighted_pair_loss"]
            <= report["parent_strong_selection_preferences"]["weighted_pair_loss"] - minimum
        )
        if item["checks"] != epoch_checks:
            raise ValueError("Trajectory epoch checks differ from the frozen recipe")
        _id(item.get("policy_weights_id"), "epoch policy weights ID")
        if all(epoch_checks.values()):
            passing.append(item)
    selected = (
        min(passing, key=lambda item: float(item["selection_preferences"]["weighted_pair_loss"]))
        if passing
        else None
    )
    if binding["selected_epoch"] != (0 if selected is None else selected["epoch"]):
        raise ValueError("Trajectory epoch selection differs from the frozen rule")
    if (
        checkpoint is not None
        and selected is not None
        and selected["policy_weights_id"]
        != manifest_identifier(checkpoint["heads"]["policy"]["weights"])
    ):
        raise ValueError("Selected trajectory policy weights differ from the recorded epoch")


def trajectory_checkpoint_as_base(checkpoint: dict[str, Any]) -> dict[str, Any]:
    validate_trajectory_checkpoint(checkpoint)
    body = {
        k: copy.deepcopy(v)
        for k, v in checkpoint.items()
        if k not in {"model_id", "trajectory_finetuning"}
    }
    body.update(
        schema_version=PRODUCTION_CHECKPOINT_SCHEMA_VERSION, model_type=PRODUCTION_MODEL_TYPE
    )
    return {**body, "model_id": manifest_identifier(body)}
