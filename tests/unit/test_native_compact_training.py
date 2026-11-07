from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from test_native_action_context import score, settings
from test_native_optimizer_probe import CREDIT, batches

from spireshift.engine_experience import save_native_episode
from spireshift.full_run_ppo_math import Adam, fit_round, loss_gradient
from spireshift.native_compact_training import PackedRow, pack, prepare_compact
from spireshift.native_context_trial import prepare


def test_compact_rows_preserve_float_bits_and_are_read_only() -> None:
    source = {12: 1e-300, 3: -3.141592653589793, 500: 0.0}
    packed = PackedRow(source)
    assert dict(packed.items()) == source and packed[3] == source[3]
    assert packed.amounts.readonly and packed.positions.readonly
    with pytest.raises(TypeError):
        packed[3] = 4  # type: ignore[index]
    with pytest.raises(TypeError):
        packed.amounts[0] = 4
    with pytest.raises(KeyError):
        _ = packed[4]
    for bad in ({-1: 1.0}, {65536: 1.0}, {0: float("inf")}):
        with pytest.raises(ValueError):
            PackedRow(bad)


def test_packed_rows_produce_identical_losses_gradients_weights_and_adam() -> None:
    m, games, _ = batches()
    original = [s for g in games for s in g.samples]
    original = [replace(s, advantage=s.target - 0.02) for s in original]
    compact = [pack(s) for s in original]
    kwargs = {
        "clip": 0.2,
        "entropy_coefficient": 0.015,
        "value_coefficient": 0.5,
        "temperature": 0.8,
    }
    assert loss_gradient(cast(Any, m), original, **kwargs) == loss_gradient(
        cast(Any, m), compact, **kwargs
    )
    a, ao, _ = fit_round(cast(Any, m), Adam.zero(m.parameter_count), original, settings(), 1)
    b, bo, _ = fit_round(cast(Any, m), Adam.zero(m.parameter_count), compact, settings(), 1)
    assert a.as_dict() == b.as_dict() and ao == bo


def test_streamed_compact_preparation_preserves_credit_and_refuses_eval(tmp_path: Path) -> None:
    m, games, cases = batches()
    paths = []
    for g, c in zip(games, cases, strict=True):
        p = tmp_path / f"case-{g.run.seed}.json"
        save_native_episode(
            p,
            c,
            {
                "partition": "train",
                "panel_purpose": "training",
                "model_id": m.model_id,
                "seed_id": g.run.seed,
                "environment_id": m.actor.environment_id,
                "training_spec_id": score().spec_id,
            },
        )
        paths.append(p)
    a, ar = prepare(paths, m, score(), settings(), CREDIT, 1)
    b, br = prepare_compact(paths, m, score(), settings(), CREDIT, 1)
    assert (
        a == b
        and br["all_source_decisions_retained"]
        and br["maximum_raw_episode_histories_retained"] == 1
    )
    assert all(isinstance(r, PackedRow) for s in b for r in s.rows)
    for k in ("cross_fit", "prediction_quality", "decisions", "choice_decisions"):
        assert ar[k] == br[k]
    header = json.loads(paths[0].read_text())
    header["binding"]["partition"] = "development"
    paths[0].write_text(json.dumps(header))
    with pytest.raises(ValueError, match="current-behavior"):
        prepare_compact(paths, m, score(), settings(), CREDIT, 1)
