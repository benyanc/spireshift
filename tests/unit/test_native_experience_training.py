from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from test_native_action_context import model, score
from test_native_inventory_input import fixture

from spireshift.full_run_ppo_math import Sample
from spireshift.native_context_cache import cached_model
from spireshift.native_experience_training import prepare


def setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, list[Sample], dict[str, Any]]:
    import spireshift.native_experience_training as m

    path = tmp_path / "episode.json"
    path.write_text(json.dumps({"binding": {"partition": "train"}}))
    p = fixture()
    case = {"status": "terminal", "decisions": [{"public_input": p, "choice": {"action_index": 0}}]}
    samples = [Sample(({0: 1.0}, {1: 1.0}), (1.0,), 0, -0.5, 0.03, 0.02)]
    monkeypatch.setattr(
        m, "original_prepare", lambda *a: (samples, {"clean_complete_training_games": 1})
    )
    monkeypatch.setattr(m, "read_native_episode", lambda *a: copy.deepcopy(case))
    return path, samples, case


def test_inventory_and_per_family_coverage_do_not_change_returns_or_credit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, samples, _ = setup(tmp_path, monkeypatch)
    before = copy.deepcopy(samples)
    outcomes = [
        {
            "seed_id": 1,
            "status": "terminal",
            "victory": False,
            "completed_acts": 1,
            "maximum_floor": 23,
            "owned_card_definitions": ["CARD_A", "FOREIGN_CARD"],
            "owned_relic_definitions": ["RELIC_A"],
        }
    ]
    result, credit = prepare([path], cached_model(model()), score(), {}, [{"id": 1}], 1, outcomes)
    assert result == before and result is samples
    e = credit["experience"]
    assert e["act_clearing_games"] == e["games_reaching_floor_17"] == 1
    assert e["distinct_owned_card_definitions"] == 2 and e["full_wins"] == 0
    assert e["choice_credit_by_family"]["rest_site"] == {
        "choice_decisions": 1,
        "raw_mean": 0.02,
        "negative": 0,
        "positive": 1,
    }
    assert not e["coverage_or_HP_added_as_rewards"]


def test_missing_scheduled_game_cannot_be_hidden_by_coverage_statistics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _, _ = setup(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="complete planned denominator"):
        prepare([path], cached_model(model()), score(), {}, [{"id": 1}], 1, [])


def test_wrong_selected_action_cannot_receive_another_family_credit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _, case = setup(tmp_path, monkeypatch)
    case["decisions"][0]["choice"]["action_index"] = 1
    outcome = {"seed_id": 1, "owned_card_definitions": [], "owned_relic_definitions": []}
    with pytest.raises(ValueError, match="exact sampled decision"):
        prepare([path], cached_model(model()), score(), {}, [{"id": 1}], 1, [outcome])
