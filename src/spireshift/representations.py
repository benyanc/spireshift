from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.types import LegalAction, Observation

MODEL_INPUT_SCHEMA_VERSION = "model-input-v1"
VECTORIZED_INPUT_SCHEMA_VERSION = "vectorized-model-input-v1"
ENCODER_ID = "mechanics-compositional-v1"
VECTORIZER_ID = "signed-sha256-feature-hash-v1"
DEFAULT_VECTOR_DIMENSION = 4096

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_WORD = re.compile(r"[^a-zA-Z0-9]+")
_PRIVILEGED_SEGMENTS = {
    "draw_order",
    "draw_pile_order",
    "future",
    "future_reward",
    "hidden",
    "is_hidden",
    "next_reward",
    "random_seed",
    "rng",
    "rng_state",
    "seed",
}
_ROOT_ENTITY_KEYS = {"player"}
_ENTITY_NAMES = {
    "bundles": "bundle",
    "cards": "card",
    "cells": "cell",
    "characters": "character",
    "clickable_cells": "cell",
    "enemies": "enemy",
    "deck": "card",
    "hand": "card",
    "items": "item",
    "next_options": "path_option",
    "options": "option",
    "potions": "potion",
    "relics": "relic",
    "rewards": "reward",
    "statuses": "status",
}
_RESOURCE_SCALARS = {"gold", "hp", "keys", "max_hp"}
_RESOURCE_COLLECTIONS = {"deck", "potions", "relics"}
_LOCATOR_SEGMENTS = {
    "column",
    "index",
    "row",
    "slot",
    "target_index",
    "x",
    "y",
}
_PROGRESSION_SEGMENTS = {"act", "ascension", "floor", "room", "room_type"}
_STATUS_SEGMENTS = {
    "intent",
    "state_type",
    "status",
    "target_type",
    "terminal",
    "victory",
}
_IDENTITY_SEGMENTS = {"id", "name", "option"}


class FeatureSemantic(StrEnum):
    MECHANIC = "mechanic"
    RESOURCE = "persistent_resource"
    STATUS = "status"
    CAPABILITY = "capability"
    LOCATOR = "locator"
    PROGRESSION = "progression"
    IDENTITY = "identity"


class FeatureValueType(StrEnum):
    BOOLEAN = "boolean"
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    NULL = "null"


@dataclass(frozen=True, slots=True)
class ScalarFeature:
    path: tuple[str, ...]
    indices: tuple[int, ...]
    semantic: FeatureSemantic
    value_type: FeatureValueType
    numeric_value: float | None = None
    categorical_value: str | None = None
    boolean_value: bool | None = None

    @classmethod
    def from_value(
        cls,
        *,
        path: tuple[str, ...],
        indices: tuple[int, ...],
        value: object,
    ) -> ScalarFeature:
        semantic = _semantic(path)
        if value is None:
            return cls(path, indices, semantic, FeatureValueType.NULL)
        if isinstance(value, bool):
            return cls(
                path,
                indices,
                semantic,
                FeatureValueType.BOOLEAN,
                boolean_value=value,
            )
        if isinstance(value, (int, float)):
            numeric = float(value)
            if not math.isfinite(numeric):
                raise ValueError(f"Feature {'.'.join(path)} must be finite")
            return cls(
                path,
                indices,
                semantic,
                FeatureValueType.NUMERIC,
                numeric_value=numeric,
            )
        if isinstance(value, str):
            return cls(
                path,
                indices,
                semantic,
                FeatureValueType.CATEGORICAL,
                categorical_value=value,
            )
        raise ValueError(
            f"Feature {'.'.join(path)} has unsupported value type {type(value).__name__}"
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "path": list(self.path),
            "indices": list(self.indices),
            "semantic": self.semantic.value,
            "value_type": self.value_type.value,
            "numeric_value": self.numeric_value,
            "categorical_value": self.categorical_value,
            "boolean_value": self.boolean_value,
        }


