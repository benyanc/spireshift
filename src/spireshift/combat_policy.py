"""Owner-run, saved-evidence combat residual experiment; no game engine or promotion."""

from __future__ import annotations

import copy
import json
import math
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from spireshift.combat_features import CombatLayout, bind_public_combat
from spireshift.combat_foundation import (
    CombatFoundationConfig,
    _pair_evidence,
    _relative_path,
    load_combat_foundation_inputs,
    load_combat_foundation_report,
)
from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.models import (
    _binary_cross_entropy,
    _dot,
    _exact_keys,
    _finite_number,
    _integer,
    _mapping,
    _quantize_artifact,
    _quantized_weights,
    _sigmoid,
    _softmax,
    _weights_as_list,
    _weights_from_list,
)
from spireshift.production_models import (
    ProductionTrainingConfig,
    ProductionTrainingResult,
    _evaluate_policy_weights,
    _load_curriculum_examples,
    _ProductionExample,
    _safe_child,
    production_model_from_checkpoint,
)
from spireshift.representations import CompositionalModelInput
from spireshift.splits import SplitManifest, SplitName
from spireshift.starting_repeatability import _prior_inventory, load_starting_repeatability_config
from spireshift.trajectory_policy import _drift, _id, _identified, _safe

CONFIG_SCHEMA = "combat-policy-training-config-v1"
HEAD_SCHEMA = "public-combat-policy-residual-v1"
CHECKPOINT_SCHEMA = "production-model-checkpoint-v9"
REPORT_SCHEMA = "production-model-training-report-v9"
MODEL_TYPE = "sparse-anchored-public-combat-residual-v1"
CLAIM = "frozen_train_only_combat_auxiliary_residual_candidate"
NORMALIZATION = "equal_signal_run_equal_signal_state_margin_weighted_pairs"
SELECTION_RULE = "minimum_selection_soft_pair_loss_passing_frozen_safety_and_advancement"
CONFIG_FIELDS = {
    "schema_version",
    "config_id",
    "foundation_config",
    "foundation_report_path",
    "foundation_report_id",
    "validation_path",
    "validation_dataset_id",
    "frozen_parent_metrics",
    "optimization",
    "limits",
    "fresh_confirmation",
    "resource_limits",
}
LIMIT_FIELDS = {
    "maximum_pair_loss_increase",
    "maximum_accuracy_drop",
    "maximum_regret_increase",
    "maximum_mean_total_variation",
    "minimum_preference_loss_improvement",
}


@dataclass(frozen=True, slots=True)
class CombatPolicyConfig:
    document: dict[str, Any]

    @classmethod
    def from_mapping(cls, value: object) -> CombatPolicyConfig:
        d = copy.deepcopy(_mapping(value, "combat policy recipe"))
        _exact_keys(d, CONFIG_FIELDS, "combat policy recipe")
        _identified(d, "config_id")
        if d["schema_version"] != CONFIG_SCHEMA:
            raise ValueError("Unsupported combat policy recipe")
        foundation = CombatFoundationConfig.from_mapping(d["foundation_config"])
        for key in ("foundation_report_path", "validation_path"):
            _relative_path(d[key])
        for key in ("foundation_report_id", "validation_dataset_id"):
            _id(d[key], key)
        frozen = _mapping(d["frozen_parent_metrics"], "frozen parent metrics")
        _exact_keys(
            frozen,
            {
                "maximum_floor_distribution",
                "tactical_death_risk",
                "terminal_value",
                "terminal_value_status",
            },
            "frozen metrics",
        )
        for key, value in frozen.items():
            _id(value, key)
        recipe = _mapping(d["optimization"], "combat optimization")
        _exact_keys(
            recipe,
            {
                "epochs",
                "learning_rate",
                "anchor_strength",
                "proximal_strength",
                "gradient_clip",
                "adagrad_epsilon",
                "vector_dimension",
                "normalization",
            },
            "combat optimization",
        )
        if not 1 <= _integer(recipe["epochs"], "epochs") <= 200:
            raise ValueError("Combat epochs must be in [1, 200]")
        for name in (
            "learning_rate",
            "anchor_strength",
            "proximal_strength",
            "gradient_clip",
            "adagrad_epsilon",
        ):
            if _finite_number(recipe[name], name) <= 0:
                raise ValueError("Combat optimizer parameters must be positive")
        if (
            recipe["vector_dimension"] != foundation.document["analysis"]["vector_dimension"]
            or recipe["normalization"] != NORMALIZATION
        ):
            raise ValueError("Combat vector space or complete-run normalization differs")
        limits = _mapping(d["limits"], "combat safety limits")
        _exact_keys(limits, LIMIT_FIELDS, "combat safety limits")
        for key, number in limits.items():
            if _finite_number(number, key) < 0:
                raise ValueError("Combat safety limits must be non-negative")
        if limits["minimum_preference_loss_improvement"] <= 0:
            raise ValueError("Combat advancement needs a positive frozen minimum")
        fresh = _mapping(d["fresh_confirmation"], "fresh combat confirmation")
        _exact_keys(
            fresh,
            {
                "partition",
                "run_offset",
                "run_count",
                "seeds",
                "prior_train_prefix_stop",
                "comparison",
                "max_decisions_per_run",
                "primary_metric",
                "promotion_rule",
                "launch",
                "claim_scope",
            },
            "fresh combat confirmation",
        )
        seeds = fresh["seeds"]
        if (
            not isinstance(seeds, list)
            or not seeds
            or any(type(s) is not int or s < 0 for s in seeds)
            or seeds != sorted(set(seeds))
        ):
            raise ValueError("Fresh confirmation needs unique complete-run seeds")
        if (
            fresh["partition"] != "train"
            or fresh["run_count"] != len(seeds)
            or fresh["run_offset"] != fresh["prior_train_prefix_stop"]
            or _integer(fresh["run_offset"], "fresh offset") < 0
            or _integer(fresh["max_decisions_per_run"], "decision cap") < 1
            or fresh["comparison"] != "paired_policy_only_candidate_vs_frozen_parent"
            or fresh["primary_metric"] != "terminal_full_run_victory"
            or fresh["promotion_rule"] != "no_automatic_promotion_auxiliary_floor_insufficient"
            or fresh["launch"] != "separate_owner_run_after_eligible_training_review"
            or fresh["claim_scope"] != "fresh_train_development_confirmation_not_final_test"
        ):
            raise ValueError("Unsupported fresh complete-run confirmation plan")
        owned = {
            s for group in foundation.document["complete_run_subfolds"].values() for s in group
        }
        if owned & set(seeds):
            raise ValueError("Fresh confirmation overlaps fitting or selection runs")
        caps = _mapping(d["resource_limits"], "combat training caps")
        _exact_keys(caps, {"wall_seconds", "cpu_seconds", "memory_bytes", "storage_bytes"}, "caps")
        if any(_integer(v, k) < 1 for k, v in caps.items()):
            raise ValueError("Combat training caps must be positive")
        return cls(d)

    @property
    def foundation(self) -> CombatFoundationConfig:
        return CombatFoundationConfig.from_mapping(self.document["foundation_config"])


