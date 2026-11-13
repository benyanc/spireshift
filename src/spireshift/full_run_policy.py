"""Standalone compact policy: every phase and every parameter can change."""

from __future__ import annotations

import json
import math
import random
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.types import LegalAction, Observation
from spireshift.full_run_features import DIRECT_FEATURES, ENCODER_ID, FullRunInput, full_run_input
from spireshift.models import _exact_keys, _mapping
from spireshift.neural_combat import _numpy
from spireshift.neural_combat_features import validate_catalog

SCHEMA = "unified-full-run-policy-v1"
GENOME_LAYOUT = "row-major-input-hidden-output-linear-v1"


def _finite_weights(value: object, length: int) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != length:
        raise ValueError("Unified policy genome shape differs")
    if any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1000 for v in value):
        raise ValueError("Unified policy genome must contain finite bounded weights")
    return tuple(float(v) for v in value)


@dataclass(frozen=True, slots=True)
class FullRunModel:
    ruleset_manifest_id: str
    patch_id: str
    dimension: int
    hidden_units: int
    catalog: dict[str, dict[str, Any]]
    card_source_sha256: str
    genome: tuple[float, ...]

    def __post_init__(self) -> None:
        if type(self.dimension) is not int or not 128 <= self.dimension <= 4096:
            raise ValueError("Unified feature dimension must be in [128,4096]")
        if type(self.hidden_units) is not int or not 4 <= self.hidden_units <= 128:
            raise ValueError("Unified hidden units must be in [4,128]")
        # Normalize before hashing: JSON 1 and 1.0 must not produce different saved
        # model IDs after the deterministic genome loader converts weights to floats.
        object.__setattr__(self, "genome", _finite_weights(list(self.genome), self.parameter_count))
        for identity in (self.ruleset_manifest_id, f"sha256:{self.card_source_sha256}"):
            if (
                not identity.startswith("sha256:")
                or len(identity) != 71
                or any(c not in "0123456789abcdef" for c in identity[7:])
            ):
                raise ValueError("Unified policy requires SHA-256 source identities")
        if not self.patch_id:
            raise ValueError("Unified policy requires a patch identity")
        object.__setattr__(self, "catalog", json.loads(json.dumps(validate_catalog(self.catalog))))

    @property
    def parameter_count(self) -> int:
        return self.dimension * self.hidden_units + 2 * self.hidden_units + self.dimension

    def unpack(self) -> tuple[Any, Any, Any, Any]:
        np = _numpy()
        g = np.asarray(self.genome, dtype=np.float64)
        n, h = self.dimension * self.hidden_units, self.hidden_units
        return g[:n].reshape(h, self.dimension), g[n : n + h], g[n + h : n + 2 * h], g[n + 2 * h :]

    def with_genome(self, genome: Sequence[float]) -> FullRunModel:
        return replace(self, genome=_finite_weights(list(genome), self.parameter_count))

    def body_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA,
            "encoder_id": ENCODER_ID,
            "ruleset_manifest_id": self.ruleset_manifest_id,
            "patch_id": self.patch_id,
            "feature_dimension": self.dimension,
            "hidden_units": self.hidden_units,
            "activation": "tanh",
            "genome_layout": GENOME_LAYOUT,
            "printed_card_catalog": self.catalog,
            "card_catalog_id": manifest_identifier(self.catalog),
            "card_source_sha256": self.card_source_sha256,
            "genome": list(self.genome),
            "scope": "all_supplied_legal_full_run_decisions",
            "heads": ["policy_logit"],
            "terminal_value_available": False,
        }

    @property
    def model_id(self) -> str:
        return manifest_identifier(self.body_dict())

    def as_dict(self) -> dict[str, Any]:
        return {**self.body_dict(), "model_id": self.model_id}

    @classmethod
    def from_mapping(cls, value: object) -> FullRunModel:
        d = _mapping(value, "unified full-run model")
        _exact_keys(
            d,
            {
                "schema_version",
                "encoder_id",
                "ruleset_manifest_id",
                "patch_id",
                "feature_dimension",
                "hidden_units",
                "activation",
                "genome_layout",
                "printed_card_catalog",
                "card_catalog_id",
                "card_source_sha256",
                "genome",
                "scope",
                "heads",
                "terminal_value_available",
                "model_id",
            },
            "unified model",
        )
        if (
            d["schema_version"] != SCHEMA
            or d["encoder_id"] != ENCODER_ID
            or d["genome_layout"] != GENOME_LAYOUT
            or d["activation"] != "tanh"
            or d["scope"] != "all_supplied_legal_full_run_decisions"
            or d["heads"] != ["policy_logit"]
            or d["terminal_value_available"] is not False
        ):
            raise ValueError("Unsupported unified full-run policy format")
        if d["model_id"] != manifest_identifier({k: v for k, v in d.items() if k != "model_id"}):
            raise ValueError("Unified policy content identity differs")
        catalog = validate_catalog(d["printed_card_catalog"])
        if d["card_catalog_id"] != manifest_identifier(catalog):
            raise ValueError("Unified card catalog identity differs")
        if type(d["feature_dimension"]) is not int or type(d["hidden_units"]) is not int:
            raise ValueError("Unified network dimensions must be integers")
        n = (
            d["feature_dimension"] * d["hidden_units"]
            + 2 * d["hidden_units"]
            + d["feature_dimension"]
        )
        return cls(
            d["ruleset_manifest_id"],
            d["patch_id"],
            d["feature_dimension"],
            d["hidden_units"],
            catalog,
            d["card_source_sha256"],
            _finite_weights(d["genome"], n),
        )


