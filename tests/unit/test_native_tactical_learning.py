from __future__ import annotations

import copy
import math
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from test_native_action_context import model, score

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import INPUT_SCHEMA
from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import Adam, log_softmax
from spireshift.native_context_cache import cached_model
from spireshift.native_tactical_cases import FAMILIES, outcome, qualify_case, tasks
from spireshift.native_tactical_learning import diagnostic_update, evaluate, fit, sample_bandit
from spireshift.native_tactical_study import coverage


def case(family: str, partition: str = "fit", seed: int = 1) -> dict[str, Any]:
    cards = (
        ("WHIRLWIND", "DEFEND_IRONCLAD")
        if family == FAMILIES[0]
        else ("DEFEND_IRONCLAD", "STRIKE_IRONCLAD")
    )
    public: dict[str, Any] = {
        "schema_version": INPUT_SCHEMA,
        "context": {
            "persistent": {
                "run": {"act": 1, "floor": 1, "ascension": 8},
                "player": {
                    "character_definition_id": "IRONCLAD",
                    "hp": 3,
                    "max_hp": 80,
                    "gold": 99,
                    "relics": [],
                    "potions": [],
                },
            },
            "interaction": {
                "kind": "combat_turn",
                "content": {
                    "context": {
                        "round": 2,
                        "player": {"energy": 3, "block": 0},
                        "enemies": [{"hp": 40}],
                    }
                },
            },
            "reads": [{"kind": "run_deck", "content": {"card_count": 2}}],
        },
        "candidates": [
            {
                "verb": "play",
                "label": card,
                "subject": {
                    "role": "playable_card",
                    "properties": {
                        "definition_id": card,
                        "cost": 1,
                        "stats": {"damage": 6} if "STRIKE" in card else {},
                    },
                },
                "arguments": [],
            }
            for card in cards
        ]
        + [{"verb": "end_turn", "label": "End turn", "subject": None, "arguments": []}],
    }
    return {
        "public_input": public,
        "public_input_id": manifest_identifier(public),
        "best": 0,
        "branches": [{"action": i, "outcome": float(i == 0)} for i in range(3)],
        "task": {
            "key": f"{partition}-{seed}-{family}",
            "family": family,
            "seed": {"id": seed, "partition": partition},
        },
    }


@pytest.mark.parametrize("values", [[0, 0, 0], [1, 1, 0], [1, 0], [1, 0.5, 0]])
def test_native_lessons_require_one_observed_success_and_complete_action_denominator(
    values: list[float],
) -> None:
    with pytest.raises(ValueError, match="unique success"):
        qualify_case(case(FAMILIES[0])["public_input"], values)


def test_wrong_character_or_ascension_is_not_a_valid_native_A8_lesson() -> None:
    public = case(FAMILIES[0])["public_input"]
    assert qualify_case(public, [1, 0, 0]) == 0
    public["context"]["persistent"]["run"]["ascension"] = 0
    with pytest.raises(ValueError, match="native-verified"):
        qualify_case(public, [1, 0, 0])


def test_survival_requires_observed_next_turn_and_encounter_finish_requires_native_reward() -> None:
    public = case(FAMILIES[1])["public_input"]
    root = {"model_input": public}
    successor = copy.deepcopy(root)
    with pytest.raises(ValueError, match="observed next"):
        outcome(FAMILIES[1], root, successor)
    successor["model_input"]["context"]["interaction"]["content"]["context"]["round"] = 3
    assert outcome(FAMILIES[1], root, successor) == 1
    successor["model_input"]["context"]["persistent"]["player"]["hp"] = 0
    assert outcome(FAMILIES[1], root, successor) == 0
    successor["model_input"]["context"]["persistent"]["player"]["hp"] = 3
    successor["model_input"]["context"]["interaction"] = {"kind": "card_selection"}
    with pytest.raises(ValueError, match="native combat reward"):
        outcome(FAMILIES[0], root, successor)
    successor["model_input"]["context"]["interaction"] = {"kind": "reward_claim"}
    assert outcome(FAMILIES[0], root, successor) == 1