def load_combat_policy_config(path: Path) -> CombatPolicyConfig:
    return CombatPolicyConfig.from_mapping(json.loads(path.read_text()))


def _frozen_metrics(report: dict[str, Any]) -> dict[str, str]:
    return {
        **{
            key: manifest_identifier(value)
            for key, value in report["held_out_metrics"].items()
            if key != "policy"
        },
        "terminal_value_status": manifest_identifier(report["terminal_value_status"]),
    }


@dataclass(frozen=True, slots=True)
class CombatPolicyHead:
    layout: CombatLayout
    dimension: int
    weights: dict[int, float]

    def scores(self, representation: CompositionalModelInput) -> tuple[float, ...]:
        # An epoch-zero artifact reproduces the parent even on an unsupported combat screen.
        if not self.weights or representation.decision_type != "combat":
            return (0.0,) * len(representation.candidates)
        bound = bind_public_combat(representation, self.layout)
        if bound is None:
            raise ValueError("Combat residual cannot bind a combat decision")
        return tuple(_dot(self.weights, features) for features in bound.vectors(self.dimension))

    def as_dict(self) -> dict[str, Any]:
        body = {
            "schema_version": HEAD_SCHEMA,
            "encoder_id": self.layout.encoder_id,
            "layout": self.layout.as_dict(),
            "vector_dimension": self.dimension,
            "weights": _weights_as_list(self.weights),
            "scope": "public_combat_only",
        }
        return {**body, "head_id": manifest_identifier(body)}

    @classmethod
    def from_mapping(cls, value: object) -> CombatPolicyHead:
        d = _mapping(value, "combat policy head")
        _exact_keys(
            d,
            {
                "schema_version",
                "encoder_id",
                "layout",
                "vector_dimension",
                "weights",
                "scope",
                "head_id",
            },
            "combat policy head",
        )
        _identified(d, "head_id")
        layout = CombatLayout.from_mapping(d["layout"])
        dimension = _integer(d["vector_dimension"], "combat dimension")
        if (
            d["schema_version"] != HEAD_SCHEMA
            or d["encoder_id"] != layout.encoder_id
            or d["scope"] != "public_combat_only"
            or not 64 <= dimension <= 65536
        ):
            raise ValueError("Unsupported combat head scope or feature space")
        weights = _weights_from_list(d["weights"], dimension, "combat weights")
        if _weights_as_list(weights) != d["weights"]:
            raise ValueError("Combat head weights must be canonical and quantized")
        return cls(layout, dimension, weights)


