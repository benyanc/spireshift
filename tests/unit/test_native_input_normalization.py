from __future__ import annotations

import copy
import random
from dataclasses import replace
from typing import Any

import pytest
from test_engine_neural import public, settings

from spireshift.engine_experience import verified_native_samples
from spireshift.engine_neural import (
    DIRECT,
    NativeActorCritic,
    encode_public_input,
    fit_native_round,
    initial_actor,
    initialize_native_critic,
    predict,
)
from spireshift.full_run_ppo_math import Adam
from spireshift.native_input_normalization import NONE, QUARTER, normalization_spec


def test_scaling_is_reversible_and_preserves_direct_actions_and_critic_inputs() -> None:
    p = public()
    rows, state = encode_public_input(p, 512)
    normalized, value_state = encode_public_input(p, 512, QUARTER)
    assert state == value_state and len(rows) == len(normalized) == len(p["candidates"])
    assert normalized != rows
    for original, scaled in zip(rows, normalized, strict=True):
        assert original == {i: v if i < len(DIRECT) else v * 4 for i, v in scaled.items()}
    assert encode_public_input(p, 512, NONE) == (rows, state)


@pytest.mark.parametrize("change", ["amounts", "cost", "target", "selection", "history", "memory"])
def test_named_amounts_costs_targets_choice_limits_and_memory_remain_distinct(change: str) -> None:
    p = public()
    original = encode_public_input(p, 512, QUARTER)
    if change == "amounts":
        p["context"]["player"]["statuses"][0]["amount"] = 7
        p["context"]["player"]["statuses"][1]["amount"] = 2
    elif change == "cost":
        p["candidates"][0]["subject"]["properties"]["cost"] = 0
    elif change == "target":
        p["candidates"][0]["arguments"] = [
            {
                "role": "target",
                "entity": {"public_slot": 2, "properties": {"hp": 1, "intents": [{"damage": 9}]}},
            }
        ]
    elif change == "selection":
        p["candidates"][0]["subject"]["properties"]["selection"] = {"minimum": 0, "maximum": 2}
    elif change == "history":
        p["candidates"][0]["history"] = {"card_reward_declined": True}
    else:
        p["context"]["memory"] = {"merchant_inspected": True}
    assert encode_public_input(p, 512, QUARTER) != original
    assert len(p["candidates"]) == 2 and p["candidates"][1]["verb"] == "skip"


def test_model_serialization_binds_normalization_and_keeps_legacy_identity() -> None:
    env = "sha256:711bbdc33754bec1338c89fac4b96d621ef4d8be32bae55a1ba190dc74c18f8c"
    legacy = initialize_native_critic(initial_actor(env))
    assert (
        legacy.model_id == "sha256:d0fabf53142e2927193409a683bf431c2eb7a5bb7bf6e2b8dcce2751b45f4449"
    )
    assert "input_normalization" not in legacy.as_dict()["actor"]
    new = initialize_native_critic(initial_actor(env, input_normalization=QUARTER))
    assert new.actor.genome == legacy.actor.genome and new.parameter_count == legacy.parameter_count
    assert new.model_id != legacy.model_id
    assert new.as_dict()["actor"]["input_normalization"] == normalization_spec(QUARTER)
    assert NativeActorCritic.from_mapping(legacy.as_dict()) == legacy
    assert NativeActorCritic.from_mapping(new.as_dict()) == new
    broken = new.as_dict()
    broken["actor"]["input_normalization"]["hashed_actor_scale"] = 0.5
    with pytest.raises(ValueError, match="normalization"):
        NativeActorCritic.from_mapping(broken)
    with pytest.raises(ValueError, match="normalization"):
        initial_actor(env, input_normalization="invented")


@pytest.mark.parametrize(
    "kind",
    [
        "combat_turn",
        "rest_site",
        "shop_inventory",
        "map_navigation",
        "card_selection",
        "card_bundle_selection",
        "card_reward_selection",
        "event_option",
        "reward_claim",
    ],
)
def test_normalized_on_policy_experience_reconstructs_and_remains_trainable(kind: str) -> None:
    p = public(kind)
    model = initialize_native_critic(
        initial_actor("sha256:" + "a" * 64, 128, 4, input_normalization=QUARTER)
    )
    # Actual sampled records, including exact behavior probabilities, precede fitting.
    case: dict[str, Any] = {
        "status": "terminal",
        "privileged_fixture": False,
        "recovered": False,
        "native_ending_evidence_agrees": True,
        "decisions": [
            {"public_input": p, "choice": predict(model, p, random.Random(i))} for i in range(16)
        ],
    }
    samples = verified_native_samples(case, model, 0.1, 1.0)
    samples = [replace(s, advantage=1.0 if s.action == 1 else -1.0) for s in samples]
    updated, _, _ = fit_native_round(
        model, Adam.zero(model.parameter_count), samples, settings(), 0
    )
    assert updated.actor.genome != model.actor.genome
    assert updated.actor.input_normalization == QUARTER
    assert NativeActorCritic.from_mapping(updated.as_dict()) == updated
    old = initialize_native_critic(initial_actor("sha256:" + "a" * 64, 128, 4))
    with pytest.raises(ValueError):
        verified_native_samples(case, old, 0.1, 1.0)


def test_normalization_does_not_relax_public_boundary_or_mutate_input() -> None:
    p = public()
    saved = copy.deepcopy(p)
    encode_public_input(p, 512, QUARTER)
    assert p == saved
    for key, value in [
        ("seed", "secret"),
        ("rng", [1]),
        ("entity_id", "opaque"),
        ("hp", float("nan")),
    ]:
        changed = copy.deepcopy(p)
        changed["context"]["player"][key] = value
        with pytest.raises(ValueError):
            encode_public_input(changed, 512, QUARTER)
