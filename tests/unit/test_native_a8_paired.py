from __future__ import annotations

from typing import Any

import pytest

from spireshift.native_a8_paired_report import summarize
from spireshift.native_a8_paired_session import WORLDS, same_start, tasks


def test_pairing_crosses_every_world_with_both_checkpoints_and_initializers() -> None:
    plan = tasks(WORLDS)
    assert len({row["key"] for row in plan}) == 48
    for index, world in enumerate(WORLDS):
        for player in (2, 3):
            pair = [row["arm"] for row in plan if row["world"] == world and row["player"] == player]
            assert pair == (
                ["original", "fitted"] if (index + player) % 2 == 0 else ["fitted", "original"]
            )
    with pytest.raises(ValueError, match="different initial"):
        same_start([{"initial_public_input_id": "a"}, {"initial_public_input_id": "b"}])


def test_incomplete_results_stay_in_planned_denominators_without_becoming_losses() -> None:
    games: dict[tuple[str, int, str], dict[str, Any]] = {
        ("world", 2, "original"): {"outcome": "capped", "native_terminal": True},
        ("world", 2, "fitted"): {"outcome": "win", "completed_acts": 3},
        ("world", 3, "original"): {"outcome": "failed"},
    }
    result = summarize(["world"], games)
    p2, p3 = (result["by_initializer"][p] for p in ("2", "3"))
    assert p2["arms"]["original"] == {
        "win": 0,
        "loss": 0,
        "capped": 1,
        "failed": 0,
        "unattempted": 0,
    }
    assert p2["fitted_minus_original_win_rate_bounds"] == [0, 1]
    assert p2["terminal_pairs"] == p2["fitted_only_wins"] == 0
    assert p3["arms"]["original"]["failed"] == p3["arms"]["fitted"]["unattempted"] == 1
    assert result["pooled_fitted_minus_original_win_rate_bounds"] == [-0.5, 1]
    assert result["seed_clustered_bootstrap_95"] is None


def test_complete_games_keep_both_initializers_in_each_seed_bootstrap_cluster() -> None:
    games = {
        ("world", 2, "original"): {"outcome": "loss", "completed_acts": 0},
        ("world", 2, "fitted"): {"outcome": "win", "completed_acts": 3},
        ("world", 3, "original"): {"outcome": "win", "completed_acts": 3},
        ("world", 3, "fitted"): {"outcome": "loss", "completed_acts": 2},
    }
    result = summarize(["world"], games)
    assert result["by_initializer"]["2"]["fitted_only_wins"] == 1
    assert result["by_initializer"]["3"]["original_only_wins"] == 1
    assert result["seed_clustered_bootstrap_95"]["intervals"] == {
        "player_2_wins": [1, 1],
        "player_3_wins": [-1, -1],
        "pooled_wins": [0, 0],
        "pooled_completed_acts": [1, 1],
    }
