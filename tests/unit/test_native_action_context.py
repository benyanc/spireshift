from __future__ import annotations

import copy
import json
import math
import time
from pathlib import Path
from typing import Any, cast

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import DIRECT, NativeActorCritic, encode_public_input
from spireshift.full_run_ppo_math import Adam
from spireshift.native_action_context import (
    CROSSED,
    MODES,
    ORIGINAL,
    SHARED,
    ActionContextModel,
    encode,
    initialize,
    policy,
)
from spireshift.native_action_context_study import (
    catalog,
    collect,
    evaluate,
    load_config,
    run_study,
    train_pair,
)
from spireshift.native_conditional_control import TASK, teaching_gradient
from spireshift.native_learning_control import collect_round, public_input
from spireshift.training_objective import load_training_score_spec

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/native-controls/action-context-v1.json"


def score() -> Any:
    return load_training_score_spec(
        ROOT / "configs/training-objective/sts2-v0.111.0-ironclad-a8-native-bootstrap-v8.json"
    )


def settings() -> dict[str, Any]:
    recipe: dict[str, Any] = json.loads(
        (ROOT / "configs/native-learning/sts2-v0.111.0-a8-input-normalized-v1.json").read_text()
    )
    return cast(dict[str, Any], recipe["learning"]["ppo"])


def model(mode: str = CROSSED, seed: int = 0) -> ActionContextModel:
    return initialize("sha256:" + "f" * 64, score().spec_id, seed, mode)


def test_initial_probabilities_and_weights_match_despite_changed_encoding() -> None:
    models = [model(mode) for mode in MODES]
    assert all(m.weights() == models[0].weights() for m in models)
    assert {m.parameter_count for m in models} == {17473}
    assert len({m.model_id for m in models}) == 3
    assert all(m.actor.dimension == 512 and m.actor.hidden_units == 32 for m in models)
    for high in (False, True):
        p = public_input(TASK, high)
        logs = [policy(p, m, score(), 0.8)[2] for m in models]
        assert all(lp == logs[0] for lp in logs)
    assert all(
        evaluate(m, score(), 0.8, held=True) == evaluate(models[0], score(), 0.8, held=True)
        for m in models
    )


@pytest.mark.parametrize("mode", MODES)
def test_encoding_preserves_direct_signals_critic_legal_menu_and_permutation(mode: str) -> None:
    m, spec = model(mode), score()
    p = public_input(TASK, False)
    base, state = encode_public_input(p, 512, m.actor.input_normalization)
    rows, same = encode(p, m, spec)
    assert same == state and len(rows) == len(p["candidates"])
    if mode == ORIGINAL:
        assert rows == base
    for old, new in zip(base, rows, strict=True):
        assert all(old.get(i, 0) == new.get(i, 0) for i in range(len(DIRECT)))
        difference = math.sqrt(
            math.fsum((new.get(i, 0) - old.get(i, 0)) ** 2 for i in old.keys() | new.keys())
        )
        assert difference <= 4 + 1e-12
        assert all(math.isfinite(x) for x in new.values())
    p["candidates"].reverse()
    reverse, same = encode(p, m, spec)
    assert reverse == tuple(reversed(rows)) and same == state
    p["candidates"].append({"verb": "cancel", "label": "Cancel", "arguments": [], "subject": None})
    assert len(encode(p, m, spec)[0]) == 3


def test_crossing_context_with_candidate_provides_a_conditional_linear_signal() -> None:
    contrasts = {}
    for mode in MODES:
        m = model(mode)
        low, _ = encode(public_input(TASK, False), m, score())
        high, _ = encode(public_input(TASK, True), m, score())
        contrasts[mode] = math.sqrt(
            math.fsum(
                (high[0].get(i, 0) - high[1].get(i, 0) - low[0].get(i, 0) + low[1].get(i, 0)) ** 2
                for i in range(512)
            )
        )
    assert contrasts[ORIGINAL] < 1e-12 and contrasts[SHARED] < 1e-12
    assert contrasts[CROSSED] > 0.1
    masked = catalog(model(), score(), hide_hp=True)
    for reverse in (False, True):
        assert masked[True, reverse, 0] == masked[False, reverse, 0]


