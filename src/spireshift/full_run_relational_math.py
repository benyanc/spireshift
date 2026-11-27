"""Versioned v3 serialization and public critic inputs; reuse verified PPO algebra."""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_ppo_math import ActorCritic as V2ActorCritic
from spireshift.full_run_ppo_math import Adam, Sample, finite_vector
from spireshift.full_run_ppo_math import fit_round as v2_fit_round
from spireshift.full_run_relational_policy import (
    RelationalFullRunModel,
    hashed_tokens,
    relational_tokens,
)
from spireshift.models import _exact_keys, _mapping

SCHEMA = "public-full-run-relational-actor-critic-v3"
VALUE_ENCODER = "public-entity-bound-bootstrap-value-v3"


def state_features(context: dict[str, Any], dimension: int) -> tuple[float, ...]:
    tokens: dict[str, float] = {}
    relational_tokens(context, "state", tokens)
    values = hashed_tokens(tokens, dimension, VALUE_ENCODER)
    return (*[values.get(i, 0.0) for i in range(dimension)], 1.0)


class ActorCritic(V2ActorCritic):
    actor: RelationalFullRunModel

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.actor, RelationalFullRunModel):
            raise ValueError("Relational learner cannot silently convert a historical actor")

    def body_dict(self) -> dict[str, Any]:
        return {**super().body_dict(), "schema_version": SCHEMA, "value_encoder_id": VALUE_ENCODER}

    def with_weights(self, values: Sequence[float]) -> ActorCritic:
        weights = finite_vector(tuple(values), self.parameter_count, "relational learner weights")
        actor = self.actor
        if not isinstance(actor, RelationalFullRunModel):
            raise ValueError("Wrong relational actor version")
        return ActorCritic(
            actor.with_genome(weights[: actor.parameter_count]), weights[actor.parameter_count :]
        )

    @classmethod
    def from_mapping(cls, value: object) -> ActorCritic:
        d = _mapping(value, "relational actor critic")
        _exact_keys(
            d,
            {
                "schema_version",
                "actor",
                "value_encoder_id",
                "value_weights",
                "value_target",
                "terminal_victory_probability_available",
                "model_id",
            },
            "relational actor critic",
        )
        if (
            d["schema_version"] != SCHEMA
            or d["value_encoder_id"] != VALUE_ENCODER
            or d["value_target"] != "declared_undiscounted_whole_episode_bootstrap_return"
            or d["terminal_victory_probability_available"] is not False
            or d["model_id"] != manifest_identifier({k: v for k, v in d.items() if k != "model_id"})
        ):
            raise ValueError("Relational actor critic identity or target differs")
        actor = RelationalFullRunModel.from_mapping(d["actor"])
        return cls(actor, finite_vector(d["value_weights"], actor.dimension + 1, "critic"))


def initialize_critic(actor: RelationalFullRunModel) -> ActorCritic:
    return ActorCritic(actor, (*([0.0] * actor.dimension), math.log(0.02 / 0.98)))


def load_actor_critic(path: Path) -> ActorCritic:
    return ActorCritic.from_mapping(json.loads(path.read_text()))


def fit_round(
    model: ActorCritic,
    optimizer: Adam,
    samples: Sequence[Sample],
    settings: dict[str, Any],
    shuffle_seed: int,
) -> tuple[ActorCritic, Adam, dict[str, Any]]:
    updated, optimizer, diagnostic = v2_fit_round(model, optimizer, samples, settings, shuffle_seed)
    if not isinstance(updated, ActorCritic):
        raise ValueError("Optimizer changed the relational learner format")
    return updated, optimizer, diagnostic
