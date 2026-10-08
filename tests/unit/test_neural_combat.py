from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from test_combat_policy import RULESET, _example, _scope_case

from spireshift.agents.learned import ProductionCheckpointPolicy
from spireshift.cli import main
from spireshift.combat_features import bind_public_combat
from spireshift.combat_policy import _records
from spireshift.core.manifest import manifest_identifier
from spireshift.neural_combat import (
    NeuralCombatConfig,
    _network_features,
    initial_neural_head,
    load_neural_combat_config,
    neural_checkpoint_parent,
    neural_gradient,
    train_neural_combat_inputs,
    validate_neural_combat_report,
)
from spireshift.neural_combat_features import (
    CARD_FLAGS,
    CARD_SOURCE,
    load_printed_card_catalog,
    neural_combat_vectors,
)
from spireshift.production_models import (
    load_production_model_checkpoint,
    load_production_training_report,
    production_model_from_checkpoint,
)

CONFIG = Path("configs/neural-combat/sts2-v0.107.1-base-v2-neural-v1.json")


def _identified(d: dict[str, Any], field: str) -> dict[str, Any]:
    return {**d, field: manifest_identifier({k: v for k, v in d.items() if k != field})}


def _catalog() -> dict[str, dict[str, Any]]:
    return {
        str(identity): {
            "Cost": 1,
            "BaseDamage": damage,
            "BaseBlock": block,
            "UpgradeDamage": 2,
            "UpgradeBlock": 2,
            "UpgradeCost": 0,
            "Type": "Attack" if damage else "Skill",
            "Target": "AnyEnemy" if damage else "Self",
            **{k: False for k in CARD_FLAGS},
        }
        for identity, damage, block in ((17, 6, 0), (45, 0, 5))
    }


def _setup() -> tuple[NeuralCombatConfig, Any, dict[str, dict[str, Any]]]:
    data, inputs, _ = _scope_case()
    document = copy.deepcopy(load_neural_combat_config(CONFIG).document)
    document["data_config"] = data.document
    document["network"].update(
        feature_dimension=64, hidden_units=8, card_catalog_id=manifest_identifier(_catalog())
    )
    document["optimization"]["epochs"] = data.document["optimization"]["epochs"]
    document["resource_limits"] = data.document["resource_limits"]
    config = NeuralCombatConfig.from_mapping(_identified(document, "config_id"))
    inputs = replace(
        inputs,
        seed_verification={
            **inputs.seed_verification,
            "fresh_seeds": config.document["fresh_confirmation"]["seeds"],
        },
    )
    return config, inputs, _catalog()


def test_public_catalog_extracts_printed_stats_and_rejects_drift(tmp_path: Path) -> None:
    source = tmp_path / CARD_SOURCE
    source.parent.mkdir(parents=True)
    source.write_text(
        'new CardDef(Id: 17, Name: "Toy", Cost: 1, BaseDamage: 6, BaseBlock: 0, '
        "UpgradeDamage: 2, UpgradeBlock: 0, UpgradeCost: -1, Type: CardType.Attack, "
        "Target: CardTarget.AnyEnemy, Exhaust: true),\n"
    )
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    catalog = load_printed_card_catalog(tmp_path, digest)
    assert catalog["17"]["Exhaust"] is True
    assert catalog["17"]["UpgradeCost"] == -1
    assert "Name" not in catalog["17"]
    source.write_text(source.read_text().replace("BaseDamage: 6", "BaseDamage: 7"))
    with pytest.raises(ValueError, match="hash differs"):
        load_printed_card_catalog(tmp_path, digest)


def test_duplicate_or_unsupported_catalog_does_not_guess(tmp_path: Path) -> None:
    source = tmp_path / CARD_SOURCE
    source.parent.mkdir(parents=True)
    line = (
        "new CardDef(Id: 17, Cost: 1, BaseDamage: 6, BaseBlock: 0, UpgradeDamage: 2, "
        "UpgradeBlock: 0, UpgradeCost: 0, Type: CardType.Attack, Target: CardTarget.AnyEnemy)\n"
    )
    source.write_text(line * 2)
    with pytest.raises(ValueError, match="Duplicate"):
        load_printed_card_catalog(tmp_path, hashlib.sha256(source.read_bytes()).hexdigest())
    source.write_text(line.replace("BaseDamage: 6", "BaseDamage: Unknown()"))
    with pytest.raises(ValueError, match="Unsupported"):
        load_printed_card_catalog(tmp_path, hashlib.sha256(source.read_bytes()).hexdigest())


