from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from spireshift import trajectory_policy as policy
from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.models import _exact_keys, _integer, _list, _mapping, _quantize_artifact
from spireshift.production_models import (
    ProductionTrainingConfig,
    ProductionTrainingResult,
    _evaluate_policy_weights,
    _load_curriculum_examples,
    load_production_model_checkpoint,
    load_production_training_report,
    production_model_from_checkpoint,
)
from spireshift.splits import SplitManifest, SplitName
from spireshift.starting_evidence import (
    CLAIM,
    StartingEvidenceConfig,
    verify_starting_option_evidence,
)
from spireshift.starting_option_training import StartingOptionSpace, prepare_starting_option_space
from spireshift.starting_options import EVIDENCE_CONFIG_SCHEMA, StartingOptionConfig

RECIPE_SCHEMA = "starting-evidence-policy-training-config-v1"
CHECKPOINT_SCHEMA = "production-model-checkpoint-v8"
REPORT_SCHEMA = "production-model-training-report-v8"
INPUT_FIELDS = (policy.INPUT_FIELDS - {"collection_id", "search_report_id", "search_config_id"}) | {
    "evidence_report_id",
    "evidence_config_id",
    "anchor_assignment_report_id",
    "anchor_assignment_config_id",
}
FOLD_FIELDS = {"anchor_complete_run_subfolds", "evidence_complete_run_subfolds"}
FIELDS = policy.CONFIG_FIELDS | FOLD_FIELDS
NORMALIZATION = "equal_complete_run_within_rank_weight"


def _groups(value: object, label: str) -> dict[str, list[int]]:
    groups = _mapping(value, label)
    _exact_keys(groups, {"fit", "selection"}, label)
    for raw in groups.values():
        seeds = [_integer(seed, label) for seed in _list(raw, label)]
        if not seeds or seeds != sorted(set(seeds)) or min(seeds) < 0:
            raise ValueError(f"{label} seeds must be nonempty, unique, nonnegative and sorted")
    if set(groups["fit"]) & set(groups["selection"]):
        raise ValueError(f"{label} fitting and selection runs overlap")
    return groups


class StartingEvidencePolicyConfig(policy.TrajectoryPolicyConfig):
    @classmethod
    def from_mapping(cls, value: object) -> StartingEvidencePolicyConfig:
        doc = copy.deepcopy(_mapping(value, "starting evidence policy recipe"))
        _exact_keys(doc, FIELDS, "starting evidence policy recipe")
        policy._identified(doc, "config_id")
        if doc["schema_version"] != RECIPE_SCHEMA or doc["objective_id"] != "terminal-victory-v1":
            raise ValueError("Unsupported starting evidence policy schema or objective")
        inputs = _mapping(doc["inputs"], "starting evidence policy inputs")
        _exact_keys(inputs, INPUT_FIELDS, "starting evidence policy inputs")
        for key, item in inputs.items():
            policy._id(item, key)
        policy._validate_optimization(doc)
        anchors = _groups(doc["anchor_complete_run_subfolds"], "anchor subfolds")
        evidence = _groups(doc["evidence_complete_run_subfolds"], "evidence subfolds")
        if (set(anchors["fit"]) | set(anchors["selection"])) & (
            set(evidence["fit"]) | set(evidence["selection"])
        ):
            raise ValueError("New evidence and original anchor complete runs overlap")
        return cls(doc)


