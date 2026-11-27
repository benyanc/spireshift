"""Public-state value baselines and undiscounted, objective-preserving action credit.

The small ridge predictor is a training baseline, not an actor representation or
a win-probability head. Complete runs, never individual decisions, own its folds.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any

from spireshift.engine_neural import validate_public_input
from spireshift.neural_combat import _numpy
from spireshift.training_objective import TrainingScoreSpec

ENCODER = "native-public-progress-residual-value-v1"
FEATURES = (
    "bias",
    "floor_fraction",
    "completed_act_fraction",
    "hp_fraction",
    "max_hp_fraction",
    "gold_fraction",
    "deck_fraction",
    "relic_fraction",
    "potion_fraction",
    "combat",
    "rest",
    "shop",
    "selection",
    "map",
    "event",
    "combat_hp",
    "rest_hp",
    "combat_energy",
    "combat_block",
    "enemy_hp",
)


def _number(d: dict[str, Any], key: str) -> float:
    value = d.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f"Missing or nonfinite public value field: {key}")
    return float(value)


def _fraction(value: float, scale: float) -> float:
    return max(0.0, value) / (max(0.0, value) + scale)


def public_value_features(
    public: dict[str, Any], score: TrainingScoreSpec
) -> tuple[tuple[float, ...], float]:
    """Fixed bounded state features; no chosen action, seed, future or engine handles.

    A deliberately small critic can omit mechanics without restricting the actor,
    which still receives the full public entity graph and every legal candidate.
    """
    validate_public_input(public)
    context = public["context"]
    player, run = context["persistent"]["player"], context["persistent"]["run"]
    floor, act = _number(run, "floor"), _number(run, "act")
    if floor < 0 or not 1 <= act <= score.total_acts:
        raise ValueError("Public progress is outside the declared run")
    hp, maximum = _number(player, "hp"), _number(player, "max_hp")
    if maximum <= 0:
        raise ValueError("Public maximum HP must be positive")
    f, a = floor / (floor + score.floor_scale), (act - 1) / score.total_acts
    potential = score.loss_progress_weight * (act - 1 + f) / (score.total_acts + 1)
    interaction = context["interaction"]
    kind = interaction["kind"]
    combat, rest, shop = (float(kind == k) for k in ("combat_turn", "rest_site", "shop_inventory"))
    selection = float("selection" in kind)
    h = max(0.0, min(1.0, hp / maximum))
    content = interaction.get("content", {}).get("context", {})
    cp = content.get("player", {}) if combat else {}
    enemies = content.get("enemies", []) if combat else []
    deck = next(
        (r["content"]["card_count"] for r in context.get("reads", []) if r["kind"] == "run_deck"),
        None,
    )
    if type(deck) is not int or deck < 0:
        raise ValueError("Value features require the public deck count")
    # These counts/amounts are observed, not estimates of card/intent effects.
    values = (
        1.0,
        f,
        a,
        h,
        _fraction(maximum, 80),
        _fraction(_number(player, "gold"), 100),
        _fraction(deck, 20),
        _fraction(len(player["relics"]), 5),
        _fraction(len(player["potions"]), 2),
        combat,
        rest,
        shop,
        selection,
        float(kind == "map_navigation"),
        float(kind == "event_option"),
        combat * h,
        rest * h,
        _fraction(_number(cp, "energy"), 3) if combat else 0.0,
        _fraction(_number(cp, "block"), 20) if combat else 0.0,
        _fraction(math.fsum(_number(e, "hp") for e in enemies), 100),
    )
    return values, potential


@dataclass(frozen=True, slots=True)
class ValueRun:
    seed: int
    round: int
    target: float
    features: tuple[tuple[float, ...], ...]
    potentials: tuple[float, ...]
    behavior_values: tuple[float, ...]
    choices: tuple[int, ...]

    def __post_init__(self) -> None:
        n = len(self.features)
        if (
            not n
            or any(len(v) != len(FEATURES) for v in self.features)
            or any(len(v) != n for v in (self.potentials, self.behavior_values, self.choices))
            or not 0 <= self.target <= 1
            or not math.isfinite(self.target)
            or any(type(c) is not int or c < 1 for c in self.choices)
            or any(not math.isfinite(x) for row in self.features for x in row)
            or any(not math.isfinite(x) for x in (*self.potentials, *self.behavior_values))
            or not any(c > 1 for c in self.choices)
        ):
            raise ValueError("Invalid complete-run value examples")


def value_run(case: dict[str, Any], seed: int, round: int, score: TrainingScoreSpec) -> ValueRun:
    from spireshift.engine_experience import score_episode

    if (
        case.get("status") != "terminal"
        or case.get("privileged_fixture") is not False
        or case.get("recovered") is not False
        or case.get("native_ending_evidence_agrees") is not True
    ):
        raise ValueError("Action credit requires a clean complete run, never a partial game")
    rows = case["decisions"]
    encoded = [public_value_features(row["public_input"], score) for row in rows]
    return ValueRun(
        seed,
        round,
        score_episode(case, seed, score)["training_return"],
        tuple(x for x, _ in encoded),
        tuple(p for _, p in encoded),
        tuple(row["choice"]["value"] for row in rows),
        tuple(len(row["public_input"]["candidates"]) for row in rows),
    )


@dataclass(frozen=True, slots=True)
class ValueBaseline:
    kind: str
    regularization: float
    weights: tuple[float, ...]
    fitting_runs: tuple[int, ...]

    def predict(self, run: ValueRun) -> tuple[float, ...]:
        if run.seed in self.fitting_runs:
            raise ValueError("Baseline cannot supply credit for a run whose outcomes fitted it")
        if self.kind == "constant":
            return (self.weights[0],) * len(run.features)
        return tuple(
            max(
                0.0,
                min(1.0, phi + math.fsum(w * x for w, x in zip(self.weights, row, strict=True))),
            )
            for row, phi in zip(run.features, run.potentials, strict=True)
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "encoder_id": ENCODER,
            "features": list(FEATURES),
            "kind": self.kind,
            "regularization": self.regularization,
            "weights": list(self.weights),
            "fitting_runs": list(self.fitting_runs),
            "value_target": "declared_whole_episode_bootstrap_return",
            "terminal_victory_probability_available": False,
        }


def fit_baseline(runs: list[ValueRun], kind: str, regularization: float) -> ValueBaseline:
    if (
        not runs
        or len({r.seed for r in runs}) != len(runs)
        or kind not in {"constant", "public_residual_ridge"}
        or type(regularization) not in (int, float)
        or not math.isfinite(regularization)
        or regularization <= 0
    ):
        raise ValueError("Invalid whole-run baseline fit")
    ids = tuple(sorted(r.seed for r in runs))
    if kind == "constant":
        return ValueBaseline(
            kind, float(regularization), (math.fsum(r.target for r in runs) / len(runs),), ids
        )
    np = _numpy()
    gram, rhs = np.zeros((len(FEATURES), len(FEATURES))), np.zeros(len(FEATURES))
    for run in runs:
        mask = np.asarray(run.choices) > 1
        x = np.asarray(run.features)[mask]
        y = run.target - np.asarray(run.potentials)[mask]
        # Every whole game has equal mass, irrespective of its length or menu count.
        gram += x.T @ x / len(x) / len(runs)
        rhs += x.T @ y / len(x) / len(runs)
    penalty = np.eye(len(FEATURES)) * regularization
    penalty[0, 0] = 0  # fit the intercept, shrink only state-dependent coefficients
    weights = np.linalg.solve(gram + penalty, rhs)
    return ValueBaseline(kind, float(regularization), tuple(float(w) for w in weights), ids)


def fold_assignment(runs: list[ValueRun], folds: int, salt: str) -> dict[int, int]:
    if (
        type(folds) is not int
        or not 2 <= folds <= len(runs)
        or len({r.seed for r in runs}) != len(runs)
    ):
        raise ValueError("Cross-fitting requires distinct whole games and at least two folds")
    ordered = sorted(r.seed for r in runs)
    ordered.sort(key=lambda seed: hashlib.sha256(f"{salt}|{seed}".encode()).digest())
    return {seed: i % folds for i, seed in enumerate(ordered)}


def cross_fitted_predictions(
    runs: list[ValueRun], kind: str, regularization: float, folds: int, salt: str
) -> tuple[dict[int, tuple[float, ...]], list[dict[str, Any]]]:
    owners = fold_assignment(runs, folds, salt)
    predictions, reports = {}, []
    for fold in range(folds):
        fitting = [r for r in runs if owners[r.seed] != fold]
        held = [r for r in runs if owners[r.seed] == fold]
        baseline = fit_baseline(fitting, kind, regularization)
        predictions.update({r.seed: baseline.predict(r) for r in held})
        reports.append(
            {**baseline.as_dict(), "fold": fold, "predicted_runs": [r.seed for r in held]}
        )
    return predictions, reports


def prediction_metrics(
    runs: list[ValueRun], predictions: dict[int, tuple[float, ...]]
) -> dict[str, Any]:
    """Equal-game weighted moments on decisions offering an actual choice."""
    if set(predictions) != {r.seed for r in runs}:
        raise ValueError("Prediction/game denominator differs")
    rows: list[tuple[float, float, float]] = []
    for run in runs:
        values = predictions[run.seed]
        if len(values) != len(run.choices) or any(not math.isfinite(v) for v in values):
            raise ValueError("Nonfinite or incomplete predictions")
        n = sum(c > 1 for c in run.choices)
        rows.extend(
            (run.target, v, 1 / n / len(runs))
            for c, v in zip(run.choices, values, strict=True)
            if c > 1
        )
    mean = math.fsum(y * w for y, _, w in rows)
    residual = math.fsum((y - v) * w for y, v, w in rows)
    variance = math.fsum((y - mean) ** 2 * w for y, _, w in rows)
    residual_variance = math.fsum((y - v - residual) ** 2 * w for y, v, w in rows)
    return {
        "independent_runs": len(runs),
        "choice_bearing_decisions": len(rows),
        "mse": math.fsum((y - v) ** 2 * w for y, v, w in rows),
        "explained_variance": 1 - residual_variance / variance if variance > 0 else None,
        "mean_prediction_error": -residual,
        "residual_variance": residual_variance,
        "weighting": "equal_complete_run_then_equal_choice_bearing_decision",
    }


def redistribute_terminal_return(target: float, potentials: tuple[float, ...]) -> tuple[float, ...]:
    """Gamma=1 potential differences, absorbing terminal potential exactly zero.

    Sum = original return - initial potential. Returning to a menu or declining a
    reward cannot mint reward; HP/resources are not extra objectives. This does
    not make noisy Monte Carlo credit informative by itself.
    """
    if (
        not potentials
        or not 0 <= target <= 1
        or not math.isfinite(target)
        or any(not math.isfinite(p) or not 0 <= p < 1 for p in potentials)
    ):
        raise ValueError("Expected finite complete-episode return and public potentials")
    following = (*potentials[1:], 0.0)
    return tuple(
        (target if i == len(potentials) - 1 else 0.0) + q - p
        for i, (p, q) in enumerate(zip(potentials, following, strict=True))
    )


def action_advantages(
    target: float, potentials: tuple[float, ...], values: tuple[float, ...], trace_lambda: float
) -> tuple[float, ...]:
    """GAE with undiscounted terminal objective; lambda<1 is explicitly biased.

    Values predict original return. Transform both rewards AND values into the
    potential-shaped coordinates. Lambda=1 must recover target-value exactly.
    No truncation bootstrap or cross-run transition is accepted here.
    """
    rewards = redistribute_terminal_return(target, potentials)
    if (
        len(values) != len(rewards)
        or any(not math.isfinite(v) for v in values)
        or not 0 <= trace_lambda <= 1
    ):
        raise ValueError("Invalid complete-run values or trace lambda")
    residual = [v - p for v, p in zip(values, potentials, strict=True)]
    result, following, credit = [], 0.0, 0.0
    for i in reversed(range(len(rewards))):
        credit = rewards[i] + following - residual[i] + trace_lambda * credit
        result.append(credit)
        following = residual[i]
    return tuple(reversed(result))