@dataclass(frozen=True, slots=True)
class CombatRecord:
    example: _ProductionExample
    features: tuple[dict[int, float], ...]
    parent_scores: tuple[float, ...]
    pairs: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class CombatPolicyInputs:
    parent_checkpoint: dict[str, Any]
    parent_report: dict[str, Any]
    audit: dict[str, Any]
    training_config: ProductionTrainingConfig
    anchors: tuple[_ProductionExample, ...]
    validation: tuple[_ProductionExample, ...]
    seed_verification: dict[str, Any]


def load_combat_policy_inputs(
    *,
    config: CombatPolicyConfig,
    project_root: Path,
    upstream_root: Path,
    split_manifest: SplitManifest,
    ruleset: RulesetIdentity,
    objective: ObjectiveSpec,
) -> CombatPolicyInputs:
    """Owner's full source verification: read saved lessons once, initialize no environment."""
    d = CombatPolicyConfig.from_mapping(config.document).document
    root = project_root.resolve()
    cached = load_combat_foundation_report(
        _safe_child(root, d["foundation_report_path"]), config.foundation
    )
    if (
        cached["report_id"] != d["foundation_report_id"]
        or cached["decision"]["pilot_data_sufficient"] is not True
    ):
        raise ValueError("Combat training requires the frozen passing owner data audit")
    fresh = d["fresh_confirmation"]
    train_seeds = split_manifest.seeds(SplitName.TRAIN)
    offset = fresh["run_offset"]
    if list(train_seeds[offset : offset + fresh["run_count"]]) != fresh["seeds"]:
        raise ValueError("Combat fresh confirmation seed window differs from the split")
    study = load_starting_repeatability_config(
        _safe_child(root, config.foundation.document["starting_study"]["config_path"])
    )
    stop = study.collection.runner.run_offset + len(study.collection.seeds)
    if fresh["prior_train_prefix_stop"] < max(stop, study.document["prior_train_prefix_stop"]):
        raise ValueError("Combat fresh cohort must follow previously inspected starting seeds")
    inventories = [
        _prior_inventory(s, root, split_manifest, ruleset)
        for s in study.document["prior_seed_sources"]
    ]
    excluded = set(train_seeds[: fresh["prior_train_prefix_stop"]])
    excluded.update(s for inv in inventories for s in inv["complete_run_seeds"])
    if excluded & set(fresh["seeds"]):
        raise ValueError("Combat confirmation overlaps previously fitted or inspected runs")
    foundation = load_combat_foundation_inputs(
        config=config.foundation,
        project_root=root,
        upstream_root=upstream_root,
        split_manifest=split_manifest,
        ruleset=ruleset,
        objective=objective,
    )
    if foundation.audit != cached:
        raise ValueError("Combat source audit regenerated different bindings or labels")
    parent = foundation.parent_checkpoint
    if _frozen_metrics(foundation.parent_report) != d["frozen_parent_metrics"]:
        raise ValueError("Combat parent validation metrics differ from the frozen recipe")
    if parent["schema_version"] != "production-model-checkpoint-v2":
        raise ValueError("This frozen combat pilot requires the accepted v2 parent")
    training = ProductionTrainingConfig.from_mapping(parent["training_config"])
    document, state_set, validation = _load_curriculum_examples(
        _safe_child(root, d["validation_path"]), split_manifest=split_manifest, config=training
    )
    if (
        document["dataset_id"] != d["validation_dataset_id"]
        or document["dataset_id"] != foundation.parent_report["validation_dataset_id"]
        or state_set.partition != "validation"
        or state_set.ruleset_manifest_id != ruleset.manifest_id
        or document["objective"] != objective.as_dict()
        or any(
            split_manifest.split_for_seed(x.run_seed) is not SplitName.VALIDATION
            for x in validation
        )
    ):
        raise ValueError("Combat validation differs from the parent's original development corpus")
    return CombatPolicyInputs(
        parent,
        foundation.parent_report,
        cached,
        training,
        foundation.examples,
        validation,
        {
            "scope": "content_addressed_seed_metadata_no_case_replay",
            "prior_inventories": inventories,
            "excluded_seed_count": len(excluded),
            "fresh_seeds": fresh["seeds"],
            "disjoint": True,
        },
    )


def _records(
    examples: tuple[_ProductionExample, ...],
    config: CombatPolicyConfig,
    parent: dict[int, float],
) -> tuple[CombatRecord, ...]:
    result = []
    foundation = config.foundation.document
    layout = CombatLayout.from_mapping(foundation["layout"])
    for item in examples:
        if item.decision_type != "combat":
            continue
        try:
            bound = bind_public_combat(item.representation, layout)
        except ValueError as error:
            raise ValueError(
                f"Combat training binding failed at {item.state_id}: {error}"
            ) from error
        if bound is None or bound.source_action_ids != tuple(
            c.source_action_id for c in item.representation.candidates
        ):
            raise ValueError("Combat training candidate alignment differs")
        features = bound.vectors(config.document["optimization"]["vector_dimension"])
        pairs = []
        for left in range(len(features)):
            for right in range(left + 1, len(features)):
                pair = _pair_evidence(item, left, right, foundation["analysis"])
                if pair["reliable_advancement"] and features[left] != features[right]:
                    pairs.append({**pair, "left": left, "right": right})
        result.append(
            CombatRecord(
                item,
                features,
                tuple(_dot(parent, f) for f in item.candidate_features),
                tuple(pairs),
            )
        )
    return tuple(result)