@dataclass(frozen=True, slots=True)
class EntityRepresentation:
    entity_type: str
    path: tuple[str, ...]
    indices: tuple[int, ...]
    features: tuple[ScalarFeature, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "entity_type": self.entity_type,
            "path": list(self.path),
            "indices": list(self.indices),
            "features": [feature.as_dict() for feature in self.features],
        }


@dataclass(frozen=True, slots=True)
class CandidateRepresentation:
    candidate_index: int
    source_action_id: str
    action_kind: str
    features: tuple[ScalarFeature, ...]

    def as_dict(self, *, include_source_id: bool = True) -> dict[str, object]:
        result: dict[str, object] = {
            "candidate_index": self.candidate_index,
            "action_kind": self.action_kind,
            "features": [feature.as_dict() for feature in self.features],
        }
        if include_source_id:
            result["source_action_id"] = self.source_action_id
        return result


@dataclass(frozen=True, slots=True)
class CompositionalModelInput:
    representation_hash: str
    ruleset_manifest_id: str
    patch_id: str
    observation_schema: str
    source_state_hash: str
    decision_type: str
    global_features: tuple[ScalarFeature, ...]
    persistent_resources: tuple[ScalarFeature, ...]
    entities: tuple[EntityRepresentation, ...]
    candidates: tuple[CandidateRepresentation, ...]
    action_mask: tuple[bool, ...]

    def body_dict(self) -> dict[str, object]:
        return {
            "schema_version": MODEL_INPUT_SCHEMA_VERSION,
            "encoder_id": ENCODER_ID,
            "ruleset_manifest_id": self.ruleset_manifest_id,
            "patch_id": self.patch_id,
            "observation_schema": self.observation_schema,
            "source_state_hash": self.source_state_hash,
            "decision_type": self.decision_type,
            "state": {
                "global_features": [feature.as_dict() for feature in self.global_features],
                "persistent_resources": [
                    feature.as_dict() for feature in self.persistent_resources
                ],
                "entities": [entity.as_dict() for entity in self.entities],
            },
            "candidates": [candidate.as_dict() for candidate in self.candidates],
            "action_mask": list(self.action_mask),
        }

    def as_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "representation_hash": self.representation_hash}

    def model_dict(self) -> dict[str, object]:
        """Return only values that may enter a model; source IDs and hashes are excluded."""

        return {
            "encoder_id": ENCODER_ID,
            "decision_type": self.decision_type,
            "state": {
                "global_features": [feature.as_dict() for feature in self.global_features],
                "persistent_resources": [
                    feature.as_dict() for feature in self.persistent_resources
                ],
                "entities": [entity.as_dict() for entity in self.entities],
            },
            "candidates": [
                candidate.as_dict(include_source_id=False) for candidate in self.candidates
            ],
            "action_mask": list(self.action_mask),
        }

    def model_feature_digest(self) -> str:
        return hashlib.sha256(_canonical_json(self.model_dict())).hexdigest()


@dataclass(frozen=True, slots=True)
class SparseEntry:
    index: int
    value: float

    def as_dict(self) -> dict[str, object]:
        return {"index": self.index, "value": self.value}


@dataclass(frozen=True, slots=True)
class VectorizedModelInput:
    dimension: int
    state: tuple[SparseEntry, ...]
    candidates: tuple[tuple[SparseEntry, ...], ...]
    action_mask: tuple[bool, ...]
    source_action_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": VECTORIZED_INPUT_SCHEMA_VERSION,
            "vectorizer_id": VECTORIZER_ID,
            "dimension": self.dimension,
            "state": [entry.as_dict() for entry in self.state],
            "candidates": [
                [entry.as_dict() for entry in candidate] for candidate in self.candidates
            ],
            "action_mask": list(self.action_mask),
            "source_action_ids": list(self.source_action_ids),
        }


@dataclass(slots=True)
class _EntityBuilder:
    entity_type: str
    path: tuple[str, ...]
    indices: tuple[int, ...]
    features: list[ScalarFeature]


