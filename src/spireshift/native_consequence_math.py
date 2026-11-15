"""Matched return-only versus consequence-assisted action-score regression.

This is explicitly off-policy supervised learning. It does not use PPO ratios,
interpret teacher returns as victories, or replace the full-run reward with HP.
Each disposable fork starts with the exact parent actor and complete PPO Adam
state; new auxiliary heads have their own zero-initialized Adam moments.
"""

from __future__ import annotations

import math
import time
from typing import Any, cast

from spireshift.engine_neural import NativeActorCritic
from spireshift.full_run_ppo_math import ActorCritic, Adam
from spireshift.native_consequence_data import TARGETS, group_weights
from spireshift.native_context_cache import CachedContextModel
from spireshift.neural_combat import _numpy

ARMS = ("return_only", "consequence", "action_blind")
SETTINGS = {
    "epochs": 128,
    "learning_rate": 0.001,
    "auxiliary_weight": 0.25,
    "l2": 0.0001,
    "gradient_clip": 5.0,
}
CURVE_STEPS = (0, 1, 4, 16, 32, 64, 128)
HEAD_SEEDS = (20261022, 20261023, 20261024)


def validate_arrays(arrays: dict[str, Any], dimension: int) -> None:
    np = _numpy()
    n = len(arrays["owners"])
    if (
        not n
        or arrays["inputs"].shape != (n, dimension)
        or arrays["action_blind"].shape != (n, dimension)
        or arrays["targets"].shape != (n, len(TARGETS))
        or arrays["mask"].shape != arrays["targets"].shape
        or arrays["mask"].dtype.kind != "b"
        or not arrays["mask"][:, 0].all()
        or arrays["plans"].shape != (n,)
        or arrays["potential"].shape != (n,)
        or any(
            not np.isfinite(arrays[k]).all()
            for k in ("inputs", "action_blind", "targets", "potential")
        )
        or np.any(arrays["targets"][:, 0] < 0)
        or np.any(arrays["targets"][:, 0] > 1)
        or not set(np.unique(arrays["targets"][:, 5]).tolist()) <= {0.0, 1.0}
    ):
        raise ValueError("Invalid current-public-input consequence arrays or observed labels")


def forward(model: CachedContextModel, heads: dict[str, Any], x: Any, offset: float) -> Any:
    np = _numpy()
    w, bias, out, linear = model.actor.unpack()
    hidden = np.tanh(x @ w.T + bias)
    return np.column_stack(
        (hidden @ out + x @ linear - offset, hidden @ heads["output"] + heads["bias"])
    )


def loss_gradient(
    model: CachedContextModel,
    heads: dict[str, Any],
    x: Any,
    target: Any,
    weights: Any,
    coefficients: Any,
    offset: float,
    regularization: float,
    auxiliary_encoder: bool,
) -> tuple[float, tuple[float, ...], dict[str, Any], dict[str, float]]:
    np = _numpy()
    w, bias, out, linear = model.actor.unpack()
    hidden = np.tanh(x @ w.T + bias)
    prediction = np.column_stack(
        (hidden @ out + x @ linear - offset, hidden @ heads["output"] + heads["bias"])
    )
    error = prediction - target
    if (
        weights.shape != error.shape
        or coefficients.shape != (len(TARGETS),)
        or not np.isfinite(error).all()
        or not np.isfinite(weights).all()
        or np.any(weights < 0)
        or not np.isfinite(coefficients).all()
        or np.any(coefficients < 0)
    ):
        raise ValueError("Invalid masked, source-balanced consequence loss")
    delta = 2 * weights * error * coefficients
    back = delta[:, :1] * out
    auxiliary_back = delta[:, 1:] @ heads["output"].T
    if auxiliary_encoder:
        back = back + auxiliary_back
    back *= 1 - hidden * hidden
    dw, db = back.T @ x + 2 * regularization * w, back.sum(axis=0)
    do = hidden.T @ delta[:, 0] + 2 * regularization * out
    dl = x.T @ delta[:, 0] + 2 * regularization * linear
    actor = (*dw.ravel(), *db, *do, *dl)
    gradient = tuple(float(v) for v in (*actor, *([0.0] * len(model.value_weights))))
    gh = {
        "output": hidden.T @ delta[:, 1:] + 2 * regularization * heads["output"],
        "bias": delta[:, 1:].sum(axis=0),
    }
    penalties = regularization * sum(
        float(np.square(v).sum()) for v in (w, out, linear, heads["output"])
    )
    mse = np.sum(weights * error * error, axis=0)
    loss = float(mse @ coefficients) + penalties
    if not math.isfinite(loss) or not all(math.isfinite(v) for v in gradient):
        raise ValueError("Nonfinite consequence learning update")
    return (
        loss,
        gradient,
        gh,
        {
            "return_loss": float(mse[0]),
            "auxiliary_loss": float(mse[1:] @ coefficients[1:]),
            "auxiliary_encoder_gradient_norm": float(
                np.linalg.norm(auxiliary_back * (1 - hidden * hidden))
            ),
        },
    )


