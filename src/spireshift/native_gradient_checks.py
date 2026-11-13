"""Whole-game, behavior-checkpoint gradient diagnostics; never an optimizer.

Independent groups fit their own nuisance predictors and advantage normalization.
Repeated partitions describe the observed finite game pool, not new replications.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import NativeActorCritic, encode_public_input
from spireshift.full_run_policy import dense_features
from spireshift.full_run_ppo_math import Sample, log_softmax, loss_gradient
from spireshift.native_value_credit import ValueRun, cross_fitted_predictions, value_run
from spireshift.neural_combat import _numpy
from spireshift.training_objective import TrainingScoreSpec


@dataclass(frozen=True)
class GameGradient:
    scope_id: str
    run: ValueRun
    log_probability_jacobian: Any
    entropy_gradient_sum: Any

    def __post_init__(self) -> None:
        np = _numpy()
        j, e = self.log_probability_jacobian, self.entropy_gradient_sum
        if (
            not self.scope_id.startswith("sha256:")
            or j.ndim != 2
            or j.shape[0] != len(self.run.choices)
            or e.shape != (j.shape[1],)
            or not np.isfinite(j).all()
            or not np.isfinite(e).all()
        ):
            raise ValueError("Invalid complete-game gradient cache")
        j.setflags(write=False)
        e.setflags(write=False)


def _backprop(x: Any, hidden: Any, output: Any, dz: Any) -> Any:
    np = _numpy()
    dh = dz[:, None] * output * (1 - hidden * hidden)
    return np.concatenate(((dh.T @ x).ravel(), dh.sum(axis=0), hidden.T @ dz, x.T @ dz))


def game_gradient(
    model: NativeActorCritic,
    case: dict[str, Any],
    seed: int,
    round: int,
    score: TrainingScoreSpec,
    temperature: float,
    scope_id: str,
) -> tuple[GameGradient, list[Sample]]:
    """Exact score-function/entropy derivatives, reconstructing every saved choice."""
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("Invalid behavior temperature")
    run = value_run(case, seed, round, score)
    np = _numpy()
    rows: list[dict[int, float]] = []
    states: list[tuple[float, ...]] = []
    menus: list[tuple[dict[int, float], ...]] = []
    choices: list[dict[str, Any]] = []
    model_id = model.model_id
    for d in case["decisions"]:
        public, c = d["public_input"], d["choice"]
        encoded, state = encode_public_input(
            public, model.actor.dimension, model.actor.input_normalization
        )
        if (
            c.get("model_id") != model_id
            or c.get("behavior") != "sampled_softmax"
            or c.get("temperature") != temperature
            or c.get("public_input_id") != manifest_identifier(public)
            or type(c.get("action_index")) is not int
            or not 0 <= c["action_index"] < len(encoded)
            or not math.isclose(c["value"], model.value(state), rel_tol=0, abs_tol=1e-10)
        ):
            raise ValueError("Gradient input is stale or crosses behavior/public ownership")
        rows.extend(encoded)
        menus.append(encoded)
        states.append(state)
        choices.append(c)
    x = dense_features(tuple(rows), model.actor.dimension)
    w, b, output, linear = model.actor.unpack()
    hidden = np.tanh(x @ w.T + b)
    logits = hidden @ output + x @ linear
    jacobian = np.zeros((len(menus), model.actor.parameter_count))
    entropy_dz = np.zeros(len(rows))
    samples, offset = [], 0
    for i, (menu, state, c) in enumerate(zip(menus, states, choices, strict=True)):
        n = len(menu)
        logp = np.asarray(log_softmax(logits[offset : offset + n], temperature))
        selected = c["action_index"]
        if not math.isclose(c["log_probability"], float(logp[selected]), rel_tol=0, abs_tol=1e-10):
            raise ValueError("Saved gradient behavior probability does not reconstruct")
        p = np.exp(logp)
        dz = -p.copy()
        dz[selected] += 1
        jacobian[i] = _backprop(
            x[offset : offset + n], hidden[offset : offset + n], output, dz / temperature
        )
        h = -float(p @ logp)
        entropy_dz[offset : offset + n] = -p * (logp + h) / temperature
        samples.append(Sample(menu, state, selected, float(logp[selected]), run.target, 0.0))
        offset += n
    return (
        GameGradient(scope_id, run, jacobian, _backprop(x, hidden, output, entropy_dz)),
        samples,
    )


def require_one_cohort(games: list[GameGradient]) -> None:
    if (
        len(games) < 4
        or len({g.run.seed for g in games}) != len(games)
        or len({g.scope_id for g in games}) != 1
        or len({g.run.round for g in games}) != 1
        or len({g.log_probability_jacobian.shape[1] for g in games}) != 1
    ):
        raise ValueError("Batch needs distinct complete games from one behavior scope/round")


@dataclass(frozen=True)
class BatchGradient:
    data: Any
    entropy: Any
    total: Any
    advantages: dict[int, tuple[float, ...]]
    folds: list[dict[str, Any]]
    summary: dict[str, Any]


def cosine(a: Any, b: Any) -> float | None:
    np = _numpy()
    norm = float(np.linalg.norm(a) * np.linalg.norm(b))
    return max(-1.0, min(1.0, float(a @ b) / norm)) if norm > 1e-24 else None


def batch_gradient(games: list[GameGradient], entropy_coefficient: float) -> BatchGradient:
    """Ascent gradient of the production loss at behavior, before Adam/reuse/clipping.

    Includes production's decision-weighted centering/std (also forced menus),
    full-return cross-fitting and temperature. No other group's outcomes enter.
    """
    require_one_cohort(games)
    if not math.isfinite(entropy_coefficient) or entropy_coefficient < 0:
        raise ValueError("Invalid exploration coefficient")
    np = _numpy()
    runs = sorted((g.run for g in games), key=lambda r: r.seed)
    values, folds = cross_fitted_predictions(
        runs, "public_residual_ridge", 0.001, 4, "native-whole-run-value-crossfit-v1"
    )
    advantages = {r.seed: tuple(r.target - v for v in values[r.seed]) for r in runs}
    a = np.asarray([v for g in games for v in advantages[g.run.seed]])
    mean, std = float(a.mean()), float(a.std())
    denominator = max(std, 1e-8)
    contributions = np.asarray(
        [
            (np.asarray(advantages[g.run.seed]) - mean)
            @ g.log_probability_jacobian
            / denominator
            / len(a)
            for g in games
        ]
    )
    data = contributions.sum(axis=0)
    entropy = entropy_coefficient * sum(g.entropy_gradient_sum for g in games) / len(a)
    dn, en = float(np.linalg.norm(data)), float(np.linalg.norm(entropy))
    norms = np.linalg.norm(contributions, axis=1)
    norm_sum = float(norms.sum())
    summary = {
        "independent_games": len(games),
        "decisions": len(a),
        "choice_bearing_decisions": sum(sum(c > 1 for c in g.run.choices) for g in games),
        "raw_advantage_mean": mean,
        "raw_advantage_std": std,
        "data_gradient_norm": dn,
        "entropy_gradient_norm": en,
        "entropy_to_data_norm_ratio": en / dn if dn > 1e-12 else None,
        "data_vs_total_cosine": cosine(data, data + entropy),
        "largest_game_contribution_norm_share": float(norms.max()) / norm_sum if norm_sum else None,
        "contribution_cancellation_ratio": dn / norm_sum if norm_sum else None,
        "baseline_fits_only_own_group": True,
        "normalization_fits_only_own_group": True,
    }
    return BatchGradient(data, entropy, data + entropy, advantages, folds, summary)


def production_gradient_check(
    model: NativeActorCritic,
    games: list[GameGradient],
    samples: list[Sample],
    settings: dict[str, Any],
) -> dict[str, Any]:
    """Independent loss implementation check; no optimizer or weight change."""
    result = batch_gradient(games, settings["entropy_coefficient"])
    if len(samples) != sum(len(g.run.choices) for g in games):
        raise ValueError("Reference sample denominator differs")
    prepared, offset = [], 0
    for game in games:
        for a in result.advantages[game.run.seed]:
            s = samples[offset]
            if s.target != game.run.target:
                raise ValueError("Reference sample game order differs")
            prepared.append(
                replace(
                    s,
                    advantage=(a - result.summary["raw_advantage_mean"])
                    / max(result.summary["raw_advantage_std"], 1e-8),
                )
            )
            offset += 1
    _, gradient, _ = loss_gradient(
        cast(Any, model),
        prepared,
        clip=settings["clip"],
        entropy_coefficient=settings["entropy_coefficient"],
        value_coefficient=settings["value_coefficient"],
        temperature=settings["temperature"],
    )
    np = _numpy()
    error = float(
        np.max(np.abs(result.total + np.asarray(gradient[: model.actor.parameter_count])))
    )
    if error > 1e-9:
        raise ValueError("Whole-game ascent gradient differs from production PPO")
    return {"passed": True, "maximum_absolute_actor_gradient_error": error, "optimizer_steps": 0}


def _describe(values: list[float | None]) -> dict[str, Any]:
    np = _numpy()
    present = [v for v in values if v is not None]
    return {
        "partitions": len(values),
        "undefined_zero_norm_pairs": len(values) - len(present),
        "median": float(np.median(present)) if present else None,
        "p10": float(np.quantile(present, 0.1)) if present else None,
        "p90": float(np.quantile(present, 0.9)) if present else None,
        "opposing_fraction": sum(v < 0 for v in present) / len(present) if present else None,
    }


def batch_size_checks(
    games: list[GameGradient], sizes: list[int], partitions: int, salt: int, entropy: float
) -> dict[str, Any]:
    require_one_cohort(games)
    if (
        not sizes
        or sizes != sorted(set(sizes))
        or any(type(n) is not int or n < 4 for n in sizes)
        or type(partitions) is not int
        or not 8 <= partitions <= 128
        or type(salt) is not int
    ):
        raise ValueError("Freeze finite whole-game sizes/partitions")
    games = sorted(games, key=lambda g: g.run.seed)
    curves: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    for n in sizes:
        if 2 * n > len(games):
            unsupported.append({"games_per_group": n, "reason": "needs_two_disjoint_groups"})
            continue
        rng = random.Random(salt + n)
        pairs: list[dict[str, Any]] = []
        for _ in range(partitions):
            indices = list(range(len(games)))
            rng.shuffle(indices)
            groups = [[games[i] for i in indices[start : start + n]] for start in (0, n)]
            a, b = (batch_gradient(group, entropy) for group in groups)
            pairs.append(
                {
                    "groups": [[g.run.seed for g in group] for group in groups],
                    "data_cosine": cosine(a.data, b.data),
                    "total_cosine": cosine(a.total, b.total),
                    "entropy_cosine": cosine(a.entropy, b.entropy),
                    "data_norms": [
                        a.summary["data_gradient_norm"],
                        b.summary["data_gradient_norm"],
                    ],
                }
            )
        curves.append(
            {
                "games_per_group": n,
                "data_agreement": _describe([p["data_cosine"] for p in pairs]),
                "total_agreement": _describe([p["total_cosine"] for p in pairs]),
                "entropy_agreement": _describe([p["entropy_cosine"] for p in pairs]),
                "partition_details": pairs,
            }
        )
    return {
        "available_independent_games": len(games),
        "full_pool": batch_gradient(games, entropy).summary,
        "disjoint_group_curves": curves,
        "unmeasured_sizes": unsupported,
        "groups_share_no_games_or_fitted_baselines_or_normalization": True,
        "resplits_are_correlated_finite_pool_descriptions": True,
        "population_confidence_intervals": False,
        "maximum_measured_games_per_group": max(
            (c["games_per_group"] for c in curves), default=None
        ),
        "larger_than_32_game_groups_observed": any(c["games_per_group"] > 32 for c in curves),
        "optimizer_or_adam_steps": 0,
        "policy_improvement_or_readiness_established": False,
    }
