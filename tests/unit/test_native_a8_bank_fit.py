from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

import spireshift.native_a8_bank_fit as fit
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import NativeActor, NativeActorCritic
from spireshift.native_a8_bank_fit_inputs import datasets
from spireshift.native_action_context import CROSSED
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_input_normalization import QUARTER
from spireshift.native_win4_plan import PLAN


def model() -> CachedContextModel:
    dimension, hidden = 128, 4
    actor = NativeActor(
        "sha256:" + "a" * 64,
        dimension,
        hidden,
        (0.01,) * (dimension * hidden + 2 * hidden + dimension),
        QUARTER,
    )
    return CachedContextModel(
        NativeActorCritic(actor, (0.0,) * (dimension + 1)),
        CROSSED,
        "sha256:" + "b" * 64,
    )


def test_world_draws_are_equal_and_cycle_through_every_choice() -> None:
    choice = fit.Decision("combat_turn", (fit.Factor(({0: 1.0}, {}), 0, "input"),))
    worlds = {"long": (choice,) * 7, "short": (choice,) * 2}
    result = fit.world_schedule(worlds, 15, "bank")
    assert result == fit.world_schedule(dict(reversed(list(worlds.items()))), 15, "bank")
    assert set(result) == set(worlds)
    for name, positions in result.items():
        size = len(worlds[name])
        assert len(positions) == 15
        for start in range(0, 15 - size + 1, size):
            assert set(positions[start : start + size]) == set(range(size))
    assert len(fit.batch(worlds, result, 0)) == 2


def test_joint_gradient_counts_an_ordered_answer_once() -> None:
    first = fit.Factor(({0: 1.0}, {1: -0.5}), 1, "first")
    second = fit.Factor(({2: 1.0}, {3: 0.25}), 0, "second")
    third = fit.Factor(({4: 1.0}, {5: 0.2}), 1, "third")
    net = model()
    grouped = fit.Decision("card_selection", (first, second))
    plain = fit.Decision("combat_turn", (third,))
    loss, grad = fit.loss_gradient(net, (grouped, plain))
    separate = [
        fit.loss_gradient(net, (fit.Decision("combat_turn", (factor,)),))
        for factor in (first, second, third)
    ]
    assert loss == pytest.approx(sum(item[0] for item in separate) / 2)
    assert grad == pytest.approx(
        tuple(sum(values) / 2 for values in zip(*(item[1] for item in separate), strict=True))
    )
    assert grad[net.actor.parameter_count :] == (0.0,) * len(net.value_weights)


def factor(verb: str, prefix: list[int]) -> dict[str, Any]:
    public = {
        "context": {
            "interaction": {
                "kind": "card_selection",
                "content": {
                    "surface": {"selection_contract": PLAN, "answer_plan": {"selected": prefix}}
                },
            }
        },
        "candidates": [{"verb": verb}, {"verb": "cancel"}],
    }
    return {
        "public_input": public,
        "public_input_id": manifest_identifier(public),
        "action_index": 0,
        "family": "card_selection",
    }


def test_ordered_encoder_rejects_partial_or_standalone_prefixes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fit, "validate_student_input", lambda public: None)
    monkeypatch.setattr(fit, "encode", lambda public, model, score: (({0: 1.0}, {}), (0.0,)))
    label: dict[str, Any] = {
        "family": "card_selection",
        "decision_contract": PLAN,
        "label_weight": 1.0,
        "answer_factors": [factor("select", []), factor("confirm", [3])],
    }
    assert len(fit.encode_decision(label, model(), cast(Any, None)).factors) == 2
    label["answer_factors"].pop()
    with pytest.raises(ValueError, match="native commit"):
        fit.encode_decision(label, model(), cast(Any, None))
    with pytest.raises(ValueError, match="standalone"):
        fit.encode_decision(factor("select", []), model(), cast(Any, None))


def test_heldout_world_cannot_be_relabelled_as_fitting(tmp_path: Path) -> None:
    scenario = {"key": "held", "seed_pool": ["held-world"]}
    ctx = {
        "models": {2: model(), 3: model()},
        "config": {"plan": {"fit": [], "heldout": [scenario], "reserved_evaluation_seeds": []}},
        "historical_failures": [],
    }
    with pytest.raises(ValueError, match="withheld"):
        datasets(
            tmp_path,
            ctx,
            {"cases": [{"case": scenario}]},
            {"lessons": [{"scenario": scenario, "world": "held-world", "partition": "fit"}]},
        )
