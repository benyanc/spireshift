"""Portable native input/experience controls; no licensed data or game processes."""

from __future__ import annotations

import copy
import math
import random
from pathlib import Path
from typing import Any

import pytest

from spireshift.engine_experience import (
    read_native_episode,
    save_native_episode,
    verified_native_samples,
)
from spireshift.engine_neural import (
    NativeActorCritic,
    encode_public_input,
    fit_native_round,
    initial_actor,
    initialize_native_critic,
    predict,
)
from spireshift.full_run_ppo_math import Adam, Sample


def public(kind: str = "combat_turn") -> dict[str, Any]:
    return {
        "schema_version": "actual-engine-public-entity-graph-v1",
        "context": {
            "interaction": {"kind": kind},
            "player": {
                "hp": 20,
                "statuses": [{"name": "Strength", "amount": 2}, {"name": "Dexterity", "amount": 7}],
            },
        },
        "candidates": [
            {
                "verb": "select",
                "label": "First",
                "subject": {
                    "public_slot": 1,
                    "properties": {"name": "Card", "cost": 1, "stats": {"damage": 6}},
                },
                "arguments": [],
            },
            {"verb": "skip", "label": "Skip", "subject": None, "arguments": []},
        ],
    }


def model() -> NativeActorCritic:
    return initialize_native_critic(initial_actor("sha256:" + "a" * 64, 128, 4))


def settings() -> dict[str, Any]:
    return {
        "epochs": 6,
        "minibatch_decisions": 8,
        "clip": 0.2,
        "temperature": 1.0,
        "entropy_coefficient": 0.01,
        "value_coefficient": 0.5,
        "actor_learning_rate": 0.005,
        "value_learning_rate": 0.005,
        "gradient_clip": 1.0,
        "target_kl": 0.1,
    }


def test_native_serialization_is_separate_and_content_bound() -> None:
    m = model()
    assert NativeActorCritic.from_mapping(m.as_dict()) == m
    broken = m.as_dict()
    broken["actor"]["encoder_id"] = "public-full-run-complete-choices-v2"
    with pytest.raises(ValueError):
        NativeActorCritic.from_mapping(broken)
    assert m.as_dict()["terminal_victory_probability_available"] is False


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
def test_every_family_can_learn_to_choose_skip_over_an_initial_preference(kind: str) -> None:
    m = model()
    p = public(kind)
    initial = predict(m, p, random.Random(0))
    rows, state = encode_public_input(p, m.actor.dimension)
    from typing import cast

    from spireshift.full_run_policy import FullRunModel, score_features
    from spireshift.full_run_ppo_math import log_softmax

    logs = log_softmax(score_features(cast(FullRunModel, m.actor), rows))
    samples = [
        Sample(rows, state, i % 2, logs[i % 2], float(i % 2), 1 if i % 2 else -1) for i in range(16)
    ]
    updated, opt, report = fit_native_round(m, Adam.zero(m.parameter_count), samples, settings(), 0)
    after = predict(updated, p, random.Random(0))
    # Compare the probability of the same candidate; the seeded draw may change.
    after_rows, _ = encode_public_input(p, updated.actor.dimension)
    after_logs = log_softmax(score_features(cast(FullRunModel, updated.actor), after_rows))
    assert after_logs[1] > logs[1]
    assert updated.actor.genome != m.actor.genome and updated.value_weights != m.value_weights
    assert opt.steps > 0 and report["all_actor_layers_and_decision_types_mutable"]
    assert initial["model_id"] != after["model_id"]


def test_named_amounts_target_properties_costs_and_optional_history_do_not_collapse() -> None:
    p = public()
    rows, state = encode_public_input(p, 512)
    for field, value in (
        ("cost", 0),
        ("stats", {"damage": 9}),
        ("selection", {"minimum": 1, "maximum": 3}),
    ):
        changed = copy.deepcopy(p)
        changed["candidates"][0]["subject"]["properties"][field] = value
        assert encode_public_input(changed, 512)[0] != rows
    changed = copy.deepcopy(p)
    changed["context"]["player"]["statuses"][0]["amount"] = 7
    changed["context"]["player"]["statuses"][1]["amount"] = 2
    assert encode_public_input(changed, 512)[1] != state
    changed = copy.deepcopy(p)
    changed["candidates"][0]["history"] = {"card_reward_declined": True}
    assert encode_public_input(changed, 512)[0] != rows


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("seed", "HIDDEN"),
        ("rng", [1]),
        ("session", {"runtime_instance_id": "ID"}),
        ("entity_id", "opaque-runtime-handle"),
        ("target_entity_ids", ["unresolved"]),
        ("hp", float("nan")),
    ],
)
def test_private_transport_opaque_or_nonfinite_input_is_rejected(key: str, value: Any) -> None:
    p = public()
    p["context"]["player"][key] = value
    with pytest.raises(ValueError):
        encode_public_input(p, 128)


def case() -> dict[str, Any]:
    m = model()
    p = public()
    return {
        "status": "terminal",
        "privileged_fixture": False,
        "recovered": False,
        "native_ending_evidence_agrees": True,
        "decisions": [{"public_input": p, "choice": predict(m, p, random.Random(1))}],
    }


def test_experience_seals_bytes_and_reconstructs_behavior(tmp_path: Path) -> None:
    path = tmp_path / "case.json"
    c = case()
    binding = {"model_id": model().model_id, "seed_manifest_id": "frozen"}
    save_native_episode(path, c, binding)
    saved = read_native_episode(path, binding)
    samples = verified_native_samples(saved, model(), 0.1, 1)
    assert len(samples) == 1 and math.isfinite(samples[0].old_log_probability)
    with pytest.raises(ValueError):
        read_native_episode(path, {**binding, "model_id": "other"})
    with path.with_suffix(".jsonl.gz").open("ab") as stream:
        stream.write(b"corrupted")
    with pytest.raises(ValueError, match="bytes"):
        read_native_episode(path, binding)


@pytest.mark.parametrize(
    "change", ["greedy", "probability", "model", "recovery", "fixture", "partial"]
)
def test_stale_or_unfit_experience_never_supplies_ppo_targets(change: str) -> None:
    c = case()
    choice = c["decisions"][0]["choice"]
    if change == "greedy":
        choice["behavior"] = "greedy"
    elif change == "probability":
        choice["log_probability"] += 0.1
    elif change == "model":
        choice["model_id"] = "another"
    elif change == "recovery":
        c["recovered"] = True
    elif change == "fixture":
        c["privileged_fixture"] = True
    elif change == "partial":
        c["status"] = "truncated"
    with pytest.raises(ValueError):
        verified_native_samples(c, model(), 0.1, 1)