def _pair_weights(records: tuple[CombatRecord, ...]) -> dict[str, tuple[float, ...]]:
    """Each informative seed contributes equally; states and correlated pairs do not inflate it."""
    counts = Counter(r.example.run_seed for r in records if r.pairs)
    result = {}
    for r in records:
        if r.pairs:
            margins = [abs(2 * p["left_preference_probability"] - 1) for p in r.pairs]
            scale = 1 / len(counts) / counts[r.example.run_seed] / sum(margins)
            result[r.example.state_id] = tuple(m * scale for m in margins)
    return result


def _scores(record: CombatRecord, weights: dict[int, float]) -> tuple[float, ...]:
    return tuple(
        a + _dot(weights, f) for a, f in zip(record.parent_scores, record.features, strict=True)
    )


def _gradient(
    records: tuple[CombatRecord, ...], weights: dict[int, float], recipe: dict[str, Any]
) -> dict[int, float]:
    gradient: dict[int, float] = defaultdict(float)
    pair_weights = _pair_weights(records)
    anchor_counts = Counter(r.example.run_seed for r in records)
    for record in records:
        scores = _scores(record, weights)
        for pair, scale in zip(
            record.pairs, pair_weights.get(record.example.state_id, ()), strict=True
        ):
            left, right = pair["left"], pair["right"]
            error = scale * (
                _sigmoid(scores[left] - scores[right]) - pair["left_preference_probability"]
            )
            for features, sign in ((record.features[left], 1), (record.features[right], -1)):
                for index, v in features.items():
                    gradient[index] += sign * error * v
        anchor_scale = (
            recipe["anchor_strength"] / len(anchor_counts) / anchor_counts[record.example.run_seed]
        )
        for features, before, after in zip(
            record.features, _softmax(record.parent_scores), _softmax(scores), strict=True
        ):
            for index, v in features.items():
                gradient[index] += anchor_scale * (after - before) * v
    for index, v in weights.items():
        gradient[index] += recipe["proximal_strength"] * v
    return dict(gradient)


def _combat_metrics(records: tuple[CombatRecord, ...], weights: dict[int, float]) -> dict[str, Any]:
    pair_weights = _pair_weights(records)
    loss = accuracy = 0.0
    regret = variation = 0.0
    counts = Counter(r.example.run_seed for r in records)
    changed = 0
    for r in records:
        scores = _scores(r, weights)
        for pair, scale in zip(r.pairs, pair_weights.get(r.example.state_id, ()), strict=True):
            left, right, target = pair["left"], pair["right"], pair["left_preference_probability"]
            margin = scores[left] - scores[right]
            loss += scale * _binary_cross_entropy(_sigmoid(margin), target)
            accuracy += scale * int(margin != 0 and (margin > 0) == (target > 0.5))
        scale = 1 / len(counts) / counts[r.example.run_seed]
        chosen = max(range(len(scores)), key=scores.__getitem__)
        previous = max(range(len(scores)), key=r.parent_scores.__getitem__)
        regret += scale * (
            max(r.example.mean_progress_utilities) - r.example.mean_progress_utilities[chosen]
        )
        variation += (
            scale
            * sum(
                abs(a - b) for a, b in zip(_softmax(scores), _softmax(r.parent_scores), strict=True)
            )
            / 2
        )
        changed += int(chosen != previous)
    return cast(
        dict[str, Any],
        _quantize_artifact(
            {
                "combat_states": len(records),
                "combat_runs": len(counts),
                "signal_states": len(pair_weights),
                "signal_runs": len({r.example.run_seed for r in records if r.pairs}),
                "pairs": sum(len(r.pairs) for r in records),
                "weighted_soft_pair_loss": loss if pair_weights else None,
                "weighted_directional_accuracy": accuracy if pair_weights else None,
                "mean_run_auxiliary_regret": regret,
                "mean_run_total_variation": variation,
                "changed_actions": changed,
            }
        ),
    )


def _combat_safe(
    current: dict[str, Any], baseline: dict[str, Any], limits: dict[str, Any], *, advancement: bool
) -> dict[str, bool]:
    checks = {
        "combat_regret": current["mean_run_auxiliary_regret"]
        <= baseline["mean_run_auxiliary_regret"] + limits["maximum_regret_increase"],
        "combat_drift": current["mean_run_total_variation"]
        <= limits["maximum_mean_total_variation"],
    }
    if baseline["weighted_soft_pair_loss"] is not None:
        checks.update(
            combat_pair_loss=current["weighted_soft_pair_loss"]
            <= baseline["weighted_soft_pair_loss"] + limits["maximum_pair_loss_increase"],
            combat_accuracy=current["weighted_directional_accuracy"]
            >= baseline["weighted_directional_accuracy"] - limits["maximum_accuracy_drop"],
        )
    if advancement:
        checks["advancement"] = (
            current["weighted_soft_pair_loss"]
            <= baseline["weighted_soft_pair_loss"] - limits["minimum_preference_loss_improvement"]
        )
    return checks


