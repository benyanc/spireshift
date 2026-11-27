"""Independent action-conditional prediction network; it never supplies action scores.

The original policy and its complete PPO Adam state are not parameters of this
learner. The copied initial hidden features belong to the predictor thereafter.
Recorded-continuation targets are not causal Q values or victory probabilities.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import validate_public_input
from spireshift.full_run_policy import dense_features
from spireshift.native_action_context import encode, policy
from spireshift.native_combat_behavior_policy import Chooser
from spireshift.native_consequence_data import TARGETS, group_weights
from spireshift.native_consequence_math import CURVE_STEPS, metrics, validate_arrays
from spireshift.native_context_cache import CachedContextModel
from spireshift.neural_combat import _numpy
from spireshift.training_objective import TrainingScoreSpec

SCHEMA = "native-independent-outcome-predictor-v1"
SETTINGS = {"epochs": 128, "learning_rate": 0.001, "l2": 0.0001, "gradient_clip": 5.0}


def validate_prediction_public(public: dict[str, Any]) -> None:
    validate_public_input(public)
    reserved = {
        "native_seed",
        "source_seed_id",
        "run_seed",
        "plan_id",
        "label_endpoints",
        "target_mask",
        "return_samples",
        "training_return",
        "private_final_identity",
    }

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if reserved.intersection(value):
                raise ValueError("Training provenance or future labels reached prediction inputs")
            for v in value.values():
                visit(v)
        elif isinstance(value, list):
            for v in value:
                visit(v)

    visit(public)


@dataclass(frozen=True)
class OutcomePredictor:
    parent_model_id: str
    feature_spec_id: str
    dimension: int
    hidden_units: int
    parameters: tuple[float, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]

    def __post_init__(self) -> None:
        if (
            any(
                not v.startswith("sha256:") or len(v) != 71
                for v in (self.parent_model_id, self.feature_spec_id)
            )
            or type(self.dimension) is not int
            or not 128 <= self.dimension <= 4096
            or type(self.hidden_units) is not int
            or not 4 <= self.hidden_units <= 128
            or len(self.parameters) != self.parameter_count
            or len(self.means) != len(TARGETS)
            or len(self.scales) != len(TARGETS)
            or any(not math.isfinite(v) for v in (*self.parameters, *self.means, *self.scales))
            or any(v <= 0 for v in self.scales)
        ):
            raise ValueError("Independent predictor identity, shape or finite calibration differs")

    @property
    def parameter_count(self) -> int:
        return (
            self.dimension * self.hidden_units
            + self.hidden_units
            + (self.hidden_units + 1) * len(TARGETS)
        )

    def unpack(self) -> tuple[Any, Any, Any, Any]:
        np = _numpy()
        g = np.asarray(self.parameters, dtype=np.float64)
        body, width, heads = self.dimension * self.hidden_units, self.hidden_units, len(TARGETS)
        return (
            g[:body].reshape(width, self.dimension),
            g[body : body + width],
            g[body + width : -heads].reshape(width, heads),
            g[-heads:],
        )

    def normalized(self, x: Any) -> Any:
        np = _numpy()
        if x.ndim != 2 or x.shape[1] != self.dimension or not np.isfinite(x).all():
            raise ValueError("Outcome predictor requires finite current-public feature rows")
        w, bias, out, offset = self.unpack()
        return np.tanh(x @ w.T + bias) @ out + offset

    def predictions(self, x: Any) -> Any:
        return self.normalized(x) * _numpy().asarray(self.scales) + _numpy().asarray(self.means)

    def body(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA,
            "parent_model_id": self.parent_model_id,
            "feature_spec_id": self.feature_spec_id,
            "dimension": self.dimension,
            "hidden_units": self.hidden_units,
            "parameters": list(self.parameters),
            "means": list(self.means),
            "scales": list(self.scales),
            "targets": list(TARGETS),
            "scope": "recorded_action_conditional_continuations_not_policy_or_victory_probability",
        }

    def as_dict(self) -> dict[str, Any]:
        body = self.body()
        return {**body, "predictor_id": manifest_identifier(body)}

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> OutcomePredictor:
        if data.get("schema_version") != SCHEMA:
            raise ValueError("Prediction and policy checkpoints are different schemas")
        p = cls(
            data["parent_model_id"],
            data["feature_spec_id"],
            data["dimension"],
            data["hidden_units"],
            tuple(data["parameters"]),
            tuple(data["means"]),
            tuple(data["scales"]),
        )
        if data != p.as_dict():
            raise ValueError("Outcome predictor seal or target contract differs")
        return p


@dataclass(frozen=True)
class PlayerWithPredictions:
    player: CachedContextModel
    predictor: OutcomePredictor

    def __post_init__(self) -> None:
        if (
            self.player.model_id != self.predictor.parent_model_id
            or self.player.feature_spec_id != self.predictor.feature_spec_id
            or self.player.actor.dimension != self.predictor.dimension
        ):
            raise ValueError("Bind predictions to the exact original public encoder/player")

    def action_policy(
        self, public: dict[str, Any], score: TrainingScoreSpec, temperature: float
    ) -> Any:
        # No predictor inference, parameters, calibration or targets reach this path.
        return policy(public, self.player, score, temperature)

    def chooser(self, score: TrainingScoreSpec, seed: str, arm: str) -> Chooser:
        return Chooser(self.player, score, seed, arm)

    def predict(self, public: dict[str, Any], score: TrainingScoreSpec) -> dict[str, Any]:
        validate_prediction_public(public)
        rows, _ = encode(public, self.player, score)
        return {
            "targets": list(TARGETS),
            "predictions": self.predictor.predictions(
                dense_features(rows, self.predictor.dimension)
            ).tolist(),
            "candidate_indices": list(range(len(rows))),
            "used_for_action_selection": False,
        }


def gradient(
    p: OutcomePredictor, x: Any, target: Any, weights: Any, coefficients: Any, l2: float
) -> tuple[float, Any]:
    np = _numpy()
    w, bias, out, offset = p.unpack()
    hidden = np.tanh(x @ w.T + bias)
    error = hidden @ out + offset - target
    if weights.shape != error.shape or coefficients.shape != (len(TARGETS),):
        raise ValueError("Independent prediction loss shape differs")
    delta = 2 * weights * coefficients * error
    dh = (delta @ out.T) * (1 - hidden * hidden)
    g = np.concatenate(
        (
            (dh.T @ x + 2 * l2 * w).ravel(),
            dh.sum(axis=0),
            (hidden.T @ delta + 2 * l2 * out).ravel(),
            delta.sum(axis=0),
        )
    )
    loss = float(
        np.sum(weights * coefficients * error * error)
        + l2 * (np.square(w).sum() + np.square(out).sum())
    )
    if not math.isfinite(loss) or not np.isfinite(g).all():
        raise ValueError("Nonfinite independent prediction gradient")
    return loss, g


def fit_predictor(
    parent: CachedContextModel,
    fitting: dict[str, Any],
    held: dict[str, Any],
    seed: int,
    deadline: float,
    *,
    epochs: int = 128,
    allow_no_held: bool = False,
) -> tuple[OutcomePredictor, dict[str, Any], dict[str, Any]]:
    np = _numpy()
    if (
        type(epochs) is not int
        or not 1 <= epochs <= SETTINGS["epochs"]
        or type(seed) is not int
        or seed < 0
    ):
        raise ValueError("Freeze a finite independent predictor schedule")
    validate_arrays(fitting, parent.actor.dimension)
    if len(held["owners"]):
        validate_arrays(held, parent.actor.dimension)
    elif not allow_no_held:
        raise ValueError("Keep an entire source world out of fitting")
    if set(fitting["owners"].tolist()) & set(held["owners"].tolist()):
        raise ValueError("No source world can validate its own predictions")
    weights = group_weights(fitting["owners"], fitting["plans"], fitting["mask"])
    means = np.sum(weights * fitting["targets"], axis=0)
    var = np.sum(weights * np.square(fitting["targets"] - means), axis=0)
    scales = np.maximum(np.sqrt(var), [0.01, *([0.05] * (len(TARGETS) - 1))])
    coefficients = np.asarray([1.0, *([0.25 / 6] * 6)])
    coefficients[(weights.sum(axis=0) == 0) | (var <= 1e-12)] = 0
    w, bias, _, _ = parent.actor.unpack()
    out = np.random.default_rng(seed).normal(0, 0.01, (parent.actor.hidden_units, len(TARGETS)))
    out[:, coefficients == 0] = 0
    values = np.concatenate((w.ravel(), bias, out.ravel(), np.zeros(len(TARGETS))))
    first, second = np.zeros_like(values), np.zeros_like(values)
    curves = []
    parent_before = parent.weights()
    for step in range(epochs + 1):
        if time.monotonic() >= deadline:
            raise TimeoutError("Independent prediction fit reached its finite cap")
        p = OutcomePredictor(
            parent.model_id,
            parent.feature_spec_id,
            parent.actor.dimension,
            parent.actor.hidden_units,
            tuple(float(v) for v in values),
            tuple(float(v) for v in means),
            tuple(float(v) for v in scales),
        )
        if step in CURVE_STEPS or step == epochs:
            curves.append(
                {
                    "step": step,
                    "fitting": metrics(p.predictions(fitting["inputs"]), fitting),
                    "held": metrics(p.predictions(held["inputs"]), held),
                }
            )
        if step == epochs:
            break
        _, g = gradient(
            p,
            fitting["inputs"],
            (fitting["targets"] - means) / scales,
            weights,
            coefficients,
            SETTINGS["l2"],
        )
        g *= min(1.0, SETTINGS["gradient_clip"] / max(float(np.linalg.norm(g)), 1e-30))
        first = 0.9 * first + 0.1 * g
        second = 0.999 * second + 0.001 * g * g
        values -= (
            SETTINGS["learning_rate"]
            * (first / (1 - 0.9 ** (step + 1)))
            / (np.sqrt(second / (1 - 0.999 ** (step + 1))) + 1e-8)
        )
    if parent.weights() != parent_before:
        raise ValueError("Prediction fitting must never mutate the original policy")
    state = {
        "schema_version": "native-independent-predictor-Adam-v1",
        "steps": epochs,
        "first": first.tolist(),
        "second": second.tolist(),
        "scope": "new_prediction_parameters_only_not_parent_PPO_Adam",
    }
    report = {
        "predictor_id": p.as_dict()["predictor_id"],
        "parent_model_id": parent.model_id,
        "parameters": p.parameter_count,
        "epochs": epochs,
        "seed": seed,
        "settings": SETTINGS,
        "parent_policy_changed": False,
        "parent_PPO_Adam_updates": 0,
        "predictor_Adam_starts_at_zero": True,
        "fitting_worlds": sorted(set(fitting["owners"].tolist())),
        "held_worlds": sorted(set(held["owners"].tolist())),
        "curves": curves,
        "constant_baseline": metrics(np.tile(means, (len(held["owners"]), 1)), held),
        "active_targets": [name for name, c in zip(TARGETS, coefficients, strict=True) if c],
        "held_outcomes_select_no_parameters_or_epoch": True,
        "ordinary_PPO_eligible": False,
        "used_for_action_selection": False,
        "full_run_objective_or_bootstrap_reward_changed": False,
    }
    return p, state, report