def load_starting_evidence_policy_inputs(
    *,
    config: StartingOptionConfig,
    evidence_config: StartingEvidenceConfig,
    evidence_path: Path,
    anchor_assignment_report_path: Path,
    parent_checkpoint_path: Path,
    parent_report_path: Path,
    train_report_path: Path,
    validation_report_path: Path,
    split_manifest: SplitManifest,
    ruleset: RulesetIdentity,
    objective: ObjectiveSpec,
) -> policy.TrajectoryPolicyInputs:
    """Verify frozen public evidence and independent folds; never replay or optimize."""
    config = StartingOptionConfig.from_mapping(config.document)
    if config.document["schema_version"] != EVIDENCE_CONFIG_SCHEMA:
        raise ValueError("Exhaustive evidence requires the v2 starting-option training config")
    recipe = config.recipe.document
    if objective.objective_id != recipe["objective_id"]:
        raise ValueError("Starting evidence policy objective differs from its recipe")
    verification = verify_starting_option_evidence(
        evidence_path, config=evidence_config, split_manifest=split_manifest, ruleset=ruleset
    )
    summary = verification["summary"]
    if summary["evidence_sufficient"] is not True:
        raise ValueError("Starting evidence failed its frozen data-sufficiency gate")
    if summary["terminal_victories"] != 0:
        raise ValueError("Positive victory evidence requires a separate terminal-learning recipe")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    parent = load_production_model_checkpoint(parent_checkpoint_path)
    parent_report = load_production_training_report(parent_report_path, checkpoint=parent)
    assignment = load_production_training_report(anchor_assignment_report_path)
    if assignment.get("schema_version") != "production-model-training-report-v7":
        raise ValueError("Original anchor assignment must come from the verified #125 report")
    original_recipe = assignment["trajectory_finetuning"]["recipe"]
    original_wrapper = assignment["starting_option_training"]["config"]
    if (
        any(recipe[key] != original_recipe[key] for key in policy.OPTIMIZATION_FIELDS)
        or config.document["dimension"] != original_wrapper["dimension"]
        or config.document["encoder_id"] != original_wrapper["encoder_id"]
    ):
        raise ValueError("Starting evidence training changed the original optimization or limits")
    training_config = ProductionTrainingConfig.from_mapping(parent["training_config"])
    if parent["heads"]["terminal_value"]["status"] != "blocked":
        raise ValueError("Auxiliary evidence requires a blocked terminal-value parent")
    train_doc, train_states, anchors = _load_curriculum_examples(
        train_report_path, split_manifest=split_manifest, config=training_config
    )
    validation_doc, validation_states, validation = _load_curriculum_examples(
        validation_report_path, split_manifest=split_manifest, config=training_config
    )
    actual_inputs = {
        "parent_model_id": parent["model_id"],
        "parent_training_report_id": parent_report["report_id"],
        "evidence_report_id": evidence["report_id"],
        "evidence_config_id": evidence_config.config_id,
        "anchor_assignment_report_id": assignment["report_id"],
        "anchor_assignment_config_id": original_recipe["config_id"],
        "train_dataset_id": train_doc["dataset_id"],
        "validation_dataset_id": validation_doc["dataset_id"],
        "split_manifest_id": split_manifest.manifest_id,
        "ruleset_manifest_id": ruleset.manifest_id,
    }
    if recipe["inputs"] != actual_inputs:
        raise ValueError(
            "Starting evidence training input identities differ from the frozen recipe"
        )
    shared = policy.INPUT_FIELDS - {"collection_id", "search_report_id", "search_config_id"}
    if any(original_recipe["inputs"][key] != actual_inputs[key] for key in shared):
        raise ValueError("Original anchor assignment belongs to different training inputs")
    if (
        evidence["model_id"] != parent["model_id"]
        or evidence["training_report_id"] != parent_report["report_id"]
        or parent["train_dataset_id"] != train_doc["dataset_id"]
        or parent_report["validation_dataset_id"] != validation_doc["dataset_id"]
    ):
        raise ValueError("Starting evidence continuation or anchor corpus differs from the parent")
    for doc in (parent, evidence):
        if (
            any(
                doc[key] != actual_inputs[key]
                for key in ("ruleset_manifest_id", "split_manifest_id")
            )
            or doc["objective_id"] != objective.objective_id
        ):
            raise ValueError("Starting evidence ruleset, split or objective differs")
    if train_states.partition != "train" or validation_states.partition != "validation":
        raise ValueError("Original anchor and validation partitions differ")
    for doc in (train_doc, validation_doc):
        if doc["signal_assessment"]["auxiliary_policy_signal_pass"] is not True:
            raise ValueError("Original anchor curriculum failed its signal gate")
    for items, partition in ((anchors, SplitName.TRAIN), (validation, SplitName.VALIDATION)):
        if not items or any(
            split_manifest.split_for_seed(item.run_seed) is not partition
            or item.representation.ruleset_manifest_id != ruleset.manifest_id
            for item in items
        ):
            raise ValueError("Original curricula have incorrect complete-run ownership or ruleset")
    anchor_seeds = {item.run_seed for item in anchors}
    original_groups = assignment["trajectory_finetuning"]["complete_run_subfolds"]
    anchor_groups = {
        key: sorted(set(original_groups[key]) & anchor_seeds) for key in ("fit", "selection")
    }
    if (
        recipe["anchor_complete_run_subfolds"] != anchor_groups
        or set(anchor_groups["fit"] + anchor_groups["selection"]) != anchor_seeds
        or recipe["evidence_complete_run_subfolds"]
        != evidence_config.document["complete_run_subfolds"]
    ):
        raise ValueError("Frozen original anchor or pre-outcome evidence ownership changed")
    runs = {
        key: sorted(anchor_groups[key] + recipe["evidence_complete_run_subfolds"][key])
        for key in ("fit", "selection")
    }
    records: list[dict[str, Any]] = []
    examples: list[policy._Preference] = []
    exclusions: Counter[str] = Counter()
    for reference in evidence["cases"]:
        # The evidence verifier has already checked this path, file hash and full public trace.
        content = (evidence_path.parent / reference["path"]).read_bytes()
        if hashlib.sha256(content).hexdigest() != reference["sha256"]:
            raise ValueError("Starting evidence case changed after saved verification")
        case = json.loads(content)
        for comparison in case["comparisons"]:
            if comparison["label"] == "tied":
                exclusions["tied"] += 1
                continue
            component = comparison["deciding_rank_component"]
            weight = float(recipe["rank_weights"][component])
            if weight == 0:
                exclusions[component] += 1
            record = {
                "run_seed": case["run_seed"],
                "decision_type": "event",
                "source_observation": case["source_observation"],
                "candidate_action_ids": [a["action_id"] for a in case["source_legal_actions"]],
                "preferred_action_id": comparison["preferred_action_id"],
                "disfavored_action_id": comparison["disfavored_action_id"],
                "comparison_id": comparison["comparison_id"],
            }
            features = policy._features(record, ruleset, training_config)
            ids = record["candidate_action_ids"]
            records.append(record)
            examples.append(
                policy._Preference(
                    int(case["run_seed"]),
                    component,
                    "event",
                    weight,
                    features[ids.index(record["preferred_action_id"])],
                    features[ids.index(record["disfavored_action_id"])],
                    features,
                )
            )
    for key in ("fit", "selection"):
        count = sum(item.weight > 0 and item.run_seed in runs[key] for item in examples)
        if count != summary["complete_run_subfolds"][key]["eligible_pairs"]:
            raise ValueError("Starting policy preferences differ from verified evidence coverage")
    return policy.TrajectoryPolicyInputs(
        parent,
        parent_report,
        training_config,
        evidence,
        train_doc,
        validation_doc,
        anchors,
        validation,
        tuple(examples),
        tuple(records),
        dict(sorted(exclusions.items())),
        runs,
    )