def _combined(
    examples: tuple[_ProductionExample, ...],
    records: tuple[CombatRecord, ...],
    offset: int,
) -> tuple[_ProductionExample, ...]:
    features = {r.example.state_id: r.features for r in records}
    return tuple(
        replace(
            x,
            candidate_features=tuple(
                {**a, **{offset + i: v for i, v in b.items()}}
                for a, b in zip(x.candidate_features, features[x.state_id], strict=True)
            ),
        )
        if x.state_id in features
        else x
        for x in examples
    )


def train_combat_policy_inputs(
    *,
    inputs: CombatPolicyInputs,
    config: CombatPolicyConfig,
    progress: Callable[[int, int], None] | None = None,
) -> ProductionTrainingResult:
    """Fit only the residual using fitting seeds; final validation cannot choose an epoch."""
    d = CombatPolicyConfig.from_mapping(config.document).document
    parent, parent_report = inputs.parent_checkpoint, inputs.parent_report
    foundation = config.foundation.document
    if (
        inputs.audit["report_id"] != d["foundation_report_id"]
        or inputs.audit["decision"]["pilot_data_sufficient"] is not True
        or parent["model_id"] != foundation["model_id"]
        or parent_report["report_id"] != foundation["training_report_id"]
        or _frozen_metrics(parent_report) != d["frozen_parent_metrics"]
    ):
        raise ValueError("Combat training input bindings differ")
    if parent["heads"]["terminal_value"]["status"] != "blocked" or any(
        o.terminal_victory
        for x in inputs.anchors + inputs.validation
        for batch in x.outcomes
        for o in batch
    ):
        raise ValueError(
            "This auxiliary combat pilot requires the recorded all-zero terminal labels"
        )
    runs = foundation["complete_run_subfolds"]
    if {x.run_seed for x in inputs.anchors} != set(runs["fit"] + runs["selection"]):
        raise ValueError("Combat training must retain the audited complete-run folds")
    if set(runs["fit"] + runs["selection"]) & {x.run_seed for x in inputs.validation}:
        raise ValueError("Combat validation shares training runs")
    model = production_model_from_checkpoint(parent)
    all_records = _records(inputs.anchors, config, model.policy_weights)
    validation_records = _records(inputs.validation, config, model.policy_weights)
    fit = tuple(r for r in all_records if r.example.run_seed in runs["fit"])
    selection = tuple(r for r in all_records if r.example.run_seed in runs["selection"])
    for role, records in (("fit", fit), ("selection", selection)):
        summary = inputs.audit["summary"]["by_subfold"][role]
        metrics = _combat_metrics(records, {})
        if (
            metrics["pairs"] != summary["learnable_advancement_pairs"]
            or metrics["signal_runs"] != summary["signal_runs"]
            or not metrics["pairs"]
        ):
            raise ValueError("Combat fitting labels differ from the completed audit")
    offset = inputs.training_config.vector_dimension + inputs.training_config.interaction_dimension
    combined_train = _combined(inputs.anchors, all_records, offset)
    selection_anchors = tuple(x for x in combined_train if x.run_seed in runs["selection"])
    combined_validation = _combined(inputs.validation, validation_records, offset)
    parent_weights = dict(model.policy_weights)
    soft = parent_report["held_out_metrics"]["policy"]["soft_target_baseline"]

    def combined_weights(weights: dict[int, float]) -> dict[int, float]:
        return {**parent_weights, **{offset + i: v for i, v in weights.items()}}

    def original_metrics(
        weights: dict[int, float], examples: tuple[_ProductionExample, ...]
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            _quantize_artifact(
                _evaluate_policy_weights(
                    combined_weights(weights), examples, inputs.training_config, soft_baseline=soft
                )
            ),
        )

    selection_baseline = _combat_metrics(selection, {})
    selection_original_baseline = original_metrics({}, selection_anchors)
    recipe, limits = d["optimization"], d["limits"]
    weights: dict[int, float] = {}
    accumulators: dict[int, float] = defaultdict(float)
    best_weights: dict[int, float] = {}
    selected_epoch = 0
    best_loss = float(selection_baseline["weighted_soft_pair_loss"])
    history = []
    layout = CombatLayout.from_mapping(foundation["layout"])
    for epoch in range(1, recipe["epochs"] + 1):
        gradient = _gradient(fit, weights, recipe)
        norm = math.sqrt(sum(v * v for v in gradient.values()))
        scale = min(1.0, recipe["gradient_clip"] / max(norm, 1e-12))
        for index in sorted(gradient):
            value = gradient[index] * scale
            accumulators[index] += value * value
            weights[index] = weights.get(index, 0) - recipe["learning_rate"] * value / (
                math.sqrt(accumulators[index]) + recipe["adagrad_epsilon"]
            )
        weights = _quantized_weights(weights)
        metrics = _combat_metrics(selection, weights)
        original = original_metrics(weights, selection_anchors)
        drift = cast(
            dict[str, Any],
            _quantize_artifact(
                _drift(combined_weights(weights), parent_weights, selection_anchors)
            ),
        )
        checks = {
            **_safe(original, selection_original_baseline, drift, limits),
            **_combat_safe(metrics, selection_baseline, limits, advancement=True),
        }
        if all(checks.values()) and metrics["weighted_soft_pair_loss"] < best_loss:
            selected_epoch, best_loss, best_weights = (
                epoch,
                metrics["weighted_soft_pair_loss"],
                dict(weights),
            )
        history.append(
            {
                "epoch": epoch,
                "head_id": CombatPolicyHead(layout, recipe["vector_dimension"], weights).as_dict()[
                    "head_id"
                ],
                "fit_combat": _combat_metrics(fit, weights),
                "selection_combat": metrics,
                "selection_original_policy": original,
                "selection_original_drift": drift,
                "checks": checks,
            }
        )
        if progress is not None and (epoch % 10 == 0 or epoch == recipe["epochs"]):
            progress(epoch, recipe["epochs"])
    # Inspect the original development validation once, after freezing the selected train epoch.
    validation_baseline = original_metrics({}, combined_validation)
    validation_metrics = original_metrics(best_weights, combined_validation)
    validation_drift = cast(
        dict[str, Any],
        _quantize_artifact(
            _drift(combined_weights(best_weights), parent_weights, combined_validation)
        ),
    )
    validation_combat_baseline = _combat_metrics(validation_records, {})
    validation_combat = _combat_metrics(validation_records, best_weights)
    validation_checks = {
        **_safe(validation_metrics, validation_baseline, validation_drift, limits),
        **_combat_safe(validation_combat, validation_combat_baseline, limits, advancement=False),
    }
    eligible = selected_epoch > 0 and all(validation_checks.values())
    head = CombatPolicyHead(layout, recipe["vector_dimension"], best_weights).as_dict()
    binding = {
        "config": d,
        "head": head,
        "selected_epoch": selected_epoch,
        "parent_schema_version": parent["schema_version"],
        "parent_model_type": parent["model_type"],
    }
    checkpoint_body = {k: copy.deepcopy(v) for k, v in parent.items() if k != "model_id"}
    checkpoint_body.update(
        schema_version=CHECKPOINT_SCHEMA, model_type=MODEL_TYPE, combat_policy_residual=binding
    )
    checkpoint = {**checkpoint_body, "model_id": manifest_identifier(checkpoint_body)}
    serialized_model = production_model_from_checkpoint(checkpoint)
    noncombat = 0
    for item in inputs.validation:
        before = model.predict(item.representation)
        after = serialized_model.predict(item.representation)
        if (
            before.tactical_death_risk != after.tactical_death_risk
            or before.maximum_floor_reach != after.maximum_floor_reach
            or before.terminal_value != after.terminal_value
        ):
            raise ValueError("Combat training changed a frozen non-policy prediction")
        if item.decision_type != "combat":
            noncombat += 1
            if after != before:
                raise ValueError("Combat training changed a non-combat prediction")
        reference = next(x for x in combined_validation if x.state_id == item.state_id)
        expected = _softmax(
            tuple(_dot(combined_weights(best_weights), f) for f in reference.candidate_features)
        )
        if max(abs(a - b) for a, b in zip(expected, after.policy, strict=True)) > 1e-10:
            raise ValueError("Serialized combat inference differs from training feature scores")
    held_out = copy.deepcopy(parent_report["held_out_metrics"])
    held_out["policy"] = validation_metrics
    body = cast(
        dict[str, Any],
        _quantize_artifact(
            {
                "schema_version": REPORT_SCHEMA,
                "model_type": MODEL_TYPE,
                "model_id": checkpoint["model_id"],
                "config": d,
                "selected_epoch": selected_epoch,
                "selected_head_id": head["head_id"],
                "train_dataset_id": foundation["dataset_id"],
                "validation_dataset_id": d["validation_dataset_id"],
                "split_manifest_id": foundation["split_manifest_id"],
                "training_runs": len(runs["fit"] + runs["selection"]),
                "validation_runs": len({x.run_seed for x in inputs.validation}),
                "training_records": len(inputs.anchors),
                "validation_records": len(inputs.validation),
                "parent_selection_combat": selection_baseline,
                "parent_selection_policy": selection_original_baseline,
                "parent_validation_policy": validation_baseline,
                "parent_validation_combat": validation_combat_baseline,
                "training_history": history,
                "selection_rule": SELECTION_RULE,
                "selection_refit": False,
                "held_out_metrics": held_out,
                "validation_drift": validation_drift,
                "validation_combat": validation_combat,
                "validation_checks": validation_checks,
                "candidate_eligible": eligible,
                "status": "requires_fresh_confirmation" if eligible else "rejected_or_no_update",
                "serialization_checks": {
                    "all_original_heads_frozen": True,
                    "all_non_policy_predictions_unchanged": True,
                    "training_inference_aligned": True,
                    "noncombat_predictions_unchanged": noncombat,
                },
                "seed_verification": inputs.seed_verification,
                "optimizer_steps": recipe["epochs"],
                "terminal_value_status": parent_report["terminal_value_status"],
                "terminal_victory_positive_labels": 0,
                "games_replayed": 0,
                "simulations": 0,
                "checkpoint_promoted": False,
                "foundation_ready": False,
                "adaptive_controller_allowed": False,
                "claim_scope": CLAIM,
            }
        ),
    )
    report = {**body, "report_id": manifest_identifier(body)}
    validate_combat_policy_report(report, checkpoint=checkpoint)
    return ProductionTrainingResult(checkpoint, report)


