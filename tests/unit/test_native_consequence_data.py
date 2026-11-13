from __future__ import annotations

import copy
from typing import Any

import numpy as np
import pytest
from test_native_action_context import model, score
from test_native_turn_teacher_policy import public as original_public
from test_native_turn_teacher_policy import selection

from spireshift.native_consequence_data import TARGETS, encode_examples, examples, group_weights
from spireshift.native_context_cache import cached_model


def public(hp: int = 40, enemy: int = 20, turn: int = 2) -> dict[str, Any]:
    p = original_public()
    p["context"]["persistent"]["player"].update(hp=hp, max_hp=80, potions=[], max_potion_slots=2)
    combat = p["context"]["interaction"]["content"]["context"]
    combat["round"] = turn
    combat["enemies"][0].update(hp=enemy, max_hp=20)
    return p


def postcombat(hp: int = 41) -> dict[str, Any]:
    p = public(hp)
    p["context"]["interaction"].update(
        kind="reward_claim", content={"context": {"kind": "reward_flow"}}
    )
    return p


def case(values: list[dict[str, Any]], actions: list[int] | None = None) -> dict[str, Any]:
    return {
        "status": "terminal",
        "victory": False,
        "maximum_floor": 6,
        "recovered": False,
        "privileged_fixture": False,
        "native_ending_evidence_agrees": True,
        "privileged_fixed_world_teacher": True,
        "student_inputs_public_only": True,
        "private_final_identity": {"native_game_over": True, "native_player_dead": True},
        "decisions": [
            {"public_input": p, "choice": {"action_index": a}}
            for p, a in zip(values, actions or [0] * len(values), strict=True)
        ],
    }


def root(p: dict[str, Any]) -> dict[str, Any]:
    return {"prefix": [], "public_input": p, "source_seed_id": 101, "numerical_seed": 2}


def test_targets_are_observed_step_turn_and_encounter_effects_not_attack_guesses() -> None:
    p = public()
    c = case([p, public(40, 14), public(35, 14, 3), postcombat()])
    rows, report = examples(c, root(p), "plan", 0.03)
    first = dict(zip(TARGETS, rows[0]["targets"], strict=True))
    assert first["recorded_continuation_full_run_return"] == 0.03
    assert first["next_public_hp_delta"] == 0
    assert first["next_public_enemy_hp_sum_delta"] == -0.3
    assert first["next_turn_hp_delta"] == -5 / 80
    assert first["encounter_exit_hp_delta"] == 1 / 80
    assert first["encounter_alive_exit"] == 1
    assert len(rows) == 3 and report["observed_alive_encounter_exit"]
    assert not rows[-1]["target_mask"][2]  # reward screen does not expose enemy HP


def test_end_turn_nested_choice_is_resolved_for_turn_target_not_silently_skipped() -> None:
    p = public()
    c = case([p, selection(p), public(30, 20, 3), postcombat(36)], [2, 0, 0, 0])
    values, summary = examples(c, root(p), "plan", 0.03)
    assert values[0]["targets"][1] == 0  # opened menu, before its choice resolves
    assert values[0]["targets"][3] == -10 / 80
    assert values[0]["label_endpoints"]["next_turn"] == 2
    assert summary["nested_decisions_resolved_not_standalone_inputs"] == 1
    assert [v["decision_index"] for v in values] == [0, 2]


def test_terminal_combat_death_has_zero_observed_hp_without_invented_enemy_or_belt() -> None:
    p = public(14)
    c = case([p], [2])
    values, summary = examples(c, root(p), "death", 0.01)
    v = values[0]
    assert [v["targets"][j] for j in (1, 3, 4)] == [-14 / 80] * 3
    assert v["targets"][5] == 0 and not summary["observed_alive_encounter_exit"]
    assert not v["target_mask"][2] and not v["target_mask"][6]