def build_model_input(
    ruleset: RulesetIdentity,
    observation: Observation,
    legal_actions: Sequence[LegalAction],
) -> CompositionalModelInput:
    if observation.patch_id != ruleset.patch_id:
        raise ValueError("Observation patch does not match representation ruleset")
    if observation.schema_version != ruleset.interface.observation_schema:
        raise ValueError("Observation schema does not match representation ruleset")
    expected_state_hash = hashlib.sha256(_canonical_json(observation.public_state)).hexdigest()
    if observation.state_hash != expected_state_hash:
        raise ValueError("Observation state hash does not match its public state")
    actions = tuple(legal_actions)
    action_ids = [action.action_id for action in actions]
    if len(action_ids) != len(set(action_ids)):
        raise ValueError("Legal action IDs must be unique")

    global_features, resources, entity_builders = _extract_state(observation.public_state)
    entities = tuple(
        EntityRepresentation(
            entity_type=entity.entity_type,
            path=entity.path,
            indices=entity.indices,
            features=tuple(entity.features),
        )
        for entity in entity_builders
    )
    candidates = tuple(
        CandidateRepresentation(
            candidate_index=index,
            source_action_id=action.action_id,
            action_kind=_normalize_token(action.kind, "action kind"),
            features=tuple(_extract_candidate_features(action.payload)),
        )
        for index, action in enumerate(actions)
    )
    body = {
        "schema_version": MODEL_INPUT_SCHEMA_VERSION,
        "encoder_id": ENCODER_ID,
        "ruleset_manifest_id": ruleset.manifest_id,
        "patch_id": ruleset.patch_id,
        "observation_schema": observation.schema_version,
        "source_state_hash": observation.state_hash,
        "decision_type": observation.decision_type.value,
        "state": {
            "global_features": [feature.as_dict() for feature in global_features],
            "persistent_resources": [feature.as_dict() for feature in resources],
            "entities": [entity.as_dict() for entity in entities],
        },
        "candidates": [candidate.as_dict() for candidate in candidates],
        "action_mask": [True] * len(candidates),
    }
    return CompositionalModelInput(
        representation_hash=manifest_identifier(body),
        ruleset_manifest_id=ruleset.manifest_id,
        patch_id=ruleset.patch_id,
        observation_schema=observation.schema_version,
        source_state_hash=observation.state_hash,
        decision_type=observation.decision_type.value,
        global_features=tuple(global_features),
        persistent_resources=tuple(resources),
        entities=entities,
        candidates=candidates,
        action_mask=tuple(True for _ in candidates),
    )


