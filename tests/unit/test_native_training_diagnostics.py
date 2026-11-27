from __future__ import annotations

import copy
import json
import random
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from test_native_action_context import model, score, settings
from test_native_context_trial import case
from test_native_optimizer_probe import CREDIT, batches

import spireshift.native_training_diagnostics as diagnostics
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import save_native_episode
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Adam, fit_round
from spireshift.native_context_cache import CachedContextModel, cached_model
from spireshift.native_context_game import predict
from spireshift.native_learning_control import TASKS, public_input
from spireshift.native_optimizer_probe import actor_gradient, credit_samples, normalized


def action(verb: str, role: str | None = None, **properties: Any) -> dict[str, Any]:
    return {
        "verb": verb,
        "subject": {"role": role, "properties": properties} if role else None,
        "label": "arbitrary text",
        "arguments": [],
    }


def public(family: str, actions: list[dict[str, Any]]) -> dict[str, Any]:
    p = public_input(TASKS[0], True)
    p["context"]["interaction"] = {"kind": family}
    p["candidates"] = actions
    return p


def test_structural_opportunities_do_not_turn_optional_actions_into_mistakes() -> None:
    p = public(
        "combat_turn",
        [action("play", "playable_card"), action("end_turn"), action("use", "potion")],
    )
    p["context"]["interaction"]["content"] = {"context": {"player": {"energy": 0}}}
    meta = diagnostics.decision_meta(p, 1)
    assert meta["opportunities"]["end_turn_with_play_available"] == [1]
    assert meta["energy"] == 0  # Free legal cards still count; no static-cost heuristic.
    assert meta["opportunities"]["potion_use"] == [2]
    p["candidates"] = [action("end_turn")]
    assert "end_turn_with_play_available" not in diagnostics.decision_meta(p, 0)["opportunities"]
    p = public(
        "card_reward_selection", [action("select", "card"), action("skip"), action("use", "potion")]
    )
    meta = diagnostics.decision_meta(p, 2)
    assert meta["opportunities"]["card_reward_skip"] == [1]
    assert meta["opportunities"]["card_reward_take"] == [0]  # Potion use is neither take nor skip.
    assert "mistake" not in meta


def test_rest_repeated_choices_shop_controls_and_outside_combat_potions_are_distinct() -> None:
    p = public(
        "rest_site",
        [
            action("activate", "rest_option", option_id="HEAL"),
            action("activate", "rest_option", option_id="SMITH"),
            action("close"),
        ],
    )
    for chosen in (0, 1, 2):
        m = diagnostics.decision_meta(p, chosen)
        assert m["opportunities"] == {"rest_option_HEAL": [0], "rest_option_SMITH": [1]}
    p = public(
        "shop_inventory",
        [
            action("activate", "shop_service"),
            action("close"),
            action("use", "potion"),
            action("activate", "potion", can_discard=True),
        ],
    )
    p["candidates"][1]["history"] = {"shop_inspected": False}
    m = diagnostics.decision_meta(p, 2)
    assert m["opportunities"]["potion_use"] == [2]
    assert m["opportunities"]["potion_discard"] == [3]
    assert m["opportunities"]["shop_purchase_or_service_control"] == [0]
    assert m["opportunities"]["shop_leave_without_prior_inspection"] == [1]
    p["candidates"][1]["history"]["shop_inspected"] = True
    assert (
        "shop_leave_without_prior_inspection"
        not in diagnostics.decision_meta(p, 1)["opportunities"]
    )
    del p["candidates"][1]["history"]
    assert (
        "shop_leave_without_prior_inspection"
        not in diagnostics.decision_meta(p, 1)["opportunities"]
    )


def test_weighting_preserves_forced_normalization_and_reports_game_length_inequality() -> None:
    m, games, _ = batches()
    s = games[0].samples[0]
    samples = [replace(s, advantage=-2), replace(s, advantage=2)]
    forced = replace(s, rows=(s.rows[0],), action=0, old_log_probability=0, advantage=100)
    samples.append(forced)
    metadata = [
        {"seed_id": 1, "family": "combat_turn"},
        {"seed_id": 2, "family": "event_option"},
        {"seed_id": 2, "family": "reward_completion"},
    ]
    r = diagnostics.weighting(samples, metadata)
    assert r["forced_decisions"] == 1 and r["choice_decisions"] == 2
    assert r["choice_sign_changes_if_normalized_without_forced"] == 1
    assert r["effective_games_from_choice_counts"] == 2
    assert sum(g["nominal_actor_choice_weight"] for g in r["games"]) == pytest.approx(2 / 3)
    assert r["nominal_weights_and_credit_mass_are_not_net_gradient_influence"]
    g = actor_gradient(m, normalized([forced]), settings(), 0)
    assert all(v == 0 for v in g)  # A single-option menu cannot teach the actor an alternative.


