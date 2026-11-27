"""Actual-engine public actor/critic. Reuse PPO mathematics, never emulator inputs/weights.

Every supplied action family is learnable. The critic predicts the declared bootstrap
episode return, not a calibrated win probability. Temporary handles never enter features.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_run import PRIVATE_FIELDS
from spireshift.full_run_policy import FullRunModel, score_features
from spireshift.full_run_ppo_math import ActorCritic as HistoricalActorCritic
from spireshift.full_run_ppo_math import (
    Adam,
    Sample,
    finite_vector,
    fit_round,
    log_softmax,
    sigmoid,
)
from spireshift.native_input_normalization import (
    NONE,
    normalization_from_mapping,
    normalization_spec,
    normalize_actor_rows,
)
from spireshift.neural_combat import _numpy

INPUT_SCHEMA = "actual-engine-public-entity-graph-v1"
ENCODER = "actual-engine-owned-public-choices-v1"
ACTOR_SCHEMA = "actual-engine-unified-actor-v1"
LEARNER_SCHEMA = "actual-engine-bootstrap-actor-critic-v1"
DIRECT = (
    "bias",
    "play",
    "end_turn",
    "use",
    "skip",
    "select",
    "confirm",
    "cancel",
    "close",
    "activate",
    "open",
    "damage",
    "block",
    "cost",
    "target_hp",
    "target_attack",
    "claim_reward",
    "declined_reward",
)
METADATA = {
    "snapshot_id",
    "bound_action_id",
    "interaction_id",
    "session",
    "observed_at",
    "read_id",
    "expected_snapshot_id",
    "observed_snapshot_id",
    "combat_id",
}


def validate_public_input(value: dict[str, Any]) -> None:
    if (
        set(value) != {"schema_version", "context", "candidates"}
        or value["schema_version"] != INPUT_SCHEMA
    ):
        raise ValueError("Expected the separately versioned actual-engine public input")
    if not isinstance(value["context"], dict) or not isinstance(value["candidates"], list):
        raise ValueError("Public input requires its context and complete candidate list")

    def visit(v: Any, key: str = "") -> None:
        if key.endswith(("entity_id", "entity_ids", "referent_id", "referent_ids")):
            pointers = v if isinstance(v, list) else [v]
            if any(
                p is not None
                and (
                    not isinstance(p, dict)
                    or set(p) != {"public_slot"}
                    or type(p["public_slot"]) is not int
                    or p["public_slot"] < 0
                )
                for p in pointers
            ):
                raise ValueError("Opaque or unresolved entity handle reached neural input")
        if isinstance(v, dict):
            for name, item in v.items():
                if name in PRIVATE_FIELDS | METADATA:
                    raise ValueError(f"Private or transport field reached neural input: {name}")
                visit(item, name)
        elif isinstance(v, list):
            for item in v:
                visit(item)
        elif isinstance(v, float) and not math.isfinite(v):
            raise ValueError("Nonfinite neural input")
        elif not isinstance(v, (str, int, float, bool, type(None))):
            raise ValueError("Unsupported public fact")

    visit(value)


def public_tokens(value: Any, prefix: str, output: dict[str, float]) -> None:
    # Keep owner paths and ordered list columns. In particular status names and
    # amounts, per-copy costs, intents, counters and selection limits cannot pool apart.
    if isinstance(value, dict):
        for key, item in sorted(value.items()):
            public_tokens(item, f"{prefix}/{key}", output)
    elif isinstance(value, list):
        output[f"{prefix}/count"] = math.log1p(len(value)) / 4
        for i, item in enumerate(value):
            public_tokens(item, f"{prefix}/{i}", output)
    elif isinstance(value, (str, bool)) or prefix.endswith("/public_slot"):
        output[f"{prefix}={value}"] = 1.0
    elif isinstance(value, (int, float)):
        output[prefix] = math.asinh(value) / 5
    elif value is None:
        output[f"{prefix}=null"] = 1.0


def hash_tokens(tokens: dict[str, float], dimension: int, offset: int = 0) -> dict[int, float]:
    values: dict[int, float] = {}
    for name, amount in sorted(tokens.items()):
        digest = hashlib.sha256(f"{ENCODER}|{name}".encode()).digest()
        index = offset + int.from_bytes(digest[:8], "big") % (dimension - offset)
        values[index] = values.get(index, 0.0) + (1 if digest[8] & 1 else -1) * amount
    return {i: max(-5.0, min(5.0, v)) for i, v in sorted(values.items()) if v}


def encode_public_input(
    value: dict[str, Any], dimension: int, input_normalization: str = NONE
) -> tuple[tuple[dict[int, float], ...], tuple[float, ...]]:
    validate_public_input(value)
    if not 128 <= dimension <= 4096:
        raise ValueError("Native neural feature dimension outside [128,4096]")
    shared: dict[str, float] = {}
    public_tokens(value["context"], "state", shared)
    context = hash_tokens(shared, dimension)
    state = (*[context.get(i, 0.0) for i in range(dimension)], 1.0)
    rows = []
    for candidate in value["candidates"]:
        tokens = dict(shared)
        public_tokens(candidate, "candidate", tokens)
        direct: dict[int, float] = {0: 1.0}
        if candidate["verb"] in DIRECT:
            direct[DIRECT.index(candidate["verb"])] = 1.0
        properties = (candidate.get("subject") or {}).get("properties", {})
        if (candidate.get("subject") or {}).get("role") == "reward":
            direct[DIRECT.index("claim_reward")] = 1.0
        if candidate.get("history", {}).get("card_reward_declined") is True:
            direct[DIRECT.index("declined_reward")] = 1.0
        stats = properties.get("stats") or {}
        for key in ("damage", "block"):
            if type(stats.get(key)) in (int, float):
                direct[DIRECT.index(key)] = math.asinh(stats[key]) / 5
        cost = properties.get("cost")
        if isinstance(cost, (int, float)) or isinstance(cost, str) and cost.isdigit():
            direct[DIRECT.index("cost")] = math.asinh(float(cost)) / 5
        for arg in candidate["arguments"]:
            if arg["role"] != "target" or not arg.get("entity"):
                continue
            target = arg["entity"]["properties"]
            if type(target.get("hp")) in (int, float):
                direct[DIRECT.index("target_hp")] = math.asinh(target["hp"]) / 5
            attacks = [intent.get("damage", 0) for intent in target.get("intents", [])]
            if all(type(a) in (int, float) for a in attacks):
                direct[DIRECT.index("target_attack")] = math.asinh(sum(attacks)) / 5
        rows.append({**direct, **hash_tokens(tokens, dimension, len(DIRECT))})
    return normalize_actor_rows(tuple(rows), len(DIRECT), input_normalization), state


@dataclass(frozen=True, slots=True)
class NativeActor:
    environment_id: str
    dimension: int
    hidden_units: int
    genome: tuple[float, ...]
    input_normalization: str = NONE

    def __post_init__(self) -> None:
        normalization_spec(self.input_normalization)
        if not self.environment_id.startswith("sha256:") or len(self.environment_id) != 71:
            raise ValueError("Native actor requires an exact environment identity")
        if type(self.dimension) is not int or not 128 <= self.dimension <= 4096:
            raise ValueError("Native actor feature dimension outside bounds")
        if type(self.hidden_units) is not int or not 4 <= self.hidden_units <= 128:
            raise ValueError("Native actor hidden size outside bounds")
        object.__setattr__(
            self, "genome", finite_vector(self.genome, self.parameter_count, "native actor")
        )

    @property
    def parameter_count(self) -> int:
        return self.dimension * self.hidden_units + 2 * self.hidden_units + self.dimension

    def unpack(self) -> tuple[Any, Any, Any, Any]:
        # Identical compact-network layout to the tested historical numerical kernel.
        g = _numpy().asarray(self.genome, dtype=_numpy().float64)
        n, h = self.dimension * self.hidden_units, self.hidden_units
        return g[:n].reshape(h, self.dimension), g[n : n + h], g[n + h : n + 2 * h], g[n + 2 * h :]

    def with_genome(self, genome: Sequence[float]) -> NativeActor:
        return replace(self, genome=tuple(genome))

    def body_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ACTOR_SCHEMA,
            "encoder_id": ENCODER,
            "environment_id": self.environment_id,
            "dimension": self.dimension,
            "hidden_units": self.hidden_units,
            "genome": list(self.genome),
            "scope": "every_current_supplied_legal_action",
            "activation": "tanh",
            **(
                {"input_normalization": normalization_spec(self.input_normalization)}
                if self.input_normalization != NONE
                else {}
            ),
        }

    @property
    def model_id(self) -> str:
        return manifest_identifier(self.body_dict())

    def as_dict(self) -> dict[str, Any]:
        return {**self.body_dict(), "model_id": self.model_id}

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> NativeActor:
        model = cls(
            value["environment_id"],
            value["dimension"],
            value["hidden_units"],
            tuple(value["genome"]),
            normalization_from_mapping(value.get("input_normalization")),
        )
        if model.as_dict() != value:
            raise ValueError(
                "Native actor schema/identity differs; old models cannot be ported implicitly"
            )
        return model


def initial_actor(
    environment_id: str,
    dimension: int = 512,
    hidden: int = 32,
    seed: int = 0,
    *,
    input_normalization: str = NONE,
) -> NativeActor:
    rng = random.Random(seed)
    scale = math.sqrt(6 / (dimension + hidden))
    weights = [rng.uniform(-scale, scale) for _ in range(dimension * hidden)]
    weights += [0.0] * hidden + [rng.uniform(-0.03, 0.03) for _ in range(hidden)]
    linear = [0.0] * dimension
    # A transparent, weak initializer only. No fixed action family or base-proximity gate.
    for name, amount in {
        "play": 2.0,
        "damage": 0.5,
        "block": 0.5,
        "end_turn": -0.5,
        "use": 1.5,
        "select": 0.1,
        "confirm": 0.5,
        "cancel": -0.5,
        "claim_reward": 0.5,
        "declined_reward": -2.0,
    }.items():
        linear[DIRECT.index(name)] = amount
    return NativeActor(
        environment_id, dimension, hidden, tuple(weights + linear), input_normalization
    )


@dataclass(frozen=True, slots=True)
class NativeActorCritic:
    actor: NativeActor
    value_weights: tuple[float, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value_weights",
            finite_vector(self.value_weights, self.actor.dimension + 1, "native critic"),
        )

    @property
    def parameter_count(self) -> int:
        return self.actor.parameter_count + len(self.value_weights)

    def weights(self) -> tuple[float, ...]:
        return (*self.actor.genome, *self.value_weights)

    def with_weights(self, values: Sequence[float]) -> NativeActorCritic:
        weights = finite_vector(values, self.parameter_count, "native actor critic")
        n = self.actor.parameter_count
        return NativeActorCritic(self.actor.with_genome(weights[:n]), weights[n:])

    def value(self, state: Sequence[float]) -> float:
        if len(state) != len(self.value_weights):
            raise ValueError("Native critic feature dimension differs")
        return float(
            sigmoid(math.fsum(a * b for a, b in zip(state, self.value_weights, strict=True)))
        )

    def body_dict(self) -> dict[str, Any]:
        return {
            "schema_version": LEARNER_SCHEMA,
            "actor": self.actor.as_dict(),
            "value_weights": list(self.value_weights),
            "value_target": "declared_undiscounted_whole_episode_bootstrap_return",
            "terminal_victory_probability_available": False,
        }

    @property
    def model_id(self) -> str:
        return manifest_identifier(self.body_dict())

    def as_dict(self) -> dict[str, Any]:
        return {**self.body_dict(), "model_id": self.model_id}

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> NativeActorCritic:
        model = cls(NativeActor.from_mapping(value["actor"]), tuple(value["value_weights"]))
        if model.as_dict() != value:
            raise ValueError("Native actor/critic identity or target differs")
        return model


def initialize_native_critic(actor: NativeActor) -> NativeActorCritic:
    return NativeActorCritic(actor, (*([0.0] * actor.dimension), math.log(0.02 / 0.98)))


def predict(
    model: NativeActorCritic,
    public: dict[str, Any],
    rng: random.Random | None,
    temperature: float = 1.0,
) -> dict[str, Any]:
    rows, state = encode_public_input(
        public, model.actor.dimension, model.actor.input_normalization
    )
    if not rows:
        raise ValueError("Neural policy requires a nonterminal complete menu")
    # The casts adapt structural numerical interfaces only; no historical actor,
    # emulator catalog, input vector or weight is loaded or converted.
    logits = score_features(cast(FullRunModel, model.actor), rows)
    logp = log_softmax(logits, temperature)
    if rng is None:
        selected = max(range(len(rows)), key=lambda i: (logits[i], -i))
    else:
        draw, cumulative, selected = rng.random(), 0.0, len(rows) - 1
        for i, item in enumerate(logp):
            cumulative += math.exp(item)
            if draw < cumulative:
                selected = i
                break
    return {
        "action_index": selected,
        "log_probability": logp[selected],
        "value": model.value(state),
        "model_id": model.model_id,
        "public_input_id": manifest_identifier(public),
        "temperature": temperature,
        "behavior": "greedy" if rng is None else "sampled_softmax",
    }


def fit_native_round(
    model: NativeActorCritic,
    optimizer: Adam,
    samples: Sequence[Sample],
    settings: dict[str, Any],
    seed: int,
) -> tuple[NativeActorCritic, Adam, dict[str, Any]]:
    updated, optimizer, diagnostic = fit_round(
        cast(HistoricalActorCritic, model), optimizer, samples, settings, seed
    )
    if not isinstance(updated, NativeActorCritic):
        raise ValueError("PPO kernel changed the native model type")
    return updated, optimizer, diagnostic