def model_input_from_mapping(value: object) -> CompositionalModelInput:
    document = _representation_mapping(value, "model input")
    _require_representation_keys(
        document,
        {
            "schema_version",
            "encoder_id",
            "representation_hash",
            "ruleset_manifest_id",
            "patch_id",
            "observation_schema",
            "source_state_hash",
            "decision_type",
            "state",
            "candidates",
            "action_mask",
        },
        "model input",
    )
    if document.get("schema_version") != MODEL_INPUT_SCHEMA_VERSION:
        raise ValueError("Unsupported model-input schema")
    if document.get("encoder_id") != ENCODER_ID:
        raise ValueError("Unsupported model-input encoder")
    state = _representation_mapping(document.get("state"), "model input state")
    _require_representation_keys(
        state,
        {"global_features", "persistent_resources", "entities"},
        "model input state",
    )
    global_features = tuple(
        _feature_from_mapping(item, f"global_features[{index}]")
        for index, item in enumerate(
            _representation_list(state.get("global_features"), "global_features")
        )
    )
    resources = tuple(
        _feature_from_mapping(item, f"persistent_resources[{index}]")
        for index, item in enumerate(
            _representation_list(state.get("persistent_resources"), "persistent_resources")
        )
    )
    entities: list[EntityRepresentation] = []
    for index, raw_entity in enumerate(_representation_list(state.get("entities"), "entities")):
        label = f"entities[{index}]"
        entity = _representation_mapping(raw_entity, label)
        _require_representation_keys(entity, {"entity_type", "path", "indices", "features"}, label)
        entities.append(
            EntityRepresentation(
                entity_type=_representation_token(
                    entity.get("entity_type"), f"{label}.entity_type"
                ),
                path=_representation_path(entity.get("path"), f"{label}.path"),
                indices=_representation_indices(entity.get("indices"), f"{label}.indices"),
                features=tuple(
                    _feature_from_mapping(item, f"{label}.features[{feature_index}]")
                    for feature_index, item in enumerate(
                        _representation_list(entity.get("features"), f"{label}.features")
                    )
                ),
            )
        )
    candidates: list[CandidateRepresentation] = []
    for index, raw_candidate in enumerate(
        _representation_list(document.get("candidates"), "candidates")
    ):
        label = f"candidates[{index}]"
        candidate = _representation_mapping(raw_candidate, label)
        _require_representation_keys(
            candidate,
            {"candidate_index", "source_action_id", "action_kind", "features"},
            label,
        )
        candidate_index = _representation_integer(
            candidate.get("candidate_index"), f"{label}.candidate_index"
        )
        if candidate_index != index:
            raise ValueError("Model-input candidate indexes must be contiguous")
        candidates.append(
            CandidateRepresentation(
                candidate_index=candidate_index,
                source_action_id=_representation_string(
                    candidate.get("source_action_id"), f"{label}.source_action_id"
                ),
                action_kind=_representation_token(
                    candidate.get("action_kind"), f"{label}.action_kind"
                ),
                features=tuple(
                    _feature_from_mapping(item, f"{label}.features[{feature_index}]")
                    for feature_index, item in enumerate(
                        _representation_list(candidate.get("features"), f"{label}.features")
                    )
                ),
            )
        )
    source_action_ids = [candidate.source_action_id for candidate in candidates]
    if len(source_action_ids) != len(set(source_action_ids)):
        raise ValueError("Model-input source action IDs must be unique")
    raw_mask = _representation_list(document.get("action_mask"), "action_mask")
    if any(item is not True for item in raw_mask) or len(raw_mask) != len(candidates):
        raise ValueError("Model-input action mask must align with legal candidates")
    representation_hash = _representation_string(
        document.get("representation_hash"), "representation_hash"
    )
    body = {key: item for key, item in document.items() if key != "representation_hash"}
    expected_hash = manifest_identifier(body)
    if representation_hash != expected_hash:
        raise ValueError(
            f"Model-input representation hash mismatch: expected {expected_hash}, "
            f"got {representation_hash}"
        )
    return CompositionalModelInput(
        representation_hash=representation_hash,
        ruleset_manifest_id=_representation_string(
            document.get("ruleset_manifest_id"), "ruleset_manifest_id"
        ),
        patch_id=_representation_string(document.get("patch_id"), "patch_id"),
        observation_schema=_representation_string(
            document.get("observation_schema"), "observation_schema"
        ),
        source_state_hash=_representation_string(
            document.get("source_state_hash"), "source_state_hash"
        ),
        decision_type=_representation_token(document.get("decision_type"), "decision_type"),
        global_features=global_features,
        persistent_resources=resources,
        entities=tuple(entities),
        candidates=tuple(candidates),
        action_mask=tuple(True for _ in candidates),
    )