def train_starting_evidence_policy(**kwargs: Any) -> ProductionTrainingResult:
    inputs = load_starting_evidence_policy_inputs(**kwargs)
    return policy.train_policy_inputs(
        inputs=inputs,
        ruleset=kwargs["ruleset"],
        config=kwargs["config"].recipe,
        residual_config=kwargs["config"],
    )


def _evidence_binding(
    inputs: policy.TrajectoryPolicyInputs, coverage: dict[str, Any]
) -> dict[str, Any]:
    summary = inputs.collection["summary"]
    absent = summary["selection_option_ids_absent_from_fitting"]
    return {
        "report_id": inputs.collection["report_id"],
        "config_id": inputs.collection["config_id"],
        "claim_scope": CLAIM,
        "evidence_sufficient": True,
        "independent_unit": "complete_run_seed",
        "preference_normalization": NORMALIZATION,
        "futures_per_option": 1,
        "games_replayed": 0,
        "selection_option_ids_absent_from_evidence_fitting": absent,
        "selection_only_ids_covered_by_fitting_anchors": sorted(
            set(absent) & set(coverage["fit_anchors"]["unique_option_ids"])
        ),
    }


def bind_starting_evidence_result(
    checkpoint: dict[str, Any], report: dict[str, Any], inputs: policy.TrajectoryPolicyInputs
) -> ProductionTrainingResult:
    report = copy.deepcopy(report)
    report["claim_scope"] = "anchored_train_starting_evidence_auxiliary_policy_candidate"
    report["starting_evidence_training"] = _evidence_binding(
        inputs, report["starting_option_training"]["coverage"]
    )
    report["selection_note"] = (
        "Original anchor folds and fresh evidence folds are preserved separately. "
        "Each option has one exact seeded future under the frozen parent continuation. "
        "Comparisons within a run are correlated. Validation is reused development evidence, "
        "not an untouched final test. No terminal-value or production promotion is claimed."
    )
    report["report_id"] = manifest_identifier({k: v for k, v in report.items() if k != "report_id"})
    policy.validate_trajectory_report(report, checkpoint=checkpoint)
    return ProductionTrainingResult(checkpoint, report)


