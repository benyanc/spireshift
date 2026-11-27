from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest
from test_engine_neural import model
from test_native_value_credit import public

from spireshift.engine_experience import score_episode, verified_native_samples
from spireshift.engine_neural import predict
from spireshift.native_credit_training import (
    CREDIT_ID,
    prepare_credit_samples,
    validate_credit_config,
)
from spireshift.training_objective import load_training_score_spec


def test_crossfit_changes_only_credit_after_exact_behavior_verification() -> None:
    score = load_training_score_spec(
        Path("configs/training-objective/sts2-v0.111.0-ironclad-a8-native-bootstrap-v8.json")
    )
    m = model()
    cases, batches = [], []
    for seed in (1, 2):
        p = public()
        # Keep the actual actor's complete-menu contract in this synthetic control.
        p["candidates"] = [{"verb": "skip", "arguments": []}, {"verb": "select", "arguments": []}]
        case: dict[str, Any] = {
            "status": "terminal",
            "recovered": False,
            "privileged_fixture": False,
            "native_ending_evidence_agrees": True,
            "victory": False,
            "completed_acts": 0,
            "maximum_floor": 5 + seed,
            "cpu_seconds": 0.1,
            "decisions": [{"public_input": p, "choice": predict(m, p, random.Random(seed), 1.0)}],
        }
        case["score"] = score_episode(case, seed, score)
        cases.append(case)
        batches.append(verified_native_samples(case, m, case["score"]["training_return"], 1.0))
    credit: dict[str, Any] = {
        "id": CREDIT_ID,
        "baseline": "public_residual_ridge",
        "regularization": 0.001,
        "folds": 4,
        "fold_salt": "native-whole-run-value-crossfit-v1",
        "trace_lambda": 1.0,
    }
    original = batches[0] + batches[1]
    prepared, report = prepare_credit_samples(cases, original, credit, score, 1)
    assert prepared != original and report is not None
    for a, b in zip(original, prepared, strict=True):
        assert (a.rows, a.state, a.target, a.action, a.old_log_probability) == (
            b.rows,
            b.state,
            b.target,
            b.action,
            b.old_log_probability,
        )
    assert report["independent_training_runs"] == 2
    assert all(
        set(f["fitting_runs"]).isdisjoint(f["predicted_runs"]) for f in report["baseline_models"]
    )
    _, reordered = prepare_credit_samples(
        list(reversed(cases)), batches[1] + batches[0], credit, score, 1
    )
    assert report == reordered
    assert prepare_credit_samples(cases, original, None, score, 1) == (original, None)
    with pytest.raises(ValueError):
        prepare_credit_samples(cases, original[:-1], credit, score, 1)
    with pytest.raises(ValueError):
        prepare_credit_samples(cases, original, {**credit, "trace_lambda": 0.95}, score, 1)


def test_untested_credit_variants_are_rejected_before_loading_evidence() -> None:
    validate_credit_config(Path("."), None, "legacy")
    for bad in ({}, {"id": "invented"}, {"id": CREDIT_ID, "trace_lambda": 0.95}):
        with pytest.raises(ValueError, match="tested cross-fit"):
            validate_credit_config(Path("."), bad, "score")
