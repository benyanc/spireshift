from __future__ import annotations

import copy
import random
from dataclasses import replace
from typing import Any

import pytest
from test_engine_neural import model, settings
from test_native_value_credit import public, score

from spireshift.engine_neural import predict
from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import log_softmax
from spireshift.native_gradient_checks import (
    GameGradient,
    batch_gradient,
    batch_size_checks,
    cosine,
    game_gradient,
    production_gradient_check,
    require_one_cohort,
)
from spireshift.neural_combat import _numpy

SCOPE = "sha256:" + "b" * 64


def case(seed: int) -> dict[str, Any]:
    m = model()
    decisions = []
    for n in (2, 1, 3):
        p = public()
        p["context"]["persistent"]["player"]["hp"] = 10 + seed
        p["candidates"] = [
            {
                "verb": "select",
                "label": f"Option {i}",
                "arguments": [],
                "subject": {"properties": {"cost": i, "damage": i + seed}},
            }
            for i in range(n)
        ]
        decisions.append({"public_input": p, "choice": predict(m, p, random.Random(seed + n), 0.8)})
    return {
        "status": "terminal",
        "recovered": False,
        "privileged_fixture": False,
        "native_ending_evidence_agrees": True,
        "victory": False,
        "completed_acts": 0,
        "maximum_floor": 3 + seed % 5,
        "cpu_seconds": 0.1,
        "decisions": decisions,
    }


def pool() -> tuple[list[GameGradient], list[Any]]:
    games, samples = [], []
    for seed in range(1, 9):
        g, s = game_gradient(model(), case(seed), seed, 1, score(), 0.8, SCOPE)
        games.append(g)
        samples.extend(s)
    return games, samples


def test_independent_game_kernel_reconstructs_actual_ppo_including_forced_choices() -> None:
    games, samples = pool()
    m = model()
    before = m.as_dict()
    config = {**settings(), "temperature": 0.8}
    assert production_gradient_check(m, games, samples, config)["passed"]
    r = batch_gradient(games, config["entropy_coefficient"])
    assert r.summary["independent_games"] == 8
    assert r.summary["decisions"] == 24 and r.summary["choice_bearing_decisions"] == 16
    assert m.as_dict() == before
    np = _numpy()
    assert np.array_equal(games[0].log_probability_jacobian[1], np.zeros(m.actor.parameter_count))


def test_log_probability_derivatives_match_finite_differences_in_every_actor_layer() -> None:
    m, c = model(), case(3)
    g, _ = game_gradient(m, c, 3, 1, score(), 0.8, SCOPE)
    p, chosen = c["decisions"][0]["public_input"], c["decisions"][0]["choice"]["action_index"]
    from spireshift.engine_neural import encode_public_input

    rows, _ = encode_public_input(p, m.actor.dimension)
    for i in (0, 13, 512, 515, 516, 519, 520, 525, 647):
        weights = list(m.actor.genome)
        weights[i] += 1e-5
        plus = replace(m.actor, genome=tuple(weights))
        weights[i] -= 2e-5
        minus = replace(m.actor, genome=tuple(weights))
        a = log_softmax(score_features(plus, rows), 0.8)[chosen]  # type: ignore[arg-type]
        b = log_softmax(score_features(minus, rows), 0.8)[chosen]  # type: ignore[arg-type]
        assert g.log_probability_jacobian[0, i] == pytest.approx((a - b) / 2e-5, abs=1e-8)


def test_group_credit_and_normalization_cannot_learn_other_groups_outcomes() -> None:
    games, _ = pool()
    left, right = games[:4], games[4:]
    a, b = batch_gradient(left, 0.01), batch_gradient(right, 0.01)
    for group, result in ((left, a), (right, b)):
        own = {g.run.seed for g in group}
        for fold in result.folds:
            assert set(fold["fitting_runs"]) | set(fold["predicted_runs"]) == own
            assert not set(fold["fitting_runs"]) & set(fold["predicted_runs"])
    changed = [replace(g, run=replace(g.run, target=0.9)) for g in right]
    batch_gradient(changed, 0.01)
    np = _numpy()
    assert np.array_equal(a.data, batch_gradient(left, 0.01).data)


@pytest.mark.parametrize("bad", ["duplicate", "scope", "round", "small"])
def test_independent_game_units_reject_duplicate_or_mixed_policy_rounds(bad: str) -> None:
    games, _ = pool()
    if bad == "duplicate":
        games[1] = games[0]
    elif bad == "scope":
        games[1] = replace(games[1], scope_id="sha256:" + "c" * 64)
    elif bad == "round":
        games[1] = replace(games[1], run=replace(games[1].run, round=2))
    else:
        games = games[:3]
    with pytest.raises(ValueError, match="one behavior"):
        require_one_cohort(games)


def test_batch_curve_groups_are_disjoint_and_do_not_extrapolate_beyond_available_games() -> None:
    games, _ = pool()
    result = batch_size_checks(games, [4, 8, 16, 32], 8, 17, 0.01)
    assert result["maximum_measured_games_per_group"] == 4
    assert [r["games_per_group"] for r in result["unmeasured_sizes"]] == [8, 16, 32]
    assert not result["larger_than_32_game_groups_observed"]
    assert result["available_independent_games"] == 8
    for pair in result["disjoint_group_curves"][0]["partition_details"]:
        a, b = map(set, pair["groups"])
        assert len(a) == len(b) == 4 and not a & b
    assert result == batch_size_checks(list(reversed(games)), [4, 8, 16, 32], 8, 17, 0.01)


def test_duplicate_decisions_do_not_create_additional_independent_games() -> None:
    games, _ = pool()
    np = _numpy()
    doubled = [
        replace(
            g,
            run=replace(
                g.run,
                features=g.run.features * 2,
                potentials=g.run.potentials * 2,
                behavior_values=g.run.behavior_values * 2,
                choices=g.run.choices * 2,
            ),
            log_probability_jacobian=np.tile(g.log_probability_jacobian, (2, 1)),
            entropy_gradient_sum=g.entropy_gradient_sum * 2,
        )
        for g in games
    ]
    a, b = batch_gradient(games, 0.01), batch_gradient(doubled, 0.01)
    assert a.summary["independent_games"] == b.summary["independent_games"] == 8
    assert b.summary["decisions"] == 2 * a.summary["decisions"]
    assert np.allclose(a.total, b.total, rtol=0, atol=1e-12)


def test_aligned_opposed_zero_and_entropy_dominated_directions_are_distinguished() -> None:
    np = _numpy()
    x = np.asarray([1.0, 0])
    assert cosine(x, x) == 1 and cosine(x, -x) == -1
    assert cosine(x, x * 0) is None
    entropy = np.asarray([0.0, 10])
    assert cosine(x, -x) < 0  # type: ignore[operator]
    assert cosine(x + entropy, -x + entropy) > 0.9  # type: ignore[operator]


@pytest.mark.parametrize("bad", ["stale", "likelihood", "privileged", "partial", "private"])
def test_saved_gradient_rejects_invalid_behavior_and_public_boundary(bad: str) -> None:
    c = copy.deepcopy(case(1))
    if bad == "stale":
        c["decisions"][0]["choice"]["model_id"] = "wrong"
    elif bad == "likelihood":
        c["decisions"][0]["choice"]["log_probability"] += 0.01
    elif bad == "privileged":
        c["privileged_fixture"] = True
    elif bad == "partial":
        c["status"] = "failed"
    else:
        c["decisions"][0]["public_input"]["context"]["seed"] = "private"
    with pytest.raises(ValueError):
        game_gradient(model(), c, 1, 1, score(), 0.8, SCOPE)
