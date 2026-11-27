from __future__ import annotations

import hashlib
import math
import struct
from collections import defaultdict
from pathlib import Path
from typing import Any

from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.models import _dot, _quantize_artifact, _softmax
from spireshift.production_models import (
    _evaluate_policy_weights,
    _ProductionExample,
    load_production_model_checkpoint,
    load_production_training_report,
    production_model_from_checkpoint,
)
from spireshift.splits import SplitManifest
from spireshift.trajectory_policy import (
    FROZEN_HEADS,
    TrajectoryPolicyConfig,
    TrajectoryPolicyInputs,
    _drift,
    _gradient,
    _Preference,
    _preference_metrics,
    _safe,
    load_trajectory_policy_inputs,
)
from spireshift.trajectory_search import TrajectorySearchConfig

DIAGNOSTIC_SCHEMA = "trajectory-policy-diagnostic-v1"


def _contrast(left: dict[int, float], right: dict[int, float]) -> dict[int, float]:
    return {
        index: value
        for index in sorted(set(left) | set(right))
        if (value := left.get(index, 0.0) - right.get(index, 0.0)) != 0
    }


def _same(actual: object, expected: object, label: str) -> None:
    if _quantize_artifact(actual) != _quantize_artifact(expected):
        raise ValueError(f"Saved trajectory report does not reconcile: {label}")


def _contrast_key(values: dict[int, float]) -> tuple[str, int]:
    # Canonicalize direction once, so an unordered pair indexes both orientations.
    sign = 1 if not values or next(iter(values.values())) > 0 else -1
    encoded = b"".join(struct.pack(">Id", index, sign * value) for index, value in values.items())
    return hashlib.sha256(encoded).hexdigest(), sign


def _preference_row(
    item: _Preference,
    record: dict[str, Any],
    parent: dict[int, float],
    candidate: dict[int, float],
    fit_seeds: set[int],
) -> dict[str, Any]:
    previous = _dot(parent, item.preferred) - _dot(parent, item.disfavored)
    current = _dot(candidate, item.preferred) - _dot(candidate, item.disfavored)
    return {
        "preference_id": record["preference_id"],
        "run_seed": item.run_seed,
        "subfold": "fit" if item.run_seed in fit_seeds else "selection",
        "decision_type": item.decision_type,
        "source_state_hash": record["source_state_hash"],
        "deciding_rank_component": item.component,
        "training_weight": item.weight,
        "candidate_action_ids": record["candidate_action_ids"],
        "preferred_action_id": record["preferred_action_id"],
        "disfavored_action_id": record["disfavored_action_id"],
        "parent_margin": previous,
        "candidate_margin": current,
        "parent_direction_correct": previous > 0,
        "candidate_direction_correct": current > 0,
        "margin_change": current - previous,
        "contrast_nonzero_coordinates": len(_contrast(item.preferred, item.disfavored)),
    }


def _overlap(
    contrast: dict[int, float],
    fitting: tuple[tuple[_Preference, dict[str, Any], dict[int, float], float], ...],
) -> dict[str, Any]:
    values = []
    norm = math.sqrt(sum(v * v for v in contrast.values()))
    for item, record, direction, direction_norm in fitting:
        if norm and direction_norm:
            cosine = min(1.0, max(-1.0, _dot(contrast, direction) / norm / direction_norm))
            values.append(
                {
                    "preference_id": record["preference_id"],
                    "run_seed": item.run_seed,
                    "decision_type": item.decision_type,
                    "rank_component": item.component,
                    "contrast_cosine": cosine,
                    "shared_coordinates": len(set(contrast) & set(direction)),
                }
            )
    return {
        "most_aligned_fit_preference": (
            max(values, key=lambda row: row["contrast_cosine"]) if values else None
        ),
        "most_opposed_fit_preference": (
            min(values, key=lambda row: row["contrast_cosine"]) if values else None
        ),
        "interpretation": "hashed_coordinate_association_not_semantic_or_causal_proof",
    }


