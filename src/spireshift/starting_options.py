from __future__ import annotations

import copy
import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from spireshift.core.manifest import manifest_identifier
from spireshift.models import (
    _dot,
    _exact_keys,
    _integer,
    _list,
    _mapping,
    _weights_as_list,
    _weights_from_list,
)
from spireshift.representations import (
    CompositionalModelInput,
    FeatureValueType,
    ScalarFeature,
)

if TYPE_CHECKING:
    from spireshift.trajectory_policy import TrajectoryPolicyConfig

ENCODER_ID = "starting-ancient-public-option-v1"
CONFIG_SCHEMA = "starting-option-policy-training-config-v1"
EVIDENCE_CONFIG_SCHEMA = "starting-option-policy-training-config-v2"
HEAD_SCHEMA = "starting-option-policy-residual-v1"
CHECKPOINT_SCHEMA = "production-model-checkpoint-v7"
REPORT_SCHEMA = "production-model-training-report-v7"
MODEL_TYPE = "sparse-anchored-starting-option-residual-v1"


@dataclass(frozen=True, slots=True)
class StartingOptionConfig:
    document: dict[str, Any]

    @classmethod
    def from_mapping(cls, value: object) -> StartingOptionConfig:
        from spireshift.trajectory_policy import TrajectoryPolicyConfig

        doc = copy.deepcopy(_mapping(value, "starting option training config"))
        recipe_field = (
            "evidence_recipe"
            if doc.get("schema_version") == EVIDENCE_CONFIG_SCHEMA
            else "trajectory_recipe"
        )
        _exact_keys(
            doc,
            {"schema_version", "config_id", "encoder_id", "dimension", recipe_field},
            "starting option training config",
        )
        if doc["config_id"] != manifest_identifier(
            {k: v for k, v in doc.items() if k != "config_id"}
        ):
            raise ValueError("Starting option config identity mismatch")
        if (
            doc["schema_version"] not in {CONFIG_SCHEMA, EVIDENCE_CONFIG_SCHEMA}
            or doc["encoder_id"] != ENCODER_ID
        ):
            raise ValueError("Unsupported starting option schema or encoder")
        if not 128 <= _integer(doc["dimension"], "residual dimension") <= 65536:
            raise ValueError("Starting option residual dimension must be in [128, 65536]")
        if recipe_field == "evidence_recipe":
            from spireshift.starting_evidence_training import StartingEvidencePolicyConfig

            StartingEvidencePolicyConfig.from_mapping(doc[recipe_field])
        else:
            TrajectoryPolicyConfig.from_mapping(doc[recipe_field])
        return cls(doc)

    @property
    def recipe(self) -> TrajectoryPolicyConfig:
        from spireshift.trajectory_policy import TrajectoryPolicyConfig

        if self.document["schema_version"] == EVIDENCE_CONFIG_SCHEMA:
            from spireshift.starting_evidence_training import StartingEvidencePolicyConfig

            return StartingEvidencePolicyConfig.from_mapping(self.document["evidence_recipe"])
        return TrajectoryPolicyConfig.from_mapping(self.document["trajectory_recipe"])


def load_starting_option_config(path: Path) -> StartingOptionConfig:
    return StartingOptionConfig.from_mapping(json.loads(path.read_text(encoding="utf-8")))


def _number(feature: ScalarFeature, label: str) -> float:
    if feature.value_type is not FeatureValueType.NUMERIC or feature.numeric_value is None:
        raise ValueError(f"Starting option {label} must be numeric")
    if not math.isfinite(feature.numeric_value):
        raise ValueError(f"Starting option {label} must be finite")
    return feature.numeric_value


def _identifier(feature: ScalarFeature, label: str, *, zero: bool = False) -> int:
    number = _number(feature, label)
    if not number.is_integer() or number < (0 if zero else 1):
        raise ValueError(f"Starting option {label} must be a positive categorical ID")
    return int(number)


def _scalars(
    features: tuple[ScalarFeature, ...],
) -> dict[tuple[tuple[str, ...], tuple[int, ...]], ScalarFeature]:
    result = {}
    for item in features:
        key = item.path, item.indices
        if key in result:
            raise ValueError("Starting option public scalar is duplicated")
        result[key] = item
    return result


