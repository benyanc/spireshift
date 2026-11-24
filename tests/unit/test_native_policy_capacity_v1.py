from __future__ import annotations

import math
from typing import Any, cast

import pytest
from test_native_a8_card_display_model import menu, parent
from test_native_action_context import score

from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import log_softmax
from spireshift.native_a8_card_display_model import extend
from spireshift.native_a8_head_policy import save
from spireshift.native_combat_intent_model import copy_with_intents, encode, load
from spireshift.native_policy_capacity_v1 import expand, retained


def test_expansion_preserves_full_initial_policy_critic_and_all_inherited_adam(
    tmp_path: Any,
) -> None:
    original = copy_with_intents(extend(parent(), ("block", "damage")))
    document = original.document()
    wide = expand(original, original.model.actor.hidden_units * 2, 4242)
    rows, state = encode(menu(), original.model, score())
    rebuilt = encode(menu(), wide.model, score())
    assert rebuilt == (rows, state)
    old = log_softmax(score_features(cast(Any, original.model.actor), rows), 0.8)
    new = log_softmax(score_features(cast(Any, wide.model.actor), rows), 0.8)
    assert all(math.isclose(a, b, rel_tol=0, abs_tol=1e-12) for a, b in zip(old, new, strict=True))
    assert original.model.value(state) == wide.model.value(state)
    assert wide.actor_adam.steps == original.actor_adam.steps
    assert wide.value_adam == original.value_adam
    assert wide.model.value_weights == original.model.value_weights
    assert (
        retained(
            wide.actor_adam.first,
            wide.model.actor.dimension,
            original.model.actor.hidden_units,
            wide.model.actor.hidden_units,
        )
        == original.actor_adam.first
    )
    assert original.document() == document
    identifier = save(tmp_path / "wide.json", wide)
    assert load(tmp_path / "wide.json") == (wide, identifier)


def test_new_scoring_units_are_deterministic_distinct_and_have_zero_output_at_initialization() -> (
    None
):
    original = copy_with_intents(extend(parent(), ("block", "damage")))
    old = original.model.actor.hidden_units
    a, b = expand(original, 128, 1), expand(original, 128, 2)
    assert a == expand(original, 128, 1)
    assert a.model.actor.genome != b.model.actor.genome
    _, biases, output, _ = a.model.actor.unpack()
    assert not any(biases[old:]) and not any(output[old:])
    with pytest.raises(ValueError, match="strictly wider"):
        expand(original, old, 1)
    with pytest.raises(ValueError, match="strictly wider"):
        expand(original, 129, 1)