def _choice_rows(
    examples: tuple[_ProductionExample, ...],
    parent: dict[int, float],
    candidate: dict[int, float],
    vector_dimension: int,
    fitting: tuple[tuple[_Preference, dict[str, Any]], ...],
    gradient: dict[int, float],
) -> list[dict[str, Any]]:
    delta = _contrast(candidate, parent)
    fitting_directions = tuple(
        (item, record, direction, math.sqrt(sum(value * value for value in direction.values())))
        for item, record in fitting
        for direction in (_contrast(item.preferred, item.disfavored),)
    )
    rows = []
    for item in examples:
        previous = tuple(_dot(parent, feature) for feature in item.candidate_features)
        current = tuple(_dot(candidate, feature) for feature in item.candidate_features)
        old = max(range(len(previous)), key=previous.__getitem__)
        new = max(range(len(current)), key=current.__getitem__)
        best = max(item.mean_progress_utilities)
        regret_change = item.mean_progress_utilities[old] - item.mean_progress_utilities[new]
        ids = [action.source_action_id for action in item.representation.candidates]
        changed = old != new
        attribution = None
        if changed:
            contrast = _contrast(item.candidate_features[new], item.candidate_features[old])
            terms = {index: delta.get(index, 0.0) * value for index, value in contrast.items()}
            before_margin = previous[new] - previous[old]
            after_margin = current[new] - current[old]
            margin_change = sum(terms.values())
            if not math.isclose(after_margin - before_margin, margin_change, abs_tol=1e-10):
                raise ValueError(
                    "Policy weight attribution does not reconcile with the action flip"
                )
            attribution = {
                "parent_new_over_old_margin": before_margin,
                "candidate_new_over_old_margin": after_margin,
                "weight_update_margin": margin_change,
                "action_coordinate_margin": sum(
                    value for index, value in terms.items() if index < vector_dimension
                ),
                "state_action_coordinate_margin": sum(
                    value for index, value in terms.items() if index >= vector_dimension
                ),
                "largest_margin_terms": [
                    {"coordinate": index, "margin_change": value}
                    for index, value in sorted(
                        terms.items(), key=lambda pair: (-abs(pair[1]), pair[0])
                    )[:8]
                ],
                "initial_preference_descent_margin": -_dot(gradient, contrast),
                "gradient_note": "unpreconditioned_derivative_not_saved_optimizer_step",
                **_overlap(contrast, fitting_directions),
            }
        rows.append(
            {
                "state_id": item.state_id,
                "run_seed": item.run_seed,
                "decision_type": item.decision_type,
                "source_state_hash": item.representation.source_state_hash,
                "representation_hash": item.representation.representation_hash,
                "candidate_action_ids": ids,
                "teacher_auxiliary_utilities": list(item.mean_progress_utilities),
                "teacher_stability_multiplier": item.stability_multiplier,
                "parent_action_id": ids[old],
                "candidate_action_id": ids[new],
                "parent_action_index": old,
                "candidate_action_index": new,
                "parent_probabilities": list(_softmax(previous)),
                "candidate_probabilities": list(_softmax(current)),
                "probability_note": "policy_distribution_not_calibrated_game_victory_probability",
                "parent_regret": best - item.mean_progress_utilities[old],
                "candidate_regret": best - item.mean_progress_utilities[new],
                "regret_change": regret_change,
                "action_changed": changed,
                "effect": "harmful"
                if regret_change > 0
                else "beneficial"
                if regret_change < 0
                else "tied",
                "weight_attribution": attribution,
            }
        )
    return rows


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    parent_sum = sum(float(row["parent_regret"]) for row in rows)
    candidate_sum = sum(float(row["candidate_regret"]) for row in rows)
    total_change = sum(float(row["regret_change"]) for row in rows)
    if not math.isclose(candidate_sum - parent_sum, total_change, abs_tol=1e-10):
        raise ValueError("Per-state regret contributions do not reconcile")
    return {
        "decisions": count,
        "changed_actions": sum(row["action_changed"] for row in rows),
        "harmful_changes": sum(row["effect"] == "harmful" for row in rows),
        "beneficial_changes": sum(row["effect"] == "beneficial" for row in rows),
        "tied_changes": sum(row["action_changed"] and row["effect"] == "tied" for row in rows),
        "parent_mean_regret": parent_sum / count if count else None,
        "candidate_mean_regret": candidate_sum / count if count else None,
        "total_regret_change": total_change,
        "mean_regret_change": total_change / count if count else None,
        "gross_harm": sum(max(0.0, float(row["regret_change"])) for row in rows),
        "gross_benefit": sum(max(0.0, -float(row["regret_change"])) for row in rows),
    }