def metrics(predictions: Any, arrays: dict[str, Any]) -> dict[str, Any]:
    np = _numpy()
    if predictions.shape != arrays["targets"].shape or not np.isfinite(predictions).all():
        raise ValueError("Consequence prediction has missing or nonfinite targets")
    weights = group_weights(arrays["owners"], arrays["plans"], arrays["mask"])
    difference = predictions - arrays["targets"]
    result = {}
    for j, name in enumerate(TARGETS):
        valid = arrays["mask"][:, j]
        result[name] = {
            "mse": float(weights[:, j] @ np.square(difference[:, j])) if valid.any() else None,
            "mae": float(weights[:, j] @ np.abs(difference[:, j])) if valid.any() else None,
            "valid_decisions": int(valid.sum()),
            "source_worlds": len(set(arrays["owners"][valid].tolist())),
        }
    return result


def fit(
    parent: CachedContextModel,
    original_adam: Adam,
    fitting: dict[str, Any],
    held: dict[str, Any],
    arm: str,
    head_seed: int,
    deadline: float,
    *,
    settings: dict[str, Any] | None = None,
    allow_no_held: bool = False,
) -> tuple[CachedContextModel, Adam, dict[str, Any], dict[str, Any]]:
    np = _numpy()
    settings = dict(SETTINGS if settings is None else settings)
    if (
        arm not in ARMS
        or set(settings) != set(SETTINGS)
        or type(settings["epochs"]) is not int
        or not 1 <= settings["epochs"] <= 128
        or type(head_seed) is not int
        or head_seed < 0
        or any(
            type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in settings.values()
        )
        or settings["learning_rate"] <= 0
        or settings["gradient_clip"] <= 0
    ):
        raise ValueError("Freeze a finite consequence fitting schedule")
    validate_arrays(fitting, parent.actor.dimension)
    if len(held["owners"]):
        validate_arrays(held, parent.actor.dimension)
    elif not allow_no_held:
        raise ValueError("Cross-validation must retain an entire unseen source game")
    if set(fitting["owners"].tolist()) & set(held["owners"].tolist()):
        raise ValueError("A complete source game cannot fit its own held consequences")
    if len(original_adam.first) != parent.parameter_count:
        raise ValueError("Keep every original PPO Adam moment")
    weights = group_weights(fitting["owners"], fitting["plans"], fitting["mask"])
    mean = np.sum(weights * fitting["targets"], axis=0)
    variance = np.sum(weights * np.square(fitting["targets"] - mean), axis=0)
    scale = np.maximum(np.sqrt(variance), [0.01, *([0.05] * (len(TARGETS) - 1))])
    active = (weights.sum(axis=0) > 0) & (variance > 1e-12)
    coefficients = np.asarray(
        [1.0, *([settings["auxiliary_weight"] / (len(TARGETS) - 1)] * (len(TARGETS) - 1))]
    )
    coefficients[1:] *= active[1:]
    name = "action_blind" if arm == "action_blind" else "inputs"
    x, xh = fitting[name], held[name]
    w, bias, out, linear = parent.actor.unpack()
    offset = float(weights[:, 0] @ (np.tanh(x @ w.T + bias) @ out + x @ linear))
    normalized = (fitting["targets"] - mean) / scale
    rng = np.random.default_rng(head_seed)
    heads = {
        "output": rng.normal(0, 0.01, (parent.actor.hidden_units, len(TARGETS) - 1)),
        "bias": np.zeros(len(TARGETS) - 1),
    }
    heads["output"][:, ~active[1:]] = 0
    head_first, head_second = ({k: np.zeros_like(v) for k, v in heads.items()} for _ in (0, 1))
    model, adam = parent, original_adam
    snapshots = []
    initial_norm = final_loss = 0.0
    for step in range(settings["epochs"] + 1):
        if time.monotonic() >= deadline:
            raise TimeoutError("Consequence fit reached its finite numerical cap")
        if step in CURVE_STEPS or step == settings["epochs"]:
            fp = forward(model, heads, x, offset) * scale + mean
            hp = forward(model, heads, xh, offset) * scale + mean
            snapshots.append(
                {"step": step, "fitting": metrics(fp, fitting), "held": metrics(hp, held)}
            )
        if step == settings["epochs"]:
            break
        loss, gradient, gh, diagnostic = loss_gradient(
            model,
            heads,
            x,
            normalized,
            weights,
            coefficients,
            offset,
            settings["l2"],
            arm != "return_only",
        )
        if step == 0:
            initial_norm = diagnostic["auxiliary_encoder_gradient_norm"]
        norm = math.sqrt(
            sum(v * v for v in gradient) + sum(float(np.square(g).sum()) for g in gh.values())
        )
        factor = min(1.0, settings["gradient_clip"] / max(norm, 1e-30))
        native, adam, _ = adam.update(
            cast(ActorCritic, model.native),
            tuple(v * factor for v in gradient),
            actor_rate=settings["learning_rate"],
            value_rate=0.0,
            maximum_norm=settings["gradient_clip"],
        )
        model = CachedContextModel(
            cast(NativeActorCritic, native), parent.mode, parent.feature_spec_id
        )
        for key in heads:
            g = gh[key] * factor
            head_first[key] = 0.9 * head_first[key] + 0.1 * g
            head_second[key] = 0.999 * head_second[key] + 0.001 * g * g
            heads[key] -= (
                settings["learning_rate"]
                * (head_first[key] / (1 - 0.9 ** (step + 1)))
                / (np.sqrt(head_second[key] / (1 - 0.999 ** (step + 1))) + 1e-8)
            )
        final_loss = loss
    constant = np.tile(mean, (len(held["owners"]), 1))
    persistence = np.zeros_like(constant)
    residual = float(weights[:, 0] @ (fitting["targets"][:, 0] - fitting["potential"]))
    persistence[:, 0] = held["potential"] + residual
    persistence[:, 5] = 1.0
    saved = {
        **{f"head_{k}": v for k, v in heads.items()},
        **{f"head_first_{k}": v for k, v in head_first.items()},
        **{f"head_second_{k}": v for k, v in head_second.items()},
        "head_steps": np.asarray([settings["epochs"]], dtype=np.int64),
        "mean": mean,
        "scale": scale,
        "coefficients": coefficients,
        "return_logit_offset": np.asarray([offset]),
    }
    report = {
        "arm": arm,
        "head_seed": head_seed,
        "epochs": settings["epochs"],
        "initial_model_id": parent.model_id,
        "trained_model_id": model.model_id,
        "initial_PPO_Adam_steps": original_adam.steps,
        "final_fork_PPO_Adam_steps": adam.steps,
        "original_PPO_Adam_moments_used_without_reset": True,
        "new_head_Adam_starts_at_zero": True,
        "auxiliary_encoder_gradient_enabled": arm != "return_only",
        "auxiliary_heads_fit_in_both_matched_arms": True,
        "initial_auxiliary_encoder_gradient_norm": initial_norm,
        "fitting_worlds": sorted(set(fitting["owners"].tolist())),
        "held_worlds": sorted(set(held["owners"].tolist())),
        "fitting_decisions": len(fitting["owners"]),
        "held_decisions": len(held["owners"]),
        "fitting_target_means": mean.tolist(),
        "fitting_target_scales": scale.tolist(),
        "active_auxiliary_heads": [TARGETS[j] for j in range(1, len(TARGETS)) if active[j]],
        "curves": snapshots,
        "fitting_constant": metrics(constant, held),
        "current_state_persistence": metrics(persistence, held),
        "last_update_loss": final_loss,
        "held_outcomes_used_for_fitting_or_epoch_selection": False,
        "original_critic_weights_unchanged": model.value_weights == parent.value_weights,
        "ordinary_PPO_eligible": False,
        "checkpoint_promoted": False,
    }
    return model, adam, saved, report


