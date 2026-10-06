from __future__ import annotations

import copy
import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spireshift import starting_evidence_training as training
from spireshift import trajectory_policy as policy
from spireshift.core.manifest import RulesetIdentity, load_patch_manifest, manifest_identifier
from spireshift.core.objective import ObjectiveSpec, load_objective
from spireshift.models import _dot, _exact_keys, _mapping, _quantize_artifact, _sigmoid, _softmax
from spireshift.production_models import (
    load_production_model_checkpoint,
    load_production_training_report,
    production_model_from_checkpoint,
)
from spireshift.resource_tracking import load_resource_report
from spireshift.splits import load_split_manifest
from spireshift.starting_evidence import load_starting_evidence_config
from spireshift.starting_option_training import StartingOptionSpace, prepare_starting_option_space
from spireshift.starting_options import (
    load_starting_option_config,
    starting_option_feature_tokens,
    starting_option_ids,
)
from spireshift.trajectory_diagnostic import _contrast

CONFIG_SCHEMA = "starting-evidence-diagnostic-config-v1"
REPORT_SCHEMA = "starting-evidence-diagnostic-v1"
STRONG = {"maximum_floor", "boss_reached", "act1_cleared"}
IDENTITIES = {
    "training_config_id",
    "candidate_model_id",
    "candidate_report_id",
    "resource_report_id",
}
REPORT_FIELDS = {
    "schema_version",
    "report_id",
    "objective",
    "config",
    "source_inputs",
    "verification",
    "resource",
    "learning_curve",
    "coverage",
    "complete_run_subfolds",
    "collection_summary",
    "exclusions",
    "preference_rows",
    "preference_coverage_by_option",
    "fitting_feature_conflicts",
    "fitting_gradient",
    "fitting_anchor_diagnosis",
    "recommendation",
    "reconciliation_pass",
    "validation_interpretation",
    "terminal_victory_positive_labels",
    "games_replayed",
    "optimizer_steps",
    "checkpoint_promoted",
    "claim_scope",
    "limitations",
}


@dataclass(frozen=True, slots=True)
class StartingEvidenceDiagnosticConfig:
    document: dict[str, Any]

    @classmethod
    def from_mapping(cls, value: object) -> StartingEvidenceDiagnosticConfig:
        doc = copy.deepcopy(_mapping(value, "starting evidence diagnostic config"))
        _exact_keys(doc, IDENTITIES | {"schema_version", "config_id", "objective_id"}, "diagnosis")
        policy._identified(doc, "config_id")
        if doc["schema_version"] != CONFIG_SCHEMA or doc["objective_id"] != "terminal-victory-v1":
            raise ValueError("Unsupported starting evidence diagnostic schema or objective")
        for key in IDENTITIES:
            policy._id(doc[key], key)
        return cls(doc)


def load_starting_evidence_diagnostic_config(path: Path) -> StartingEvidenceDiagnosticConfig:
    return StartingEvidenceDiagnosticConfig.from_mapping(json.loads(path.read_text()))


def _same(actual: object, expected: object, label: str) -> None:
    if _quantize_artifact(actual) != _quantize_artifact(expected):
        raise ValueError(f"Starting evidence diagnosis does not reconcile: {label}")


def _close(actual: float, expected: float, label: str) -> None:
    if not math.isfinite(actual) or not math.isclose(actual, expected, abs_tol=1e-10, rel_tol=0):
        raise ValueError(f"Starting evidence diagnosis does not reconcile: {label}")


