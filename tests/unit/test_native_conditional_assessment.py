from __future__ import annotations

import time
from pathlib import Path

import pytest

from spireshift.native_conditional_assessment import assess, initial_conditioning


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_initial_probe_preserves_hp_but_exposes_missing_linear_interaction(seed: int) -> None:
    result = initial_conditioning(seed)
    assert result == initial_conditioning(seed)
    assert result["public_HP_difference_survives_encoding"]
    assert result["HP_difference_same_for_both_candidate_rows"]
    assert result["direct_linear_conditional_gradient_norm"] == 0
    assert result["whole_actor_conditional_gradient_norm"] > 0
    assert 0 < result["conditional_to_ordinary_gradient_norm_ratio"] < 0.001
    assert result["actual_optimizer_updates_measured_by_this_probe"] is False


def test_saved_assessment_cannot_fall_through_to_fitting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = {"workspace": "artifacts/synthetic-learning/no-saved-result"}
    monkeypatch.setattr(
        "spireshift.native_conditional_assessment.load_config", lambda *_: (cfg, {}, None)
    )
    monkeypatch.setattr(
        "spireshift.native_conditional_control.paired_seed",
        lambda *_a, **_kw: pytest.fail("Assessment started learning"),
    )
    before = time.monotonic()
    with pytest.raises(FileNotFoundError):
        assess(tmp_path, tmp_path / "unused.json")
    assert not (tmp_path / cfg["workspace"]).exists()
    assert time.monotonic() - before < 1
