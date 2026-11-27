"""A separately versioned player that binds visible amounts to their owners.

The v2 encoder pools the identity and value fields of list items independently.
That loses status/amount, relic/counter and card/upgrade relationships before
the network sees them. Keep the v2 public bindings and numerical architecture,
but give each visible entity its own semantic feature prefix. Old models and
their experiment implementations are deliberately left untouched.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.types import LegalAction, Observation
from spireshift.full_run_features import FullRunInput
from spireshift.full_run_policy import FullRunDecision, score_features
from spireshift.full_run_public_policy import (
    DIRECT_FEATURES,
    PublicFullRunModel,
    initial_public_full_run_model,
    public_full_run_input,
)

ENCODER_ID = "public-full-run-entity-bound-choices-v3"
SCHEMA = "unified-full-run-relational-policy-v3"
ENTITY_KEYS = ("card_id", "status_id", "relic_id", "enemy_id", "potion_id")


def relational_tokens(value: object, prefix: str, output: dict[str, float]) -> None:
    """Pool unordered visible objects, keeping each object's properties together.

    Positions are only retained where the public object itself declares one,
    e.g. an enemy target. Card list order never enters the policy. Scalar tuples
    retain their documented public layout, rather than mixing their columns.
    No action handle, run seed, observation hash or hidden engine value enters.
    """
    if isinstance(value, dict):
        for key, item in sorted(value.items()):
            relational_tokens(item, f"{prefix}/{key}", output)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if isinstance(item, dict):
                identity = next((key for key in ENTITY_KEYS if key in item), None)
                if identity is None:
                    # Preserve correlations even for an anonymous visible object.
                    # This is content, never an invented quality or hidden locator.
                    key = json.dumps(item, sort_keys=True, separators=(",", ":"))
                    item_prefix = f"{prefix}/object={key}"
                else:
                    qualifiers = {identity: item[identity]}
                    for name in ("upgraded", "enchantment_id", "position"):
                        if name in item:
                            qualifiers[name] = item[name]
                    key = json.dumps(qualifiers, sort_keys=True, separators=(",", ":"))
                    item_prefix = f"{prefix}/entity={key}"
                output[f"{item_prefix}/present"] = output.get(f"{item_prefix}/present", 0) + 1
            else:
                item_prefix = f"{prefix}/column={index}"
            relational_tokens(item, item_prefix, output)
        output[f"{prefix}/count"] = math.log1p(len(value)) / 4
    elif isinstance(value, (bool, str)) or prefix.endswith(("_id", "/position", "/node_type")):
        token = f"{prefix}={value}"
        output[token] = output.get(token, 0) + 1
    elif isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError("Nonfinite relational public feature")
        output[prefix] = output.get(prefix, 0) + math.asinh(value) / 5
    elif value is None:
        output[f"{prefix}=absent"] = 1
    else:
        raise ValueError("Unsupported relational public feature type")


def hashed_tokens(
    tokens: dict[str, float], dimension: int, encoder: str, offset: int = 0
) -> dict[int, float]:
    if not 0 <= offset < dimension:
        raise ValueError("Invalid relational hash feature extent")
    values: dict[int, float] = {}
    for token, amount in sorted(tokens.items()):
        digest = hashlib.sha256(f"{encoder}|{token}".encode()).digest()
        index = offset + int.from_bytes(digest[:8], "big") % (dimension - offset)
        values[index] = values.get(index, 0) + (1 if digest[8] & 1 else -1) * amount
    return {i: max(-5.0, min(5.0, v)) for i, v in sorted(values.items()) if v}


def relational_full_run_input(
    ruleset: RulesetIdentity,
    observation: Observation,
    actions: tuple[LegalAction, ...],
    catalog: dict[str, dict[str, Any]],
    dimension: int,
) -> FullRunInput:
    # All public/patch checks, complete menus, ordinary targeting and printed
    # properties come from the frozen admitted v2 binder. Only encoding changes.
    base = public_full_run_input(ruleset, observation, actions, catalog, dimension)
    shared: dict[str, float] = {}
    relational_tokens(base.context, "state", shared)
    rows = []
    for binding, old in zip(base.bindings, base.vectors, strict=True):
        # The binder retains raw descriptors; v2 has already validated/printed
        # candidate properties. Obtain the printed contents without engine calls.
        from spireshift.full_run_public_policy import _printed

        printed = _printed(binding, catalog)
        if binding["kind"] == "confirm_bundle":
            printed.pop("selected_bundle")
            printed["selected_cards"] = base.context["bundle_selection"]["selected_cards"]
        tokens = dict(shared)
        relational_tokens(printed, "candidate", tokens)
        direct = {i: v for i, v in old.items() if i < len(DIRECT_FEATURES)}
        rows.append(
            {**direct, **hashed_tokens(tokens, dimension, ENCODER_ID, len(DIRECT_FEATURES))}
        )
    return FullRunInput(
        base.representation_hash, base.source_action_ids, base.bindings, tuple(rows), base.context
    )


class RelationalFullRunModel(PublicFullRunModel):
    def body_dict(self) -> dict[str, Any]:
        return {**super().body_dict(), "schema_version": SCHEMA, "encoder_id": ENCODER_ID}

    def with_genome(self, genome: Sequence[float]) -> RelationalFullRunModel:
        return cast(RelationalFullRunModel, super().with_genome(genome))

    @classmethod
    def from_mapping(cls, value: object) -> RelationalFullRunModel:
        from spireshift.full_run_public_policy import ENCODER_ID as V2_ENCODER
        from spireshift.full_run_public_policy import SCHEMA as V2_SCHEMA

        if (
            not isinstance(value, dict)
            or value.get("schema_version") != SCHEMA
            or value.get("encoder_id") != ENCODER_ID
        ):
            raise ValueError("Relational player requires its separate v3 model format")
        body = {k: v for k, v in value.items() if k != "model_id"}
        if value.get("model_id") != manifest_identifier(body):
            raise ValueError("Relational full-run model identity differs")
        numerical = {**body, "schema_version": V2_SCHEMA, "encoder_id": V2_ENCODER}
        model = PublicFullRunModel.from_mapping(
            {**numerical, "model_id": manifest_identifier(numerical)}
        )
        return cls(
            model.ruleset_manifest_id,
            model.patch_id,
            model.dimension,
            model.hidden_units,
            model.catalog,
            model.card_source_sha256,
            model.genome,
        )


def initial_relational_model(
    ruleset: RulesetIdentity,
    catalog: dict[str, dict[str, Any]],
    card_source_sha256: str,
    *,
    dimension: int = 256,
    hidden_units: int = 16,
    initialization_seed: int = 0,
) -> RelationalFullRunModel:
    model = initial_public_full_run_model(
        ruleset,
        catalog,
        card_source_sha256,
        dimension=dimension,
        hidden_units=hidden_units,
        initialization_seed=initialization_seed,
    )
    return RelationalFullRunModel(
        model.ruleset_manifest_id,
        model.patch_id,
        model.dimension,
        model.hidden_units,
        model.catalog,
        model.card_source_sha256,
        model.genome,
    )


def load_relational_model(path: Path) -> RelationalFullRunModel:
    return RelationalFullRunModel.from_mapping(json.loads(path.read_text()))


class RelationalFullRunPolicy:
    def __init__(self, ruleset: RulesetIdentity, model: RelationalFullRunModel) -> None:
        if model.ruleset_manifest_id != ruleset.manifest_id or model.patch_id != ruleset.patch_id:
            raise ValueError("Relational player belongs to another ruleset")
        self.ruleset, self.model = ruleset, model
        self.model_id, self.policy_id = model.model_id, f"relational-full-run-v3:{model.model_id}"

    def predict(
        self, observation: Observation, legal_actions: Sequence[LegalAction]
    ) -> FullRunDecision:
        actions = tuple(legal_actions)
        if not actions:
            raise ValueError("Relational player requires every supplied legal candidate")
        inputs = relational_full_run_input(
            self.ruleset, observation, actions, self.model.catalog, self.model.dimension
        )
        logits = score_features(self.model, inputs.vectors)
        maximum = max(logits)
        weights = tuple(math.exp(v - maximum) for v in logits)
        probabilities = tuple(v / math.fsum(weights) for v in weights)
        index = max(range(len(actions)), key=lambda i: (logits[i], -i))
        return FullRunDecision(inputs, logits, probabilities, index, actions[index])

    def choose_action(
        self, observation: Observation, legal_actions: Sequence[LegalAction]
    ) -> LegalAction:
        return self.predict(observation, legal_actions).selected_action