def test_policy_movement_and_family_gradients_match_the_unmodified_numerical_kernel() -> None:
    m, games, cases = batches()
    samples = credit_samples(games, CREDIT)
    metas = [
        {**diagnostics.decision_meta(c["decisions"][0]["public_input"], s.action), "seed_id": i}
        for i, (s, c) in enumerate(zip(samples, cases, strict=True))
    ]
    for i, meta in enumerate(metas):
        meta["family"] = "family_a" if i % 2 else "family_b"
    identity = diagnostics.measure(m, m, samples, metas, settings())
    assert identity["global_clipped_surrogate_gain"] == 0
    assert identity["families"][0]["mean_choice_tv"] == 0
    updated, _, _ = fit_round(cast(Any, m), Adam.zero(m.parameter_count), samples, settings(), 1)
    assert isinstance(updated, CachedContextModel)
    changed = diagnostics.measure(m, updated, samples, metas, settings())
    assert changed["global_advantage_weighted_log_movement"] > 0
    direct = actor_gradient(m, normalized(samples), settings(), 0)
    from spireshift.neural_combat import _numpy

    assert changed["initial_data_gradient_norm"] == pytest.approx(
        float(_numpy().linalg.norm(direct))
    )
    assert not changed["action_quality_or_causal_mistakes_established"]
    broken = [replace(samples[0], old_log_probability=3), *samples[1:]]
    with pytest.raises(ValueError, match="reconstruct"):
        diagnostics.measure(m, m, broken, metas, settings())
    with pytest.raises(TimeoutError):
        diagnostics.measure(m, m, samples, metas, settings(), 0)


def saved(tmp_path: Path, fault: str | None = None) -> tuple[Any, ...]:
    m, spec = cached_model(model()), score()
    cohort: dict[str, Any] = {
        "number": 0,
        "source_config": {"id": "cfg"},
        "seed_manifest": {"id": "seeds"},
        "cases": [],
    }
    for i in range(8):
        c = case(f"TRAIN{i}", lambda p, seed=i: predict(m, spec, p, random.Random(seed), 0.8))
        c["private_final_identity"] = {"secret": "must not appear in the report"}
        b = {
            "partition": "train",
            "panel_purpose": "training",
            "model_id": m.model_id,
            "seed_id": i,
            "native_seed": c["seed"],
            "config_id": "cfg",
            "seed_manifest_id": "seeds",
            "environment_id": m.actor.environment_id,
            "training_spec_id": spec.spec_id,
        }
        if i == 0:
            if fault == "development":
                b["partition"] = "development"
            if fault == "partial":
                c["status"] = "failed"
            if fault == "fixture":
                c["privileged_fixture"] = True
            if fault == "recovered":
                c["recovered"] = True
            if fault == "seed":
                b["native_seed"] = "unowned"
            if fault == "model":
                b["model_id"] = "stale"
            if fault == "probability":
                c["decisions"][0]["choice"]["log_probability"] += 1
        p = tmp_path / f"case-{i}.json"
        save_native_episode(p, c, b)
        cohort["cases"].append({"path": p.name, "seed_id": i, "native_seed": f"TRAIN{i}"})
    atomic_json(tmp_path / "before.json", m.as_dict())
    cohort.update(
        before={"path": "before.json", "kind": "model", "id": m.model_id},
        after={"path": "before.json", "kind": "model", "id": m.model_id},
        expected_decisions=8,
    )
    parent = {
        "training_spec": {"path": "unused.json"},
        "learning": {"ppo": settings(), "credit_assignment": CREDIT},
    }
    return m, cohort, parent


@pytest.mark.parametrize(
    "fault", ["development", "partial", "fixture", "recovered", "seed", "model", "probability"]
)
def test_only_clean_completed_own_behavior_training_can_be_diagnosed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    _, c, parent = saved(tmp_path, fault)
    monkeypatch.setattr(diagnostics, "load_training_score_spec", lambda *_: score())
    with pytest.raises(ValueError):
        diagnostics.diagnose(tmp_path, {}, parent, c, time.monotonic() + 10)