@pytest.mark.parametrize(
    "fault",
    [
        "recovered",
        "privileged_fixture",
        "status",
        "native_ending_evidence_agrees",
        "student_inputs_public_only",
        "privileged_fixed_world_teacher",
    ],
)
def test_bad_or_out_of_scope_episodes_are_never_learning_examples(fault: str) -> None:
    p = public()
    c = case([p])
    c[fault] = "failed" if fault == "status" else not c[fault]
    with pytest.raises(ValueError, match="sealed"):
        examples(c, root(p), "bad", 0.03)


def test_missing_exit_cannot_be_filled_using_an_unrelated_later_floor() -> None:
    p = public()
    c = case([p])
    c["maximum_floor"] = 99
    with pytest.raises(ValueError, match="exit"):
        examples(c, root(p), "bad", 0.03)


def test_no_source_prefix_decision_or_postfight_menu_enters_training() -> None:
    p = public()
    before = public(80)
    r = {**root(p), "prefix": [{"action_index": 0}]}
    c = case([before, p, postcombat()])
    rows, summary = examples(c, r, "plan", 0.03)
    assert len(rows) == 1 and rows[0]["decision_index"] == 1
    assert rows[0]["public_input"] == p and summary["prefix_decisions_excluded"] == 1


def test_targets_source_ids_and_future_endpoints_cannot_change_current_features() -> None:
    p = public()
    values, _ = examples(case([p, postcombat()]), root(p), "plan", 0.03)
    original = encode_examples(values, cached_model(model()), score())
    changed = copy.deepcopy(values)
    changed[0].update(
        source_seed_id=999,
        plan_id="other",
        targets=[0.9] * len(TARGETS),
        label_endpoints={"next_turn": "invented future"},
    )
    encoded = encode_examples(changed, cached_model(model()), score())
    assert np.array_equal(original["inputs"], encoded["inputs"])
    assert np.array_equal(original["action_blind"], encoded["action_blind"])


def test_action_blind_control_hides_chosen_move_but_preserves_current_legal_menu() -> None:
    p = public()
    values, _ = examples(case([p, postcombat()]), root(p), "plan", 0.03)
    other = copy.deepcopy(values[0])
    other["action_index"] = 2
    arrays = encode_examples([values[0], other], cached_model(model()), score())
    assert np.array_equal(arrays["action_blind"][0], arrays["action_blind"][1])
    assert not np.array_equal(arrays["inputs"][0], arrays["inputs"][1])


def test_private_or_opaque_current_fields_are_still_rejected_by_encoder() -> None:
    p = public()
    values, _ = examples(case([p, postcombat()]), root(p), "plan", 0.03)
    values[0]["public_input"]["context"]["rng"] = 123
    with pytest.raises(ValueError, match="Private"):
        encode_examples(values, cached_model(model()), score())


def test_source_plan_valid_decision_weighting_never_counts_longer_repeats_as_worlds() -> None:
    owners = np.asarray([1, 1, 1, 2])
    plans = np.asarray(["a", "a", "b", "c"])
    mask = np.ones((4, len(TARGETS)), dtype=np.bool_)
    mask[:3, 2] = False
    mask[:, 6] = False
    weights = group_weights(owners, plans, mask)
    assert weights[:, 0].tolist() == [0.125, 0.125, 0.25, 0.5]
    assert weights[:, 2].tolist() == [0, 0, 0, 1]
    assert not weights[:, 6].any()
    assert np.array_equal(weights.sum(axis=0), [1, 1, 1, 1, 1, 1, 0])


def test_potion_consumption_is_observed_without_assigning_it_a_positive_reward() -> None:
    p, after = public(), public()
    p["context"]["persistent"]["player"]["potions"] = [{"name": "Potion"}]
    values, _ = examples(case([p, after, postcombat()]), root(p), "plan", 0.03)
    assert values[0]["targets"][6] == -0.5 and values[0]["target_mask"][6]
    assert values[0]["targets"][0] == 0.03