@pytest.mark.parametrize("mode", MODES)
def test_original_entity_ownership_mechanics_and_information_boundary_remain(mode: str) -> None:
    m, p = model(mode), public_input(TASK, False)
    p["context"]["persistent"]["player"]["statuses"] = [
        {"name": "Strength", "amount": 2},
        {"name": "Dexterity", "amount": 7},
    ]
    p["candidates"][0]["subject"] = {
        "role": "card",
        "properties": {"cost": 0, "stats": {"damage": 6}},
    }
    rows = encode(p, m, score())[0]
    changed = copy.deepcopy(p)
    changed["context"]["persistent"]["player"]["statuses"][0]["amount"] = 7
    changed["context"]["persistent"]["player"]["statuses"][1]["amount"] = 2
    assert encode(changed, m, score())[0] != rows
    changed = copy.deepcopy(p)
    changed["candidates"][0]["subject"]["properties"]["cost"] = 2
    assert encode(changed, m, score())[0] != rows
    assert p["candidates"][1]["verb"] == "skip"
    for name, value in (("seed", 123), ("snapshot_id", "opaque"), ("target_entity_id", "bad")):
        changed = copy.deepcopy(p)
        changed["context"][name] = value
        with pytest.raises(ValueError):
            encode(changed, m, score())


def test_original_collection_is_numerically_identical_and_teacher_labels_stay_separate() -> None:
    m, cfg = model(ORIGINAL), settings()
    samples, labels, collection = collect(m, catalog(m, score()), cfg, 0, 1, 16)
    old, report = collect_round(m.native, TASK, score(), cfg, 0, 1, 16)
    assert samples == old
    assert [
        {k: v for k, v in o.items() if k != "menu_reversed"} for o in collection["outcomes"]
    ] == report["outcomes"]
    assert collection["no_self_outcome_fitting"]
    assert (
        collection["supervised_labels_supplied_to_PPO"] == collection["intermediate_rewards"] == 0
    )
    for i, outcome in enumerate(collection["outcomes"]):
        optimal = 0 if outcome["high_hp"] else 1
        assert labels[6 * i] == (1 - optimal if outcome["menu_reversed"] else optimal)
        assert all(s.target == float(outcome["victory"]) for s in samples[i * 6 : (i + 1) * 6])


def test_new_encoding_derivatives_and_original_optimizer_keep_versioned_identity(
    tmp_path: Path,
) -> None:
    m, cfg = model(), settings()
    samples, labels, _ = collect(m, catalog(m, score()), cfg, 0, 1, 8)
    _, gradient, _ = teaching_gradient(cast(Any, m), samples, labels, cfg)
    weights = list(m.weights())
    for i in (42, 512 * 32 + 32, m.actor.parameter_count - 512 + 71, len(weights) - 1):
        plus, minus = list(weights), list(weights)
        plus[i] += 1e-5
        minus[i] -= 1e-5
        numeric = (
            teaching_gradient(cast(Any, m.with_weights(plus)), samples, labels, cfg)[0]
            - teaching_gradient(cast(Any, m.with_weights(minus)), samples, labels, cfg)[0]
        ) / 2e-5
        assert gradient[i] == pytest.approx(numeric, abs=2e-9)
    recipe = {
        "rounds": 2,
        "episodes_per_round": 8,
        "acceptance": {
            "minimum_exact_victory_gain": 0.1,
            "minimum_optimal_action_probability": 0.75,
        },
    }
    pair = train_pair(
        recipe, {**cfg, "target_kl": 0.0}, score(), CROSSED, 0, time.monotonic() + 20, tmp_path
    )
    methods = {m["method"]: m for m in pair["results"]}
    assert methods["ppo"]["work"] == methods["teacher"]["work"]
    assert methods["ppo"]["work"]["optimizer_steps"] == 2
    assert methods["ppo"]["work"]["choice_presentations"] == 16
    assert methods["hp_removed_teacher"]["final"]["greedy_accuracy"] == 0.5
    saved = json.loads((tmp_path / f"{CROSSED}-seed-0-ppo-synthetic-model.json").read_text())
    fitted = ActionContextModel.from_mapping(saved)
    assert fitted.mode == CROSSED and fitted.actor.genome != m.actor.genome
    assert fitted.value_weights != m.value_weights
    # The hidden layer starts with zero output weights, but is not frozen.
    assert fitted.actor.unpack()[0].tolist() != m.actor.unpack()[0].tolist()
    assert Adam.zero(fitted.parameter_count).steps == 0


