"""One owner-run neural combat pilot on saved evidence; no games or automatic next round."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import random
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from spireshift.combat_features import CombatLayout, bind_public_combat
from spireshift.combat_policy import (
    SELECTION_RULE,
    CombatPolicyConfig,
    CombatPolicyInputs,
    CombatRecord,
    _combat_metrics,
    _combat_safe,
    _combined,
    _frozen_metrics,
    _pair_weights,
    _reconcile_selection_gate_sources,
    _records,
    _selection_checks,
    _validate_combat_training_report,
    load_combat_policy_inputs,
)
from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.models import (
    _dot,
    _exact_keys,
    _finite_number,
    _integer,
    _mapping,
    _quantize_artifact,
    _softmax,
)
from spireshift.neural_combat_features import (
    ENCODER_ID,
    load_printed_card_catalog,
    neural_combat_vectors,
    validate_catalog,
)
from spireshift.production_models import (
    ProductionTrainingResult,
    _evaluate_policy_weights,
    _ProductionExample,
    _safe_child,
    production_model_from_checkpoint,
)
from spireshift.representations import CompositionalModelInput
from spireshift.splits import SplitManifest, SplitName
from spireshift.trajectory_policy import _drift, _id, _identified, _safe

CONFIG_SCHEMA = "neural-combat-policy-training-config-v1"
HEAD_SCHEMA = "public-neural-combat-policy-v1"
CHECKPOINT_SCHEMA = "production-model-checkpoint-v10"
REPORT_SCHEMA = "production-model-training-report-v10"
MODEL_TYPE = "shared-public-combat-neural-policy-v1"
CLAIM = "frozen_train_only_neural_combat_auxiliary_candidate"


@dataclass(frozen=True, slots=True)
class NeuralCombatConfig:
    document: dict[str, Any]

    @classmethod
    def from_mapping(cls, value: object) -> NeuralCombatConfig:
        d = copy.deepcopy(_mapping(value, "neural combat recipe"))
        _exact_keys(
            d,
            {
                "schema_version",
                "config_id",
                "data_config",
                "diagnosis",
                "network",
                "optimization",
                "fresh_confirmation",
                "iteration",
                "resource_limits",
            },
            "neural combat recipe",
        )
        _identified(d, "config_id")
        if d["schema_version"] != CONFIG_SCHEMA:
            raise ValueError("Unsupported neural combat recipe")
        data = CombatPolicyConfig.from_mapping(d["data_config"])
        if data.document["schema_version"] != "combat-policy-training-config-v3":
            raise ValueError("Neural pilot requires the reconciled combat data/gate protocol")
        network = _mapping(d["network"], "neural architecture")
        _exact_keys(
            network,
            {
                "encoder_id",
                "feature_dimension",
                "hidden_units",
                "activation",
                "initialization_seed",
                "card_source_sha256",
                "card_core_sha256",
                "card_catalog_id",
            },
            "neural architecture",
        )
        if (
            network["encoder_id"] != ENCODER_ID
            or network["activation"] != "tanh"
            or not 64 <= _integer(network["feature_dimension"], "feature dimension") <= 4096
            or not 4 <= _integer(network["hidden_units"], "hidden units") <= 128
            or _integer(network["initialization_seed"], "initialization seed") < 0
        ):
            raise ValueError("Neural architecture is outside the frozen bounds")
        for name in ("card_source_sha256", "card_core_sha256"):
            _id(f"sha256:{network[name]}", name)
        _id(network["card_catalog_id"], "printed catalog ID")
        recipe = _mapping(d["optimization"], "neural optimization")
        _exact_keys(
            recipe,
            {
                "epochs",
                "learning_rate",
                "anchor_strength",
                "l2_regularization",
                "gradient_clip",
                "adam_epsilon",
                "adam_beta1",
                "adam_beta2",
                "normalization",
            },
            "neural optimization",
        )
        if (
            recipe["epochs"] != data.document["optimization"]["epochs"]
            or recipe["normalization"] != data.document["optimization"]["normalization"]
        ):
            raise ValueError("Neural pilot changed the source epoch or run-normalization contract")
        for name in (
            "learning_rate",
            "anchor_strength",
            "l2_regularization",
            "gradient_clip",
            "adam_epsilon",
        ):
            if not 0 < _finite_number(recipe[name], name) <= 10:
                raise ValueError("Neural optimizer setting is outside bounds")
        for name in ("adam_beta1", "adam_beta2"):
            if not 0 < _finite_number(recipe[name], name) < 1:
                raise ValueError("Adam moments must be in (0, 1)")
        diagnosis = _mapping(d["diagnosis"], "source diagnosis")
        _exact_keys(diagnosis, {"path", "report_id", "inspected_seeds"}, "source diagnosis")
        _safe_child(Path.cwd(), diagnosis["path"])
        _id(diagnosis["report_id"], "diagnostic ID")
        inspected = diagnosis["inspected_seeds"]
        if (
            not isinstance(inspected, list)
            or not inspected
            or any(type(s) is not int or s < 0 for s in inspected)
            or inspected != sorted(set(inspected))
        ):
            raise ValueError("Diagnostic seeds must be unique complete runs")
        fresh = _mapping(d["fresh_confirmation"], "neural fresh reservation")
        _exact_keys(
            fresh,
            {"partition", "run_offset", "run_count", "seeds", "prior_train_prefix_stop"},
            "neural fresh reservation",
        )
        seeds = fresh["seeds"]
        if (
            fresh["partition"] != "train"
            or not isinstance(seeds, list)
            or not seeds
            or any(type(s) is not int or s < 0 for s in seeds)
            or seeds != sorted(set(seeds))
            or fresh["run_count"] != len(seeds)
            or _integer(fresh["run_offset"], "run offset") != fresh["prior_train_prefix_stop"]
            or fresh["run_offset"]
            < data.document["fresh_confirmation"]["run_offset"]
            + data.document["fresh_confirmation"]["run_count"]
            or set(seeds) & set(inspected)
        ):
            raise ValueError("Neural confirmation must follow the inspected comparison")
        owned = data.foundation.document["complete_run_subfolds"]
        if set(seeds) & set(owned["fit"] + owned["selection"]):
            raise ValueError("Neural reservation overlaps learning runs")
        iteration = _mapping(d["iteration"], "bounded neural iteration")
        _exact_keys(
            iteration,
            {"round", "maximum_rounds", "automatic_followup", "plateau_rule"},
            "bounded neural iteration",
        )
        if (
            iteration["round"] != 1
            or iteration["maximum_rounds"] != 3
            or iteration["automatic_followup"] is not False
            or iteration["plateau_rule"] != "review_after_three_frozen_rounds_without_gameplay_gain"
        ):
            raise ValueError("Only the first owner-reviewed pilot is implemented")
        if d["resource_limits"] != data.document["resource_limits"]:
            raise ValueError("Neural pilot must retain the source training caps")
        return cls(d)

    @property
    def data(self) -> CombatPolicyConfig:
        return CombatPolicyConfig.from_mapping(self.document["data_config"])


def load_neural_combat_config(path: Path) -> NeuralCombatConfig:
    return NeuralCombatConfig.from_mapping(json.loads(path.read_text()))


def _parameters(value: object, rows: int, columns: int) -> tuple[tuple[float, ...], ...]:
    if not isinstance(value, list) or len(value) != rows:
        raise ValueError("Neural parameter matrix shape differs")
    result = []
    for row in value:
        if not isinstance(row, list) or len(row) != columns:
            raise ValueError("Neural parameter row shape differs")
        parsed = tuple(_finite_number(v, "neural parameter") for v in row)
        if any(abs(v) > 100 or round(v, 12) != v for v in parsed):
            raise ValueError("Neural parameters must be bounded and canonically quantized")
        result.append(parsed)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class NeuralCombatHead:
    layout: CombatLayout
    dimension: int
    catalog: dict[str, dict[str, Any]]
    source_sha256: str
    input_weights: tuple[tuple[float, ...], ...]
    hidden_bias: tuple[float, ...]
    output_weights: tuple[float, ...]

    @property
    def active(self) -> bool:
        return any(self.output_weights)

    def feature_scores(self, features: tuple[dict[int, float], ...]) -> tuple[float, ...]:
        return tuple(
            sum(
                output * math.tanh(bias + sum(weights[i] * v for i, v in item.items()))
                for weights, bias, output in zip(
                    self.input_weights, self.hidden_bias, self.output_weights, strict=True
                )
            )
            for item in features
        )

    def scores(self, representation: CompositionalModelInput) -> tuple[float, ...]:
        if not self.active or representation.decision_type != "combat":
            return (0.0,) * len(representation.candidates)
        bound = bind_public_combat(representation, self.layout)
        if bound is None:
            raise ValueError("Neural policy cannot bind the public combat menu")
        return self.feature_scores(neural_combat_vectors(bound, self.catalog, self.dimension))

    def as_dict(self) -> dict[str, Any]:
        body = {
            "schema_version": HEAD_SCHEMA,
            "encoder_id": ENCODER_ID,
            "layout": self.layout.as_dict(),
            "feature_dimension": self.dimension,
            "hidden_units": len(self.hidden_bias),
            "activation": "tanh",
            "card_source_sha256": self.source_sha256,
            "printed_card_catalog": self.catalog,
            "input_weights": [list(row) for row in self.input_weights],
            "hidden_bias": list(self.hidden_bias),
            "output_weights": list(self.output_weights),
            "scope": "public_combat_only",
        }
        return {**body, "head_id": manifest_identifier(body)}

    @classmethod
    def from_mapping(cls, value: object) -> NeuralCombatHead:
        d = _mapping(value, "neural combat head")
        _exact_keys(
            d,
            {
                "schema_version",
                "encoder_id",
                "layout",
                "feature_dimension",
                "hidden_units",
                "activation",
                "card_source_sha256",
                "printed_card_catalog",
                "input_weights",
                "hidden_bias",
                "output_weights",
                "scope",
                "head_id",
            },
            "neural combat head",
        )
        _identified(d, "head_id")
        dimension = _integer(d["feature_dimension"], "feature dimension")
        hidden = _integer(d["hidden_units"], "hidden units")
        if (
            d["schema_version"] != HEAD_SCHEMA
            or d["encoder_id"] != ENCODER_ID
            or d["activation"] != "tanh"
            or d["scope"] != "public_combat_only"
            or not 64 <= dimension <= 4096
            or not 4 <= hidden <= 128
        ):
            raise ValueError("Unsupported neural combat head")
        _id(f"sha256:{d['card_source_sha256']}", "card source")
        return cls(
            CombatLayout.from_mapping(d["layout"]),
            dimension,
            validate_catalog(d["printed_card_catalog"]),
            d["card_source_sha256"],
            _parameters(d["input_weights"], hidden, dimension),
            _parameters([d["hidden_bias"]], 1, hidden)[0],
            _parameters([d["output_weights"]], 1, hidden)[0],
        )


def initial_neural_head(
    config: NeuralCombatConfig, catalog: dict[str, dict[str, Any]]
) -> NeuralCombatHead:
    network = config.document["network"]
    dimension, hidden = network["feature_dimension"], network["hidden_units"]
    rng = random.Random(network["initialization_seed"])
    scale = math.sqrt(6 / (dimension + hidden))
    return NeuralCombatHead(
        config.data.residual_layout,
        dimension,
        validate_catalog(catalog),
        network["card_source_sha256"],
        tuple(
            tuple(round(rng.uniform(-scale, scale), 12) for _ in range(dimension))
            for _ in range(hidden)
        ),
        (0.0,) * hidden,
        (0.0,) * hidden,
    )


def load_neural_combat_inputs(
    *,
    config: NeuralCombatConfig,
    project_root: Path,
    upstream_root: Path,
    split_manifest: SplitManifest,
    ruleset: RulesetIdentity,
    objective: ObjectiveSpec,
) -> tuple[CombatPolicyInputs, dict[str, dict[str, Any]]]:
    d = config.document
    diagnosis = json.loads(_safe_child(project_root.resolve(), d["diagnosis"]["path"]).read_text())
    _identified(diagnosis, "report_id")
    if (
        diagnosis["report_id"] != d["diagnosis"]["report_id"]
        or diagnosis["summary"]["analysis_integrity_pass"] is not True
        or sorted({c["seed"] for c in diagnosis["cases"]}) != d["diagnosis"]["inspected_seeds"]
    ):
        raise ValueError("Neural recipe source diagnosis differs")
    fresh = d["fresh_confirmation"]
    seeds = split_manifest.seeds(SplitName.TRAIN)
    if (
        list(seeds[fresh["run_offset"] : fresh["run_offset"] + fresh["run_count"]])
        != fresh["seeds"]
    ):
        raise ValueError("Neural fresh cohort differs from complete-run split ownership")
    if not set(d["diagnosis"]["inspected_seeds"]) <= set(seeds[: fresh["run_offset"]]):
        raise ValueError("Neural fresh reservation does not exclude inspected evidence")
    network = d["network"]
    core_path = _safe_child(upstream_root.resolve(), "src/Sts2Emulator/Core/Card.cs")
    if hashlib.sha256(core_path.read_bytes()).hexdigest() != network["card_core_sha256"]:
        raise ValueError("Printed card definition semantics changed")
    catalog = load_printed_card_catalog(upstream_root, network["card_source_sha256"])
    if manifest_identifier(catalog) != network["card_catalog_id"]:
        raise ValueError("Parsed printed catalog differs from the frozen recipe")
    inputs = load_combat_policy_inputs(
        config=config.data,
        project_root=project_root,
        upstream_root=upstream_root,
        split_manifest=split_manifest,
        ruleset=ruleset,
        objective=objective,
    )
    return replace(
        inputs,
        seed_verification={
            **inputs.seed_verification,
            "fresh_seeds": fresh["seeds"],
            "historical_data_recipe_reservation_unused": True,
            "neural_diagnosis_report_id": diagnosis["report_id"],
            "printed_catalog_source_verified": True,
        },
    ), catalog


def _numpy() -> Any:
    try:
        import numpy as np
    except ImportError as error:
        raise ValueError("Neural fitting needs the optional 'neural' dependency extra") from error
    return np


def neural_gradient(
    x: Any,
    parameters: tuple[Any, Any, Any],
    records: tuple[CombatRecord, ...],
    recipe: dict[str, Any],
) -> tuple[float, tuple[Any, Any, Any]]:
    """Fully train both layers, with run-balanced pair loss and policy anchoring."""
    np = _numpy()
    w1, bias, w2 = parameters
    hidden = np.tanh(x @ w1.T + bias)
    residual = hidden @ w2
    derivative = np.zeros(len(x), dtype=np.float64)
    pair_weights = _pair_weights(records)
    counts = Counter(r.example.run_seed for r in records)
    loss = 0.0
    at = 0
    for r in records:
        count = len(r.features)
        score = np.asarray(r.parent_scores) + residual[at : at + count]
        for pair, scale in zip(r.pairs, pair_weights.get(r.example.state_id, ()), strict=True):
            left, right, target = pair["left"], pair["right"], pair["left_preference_probability"]
            margin = float(score[left] - score[right])
            probability = 1 / (1 + math.exp(-max(-700.0, min(700.0, margin))))
            loss += scale * (max(margin, 0) - target * margin + math.log1p(math.exp(-abs(margin))))
            error = scale * (probability - target)
            derivative[at + left] += error
            derivative[at + right] -= error
        prior = np.asarray(r.parent_scores)
        prior_log = prior - prior.max()
        prior_log -= np.log(np.exp(prior_log).sum())
        prior = np.exp(prior_log)
        log_policy = score - score.max()
        log_policy -= np.log(np.exp(log_policy).sum())
        policy = np.exp(log_policy)
        anchor_scale = recipe["anchor_strength"] / len(counts) / counts[r.example.run_seed]
        loss += anchor_scale * float(np.sum(prior * (prior_log - log_policy)))
        derivative[at : at + count] += anchor_scale * (policy - prior)
        at += count
    if at != len(x):
        raise ValueError("Neural batch and legal candidate alignment differs")
    l2 = recipe["l2_regularization"]
    loss += l2 / 2 * sum(float(np.sum(p * p)) for p in parameters)
    hidden_derivative = derivative[:, None] * w2 * (1 - hidden * hidden)
    return loss, (
        hidden_derivative.T @ x + l2 * w1,
        hidden_derivative.sum(axis=0) + l2 * bias,
        hidden.T @ derivative + l2 * w2,
    )


def _network_features(
    records: tuple[CombatRecord, ...], head: NeuralCombatHead
) -> tuple[tuple[dict[int, float], ...], ...]:
    batches = []
    for record in records:
        bound = bind_public_combat(record.example.representation, head.layout)
        if bound is None:
            raise ValueError("Neural fitting requires public combat actions")
        batch = neural_combat_vectors(bound, head.catalog, head.dimension)
        if bound.source_action_ids != tuple(
            c.source_action_id for c in record.example.representation.candidates
        ):
            raise ValueError("Neural fitting candidate ordering differs")
        if any(batch[p["left"]] == batch[p["right"]] for p in record.pairs):
            raise ValueError(
                f"Neural feature alias hides a reliable pair at {record.example.state_id}"
            )
        batches.append(batch)
    return tuple(batches)


def _residual_records(
    records: tuple[CombatRecord, ...],
    batches: tuple[tuple[dict[int, float], ...], ...],
    head: NeuralCombatHead,
) -> tuple[CombatRecord, ...]:
    # Reuse the established metrics/gates with a single already-computed logit coordinate.
    # These temporary features are never published as a linear model or training input.
    return tuple(
        replace(r, features=tuple({0: score} for score in head.feature_scores(batch)))
        for r, batch in zip(records, batches, strict=True)
    )


def train_neural_combat_inputs(
    *,
    inputs: CombatPolicyInputs,
    config: NeuralCombatConfig,
    catalog: dict[str, dict[str, Any]],
    progress: Callable[[int, int], None] | None = None,
) -> ProductionTrainingResult:
    config = NeuralCombatConfig.from_mapping(config.document)
    data, d = config.data, config.document
    parent, report = inputs.parent_checkpoint, inputs.parent_report
    foundation = data.foundation.document
    if (
        parent["model_id"] != foundation["model_id"]
        or report["report_id"] != foundation["training_report_id"]
        or inputs.audit["report_id"] != data.document["foundation_report_id"]
        or inputs.audit["decision"]["pilot_data_sufficient"] is not True
        or _frozen_metrics(report) != data.document["frozen_parent_metrics"]
    ):
        raise ValueError("Neural training sources differ from the frozen foundation")
    folds = foundation["complete_run_subfolds"]
    if (
        {x.run_seed for x in inputs.anchors} != set(folds["fit"] + folds["selection"])
        or set(folds["fit"] + folds["selection"]) & {x.run_seed for x in inputs.validation}
        or set(d["fresh_confirmation"]["seeds"])
        & {x.run_seed for x in inputs.anchors + inputs.validation}
    ):
        raise ValueError("Neural complete-run learning/selection/validation ownership differs")
    if parent["heads"]["terminal_value"]["status"] != "blocked" or any(
        o.terminal_victory
        for x in inputs.anchors + inputs.validation
        for batch in x.outcomes
        for o in batch
    ):
        raise ValueError("This auxiliary neural pilot requires the recorded zero victory labels")
    model = production_model_from_checkpoint(parent)
    all_records = _records(inputs.anchors, data, model.policy_weights)
    fit = tuple(r for r in all_records if r.example.run_seed in folds["fit"])
    selection = tuple(r for r in all_records if r.example.run_seed in folds["selection"])
    validation = _records(inputs.validation, data, model.policy_weights)
    for role, records in (("fit", fit), ("selection", selection)):
        baseline = _combat_metrics(records, {})
        audited = inputs.audit["summary"]["by_subfold"][role]
        if (
            baseline["pairs"] != audited["learnable_advancement_pairs"]
            or baseline["signal_runs"] != audited["signal_runs"]
            or not baseline["pairs"]
        ):
            raise ValueError("Neural pilot pair labels differ from the verified audit")
    head = initial_neural_head(config, catalog)
    if manifest_identifier(catalog) != d["network"]["card_catalog_id"]:
        raise ValueError("Neural fitting catalog is not the frozen printed source")
    fit_batches = _network_features(fit, head)
    selection_batches = _network_features(selection, head)
    validation_batches = _network_features(validation, head)
    np = _numpy()
    x = np.zeros((sum(len(batch) for batch in fit_batches), head.dimension), dtype=np.float64)
    for row, features in zip(x, (item for batch in fit_batches for item in batch), strict=True):
        for index, value in features.items():
            row[index] = value
    parameters = (
        np.asarray(head.input_weights),
        np.asarray(head.hidden_bias),
        np.asarray(head.output_weights),
    )
    moments = tuple(np.zeros_like(p) for p in parameters)
    variances = tuple(np.zeros_like(p) for p in parameters)
    selection_anchors = tuple(x for x in inputs.anchors if x.run_seed in folds["selection"])
    offset = inputs.training_config.vector_dimension + inputs.training_config.interaction_dimension
    parent_weights = dict(model.policy_weights)
    soft = report["held_out_metrics"]["policy"]["soft_target_baseline"]

    def metrics(
        examples: tuple[_ProductionExample, ...],
        records: tuple[CombatRecord, ...],
        batches: tuple[tuple[dict[int, float], ...], ...],
        current: NeuralCombatHead,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        residuals = _residual_records(records, batches, current)
        combined = _combined(examples, residuals, offset)
        weights = {**parent_weights, offset: 1.0}
        return cast(
            tuple[dict[str, Any], dict[str, Any], dict[str, Any]],
            _quantize_artifact(
                (
                    _combat_metrics(residuals, {0: 1.0}),
                    _evaluate_policy_weights(
                        weights, combined, inputs.training_config, soft_baseline=soft
                    ),
                    _drift(weights, parent_weights, combined),
                )
            ),
        )

    base_combat, base_policy, _ = metrics(selection_anchors, selection, selection_batches, head)
    _reconcile_selection_gate_sources(
        selection=selection, selection_anchors=selection_anchors, baseline=base_policy, config=data
    )
    best_head, best_epoch, best_loss = head, 0, base_combat["weighted_soft_pair_loss"]
    history = []
    recipe, limits = d["optimization"], data.document["limits"]
    for epoch in range(1, recipe["epochs"] + 1):
        loss, gradients = neural_gradient(x, parameters, fit, recipe)
        if not math.isfinite(loss) or any(not np.isfinite(g).all() for g in gradients):
            raise ValueError("Neural fitting produced nonfinite loss or gradients")
        norm = math.sqrt(sum(float(np.sum(g * g)) for g in gradients))
        scale = min(1.0, recipe["gradient_clip"] / max(norm, 1e-12))
        for p, m, v, gradient in zip(parameters, moments, variances, gradients, strict=True):
            gradient = gradient * scale
            b1, b2 = recipe["adam_beta1"], recipe["adam_beta2"]
            m[:] = b1 * m + (1 - b1) * gradient
            v[:] = b2 * v + (1 - b2) * gradient * gradient
            p -= (
                recipe["learning_rate"]
                * (m / (1 - b1**epoch))
                / (np.sqrt(v / (1 - b2**epoch)) + recipe["adam_epsilon"])
            )
            p[:] = np.round(p, 12)
            if not np.isfinite(p).all() or np.max(np.abs(p)) > 100:
                raise ValueError("Neural parameter update is outside bounds")
        head = replace(
            head,
            input_weights=tuple(tuple(float(v) for v in row) for row in parameters[0]),
            hidden_bias=tuple(float(v) for v in parameters[1]),
            output_weights=tuple(float(v) for v in parameters[2]),
        )
        combat, policy, drift = metrics(selection_anchors, selection, selection_batches, head)
        checks = {
            **_selection_checks(policy, base_policy, drift, data),
            **_combat_safe(combat, base_combat, limits, advancement=True),
        }
        if all(checks.values()) and combat["weighted_soft_pair_loss"] < best_loss:
            best_head, best_epoch, best_loss = head, epoch, combat["weighted_soft_pair_loss"]
        history.append(
            {
                "epoch": epoch,
                "head_id": head.as_dict()["head_id"],
                "fit_combat": metrics(tuple(r.example for r in fit), fit, fit_batches, head)[0],
                "selection_combat": combat,
                "selection_original_policy": policy,
                "selection_original_drift": drift,
                "checks": checks,
            }
        )
        if progress is not None:
            progress(epoch, recipe["epochs"])
    # Original development validation is evaluated after train-only epoch selection.
    empty = initial_neural_head(config, catalog)
    val_base_combat, val_base_policy, _ = metrics(
        inputs.validation, validation, validation_batches, empty
    )
    val_combat, val_policy, val_drift = metrics(
        inputs.validation, validation, validation_batches, best_head
    )
    validation_checks = {
        **_safe(val_policy, val_base_policy, val_drift, limits),
        **_combat_safe(val_combat, val_base_combat, limits, advancement=False),
    }
    eligible = best_epoch > 0 and all(validation_checks.values())
    binding = {
        "config": d,
        "head": best_head.as_dict(),
        "selected_epoch": best_epoch,
        "parent_schema_version": parent["schema_version"],
        "parent_model_type": parent["model_type"],
    }
    body = {k: copy.deepcopy(v) for k, v in parent.items() if k != "model_id"}
    body.update(
        schema_version=CHECKPOINT_SCHEMA, model_type=MODEL_TYPE, neural_combat_policy=binding
    )
    checkpoint = {**body, "model_id": manifest_identifier(body)}
    loaded = production_model_from_checkpoint(checkpoint)
    noncombat = 0
    selected_scores = {
        r.example.state_id: best_head.feature_scores(batch)
        for r, batch in zip(validation, validation_batches, strict=True)
    }
    for item in inputs.validation:
        before, after = model.predict(item.representation), loaded.predict(item.representation)
        if (
            before.tactical_death_risk != after.tactical_death_risk
            or before.maximum_floor_reach != after.maximum_floor_reach
            or before.terminal_value != after.terminal_value
        ):
            raise ValueError("Neural pilot changed a frozen non-policy head")
        if item.decision_type != "combat":
            noncombat += 1
            if before != after:
                raise ValueError("Neural pilot changed a non-combat prediction")
        residual = selected_scores.get(item.state_id, (0.0,) * len(item.candidate_features))
        expected = _softmax(
            tuple(
                _dot(parent_weights, f) + s
                for f, s in zip(item.candidate_features, residual, strict=True)
            )
        )
        if max(abs(a - b) for a, b in zip(expected, after.policy, strict=True)) > 1e-10:
            raise ValueError("Serialized neural inference differs from training scores")
    held_out = copy.deepcopy(report["held_out_metrics"])
    held_out["policy"] = val_policy
    report_body = cast(
        dict[str, Any],
        _quantize_artifact(
            {
                "schema_version": REPORT_SCHEMA,
                "model_type": MODEL_TYPE,
                "model_id": checkpoint["model_id"],
                "config": data.document,
                "neural_config": d,
                "selected_epoch": best_epoch,
                "selected_head_id": best_head.as_dict()["head_id"],
                "train_dataset_id": foundation["dataset_id"],
                "validation_dataset_id": data.document["validation_dataset_id"],
                "split_manifest_id": foundation["split_manifest_id"],
                "training_runs": len(folds["fit"] + folds["selection"]),
                "validation_runs": len({x.run_seed for x in inputs.validation}),
                "training_records": len(inputs.anchors),
                "validation_records": len(inputs.validation),
                "parent_selection_combat": base_combat,
                "parent_selection_policy": base_policy,
                "parent_validation_policy": val_base_policy,
                "parent_validation_combat": val_base_combat,
                "training_history": history,
                "selection_rule": SELECTION_RULE,
                "selection_refit": False,
                "held_out_metrics": held_out,
                "validation_drift": val_drift,
                "validation_combat": val_combat,
                "validation_checks": validation_checks,
                "candidate_eligible": eligible,
                "status": "requires_fresh_confirmation" if eligible else "rejected_or_no_update",
                "serialization_checks": {
                    "all_original_heads_frozen": True,
                    "all_non_policy_predictions_unchanged": True,
                    "training_inference_aligned": True,
                    "noncombat_predictions_unchanged": noncombat,
                },
                "seed_verification": {
                    **inputs.seed_verification,
                    "selection_gate_sources_reconciled": True,
                },
                "optimizer_steps": recipe["epochs"],
                "terminal_value_status": report["terminal_value_status"],
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
    result = {**report_body, "report_id": manifest_identifier(report_body)}
    validate_neural_combat_report(result, checkpoint=checkpoint)
    return ProductionTrainingResult(checkpoint, result)


def neural_checkpoint_parent(value: object) -> tuple[dict[str, Any], NeuralCombatHead]:
    checkpoint = copy.deepcopy(_mapping(value, "neural checkpoint"))
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
            "neural_combat_policy",
        },
        "neural checkpoint",
    )
    _identified(checkpoint, "model_id")
    if checkpoint["schema_version"] != CHECKPOINT_SCHEMA or checkpoint["model_type"] != MODEL_TYPE:
        raise ValueError("Unsupported neural checkpoint")
    binding = _mapping(checkpoint.pop("neural_combat_policy"), "neural binding")
    _exact_keys(
        binding,
        {"config", "head", "selected_epoch", "parent_schema_version", "parent_model_type"},
        "neural binding",
    )
    config = NeuralCombatConfig.from_mapping(binding["config"])
    head = NeuralCombatHead.from_mapping(binding["head"])
    network = config.document["network"]
    if (
        head.layout != config.data.residual_layout
        or head.dimension != network["feature_dimension"]
        or len(head.hidden_bias) != network["hidden_units"]
        or head.source_sha256 != network["card_source_sha256"]
        or manifest_identifier(head.catalog) != network["card_catalog_id"]
        or not 0
        <= _integer(binding["selected_epoch"], "selected epoch")
        <= config.document["optimization"]["epochs"]
        or (binding["selected_epoch"] == 0 and head.active)
        or binding["parent_schema_version"] != "production-model-checkpoint-v2"
        or binding["parent_model_type"] != "sparse-pairwise-curriculum-multihead-v2"
    ):
        raise ValueError("Neural head, selected epoch or parent binding differs")
    checkpoint.update(
        schema_version=binding["parent_schema_version"], model_type=binding["parent_model_type"]
    )
    checkpoint["model_id"] = manifest_identifier(
        {k: v for k, v in checkpoint.items() if k != "model_id"}
    )
    if checkpoint["model_id"] != config.data.foundation.document["model_id"]:
        raise ValueError("Neural checkpoint changed its original parent")
    return checkpoint, head


def validate_neural_combat_report(
    report: object, *, checkpoint: dict[str, Any] | None = None
) -> dict[str, Any]:
    return _validate_combat_training_report(report, checkpoint=checkpoint, neural=True)


def summarize_neural_combat_training(report: dict[str, Any]) -> dict[str, Any]:
    d = validate_neural_combat_report(report)
    network = d["neural_config"]["network"]
    return {
        k: d[k]
        for k in (
            "model_id",
            "report_id",
            "selected_epoch",
            "candidate_eligible",
            "status",
            "validation_checks",
            "validation_combat",
            "optimizer_steps",
            "terminal_victory_positive_labels",
            "checkpoint_promoted",
            "foundation_ready",
        )
    } | {
        "valid": True,
        "architecture": f"{network['feature_dimension']} → {network['hidden_units']} tanh → 1",
        "trainable_parameters": network["hidden_units"] * (network["feature_dimension"] + 2),
        "games_replayed": 0,
        "automatic_followup": False,
        "next_step": "review_saved_training_before_separate_owner_gameplay_confirmation",
    }