def vectorize_model_input(
    representation: CompositionalModelInput,
    *,
    dimension: int = DEFAULT_VECTOR_DIMENSION,
) -> VectorizedModelInput:
    if dimension < 64:
        raise ValueError("Vector dimension must be at least 64")
    state_values: dict[int, float] = {}
    _add_hashed(state_values, f"decision_type|{representation.decision_type}", 1.0, dimension)
    for feature in representation.global_features:
        _add_feature(state_values, "global", feature, dimension)
    for feature in representation.persistent_resources:
        _add_feature(state_values, "resource", feature, dimension)
    for entity in representation.entities:
        entity_scope = f"entity|{entity.entity_type}|{'.'.join(entity.path)}"
        _add_hashed(state_values, f"{entity_scope}|present", 1.0, dimension)
        for depth, index in enumerate(entity.indices):
            _add_hashed(
                state_values,
                f"{entity_scope}|position|{depth}",
                float(index),
                dimension,
            )
        for feature in entity.features:
            _add_feature(
                state_values,
                entity_scope,
                feature,
                dimension,
                position_offset=len(entity.indices),
            )

    candidate_vectors: list[tuple[SparseEntry, ...]] = []
    for candidate in representation.candidates:
        values: dict[int, float] = {}
        _add_hashed(values, f"action_kind|{candidate.action_kind}", 1.0, dimension)
        for feature in candidate.features:
            _add_feature(values, f"candidate|{candidate.action_kind}", feature, dimension)
        candidate_vectors.append(_sparse_entries(values))
    return VectorizedModelInput(
        dimension=dimension,
        state=_sparse_entries(state_values),
        candidates=tuple(candidate_vectors),
        action_mask=representation.action_mask,
        source_action_ids=tuple(
            candidate.source_action_id for candidate in representation.candidates
        ),
    )


def _extract_state(
    public_state: dict[str, Any],
) -> tuple[list[ScalarFeature], list[ScalarFeature], list[_EntityBuilder]]:
    global_features: list[ScalarFeature] = []
    resources: list[ScalarFeature] = []
    entities: list[_EntityBuilder] = []

    def add_scalar(
        *,
        path: tuple[str, ...],
        indices: tuple[int, ...],
        value: object,
        owner: _EntityBuilder | None,
    ) -> None:
        feature = ScalarFeature.from_value(path=path, indices=indices, value=value)
        if _is_persistent_resource(path):
            resources.append(replace(feature, semantic=FeatureSemantic.RESOURCE))
        if owner is not None:
            owner.features.append(feature)
        elif not _is_persistent_resource(path):
            global_features.append(feature)

    def walk(
        value: object,
        *,
        path: tuple[str, ...],
        indices: tuple[int, ...],
        owner: _EntityBuilder | None,
    ) -> None:
        if isinstance(value, dict):
            for raw_key in sorted(value):
                if not isinstance(raw_key, str):
                    raise ValueError("Public-state object keys must be strings")
                key = _normalize_token(raw_key, "public-state key")
                _reject_privileged(key, path)
                child = value[raw_key]
                child_path = (*path, key)
                if not path and key == "state_type":
                    continue
                if isinstance(child, dict) and not path and key in _ROOT_ENTITY_KEYS:
                    entity = _EntityBuilder(key, child_path, indices, [])
                    entities.append(entity)
                    walk(child, path=child_path, indices=indices, owner=entity)
                elif isinstance(child, list):
                    walk_list(
                        child,
                        path=child_path,
                        indices=indices,
                        owner=owner,
                    )
                else:
                    walk(child, path=child_path, indices=indices, owner=owner)
            return
        if isinstance(value, list):
            walk_list(value, path=path, indices=indices, owner=owner)
            return
        add_scalar(path=path, indices=indices, value=value, owner=owner)

    def walk_list(
        values: list[object],
        *,
        path: tuple[str, ...],
        indices: tuple[int, ...],
        owner: _EntityBuilder | None,
    ) -> None:
        entity_type = _entity_type(path[-1])
        for index, item in enumerate(values):
            item_indices = (*indices, index)
            if isinstance(item, dict):
                entity = _EntityBuilder(entity_type, path, item_indices, [])
                entities.append(entity)
                walk(item, path=path, indices=item_indices, owner=entity)
            else:
                walk(item, path=path, indices=item_indices, owner=owner)

    walk(public_state, path=(), indices=(), owner=None)
    return global_features, resources, entities