def combat_checkpoint_parent(value: object) -> tuple[dict[str, Any], CombatPolicyHead]:
    checkpoint = copy.deepcopy(_mapping(value, "combat checkpoint"))
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
            "combat_policy_residual",
        },
        "combat checkpoint",
    )
    _identified(checkpoint, "model_id")
    if checkpoint["schema_version"] != CHECKPOINT_SCHEMA or checkpoint["model_type"] != MODEL_TYPE:
        raise ValueError("Unsupported combat checkpoint")
    binding = _mapping(checkpoint.pop("combat_policy_residual"), "combat residual binding")
    _exact_keys(
        binding,
        {"config", "head", "selected_epoch", "parent_schema_version", "parent_model_type"},
        "combat binding",
    )
    config = CombatPolicyConfig.from_mapping(binding["config"])
    head = CombatPolicyHead.from_mapping(binding["head"])
    if (
        head.layout.as_dict() != config.foundation.document["layout"]
        or head.dimension != config.document["optimization"]["vector_dimension"]
        or not 0
        <= _integer(binding["selected_epoch"], "selected epoch")
        <= config.document["optimization"]["epochs"]
        or (binding["selected_epoch"] == 0 and head.weights)
        or binding["parent_schema_version"] != "production-model-checkpoint-v2"
        or binding["parent_model_type"] != "sparse-pairwise-curriculum-multihead-v2"
    ):
        raise ValueError("Combat head, epoch or parent schema binding differs")
    checkpoint["schema_version"] = binding["parent_schema_version"]
    checkpoint["model_type"] = binding["parent_model_type"]
    checkpoint["model_id"] = manifest_identifier(
        {k: v for k, v in checkpoint.items() if k != "model_id"}
    )
    if checkpoint["model_id"] != config.foundation.document["model_id"]:
        raise ValueError("Combat checkpoint changed an original parent head or provenance")
    return checkpoint, head


