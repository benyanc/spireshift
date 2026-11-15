from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.core.types import DecisionType, LegalAction, Observation
from spireshift.production_models import ProductionBaseModel
from spireshift.representations import CompositionalModelInput, build_model_input
from spireshift.starting_options import (
    StartingOptionHead,
    load_starting_option_config,
    option_coverage,
    starting_option_ids,
)


def _input(
    *,
    options: tuple[int, ...] = (5, 9, 9000),
    indices: tuple[int, ...] = (0, 1, 2),
    overrides: dict[str, Any] | None = None,
    phase: str = "ancient",
) -> CompositionalModelInput:
    public = {
        "floor": 1,
        "act": "underdocks",
        "player_hp": 64,
        "player_max_hp": 80,
        "gold": 99,
        "neow_options": list(options),
        "deck": [{"card_id": 3, "upgraded": False}, {"card_id": 7, "upgraded": True}],
        "relic_slots": [{"relic_id": 11, "used_up": False}],
        **(overrides or {}),
    }
    observation = Observation(
        "observation-v1",
        MockSpireEnvironment.patch_id,
        DecisionType.EVENT if phase == "ancient" else DecisionType.COMBAT,
        public,
        hashlib.sha256(
            json.dumps(public, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    )
    actions = tuple(
        LegalAction(
            f"evangambit:{phase}:{index}",
            f"evangambit_{phase}",
            {"phase": phase, "action_index": index},
        )
        for index in indices
    )
    return build_model_input(MockSpireEnvironment.ruleset, observation, actions)


def test_option_identity_follows_both_menu_and_candidate_permutations() -> None:
    head = StartingOptionHead(4096, (5, 9, 9000))
    original = head.features(_input())
    moved = head.features(_input(options=(9000, 5, 9)))
    assert moved == (original[2], original[0], original[1])
    reordered = head.features(_input(indices=(2, 0, 1)))
    assert reordered == (original[2], original[0], original[1])
    head.weights = dict(original[2])
    scores = head.scores(_input())
    assert head.scores(_input(options=(9000, 5, 9))) == (scores[2], scores[0], scores[1])
    assert head.scores(_input(indices=(2, 0, 1))) == (scores[2], scores[0], scores[1])


def test_ids_are_categories_and_unknown_ids_share_an_explicit_fallback() -> None:
    head = StartingOptionHead(65536, (5, 9, 9000))
    values = head.features(_input())
    assert values[1] != values[2]
    # The number 9000 has exactly the same feature magnitudes as 9; it is not a strength.
    assert sorted(abs(value) for value in values[1].values()) == sorted(
        abs(value) for value in values[2].values()
    )
    unknown = StartingOptionHead(4096, (5, 9))
    assert unknown.features(_input())[2] == unknown.features(_input(options=(5, 9, 8000)))[2]
    coverage = option_coverage(((23, _input()),), unknown)
    assert coverage["unknown_option_ids"] == [9000]
    assert coverage["unknown_candidate_options"] == 1


@pytest.mark.parametrize(
    "options,indices,overrides",
    [
        ((5, 9), (0, 1), {}),
        ((5, 0, 9), (0, 1, 2), {}),
        ((5, 9, 9000), (0, 3), {}),
        ((5, 9, 9000), (0, 0), {}),
        ((5, 9, 9000), (0, 1), {"player_max_hp": 0}),
        ((5, 9, 9000), (0, 1), {"gold": -1}),
    ],
)
def test_malformed_menu_dispatch_or_context_fails_closed(
    options: tuple[int, ...], indices: tuple[int, ...], overrides: dict[str, Any]
) -> None:
    with pytest.raises(ValueError):
        StartingOptionHead(4096, (5, 9, 9000)).features(
            _input(options=options, indices=indices, overrides=overrides)
        )


def test_payload_cannot_disguise_an_ancient_action_as_another_phase() -> None:
    representation = _input()
    candidate = representation.candidates[0]
    fields = tuple(
        replace(feature, categorical_value="combat") if feature.path == ("phase",) else feature
        for feature in candidate.features
    )
    disguised = replace(
        representation,
        candidates=(replace(candidate, features=fields), *representation.candidates[1:]),
    )
    with pytest.raises(ValueError, match="phases"):
        starting_option_ids(disguised)


def test_only_visible_typed_context_enters_the_residual() -> None:
    head = StartingOptionHead(4096, (5, 9, 9000))
    first = _input(overrides={"observation_vector": [1, 2, 3]})
    second = _input(overrides={"observation_vector": [900000, 0, -7]})
    assert head.features(first) == head.features(second)
    assert head.features(first) != head.features(_input(overrides={"player_hp": 20}))
    with pytest.raises(ValueError, match="Privileged"):
        _input(overrides={"rng_state": 99})


def test_deck_and_relic_inventory_are_bags_and_keep_categorical_ids() -> None:
    head = StartingOptionHead(4096, (5, 9, 9000))
    old = _input()
    swapped = _input(
        overrides={
            "deck": [{"card_id": 7, "upgraded": True}, {"card_id": 3, "upgraded": False}],
            "relic_slots": [{"relic_id": 11, "used_up": False}],
        }
    )
    assert head.features(old) == head.features(swapped)
    assert head.features(old) != head.features(
        _input(overrides={"relic_slots": [{"relic_id": 12, "used_up": False}]})
    )


def test_zero_residual_exactly_preserves_parent_and_other_phases() -> None:
    model = ProductionBaseModel(128, 256, 32, (3,))
    model.policy_weights = {1: 0.7, 132: -0.2}
    model.tactical_risk_weights = {137: 0.2}
    model.floor_weights = {3: {10: 0.4}}
    model.floor_biases = {3: 0.1}
    parent = copy.deepcopy(model)
    head = StartingOptionHead(4096, (5, 9, 9000))
    model.starting_option_residual = head
    for representation in (_input(), _input(phase="combat"), _input(overrides={"floor": 18})):
        assert model.predict(representation) == parent.predict(representation)
    head.weights = dict(head.features(_input())[0])
    changed = model.predict(_input())
    assert changed.policy != parent.predict(_input()).policy
    assert changed.tactical_death_risk == parent.predict(_input()).tactical_death_risk
    assert changed.maximum_floor_reach == parent.predict(_input()).maximum_floor_reach
    assert model.predict(_input(phase="combat")) == parent.predict(_input(phase="combat"))
    assert model.predict(_input(overrides={"floor": 18})) == parent.predict(
        _input(overrides={"floor": 18})
    )


def test_config_and_head_versions_are_strict_and_frozen_recipe_is_unchanged() -> None:
    path = Path("configs/starting-option-policy/sts2-v0.107.1-base-v2-frontier-preferences-v1.json")
    config = load_starting_option_config(path)
    old = json.loads(
        Path(
            "configs/trajectory-policy/sts2-v0.107.1-base-v2-frontier-preferences-v1.json"
        ).read_text()
    )
    assert config.recipe.document == old
    head = StartingOptionHead(4096, (5, 9, 9000), {1: 0.2})
    assert StartingOptionHead.from_mapping(head.as_dict()).as_dict() == head.as_dict()
    corrupt = head.as_dict()
    corrupt["encoder_id"] = "future-encoder"
    with pytest.raises(ValueError, match="encoder"):
        StartingOptionHead.from_mapping(corrupt)
    corrupt = head.as_dict()
    corrupt["known_option_ids"] = [5, 5]
    with pytest.raises(ValueError, match="unique"):
        StartingOptionHead.from_mapping(corrupt)
    registry = Registry().with_resources(
        [
            (schema["$id"], Resource.from_contents(schema))
            for p in Path("schemas").glob("*.json")
            for schema in [json.loads(p.read_text())]
        ]
    )
    for name, document in (
        ("starting-option-policy-training-config-v1", config.document),
        ("starting-option-policy-residual-v1", head.as_dict()),
    ):
        Draft202012Validator(
            json.loads(Path("schemas", name + ".json").read_text()), registry=registry
        ).validate(document)
