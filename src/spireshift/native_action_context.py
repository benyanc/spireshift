"""Versioned public numeric/context-candidate features with unchanged PPO math.

Keep the original native graph projection, direct coordinates, critic inputs,
action menu and parameter count. Additional feature terms are explicitly hashed;
they are not lossless encodings or hand-assigned rewards. Legacy models remain
under their original schema, encoder and source files.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import (
    DIRECT,
    NativeActor,
    NativeActorCritic,
    encode_public_input,
    initial_actor,
    initialize_native_critic,
    public_tokens,
)
from spireshift.full_run_policy import FullRunModel, score_features
from spireshift.full_run_ppo_math import log_softmax
from spireshift.native_input_normalization import QUARTER
from spireshift.native_value_credit import FEATURES, public_value_features
from spireshift.training_objective import TrainingScoreSpec

ORIGINAL = "native-original-quarter-v1"
SHARED = "native-public-numeric-shared-v1"
CROSSED = "native-public-numeric-candidate-cross-v1"
MODES = (ORIGINAL, SHARED, CROSSED)
GAIN = 4.0
SCHEMA = "native-public-action-context-policy-v1"


def encoding_spec(mode: str) -> dict[str, Any]:
    if mode not in MODES:
        raise ValueError("Unknown public action-context encoding")
    return {
        "id": mode,
        "base": "unchanged_native_public_graph_quarter_projection",
        "numeric_features": list(FEATURES[1:]) if mode != ORIGINAL else [],
        "extra_projection_gain": GAIN if mode != ORIGINAL else 0.0,
        "extra_projection_norm": "at_most_one_L2_before_gain",
        "hash_salt": "native-public-action-context-hash-v1",
        "direct_coordinates_and_critic": "unchanged",
        "candidate_tokens": "all_validated_public_candidate_fields" if mode == CROSSED else None,
    }


def _project(tokens: dict[str, float], dimension: int) -> dict[int, float]:
    values: dict[int, float] = {}
    for token, amount in sorted(tokens.items()):
        digest = hashlib.sha256(f"native-public-action-context-hash-v1|{token}".encode()).digest()
        i = len(DIRECT) + int.from_bytes(digest[:8], "big") % (dimension - len(DIRECT))
        values[i] = values.get(i, 0.0) + (1 if digest[8] & 1 else -1) * amount
    norm = math.sqrt(math.fsum(v * v for v in values.values()))
    return {i: GAIN * v / max(1.0, norm) for i, v in values.items() if v}


@dataclass(frozen=True)
class ActionContextModel:
    native: NativeActorCritic
    mode: str
    feature_spec_id: str

    def __post_init__(self) -> None:
        encoding_spec(self.mode)
        if not self.feature_spec_id.startswith("sha256:") or len(self.feature_spec_id) != 71:
            raise ValueError("Action-context model needs its exact numeric-feature score spec")
        if self.native.actor.input_normalization != QUARTER:
            raise ValueError("Action-context experiment requires quarter normalization")

    @property
    def actor(self) -> NativeActor:
        return self.native.actor

    @property
    def value_weights(self) -> tuple[float, ...]:
        return self.native.value_weights

    @property
    def parameter_count(self) -> int:
        return self.native.parameter_count

    def value(self, row: Sequence[float]) -> float:
        return self.native.value(row)

    def weights(self) -> tuple[float, ...]:
        return self.native.weights()

    def with_weights(self, values: Sequence[float]) -> ActionContextModel:
        return replace(self, native=self.native.with_weights(values))

    def body_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA,
            "encoding": encoding_spec(self.mode),
            "feature_spec_id": self.feature_spec_id,
            "native_parameters": self.native.as_dict(),
            "terminal_victory_probability_available": False,
        }

    @property
    def model_id(self) -> str:
        return manifest_identifier(self.body_dict())

    def as_dict(self) -> dict[str, Any]:
        return {**self.body_dict(), "model_id": self.model_id}

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> ActionContextModel:
        model = cls(
            NativeActorCritic.from_mapping(value["native_parameters"]),
            value["encoding"]["id"],
            value["feature_spec_id"],
        )
        if value != model.as_dict():
            raise ValueError("Action-context model schema, encoding or identity differs")
        return model


def initialize(environment: str, score_id: str, seed: int, mode: str) -> ActionContextModel:
    actor = initial_actor(environment, 512, 32, seed, input_normalization=QUARTER)
    w, b, out, linear = actor.unpack()
    # Common, declared initializer: zero hidden output weights make initial
    # policies exactly identical across feature treatments. No actor layer is
    # frozen; output and hidden weights can learn through the original kernel.
    genome = (*w.ravel(), *b, *([0.0] * len(out)), *linear)
    actor = actor.with_genome(tuple(float(v) for v in genome))
    return ActionContextModel(initialize_native_critic(actor), mode, score_id)


def encode(
    public: dict[str, Any], model: ActionContextModel, score: TrainingScoreSpec
) -> tuple[tuple[dict[int, float], ...], tuple[float, ...]]:
    if score.spec_id != model.feature_spec_id:
        raise ValueError("Action-context numeric feature specification differs")
    rows, state = encode_public_input(
        public, model.actor.dimension, model.actor.input_normalization
    )
    if model.mode == ORIGINAL:
        return rows, state
    numeric, _ = public_value_features(public, score)
    shared = {name: value for name, value in zip(FEATURES[1:], numeric[1:], strict=True) if value}
    shared_projection = _project(shared, model.actor.dimension) if model.mode == SHARED else {}
    result = []
    for row, candidate in zip(rows, public["candidates"], strict=True):
        if model.mode == SHARED:
            addition = shared_projection
        else:
            tokens: dict[str, float] = {}
            public_tokens(candidate, "candidate", tokens)
            addition = _project(
                {
                    f"{name}*{key}": value * amount
                    for name, value in shared.items()
                    for key, amount in tokens.items()
                },
                model.actor.dimension,
            )
        result.append(
            {
                i: row.get(i, 0.0) + addition.get(i, 0.0)
                for i in sorted(row.keys() | addition.keys())
                if row.get(i, 0.0) + addition.get(i, 0.0)
            }
        )
    return tuple(result), state


def policy(
    public: dict[str, Any], model: ActionContextModel, score: TrainingScoreSpec, temperature: float
) -> tuple[tuple[dict[int, float], ...], tuple[float, ...], tuple[float, ...]]:
    rows, state = encode(public, model, score)
    return (
        rows,
        state,
        log_softmax(score_features(cast(FullRunModel, model.actor), rows), temperature),
    )