def test_features_bind_objects_not_operational_handles_and_reject_missing_metadata() -> None:
    config, inputs, catalog = _setup()
    representation = inputs.anchors[0].representation
    bound = bind_public_combat(representation, config.data.residual_layout)
    assert bound is not None
    vectors = neural_combat_vectors(bound, catalog, 64)
    renamed = replace(bound, source_action_ids=tuple("private-handle" for _ in bound.bindings))
    assert vectors == neural_combat_vectors(renamed, catalog, 64)
    assert len(vectors) == len(representation.candidates)
    assert vectors[0] != vectors[1] != vectors[2]
    with pytest.raises(ValueError, match="absent from the frozen catalog"):
        neural_combat_vectors(bound, {"17": catalog["17"]}, 64)


def test_both_network_layers_have_correct_gradients() -> None:
    config, inputs, catalog = _setup()
    parent = production_model_from_checkpoint(inputs.parent_checkpoint)
    records = tuple(
        r
        for r in _records(inputs.anchors, config.data, parent.policy_weights)
        if r.example.run_seed in config.data.foundation.document["complete_run_subfolds"]["fit"]
    )
    head = initial_neural_head(config, catalog)
    batches = _network_features(records, head)
    x = np.zeros((sum(map(len, batches)), head.dimension), dtype=np.float64)
    for row, features in zip(x, (f for b in batches for f in b), strict=True):
        for i, value in features.items():
            row[i] = value
    parameters = (
        np.asarray(head.input_weights),
        np.asarray(head.hidden_bias),
        np.linspace(-0.1, 0.1, len(head.output_weights)),
    )
    active = replace(head, output_weights=tuple(float(v) for v in parameters[2]))
    expected = np.tanh(x @ parameters[0].T + parameters[1]) @ parameters[2]
    actual = [score for batch in batches for score in active.feature_scores(batch)]
    assert actual == pytest.approx(expected.tolist(), abs=1e-12)
    loss, gradients = neural_gradient(x, parameters, records, config.document["optimization"])
    assert np.isfinite(loss) and np.linalg.norm(gradients[0]) > 0
    for layer, coordinate in ((0, (0, 3)), (0, (2, 10)), (1, (2,)), (2, (1,))):
        delta = 1e-6
        parameters[layer][coordinate] += delta
        above = neural_gradient(x, parameters, records, config.document["optimization"])[0]
        parameters[layer][coordinate] -= 2 * delta
        below = neural_gradient(x, parameters, records, config.document["optimization"])[0]
        parameters[layer][coordinate] += delta
        assert gradients[layer][coordinate] == pytest.approx(
            (above - below) / (2 * delta), abs=1e-7
        )


def test_saved_neural_candidate_roundtrip_preserves_other_heads(tmp_path: Path) -> None:
    config, inputs, catalog = _setup()
    result = train_neural_combat_inputs(inputs=inputs, config=config, catalog=catalog)
    checkpoint = tmp_path / "checkpoint.json"
    report = tmp_path / "report.json"
    checkpoint.write_text(json.dumps(result.checkpoint))
    report.write_text(json.dumps(result.report))
    loaded = load_production_model_checkpoint(checkpoint)
    checked = load_production_training_report(report, checkpoint=loaded)
    assert checked["candidate_eligible"] is True and checked["selected_epoch"] > 0
    original, head = neural_checkpoint_parent(loaded)
    assert original == inputs.parent_checkpoint
    assert head.dimension == 64 and len(head.hidden_bias) == 8
    assert checked["optimizer_steps"] == config.document["optimization"]["epochs"]
    assert checked["games_replayed"] == checked["simulations"] == 0
    assert checked["checkpoint_promoted"] is checked["foundation_ready"] is False
    parent = production_model_from_checkpoint(original)
    model = production_model_from_checkpoint(loaded)
    for item in inputs.validation:
        before, after = parent.predict(item.representation), model.predict(item.representation)
        assert before.tactical_death_risk == after.tactical_death_risk
        assert before.maximum_floor_reach == after.maximum_floor_reach
        assert before.terminal_value == after.terminal_value is None
        assert after.source_action_ids == before.source_action_ids
        if item.decision_type != "combat":
            assert before == after
    policy = ProductionCheckpointPolicy(checkpoint=loaded, training_report=checked, ruleset=RULESET)
    assert policy.model_id == loaded["model_id"]


