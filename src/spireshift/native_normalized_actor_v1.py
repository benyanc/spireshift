"""A frozen reference plus a fully learnable, initially zero scoring correction."""

from __future__ import annotations

import sys
from collections.abc import Iterator, Sequence
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from spireshift.engine_learning import identified
from spireshift.engine_neural import NativeActor, NativeActorCritic, initial_actor
from spireshift.full_run_policy import dense_features
from spireshift.full_run_policy import score_features as original_scores
from spireshift.full_run_policy import score_gradient as original_gradient
from spireshift.full_run_ppo_math import Adam
from spireshift.native_a8_head_policy import HeadState
from spireshift.native_combat_intent_model import (
    CombatIntentModel,
    CombatIntentState,
    using_intent_encoder,
)
from spireshift.native_combat_intent_model import load as original_load
from spireshift.native_input_normalization import normalization_from_mapping
from spireshift.neural_combat import _numpy

SCHEMA = "native-frozen-reference-scoring-correction-v1"
METHODS = ("raw", "normalized")
EPSILON = 1e-5


@dataclass(frozen=True, kw_only=True)
class CorrectionActor(NativeActor):
    reference: NativeActor
    correction_normalization: str

    def __post_init__(self) -> None:
        super().__post_init__()
        if (
            type(self.reference) is not NativeActor
            or self.correction_normalization not in METHODS
            or (self.environment_id, self.dimension, self.input_normalization)
            != (
                self.reference.environment_id,
                self.reference.dimension,
                self.reference.input_normalization,
            )
        ):
            raise ValueError("Require a plain frozen reference and one declared correction")

    def unpack(self) -> tuple[Any, Any, Any, Any]:
        raise ValueError("Correction actors require the qualified scoring and gradient dispatch")

    def body_dict(self) -> dict[str, Any]:
        return {
            **super().body_dict(),
            "schema_version": SCHEMA,
            "reference": self.reference.as_dict(),
            "correction_normalization": self.correction_normalization,
            "normalization_epsilon": EPSILON,
            "normalization_axis": "hidden_units_within_each_candidate",
            "reference_parameters_trainable": False,
            "correction_parameters_trainable": True,
        }

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> CorrectionActor:
        actor = cls(
            value["environment_id"],
            value["dimension"],
            value["hidden_units"],
            tuple(value["genome"]),
            normalization_from_mapping(value.get("input_normalization")),
            reference=NativeActor.from_mapping(value["reference"]),
            correction_normalization=value["correction_normalization"],
        )
        if actor.as_dict() != value:
            raise ValueError(
                "The correction architecture, reference or full parameter state changed"
            )
        return actor


def activations(actor: CorrectionActor, rows: tuple[dict[int, float], ...]) -> tuple[Any, ...]:
    np = _numpy()
    x = dense_features(rows, actor.dimension)
    w, b, out, linear = NativeActor.unpack(actor)
    z = x @ w.T + b
    inverse = None
    if actor.correction_normalization == "normalized":
        centered = z - np.mean(z, axis=1, keepdims=True)
        inverse = 1.0 / np.sqrt(np.mean(centered * centered, axis=1, keepdims=True) + EPSILON)
        z = centered * inverse
    return x, z, np.tanh(z), inverse, out, linear


def score_features(actor: Any, rows: tuple[dict[int, float], ...]) -> tuple[float, ...]:
    if not isinstance(actor, CorrectionActor):
        return original_scores(actor, rows)
    x, _, h, _, out, linear = activations(actor, rows)
    reference = _numpy().asarray(reference_scores(actor.reference, rows))
    return tuple(float(v) for v in reference + h @ out + x @ linear)


def reference_scores(actor: NativeActor, rows: tuple[dict[int, float], ...]) -> tuple[float, ...]:
    return original_scores(cast(Any, actor), rows)


def score_gradient(
    actor: Any, rows: tuple[dict[int, float], ...], logit_gradient: Sequence[float]
) -> tuple[float, ...]:
    if not isinstance(actor, CorrectionActor):
        return original_gradient(actor, rows, logit_gradient)
    np = _numpy()
    x, z, h, inverse, out, _ = activations(actor, rows)
    dz = np.asarray(logit_gradient, dtype=np.float64)
    if dz.shape != (len(rows),) or not np.isfinite(dz).all():
        raise ValueError("Invalid correction logit derivative")
    dh = dz[:, None] * out * (1.0 - h * h)
    if inverse is not None:
        dh = inverse * (
            dh - np.mean(dh, axis=1, keepdims=True) - z * np.mean(dh * z, axis=1, keepdims=True)
        )
    # The frozen reference contributes scores but has no optimizer coordinates.
    return tuple(
        float(v) for v in np.concatenate(((dh.T @ x).ravel(), dh.sum(axis=0), h.T @ dz, x.T @ dz))
    )


@contextmanager
def using_correction_scoring() -> Iterator[None]:
    """Bind inference, PPO and independent replay; old models keep their old kernel."""
    with using_intent_encoder(), ExitStack() as stack:
        for name, module in list(sys.modules.items()):
            if not name.startswith("spireshift.") or module is None:
                continue
            for field, original, replacement in (
                ("score_features", original_scores, score_features),
                ("score_gradient", original_gradient, score_gradient),
            ):
                if getattr(module, field, None) is original:
                    stack.enter_context(patch.object(module, field, replacement))
        yield


def initialize(source: HeadState, method: str, seed: int) -> CombatIntentState:
    if (
        not isinstance(source.model, CombatIntentModel)
        or source.model.arm != "shared"
        or type(source.model.actor) is not NativeActor
    ):
        raise ValueError("Start only from the exact plain shared-head reference")
    if method not in METHODS:
        raise ValueError("Unknown correction method")
    baseline = source.model.actor
    fresh = initial_actor(
        baseline.environment_id,
        baseline.dimension,
        32,
        seed,
        input_normalization=baseline.input_normalization,
    )
    n = fresh.dimension * fresh.hidden_units + fresh.hidden_units
    genome = (*fresh.genome[:n], *([0.0] * (fresh.hidden_units + fresh.dimension)))
    actor = CorrectionActor(
        fresh.environment_id,
        fresh.dimension,
        fresh.hidden_units,
        genome,
        fresh.input_normalization,
        reference=baseline,
        correction_normalization=method,
    )
    model = replace(source.model, native=NativeActorCritic(actor, source.model.value_weights))
    zero = (0.0,) * actor.parameter_count
    return CombatIntentState(model, Adam(0, zero, zero), None, source.value_adam)


def load(path: Path) -> tuple[HeadState, str]:
    saved = identified(path, "state_id")
    actor_doc = saved.get("base_model", {}).get("native_parameters", {}).get("actor", {})
    if actor_doc.get("schema_version") != SCHEMA:
        return original_load(path)
    base = saved["base_model"]
    actor = CorrectionActor.from_mapping(actor_doc)
    model = CombatIntentModel(
        NativeActorCritic(actor, tuple(base["native_parameters"]["value_weights"])),
        base["encoding"]["id"],
        base["feature_spec_id"],
        stat_names=tuple(saved["card_display_encoding"]["columns"]),
    )
    state = CombatIntentState(
        model,
        Adam.from_mapping(saved["actor_adam"], actor.parameter_count),
        None,
        Adam.from_mapping(saved["value_adam"], len(model.value_weights)),
    )
    if state.document() != {k: v for k, v in saved.items() if k != "state_id"}:
        raise ValueError("The correction model, frozen reference or full Adam failed exact reload")
    return state, str(saved["state_id"])
