from __future__ import annotations

from typing import Any

import pytest

from spireshift import native_combat_behavior_data as module
from spireshift.native_combat_behavior_data import summarize, tasks


def seeds() -> list[dict[str, Any]]:
    return [{"id": 100, "seed": "FRESH100"}, {"id": 101, "seed": "FRESH101"}]


def records(control: bool = False) -> dict[str, dict[str, Any]]:
    return {
        t["key"]: {
            "numerical_seed": t["numerical_seed"],
            "arm": t["arm"],
            "seed_id": t["seed"]["id"],
            "status": "terminal",
            "victory": False,
            "maximum_floor": 10 + (t["arm"] == "greedy"),
            "completed_acts": 0,
            "training_return": 0.1,
            "cpu_seconds": 2.0,
        }
        for t in tasks(seeds(), control)
    }


def test_plan_has_every_paired_cell_counterbalanced_and_separate_repeats() -> None:
    plan = tasks(seeds(), True)
    assert len(plan) == 12 and len({t["key"] for t in plan}) == 12
    assert [t["arm"] for t in plan[:4]] == ["sampled", "greedy", "greedy", "sampled"]
    assert [t["arm"] for t in plan[4:8]] == ["greedy", "sampled", "sampled", "greedy"]
    assert {t["duplicate_of"] for t in plan[8:]} == {t["key"] for t in plan[:4]}


def test_pooled_intervals_resample_game_seeds_jointly_not_player_game_cells(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "RESAMPLES", 100)
    result = summarize(seeds(), records(), control=False)
    assert result["denominator"] == 8 and result["independent_game_seeds"] == 2
    assert result["pooled_greedy_minus_sampled"]["maximum_floor"] == {
        "mean": 1,
        "interval95": [1, 1],
    }
    assert not result["uncertainty_covers_population_of_training_initializers"]


def test_failed_missing_and_duplicate_games_keep_original_denominator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "RESAMPLES", 100)
    rows = records(True)
    rows["game-100-p2-greedy"]["status"] = "failed"
    rows.pop("game-101-p3-greedy")
    result = summarize(seeds(), rows, control=True)
    assert result["denominator"] == 8 and result["completed_games"] == 6
    assert result["failed_games"] == result["not_attempted_games"] == 1
    assert result["players"][0]["arms"]["greedy"]["mean_floor"] == 5.5
    assert not result["base_readiness_passed"] and not result["checkpoint_promoted"]


def test_unplanned_or_misbound_games_cannot_change_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "RESAMPLES", 100)
    rows = records()
    rows["replacement"] = rows["game-100-p2-greedy"]
    with pytest.raises(ValueError, match="unplanned"):
        summarize(seeds(), rows, control=False)
    rows.pop("replacement")
    rows["game-100-p2-greedy"]["seed_id"] = 102
    with pytest.raises(ValueError, match="paired cell"):
        summarize(seeds(), rows, control=False)