def test_rejected_neural_pilot_retains_exact_parent_and_cannot_be_deployed() -> None:
    config, inputs, catalog = _setup()
    document = copy.deepcopy(config.document)
    document["optimization"]["learning_rate"] = 1e-8
    config = NeuralCombatConfig.from_mapping(_identified(document, "config_id"))
    result = train_neural_combat_inputs(inputs=inputs, config=config, catalog=catalog)
    assert result.report["selected_epoch"] == 0
    assert result.report["candidate_eligible"] is False
    before = production_model_from_checkpoint(inputs.parent_checkpoint)
    after = production_model_from_checkpoint(result.checkpoint)
    for item in inputs.validation:
        assert after.predict(item.representation) == before.predict(item.representation)
    with pytest.raises(ValueError, match="did not pass"):
        ProductionCheckpointPolicy(
            checkpoint=result.checkpoint, training_report=result.report, ruleset=RULESET
        )


@pytest.mark.parametrize(
    "change", ["parent", "catalog", "nonfinite", "shape", "selection", "promotion"]
)
def test_reidentified_mutations_cannot_bypass_binding_or_gates(change: str) -> None:
    config, inputs, catalog = _setup()
    result = train_neural_combat_inputs(inputs=inputs, config=config, catalog=catalog)
    checkpoint, report = copy.deepcopy(result.checkpoint), copy.deepcopy(result.report)
    binding = checkpoint["neural_combat_policy"]
    if change == "parent":
        checkpoint["heads"]["policy"]["weights"].append([383, 0.1])
    elif change == "catalog":
        binding["head"]["printed_card_catalog"]["17"]["BaseDamage"] += 1
    elif change == "nonfinite":
        binding["head"]["output_weights"][0] = float("nan")
    elif change == "shape":
        binding["head"]["input_weights"][0].pop()
    elif change == "selection":
        report["selected_epoch"] = config.document["optimization"]["epochs"] + 1
    else:
        report["checkpoint_promoted"] = True
    if change != "nonfinite":
        binding["head"] = _identified(binding["head"], "head_id")
        checkpoint = _identified(checkpoint, "model_id")
        report = _identified(report, "report_id")
    with pytest.raises(ValueError):
        validate_neural_combat_report(report, checkpoint=checkpoint)


def test_overlap_and_unverified_source_stop_before_neural_gradient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, inputs, catalog = _setup()

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("Optimizer must not run on overlapping or unaudited sources")

    monkeypatch.setattr("spireshift.neural_combat.neural_gradient", forbidden)
    with pytest.raises(ValueError, match="ownership differs"):
        train_neural_combat_inputs(
            inputs=replace(inputs, validation=(_example(1),)), config=config, catalog=catalog
        )
    with pytest.raises(ValueError, match="sources differ"):
        train_neural_combat_inputs(
            inputs=replace(inputs, audit={**inputs.audit, "report_id": "sha256:" + "0" * 64}),
            config=config,
            catalog=catalog,
        )


def test_fresh_reservation_cannot_reuse_the_inspected_games() -> None:
    config = load_neural_combat_config(CONFIG)
    changed = copy.deepcopy(config.document)
    changed["fresh_confirmation"]["seeds"][0] = changed["diagnosis"]["inspected_seeds"][0]
    changed["fresh_confirmation"]["seeds"].sort()
    with pytest.raises(ValueError, match="inspected comparison"):
        NeuralCombatConfig.from_mapping(_identified(changed, "config_id"))


