from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
from test_native_action_context import model, score
from test_native_situation_bank import public

import spireshift.native_value_credit as value_module
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import save_native_episode
from spireshift.native_context_cache import cached_model
from spireshift.native_experience_diagnostic_data import prepare, restore_predictions
from spireshift.native_experience_feedback import matched_feedback
from spireshift.native_structured_policy import CONTRACT, Chooser
from spireshift.native_structured_training import prepare as original_prepare
from spireshift.native_value_credit import ValueRun, cross_fitted_predictions

CREDIT: dict[str, Any] = {
    "baseline": "public_residual_ridge",
    "regularization": 0.001,
    "folds": 2,
    "fold_salt": "diagnostic-test",
}


def runs() -> list[ValueRun]:
    x = (1.0, *([0.0] * 19))
    return [
        ValueRun(i, 1, 0.1 + i / 100, (x, x), (0.01, 0.02), (0.0, 0.0), (2, 1)) for i in range(4)
    ]


def test_saved_coefficients_restore_without_refitting_or_fitting_their_own_outcomes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = runs()
    expected, saved = cross_fitted_predictions(
        records, CREDIT["baseline"], CREDIT["regularization"], 2, CREDIT["fold_salt"]
    )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("The diagnostic must not fit a value baseline")

    monkeypatch.setattr(value_module, "fit_baseline", forbidden)
    assert restore_predictions(records, saved, CREDIT) == expected
    assert restore_predictions(list(reversed(records)), saved, CREDIT) == expected


@pytest.mark.parametrize("fault", ["self_fit", "missing_fold", "feature", "penalty", "nan"])
def test_wrong_saved_fold_ownership_or_coefficients_are_rejected(fault: str) -> None:
    records = runs()
    _, saved = cross_fitted_predictions(
        records, CREDIT["baseline"], CREDIT["regularization"], 2, CREDIT["fold_salt"]
    )
    if fault == "self_fit":
        saved[0]["fitting_runs"].append(saved[0]["predicted_runs"][0])
    elif fault == "missing_fold":
        saved.pop()
    elif fault == "feature":
        saved[0]["features"][0] = "foreign"
    elif fault == "penalty":
        saved[0]["regularization"] = 1.0
    else:
        saved[0]["weights"][0] = float("nan")
    with pytest.raises(ValueError):
        restore_predictions(records, saved, CREDIT)


def episodes(root: Path) -> tuple[Any, dict[str, Any], dict[str, Any], list[Path], dict[str, Any]]:
    m = cached_model(model())
    cfg = {
        "seed_manifest": {"id": "manifest"},
        "environment_manifest": {"id": m.actor.environment_id},
        "training_spec": {"id": score().spec_id},
        "credit": CREDIT,
    }
    seeds: list[dict[str, Any]] = [{"id": i, "seed": f"CAN0N1CAL{i}"} for i in range(4)]
    paths = []
    for seed in seeds:
        p = public(floor=5 + seed["id"])
        p["context"]["persistent"]["run"]["act_definition_id"] = "UNDERDOCKS"
        choice = Chooser(m, score(), seed["seed"], True)(p)
        case = {
            "seed": seed["seed"],
            "status": "terminal",
            "victory": False,
            "maximum_floor": 8 + seed["id"],
            "completed_acts": 0,
            "cpu_seconds": 0.1,
            "native_ending_evidence_agrees": True,
            "privileged_fixture": False,
            "privileged_fixed_world_teacher": False,
            "recovered": False,
            "ordinary_PPO_eligible": True,
            "policy_contract": CONTRACT,
            "decisions": [{"public_input": p, "choice": choice}],
        }
        binding = {
            "config_id": manifest_identifier(cfg),
            "seed_manifest_id": "manifest",
            "seed_id": seed["id"],
            "native_seed": seed["seed"],
            "partition": "train",
            "panel_purpose": "training",
            "model_id": m.model_id,
            "environment_id": m.actor.environment_id,
            "training_spec_id": score().spec_id,
            "policy_contract": CONTRACT,
        }
        path = root / f"game-{seed['id']}.json"
        save_native_episode(path, case, binding)
        paths.append(path)
    _, credit = original_prepare(paths, m, score(), cfg, seeds, 1)
    return m, cfg, {"round": 1, "seeds": seeds}, paths, credit