def _group(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    return {
        str(value): _summary([row for row in rows if row[field] == value])
        for value in sorted({row[field] for row in rows})
    }


def _anchor_conflicts(
    inputs: TrajectoryPolicyInputs,
    fitting: tuple[tuple[_Preference, dict[str, Any]], ...],
    parent: dict[int, float],
    gradient: dict[int, float],
) -> dict[str, Any]:
    exact: list[dict[str, Any]] = []
    feature_aliases: list[dict[str, Any]] = []
    directions: list[dict[str, Any]] = []
    anchors_by_hash: dict[str, list[_ProductionExample]] = defaultdict(list)
    anchors_by_contrast: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in inputs.anchors:
        anchors_by_hash[item.representation.source_state_hash].append(item)
        best = max(
            range(len(item.mean_progress_utilities)), key=item.mean_progress_utilities.__getitem__
        )
        others = [i for i in range(len(item.candidate_features)) if i != best]
        if not others:
            continue
        other = max(others, key=lambda index: _dot(parent, item.candidate_features[index]))
        if item.mean_progress_utilities[best] > item.mean_progress_utilities[other]:
            desired = _contrast(item.candidate_features[best], item.candidate_features[other])
            directions.append(
                {
                    "state_id": item.state_id,
                    "run_seed": item.run_seed,
                    "decision_type": item.decision_type,
                    "subfold": "fit" if item.run_seed in inputs.runs["fit"] else "selection",
                    "teacher_utility_gap": item.mean_progress_utilities[best]
                    - item.mean_progress_utilities[other],
                    "initial_descent_teacher_margin": -_dot(gradient, desired),
                }
            )
        # Index each unordered pair once; canonical direction preserves exact equality.
        for left in range(len(item.candidate_features)):
            for right in range(left + 1, len(item.candidate_features)):
                contrast = _contrast(item.candidate_features[left], item.candidate_features[right])
                key, sign = _contrast_key(contrast)
                anchors_by_contrast[key].append(
                    {
                        "state_id": item.state_id,
                        "run_seed": item.run_seed,
                        "source_state_hash": item.representation.source_state_hash,
                        "teacher_utility_gap": sign
                        * (
                            item.mean_progress_utilities[left] - item.mean_progress_utilities[right]
                        ),
                    }
                )
    for preference, record in fitting:
        for anchor in anchors_by_hash[record["source_state_hash"]]:
            ids = [candidate.source_action_id for candidate in anchor.representation.candidates]
            if ids != record["candidate_action_ids"]:
                continue
            left, right = (
                ids.index(record["preferred_action_id"]),
                ids.index(record["disfavored_action_id"]),
            )
            exact.append(
                {
                    "preference_id": record["preference_id"],
                    "state_id": anchor.state_id,
                    "teacher_utility_gap": anchor.mean_progress_utilities[left]
                    - anchor.mean_progress_utilities[right],
                }
            )
        direction = _contrast(preference.preferred, preference.disfavored)
        key, sign = _contrast_key(direction)
        feature_aliases.extend(
            {
                "preference_id": record["preference_id"],
                **entry,
                "teacher_utility_gap": sign * entry["teacher_utility_gap"],
            }
            for entry in anchors_by_contrast[key]
            if entry["source_state_hash"] != record["source_state_hash"]
        )
    fit_directions = [row for row in directions if row["subfold"] == "fit"]
    return {
        "exact_state_action_overlap": exact,
        "exact_overlap_conflicts": sum(row["teacher_utility_gap"] < 0 for row in exact),
        "exact_hashed_contrast_aliases": feature_aliases,
        "opposing_aliases": sum(row["teacher_utility_gap"] < 0 for row in feature_aliases),
        "teacher_margin_directions": directions,
        "fit_teacher_margins": len(fit_directions),
        "fit_margins_opposed_by_initial_preference_gradient": sum(
            row["initial_descent_teacher_margin"] < 0 for row in fit_directions
        ),
        "interpretation": (
            "Exact public-state overlap can establish target disagreement. Contrast equality "
            "may reflect intentional abstraction or collisions. Gradient and cosine associations "
            "do not isolate causal effects of individual training examples."
        ),
    }


def diagnose_trajectory_policy(
    *,
    parent_checkpoint_path: Path,
    parent_report_path: Path,
    candidate_checkpoint_path: Path,
    candidate_report_path: Path,
    collection_path: Path,
    search_report_path: Path,
    search_config: TrajectorySearchConfig,
    train_report_path: Path,
    validation_report_path: Path,
    split_manifest: SplitManifest,
    ruleset: RulesetIdentity,
    config: TrajectoryPolicyConfig,
    objective: ObjectiveSpec,
) -> dict[str, Any]:
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
    checkpoint = load_production_model_checkpoint(candidate_checkpoint_path)
    saved = load_production_training_report(candidate_report_path, checkpoint=checkpoint)
    if checkpoint.get("schema_version") != "production-model-checkpoint-v6":
        raise ValueError("Trajectory diagnosis requires a v6 candidate")
    binding = checkpoint["trajectory_finetuning"]
    if binding["recipe"] != config.document or binding["complete_run_subfolds"] != inputs.runs:
        raise ValueError(
            "Candidate recipe or complete-run assignment differs from diagnostic inputs"
        )
    for field in ("training_config", "representation_encoder_id", "vectorizer_id"):
        if checkpoint[field] != inputs.parent_checkpoint[field]:
            raise ValueError("Candidate representation or base training configuration differs")
    if any(
        checkpoint["heads"][head] != inputs.parent_checkpoint["heads"][head]
        for head in FROZEN_HEADS
    ):
        raise ValueError("Candidate non-policy heads differ from its actual parent")
    for field, expected in (
        ("training_records", len(inputs.anchors)),
        ("training_runs", len(inputs.runs["fit"]) + len(inputs.runs["selection"])),
        ("fit_anchor_records", sum(item.run_seed in inputs.runs["fit"] for item in inputs.anchors)),
        (
            "selection_anchor_records",
            sum(item.run_seed in inputs.runs["selection"] for item in inputs.anchors),
        ),
        ("validation_records", len(inputs.validation)),
        ("validation_runs", len({item.run_seed for item in inputs.validation})),
        ("collection_summary", inputs.collection["summary"]),
        ("exclusions", inputs.exclusions),
    ):
        _same(saved[field], expected, field)
    parent = dict(production_model_from_checkpoint(inputs.parent_checkpoint).policy_weights)
    candidate = dict(production_model_from_checkpoint(checkpoint).policy_weights)
    fit_seeds = set(inputs.runs["fit"])
    eligible = tuple(item for item in inputs.preferences if item.weight > 0)
    fit = tuple(item for item in eligible if item.run_seed in fit_seeds)
    selection = tuple(item for item in eligible if item.run_seed not in fit_seeds)
    fit_records = tuple(
        (item, record)
        for item, record in zip(inputs.preferences, inputs.preference_records, strict=True)
        if item.weight > 0 and item.run_seed in fit_seeds
    )
    selection_anchors = tuple(item for item in inputs.anchors if item.run_seed not in fit_seeds)
    baseline = inputs.parent_report["held_out_metrics"]["policy"]["soft_target_baseline"]
    for weights, examples, expected, label in (
        (parent, inputs.validation, saved["parent_validation_policy"], "parent validation metrics"),
        (
            candidate,
            inputs.validation,
            saved["held_out_metrics"]["policy"],
            "candidate validation metrics",
        ),
        (parent, selection_anchors, saved["parent_selection_policy"], "parent selection metrics"),
    ):
        _same(
            _evaluate_policy_weights(
                weights, examples, inputs.training_config, soft_baseline=baseline
            ),
            expected,
            label,
        )
    _same(
        _drift(candidate, parent, inputs.validation), saved["validation_drift"], "validation drift"
    )
    _same(
        _preference_metrics(parent, selection),
        saved["parent_selection_preferences"],
        "parent preferences",
    )
    _same(
        _preference_metrics(candidate, inputs.preferences),
        saved["preference_diagnostics"],
        "all preferences",
    )
    for field, expected in (
        ("eligible_preferences", len(eligible)),
        ("fit_preferences", len(fit)),
        ("selection_preferences", len(selection)),
    ):
        _same(saved[field], expected, field)
    if binding["selected_epoch"] > 0:
        selected = saved["training_history"][binding["selected_epoch"] - 1]
        for label, values in (("fit_preferences", fit), ("selection_preferences", selection)):
            _same(_preference_metrics(candidate, values), selected[label], label)
        _same(
            _evaluate_policy_weights(
                candidate, selection_anchors, inputs.training_config, soft_baseline=baseline
            ),
            selected["selection_policy"],
            "selected anchor metrics",
        )
    # This is an analytical derivative, not an optimizer step or a training run.
    gradient = _gradient(parent, parent, fit, (), config.document)
    validation_rows = _choice_rows(
        inputs.validation,
        parent,
        candidate,
        inputs.training_config.vector_dimension,
        fit_records,
        gradient,
    )
    anchor_rows = _choice_rows(
        inputs.anchors, parent, candidate, inputs.training_config.vector_dimension, (), gradient
    )
    summary = _summary(validation_rows)
    for key, field in (
        ("parent_mean_regret", "parent_validation_policy"),
        ("candidate_mean_regret", "held_out_metrics"),
    ):
        expected = saved[field] if field != "held_out_metrics" else saved[field]["policy"]
        _same(summary[key], expected["mean_progress_utility_regret"], key)
    _same(
        summary["changed_actions"],
        saved["validation_drift"]["changed_actions"],
        "changed action count",
    )
    checks = _safe(
        saved["held_out_metrics"]["policy"],
        saved["parent_validation_policy"],
        saved["validation_drift"],
        config.document["limits"],
    )
    _same(checks, saved["validation_checks"], "frozen validation checks")
    preference_rows = [
        _preference_row(item, record, parent, candidate, fit_seeds)
        for item, record in zip(inputs.preferences, inputs.preference_records, strict=True)
    ]
    coverage = {
        decision_type: {
            "fit_preferences": sum(item.decision_type == decision_type for item in fit),
            "selection_preferences": sum(item.decision_type == decision_type for item in selection),
            "strong_fit_runs": len(
                {
                    item.run_seed
                    for item in fit
                    if item.decision_type == decision_type
                    and item.component in {"maximum_floor", "boss_reached", "act1_cleared"}
                }
            ),
        }
        for decision_type in sorted(
            {item.decision_type for item in inputs.validation}
            | {item.decision_type for item in eligible}
        )
    }
    conflicts = _anchor_conflicts(inputs, fit_records, parent, gradient)
    body = _quantize_artifact(
        {
            "schema_version": DIAGNOSTIC_SCHEMA,
            "objective": objective.as_dict(),
            "inputs": {
                **config.document["inputs"],
                "recipe_id": config.config_id,
                "candidate_model_id": checkpoint["model_id"],
                "candidate_report_id": saved["report_id"],
            },
            "complete_run_subfolds": inputs.runs,
            "reconciliation_pass": True,
            "candidate_eligible": saved["candidate_eligible"],
            "validation_checks": checks,
            "validation_summary": summary,
            "validation_by_decision_type": _group(validation_rows, "decision_type"),
            "validation_by_run": _group(validation_rows, "run_seed"),
            "validation_choices": validation_rows,
            "anchor_summary": _summary(anchor_rows),
            "anchor_by_decision_type": _group(anchor_rows, "decision_type"),
            "anchor_by_run": _group(anchor_rows, "run_seed"),
            "anchor_conflicts": conflicts,
            "preference_summary": {
                "all_mutations": inputs.collection["summary"],
                "exclusions": inputs.exclusions,
                "parent_fit": _preference_metrics(parent, fit),
                "candidate_fit": _preference_metrics(candidate, fit),
                "parent_selection": _preference_metrics(parent, selection),
                "candidate_selection": _preference_metrics(candidate, selection),
            },
            "preference_coverage": coverage,
            "preference_choices": preference_rows,
            "terminal_victory_positive_labels": 0,
            "checkpoint_promoted": False,
            "claim_scope": "saved_development_auxiliary_policy_regression_diagnosis",
            "limitations": [
                "Teacher utilities are noisy auxiliary continuation estimates, "
                "not terminal win probabilities.",
                "Validation is reused development evidence, not an untouched final test.",
                "Coordinate overlap and initial gradients do not prove semantic hash "
                "collisions or causal attribution to a training label.",
                "No new candidate, epoch selection, blend, replay, "
                "or training is produced by this report.",
            ],
        }
    )
    return {**body, "report_id": manifest_identifier(body)}
