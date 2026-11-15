"""Explicit, weight-preserving neural support for inspected public discard choices."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from spireshift.agents.learned import ProductionCheckpointPolicy
from spireshift.combat_features import (
    DISCARD_LAYOUT_SCHEMA,
    TRANSFORM_LAYOUT_SCHEMA,
    CombatLayout,
    bind_public_combat,
)
from spireshift.combat_foundation import _relative_path
from spireshift.core.manifest import manifest_identifier
from spireshift.models import _exact_keys, _mapping
from spireshift.neural_combat import NeuralCombatHead
from spireshift.production_models import _safe_child
from spireshift.resource_tracking import load_resource_report
from spireshift.splits import SplitManifest
from spireshift.trajectory_policy import _id, _identified

REPAIR_SCHEMA = "neural-public-discard-selection-repair-v1"
REPAIRED_CLAIM = "paired_inspected_train_neural_selection_compatibility"
CAPTURE_CLAIM = "inspected_failure_public_reproduction_not_strength_evidence"
ENGINE_FILES = {
    "src/Sts2Emulator/Core/PendingCardSelection.cs",
    "src/Sts2Emulator/Core/CombatObservation.cs",
    "src/Sts2Emulator/Core/CombatEngine.cs",
}


def validate_selection_repair(value: object) -> dict[str, Any]:
    d = copy.deepcopy(_mapping(value, "neural selection repair"))
    _exact_keys(
        d,
        {
            "schema_version",
            "source_confirmation_path",
            "source_confirmation_id",
            "source_comparison_path",
            "source_comparison_report_id",
            "source_comparison_resource_path",
            "source_comparison_resource_report_id",
            "capture_collection_path",
            "capture_collection_id",
            "engine_source_root",
            "engine_source_sha256",
            "layout",
            "weights_rule",
            "information_policy",
        },
        "neural selection repair",
    )
    for key, item in d.items():
        if key.endswith("_path") or key == "engine_source_root":
            _relative_path(item)
        elif key.endswith("_id"):
            _id(item, key)
    layout = CombatLayout.from_mapping(d["layout"])
    sources = _mapping(d["engine_source_sha256"], "selection semantics sources")
    _exact_keys(sources, ENGINE_FILES, "selection semantics sources")
    for digest in sources.values():
        _id(f"sha256:{digest}", "selection source hash")
    if (
        d["schema_version"] != REPAIR_SCHEMA
        or layout.schema_version != DISCARD_LAYOUT_SCHEMA
        or d["weights_rule"] != "unchanged_checkpoint_weights_explicit_runtime_layout_extension"
        or d["information_policy"] != "public_visible_choices_and_supplied_legal_menu_only"
    ):
        raise ValueError("Neural selection repair contract differs")
    return d


def selection_policy_id(model_id: str, layout: CombatLayout) -> str:
    identity = manifest_identifier({"schema_version": REPAIR_SCHEMA, "layout": layout.as_dict()})
    return f"neural-selection-compatibility-policy-v1:{model_id}:{identity}"


class NeuralSelectionCompatibilityPolicy(ProductionCheckpointPolicy):
    """Uses the same learned scores; supplies a separately identified public binding."""

    def __init__(self, source: ProductionCheckpointPolicy, layout: CombatLayout) -> None:
        head = source._model.combat_policy_residual
        if (
            not isinstance(head, NeuralCombatHead)
            or head.layout.schema_version != TRANSFORM_LAYOUT_SCHEMA
            or layout.schema_version != DISCARD_LAYOUT_SCHEMA
            or (head.layout.patch_id, head.layout.ruleset_manifest_id)
            != (layout.patch_id, layout.ruleset_manifest_id)
        ):
            raise ValueError("Selection repair requires the matching v3 neural source policy")
        self._model = copy.copy(source._model)
        self._model.combat_policy_residual = replace(head, layout=layout)
        self.model_id, self.split_manifest_id, self.ruleset = (
            source.model_id,
            source.split_manifest_id,
            source.ruleset,
        )
        self.policy_id = selection_policy_id(self.model_id, layout)


def prepare_selection_repair(
    *,
    repair: dict[str, Any],
    confirmation_document: dict[str, Any],
    candidate: ProductionCheckpointPolicy,
    reference: ProductionCheckpointPolicy,
    project_root: Path,
    split: SplitManifest,
) -> NeuralSelectionCompatibilityPolicy:
    """Read/validate saved public evidence only; never initialize a game or predict."""
    from spireshift.combat_confirmation import CLAIM, SCHEMA, load_combat_confirmation_config
    from spireshift.combat_replay_diagnostic import _actions, _observation
    from spireshift.production_evaluation import (
        LEARNED_POLICY_KIND,
        load_production_policy_evaluation,
    )
    from spireshift.representations import build_model_input

    d, root = validate_selection_repair(repair), project_root.resolve()
    source_config = load_combat_confirmation_config(
        _safe_child(root, d["source_confirmation_path"])
    )
    expected = copy.deepcopy(confirmation_document)
    del expected["selection_repair"]
    expected.update(schema_version=SCHEMA, claim_scope=CLAIM)
    expected["config_id"] = manifest_identifier(
        {k: v for k, v in expected.items() if k != "config_id"}
    )
    if (
        source_config.document != expected
        or source_config.document["config_id"] != d["source_confirmation_id"]
    ):
        raise ValueError(
            "Selection repair must preserve the inspected source models/cohort/budgets"
        )
    source_path = _safe_child(root, d["source_comparison_path"])
    comparison = load_production_policy_evaluation(
        source_path,
        model_id=candidate.model_id,
        training_report_id=expected["candidate"]["report_id"],
        reference_model_id=reference.model_id,
        reference_training_report_id=expected["reference"]["report_id"],
        split_manifest=split,
    )
    resource = load_resource_report(_safe_child(root, d["source_comparison_resource_path"]))
    if (
        comparison["report_id"] != d["source_comparison_report_id"]
        or comparison["confirmation_config"] != source_config.document
        or resource["report_id"] != d["source_comparison_resource_report_id"]
        or resource["status"] != "failed"
        or resource["exit_code"] != 1
        or resource["cap"] is not None
        or resource["experiment_kind"] != "rollout"
        or resource["usage"]["trajectories"] != len(comparison["cases"])
        or resource["usage"]["simulations"] != 0
        or resource["usage"]["transitions"]
        != sum(
            comparison["summary"][arm]["completed_transitions"]
            for arm in ("candidate", "reference")
        )
    ):
        raise ValueError("Selection repair source comparison/resource differs")
    failures = {}
    for entry in comparison["cases"]:
        case = json.loads(_safe_child(source_path.parent, entry["path"]).read_text())
        if case["status"] == "failed":
            if case["policy_kind"] != LEARNED_POLICY_KIND:
                raise ValueError("This repair cannot substitute for a failed reference policy")
            failures[case["seed"]] = case
    collection_path = _safe_child(root, d["capture_collection_path"])
    collection = json.loads(collection_path.read_text())
    _identified(collection, "report_id")
    if (
        collection["schema_version"] != "public-combat-menu-failure-capture-collection-v1"
        or collection["claim_scope"] != CAPTURE_CLAIM
        or collection["report_id"] != d["capture_collection_id"]
        or collection["source_report_id"] != comparison["report_id"]
        or not failures
        or sorted(c["seed"] for c in collection["cases"]) != sorted(failures)
        or collection["games"] != len(failures)
        or collection["simulations"] != 0
        or collection["optimizer_steps"] != 0
    ):
        raise ValueError("Selection capture inventory or identities differ")
    layout = CombatLayout.from_mapping(d["layout"])
    if (layout.patch_id, layout.ruleset_manifest_id) != (
        candidate.ruleset.patch_id,
        candidate.ruleset.manifest_id,
    ):
        raise ValueError("Selection runtime layout belongs to another ruleset")
    transitions = 0
    for entry in collection["cases"]:
        capture = json.loads(_safe_child(collection_path.parent, entry["path"]).read_text())
        _identified(capture, "capture_id")
        source_case = failures[entry["seed"]]
        replay = capture["replay_result"]
        rows = capture["public_rows"]
        if (
            capture["schema_version"] != "public-combat-menu-failure-capture-v1"
            or capture["claim_scope"] != CAPTURE_CLAIM
            or capture["capture_id"] != entry["capture_id"]
            or capture["source_case_id"] != source_case["case_id"]
            or capture["source_report_id"] != comparison["report_id"]
            or capture["model_id"] != candidate.model_id
            or capture["ruleset_manifest_id"] != candidate.ruleset.manifest_id
            or capture["objective"] != expected["objective"]
            or capture["seed"] != entry["seed"]
            or capture["optimizer_steps"] != 0
            or entry["source_case_reproduced"] is not True
            or any(replay[k] != source_case[k] for k in ("status", "error", "public_progress"))
            or any(
                replay["activity"][k] != source_case["activity"][k]
                for k in ("attempted_decisions", "completed_transitions")
            )
            or len(rows) != source_case["activity"]["attempted_decisions"]
            or len(rows) != source_case["activity"]["completed_transitions"] + 1
        ):
            raise ValueError("Saved public failure capture differs from its inspected source case")
        for index, row in enumerate(rows):
            _exact_keys(
                row, {"observation", "legal_actions", "selected_action_id"}, "public capture row"
            )
            obs, actions = _observation(row["observation"]), _actions(row["legal_actions"])
            representation = build_model_input(candidate.ruleset, obs, actions)
            if index < len(rows) - 1:
                if row["selected_action_id"] not in {a.action_id for a in actions}:
                    raise ValueError("Captured prefix action is outside its public menu")
            else:
                vector = obs.public_state["observation_vector"]
                if (
                    row["selected_action_id"] is not None
                    or vector[183] not in {1, 13}
                    or vector[183] != entry["selection_kind"]
                    or vector[184] != entry["visible_choices"]
                    or len(actions) != entry["legal_action_count"]
                ):
                    raise ValueError("Captured failure is not the specified public discard menu")
                bind_public_combat(representation, layout)
        transitions += source_case["activity"]["completed_transitions"]
    if collection["transitions"] != transitions:
        raise ValueError("Captured diagnostic transition accounting differs")
    engine = _safe_child(root, d["engine_source_root"])
    for relative, digest in d["engine_source_sha256"].items():
        if hashlib.sha256(_safe_child(engine, relative).read_bytes()).hexdigest() != digest:
            raise ValueError("Pinned public selection semantics source differs")
    return NeuralSelectionCompatibilityPolicy(candidate, layout)