def mathematical_controls(parent: CachedContextModel, adam: Adam) -> dict[str, Any]:
    """Invented numerical labels test derivatives, never supply game supervision."""
    np = _numpy()
    rng = np.random.default_rng(20261021)
    x = rng.normal(0, 0.1, (8, parent.actor.dimension))
    target = rng.normal(0, 0.1, (8, len(TARGETS)))
    weights = np.full(target.shape, 1 / len(x))
    coefficients = np.asarray([1.0, *([0.25 / (len(TARGETS) - 1)] * (len(TARGETS) - 1))])
    heads = {
        "output": rng.normal(0, 0.03, (parent.actor.hidden_units, len(TARGETS) - 1)),
        "bias": np.zeros(len(TARGETS) - 1),
    }
    before, moments = parent.weights(), adam.as_dict()
    _, joint, joint_head, _ = loss_gradient(
        parent, heads, x, target, weights, coefficients, 0.0, 0.0001, True
    )
    _, control, control_head, _ = loss_gradient(
        parent, heads, x, target, weights, coefficients, 0.0, 0.0001, False
    )
    return_coefficients = coefficients.copy()
    return_coefficients[1:] = 0
    _, only_return, _, _ = loss_gradient(
        parent, heads, x, target, weights, return_coefficients, 0.0, 0.0001, True
    )
    if control != only_return or any(
        not np.array_equal(joint_head[k], control_head[k]) for k in heads
    ):
        raise ValueError("Return-only control leaked auxiliary gradients or changed head fitting")
    body = parent.actor.dimension * parent.actor.hidden_units + parent.actor.hidden_units
    if (
        not any(abs(joint[i] - control[i]) > 1e-10 for i in range(body))
        or joint[body:] != control[body:]
    ):
        raise ValueError("Auxiliary consequences must affect the shared hidden encoder only")
    errors = []
    for index in (
        0,
        parent.actor.dimension - 1,
        body - 1,
        body,
        parent.actor.parameter_count - 1,
        parent.parameter_count - 1,
    ):
        losses = []
        for sign in (-1, 1):
            values = list(before)
            values[index] += sign * 1e-5
            changed = cast(CachedContextModel, parent.with_weights(values))
            losses.append(
                loss_gradient(changed, heads, x, target, weights, coefficients, 0.0, 0.0001, True)[
                    0
                ]
            )
        numerical = (losses[1] - losses[0]) / 2e-5
        errors.append(abs(numerical - joint[index]))
    for key, position in (("output", (0, 0)), ("bias", (0,))):
        losses = []
        for sign in (-1, 1):
            changed_heads = {k: v.copy() for k, v in heads.items()}
            changed_heads[key][position] += sign * 1e-5
            losses.append(
                loss_gradient(
                    parent, changed_heads, x, target, weights, coefficients, 0.0, 0.0001, True
                )[0]
            )
        errors.append(abs((losses[1] - losses[0]) / 2e-5 - joint_head[key][position]))
    if max(errors) > 1e-6 or parent.weights() != before or adam.as_dict() != moments:
        raise ValueError("Consequence derivative or immutable parent control failed")
    return {
        "passed": True,
        "invented_labels_only_not_game_evidence": True,
        "finite_difference_coordinates": len(errors),
        "maximum_absolute_gradient_error": max(errors),
        "return_only_encoder_equals_return_loss_gradient": True,
        "auxiliary_heads_identically_fitted_in_both_arms": True,
        "auxiliary_gradient_reaches_hidden_encoder_only": True,
        "parent_weights_and_every_Adam_moment_unchanged": True,
    }