def test_bandit_permutations_map_native_outcomes_and_oracle_baseline_consistently() -> None:
    m = cached_model(model())
    data = [case(family) for family in FAMILIES]
    samples, labels = sample_bandit(m, data, score(), 64, "test")
    assert len(samples) == len(labels) == 64 and len(set(labels)) > 1
    for s, label in zip(samples, labels, strict=True):
        assert s.target == float(s.action == label)
        logs = log_softmax(score_features(cast(Any, m.actor), s.rows), 0.8)
        expected = math.exp(logs[label])
        # The exact state baseline is the probability of the unique successful move.
        baseline = s.target - s.advantage
        assert 0 < baseline < 1
        assert baseline == pytest.approx(expected)
    result = evaluate(m, data, score())
    assert result["candidate_permutation_control_passed"]


def test_zero_credit_preserves_warm_state_instead_of_momentum_only_movement() -> None:
    m = cached_model(model())
    adam = Adam(10, (0.1,) * m.parameter_count, (0.2,) * m.parameter_count)
    samples, _ = sample_bandit(m, [case(f) for f in FAMILIES], score(), 8, "constant")
    after, opt, work = diagnostic_update(
        m, adam, [replace(s, advantage=1.0) for s in samples], {}, 1
    )
    assert after is m and opt is adam and work["optimizer_steps"] == 0


def test_small_fit_matches_work_and_preserves_every_original_weight_and_Adam_moment(
    tmp_path: Path,
) -> None:
    m = cached_model(model())
    adam = Adam(4, (0.001,) * m.parameter_count, (0.01,) * m.parameter_count)
    before = m.as_dict(), adam.as_dict()
    data = [case(f) for f in FAMILIES] + [case(f, "heldout", 2) for f in FAMILIES]
    result = fit({"rounds": 2, "sampled_choices_per_round": 8}, m, adam, score(), data, 2, tmp_path)
    assert (m.as_dict(), adam.as_dict()) == before
    assert result["frozen_actor_control_passed"]
    assert not result["ordinary_full_run_PPO_eligible"] and not result["heldout_used_for_selection"]
    assert result["methods"]["ppo"]["new_optimizer_steps"] > 0
    assert (
        result["methods"]["ppo"]["new_optimizer_steps"]
        == result["methods"]["teaching"]["new_optimizer_steps"]
    )
    assert (tmp_path / "ppo-state.json").exists() and (tmp_path / "teaching-state.json").exists()


def test_complete_seed_overlap_is_rejected_and_public_state_overlap_is_reported(
    tmp_path: Path,
) -> None:
    m = cached_model(model())
    a, b = case(FAMILIES[0]), case(FAMILIES[0], "heldout", 1)
    assert coverage([a, b])["public_inputs_in_both_partitions"] == 1
    with pytest.raises(ValueError, match="held-out complete native seed"):
        fit({}, m, Adam.zero(m.parameter_count), score(), [a, b], 2, tmp_path)


def test_heldout_answers_cannot_change_fitted_weights_or_optimizer(tmp_path: Path) -> None:
    import json

    m = cached_model(model())
    adam = Adam.zero(m.parameter_count)
    fitting = [case(f) for f in FAMILIES]
    held = [case(f, "heldout", 2) for f in FAMILIES]
    altered = copy.deepcopy(held)
    for row in altered:
        row["best"] = 1
        row["branches"] = [{"action": i, "outcome": float(i == 1)} for i in range(3)]
    cfg = {"rounds": 2, "sampled_choices_per_round": 8}
    fit(cfg, m, adam, score(), fitting + held, 2, tmp_path / "a")
    fit(cfg, m, adam, score(), fitting + altered, 2, tmp_path / "b")
    for name in ("ppo", "teaching"):
        a = json.loads((tmp_path / "a" / f"{name}-state.json").read_text())
        b = json.loads((tmp_path / "b" / f"{name}-state.json").read_text())
        assert a == b


def test_plan_contains_both_families_for_each_frozen_seed_without_game_execution() -> None:
    result = tasks({"seeds": [{"id": 1, "partition": "fit"}, {"id": 2, "partition": "heldout"}]})
    assert len(result) == 4 and len({r["key"] for r in result}) == 4
    assert {r["family"] for r in result} == set(FAMILIES)
