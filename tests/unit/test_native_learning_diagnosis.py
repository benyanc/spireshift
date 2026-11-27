from __future__ import annotations

import math

import pytest

from spireshift.native_learning_diagnosis import signal_metrics


def test_perfect_and_constant_critics_have_expected_variance() -> None:
    assert signal_metrics([(0.01, 0.01), (0.03, 0.03)])["critic_explained_variance"] == 1
    constant = signal_metrics([(0.01, 0.02), (0.03, 0.02)])
    assert constant["critic_explained_variance"] == pytest.approx(0)
    assert constant["critic_mse_over_in_sample_constant"] == pytest.approx(1)


def test_wrong_critic_increases_noise_and_mse() -> None:
    result = signal_metrics([(0.01, 0.03), (0.03, 0.01)])
    assert result["critic_explained_variance"] == pytest.approx(-3)
    assert result["critic_mse_over_in_sample_constant"] == pytest.approx(4)


def test_biased_constant_can_have_zero_explained_variance_and_large_mse() -> None:
    result = signal_metrics([(0.01, 0.5), (0.03, 0.5)])
    assert result["critic_explained_variance"] == pytest.approx(0)
    assert result["critic_mse_over_in_sample_constant"] > 100


def test_repeated_targets_do_not_invent_uncertainty() -> None:
    result = signal_metrics([(0.02, 0.01), (0.02, 0.03)])
    assert result["target_std"] == 0
    assert result["critic_explained_variance"] is None
    assert result["critic_mse_over_in_sample_constant"] is None


@pytest.mark.parametrize("pairs", [[], [(math.inf, 0)], [(0, math.nan)]])
def test_empty_or_nonfinite_diagnostics_are_rejected(pairs: list[tuple[float, float]]) -> None:
    with pytest.raises(ValueError, match="finite"):
        signal_metrics(pairs)
