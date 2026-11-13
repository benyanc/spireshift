from __future__ import annotations

import math
from typing import Any, cast

import numpy as np
import pytest
from test_native_action_context import model

from spireshift.full_run_policy import FullRunModel, dense_features, score_features
from spireshift.native_action_rankings import compare, describe, scores, selected


def test_identical_scores_have_exact_ranking_probability_and_sampling_controls() -> None:
    c = compare((2.0, 1.0, -1.0), (2.0, 1.0, -1.0), draw=0.75)
    assert not c["greedy_changed"] and not c["same_draw_choice_changed"]
    assert c["original_best_rank_after"] == 0
    assert c["KL_before_to_after"] == c["entropy_change"] == 0
    assert c["strict_pair_inversions"] == 0 and c["strict_pairs_compared"] == 3


def test_additive_shift_changes_neither_ranking_nor_probabilities() -> None:
    c = compare((2.0, 1.0, -1.0), (12.0, 11.0, 9.0), draw=0.5)
    assert not c["greedy_changed"] and not c["same_draw_choice_changed"]
    assert c["before_margin"] == c["after_margin"] == 1
    assert c["before_centered_RMS"] == pytest.approx(c["after_centered_RMS"])
    assert c["KL_before_to_after"] == pytest.approx(0, abs=1e-14)


def test_compression_changes_sampling_without_reordering_actions() -> None:
    c = compare((4.0, 0.0), (0.04, 0.0), draw=0.75)
    assert not c["greedy_changed"] and c["same_draw_choice_changed"]
    assert c["after_margin"] < c["before_margin"]
    assert c["entropy_change"] > 0 and c["KL_before_to_after"] > 0


def test_rank_inversion_and_signed_original_margin_are_distinct_from_scale() -> None:
    c = compare((3.0, 2.0, 1.0), (1.0, 2.0, 3.0))
    assert c["greedy_changed"] and c["original_best_rank_after"] == 2
    assert c["original_best_signed_margin_after"] == -2
    assert c["strict_pair_inversions"] == c["strict_pairs_compared"] == 3
    assert c["same_draw_choice_changed"] is None


def test_exact_ties_have_stable_first_index_and_no_fake_strict_inversions() -> None:
    assert describe((1.0, 1.0, 0.0))["greedy_index"] == 0
    assert selected((0.0, 0.0), None) == 0
    c = compare((1.0, 1.0), (1.0, 1.0))
    assert c["before_margin"] == 0 and c["strict_pairs_compared"] == 0
    assert not c["greedy_changed"]


def test_single_action_has_no_invented_competitor_margin() -> None:
    c = compare((0.0,), (10.0,), draw=0.0)
    assert c["before_margin"] is None and c["original_best_signed_margin_after"] is None
    assert not c["greedy_changed"] and not c["same_draw_choice_changed"]


@pytest.mark.parametrize("bad", [(), (math.nan,), (math.inf,)])
def test_bad_menus_fail_before_diagnostic(bad: Any) -> None:
    with pytest.raises(ValueError):
        describe(bad)


@pytest.mark.parametrize("draw", [-0.1, 1.0, math.nan, True])
def test_invalid_recorded_draw_is_rejected(draw: Any) -> None:
    with pytest.raises(ValueError):
        selected((-0.5, -1.0), draw)


def test_legal_menu_differences_never_count_as_rank_change() -> None:
    with pytest.raises(ValueError, match="legal menu"):
        compare((1.0,), (1.0, 2.0))


def test_preunpacked_scoring_is_exactly_the_historical_actor_kernel() -> None:
    m = model().actor
    rows = ({1: 1.0, 21: -0.7}, {0: 0.3, 128: 0.9}, {5: 1.0})
    x = dense_features(rows, m.dimension)
    assert scores(x, m.unpack()) == score_features(cast(FullRunModel, m), rows)
    with pytest.raises(ValueError):
        scores(np.full(x.shape, np.nan), m.unpack())