def _extract_candidate_features(payload: dict[str, Any]) -> list[ScalarFeature]:
    features: list[ScalarFeature] = []

    def walk(value: object, path: tuple[str, ...], indices: tuple[int, ...]) -> None:
        if isinstance(value, dict):
            for raw_key in sorted(value):
                if not isinstance(raw_key, str):
                    raise ValueError("Action payload keys must be strings")
                key = _normalize_token(raw_key, "action payload key")
                _reject_privileged(key, path)
                walk(value[raw_key], (*path, key), indices)
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, path, (*indices, index))
            return
        features.append(ScalarFeature.from_value(path=path, indices=indices, value=value))

    walk(payload, (), ())
    return features


def _semantic(path: tuple[str, ...]) -> FeatureSemantic:
    if not path:
        return FeatureSemantic.MECHANIC
    leaf = path[-1]
    if _is_direct_persistent_scalar(path):
        return FeatureSemantic.RESOURCE
    if (
        leaf in _LOCATOR_SEGMENTS
        or leaf == "target"
        or leaf.endswith("_index")
        or leaf.endswith("_slot")
    ):
        return FeatureSemantic.LOCATOR
    if leaf in _PROGRESSION_SEGMENTS:
        return FeatureSemantic.PROGRESSION
    if leaf in _STATUS_SEGMENTS or leaf.endswith("_status"):
        return FeatureSemantic.STATUS
    if (
        leaf.startswith("can_")
        or leaf.startswith("has_")
        or leaf.startswith("is_")
        or leaf in {"enabled", "locked", "revealed", "stocked"}
    ):
        return FeatureSemantic.CAPABILITY
    if leaf in _IDENTITY_SEGMENTS or leaf.endswith("_id") or leaf.endswith("_name"):
        return FeatureSemantic.IDENTITY
    return FeatureSemantic.MECHANIC


def _is_persistent_resource(path: tuple[str, ...]) -> bool:
    if _is_direct_persistent_scalar(path):
        return True
    return len(path) >= 2 and path[0] in {"player", "run"} and path[1] in _RESOURCE_COLLECTIONS


def _is_direct_persistent_scalar(path: tuple[str, ...]) -> bool:
    return len(path) >= 2 and path[0] in {"player", "run"} and path[-1] in _RESOURCE_SCALARS


def _entity_type(collection_name: str) -> str:
    explicit = _ENTITY_NAMES.get(collection_name)
    if explicit is not None:
        return explicit
    if collection_name.endswith("ies"):
        return f"{collection_name[:-3]}y"
    if collection_name.endswith("s") and len(collection_name) > 1:
        return collection_name[:-1]
    return collection_name


def _normalize_token(value: str, label: str) -> str:
    separated = _CAMEL_BOUNDARY.sub("_", value.strip())
    normalized = _NON_WORD.sub("_", separated).strip("_").casefold()
    if not normalized:
        raise ValueError(f"{label} must contain a letter or number")
    return normalized


def _reject_privileged(segment: str, parent_path: tuple[str, ...]) -> None:
    if (
        segment in _PRIVILEGED_SEGMENTS
        or segment.endswith("_seed")
        or segment.startswith("future_")
        or segment.startswith("rng_")
    ):
        location = ".".join((*parent_path, segment))
        raise ValueError(f"Privileged feature is forbidden: {location}")


def _add_feature(
    values: dict[int, float],
    scope: str,
    feature: ScalarFeature,
    dimension: int,
    *,
    position_offset: int = 0,
) -> None:
    path = ".".join(feature.path)
    base = f"{scope}|{feature.semantic.value}|{path}|{feature.value_type.value}"
    if feature.value_type is FeatureValueType.NUMERIC:
        assert feature.numeric_value is not None
        _add_hashed(values, f"{base}|present", 1.0, dimension)
        _add_hashed(values, base, feature.numeric_value, dimension)
    elif feature.value_type is FeatureValueType.CATEGORICAL:
        assert feature.categorical_value is not None
        _add_hashed(values, f"{base}|{feature.categorical_value}", 1.0, dimension)
    elif feature.value_type is FeatureValueType.BOOLEAN:
        assert feature.boolean_value is not None
        _add_hashed(values, f"{base}|{str(feature.boolean_value).casefold()}", 1.0, dimension)
    else:
        _add_hashed(values, f"{base}|null", 1.0, dimension)
    for depth, index in enumerate(feature.indices[position_offset:], start=position_offset):
        _add_hashed(values, f"{scope}|position|{path}|{depth}", float(index), dimension)