def test_cached_cli_does_not_initialize_engine_load_sources_or_fit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config, inputs, catalog = _setup()
    result = train_neural_combat_inputs(inputs=inputs, config=config, catalog=catalog)
    recipe = tmp_path / "recipe.json"
    recipe.write_text(json.dumps(config.document))
    model = tmp_path / "model"
    model.mkdir()
    (model / "checkpoint.json").write_text(json.dumps(result.checkpoint))
    (model / "training-report.json").write_text(json.dumps(result.report))

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("Cached display must not fit, load teacher sources, or initialize a game")

    monkeypatch.setattr("spireshift.neural_combat.load_neural_combat_inputs", forbidden)
    monkeypatch.setattr("spireshift.neural_combat.neural_gradient", forbidden)
    monkeypatch.setattr("spireshift.cli.load_evangambit_backend", forbidden)
    assert main(["model", "show-neural-combat-training", str(model), "--config", str(recipe)]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["optimizer_steps_this_command"] == d["games_replayed"] == 0
    assert d["source_inputs_reaudited"] is False


def test_owner_cli_publishes_only_one_training_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, inputs, catalog = _setup()
    recipe = tmp_path / "recipe.json"
    recipe.write_text(json.dumps(config.document))
    monkeypatch.setattr("spireshift.cli.load_split_manifest", lambda p: object())
    monkeypatch.setattr(
        "spireshift.cli.load_patch_manifest",
        lambda p: SimpleNamespace(ruleset_identity=lambda: RULESET),
    )
    monkeypatch.setattr(
        "spireshift.neural_combat.load_neural_combat_inputs", lambda **kw: (inputs, catalog)
    )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("Saved-data pilot must never initialize a game")

    monkeypatch.setattr("spireshift.cli.load_evangambit_backend", forbidden)
    args = [
        "model",
        "train-neural-combat-policy",
        str(recipe),
        "--split-manifest",
        "split.json",
        "--manifest",
        "manifest.json",
        "--upstream-root",
        "upstream",
        "--output-dir",
        str(tmp_path / "model"),
    ]
    assert main(args) == 0
    assert main(args) == 1
    report = json.loads((tmp_path / "model/training-report.json").read_text())
    assert (
        report["games_replayed"] == 0
        and report["optimizer_steps"] == config.document["optimization"]["epochs"]
    )


def test_owner_script_caps_rotates_and_does_not_chain_games(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "bin").mkdir()
    script = tmp_path / "scripts/train.sh"
    script.write_text(Path("scripts/train-neural-combat-policy-v1.sh").read_text())
    log = tmp_path / "calls"
    uv = tmp_path / "bin/uv"
    uv.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$SPIRESHIFT_TEST_CALLS"\n')
    uv.chmod(0o755)
    env = {
        **os.environ,
        "PATH": str(uv.parent) + os.pathsep + os.environ["PATH"],
        "SPIRESHIFT_TEST_CALLS": str(log),
    }
    resources = tmp_path / "artifacts/resources"
    resources.mkdir(parents=True)
    (resources / "neural-combat-base-v11-train-v1-attempt-1.json").write_text("{}")
    subprocess.run(["bash", str(script)], env=env, check=True, capture_output=True)
    calls = log.read_text()
    assert calls.count("resources run") == 1 and "attempt-2.json" in calls
    assert "--max-wall-seconds 1800" in calls and "--workers 1" in calls
    assert "evaluate" not in calls and "discover" not in calls
    root = tmp_path / "artifacts/models/sts2-v0.107.1-base-v11"
    root.mkdir(parents=True)
    (root / "checkpoint.json").write_text("{}")
    log.write_text("")
    failed = subprocess.run(["bash", str(script)], env=env, capture_output=True)
    assert failed.returncode == 1 and log.read_text() == ""
    (root / "training-report.json").write_text("{}")
    subprocess.run(["bash", str(script)], env=env, check=True, capture_output=True)
    assert (
        "show-neural-combat-training" in log.read_text() and "resources run" not in log.read_text()
    )


def test_neural_json_schemas_cover_the_frozen_recipe_and_toy_artifacts() -> None:
    registry: Registry[Any] = Registry().with_resources(
        (
            f"https://spireshift.dev/schemas/{p.name}",
            Resource.from_contents(json.loads(p.read_text())),
        )
        for p in Path("schemas").glob("*.json")
    )
    config, inputs, catalog = _setup()
    result = train_neural_combat_inputs(inputs=inputs, config=config, catalog=catalog)
    for name, document in (
        ("neural-combat-policy-training-config-v1", load_neural_combat_config(CONFIG).document),
        ("neural-combat-policy-training-config-v1", config.document),
        ("public-neural-combat-policy-v1", result.checkpoint["neural_combat_policy"]["head"]),
        ("production-model-checkpoint-v10", result.checkpoint),
        ("production-model-training-report-v10", result.report),
    ):
        Draft202012Validator(
            json.loads(Path(f"schemas/{name}.json").read_text()), registry=registry
        ).validate(document)