def starting_option_ids(representation: CompositionalModelInput) -> tuple[int, ...] | None:
    """Bind execution indices to public IDs; never use the index as a learned feature."""
    phases = []
    for candidate in representation.candidates:
        fields = _scalars(candidate.features)
        phase = fields.get((("phase",), ()))
        phases.append(None if phase is None else phase.categorical_value)
    ancient = [
        phase == "ancient"
        or candidate.action_kind == "evangambit_ancient"
        or candidate.source_action_id.startswith("evangambit:ancient:")
        for phase, candidate in zip(phases, representation.candidates, strict=True)
    ]
    if not any(ancient):
        return None
    if not all(phase == "ancient" for phase in phases) or representation.decision_type != "event":
        raise ValueError("Starting option candidate phases are misaligned")
    fields = _scalars(representation.global_features + representation.persistent_resources)
    floor_feature = fields.get((("floor",), ()))
    if floor_feature is None:
        raise ValueError("Starting option public floor is missing")
    floor = _number(floor_feature, "floor")
    if not floor.is_integer() or floor < 1:
        raise ValueError("Starting option public floor is invalid")
    if floor != 1 or len(representation.candidates) < 2:
        return None  # Later Ancients and forced proceed actions keep the parent policy.
    options = {
        indices[0]: _identifier(feature, "visible option ID")
        for (path, indices), feature in fields.items()
        if path == ("neow_options",) and len(indices) == 1
    }
    if sorted(options) != [0, 1, 2]:
        raise ValueError("Starting option menu must contain three visible IDs")
    selected = []
    indices_seen = set()
    for candidate in representation.candidates:
        fields = _scalars(candidate.features)
        index_feature = fields.get((("action_index",), ()))
        if index_feature is None:
            raise ValueError("Starting option action index is missing")
        index = _identifier(index_feature, "action index", zero=True)
        if (
            index not in options
            or index in indices_seen
            or candidate.action_kind != "evangambit_ancient"
            or candidate.source_action_id != f"evangambit:ancient:{index}"
            or set(fields) != {(("phase",), ()), (("action_index",), ())}
        ):
            raise ValueError("Starting option public option/action alignment differs")
        indices_seen.add(index)
        selected.append(options[index])
    return tuple(selected)


def _context(representation: CompositionalModelInput) -> dict[str, float]:
    fields = _scalars(representation.global_features + representation.persistent_resources)

    def scalar(name: str) -> ScalarFeature:
        value = fields.get(((name,), ()))
        if value is None:
            raise ValueError(f"Starting option public {name} is missing")
        return value

    act = scalar("act")
    if act.value_type is not FeatureValueType.CATEGORICAL or not act.categorical_value:
        raise ValueError("Starting option act must be categorical")
    hp, maximum = _number(scalar("player_hp"), "HP"), _number(scalar("player_max_hp"), "max HP")
    gold = _number(scalar("gold"), "gold")
    if not 0 <= hp <= maximum or maximum <= 0 or gold < 0:
        raise ValueError("Starting option public resources are invalid")
    result = {
        "bias": 1.0,
        f"act:{act.categorical_value}": 1.0,
        "hp_fraction": hp / maximum,
        "max_hp_scaled": min(maximum / 100, 2.0),
        "gold_log_scaled": min(math.log1p(gold) / math.log1p(1000), 1.0),
    }
    deck: Counter[str] = Counter()
    relics: Counter[str] = Counter()
    for entity in representation.entities:
        values = _scalars(entity.features)
        if entity.path == ("deck",):
            identity = values.get((("deck", "card_id"), entity.indices))
            upgrade = values.get((("deck", "upgraded"), entity.indices))
            if (
                identity is None
                or upgrade is None
                or upgrade.value_type is not FeatureValueType.BOOLEAN
            ):
                raise ValueError("Starting option public deck identity/upgrade is missing")
            card_id = _identifier(identity, "card ID")
            deck[f"card:{card_id}:upgraded:{int(bool(upgrade.boolean_value))}"] += 1
        elif entity.path == ("relic_slots",):
            identity = values.get((("relic_slots", "relic_id"), entity.indices))
            used = values.get((("relic_slots", "used_up"), entity.indices))
            if identity is None or used is None or used.value_type is not FeatureValueType.BOOLEAN:
                raise ValueError("Starting option public relic identity/status is missing")
            relic_id = _identifier(identity, "relic ID", zero=True)
            if relic_id:
                relics[f"relic:{relic_id}:used:{int(bool(used.boolean_value))}"] += 1
    if not any(entity.path == ("relic_slots",) for entity in representation.entities):
        for (path, _), feature in fields.items():
            if path == ("relics",):
                relic_id = _identifier(feature, "relic ID", zero=True)
                if relic_id:
                    relics[f"relic:{relic_id}:used:0"] += 1
    size = sum(deck.values())
    result["deck_size_scaled"] = min(size / 100, 1.0)
    result.update({key: count / max(size, 1) for key, count in sorted(deck.items())})
    result.update({key: min(count, 10) / 10 for key, count in sorted(relics.items())})
    return result