def validate_starting_evidence_report(report: dict[str, Any]) -> None:
    recipe = StartingEvidencePolicyConfig.from_mapping(report["trajectory_finetuning"]["recipe"])
    wrapper = report["starting_option_training"]["config"]
    if wrapper["schema_version"] != EVIDENCE_CONFIG_SCHEMA:
        raise ValueError("Starting evidence report requires its v2 residual binding")
    summary = _mapping(report["collection_summary"], "starting evidence summary")
    groups = recipe.document["evidence_complete_run_subfolds"]
    for key in ("fit", "selection"):
        row = summary["complete_run_subfolds"][key]
        if (
            row["configured_runs"] != len(groups[key])
            or row["completed_runs"] != len(groups[key])
            or row["eligible_pairs"] != report[f"{key}_preferences"]
        ):
            raise ValueError("Starting evidence report changed complete-run coverage")
    count = len(groups["fit"]) + len(groups["selection"])
    if (
        summary["evidence_sufficient"] is not True
        or not all(summary["sufficiency_checks"].values())
        or summary["benchmark_denominator"] != count
        or summary["completed_runs"] != count
        or summary["candidate_denominator"] != 3 * count
        or summary["completed_branches"] != 3 * count
        or any(
            summary[key] != 0
            for key in (
                "terminal_victories",
                "failed_runs",
                "failed_or_missing_branches",
                "truncated_trajectories",
            )
        )
    ):
        raise ValueError("Starting evidence report violates its fixed auxiliary-only evidence gate")
    expected = {
        "report_id": recipe.document["inputs"]["evidence_report_id"],
        "config_id": recipe.document["inputs"]["evidence_config_id"],
        "claim_scope": CLAIM,
        "evidence_sufficient": True,
        "independent_unit": "complete_run_seed",
        "preference_normalization": NORMALIZATION,
        "futures_per_option": 1,
        "games_replayed": 0,
        "selection_option_ids_absent_from_evidence_fitting": summary[
            "selection_option_ids_absent_from_fitting"
        ],
        "selection_only_ids_covered_by_fitting_anchors": sorted(
            set(summary["selection_option_ids_absent_from_fitting"])
            & set(
                report["starting_option_training"]["coverage"]["fit_anchors"]["unique_option_ids"]
            )
        ),
    }
    if report["starting_evidence_training"] != expected:
        raise ValueError(
            "Starting evidence training provenance, normalization or vocabulary differs"
        )


def verify_starting_evidence_policy(
    *, checkpoint_path: Path, report_path: Path, **kwargs: Any
) -> dict[str, Any]:
    inputs = load_starting_evidence_policy_inputs(**kwargs)
    config = kwargs["config"]
    inputs, space = prepare_starting_option_space(inputs, kwargs["ruleset"], config)
    checkpoint = load_production_model_checkpoint(checkpoint_path)
    report = load_production_training_report(report_path, checkpoint=checkpoint)
    return verify_prepared_starting_evidence_policy(
        inputs=inputs, space=space, checkpoint=checkpoint, report=report
    )