def test_policy_serialization_cannot_silently_change_encoder_or_score() -> None:
    m = model()
    assert ActionContextModel.from_mapping(m.as_dict()) == m
    for name in ("feature_spec_id", "encoding"):
        changed = m.as_dict()
        if name == "encoding":
            changed[name]["id"] = SHARED
        else:
            changed[name] = "sha256:" + "0" * 64
        with pytest.raises(ValueError):
            ActionContextModel.from_mapping(changed)
    with pytest.raises((ValueError, KeyError)):
        NativeActorCritic.from_mapping(m.as_dict())
    with pytest.raises(ValueError, match="specification differs"):
        encode(
            public_input(TASK, False),
            initialize("sha256:" + "f" * 64, "sha256:" + "0" * 64, 0, CROSSED),
            score(),
        )


def test_frozen_recipe_loads_with_unchanged_native_learning_rules() -> None:
    cfg, ppo, spec = load_config(ROOT, CONFIG)
    assert ppo == settings() and spec.spec_id == score().spec_id
    assert cfg["resource_limits"]["wall_seconds"] < 300


@pytest.mark.parametrize(
    "field",
    [
        "rounds",
        "held_out_hp",
        "initializer",
        "resource_limits",
        "implementation_sha256",
        "acceptance",
        "objective",
        "reference_control",
    ],
)
def test_recipe_treatment_sources_and_budget_cannot_drift(tmp_path: Path, field: str) -> None:
    cfg = json.loads(CONFIG.read_text())
    cfg[field] = {} if isinstance(cfg[field], dict) else None
    path = tmp_path / "recipe.json"
    path.write_text(json.dumps(cfg))
    with pytest.raises((ValueError, KeyError, TypeError)):
        load_config(ROOT, path)


def test_cached_seals_and_unfinished_directory_do_not_restart_fitting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = {"workspace": "artifacts/synthetic-learning/cached"}
    output = tmp_path / cfg["workspace"]
    output.mkdir(parents=True)
    (output / "config-at-launch.json").write_text(json.dumps(cfg))
    evidence = output / "round.json"
    evidence.write_text("preserve")
    from spireshift.engine_qualification import _sha_file

    body = {
        "config_id": manifest_identifier(cfg),
        "files": [{"path": evidence.name, "sha256": _sha_file(evidence)}],
    }
    report = {**body, "report_id": manifest_identifier(body)}
    (output / "report.json").write_text(json.dumps(report))
    monkeypatch.setattr(
        "spireshift.native_action_context_study.load_config", lambda *_: (cfg, settings(), score())
    )
    monkeypatch.setattr(
        "spireshift.native_action_context_study.train_pair",
        lambda *_: pytest.fail("Unexpected fitting"),
    )
    assert run_study(tmp_path, Path("unused")) == report
    evidence.write_text("changed")
    with pytest.raises(ValueError, match="evidence changed"):
        run_study(tmp_path, Path("unused"))
    (output / "report.json").unlink()
    with pytest.raises(FileExistsError, match="Preserve"):
        run_study(tmp_path, Path("unused"))
    assert evidence.read_text() == "changed"