@dataclass(slots=True)
class StartingOptionHead:
    dimension: int
    known_option_ids: tuple[int, ...]
    weights: dict[int, float] = field(default_factory=dict)

    def features(self, representation: CompositionalModelInput) -> tuple[dict[int, float], ...]:
        options = starting_option_ids(representation)
        if options is None:
            return tuple({} for _ in representation.candidates)
        context = _context(representation)
        known = set(self.known_option_ids)
        result = []
        for identity in options:
            # Unseen IDs share an explicit category, never a magnitude or menu-position feature.
            category = str(identity) if identity in known else "unknown"
            features: dict[int, float] = {}
            for key, value in context.items():
                token = json.dumps(
                    [ENCODER_ID, "ancient_option_id", category, key], separators=(",", ":")
                )
                digest = hashlib.sha256(token.encode()).digest()
                index = int.from_bytes(digest[:8], "big") % self.dimension
                sign = 1.0 if digest[8] & 1 else -1.0
                features[index] = features.get(index, 0.0) + sign * value
            result.append({index: value for index, value in sorted(features.items()) if value})
        return tuple(result)

    def scores(self, representation: CompositionalModelInput) -> tuple[float, ...]:
        return tuple(_dot(self.weights, candidate) for candidate in self.features(representation))

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": HEAD_SCHEMA,
            "encoder_id": ENCODER_ID,
            "dimension": self.dimension,
            "known_option_ids": list(self.known_option_ids),
            "weights": _weights_as_list(self.weights),
        }

    @classmethod
    def from_mapping(cls, value: object) -> StartingOptionHead:
        doc = _mapping(value, "starting option residual")
        _exact_keys(
            doc,
            {"schema_version", "encoder_id", "dimension", "known_option_ids", "weights"},
            "starting option residual",
        )
        if doc["schema_version"] != HEAD_SCHEMA or doc["encoder_id"] != ENCODER_ID:
            raise ValueError("Unsupported starting option residual encoder")
        dimension = _integer(doc["dimension"], "residual dimension")
        if not 128 <= dimension <= 65536:
            raise ValueError("Invalid starting option residual dimension")
        ids = tuple(
            _integer(item, "known option ID")
            for item in _list(doc["known_option_ids"], "known option IDs")
        )
        if not ids or ids != tuple(sorted(set(ids))) or min(ids) <= 0:
            raise ValueError("Known option IDs must be positive, unique and sorted")
        return cls(
            dimension, ids, _weights_from_list(doc["weights"], dimension, "residual weights")
        )


def option_coverage(
    rows: tuple[tuple[int, CompositionalModelInput], ...], head: StartingOptionHead
) -> dict[str, Any]:
    runs = set()
    ids: list[int] = []
    states = 0
    for seed, representation in rows:
        options = starting_option_ids(representation)
        if options is not None:
            head.features(representation)  # Validate all visible context even before optimization.
            states += 1
            runs.add(seed)
            ids.extend(options)
    unknown = sorted(set(ids) - set(head.known_option_ids))
    return {
        "records": len(rows),
        "scoped_records": states,
        "scoped_complete_runs": len(runs),
        "candidate_options": len(ids),
        "unique_option_ids": sorted(set(ids)),
        "unknown_candidate_options": sum(item in unknown for item in ids),
        "unknown_option_ids": unknown,
    }