def load_full_run_model(path: Path) -> FullRunModel:
    return FullRunModel.from_mapping(json.loads(path.read_text(encoding="utf-8")))


def initial_full_run_model(
    ruleset: RulesetIdentity,
    catalog: dict[str, dict[str, Any]],
    card_source_sha256: str,
    *,
    dimension: int = 256,
    hidden_units: int = 16,
    initialization_seed: int = 0,
) -> FullRunModel:
    """Simple tactics initialize learnable weights; they never filter or lock actions."""
    rng = random.Random(initialization_seed)
    scale = math.sqrt(6 / (dimension + hidden_units))
    g = [rng.uniform(-scale, scale) for _ in range(dimension * hidden_units)]
    g += [0.0] * hidden_units
    g += [rng.uniform(-0.03, 0.03) for _ in range(hidden_units)]
    linear = [0.0] * dimension
    warm_start = {
        "play_card": 0.4,
        "printed_damage": 0.2,
        "printed_useful_damage": 0.7,
        "printed_kill": 1.5,
        "printed_needed_block": 1.4,
        "printed_excess_block": -0.2,
        "printed_cost": -0.15,
        "end_turn": -0.5,
        "use_potion": 0.1,
        "heal_missing_hp": 2,
        "upgrade": 0.45,
        "take_card": 0.2,
        "card_quality": 0.4,
        "card_is_power": 0.2,
        "card_is_curse": -0.5,
        "remove_bad_card": 1,
        "shop_price": -0.4,
        "buy_relic": 0.5,
        "buy_potion": 0.15,
        "claim_reward": 1,
        "skip_reward": -0.3,
        "route_rest_missing_hp": 1,
        "route_elite": -0.2,
        "route_treasure": 0.4,
        "confirm": 0.5,
        "route_event": 0.1,
    }
    for name, weight in warm_start.items():
        linear[DIRECT_FEATURES.index(name)] = weight
    return FullRunModel(
        ruleset.manifest_id,
        ruleset.patch_id,
        dimension,
        hidden_units,
        validate_catalog(catalog),
        card_source_sha256,
        tuple(g + linear),
    )


def dense_features(rows: tuple[dict[int, float], ...], dimension: int) -> Any:
    np = _numpy()
    x = np.zeros((len(rows), dimension), dtype=np.float64)
    for row, values in enumerate(rows):
        for index, value in values.items():
            if not 0 <= index < dimension or not math.isfinite(value):
                raise ValueError("Invalid unified feature coordinate")
            x[row, index] = value
    return x


def score_features(model: FullRunModel, rows: tuple[dict[int, float], ...]) -> tuple[float, ...]:
    np = _numpy()
    w, b, out, linear = model.unpack()
    x = dense_features(rows, model.dimension)
    return tuple(float(v) for v in np.tanh(x @ w.T + b) @ out + x @ linear)


def score_gradient(
    model: FullRunModel,
    rows: tuple[dict[int, float], ...],
    logit_gradient: Sequence[float],
) -> tuple[float, ...]:
    """Backpropagate through the entire genome; usable by return-trained NN updates."""
    np = _numpy()
    x = dense_features(rows, model.dimension)
    w, b, out, _ = model.unpack()
    dz = np.asarray(logit_gradient, dtype=np.float64)
    if dz.shape != (len(rows),) or not np.isfinite(dz).all():
        raise ValueError("Invalid unified logit gradient")
    hidden = np.tanh(x @ w.T + b)
    dh = dz[:, None] * out * (1 - hidden * hidden)
    return tuple(
        float(v)
        for v in np.concatenate(((dh.T @ x).ravel(), dh.sum(axis=0), hidden.T @ dz, x.T @ dz))
    )


@dataclass(frozen=True, slots=True)
class FullRunDecision:
    inputs: FullRunInput
    logits: tuple[float, ...]
    probabilities: tuple[float, ...]
    candidate_index: int
    selected_action: LegalAction


class FullRunPolicy:
    def __init__(self, ruleset: RulesetIdentity, model: FullRunModel) -> None:
        if model.ruleset_manifest_id != ruleset.manifest_id or model.patch_id != ruleset.patch_id:
            raise ValueError("Unified policy belongs to another ruleset or patch")
        self.ruleset, self.model = ruleset, model
        self.policy_id = f"unified-full-run-v1:{model.model_id}"
        self.model_id = model.model_id

    def predict(
        self, observation: Observation, legal_actions: Sequence[LegalAction]
    ) -> FullRunDecision:
        actions = tuple(legal_actions)
        if not actions:
            raise ValueError("Unified policy requires supplied legal candidates")
        inputs = full_run_input(
            self.ruleset, observation, actions, self.model.catalog, self.model.dimension
        )
        logits = score_features(self.model, inputs.vectors)
        maximum = max(logits)
        weights = tuple(math.exp(v - maximum) for v in logits)
        probabilities = tuple(v / math.fsum(weights) for v in weights)
        # This v1 player acts greedily. Softmax is exposed for future gradient training;
        # collection must record greedy behavior probability 1, not pretend it sampled.
        index = max(range(len(actions)), key=lambda i: (logits[i], -i))
        return FullRunDecision(inputs, logits, probabilities, index, actions[index])

    def choose_action(
        self, observation: Observation, legal_actions: Sequence[LegalAction]
    ) -> LegalAction:
        return self.predict(observation, legal_actions).selected_action
