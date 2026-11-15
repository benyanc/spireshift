from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from spireshift.native_inventory_credit_data import (
    alias_diagnostics,
    effective_rows,
    verify_binding,
)
from spireshift.native_inventory_credit_features import inventory
from spireshift.native_inventory_credit_math import (
    METHODS,
    SALT,
    credit_diagnostics,
    forecasts,
    runs,
)
from spireshift.native_inventory_credit_report import restore_forecasts
from spireshift.native_value_credit import FEATURES, fold_assignment, public_value_features
from spireshift.training_objective import load_training_score_spec


def public() -> dict[str, Any]:
    relics = [{"definition_id": "RELIC_A"}, {"definition_id": "RELIC_B"}]
    return {
        "schema_version": "actual-engine-public-entity-graph-v1",
        "context": {
            "persistent": {
                "run": {"act": 1, "floor": 5},
                "player": {"hp": 40, "max_hp": 80, "gold": 100, "relics": relics, "potions": []},
            },
            "interaction": {
                "kind": "rest_site",
                "content": {
                    "context": {
                        "player": {
                            "relics": [
                                {"id": "RELIC_A", "counter": 2},
                                {"id": "RELIC_B", "counter": 7},
                            ]
                        }
                    }
                },
            },
            "reads": [
                {
                    "kind": "run_deck",
                    "content": {
                        "card_count": 2,
                        "cards": [
                            {"definition_id": "CARD_A", "is_upgraded": False, "cost": "1"},
                            {
                                "definition_id": "CROSS_CHARACTER_CARD",
                                "is_upgraded": True,
                                "cost": "0",
                            },
                        ],
                    },
                }
            ],
        },
        "candidates": [{"verb": "skip"}, {"verb": "select"}],
    }


def score() -> Any:
    return load_training_score_spec(
        Path("configs/training-objective/sts2-v0.111.0-ironclad-a8-native-bootstrap-v8.json")
    )


@pytest.mark.parametrize("field", ["deck", "relic"])
def test_same_counts_can_hide_different_owned_definitions(field: str) -> None:
    p = public()
    original = inventory(p)
    before = public_value_features(p, score())
    if field == "deck":
        p["context"]["reads"][0]["content"]["cards"][0]["definition_id"] = "DIFFERENT_CARD"
    else:
        p["context"]["persistent"]["player"]["relics"][0]["definition_id"] = "DIFFERENT_RELIC"
        p["context"]["interaction"]["content"]["context"]["player"]["relics"][0]["id"] = (
            "DIFFERENT_RELIC"
        )
    assert public_value_features(p, score()) == before
    assert inventory(p)["values"] != original["values"]
    assert inventory(p)[field + "_signature"] != original[field + "_signature"]


def test_inventory_is_a_bag_and_does_not_use_chosen_offered_actions_or_slots() -> None:
    p = public()
    before = inventory(p)
    p["context"]["reads"][0]["content"]["cards"].reverse()
    p["context"]["persistent"]["player"]["relics"].reverse()
    p["context"]["interaction"]["content"]["context"]["player"]["relics"].reverse()
    p["candidates"] = [{"verb": "different", "label": "DIFFERENT_OFFERED_CARD"}]
    p["context"]["persistent"]["player"]["entity_id"] = {"public_slot": 999}
    assert inventory(p) == before


@pytest.mark.parametrize("field,value", [("is_upgraded", True), ("cost", "0"), ("cost", 1)])
def test_per_copy_upgrade_and_typed_displayed_cost_are_distinguished(
    field: str, value: Any
) -> None:
    p = public()
    before = inventory(p)
    p["context"]["reads"][0]["content"]["cards"][0][field] = value
    assert inventory(p)["deck_signature"] != before["deck_signature"]
    assert inventory(p)["values"] != before["values"]


def test_relic_amounts_stay_with_their_definition_and_numeric_zero_is_present() -> None:
    p = public()
    before = inventory(p)
    relics = p["context"]["interaction"]["content"]["context"]["player"]["relics"]
    relics[0]["counter"], relics[1]["counter"] = 7, 2
    assert inventory(p)["values"] != before["values"]
    relics[0]["counter"] = 0
    assert "relic/counter/RELIC_A" in inventory(p)["values"]
    assert inventory(p)["values"]["relic/counter/RELIC_A"] == 0