def _resource_provenance(
    path: Path, expected_id: str, paths: dict[str, Path], objective: ObjectiveSpec
) -> dict[str, Any]:
    doc = load_resource_report(path)
    if (
        doc["report_id"] != expected_id
        or doc["experiment_kind"] != "training"
        or doc["status"] != "completed"
        or doc["exit_code"] != 0
        or doc["cap"] is not None
    ):
        raise ValueError("Diagnosis requires the bound completed training resource report")
    command = doc["command"]
    if command[:5] != ["uv", "run", "spireshift", "model", "finetune-starting-evidence-policy"]:
        raise ValueError("Resource command is not the starting evidence training job")
    root = Path(doc["working_directory"])
    if not root.is_absolute() or len(command) < 8 or (len(command) - 8) % 2:
        raise ValueError("Resource training command or working directory is malformed")
    flags = command[8::2]
    arguments = dict(zip(flags, command[9::2], strict=True))
    expected_flags = set(paths) - {"config", "parent_checkpoint", "checkpoint"}
    if len(flags) != len(set(flags)) or set(flags) - {"--objective-config"} != expected_flags:
        raise ValueError("Resource training command flags differ from the saved inputs")
    recorded = {
        "config": command[5],
        "parent_checkpoint": command[6],
        "checkpoint": command[7],
        **arguments,
    }
    if any((root / recorded[key]).resolve() != value.resolve() for key, value in paths.items()):
        raise ValueError("Resource training command belongs to different source/output paths")
    saved_objective = root / arguments.get("--objective-config", "configs/default.toml")
    _same(load_objective(saved_objective).as_dict(), objective.as_dict(), "resource objective")
    roots = tuple(Path(p).resolve() for p in doc["artifacts"]["roots"])
    if any(
        not any(paths[key].resolve().is_relative_to(root) for root in roots)
        for key in ("checkpoint", "--report")
    ):
        raise ValueError("Resource artifact roots do not cover the saved training outputs")
    return {
        "report_id": doc["report_id"],
        "status": doc["status"],
        "usage": doc["usage"],
        "limits": doc["limits"],
        "hardware": doc["hardware"],
        "command_binding_pass": True,
    }


def _metric_inventory(metric: dict[str, Any], examples: tuple[policy._Preference, ...]) -> None:
    """Check recorded history against source inventory, not unavailable intermediate weights."""
    inventory = policy._preference_metrics({}, examples)

    def check(row: dict[str, Any], expected: dict[str, Any]) -> None:
        for field in ("records", "eligible_records", "unique_runs", "effective_weight"):
            _same(row[field], expected[field], f"history {field}")
        for field in ("directional_accuracy", "weighted_pair_loss"):
            value = row[field]
            if expected[field] is None:
                _same(value, None, field)
            elif not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
                raise ValueError("History contains an invalid preference metric")
        if row["directional_accuracy"] is not None:
            accuracy = row["directional_accuracy"]
            if accuracy > 1:
                raise ValueError("History preference accuracy exceeds one")
            correct = accuracy * row["records"]
            _close(correct, round(correct), "history directional accuracy count")

    check(metric, inventory)
    for group in ("by_run", "by_rank_component"):
        _same(sorted(metric[group]), sorted(inventory[group]), f"history {group} ownership")
        for key, expected in inventory[group].items():
            check(metric[group][key], expected)
        correct = sum(
            row["records"] * row["directional_accuracy"] for row in metric[group].values()
        )
        _close(
            correct / len(examples), metric["directional_accuracy"], "history accuracy aggregate"
        )
    # Component losses renormalize within each component; only run losses reconstruct the total.
    weighted = sum(
        row["effective_weight"] * row["weighted_pair_loss"] for row in metric["by_run"].values()
    )
    _close(
        weighted / metric["effective_weight"],
        metric["weighted_pair_loss"],
        "history loss aggregate",
    )