def verify_prepared_starting_evidence_policy(
    *,
    inputs: policy.TrajectoryPolicyInputs,
    space: StartingOptionSpace,
    checkpoint: dict[str, Any],
    report: dict[str, Any],
) -> dict[str, Any]:
    """Reconcile a saved result using already verified and augmented source inputs."""
    config = space.config
    if (
        checkpoint["schema_version"] != CHECKPOINT_SCHEMA
        or report["schema_version"] != REPORT_SCHEMA
    ):
        raise ValueError("Saved starting evidence training has the wrong artifact version")
    if checkpoint["trajectory_finetuning"]["recipe"] != config.recipe.document:
        raise ValueError("Saved starting evidence training recipe differs")
    weights = {**production_model_from_checkpoint(inputs.parent_checkpoint).policy_weights}
    offset = space.offset
    for row in checkpoint["starting_option_residual"]["head"]["weights"]:
        weights[offset + row["index"]] = row["value"]
    baseline = dict(production_model_from_checkpoint(inputs.parent_checkpoint).policy_weights)
    fit_anchors = tuple(a for a in inputs.anchors if a.run_seed in inputs.runs["fit"])
    selection_anchors = tuple(a for a in inputs.anchors if a.run_seed in inputs.runs["selection"])
    eligible = tuple(p for p in inputs.preferences if p.weight > 0)
    selection = tuple(p for p in eligible if p.run_seed in inputs.runs["selection"])
    strong = tuple(
        p for p in selection if p.component in {"maximum_floor", "boss_reached", "act1_cleared"}
    )
    soft_baseline = inputs.parent_report["held_out_metrics"]["policy"]["soft_target_baseline"]

    def metrics(w: dict[int, float], rows: Any) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            _quantize_artifact(
                _evaluate_policy_weights(
                    w, rows, inputs.training_config, soft_baseline=soft_baseline
                )
            ),
        )

    expected = {
        "collection_summary": inputs.collection["summary"],
        "exclusions": inputs.exclusions,
        "fit_anchor_records": len(fit_anchors),
        "selection_anchor_records": len(selection_anchors),
        "training_records": len(inputs.anchors),
        "validation_records": len(inputs.validation),
        "parent_selection_policy": metrics(baseline, selection_anchors),
        "parent_validation_policy": metrics(baseline, inputs.validation),
        "parent_selection_preferences": _quantize_artifact(
            policy._preference_metrics(baseline, selection)
        ),
        "parent_strong_selection_preferences": _quantize_artifact(
            policy._preference_metrics(baseline, strong)
        ),
        "preference_diagnostics": _quantize_artifact(
            policy._preference_metrics(weights, inputs.preferences)
        ),
        "validation_drift": _quantize_artifact(policy._drift(weights, baseline, inputs.validation)),
        "starting_option_training": space.report_binding(weights),
        "starting_evidence_training": _evidence_binding(inputs, space.coverage),
    }
    if any(report[key] != value for key, value in expected.items()) or report["held_out_metrics"][
        "policy"
    ] != metrics(weights, inputs.validation):
        raise ValueError(
            "Saved starting evidence training metrics or coverage differ from its inputs"
        )
    if (
        any(
            report["held_out_metrics"][key] != inputs.parent_report["held_out_metrics"][key]
            for key in policy.FROZEN_HEADS
        )
        or report["terminal_value_status"] != inputs.parent_report["terminal_value_status"]
    ):
        raise ValueError("Starting evidence training changed frozen non-policy reports")
    epoch = report["trajectory_finetuning"]["selected_epoch"]
    if epoch:
        selected = report["training_history"][epoch - 1]
        fit = tuple(p for p in eligible if p.run_seed in inputs.runs["fit"])
        selected_expected = {
            "fit_preferences": _quantize_artifact(policy._preference_metrics(weights, fit)),
            "selection_preferences": _quantize_artifact(
                policy._preference_metrics(weights, selection)
            ),
            "strong_selection_preferences": _quantize_artifact(
                policy._preference_metrics(weights, strong)
            ),
            "selection_policy": metrics(weights, selection_anchors),
            "selection_drift": _quantize_artifact(
                policy._drift(weights, baseline, selection_anchors)
            ),
        }
        if any(selected[key] != value for key, value in selected_expected.items()):
            raise ValueError("Selected epoch metrics differ from saved starting policy weights")
    # Full parent reconstruction is checked by checkpoint loading; separately check later choices.
    model = production_model_from_checkpoint(checkpoint)
    parent_model = production_model_from_checkpoint(inputs.parent_checkpoint)
    from spireshift.starting_options import starting_option_ids

    later = tuple(a for a in inputs.validation if starting_option_ids(a.representation) is None)
    if any(
        model.predict(a.representation) != parent_model.predict(a.representation) for a in later
    ):
        raise ValueError("Starting residual changed a later decision or frozen head")
    return {
        "valid": True,
        "model_id": checkpoint["model_id"],
        "report_id": report["report_id"],
        "selected_epoch": report["trajectory_finetuning"]["selected_epoch"],
        "candidate_eligible": report["candidate_eligible"],
        "status": report["status"],
        "eligible_preferences": len(eligible),
        "fit_preferences": report["fit_preferences"],
        "selection_preferences": report["selection_preferences"],
        "validation_records": len(inputs.validation),
        "validation_checks": report["validation_checks"],
        "coverage": space.coverage,
        "starting_evidence_training": report["starting_evidence_training"],
        "later_validation_decisions_unchanged": len(later),
        "games_replayed": 0,
        "terminal_victory_positive_labels": 0,
        "checkpoint_promoted": False,
    }