def validate_combat_policy_report(
    report: object, *, checkpoint: dict[str, Any] | None = None
) -> dict[str, Any]:
    d = _mapping(report, "combat training report")
    _exact_keys(
        d,
        {
            "schema_version",
            "report_id",
            "model_id",
            "model_type",
            "config",
            "selected_epoch",
            "selected_head_id",
            "train_dataset_id",
            "validation_dataset_id",
            "split_manifest_id",
            "training_runs",
            "validation_runs",
            "training_records",
            "validation_records",
            "parent_selection_combat",
            "parent_selection_policy",
            "parent_validation_policy",
            "parent_validation_combat",
            "training_history",
            "selection_rule",
            "selection_refit",
            "held_out_metrics",
            "validation_drift",
            "validation_combat",
            "validation_checks",
            "candidate_eligible",
            "status",
            "serialization_checks",
            "seed_verification",
            "optimizer_steps",
            "terminal_value_status",
            "terminal_victory_positive_labels",
            "games_replayed",
            "simulations",
            "checkpoint_promoted",
            "foundation_ready",
            "adaptive_controller_allowed",
            "claim_scope",
        },
        "combat training report",
    )
    _identified(d, "report_id")
    config = CombatPolicyConfig.from_mapping(d["config"])
    f = config.foundation.document
    if (
        d["schema_version"] != REPORT_SCHEMA
        or d["model_type"] != MODEL_TYPE
        or d["claim_scope"] != CLAIM
        or d["selection_rule"] != SELECTION_RULE
        or d["selection_refit"] is not False
        or d["train_dataset_id"] != f["dataset_id"]
        or d["validation_dataset_id"] != config.document["validation_dataset_id"]
        or d["split_manifest_id"] != f["split_manifest_id"]
        or d["training_runs"]
        != len(f["complete_run_subfolds"]["fit"] + f["complete_run_subfolds"]["selection"])
    ):
        raise ValueError("Combat report source binding or selection scope differs")
    for field in ("games_replayed", "simulations", "terminal_victory_positive_labels"):
        if type(d[field]) is not int or d[field] != 0:
            raise ValueError("Combat training may not claim game replay or terminal positives")
    for field in ("checkpoint_promoted", "foundation_ready", "adaptive_controller_allowed"):
        if d[field] is not False:
            raise ValueError("Combat auxiliary experiment cannot promote or certify readiness")
    if d["optimizer_steps"] != config.document["optimization"]["epochs"]:
        raise ValueError("Combat optimizer step count differs")
    history = d["training_history"]
    if not isinstance(history, list) or len(history) != d["optimizer_steps"]:
        raise ValueError("Combat history denominator differs")
    best = 0
    best_loss = d["parent_selection_combat"]["weighted_soft_pair_loss"]
    limits = config.document["limits"]
    for epoch, row in enumerate(history, 1):
        checks = {
            **_safe(
                row["selection_original_policy"],
                d["parent_selection_policy"],
                row["selection_original_drift"],
                limits,
            ),
            **_combat_safe(
                row["selection_combat"], d["parent_selection_combat"], limits, advancement=True
            ),
        }
        if row["epoch"] != epoch or row["checks"] != checks:
            raise ValueError("Combat history checks differ from frozen limits")
        _id(row["head_id"], "history head ID")
        loss = row["selection_combat"]["weighted_soft_pair_loss"]
        if all(checks.values()) and loss < best_loss:
            best, best_loss = epoch, loss
    if d["selected_epoch"] != best:
        raise ValueError("Combat selected epoch differs from train-only selection")
    validation_checks = {
        **_safe(
            d["held_out_metrics"]["policy"],
            d["parent_validation_policy"],
            d["validation_drift"],
            limits,
        ),
        **_combat_safe(
            d["validation_combat"], d["parent_validation_combat"], limits, advancement=False
        ),
    }
    eligible = best > 0 and all(validation_checks.values())
    if (
        d["validation_checks"] != validation_checks
        or d["candidate_eligible"] is not eligible
        or d["status"] != ("requires_fresh_confirmation" if eligible else "rejected_or_no_update")
    ):
        raise ValueError("Combat result eligibility differs from frozen checks")
    if _frozen_metrics(d) != config.document["frozen_parent_metrics"]:
        raise ValueError("Combat report changed frozen non-policy validation metrics")
    if best == 0 and (
        d["held_out_metrics"]["policy"] != d["parent_validation_policy"]
        or d["validation_combat"] != d["parent_validation_combat"]
        or d["validation_drift"]["mean_total_variation"] != 0
        or d["validation_drift"]["changed_actions"] != 0
    ):
        raise ValueError("Epoch-zero combat fallback must reproduce the parent diagnostics")
    checks = d["serialization_checks"]
    if (
        any(
            checks.get(key) is not True
            for key in (
                "all_original_heads_frozen",
                "all_non_policy_predictions_unchanged",
                "training_inference_aligned",
            )
        )
        or checks["noncombat_predictions_unchanged"]
        != d["validation_records"] - d["validation_combat"]["combat_states"]
        or d["seed_verification"]["fresh_seeds"] != config.document["fresh_confirmation"]["seeds"]
        or d["seed_verification"]["disjoint"] is not True
    ):
        raise ValueError("Combat saved inference or fresh seed checks differ")
    if checkpoint is not None:
        _, head = combat_checkpoint_parent(checkpoint)
        binding = checkpoint["combat_policy_residual"]
        if (
            d["model_id"] != checkpoint["model_id"]
            or d["config"] != binding["config"]
            or best != binding["selected_epoch"]
            or d["selected_head_id"] != head.as_dict()["head_id"]
            or (best > 0 and history[best - 1]["head_id"] != d["selected_head_id"])
        ):
            raise ValueError("Combat report selected head/checkpoint differs")
    return d


def summarize_combat_policy_training(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "valid": True,
        "model_id": report["model_id"],
        "report_id": report["report_id"],
        "selected_epoch": report["selected_epoch"],
        "candidate_eligible": report["candidate_eligible"],
        "status": report["status"],
        "validation_checks": report["validation_checks"],
        "parent_selection_combat": report["parent_selection_combat"],
        "selected_selection_combat": report["training_history"][report["selected_epoch"] - 1][
            "selection_combat"
        ]
        if report["selected_epoch"]
        else report["parent_selection_combat"],
        "validation_combat": report["validation_combat"],
        "serialization_checks": report["serialization_checks"],
        "fresh_confirmation_runs_reserved": len(report["config"]["fresh_confirmation"]["seeds"]),
        "games_replayed": 0,
        "terminal_victory_positive_labels": 0,
        "checkpoint_promoted": False,
        "foundation_ready": False,
        "adaptive_controller_allowed": False,
        "claim_scope": CLAIM,
    }
