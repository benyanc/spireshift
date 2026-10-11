from copy import deepcopy
from typing import Any

import pytest

from spireshift.engine_reward_generation import METHODS, compare_reward_fixtures


def fixtures(relic: str = "CallingBell") -> tuple[dict[str, Any], dict[str, Any]]:
    pins = {
        role: {
            "artifact_sha256": role,
            "runtime_sts2_sha256": "game",
            "godot_stub_sha256": "stub",
        }
        for role in ("legacy", "repaired")
    }
    before: dict[str, Any] = {
        "run_rng": {"counter": 1},
        "player_rng": {"counter": 3},
        "relic_grab_bag": {"pool": ["FAKE_A", "FAKE_B"]},
    }
    after = deepcopy(before)
    after["player_rng"]["counter"] = 8
    after["relic_grab_bag"]["pool"] = ["FAKE_B"]
    rows = {}
    count = 3 if relic == "CallingBell" else 5
    for role in ("reference", "legacy", "repaired"):
        old = role == "legacy"
        rows[role] = {
            "schema_version": "native-reward-generation-fixture-v1",
            "seed": "SYNTH1",
            "relic": relic,
            "mode": "original_normal" if role == "reference" else "test",
            "wrapper_sha256": "repaired" if role == "repaired" else "legacy",
            "game_sha256": "game",
            "stub_sha256": "stub",
            "original_method_il_sha256": METHODS[relic],
            "managed_runtime_version": "9.0.7",
            "global_test_mode_retained": True,
            "privileged_fixture": True,
            "training_allowed": False,
            "shipped_game_compared": False,
            "full_run_attempts": 0,
            "reward_selections": 0,
            "hook_installed": role == "repaired",
            "hook_methods": 2 if role == "repaired" else 0,
            "populated_at_construction": [old] * count,
            "generated_rewards": [
                {
                    "kind": "relic" if relic == "CallingBell" else "potion",
                    "id": "FAKE_PRESET" if old else "FAKE_DRAW",
                    "rarity": "Common",
                }
            ]
            * count,
            "private_before": deepcopy(before),
            "private_after": deepcopy(before if old else after),
        }
    return rows, pins


@pytest.mark.parametrize("relic", ["CallingBell", "Cauldron"])
def test_native_generation_comparison_never_claims_shipped_or_training(relic: str) -> None:
    rows, pins = fixtures(relic)
    verdict = compare_reward_fixtures(rows, "SYNTH1", relic, pins)
    assert verdict["candidate_matches_original_normal"]
    assert verdict["private_rng_and_pool_state_compared"]
    assert verdict["training_allowed"] is False
    assert verdict["shipped_game_compared"] is False


@pytest.mark.parametrize("part", ["run_rng", "player_rng", "relic_grab_bag"])
def test_correct_offers_with_changed_rng_or_pool_still_fail(part: str) -> None:
    rows, pins = fixtures()
    rows["repaired"]["private_after"][part] = {"wrong": 1}
    with pytest.raises(ValueError, match="differs from"):
        compare_reward_fixtures(rows, "SYNTH1", "CallingBell", pins)


def test_matching_offers_from_a_different_start_are_not_a_comparison() -> None:
    rows, pins = fixtures()
    rows["repaired"]["private_before"]["player_rng"]["counter"] = 40
    with pytest.raises(ValueError, match="different RNG"):
        compare_reward_fixtures(rows, "SYNTH1", "CallingBell", pins)


@pytest.mark.parametrize(
    "field,value",
    [
        ("wrapper_sha256", "other"),
        ("game_sha256", "other"),
        ("stub_sha256", "other"),
        ("original_method_il_sha256", "other"),
        ("mode", "original_normal"),
        ("hook_methods", 1),
        ("global_test_mode_retained", False),
        ("reward_selections", 1),
        ("shipped_game_compared", True),
        ("training_allowed", True),
        ("generated_rewards", []),
        ("private_after", {}),
    ],
)
def test_incomplete_or_wrongly_bound_fixtures_fail(field: str, value: object) -> None:
    rows, pins = fixtures()
    rows["repaired"][field] = value
    with pytest.raises(ValueError, match="Unbound or incomplete"):
        compare_reward_fixtures(rows, "SYNTH1", "CallingBell", pins)


def test_unchanged_legacy_path_cannot_demonstrate_a_repair() -> None:
    rows, pins = fixtures()
    for key in ("generated_rewards", "private_after"):
        rows["legacy"][key] = deepcopy(rows["reference"][key])
    with pytest.raises(ValueError, match="did not expose"):
        compare_reward_fixtures(rows, "SYNTH1", "CallingBell", pins)
