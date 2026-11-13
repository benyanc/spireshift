"""Saved-artifact feasibility audit for a combat-only selection gate; no fitting or games."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import ObjectiveSpec, load_objective
from spireshift.models import _exact_keys, _finite_number, _integer, _mapping, _quantize_artifact
from spireshift.resource_tracking import load_resource_report
from spireshift.trajectory_policy import _id, _identified

SCHEMA = "combat-selection-gate-audit-v1"
SCOPE = "cached_training_and_foundation_artifacts_no_source_reaudit"
GATE_SCOPE = "relative_train_selection_safety_absolute_original_validation"
TOLERANCE = 1e-9  # Artifact rounding reconciliation, never a training safety tolerance.
IDENTITIES = {
    "training_config_id",
    "candidate_model_id",
    "candidate_report_id",
    "resource_report_id",
    "foundation_report_id",
    "parent_model_id",
    "parent_report_id",
    "train_dataset_id",
    "validation_dataset_id",
    "split_manifest_id",
}
FIELDS = {
    "schema_version",
    "audit_id",
    "objective",
    "sources",
    "selection_regret_bound",
    "selection_parent_gate",
    "quality_reference",
    "recorded_history",
    "decision",
    "scope",
    "source_cases_opened",
    "optimizer_steps",
    "games_replayed",
    "checkpoint_promoted",
}


def regret_feasibility(
    *,
    decisions: int,
    combat_decisions: int,
    parent_mean_regret: float,
    combat_parent_regret_sum: float,
    source_order_mean_regret: float,
) -> dict[str, Any]:
    """An optimistic bound: even an unconstrained combat oracle cannot repair frozen choices."""
    if (
        type(decisions) is not int
        or type(combat_decisions) is not int
        or not 0 < combat_decisions <= decisions
        or any(
            not math.isfinite(x) or x < 0
            for x in (parent_mean_regret, combat_parent_regret_sum, source_order_mean_regret)
        )
    ):
        raise ValueError("Invalid combat gate regret inventory")
    fixed_regret = decisions * parent_mean_regret - combat_parent_regret_sum
    if fixed_regret < -TOLERANCE:
        raise ValueError("Combat regret exceeds the recorded all-decision regret")
    lower = max(0.0, fixed_regret) / decisions
    return cast(
        dict[str, Any],
        _quantize_artifact(
            {
                "decisions": decisions,
                "combat_decisions": combat_decisions,
                "frozen_noncombat_decisions": decisions - combat_decisions,
                "parent_mean_regret": parent_mean_regret,
                "combat_parent_regret_sum": combat_parent_regret_sum,
                "optimistic_global_regret_lower_bound": lower,
                "source_order_mean_regret": source_order_mean_regret,
                "infeasibility_margin": lower - source_order_mean_regret,
                "rounding_tolerance": TOLERANCE,
                "impossible_even_with_perfect_combat": lower > source_order_mean_regret + TOLERANCE,
            }
        ),
    )


def validate_combat_gate_audit(value: object) -> dict[str, Any]:
    d = _mapping(value, "combat selection gate audit")
    _exact_keys(d, FIELDS, "combat selection gate audit")
    _identified(d, "audit_id")
    objective = ObjectiveSpec.from_mapping(_mapping(d["objective"], "objective"))
    sources = _mapping(d["sources"], "combat gate sources")
    _exact_keys(sources, IDENTITIES, "combat gate sources")
    for key, item in sources.items():
        _id(item, key)
    bound = _mapping(d["selection_regret_bound"], "combat regret bound")
    expected = regret_feasibility(
        decisions=_integer(bound.get("decisions"), "decisions"),
        combat_decisions=_integer(bound.get("combat_decisions"), "combat decisions"),
        parent_mean_regret=_finite_number(bound.get("parent_mean_regret"), "parent regret"),
        combat_parent_regret_sum=_finite_number(
            bound.get("combat_parent_regret_sum"), "combat regret"
        ),
        source_order_mean_regret=_finite_number(
            bound.get("source_order_mean_regret"), "source order"
        ),
    )
    _exact_keys(bound, set(expected), "combat regret bound")
    if bound != expected:
        raise ValueError("Combat gate bound does not reconcile")
    reference = _mapping(d["quality_reference"], "combat gate reference")
    _exact_keys(
        reference,
        {
            "selection_dataset_id",
            "soft_baseline_dataset_id",
            "populations_differ",
            "selection_soft_reference_copied_from_validation",
            "matched_selection_soft_reference_available",
        },
        "combat gate reference",
    )
    if (
        reference["selection_dataset_id"] != sources["train_dataset_id"]
        or reference["soft_baseline_dataset_id"] != sources["validation_dataset_id"]
        or reference["populations_differ"] is not True
        or sources["train_dataset_id"] == sources["validation_dataset_id"]
        or reference["selection_soft_reference_copied_from_validation"] is not True
        or reference["matched_selection_soft_reference_available"] is not False
    ):
        raise ValueError("Combat gate reference ownership differs")
    parent_gate = _mapping(d["selection_parent_gate"], "parent selection gate")
    if (
        parent_gate.get("passed") is not False
        or parent_gate.get("checks", {}).get("regret_below_source_order") is not False
    ):
        raise ValueError("Combat gate audit does not describe the rejected parent selection gate")
    history = _mapping(d["recorded_history"], "combat recorded history")
    _exact_keys(
        history,
        {
            "epochs",
            "selected_epoch",
            "candidate_eligible",
            "failed_check_counts",
            "epochs_blocked_only_by_absolute_selection_gate",
            "intermediate_weights_available",
            "final_validation_describes_parent",
        },
        "combat recorded history",
    )
    epochs = _integer(history["epochs"], "epochs")
    counts = _mapping(history["failed_check_counts"], "failed checks")
    only = history["epochs_blocked_only_by_absolute_selection_gate"]
    if (
        epochs < 1
        or history["selected_epoch"] != 0
        or history["candidate_eligible"] is not False
        or counts.get("original_auxiliary_gate") != epochs
        or any(type(x) is not int or not 0 <= x <= epochs for x in counts.values())
        or not isinstance(only, list)
        or only != sorted(set(only))
        or any(type(x) is not int or not 1 <= x <= epochs for x in only)
        or history["intermediate_weights_available"] is not False
        or history["final_validation_describes_parent"] is not True
    ):
        raise ValueError("Combat gate history interpretation differs")
    decision = {
        "corrected_selection_gate_scope": GATE_SCOPE,
        "original_result_remains_rejected": True,
        "automatic_training_allowed": False,
        "automatic_gameplay_allowed": False,
        "adaptive_controller_allowed": False,
        "next_step": "new_versioned_recipe_source_reconciliation_before_owner_training",
    }
    if (
        d["schema_version"] != SCHEMA
        or d["scope"] != SCOPE
        or objective.objective_id != "terminal-victory-v1"
        or bound["impossible_even_with_perfect_combat"] is not True
        or d["decision"] != decision
        or d["checkpoint_promoted"] is not False
        or any(
            type(d[k]) is not int or d[k] != 0
            for k in ("source_cases_opened", "optimizer_steps", "games_replayed")
        )
    ):
        raise ValueError("Combat gate audit cannot authorize promotion or relax the objective")
    return d


def build_combat_gate_audit(
    *,
    saved: dict[str, Any],
    foundation: dict[str, Any],
    parent_report: dict[str, Any],
    resource_report_id: str,
) -> dict[str, Any]:
    """Analyze already verified documents; never reconstruct discarded epoch weights."""
    from spireshift.combat_policy import CombatPolicyConfig, validate_combat_policy_report

    saved = validate_combat_policy_report(saved)
    config = CombatPolicyConfig.from_mapping(saved["config"])
    f = config.foundation.document
    if (
        config.document["schema_version"] != "combat-policy-training-config-v2"
        or saved["selected_epoch"] != 0
        or saved["candidate_eligible"] is not False
        or foundation["report_id"] != config.document["foundation_report_id"]
        or parent_report["report_id"] != f["training_report_id"]
        or saved["parent_selection_policy"]["soft_target_baseline"]
        != parent_report["held_out_metrics"]["policy"]["soft_target_baseline"]
    ):
        raise ValueError("Combat gate diagnosis needs the frozen rejected v2 recipe")
    rows = [r for r in foundation["rows"] if r["subfold"] == "selection"]
    history = saved["training_history"]
    decisions = history[0]["selection_original_drift"]["decisions"]
    if (
        len(rows) != saved["parent_selection_combat"]["combat_states"]
        or any(r["binding_status"] != "completed" for r in rows)
        or any(row["selection_original_drift"]["decisions"] != decisions for row in history)
    ):
        raise ValueError("Combat gate selection denominators differ")
    bound = regret_feasibility(
        decisions=decisions,
        combat_decisions=len(rows),
        parent_mean_regret=saved["parent_selection_policy"]["mean_progress_utility_regret"],
        combat_parent_regret_sum=sum(row["parent_auxiliary_regret"] for row in rows),
        source_order_mean_regret=saved["parent_selection_policy"][
            "source_order_mean_progress_utility_regret"
        ],
    )
    body = cast(
        dict[str, Any],
        _quantize_artifact(
            {
                "schema_version": SCHEMA,
                "objective": f["objective"],
                "sources": {
                    "training_config_id": config.document["config_id"],
                    "candidate_model_id": saved["model_id"],
                    "candidate_report_id": saved["report_id"],
                    "resource_report_id": resource_report_id,
                    "foundation_report_id": foundation["report_id"],
                    "parent_model_id": f["model_id"],
                    "parent_report_id": f["training_report_id"],
                    "train_dataset_id": f["dataset_id"],
                    "validation_dataset_id": saved["validation_dataset_id"],
                    "split_manifest_id": saved["split_manifest_id"],
                },
                "selection_regret_bound": bound,
                "selection_parent_gate": saved["parent_selection_policy"]["auxiliary_policy_gate"],
                "quality_reference": {
                    "selection_dataset_id": f["dataset_id"],
                    "soft_baseline_dataset_id": saved["validation_dataset_id"],
                    "populations_differ": f["dataset_id"] != saved["validation_dataset_id"],
                    "selection_soft_reference_copied_from_validation": True,
                    "matched_selection_soft_reference_available": False,
                },
                "recorded_history": {
                    "epochs": len(history),
                    "selected_epoch": saved["selected_epoch"],
                    "candidate_eligible": saved["candidate_eligible"],
                    "failed_check_counts": dict(
                        sorted(
                            Counter(
                                k for row in history for k, v in row["checks"].items() if not v
                            ).items()
                        )
                    ),
                    "epochs_blocked_only_by_absolute_selection_gate": [
                        row["epoch"]
                        for row in history
                        if {k for k, v in row["checks"].items() if not v}
                        == {"original_auxiliary_gate"}
                    ],
                    "intermediate_weights_available": False,
                    "final_validation_describes_parent": True,
                },
                "decision": {
                    "corrected_selection_gate_scope": GATE_SCOPE,
                    "original_result_remains_rejected": True,
                    "automatic_training_allowed": False,
                    "automatic_gameplay_allowed": False,
                    "adaptive_controller_allowed": False,
                    "next_step": "new_versioned_recipe_source_reconciliation_before_owner_training",
                },
                "scope": SCOPE,
                "source_cases_opened": 0,
                "optimizer_steps": 0,
                "games_replayed": 0,
                "checkpoint_promoted": False,
            }
        ),
    )
    return validate_combat_gate_audit({**body, "audit_id": manifest_identifier(body)})


def audit_saved_combat_selection_gate(
    *,
    config_path: Path,
    model_root: Path,
    resource_path: Path,
    project_root: Path,
    objective: ObjectiveSpec,
) -> dict[str, Any]:
    """A bounded cached-file audit; the next owner trainer rechecks the actual source data."""
    from spireshift.combat_foundation import load_combat_foundation_report
    from spireshift.combat_policy import load_combat_policy_config
    from spireshift.production_models import (
        _safe_child,
        load_production_model_checkpoint,
        load_production_training_report,
    )

    root = project_root.resolve()
    config = load_combat_policy_config(config_path)
    f = config.foundation.document
    if objective.as_dict() != f["objective"]:
        raise ValueError("Combat gate audit objective differs from the training experiment")
    checkpoint = load_production_model_checkpoint(model_root / "checkpoint.json")
    saved = load_production_training_report(
        model_root / "training-report.json", checkpoint=checkpoint
    )
    if (
        saved["config"] != config.document
        or checkpoint["combat_policy_residual"]["head"]["weights"]
    ):
        raise ValueError("Combat gate audit requires the immutable epoch-zero fallback")
    parent = load_production_model_checkpoint(_safe_child(root, f["parent_checkpoint"]))
    parent_report = load_production_training_report(
        _safe_child(root, f["parent_report"]), checkpoint=parent
    )
    foundation = load_combat_foundation_report(
        _safe_child(root, config.document["foundation_report_path"]), config.foundation
    )
    resource = load_resource_report(resource_path)
    command = resource["command"]
    if (
        resource["experiment_kind"] != "training"
        or resource["status"] != "completed"
        or resource["exit_code"] != 0
        or resource["cap"] is not None
        or command[:5] != ["uv", "run", "spireshift", "model", "train-combat-policy"]
        or len(command) < 6
        or (len(command) - 6) % 2
        or any(
            resource["usage"][key] != 0 for key in ("trajectories", "simulations", "transitions")
        )
    ):
        raise ValueError("Combat gate audit needs the completed saved-data training resource")
    recorded_root = Path(resource["working_directory"])
    flags = command[6::2]
    arguments = dict(zip(flags, command[7::2], strict=True))
    if (
        not recorded_root.is_absolute()
        or len(flags) != len(set(flags))
        or set(flags)
        - {
            "--project-root",
            "--objective-config",
            "--upstream-root",
            "--split-manifest",
            "--manifest",
            "--output-dir",
        }
        or not {"--upstream-root", "--split-manifest", "--manifest", "--output-dir"} <= set(flags)
    ):
        raise ValueError("Combat gate training command flags differ")
    if (
        (recorded_root / command[5]).resolve() != config_path.resolve()
        or (recorded_root / arguments["--output-dir"]).resolve() != model_root.resolve()
        or (recorded_root / arguments.get("--project-root", ".")).resolve() != root
        or load_objective(
            recorded_root / arguments.get("--objective-config", "configs/default.toml")
        ).as_dict()
        != objective.as_dict()
        or not any(
            model_root.resolve().is_relative_to(Path(p).resolve())
            for p in resource["artifacts"]["roots"]
        )
    ):
        raise ValueError("Combat gate resource command belongs to different saved outputs")
    return build_combat_gate_audit(
        saved=saved,
        foundation=foundation,
        parent_report=parent_report,
        resource_report_id=resource["report_id"],
    )


def load_combat_gate_audit(path: Path) -> dict[str, Any]:
    return validate_combat_gate_audit(json.loads(path.read_text()))
