"""Frozen fresh-development pairing for an eligible linear or neural combat policy."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spireshift.agents.learned import ProductionCheckpointPolicy
from spireshift.combat_foundation import _relative_path
from spireshift.combat_policy import load_combat_policy_config
from spireshift.core.manifest import RulesetIdentity
from spireshift.core.objective import ObjectiveSpec
from spireshift.models import _exact_keys, _integer, _mapping
from spireshift.production_models import (
    _safe_child,
    load_production_model_checkpoint,
    load_production_training_report,
)
from spireshift.resource_tracking import load_resource_report
from spireshift.splits import SplitManifest, SplitName
from spireshift.starting_repeatability import _prior_inventory
from spireshift.trajectory_policy import _id, _identified
from spireshift.trajectory_search import Act1Milestones

SCHEMA = "combat-policy-confirmation-config-v1"
REPAIRED_SCHEMA = "combat-policy-confirmation-config-v2"
CLAIM = "paired_fresh_train_development_policy_only_confirmation"
COMPUTE_BOUNDARY = {
    "clock": "process_time",
    "workers": 1,
    "charged": "all_process_cpu_from_reset_return_through_final_outcome_check",
    "initialization": "factory_and_reset_cpu_reported_separately",
    "enforcement": "cooperative_before_and_after_policy_and_transition",
    "over_budget_outcome": "truncated_non_victory_in_original_denominator",
    "cleanup": "reported_separately_not_charged_to_decisions",
}


@dataclass(frozen=True)
class CombatConfirmationConfig:
    document: dict[str, Any]

    @classmethod
    def from_mapping(cls, value: object) -> CombatConfirmationConfig:
        d = copy.deepcopy(_mapping(value, "combat confirmation"))
        repaired = d.get("schema_version") == REPAIRED_SCHEMA
        _exact_keys(
            d,
            {
                "schema_version",
                "config_id",
                "training_config_path",
                "training_config_id",
                "candidate",
                "reference",
                "objective",
                "ruleset_manifest_id",
                "patch_id",
                "split_manifest_id",
                "partition",
                "seeds",
                "run_offset",
                "prior_train_prefix_stop",
                "maximum_decisions_per_run",
                "cycle_repetition_threshold",
                "liveness_tail_length",
                "no_op_fallback_threshold",
                "milestones",
                "compute_boundary",
                "claim_scope",
                "promotion_rule",
            }
            | ({"selection_repair"} if repaired else set()),
            "combat confirmation",
        )
        _identified(d, "config_id")
        for key in ("config_id", "training_config_id", "ruleset_manifest_id", "split_manifest_id"):
            _id(d[key], key)
        _relative_path(d["training_config_path"])
        for role in ("candidate", "reference"):
            fields = {"checkpoint_path", "report_path", "model_id", "report_id"}
            if role == "candidate":
                fields |= {"resource_path", "resource_report_id"}
            part = _mapping(d[role], role)
            _exact_keys(part, fields, role)
            for key, item in part.items():
                _relative_path(item) if key.endswith("_path") else _id(item, key)
        objective = ObjectiveSpec.from_mapping(_mapping(d["objective"], "objective"))
        if repaired:
            from spireshift.neural_selection import REPAIRED_CLAIM, validate_selection_repair

            repair = validate_selection_repair(d["selection_repair"])
            if (
                repair["layout"]["patch_id"] != d["patch_id"]
                or repair["layout"]["ruleset_manifest_id"] != d["ruleset_manifest_id"]
            ):
                raise ValueError("Selection repair layout differs from confirmation ruleset")
            claim = REPAIRED_CLAIM
        else:
            claim = CLAIM
        Act1Milestones.from_mapping(d["milestones"])
        seeds = d["seeds"]
        if (
            d["schema_version"] not in {SCHEMA, REPAIRED_SCHEMA}
            or d["partition"] != "train"
            or d["claim_scope"] != claim
            or d["promotion_rule"] != "no_automatic_promotion_auxiliary_floor_insufficient"
            or d["compute_boundary"] != COMPUTE_BOUNDARY
            or objective.objective_id != "terminal-victory-v1"
            or not isinstance(seeds, list)
            or not seeds
            or any(type(s) is not int or s < 0 for s in seeds)
            or len(seeds) != len(set(seeds))
            or d["candidate"]["model_id"] == d["reference"]["model_id"]
            or not isinstance(d["patch_id"], str)
            or not d["patch_id"]
        ):
            raise ValueError("Combat confirmation protocol or identities differ")
        for key, minimum in (
            ("run_offset", 0),
            ("prior_train_prefix_stop", 0),
            ("maximum_decisions_per_run", 1),
            ("cycle_repetition_threshold", 2),
            ("liveness_tail_length", 1),
            ("no_op_fallback_threshold", 1),
        ):
            if _integer(d[key], key) < minimum:
                raise ValueError(f"Invalid combat confirmation {key}")
        if d["run_offset"] < d["prior_train_prefix_stop"]:
            raise ValueError("Combat confirmation overlaps the inspected train prefix")
        return cls(d)

    def candidate_policy_id(self) -> str:
        model_id = self.document["candidate"]["model_id"]
        if self.document["schema_version"] == REPAIRED_SCHEMA:
            from spireshift.combat_features import CombatLayout
            from spireshift.neural_selection import selection_policy_id

            return selection_policy_id(
                model_id, CombatLayout.from_mapping(self.document["selection_repair"]["layout"])
            )
        return f"production-checkpoint-policy-v1:{model_id}"

    def validate_evaluation(
        self,
        *,
        model_id: str,
        report_id: str,
        reference_model_id: str | None,
        reference_report_id: str | None,
        split: SplitManifest,
        ruleset_manifest_id: str,
        patch_id: str,
        seeds: tuple[int, ...],
        workers: int,
        maximum_decisions: int,
        cycle_threshold: int,
        tail_length: int,
        fallback_threshold: int,
    ) -> None:
        d = self.document
        if (
            model_id != d["candidate"]["model_id"]
            or report_id != d["candidate"]["report_id"]
            or reference_model_id != d["reference"]["model_id"]
            or reference_report_id != d["reference"]["report_id"]
            or split.manifest_id != d["split_manifest_id"]
            or ruleset_manifest_id != d["ruleset_manifest_id"]
            or patch_id != d["patch_id"]
            or seeds != tuple(d["seeds"])
            or workers != 1
            or maximum_decisions != d["maximum_decisions_per_run"]
            or cycle_threshold != d["cycle_repetition_threshold"]
            or tail_length != d["liveness_tail_length"]
            or fallback_threshold != d["no_op_fallback_threshold"]
            or list(split.seeds(SplitName.TRAIN)[d["run_offset"] : d["run_offset"] + len(seeds)])
            != list(seeds)
            or any(split.split_for_seed(seed) != SplitName.TRAIN for seed in seeds)
        ):
            raise ValueError("Fresh combat evaluation differs from its frozen confirmation")


def load_combat_confirmation_config(path: Path) -> CombatConfirmationConfig:
    return CombatConfirmationConfig.from_mapping(json.loads(path.read_text()))


def load_confirmation_policies(
    *,
    config: CombatConfirmationConfig,
    project_root: Path,
    split: SplitManifest,
    ruleset: RulesetIdentity,
    objective: ObjectiveSpec,
) -> tuple[ProductionCheckpointPolicy, ProductionCheckpointPolicy]:
    """Bounded saved-artifact verification; never open teacher case files or initialize a game."""
    config = CombatConfirmationConfig.from_mapping(config.document)
    d = config.document
    root = project_root.resolve()
    candidate = d["candidate"]
    reference = d["reference"]
    cp = load_production_model_checkpoint(_safe_child(root, candidate["checkpoint_path"]))
    report = load_production_training_report(
        _safe_child(root, candidate["report_path"]), checkpoint=cp
    )
    parent = load_production_model_checkpoint(_safe_child(root, reference["checkpoint_path"]))
    parent_report = load_production_training_report(
        _safe_child(root, reference["report_path"]), checkpoint=parent
    )
    resource = load_resource_report(_safe_child(root, candidate["resource_path"]))
    training_path = _safe_child(root, d["training_config_path"])
    if report.get("schema_version") == "production-model-training-report-v10":
        from spireshift.neural_combat import load_neural_combat_config

        neural = load_neural_combat_config(training_path)
        training_document = neural.document
        f = neural.data.foundation.document
        fresh = neural.document["fresh_confirmation"]
        maximum_decisions = neural.data.document["fresh_confirmation"]["max_decisions_per_run"]
        report_recipe_matches = (
            report["neural_config"] == training_document
            and report["config"] == neural.data.document
        )
        # The neural pilot inspected the preceding linear comparison. Check its compact
        # identity/seed inventory too; never replay diagnostic or teacher cases here.
        source = neural.document["diagnosis"]
        diagnosis = json.loads(_safe_child(root, source["path"]).read_text())
        _identified(diagnosis, "report_id")
        inspected = source["inspected_seeds"]
        if (
            diagnosis["report_id"] != source["report_id"]
            or diagnosis["summary"]["analysis_integrity_pass"] is not True
            or sorted({case["seed"] for case in diagnosis["cases"]}) != inspected
            or not set(inspected) <= set(split.seeds(SplitName.TRAIN)[: fresh["run_offset"]])
            or set(inspected) & set(d["seeds"])
        ):
            raise ValueError("Neural confirmation diagnosis differs or overlaps fresh seeds")
    else:
        recipe = load_combat_policy_config(training_path)
        training_document = recipe.document
        f = recipe.foundation.document
        fresh = recipe.document["fresh_confirmation"]
        maximum_decisions = fresh["max_decisions_per_run"]
        report_recipe_matches = report["config"] == training_document
    verification = report["seed_verification"]
    if (
        training_document["config_id"] != d["training_config_id"]
        or not report_recipe_matches
        or cp["model_id"] != candidate["model_id"]
        or report["report_id"] != candidate["report_id"]
        or parent["model_id"] != reference["model_id"]
        or parent_report["report_id"] != reference["report_id"]
        or reference["model_id"] != f["model_id"]
        or reference["report_id"] != f["training_report_id"]
        or reference["checkpoint_path"] != f["parent_checkpoint"]
        or reference["report_path"] != f["parent_report"]
        or report["candidate_eligible"] is not True
        or report["status"] != "requires_fresh_confirmation"
        or verification["disjoint"] is not True
        or verification["fresh_seeds"] != d["seeds"]
        or d["seeds"] != fresh["seeds"]
        or d["run_offset"] != fresh["run_offset"]
        or d["prior_train_prefix_stop"] != fresh["prior_train_prefix_stop"]
        or d["maximum_decisions_per_run"] != maximum_decisions
        or d["objective"] != objective.as_dict()
        or d["objective"] != f["objective"]
        or resource["report_id"] != candidate["resource_report_id"]
        or resource["status"] != "completed"
        or resource["exit_code"] != 0
        or resource["cap"] is not None
        or resource["experiment_kind"] != "training"
        or any(resource["usage"][k] != 0 for k in ("trajectories", "simulations", "transitions"))
    ):
        raise ValueError("Combat confirmation needs its frozen eligible owner training result")
    # Confirm cached seed inventories remain intact; no source-case or game replay.
    for inventory in verification["prior_inventories"]:
        checked = _prior_inventory(
            {k: inventory[k] for k in ("kind", "path", "source_id")}, root, split, ruleset
        )
        if checked != inventory or set(checked["complete_run_seeds"]) & set(d["seeds"]):
            raise ValueError("Combat confirmation prior seed inventory differs or overlaps")
    candidate_policy = ProductionCheckpointPolicy(
        checkpoint=cp, training_report=report, ruleset=ruleset
    )
    reference_policy = ProductionCheckpointPolicy(
        checkpoint=parent, training_report=parent_report, ruleset=ruleset
    )
    if d["schema_version"] == REPAIRED_SCHEMA:
        from spireshift.neural_selection import prepare_selection_repair

        candidate_policy = prepare_selection_repair(
            repair=d["selection_repair"],
            confirmation_document=d,
            candidate=candidate_policy,
            reference=reference_policy,
            project_root=root,
            split=split,
        )
    config.validate_evaluation(
        model_id=candidate_policy.model_id,
        report_id=report["report_id"],
        reference_model_id=reference_policy.model_id,
        reference_report_id=parent_report["report_id"],
        split=split,
        ruleset_manifest_id=ruleset.manifest_id,
        patch_id=ruleset.patch_id,
        seeds=tuple(d["seeds"]),
        workers=1,
        maximum_decisions=d["maximum_decisions_per_run"],
        cycle_threshold=d["cycle_repetition_threshold"],
        tail_length=d["liveness_tail_length"],
        fallback_threshold=d["no_op_fallback_threshold"],
    )
    return candidate_policy, reference_policy
