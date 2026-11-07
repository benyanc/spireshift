from __future__ import annotations

import copy
import random
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from test_native_action_context import model, score, settings
from test_native_context_trial import case

import spireshift.native_optimizer_probe as probe
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import save_native_episode
from spireshift.engine_qualification import EngineQualificationConfig
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Adam, fit_round
from spireshift.native_action_context import CROSSED
from spireshift.native_context_cache import CachedContextModel, cached_model
from spireshift.native_context_game import predict, verified_samples
from spireshift.native_context_trial import prepare
from spireshift.native_value_credit import cross_fitted_predictions, value_run

CREDIT = {
    "baseline": "public_residual_ridge",
    "regularization": 0.001,
    "folds": 4,
    "fold_salt": "native-whole-run-value-crossfit-v1",
}


def batches() -> tuple[Any, list[probe.GameBatch], list[dict[str, Any]]]:
    m, s = cached_model(model()), score()
    games, cases = [], []
    for i in range(8):
        c = case(f"TRAIN{i}", lambda p, seed=i: predict(m, s, p, random.Random(seed), 0.8))
        c["maximum_floor"] = 2 + i % 4 * 2
        run = value_run(c, i, 1, s)
        games.append(probe.GameBatch(run, tuple(verified_samples(c, m, s, run.target, 0.8))))
        cases.append(c)
    return m, games, cases


def test_probe_preserves_production_game_order_cross_fitting_and_normalization(
    tmp_path: Path,
) -> None:
    m, games, cases = batches()
    paths = []
    for game, c in zip(games, cases, strict=True):
        p = tmp_path / f"case-{game.run.seed}.json"
        save_native_episode(
            p,
            c,
            {
                "partition": "train",
                "panel_purpose": "training",
                "model_id": m.model_id,
                "seed_id": game.run.seed,
            },
        )
        paths.append(p)
    samples, _ = prepare(paths, m, score(), settings(), CREDIT, 1)
    assert probe.credit_samples(games, CREDIT) == samples
    with pytest.raises(ValueError, match="distinct"):
        probe.credit_samples([*games, games[0]], CREDIT)


def test_movement_zero_at_behavior_and_reports_real_fitting_without_strength_claim() -> None:
    m, games, _ = batches()
    samples = probe.credit_samples(games, CREDIT)
    normalized = probe.normalized(samples)
    identity = probe.movement(m, m, normalized, settings())
    assert identity["mean_choice_total_variation"] == 0
    assert identity["clipped_training_surrogate_gain"] == 0
    updated, _, _ = fit_round(cast(Any, m), Adam.zero(m.parameter_count), samples, settings(), 1)
    assert isinstance(updated, CachedContextModel)
    change = probe.movement(m, updated, normalized, settings())
    assert change["advantage_weighted_log_probability_movement"] > 0
    assert change["mean_choice_total_variation"] > 0
    assert change["mean_choice_menu_forward_kl"] > 0
    assert change["claim_scope"] == "in_sample_training_signal_fit_not_action_quality_or_gameplay"
    broken = [replace(normalized[0], old_log_probability=1), *normalized[1:]]
    with pytest.raises(ValueError, match="different behavior"):
        probe.movement(m, updated, broken, settings())


def test_independent_groups_do_not_share_games_outcomes_or_normalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    m, games, _ = batches()
    seen: list[set[int]] = []
    original = cross_fitted_predictions

    def record(runs: Any, *args: Any) -> Any:
        seen.append({r.seed for r in runs})
        return original(runs, *args)

    monkeypatch.setattr(probe, "cross_fitted_predictions", record)
    report = probe.independent_groups(m, games, settings(), CREDIT)
    assert len(seen) == 2 and not seen[0] & seen[1] and seen[0] | seen[1] == set(range(8))
    assert report["games_per_group"] == [4, 4]
    assert report["single_split_diagnostic_not_population_confidence"]


@pytest.mark.parametrize("fault", [None, "development", "model", "panel", "config", "manifest"])
def test_cohort_loader_refuses_wrong_ownership_and_never_uses_evaluation(
    tmp_path: Path, fault: str | None
) -> None:
    m, _, cases = batches()
    context = {"legacy_recipe": {"path": "legacy.json"}}
    legacy = {"workspace": "artifacts/legacy", "seed_manifest": {"id": "seeds"}}
    atomic_json(tmp_path / "context.json", context)
    atomic_json(tmp_path / "legacy.json", legacy)
    arm = tmp_path / "artifacts/legacy" / f"{CROSSED}-seed-0"
    atomic_json(arm / "initial-model.json", m.as_dict())
    atomic_json(arm / "round-001-model.json", m.as_dict())
    for i in range(32):
        c = cases[i % len(cases)]
        binding = {
            "partition": "train",
            "panel_purpose": "training",
            "model_id": m.model_id,
            "panel": "round-001",
            "config_id": manifest_identifier(legacy),
            "seed_manifest_id": "seeds",
            "environment_id": m.actor.environment_id,
            "training_spec_id": score().spec_id,
            "seed_id": 820001 + i,
        }
        if i == 0:
            field = {
                "development": "partition",
                "model": "model_id",
                "panel": "panel",
                "config": "config_id",
                "manifest": "seed_manifest_id",
            }.get(fault or "")
            if field:
                binding[field] = "wrong"
        save_native_episode(arm / f"round-001/case-{820001 + i}.json", c, binding)
    q = EngineQualificationConfig(document={}, root=tmp_path)
    parent = {
        "environment_manifest": {"id": m.actor.environment_id},
        "learning": {"ppo": settings()},
    }
    cfg = {"source_recipe": {"path": "context.json"}}
    if fault:
        with pytest.raises(ValueError, match="own-behavior TRAIN"):
            probe.cohort(q, cfg, parent, 0, score())
    else:
        _, opt, games, expected, sources = probe.cohort(q, cfg, parent, 0, score())
        assert opt.steps == 0 and len(games) == 32 and expected == m.model_id
        assert len(sources) == 66


def test_probe_settings_are_one_factor_interventions() -> None:
    for variant in probe.VARIANTS:
        changed = copy.deepcopy(settings())
        changed["actor_learning_rate"] *= variant["actor_rate_multiplier"]
        changed["epochs"] *= variant["epochs_multiplier"]
        assert sum(changed[k] != settings()[k] for k in changed) == (
            0 if variant["name"] == "standard" else 1
        )