def _add_hashed(values: dict[int, float], token: str, value: float, dimension: int) -> None:
    digest = hashlib.sha256(token.encode()).digest()
    index = int.from_bytes(digest[:8], "big") % dimension
    sign = 1.0 if digest[8] & 1 == 0 else -1.0
    values[index] = values.get(index, 0.0) + sign * value


def _sparse_entries(values: dict[int, float]) -> tuple[SparseEntry, ...]:
    return tuple(
        SparseEntry(index, value) for index, value in sorted(values.items()) if value != 0.0
    )


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _feature_from_mapping(value: object, label: str) -> ScalarFeature:
    feature = _representation_mapping(value, label)
    _require_representation_keys(
        feature,
        {
            "path",
            "indices",
            "semantic",
            "value_type",
            "numeric_value",
            "categorical_value",
            "boolean_value",
        },
        label,
    )
    path = _representation_path(feature.get("path"), f"{label}.path")
    indices = _representation_indices(feature.get("indices"), f"{label}.indices")
    try:
        semantic = FeatureSemantic(
            _representation_string(feature.get("semantic"), f"{label}.semantic")
        )
        value_type = FeatureValueType(
            _representation_string(feature.get("value_type"), f"{label}.value_type")
        )
    except ValueError as error:
        raise ValueError(f"{label} has an unsupported semantic or value type") from error
    numeric = feature.get("numeric_value")
    categorical = feature.get("categorical_value")
    boolean = feature.get("boolean_value")
    if value_type is FeatureValueType.NUMERIC:
        if not isinstance(numeric, int | float) or isinstance(numeric, bool):
            raise ValueError(f"{label}.numeric_value must be numeric")
        numeric_value = float(numeric)
        if not math.isfinite(numeric_value):
            raise ValueError(f"{label}.numeric_value must be finite")
        if categorical is not None or boolean is not None:
            raise ValueError(f"{label} has values outside its declared numeric type")
        return ScalarFeature(path, indices, semantic, value_type, numeric_value=numeric_value)
    if value_type is FeatureValueType.CATEGORICAL:
        if not isinstance(categorical, str) or numeric is not None or boolean is not None:
            raise ValueError(f"{label} has values outside its declared categorical type")
        return ScalarFeature(path, indices, semantic, value_type, categorical_value=categorical)
    if value_type is FeatureValueType.BOOLEAN:
        if not isinstance(boolean, bool) or numeric is not None or categorical is not None:
            raise ValueError(f"{label} has values outside its declared boolean type")
        return ScalarFeature(path, indices, semantic, value_type, boolean_value=boolean)
    if numeric is not None or categorical is not None or boolean is not None:
        raise ValueError(f"{label} null feature carries a non-null value")
    return ScalarFeature(path, indices, semantic, value_type)


def _representation_mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    if any(not isinstance(key, str) for key in value):
        raise ValueError(f"{label} keys must be strings")
    return {str(key): item for key, item in value.items()}


def _representation_list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def _representation_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _representation_integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _representation_token(value: object, label: str) -> str:
    token = _representation_string(value, label)
    if _normalize_token(token, label) != token:
        raise ValueError(f"{label} must be normalized")
    return token


def _representation_path(value: object, label: str) -> tuple[str, ...]:
    items = _representation_list(value, label)
    if not items:
        raise ValueError(f"{label} must not be empty")
    return tuple(
        _representation_token(item, f"{label}[{index}]") for index, item in enumerate(items)
    )


def _representation_indices(value: object, label: str) -> tuple[int, ...]:
    return tuple(
        _representation_integer(item, f"{label}[{index}]")
        for index, item in enumerate(_representation_list(value, label))
    )


def _require_representation_keys(value: dict[str, object], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError(
            f"{label} fields differ: missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )
