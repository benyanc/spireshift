"""A zero-initialized named-input supplement and an equal-size hashed control.

The original 512 coordinates and all inherited weights/Adam moments keep their
meaning. Unknown facts still reach the original encoder. This is deliberately a
bounded supplement, not a claim to encode every game state without compression.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cached_property
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import NativeActor, NativeActorCritic
from spireshift.full_run_ppo_math import Adam
from spireshift.native_action_context import encode as original_encode
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_structured_vocabulary import facts, validate
from spireshift.training_objective import TrainingScoreSpec

BASE = 512
SCHEMA = "native-named-input-supplement-policy-v1"
ARMS = ("unchanged", "hashed", "named")


def resize(values: Sequence[float], before: int, after: int, hidden: int) -> tuple[float, ...]:
    """Copy all original coordinates, including the critic bias, with zero padding."""
    if before < BASE or after < BASE:
        raise ValueError("Never discard the original public coordinates")
    n = before * hidden
    expected = n + 2 * hidden + 2 * before + 1
    if len(values) != expected:
        raise ValueError("Weight or Adam layout differs from the declared actor/critic")
    result: list[float] = []
    for row in range(hidden):
        result.extend(values[row * before : row * before + min(before, after)])
        result.extend([0.0] * max(0, after - before))
    result.extend(values[n : n + 2 * hidden])
    for start, length in ((n + 2 * hidden, before), (n + 2 * hidden + before, before)):
        result.extend(values[start : start + min(length, after)])
        result.extend([0.0] * max(0, after - before))
    result.append(values[-1])
    return tuple(result)


@dataclass(frozen=True)
class SupplementModel(CachedContextModel):
    vocabulary: tuple[str, ...]
    projection: str

    def __post_init__(self) -> None:
        super().__post_init__()
        if (
            self.projection not in {"hashed", "named"}
            or not self.vocabulary
            or tuple(sorted(set(self.vocabulary))) != self.vocabulary
            or self.actor.dimension != BASE + len(self.vocabulary)
        ):
            raise ValueError("Supplement needs a frozen unique vocabulary and matched dimensions")

    @cached_property
    def columns(self) -> dict[str, int]:
        return {name: i for i, name in enumerate(self.vocabulary)}

    @cached_property
    def hash_columns(self) -> dict[str, tuple[int, int]]:
        result = {}
        for name in self.vocabulary:
            digest = hashlib.sha256(f"native-named-supplement-hash-v1|{name}".encode()).digest()
            result[name] = (
                int.from_bytes(digest[:8], "big") % len(self.vocabulary),
                1 if digest[8] & 1 else -1,
            )
        return result

    @cached_property
    def base_encoder(self) -> CachedContextModel:
        values = resize(self.weights(), self.actor.dimension, BASE, self.actor.hidden_units)
        size = BASE * self.actor.hidden_units + 2 * self.actor.hidden_units + BASE
        actor = NativeActor(
            self.actor.environment_id,
            BASE,
            self.actor.hidden_units,
            values[:size],
            self.actor.input_normalization,
        )
        return CachedContextModel(
            NativeActorCritic(actor, values[size:]), self.mode, self.feature_spec_id
        )

    def body_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA,
            "base_encoding": self.mode,
            "feature_spec_id": self.feature_spec_id,
            "vocabulary": list(self.vocabulary),
            "projection": self.projection,
            "supplement_normalization": "common_preprojection_at_most_one_L2_v1",
            "original_dimension": BASE,
            "unknown_facts": "original_encoder_retained",
            "native_parameters": self.native.as_dict(),
            "terminal_victory_probability_available": False,
        }

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> SupplementModel:
        model = cls(
            NativeActorCritic.from_mapping(value["native_parameters"]),
            value["base_encoding"],
            value["feature_spec_id"],
            tuple(value["vocabulary"]),
            value["projection"],
        )
        if model.as_dict() != value:
            raise ValueError("Named-input supplement schema or identity changed")
        return model


def extend(
    parent: CachedContextModel, adam: Adam, vocabulary: tuple[str, ...], arm: str
) -> tuple[CachedContextModel, Adam]:
    if arm not in ARMS or parent.actor.dimension != BASE:
        raise ValueError("Use an original 512-input parent and a declared comparison arm")
    if arm == "unchanged":
        return parent, Adam.from_mapping(adam.as_dict(), parent.parameter_count)
    dimension, hidden = BASE + len(vocabulary), parent.actor.hidden_units
    values = resize(parent.weights(), BASE, dimension, hidden)
    actor_size = dimension * hidden + 2 * hidden + dimension
    actor = NativeActor(
        parent.actor.environment_id,
        dimension,
        hidden,
        values[:actor_size],
        parent.actor.input_normalization,
    )
    model = SupplementModel(
        NativeActorCritic(actor, values[actor_size:]),
        parent.mode,
        parent.feature_spec_id,
        vocabulary,
        arm,
    )
    optimizer = Adam(
        adam.steps,
        resize(adam.first, BASE, dimension, hidden),
        resize(adam.second, BASE, dimension, hidden),
    )
    for original, expanded in (
        (parent.weights(), model.weights()),
        (adam.first, optimizer.first),
        (adam.second, optimizer.second),
    ):
        if resize(expanded, dimension, BASE, hidden) != tuple(original):
            raise ValueError("An inherited weight or Adam moment changed during extension")
    return model, optimizer


def encode(
    public: dict[str, Any], model: CachedContextModel, score: TrainingScoreSpec
) -> tuple[tuple[dict[int, float], ...], tuple[float, ...]]:
    validate(public)
    if not isinstance(model, SupplementModel):
        return original_encode(public, model, score)
    rows, state = original_encode(public, model.base_encoder, score)
    result = []
    for row, tokens in zip(rows, facts(public), strict=True):
        selected = {name: value for name, value in tokens.items() if name in model.columns}
        # Normalize the SAME semantic vector before either projection. Hash
        # cancellation is measured, not hidden by a different post-hash norm.
        norm = max(1.0, math.sqrt(math.fsum(v * v for v in selected.values())))
        addition: dict[int, float] = {}
        for name, value in sorted(selected.items()):
            index, sign = (
                (model.columns[name], 1)
                if model.projection == "named"
                else model.hash_columns[name]
            )
            addition[BASE + index] = addition.get(BASE + index, 0.0) + sign * value / norm
        result.append({**row, **{i: v for i, v in addition.items() if v}})
    return tuple(result), (*state[:-1], *([0.0] * len(model.vocabulary)), state[-1])


def vocabulary_id(names: tuple[str, ...]) -> str:
    return manifest_identifier(
        {"schema": "frozen_named_public_fact_columns_v1", "columns": list(names)}
    )