def test_cost_upgrade_pairs_remain_attached_to_each_card_copy() -> None:
    p = public()
    cards = p["context"]["reads"][0]["content"]["cards"]
    cards[1]["definition_id"] = cards[0]["definition_id"]
    before = inventory(p)
    cards[0]["cost"], cards[1]["cost"] = cards[1]["cost"], cards[0]["cost"]
    assert inventory(p)["values"] != before["values"]


@pytest.mark.parametrize(
    "fault", ["missing_deck", "missing_upgrade", "wrong_counters", "private", "opaque"]
)
def test_missing_or_private_inventory_is_rejected(fault: str) -> None:
    p = public()
    if fault == "missing_deck":
        del p["context"]["reads"][0]["content"]["cards"]
    elif fault == "missing_upgrade":
        del p["context"]["reads"][0]["content"]["cards"][0]["is_upgraded"]
    elif fault == "wrong_counters":
        p["context"]["interaction"]["content"]["context"]["player"]["relics"][0]["id"] = "OTHER"
    elif fault == "private":
        p["context"]["seed"] = "SECRET_WORLD"
    else:
        p["context"]["persistent"]["player"]["entity_id"] = "opaque-handle"
    with pytest.raises(ValueError):
        inventory(p)


def data() -> tuple[dict[str, Any], list[str]]:
    worlds = np.repeat(np.arange(16), 2)
    x = np.zeros((len(worlds), len(FEATURES)))
    x[:, 0] = 1
    extras = np.column_stack((worlds % 2, (worlds // 2) % 2)).astype(float)
    return {
        "world": worlds,
        "coarse": x,
        "target": 0.3 + 0.4 * (worlds % 2),
        "potential": np.zeros(len(worlds)),
        "behavior_value": np.zeros(len(worlds)),
        "choices": np.full(len(worlds), 2),
        "log_probability": np.full(len(worlds), np.log(0.5)),
        "family": np.asarray(["combat_turn"] * len(worlds)),
        "inventory": extras,
        "inventory_present": np.ones_like(extras, dtype=bool),
    }, ["deck/id/SIGNAL", "relic/id/INDEPENDENT"]


def fit(d: dict[str, Any], names: list[str], directory: Path) -> tuple[Any, Any]:
    import time

    directory.mkdir()
    with (directory / "extracted.npz").open("xb") as handle:
        np.savez_compressed(handle, **d)
    predicted, report = forecasts(d, names, 1, directory, time.monotonic() + 30)
    with (directory / "forecasts.npz").open("xb") as handle:
        np.savez_compressed(handle, **predicted)
    return predicted, report


def test_typed_inventory_probe_learns_planted_signal_and_restores_without_refitting(
    tmp_path: Path,
) -> None:
    d, names = data()
    _, report = fit(d, names, tmp_path / "fit")
    errors = report["prediction"]["mse"]
    assert errors["deck"] < errors["current"]
    restored = restore_forecasts(tmp_path / "fit", {"names": names}, report["coarse_folds"], 1)
    assert restored["all_forecasts_restored_bit_for_bit"]
    assert restored["baseline_or_inventory_refits"] == 0


def test_held_world_targets_and_held_only_names_cannot_fit_their_own_forecast(
    tmp_path: Path,
) -> None:
    d, names = data()
    baseline, _ = fit(d, names, tmp_path / "base")
    assignment = fold_assignment(runs(d, 1), 4, SALT)
    held = np.asarray([assignment[int(i)] == 0 for i in d["world"]])
    changed = copy.deepcopy(d)
    changed["target"][held] = 0.99
    changed["inventory"] = np.column_stack((d["inventory"], held.astype(float)))
    changed["inventory_present"] = np.column_stack((d["inventory_present"], held))
    again, report = fit(changed, [*names, "deck/id/HELD_ONLY"], tmp_path / "changed")
    for method in (*METHODS, "constant"):
        assert np.array_equal(baseline[method][held], again[method][held])
    assert report["folds"][0]["variants"]["deck"]["held_only_columns"] == 1


def test_numeric_zero_observed_in_fit_is_not_a_held_only_feature(tmp_path: Path) -> None:
    d, names = data()
    assignment = fold_assignment(runs(d, 1), 4, SALT)
    held = np.asarray([assignment[int(i)] == 0 for i in d["world"]])
    d["inventory"] = np.column_stack((d["inventory"], held.astype(float)))
    d["inventory_present"] = np.column_stack(
        (d["inventory_present"], np.ones(len(held), dtype=bool))
    )
    _, report = fit(d, [*names, "relic/counter/ZERO"], tmp_path / "fit")
    row = report["folds"][0]["variants"]["relic"]
    assert row["held_only_columns"] == 0
    assert row["fitting_columns"] == 2


def test_saved_forecast_corruption_is_detected(tmp_path: Path) -> None:
    d, names = data()
    predicted, report = fit(d, names, tmp_path / "fit")
    predicted["deck"][0] += 0.01
    with (tmp_path / "fit/forecasts.npz").open("wb") as handle:
        np.savez_compressed(handle, **predicted)
    with pytest.raises(ValueError, match="bit-for-bit"):
        restore_forecasts(tmp_path / "fit", {"names": names}, report["coarse_folds"], 1)


def test_restoration_uses_original_batch_layout_with_nontrivial_floating_point_inputs(
    tmp_path: Path,
) -> None:
    d, names = data()
    extra = np.random.default_rng(8).normal(size=(len(d["world"]), 30))
    d["inventory"] = np.column_stack((d["inventory"], extra))
    d["inventory_present"] = np.ones_like(d["inventory"], dtype=bool)
    names += [f"deck/numerical/{i}" for i in range(30)]
    _, report = fit(d, names, tmp_path / "fit")
    restored = restore_forecasts(tmp_path / "fit", {"names": names}, report["coarse_folds"], 1)
    assert restored["all_forecasts_restored_bit_for_bit"]


def test_selected_logit_coefficient_matches_finite_difference_and_forced_menu_is_zero() -> None:
    d, _ = data()
    d["choices"][-1] = 1
    d["log_probability"][-1] = 0
    predictions = {k: np.full(len(d["world"]), 0.5) for k in METHODS}
    report = credit_diagnostics(d, predictions)
    a = d["target"] - 0.5
    z = (a - a.mean()) / a.std()
    expected = np.where(d["choices"] > 1, z * 0.5 / 0.8, 0)
    row = report["whole_batch"]["methods"]["current"]["chosen_logit_ascent_coefficient"]
    assert row["mean"] == pytest.approx(float(expected[:-1].mean()))
    eps = 1e-6

    def objective(logit: float) -> float:
        return float(z[0] * (-np.log1p(np.exp(-logit / 0.8))))

    assert (objective(eps) - objective(-eps)) / (2 * eps) == pytest.approx(expected[0])


def test_zero_centered_credit_gives_no_chosen_logit_coefficient() -> None:
    d, _ = data()
    predictions = {k: d["target"].copy() for k in METHODS}
    report = credit_diagnostics(d, predictions)
    assert (
        report["whole_batch"]["methods"]["current"]["chosen_logit_ascent_coefficient"]["std"] == 0
    )


def test_alias_diagnosis_counts_information_loss_without_claiming_causal_effects() -> None:
    d, _ = data()
    d["deck_signature"] = np.asarray([f"deck-{int(i) % 2}" for i in d["world"]])
    d["relic_signature"] = np.asarray(["relic"] * len(d["world"]))
    result = alias_diagnostics(d)
    assert result["groups_with_distinct_decks"] == 1
    assert result["cross_world_inventory_alias_groups"] == 1
    assert not result["different_true_state_values_or_causal_effects_proven"]


def test_recovered_or_greedy_episodes_are_not_decoded_as_training() -> None:
    with pytest.raises(ValueError, match="clean unprivileged"):
        effective_rows({"status": "terminal", "recovered": True}, "model", score())


def test_binding_rejects_evaluation_foreign_models_and_worlds() -> None:
    source = {
        "seed_manifest": {"id": "seeds"},
        "environment_manifest": {"id": "env"},
        "training_spec": {"id": "score"},
    }
    with pytest.raises(ValueError, match="Reject evaluation"):
        verify_binding({"partition": "development"}, source, "model", {1: "WORLD"})