def _learning_curve(
    saved: dict[str, Any], inputs: policy.TrajectoryPolicyInputs, parent: dict[int, float]
) -> dict[str, Any]:
    eligible = tuple(p for p in inputs.preferences if p.weight > 0)
    fit = tuple(p for p in eligible if p.run_seed in inputs.runs["fit"])
    selection = tuple(p for p in eligible if p.run_seed in inputs.runs["selection"])
    strong = tuple(p for p in selection if p.component in STRONG)
    baselines = {
        "fit_preferences": policy._preference_metrics(parent, fit),
        "selection_preferences": saved["parent_selection_preferences"],
        "strong_selection_preferences": saved["parent_strong_selection_preferences"],
    }
    rows = []
    failed: Counter[str] = Counter()
    minimum = saved["trajectory_finetuning"]["recipe"]["limits"][
        "minimum_preference_loss_improvement"
    ]
    for epoch in saved["training_history"]:
        for name, examples in (
            ("fit_preferences", fit),
            ("selection_preferences", selection),
            ("strong_selection_preferences", strong),
        ):
            _metric_inventory(epoch[name], examples)
        _same(
            epoch["selection_drift"]["decisions"],
            saved["selection_anchor_records"],
            "anchor drift count",
        )
        for key in ("decisive_pairs", "effective_pair_weight"):
            _same(
                epoch["selection_policy"][key],
                saved["parent_selection_policy"][key],
                f"anchor {key}",
            )
        failed.update(key for key, value in epoch["checks"].items() if not value)
        gains = {
            key: baseline["weighted_pair_loss"] - epoch[key]["weighted_pair_loss"]
            for key, baseline in baselines.items()
        }
        rows.append(
            {
                "epoch": epoch["epoch"],
                "policy_weights_id": epoch["policy_weights_id"],
                "gains": gains,
                "failed_checks": sorted(key for key, value in epoch["checks"].items() if not value),
                "fit_preferences": epoch["fit_preferences"],
                "selection_preferences": epoch["selection_preferences"],
                "strong_selection_preferences": epoch["strong_selection_preferences"],
            }
        )
    best = max(rows, key=lambda row: row["gains"]["selection_preferences"])
    last = rows[-1]
    return {
        "baselines": baselines,
        "epochs": rows,
        "failed_check_counts": dict(sorted(failed.items())),
        "required_gain": minimum,
        "best_recorded_epoch": best["epoch"],
        "best_overall_gain": best["gains"]["selection_preferences"],
        "best_overall_shortfall": max(0, minimum - best["gains"]["selection_preferences"]),
        "last_epoch_is_best": best["epoch"] == last["epoch"],
        "last_interval_overall_gain": (
            last["gains"]["selection_preferences"] - rows[-2]["gains"]["selection_preferences"]
            if len(rows) > 1
            else None
        ),
        "component_selection_gains_at_best": {
            key: value["weighted_pair_loss"]
            - best["selection_preferences"]["by_rank_component"][key]["weighted_pair_loss"]
            for key, value in baselines["selection_preferences"]["by_rank_component"].items()
        },
        "unselected_weights_available": False,
        "history_verification_scope": (
            "source_inventory_aggregate_arithmetic_and_frozen_checks_not_weight_replay"
        ),
    }


def _key(values: Mapping[Any, float]) -> tuple[str, int]:
    ordered = sorted((str(key), value) for key, value in values.items() if value)
    sign = 1 if not ordered or ordered[0][1] > 0 else -1
    return manifest_identifier([[key, sign * value] for key, value in ordered]), sign


