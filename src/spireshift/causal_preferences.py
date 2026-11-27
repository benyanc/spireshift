from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spireshift.combat_search_intervention import (
    CombatSearchInterventionSpec,
    load_combat_search_interventions,
)
from spireshift.core.manifest import manifest_identifier
from spireshift.models import _artifact_float
from spireshift.splits import SplitManifest, SplitName

CAUSAL_PREFERENCE_SET_SCHEMA_VERSION = "production-causal-preference-set-v1"


@dataclass(frozen=True, slots=True)
class CausalPreferenceRecord:
    preference: dict[str, Any]
    source_observation: dict[str, Any]
    candidate_action_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CausalPreferenceEvidence:
    document: dict[str, Any]
    records: tuple[CausalPreferenceRecord, ...]


def freeze_causal_preferences(
    *,
    intervention_report_path: Path,
    intervention_spec: CombatSearchInterventionSpec,
    split_manifest: SplitManifest,
) -> dict[str, Any]:
    report = load_combat_search_interventions(
        intervention_report_path,
        spec=intervention_spec,
        split_manifest=split_manifest,
    )
    root = intervention_report_path.expanduser().resolve().parent
    preferences: list[dict[str, Any]] = []
    for raw_reference in _list(report.get("cases"), "intervention case references"):
        reference = _mapping(raw_reference, "intervention case reference")
        case_path = _safe_child(root, _string(reference.get("path"), "intervention case path"))
        case = _load_object(case_path, "intervention case")
        seed = _integer(case.get("seed"), "intervention seed")
        for ordinal, raw_intervention in enumerate(
            _list(case.get("interventions"), "interventions")
        ):
            intervention = _mapping(raw_intervention, "intervention")
            if intervention.get("status") != "completed":
                continue
            label = _string(intervention.get("paired_label"), "paired label")
            if label not in {"beneficial", "harmful", "tied"}:
                continue
            base_action = _string(intervention.get("base_action_id"), "base action")
            search_action = _string(intervention.get("search_action_id"), "search action")
            if label == "beneficial":
                preferred, disfavored, probability, weight = (
                    search_action,
                    base_action,
                    1.0,
                    1.0,
                )
            elif label == "harmful":
                preferred, disfavored, probability, weight = (
                    base_action,
                    search_action,
                    0.0,
                    1.0,
                )
            else:
                preferred, disfavored, probability, weight = None, None, 0.5, 0.1
            preference_body = {
                "seed": seed,
                "intervention_ordinal": ordinal,
                "source_case_id": _string(case.get("case_id"), "intervention case ID"),
                "decision_index": _integer(intervention.get("decision_index"), "decision index"),
                "source_state_hash": _string(
                    intervention.get("source_state_hash"), "source state hash"
                ),
                "source_floor": intervention.get("source_floor"),
                "paired_label": label,
                "base_action_id": base_action,
                "search_action_id": search_action,
                "preferred_action_id": preferred,
                "disfavored_action_id": disfavored,
                "search_over_base_probability": probability,
                "training_weight": weight,
                "search_advantage": _artifact_float(
                    _number(intervention.get("search_advantage"), "search advantage")
                ),
                "maximum_floor_difference": intervention.get("maximum_floor_difference"),
                "victory_difference": intervention.get("victory_difference"),
            }
            preferences.append(
                {
                    **preference_body,
                    "preference_id": manifest_identifier(preference_body),
                }
            )
    preferences.sort(
        key=lambda item: (
            int(item["seed"]),
            int(item["decision_index"]),
            int(item["intervention_ordinal"]),
        )
    )
    labels = Counter(str(item["paired_label"]) for item in preferences)
    body: dict[str, Any] = {
        "schema_version": CAUSAL_PREFERENCE_SET_SCHEMA_VERSION,
        "intervention_spec_id": intervention_spec.spec_id,
        "intervention_report_id": report["report_id"],
        "source_model_id": report["model_id"],
        "source_training_report_id": report["training_report_id"],
        "split_manifest_id": split_manifest.manifest_id,
        "ruleset_manifest_id": split_manifest.ruleset_manifest_id,
        "objective_id": split_manifest.objective_id,
        "partition": SplitName.TRAIN.value,
        "preferences": preferences,
        "summary": {
            "preferences": len(preferences),
            "unique_runs": len({int(item["seed"]) for item in preferences}),
            "beneficial": labels["beneficial"],
            "harmful": labels["harmful"],
            "tied": labels["tied"],
            "effective_training_weight": _artifact_float(
                sum(float(item["training_weight"]) for item in preferences)
            ),
        },
        "claim_scope": "verified_train_only_single_intervention_preferences",
    }
    return {**body, "preference_set_id": manifest_identifier(body)}


def load_causal_preference_evidence(
    preference_path: Path,
    *,
    intervention_report_path: Path,
    intervention_spec: CombatSearchInterventionSpec,
    split_manifest: SplitManifest,
) -> CausalPreferenceEvidence:
    document = _load_object(preference_path, "causal preference set")
    expected = freeze_causal_preferences(
        intervention_report_path=intervention_report_path,
        intervention_spec=intervention_spec,
        split_manifest=split_manifest,
    )
    if document != expected:
        raise ValueError("Causal preference set differs from verified intervention evidence")

    preferences = {
        (
            _integer(item.get("seed"), "preference seed"),
            _integer(item.get("intervention_ordinal"), "intervention ordinal"),
        ): item
        for item in (
            _mapping(value, "causal preference")
            for value in _list(document.get("preferences"), "causal preferences")
        )
    }
    report = load_combat_search_interventions(
        intervention_report_path,
        spec=intervention_spec,
        split_manifest=split_manifest,
    )
    root = intervention_report_path.expanduser().resolve().parent
    records: list[CausalPreferenceRecord] = []
    for raw_reference in _list(report.get("cases"), "intervention case references"):
        reference = _mapping(raw_reference, "intervention case reference")
        case = _load_object(
            _safe_child(root, _string(reference.get("path"), "intervention case path")),
            "intervention case",
        )
        seed = _integer(case.get("seed"), "intervention seed")
        for ordinal, raw_intervention in enumerate(
            _list(case.get("interventions"), "interventions")
        ):
            preference = preferences.get((seed, ordinal))
            if preference is None:
                continue
            intervention = _mapping(raw_intervention, "intervention")
            source_observation = _mapping(
                intervention.get("source_observation"), "source observation"
            )
            candidates = tuple(
                _string(
                    _mapping(value, "intervention candidate").get("action_id"),
                    "candidate action ID",
                )
                for value in _list(intervention.get("candidates"), "intervention candidates")
            )
            records.append(
                CausalPreferenceRecord(
                    preference=dict(preference),
                    source_observation=dict(source_observation),
                    candidate_action_ids=candidates,
                )
            )
    records.sort(
        key=lambda item: (
            int(item.preference["seed"]),
            int(item.preference["decision_index"]),
            int(item.preference["intervention_ordinal"]),
        )
    )
    if len(records) != len(preferences):
        raise ValueError("Causal preference source observations are incomplete")
    return CausalPreferenceEvidence(document=document, records=tuple(records))


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load {label} {path}: {error}") from error
    return _mapping(value, label)


def _safe_child(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if root not in path.parents:
        raise ValueError("Intervention case escapes its report root")
    return path


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an object")
    return value


def _list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    return value


def _number(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    return float(value)