def test_saved_train_samples_and_inventory_reconstruct_without_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    m, cfg, task, paths, credit = episodes(tmp_path)
    expected, _ = original_prepare(paths, m, score(), cfg, task["seeds"], 1)
    before = {str(p): p.read_bytes() for p in tmp_path.iterdir()}
    monkeypatch.setattr(
        value_module, "fit_baseline", lambda *a: pytest.fail("Unexpected baseline fit")
    )
    samples, metadata, details = prepare(
        tmp_path, cfg, task, [p.name for p in paths], m, score(), credit, time.monotonic() + 10
    )
    assert [s.advantage for s in samples] == [s.advantage for s in expected]
    assert len(samples) == len(metadata) == details["games"] == 4
    assert details["inventory_coverage"]["distinct_card_definitions"] == 2
    assert details["credit_reconstruction"]["baseline_refits"] == 0
    assert len(details["per_game_feedback"]) == 4
    assert {str(p): p.read_bytes() for p in tmp_path.iterdir()} == before


@pytest.mark.parametrize(
    "fault", ["development", "stale", "duplicate", "missing", "bad_denominator"]
)
def test_bad_source_ownership_or_denominator_stops_the_diagnostic(
    tmp_path: Path, fault: str
) -> None:
    m, cfg, task, paths, credit = episodes(tmp_path)
    names = [p.name for p in paths]
    if fault in {"development", "stale"}:
        doc = json.loads(paths[0].read_text())
        doc["binding"]["partition" if fault == "development" else "model_id"] = (
            "development" if fault == "development" else "foreign"
        )
        paths[0].write_text(json.dumps(doc))
    elif fault == "duplicate":
        names[1] = names[0]
    elif fault == "missing":
        names.pop()
    else:
        credit["decisions"] += 1
    with pytest.raises(ValueError):
        prepare(tmp_path, cfg, task, names, m, score(), credit, time.monotonic() + 10)


def result(arm: str) -> dict[str, Any]:
    return {
        "player": 2,
        "arm": arm,
        "before_model_id": "same",
        "planned_games": 1,
        "normalization_and_game_weighting": {"raw_advantage_mean": 0.0, "raw_advantage_std": 1.0},
        "per_game_feedback": [
            {
                "seed_id": 1,
                "learning_trace_id": "trace",
                "raw_advantages": [0.1, -0.2],
                "choice_mask": [True, True],
            }
        ],
    }


def test_shared_history_feedback_difference_is_measured_without_claiming_correctness() -> None:
    a, b = result("batch32"), result("batch128")
    b["per_game_feedback"][0]["raw_advantages"][0] = -0.1
    c = matched_feedback([a, b])[0]
    assert c["all_small_batch_games_matched"]
    assert c["normalized_feedback_sign_disagreement_fraction"] == 0.5
    assert c["small_baseline_mse_on_shared_games"] == pytest.approx(0.025)
    assert "not_action_quality" in c["scope"]


@pytest.mark.parametrize("fault", ["trace", "model", "failed_world"])
def test_unmatched_train_histories_are_not_treated_as_identical_states(fault: str) -> None:
    a, b = result("batch32"), result("batch128")
    if fault == "trace":
        b["per_game_feedback"][0]["learning_trace_id"] = "different"
    elif fault == "model":
        b["before_model_id"] = "different"
    else:
        b["planned_games"] = 2
    c = matched_feedback([a, b])[0]
    assert not c["all_small_batch_games_matched"]
    assert c["normalized_feedback_sign_disagreement_fraction"] is None
    assert c["large_baseline_mse_on_shared_games"] is None


def test_shared_feedback_does_not_compare_a_half_finished_pair() -> None:
    assert matched_feedback([result("batch32")]) == []


def test_shared_feedback_rejects_short_vectors_even_with_a_matching_trace_id() -> None:
    a, b = result("batch32"), result("batch128")
    b["per_game_feedback"][0]["raw_advantages"].pop()
    with pytest.raises(ValueError):
        matched_feedback([a, b])