def _token_contrast(left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
    return {
        key: value
        for key in sorted(set(left) | set(right))
        if (value := left.get(key, 0) - right.get(key, 0)) != 0
    }


def _residual(features: dict[int, float], offset: int) -> dict[int, float]:
    return {key - offset: value for key, value in features.items() if key >= offset and value}


def _gradient_components(
    fit: tuple[policy._Preference, ...],
    parent: dict[int, float],
    recipe: dict[str, Any],
    offset: int,
) -> dict[str, dict[int, float]]:
    # Keep the full fitting-run denominators while decomposing; filtering first would renormalize.
    counts = Counter(p.run_seed for p in fit)
    parts: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for p in fit:
        error = (
            recipe["preference_strength"]
            * p.weight
            / counts[p.run_seed]
            / len(counts)
            * (_sigmoid(_dot(parent, p.preferred) - _dot(parent, p.disfavored)) - 1)
        )
        for key, value in _residual(_contrast(p.preferred, p.disfavored), offset).items():
            parts[p.component][key] += error * value
    return {key: dict(value) for key, value in sorted(parts.items())}


def _sum_gradients(parts: list[dict[int, float]]) -> dict[int, float]:
    result: dict[int, float] = defaultdict(float)
    for part in parts:
        for key, value in part.items():
            result[key] += value
    return dict(result)


def _cosine(left: dict[int, float], right: dict[int, float]) -> float | None:
    denominator = math.sqrt(sum(v * v for v in left.values()) * sum(v * v for v in right.values()))
    return min(1.0, max(-1.0, _dot(left, right) / denominator)) if denominator else None


def _preference_rows(
    inputs: policy.TrajectoryPolicyInputs,
    space: StartingOptionSpace,
    parent: dict[int, float],
    ruleset: RulesetIdentity,
    gradients: dict[str, dict[int, float]],
) -> list[dict[str, Any]]:
    rows = []
    for p, record in zip(inputs.preferences, inputs.preference_records, strict=True):
        representation = policy._preference_representation(record, ruleset)
        options = starting_option_ids(representation)
        if options is None:
            raise ValueError("Evidence diagnostic contains a non-starting preference")
        ids = record["candidate_action_ids"]
        left, right = (
            ids.index(record["preferred_action_id"]),
            ids.index(record["disfavored_action_id"]),
        )
        tokens = starting_option_feature_tokens(representation, space.head.known_option_ids)
        semantic = _token_contrast(tokens[left], tokens[right])
        hashed = _residual(_contrast(p.preferred, p.disfavored), space.offset)
        semantic_key, semantic_sign = _key(semantic)
        hashed_key, hashed_sign = _key(hashed)
        context = {json.loads(token)[-1]: value for token, value in tokens[left].items()}
        rows.append(
            {
                "comparison_id": record["comparison_id"],
                "run_seed": p.run_seed,
                "subfold": "fit" if p.run_seed in inputs.runs["fit"] else "selection",
                "source_state_hash": representation.source_state_hash,
                "rank_component": p.component,
                "training_weight": p.weight,
                "menu_option_ids": list(options),
                "preferred_option_id": options[left],
                "disfavored_option_id": options[right],
                "preferred_action_id": record["preferred_action_id"],
                "disfavored_action_id": record["disfavored_action_id"],
                "public_context": context,
                "public_context_id": manifest_identifier(context),
                "parent_margin": _dot(parent, p.preferred) - _dot(parent, p.disfavored),
                "semantic_contrast_id": semantic_key,
                "semantic_direction": semantic_sign,
                "hashed_contrast_id": hashed_key,
                "hashed_direction": hashed_sign,
                "residual_contrast_coordinates": len(hashed),
                "initial_descent_margins": {
                    key: -_dot(value, hashed) for key, value in gradients.items()
                },
            }
        )
    return rows


def _feature_conflicts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fitting = [row for row in rows if row["subfold"] == "fit" and row["training_weight"] > 0]
    semantic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    hashed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in fitting:
        semantic[row["semantic_contrast_id"]].append(row)
        hashed[row["hashed_contrast_id"]].append(row)
    opposing = []
    for key, members in sorted(semantic.items()):
        if len({row["semantic_direction"] for row in members}) > 1:
            lower = max(-row["parent_margin"] for row in members if row["semantic_direction"] == 1)
            upper = min(row["parent_margin"] for row in members if row["semantic_direction"] == -1)
            opposing.append(
                {
                    "semantic_contrast_id": key,
                    "independent_runs": sorted({row["run_seed"] for row in members}),
                    "parent_adjusted_lower_bound": lower,
                    "parent_adjusted_upper_bound": upper,
                    "strict_margin_constraints_incompatible": lower >= upper,
                    "members": [
                        {
                            k: row[k]
                            for k in (
                                "comparison_id",
                                "run_seed",
                                "rank_component",
                                "semantic_direction",
                                "source_state_hash",
                            )
                        }
                        for row in members
                    ],
                }
            )
    aliases = [
        {
            "hashed_contrast_id": key,
            "semantic_contrast_ids": sorted({row["semantic_contrast_id"] for row in members}),
            "comparison_ids": [row["comparison_id"] for row in members],
        }
        for key, members in sorted(hashed.items())
        if len({r["semantic_contrast_id"] for r in members}) > 1
    ]
    return {
        "fitting_only": True,
        "semantic_groups": len(semantic),
        "opposing_semantic_groups": opposing,
        "different_semantics_same_hashed_contrast": aliases,
        "zero_residual_contrasts": [
            r["comparison_id"] for r in fitting if r["residual_contrast_coordinates"] == 0
        ],
        "incompatible_parent_adjusted_groups": sum(
            group["strict_margin_constraints_incompatible"] for group in opposing
        ),
        "interpretation": (
            "Contradictory realized labels under shared features can reflect "
            "omitted context or random futures; they do not prove an encoder bug "
            "or contradictory expected values. Parent-adjusted bounds test one "
            "shared margin at a time; compatible bounds do not prove global feasibility."
        ),
    }


def _anchor_diagnosis(
    inputs: policy.TrajectoryPolicyInputs,
    space: StartingOptionSpace,
    parent: dict[int, float],
    rows: list[dict[str, Any]],
    full_gradient: dict[int, float],
    recipe: dict[str, Any],
) -> dict[str, Any]:
    semantic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    hashed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    fit_anchors = tuple(a for a in inputs.anchors if a.run_seed in inputs.runs["fit"])
    norm = math.sqrt(sum(v * v for v in full_gradient.values()))
    descent = {k: -v / norm for k, v in full_gradient.items()} if norm else {}
    counts = Counter(a.run_seed for a in fit_anchors)
    curvature = 0.0
    directions: list[dict[str, Any]] = []
    token_buckets: dict[int, set[str]] = defaultdict(set)
    for a in fit_anchors:
        residuals = tuple(_residual(f, space.offset) for f in a.candidate_features)
        direction_logits = tuple(_dot(descent, f) for f in residuals)
        probabilities = _softmax(tuple(_dot(parent, f) for f in a.candidate_features))
        mean = sum(p * v for p, v in zip(probabilities, direction_logits, strict=True))
        variance = sum(
            p * (v - mean) ** 2 for p, v in zip(probabilities, direction_logits, strict=True)
        )
        curvature += recipe["anchor_strength"] / counts[a.run_seed] / len(counts) * variance
        options = starting_option_ids(a.representation)
        if options is None:
            continue
        tokens = starting_option_feature_tokens(a.representation, space.head.known_option_ids)
        for candidate_tokens in tokens:
            for token in candidate_tokens:
                digest = hashlib.sha256(token.encode()).digest()
                token_buckets[int.from_bytes(digest[:8], "big") % space.head.dimension].add(token)
        for left in range(len(options)):
            for right in range(left + 1, len(options)):
                semantic_key, semantic_sign = _key(_token_contrast(tokens[left], tokens[right]))
                contrast = _contrast(residuals[left], residuals[right])
                hashed_key, hashed_sign = _key(contrast)
                gap = a.mean_progress_utilities[left] - a.mean_progress_utilities[right]
                record = {
                    "state_id": a.state_id,
                    "run_seed": a.run_seed,
                    "source_state_hash": a.representation.source_state_hash,
                    "teacher_utility_gap": gap,
                    "semantic_direction": semantic_sign,
                    "hashed_direction": hashed_sign,
                    "teacher_stability_multiplier": a.stability_multiplier,
                }
                semantic[semantic_key].append(record)
                hashed[hashed_key].append(record)
                if gap:
                    directions.append(
                        {
                            "state_id": a.state_id,
                            "run_seed": a.run_seed,
                            "left_option_id": options[left],
                            "right_option_id": options[right],
                            "teacher_utility_gap": gap,
                            "initial_descent_teacher_margin": -_dot(full_gradient, contrast)
                            * (1 if gap > 0 else -1),
                        }
                    )
    overlaps: list[dict[str, Any]] = []
    for row in rows:
        if row["subfold"] != "fit" or row["training_weight"] <= 0:
            continue
        matches = semantic[row["semantic_contrast_id"]]
        for anchor in matches:
            overlaps.append(
                {
                    "comparison_id": row["comparison_id"],
                    "preference_run_seed": row["run_seed"],
                    **{
                        k: anchor[k]
                        for k in ("state_id", "run_seed", "teacher_stability_multiplier")
                    },
                    "exact_public_state": row["source_state_hash"] == anchor["source_state_hash"],
                    "teacher_gap_in_preference_direction": anchor["teacher_utility_gap"]
                    * anchor["semantic_direction"]
                    * row["semantic_direction"],
                    "match_kind": "semantic_contrast",
                }
            )
        semantic_states = {(a["state_id"], a["run_seed"]) for a in matches}
        for anchor in hashed[row["hashed_contrast_id"]]:
            if (anchor["state_id"], anchor["run_seed"]) not in semantic_states:
                overlaps.append(
                    {
                        "comparison_id": row["comparison_id"],
                        "preference_run_seed": row["run_seed"],
                        **{
                            k: anchor[k]
                            for k in ("state_id", "run_seed", "teacher_stability_multiplier")
                        },
                        "exact_public_state": row["source_state_hash"]
                        == anchor["source_state_hash"],
                        "teacher_gap_in_preference_direction": anchor["teacher_utility_gap"]
                        * anchor["hashed_direction"]
                        * row["hashed_direction"],
                        "match_kind": "hashed_contrast_only",
                    }
                )
    return {
        "fitting_only": True,
        "target_overlaps": overlaps,
        "opposed_semantic_targets": sum(
            r["match_kind"] == "semantic_contrast" and r["teacher_gap_in_preference_direction"] < 0
            for r in overlaps
        ),
        "teacher_margin_directions": directions,
        "teacher_margins_opposed_by_initial_descent": sum(
            r["initial_descent_teacher_margin"] < 0 for r in directions
        ),
        "anchor_gradient_at_parent": 0.0,
        "proximal_gradient_at_parent": 0.0,
        "anchor_curvature_along_unit_preference_descent": curvature,
        "proximal_curvature_along_unit_preference_descent": recipe["proximal_strength"]
        if norm
        else None,
        "shared_token_coordinates": [
            {"coordinate": k, "tokens": sorted(v)}
            for k, v in sorted(token_buckets.items())
            if len(v) > 1
        ],
        "interpretation": (
            "The optimizer anchors to the parent distribution, not teacher "
            "utilities. Curvature is an analytic local constraint, not an AdaGrad "
            "step or proof that anchoring caused rejection. Coordinate sharing "
            "alone is not a contradictory contrast."
        ),
    }


def _recommendation(
    conflicts: dict[str, Any], gradient: dict[str, Any], curve: dict[str, Any]
) -> dict[str, Any]:
    if (
        conflicts["zero_residual_contrasts"]
        or conflicts["different_semantics_same_hashed_contrast"]
    ):
        intervention = "audit_residual_feature_aliases"
        reason = (
            "Fitting comparisons contain indistinguishable residual contrasts or "
            "different semantic contrasts sharing coordinates. Check public "
            "feature/fallback behavior before more training."
        )
    elif conflicts["opposing_semantic_groups"]:
        intervention = "measure_starting_label_repeatability"
        reason = (
            "Opposing realized fitting targets share the same semantic contrast. "
            "Measure consistency across independent training futures and separate "
            "missing public context from outcome noise before using them as fixed "
            "targets."
        )
    elif gradient["strong_weak_cosine"] is not None and gradient["strong_weak_cosine"] < 0:
        intervention = "prespecified_strong_label_ablation"
        reason = (
            "Strong and weak fitting gradients locally oppose one another. A "
            "controlled fitting-only ablation can test this association; it needs "
            "a new frozen recipe and fresh confirmation data."
        )
    else:
        intervention = None
        reason = (
            "No specific cause is established by the saved data. Record "
            "intermediate weights and fitting-objective/optimizer diagnostics in a "
            "separately frozen follow-up before attributing the result to "
            "insufficient optimization."
        )
    return {
        "proposed_intervention": intervention,
        "reason": reason,
        "last_recorded_epoch_was_best": curve["last_epoch_is_best"],
        "recipe_frozen": False,
        "requires_fresh_confirmation_plan": True,
        "automatic_training_allowed": False,
        "threshold_changes_allowed": False,
        "interpretation": (
            "Diagnostic recommendation only; no causal identification, model "
            "selection, game-win claim or new training authorization."
        ),
    }


def _coverage_by_option(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["training_weight"] <= 0:
            continue
        for role in ("preferred", "disfavored"):
            key = f"{row['subfold']}|{role}|{row[f'{role}_option_id']}"
            groups[key].append(row)
    return {
        key: {
            "comparisons": len(members),
            "complete_runs": sorted({row["run_seed"] for row in members}),
            "public_context_ids": sorted({row["public_context_id"] for row in members}),
            "rank_counts": dict(sorted(Counter(row["rank_component"] for row in members).items())),
            "parent_direction_correct": sum(row["parent_margin"] > 0 for row in members),
            "opposed_by_initial_fit_descent": sum(
                row["initial_descent_margins"]["full"] < 0 for row in members
            ),
        }
        for key, members in sorted(groups.items())
    }


def diagnose_starting_evidence_policy(
    *,
    diagnostic_config: StartingEvidenceDiagnosticConfig,
    checkpoint_path: Path,
    report_path: Path,
    resource_report_path: Path,
    source_paths: dict[str, Path],
    **kwargs: Any,
) -> dict[str, Any]:
    config = StartingEvidenceDiagnosticConfig.from_mapping(diagnostic_config.document).document
    expected_paths = {
        "parent_checkpoint": kwargs["parent_checkpoint_path"],
        "checkpoint": checkpoint_path,
        "--parent-report": kwargs["parent_report_path"],
        "--report": report_path,
        "--evidence": kwargs["evidence_path"],
        "--anchor-assignment-report": kwargs["anchor_assignment_report_path"],
        "--train-report": kwargs["train_report_path"],
        "--validation-report": kwargs["validation_report_path"],
    }
    if set(source_paths) != set(expected_paths) | {
        "config",
        "--evidence-config",
        "--split-manifest",
        "--ruleset-manifest",
    } or any(source_paths[k].resolve() != v.resolve() for k, v in expected_paths.items()):
        raise ValueError("Diagnostic source paths differ from the source loader")
    _same(
        load_starting_option_config(source_paths["config"]).document,
        kwargs["config"].document,
        "training config file",
    )
    _same(
        load_starting_evidence_config(source_paths["--evidence-config"]).document,
        kwargs["evidence_config"].document,
        "evidence config file",
    )
    _same(
        load_split_manifest(source_paths["--split-manifest"]).manifest_id,
        kwargs["split_manifest"].manifest_id,
        "split file",
    )
    _same(
        load_patch_manifest(source_paths["--ruleset-manifest"]).ruleset_identity().manifest_id,
        kwargs["ruleset"].manifest_id,
        "ruleset file",
    )
    inputs = training.load_starting_evidence_policy_inputs(**kwargs)
    inputs, space = prepare_starting_option_space(inputs, kwargs["ruleset"], kwargs["config"])
    checkpoint = load_production_model_checkpoint(checkpoint_path)
    saved = load_production_training_report(report_path, checkpoint=checkpoint)
    _same(config["objective_id"], kwargs["objective"].objective_id, "objective")
    for key, value in {
        "training_config_id": space.config.document["config_id"],
        "candidate_model_id": checkpoint["model_id"],
        "candidate_report_id": saved["report_id"],
    }.items():
        _same(config[key], value, key)
    verification = training.verify_prepared_starting_evidence_policy(
        inputs=inputs, space=space, checkpoint=checkpoint, report=saved
    )
    resource = _resource_provenance(
        resource_report_path, config["resource_report_id"], source_paths, kwargs["objective"]
    )
    parent = production_model_from_checkpoint(inputs.parent_checkpoint).policy_weights
    curve = _learning_curve(saved, inputs, parent)
    fit = tuple(p for p in inputs.preferences if p.weight > 0 and p.run_seed in inputs.runs["fit"])
    recipe = space.config.recipe.document
    parts = _gradient_components(fit, parent, recipe, space.offset)
    full = _sum_gradients(list(parts.values()))
    actual = _residual(policy._gradient(parent, parent, fit, (), recipe), space.offset)
    for coordinate in set(actual) | set(full):
        _close(
            full.get(coordinate, 0),
            actual.get(coordinate, 0),
            "run-normalized gradient decomposition",
        )
    strong = _sum_gradients([v for k, v in parts.items() if k in STRONG])
    weak = _sum_gradients([v for k, v in parts.items() if k not in STRONG])
    gradient = {
        "component_squared_norms": {
            k: sum(v * v for v in part.values()) for k, part in parts.items()
        },
        "strong_weak_cosine": _cosine(strong, weak),
        "full_squared_norm": sum(v * v for v in full.values()),
        "normalization": training.NORMALIZATION,
        "selection_contributes_to_gradient": False,
        "derivative_only_no_optimizer_step": True,
    }
    rows = _preference_rows(
        inputs, space, parent, kwargs["ruleset"], {"full": full, "strong": strong, "weak": weak}
    )
    conflicts = _feature_conflicts(rows)
    anchors = _anchor_diagnosis(inputs, space, parent, rows, full, recipe)
    body = _quantize_artifact(
        {
            "schema_version": REPORT_SCHEMA,
            "objective": kwargs["objective"].as_dict(),
            "config": config,
            "source_inputs": recipe["inputs"],
            "verification": verification,
            "resource": resource,
            "learning_curve": curve,
            "coverage": space.coverage,
            "complete_run_subfolds": {
                "anchors": recipe["anchor_complete_run_subfolds"],
                "evidence": recipe["evidence_complete_run_subfolds"],
            },
            "collection_summary": inputs.collection["summary"],
            "exclusions": inputs.exclusions,
            "preference_rows": rows,
            "preference_coverage_by_option": _coverage_by_option(rows),
            "fitting_feature_conflicts": conflicts,
            "fitting_gradient": gradient,
            "fitting_anchor_diagnosis": anchors,
            "recommendation": _recommendation(conflicts, gradient, curve),
            "reconciliation_pass": True,
            "validation_interpretation": "unchanged_epoch_zero_fallback"
            if verification["selected_epoch"] == 0
            else "saved_selected_epoch_only",
            "terminal_victory_positive_labels": 0,
            "games_replayed": 0,
            "optimizer_steps": 0,
            "checkpoint_promoted": False,
            "claim_scope": "saved_starting_evidence_auxiliary_learning_diagnosis",
            "limitations": [
                (
                    "Unselected epoch weights were not retained. Historical rows are "
                    "checked against source inventory, arithmetic and frozen gates; "
                    "intermediate predictions cannot be independently replayed."
                ),
                (
                    "Selection and development validation have been inspected. They are "
                    "diagnostic evidence, not an untouched confirmation test."
                ),
                (
                    "Each option has one realized fixed-policy seeded future. "
                    "Contradictory labels and gradient associations do not identify "
                    "expected-value conflicts or individual causal effects."
                ),
                (
                    "Floor and frontier labels remain auxiliary. Zero terminal victories "
                    "do not establish a competent full-run policy, terminal-value "
                    "readiness or adaptive-controller readiness."
                ),
            ],
        }
    )
    return {**body, "report_id": manifest_identifier(body)}


def summarize_starting_evidence_diagnosis(report: dict[str, Any]) -> dict[str, Any]:
    curve = report["learning_curve"]
    conflicts = report["fitting_feature_conflicts"]
    return {
        "report_id": report["report_id"],
        "reconciliation_pass": report["reconciliation_pass"],
        "selected_epoch": report["verification"]["selected_epoch"],
        "candidate_eligible": report["verification"]["candidate_eligible"],
        "validation_interpretation": report["validation_interpretation"],
        "best_recorded_epoch": curve["best_recorded_epoch"],
        "best_overall_gain": curve["best_overall_gain"],
        "required_gain": curve["required_gain"],
        "failed_check_counts": curve["failed_check_counts"],
        "component_selection_gains_at_best": curve["component_selection_gains_at_best"],
        "opposing_fitting_semantic_groups": len(conflicts["opposing_semantic_groups"]),
        "incompatible_parent_adjusted_groups": conflicts["incompatible_parent_adjusted_groups"],
        "different_semantics_same_hashed_contrast": len(
            conflicts["different_semantics_same_hashed_contrast"]
        ),
        "zero_residual_contrasts": len(conflicts["zero_residual_contrasts"]),
        "strong_weak_fitting_gradient_cosine": report["fitting_gradient"]["strong_weak_cosine"],
        "opposed_fitting_anchor_targets": report["fitting_anchor_diagnosis"][
            "opposed_semantic_targets"
        ],
        "recommendation": report["recommendation"],
        "terminal_victory_positive_labels": 0,
        "games_replayed": 0,
        "optimizer_steps": 0,
        "checkpoint_promoted": False,
    }


def load_starting_evidence_diagnostic_report(
    path: Path, config: StartingEvidenceDiagnosticConfig
) -> dict[str, Any]:
    """Show a cached audit with its identity/bindings checked; do not reaudit the sources."""
    doc = _mapping(json.loads(path.read_text()), "starting evidence diagnostic report")
    _exact_keys(doc, REPORT_FIELDS, "cached starting evidence diagnosis")
    policy._identified(doc, "report_id")
    if doc["schema_version"] != REPORT_SCHEMA:
        raise ValueError("Unsupported starting evidence diagnostic report schema")
    _same(doc["config"], config.document, "cached diagnostic config")
    _same(doc["verification"]["model_id"], config.document["candidate_model_id"], "cached model")
    _same(
        doc["verification"]["report_id"],
        config.document["candidate_report_id"],
        "cached training report",
    )
    _same(
        doc["resource"]["report_id"],
        config.document["resource_report_id"],
        "cached resource report",
    )
    _same(doc["objective"]["id"], config.document["objective_id"], "cached objective")
    if (
        doc["reconciliation_pass"] is not True
        or doc["checkpoint_promoted"] is not False
        or any(
            doc[key] != 0
            for key in ("games_replayed", "optimizer_steps", "terminal_victory_positive_labels")
        )
        or doc["claim_scope"] != "saved_starting_evidence_auxiliary_learning_diagnosis"
    ):
        raise ValueError("Cached starting diagnosis exceeds its saved-data claim")
    return doc
