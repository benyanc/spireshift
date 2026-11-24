from __future__ import annotations

from typing import Any

import pytest
from test_native_a8_card_display_model import menu, parent
from test_native_action_context import score

from spireshift.native_a8_card_display_model import extend
from spireshift.native_combat_intent_model import copy_with_intents
from spireshift.native_qualified_learning_result_v1 import architecture_diagnostics


def test_saved_health_metrics_are_bounded_and_do_not_update_a_model() -> None:
    state = copy_with_intents(extend(parent(), ("block", "damage")))
    document = state.document()
    states = {name: {p: (state, "full-state") for p in (2, 3)} for name in ("start", "final")}
    samples: dict[int, list[tuple[int, str, dict[str, Any]]]] = {
        p: [(0, "saved-frame", menu())] for p in (2, 3)
    }
    result = architecture_diagnostics(samples, states, score())
    assert result["training_labels_created"] == 0
    assert len(result["measurements"]) == 4
    for record in result["measurements"].values():
        assert record["actor_parameters"] == state.model.actor.parameter_count
        assert 0 <= record["hidden_activation_fraction_above_abs_0_95"] <= 1
        assert 0 <= record["mean_entropy_fraction_of_uniform"] <= 1
        assert 0 <= record["mean_hidden_range_across_legal_actions"] <= 2
    assert state.document() == document


def test_empty_model_health_samples_cannot_be_reported_as_a_pass() -> None:
    with pytest.raises(ValueError, match="both initializers"):
        architecture_diagnostics({2: [], 3: []}, {}, score())
