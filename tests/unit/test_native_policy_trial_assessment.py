from __future__ import annotations

from typing import Any

from spireshift.native_policy_trial_assessment import conclusion


def report(*, failure: bool = False, gain: float = -0.46875) -> dict[str, Any]:
    arms = {
        name: {
            "recorded": 32,
            "denominator": 32,
            "wins": 0,
            "failed_games": 0,
            "not_attempted_games": 0,
        }
        for name in ("original", "ppo")
    }
    return {
        "failed_games": int(failure),
        "summary": {
            "players": [
                {"arms": arms, "ppo_minus_original": {"maximum_floor": {"mean": gain}}}
                for _ in range(2)
            ],
            "pooled_ppo_minus_original": {"maximum_floor": {"interval95": [-1.375, 0.4375]}},
        },
    }


def test_small_clean_negative_point_estimate_does_not_promote_or_identify_a_cause() -> None:
    decision = conclusion(report())
    assert decision["complete_clean_comparison"]
    assert not decision["updated_players_have_positive_floor_point_estimates"]
    assert not decision["checkpoint_promoted"] and not decision["automatic_scale_up_allowed"]
    assert decision["small_comparison_cannot_identify_the_cause_of_stalled_learning"]
    assert decision["no_observed_wins_is_not_proof_of_zero_win_probability"]


def test_failure_is_not_ignored_and_even_positive_floors_do_not_automatically_scale() -> None:
    assert not conclusion(report(failure=True))["complete_clean_comparison"]
    decision = conclusion(report(gain=1.0))
    assert decision["updated_players_have_positive_floor_point_estimates"]
    assert not decision["automatic_scale_up_allowed"] and not decision["base_readiness_passed"]
