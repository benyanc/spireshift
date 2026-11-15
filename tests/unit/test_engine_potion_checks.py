from __future__ import annotations

import argparse
from typing import Any

import pytest

from spireshift.engine_learning import choice_sampling_seed, evaluation_policy
from spireshift.engine_potion_checks import ANYTIME, check_effect, potion_cases
from spireshift.engine_qualification_cli import add_engine_parser
from spireshift.engine_worker_qualification import worker_script


def observation(**changes: Any) -> dict[str, Any]:
    player = {"hp": 30, "max_hp": 80, "gold": 200, "potions": [], "max_potion_slots": 2}
    player.update(changes)
    return {
        "snapshot": {
            "persistent": {"content": {"player": player}},
            "interaction": {"kind": "rest_site"},
        }
    }


def test_finite_potion_panel_covers_native_anytime_set_and_binding_rejections() -> None:
    cases = potion_cases()
    assert len(cases) == 25
    assert len({c["id"] for c in cases}) == len(cases)
    assert {c["potion"] for c in cases} >= ANYTIME
    assert {"stale_potion", "stale_target", "stale_room"} <= {c["mode"] for c in cases}
    assert {c["room"] for c in cases} >= {"map", "rest", "reward", "shop", "event"}


def test_real_merchant_gold_and_fake_merchant_fight_are_distinct_effects() -> None:
    before = observation()
    real = {"potion": "FOUL_POTION", "room": "shop"}
    fake = {**real, "event": "FAKE_MERCHANT"}
    check_effect(real, before, observation(gold=300))
    with pytest.raises(ValueError, match="Fake merchant"):
        check_effect(fake, before, observation(gold=300))
    fight = observation()
    fight["snapshot"]["interaction"]["kind"] = "combat_turn"
    check_effect(fake, before, fight)
    with pytest.raises(ValueError, match="Real merchant"):
        check_effect(real, before, fight)


def test_potion_checks_verify_effects_without_adding_learning_labels() -> None:
    check_effect({"potion": "BLOOD_POTION"}, observation(), observation(hp=46))
    check_effect({"potion": "AMBERGRIS"}, observation(), observation(hp=70))
    check_effect({"potion": "FRUIT_JUICE"}, observation(), observation(hp=35, max_hp=85))
    with pytest.raises(ValueError, match="healing"):
        check_effect({"potion": "BLOOD_POTION"}, observation(), observation(hp=31))
    # Refill may legally generate a new copy with the same definition ID.
    check_effect(
        {"potion": "ENTROPIC_BREW"},
        observation(),
        observation(potions=[{"definition_id": "ENTROPIC_BREW"}, {"definition_id": "OTHER"}]),
    )


def test_new_learning_worker_is_explicit_and_diagnostic_worker_cannot_substitute() -> None:
    assert worker_script({}) == "engine-native-worker-v4.mjs"
    assert worker_script({"worker_script": "engine-native-worker-v7.mjs"}).endswith("v7.mjs")
    with pytest.raises(ValueError, match="Unqualified"):
        worker_script({"worker_script": "engine-mechanics-worker-v3.mjs"})


def test_potion_cli_has_separate_execution_and_saved_only_verification() -> None:
    parser = argparse.ArgumentParser()
    add_engine_parser(parser.add_subparsers(dest="command"))
    parsed = parser.parse_args(
        ["engine", "verify-potion-controls", "qualification.json", "potions.json"]
    )
    assert parsed.engine_command == "verify-potion-controls"
    with pytest.raises(SystemExit):
        parser.parse_args(["engine", "check-potion-controls", "qualification.json", "potions.json"])


def test_frozen_evaluation_randomness_is_paired_and_separate_from_training() -> None:
    document: dict[str, Any] = {
        "evaluation_policy": {
            "behavior": "sampled_softmax",
            "temperature": 0.8,
            "sampling_seed": 11,
            "coupling": "same_run_seed_across_checkpoints",
        },
        "learning": {"sampling_seed": 22},
    }
    assert evaluation_policy({}) == {"behavior": "greedy"}
    assert choice_sampling_seed(document, "initial", 101, False) == choice_sampling_seed(
        document, "updated", 101, False
    )
    assert choice_sampling_seed(document, "round-001", 101, True) != choice_sampling_seed(
        document, "round-002", 101, True
    )
    assert choice_sampling_seed(document, "initial", 101, False) != choice_sampling_seed(
        document, "initial", 102, False
    )
    document["evaluation_policy"]["temperature"] = 0
    with pytest.raises(ValueError, match="Evaluation"):
        evaluation_policy(document)