def test_diagnostic_is_read_only_uses_public_fields_and_does_not_update_models(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, c, parent = saved(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    monkeypatch.setattr(diagnostics, "load_training_score_spec", lambda *_: score())
    monkeypatch.setattr(Adam, "update", lambda *_a, **_k: pytest.fail("No optimizer may run"))
    r = diagnostics.diagnose(tmp_path, {}, parent, c, time.monotonic() + 10)
    assert r["games"] == 8 and r["decisions"] == 8
    assert "secret" not in json.dumps(r) and "must not appear" not in json.dumps(r)
    assert r["credit_reconstruction"]["no_self_outcome_fitting"]
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
    text = diagnostics.summary_text([r])
    assert "not optimal-action" in text and "Cohort 0" in text


def test_completed_reports_are_sealed_and_reopening_performs_no_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, c, parent = saved(tmp_path)
    monkeypatch.setattr(diagnostics, "load_training_score_spec", lambda *_: score())
    result = diagnostics.diagnose(tmp_path, {}, parent, c, time.monotonic() + 10)
    raw = result["normalization_and_game_weighting"]
    probe = {
        "report_id": "source",
        "sources": {"before.json": _sha_file(tmp_path / "before.json")},
        "results": [
            {
                "cohort": 0,
                "variant": "standard",
                "work": {k: raw[k] for k in ("raw_advantage_mean", "raw_advantage_std")},
                "movement": {"clipped_training_surrogate_gain": 0},
            }
        ],
    }
    atomic_json(tmp_path / "probe.json", probe)
    cfg = {
        "workspace": "artifacts/completed-only",
        "resource_limits": {"wall_seconds": 240},
        "protected_files_sha256": {},
        "implementation_sha256": {},
        "probe_report": {"path": "probe.json"},
        "cohorts": [c],
    }
    atomic_json(tmp_path / "recipe.json", cfg)
    monkeypatch.setattr(diagnostics, "load", lambda *_: (cfg, parent, probe))
    monkeypatch.setattr(diagnostics, "diagnose", lambda *_: copy.deepcopy(result))
    a = diagnostics.run(tmp_path, tmp_path / "recipe.json")
    monkeypatch.setattr(
        diagnostics, "diagnose", lambda *_: pytest.fail("Completed evidence is reused")
    )
    assert diagnostics.run(tmp_path, tmp_path / "recipe.json") == a
    assert (
        a["games_launched"]
        == a["policy_optimizer_steps"]
        == a["running_experiment_records_read"]
        == 0
    )
    p = tmp_path / a["summary_path"]
    p.write_text(p.read_text() + "tampered")
    with pytest.raises(ValueError, match="changed"):
        diagnostics.run(tmp_path, tmp_path / "recipe.json")


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "running_report",
        "unsealed_case",
        "repeated_game",
        "wrong_native_seed",
        "protected_change",
    ],
)
def test_loader_binds_a_completed_report_train_ownership_and_unchanged_protected_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    _, c, parent = saved(tmp_path)
    seeds = {"seeds": [{"id": i, "seed": f"TRAIN{i}", "partition": "train"} for i in range(8)]}
    sid = manifest_identifier(seeds)
    atomic_json(tmp_path / "seeds.json", {**seeds, "manifest_id": sid})
    c["seed_manifest"] = {"path": "seeds.json", "id": sid}
    source = {"seed_manifest": c["seed_manifest"]}
    atomic_json(tmp_path / "source.json", source)
    c["source_config"] = {"path": "source.json", "id": manifest_identifier(source)}
    (tmp_path / "protected.txt").write_text("original")
    protected = {"protected.txt": _sha_file(tmp_path / "protected.txt")}
    probe_config: dict[str, Any] = {}
    report: dict[str, Any] = {
        "status": "running" if fault == "running_report" else "train_only_optimizer_probe_complete",
        "config_id": manifest_identifier(probe_config),
        "results": [
            {
                "cohort": 0,
                "variant": "standard",
                "before_model_id": c["before"]["id"],
                "after_model_id": c["after"]["id"],
                "source_games": 8,
            }
        ],
        "sources": {p.name: _sha_file(p) for p in tmp_path.iterdir() if p.is_file()},
    }
    if fault == "unsealed_case":
        del report["sources"]["case-0.json"]
    if fault == "repeated_game":
        c["cases"][1]["seed_id"] = 0
    if fault == "wrong_native_seed":
        c["cases"][0]["native_seed"] = "other"
    atomic_json(tmp_path / "report.json", {**report, "report_id": manifest_identifier(report)})
    cfg = {
        "schema_version": "native-completed-training-diagnostics-config-v1",
        "qualification": "unused",
        "probe_config": {"path": "unused", "id": manifest_identifier(probe_config)},
        "probe_report": {"path": "report.json", "id": manifest_identifier(report)},
        "implementation_sha256": {},
        "protected_files_sha256": protected,
        "resource_limits": {
            "wall_seconds": 240,
            "cpu_seconds": 240,
            "resident_memory_bytes": 1000000000,
            "storage_bytes": 100000000,
        },
        "maximum_games": 64,
        "cohorts": [c],
    }
    atomic_json(tmp_path / "config.json", cfg)
    if fault == "protected_change":
        (tmp_path / "protected.txt").write_text("changed")
    monkeypatch.setattr(diagnostics, "SOURCES", ())
    monkeypatch.setattr(diagnostics, "load_engine_qualification_config", lambda *_: object())
    monkeypatch.setattr(diagnostics, "load_probe", lambda *_: (probe_config, parent))
    if fault:
        with pytest.raises(ValueError):
            diagnostics.load(tmp_path, tmp_path / "config.json")
    else:
        assert diagnostics.load(tmp_path, tmp_path / "config.json")[0] == cfg
