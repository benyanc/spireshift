from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.agents.learned import ProductionCheckpointPolicy
from spireshift.bootstrap_teacher import (
    CurriculumSignalSpec,
    CurriculumStateCase,
    CurriculumStateSet,
)
from spireshift.cli import main
from spireshift.combat_features import (
    SELECTION_LAYOUT_SCHEMA,
    TRANSFORM_LAYOUT_SCHEMA,
    CombatLayout,
)
from spireshift.combat_foundation import analyze_combat_foundation
from spireshift.combat_policy import (
    CombatPolicyConfig,
    CombatPolicyHead,
    CombatPolicyInputs,
    CombatRecord,
    _frozen_metrics,
    _gradient,
    _pair_weights,
    _records,
    combat_checkpoint_parent,
    load_combat_policy_config,
    load_combat_policy_inputs,
    preflight_combat_validation_bindings,
    train_combat_policy_inputs,
    validate_combat_policy_report,
)
from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import load_objective
from spireshift.core.types import DecisionType, LegalAction, Observation
from spireshift.models import _candidate_features, _dot, _weights_as_list
from spireshift.production_models import (
    ProductionTrainingConfig,
    _Outcome,
    _ProductionExample,
    load_production_model_checkpoint,
    load_production_training_report,
    production_model_from_checkpoint,
)
from spireshift.representations import build_model_input, vectorize_model_input
from spireshift.resource_tracking import EXPERIMENT_METRICS_ENV
from spireshift.splits import load_split_manifest

CONFIG_PATH = Path("configs/combat-policy/sts2-v0.107.1-base-v2-combat-residual-v1.json")
EXTENDED_CONFIG_PATH = Path("configs/combat-policy/sts2-v0.107.1-base-v2-combat-residual-v2.json")
RULESET = MockSpireEnvironment.ruleset
LAYOUT = CombatLayout(RULESET.patch_id, RULESET.manifest_id, SELECTION_LAYOUT_SCHEMA)


def _identified(d: dict[str, Any], field: str) -> dict[str, Any]:
    return {**d, field: manifest_identifier({k: v for k, v in d.items() if k != field})}


def _example(
    seed: int, *, combat: bool = True, index: int = 0, selection_kind: int = 0
) -> _ProductionExample:
    v = [0] * 682
    v[:8] = [20, 40, 2, 3, 3, 8, 2, 0]
    v[8:16] = [17, 0, 0, 0, 45, 1, 2, 3]
    v[48:50] = [47, 1]
    v[80:87] = [10, 20, 1, 0, 6, 0, 3]
    if selection_kind:
        v[183:193] = [selection_kind, 2, *v[8:16]]
    count = 2 if selection_kind else 4
    state = {
        "observation_vector": v,
        "player_hp": 20,
        "player_max_hp": 40,
        "enemy_def_ids": [7],
        "potions": [47, 0, 0, 0, 0, 0],
        "act": "underdocks",
        "floor": 2,
        "terminal": False,
        "victory": False,
    }
    if not combat:
        state = {"floor": 2, "act": "underdocks", "terminal": False, "victory": False}
    kind = DecisionType.COMBAT if combat else DecisionType.PATH
    actions = tuple(
        LegalAction(
            f"action-{i}",
            "evangambit_combat" if combat else "evangambit_path",
            {
                "phase": kind.value,
                "action_index": i,
                **({"target_index": 0} if i in (0, 3) and combat else {}),
            },
        )
        for i in range(count)
    )
    obs = Observation(
        "observation-v1", RULESET.patch_id, kind, state, manifest_identifier(state)[7:]
    )
    rep = build_model_input(RULESET, obs, actions)
    vector = vectorize_model_input(rep, dimension=128)
    features = tuple(_candidate_features(vector.state, c, 128, 256) for c in vector.candidates)
    return _ProductionExample(
        f"seed-{seed}-{kind.value}-{index}",
        seed,
        kind.value,
        rep,
        features,
        tuple(
            row[:count]
            for row in (
                (0.5, 0.1, 0.5, 0.1),
                (0.9, 0.5, 0.9, 0.9),
                (0.5, 0.1, 0.5, 0.1),
                (0.9, 0.1, 0.9, 0.5),
            )[:count]
        ),
        (0.25, 0.75) if selection_kind else (0.1, 0.5, 0.1, 0.3),
        1.0,
        1.0,
        1,
        (0.1, 0.5, 0.1, 0.3)[:count],
        tuple(
            tuple(_Outcome(floor, True, False, True, 20) for _ in range(16))
            for floor in (2, 6, 2, 5)[:count]
        ),
    )


def _extended_inputs() -> tuple[CombatPolicyConfig, CombatPolicyInputs]:
    config, inputs = _inputs()
    recipe = copy.deepcopy(config.document)
    recipe["schema_version"] = "combat-policy-training-config-v2"
    recipe["residual_layout"] = CombatLayout(
        RULESET.patch_id, RULESET.manifest_id, TRANSFORM_LAYOUT_SCHEMA
    ).as_dict()
    return CombatPolicyConfig.from_mapping(_identified(recipe, "config_id")), replace(
        inputs, validation=(_example(5, selection_kind=20), *inputs.validation[1:])
    )


def _public_preflight_dataset(tmp_path: Path, *, selection_kind: int = 20) -> CombatPolicyConfig:
    config, inputs = _extended_inputs()
    examples = (_example(5), _example(6, selection_kind=selection_kind), inputs.validation[-1])
    cases = tuple(
        CurriculumStateCase(
            e.state_id,
            e.run_seed,
            DecisionType(e.decision_type),
            0,
            e.representation.source_state_hash,
            len(e.representation.candidates),
            2,
            "underdocks",
        )
        for e in examples
    )
    state_set = CurriculumStateSet(
        "pending",
        config.foundation.document["split_manifest_id"],
        RULESET.manifest_id,
        "terminal-victory-v1",
        "public-progress-bootstrap-v1",
        "validation",
        "toy-public-preflight",
        {"captured_coordinates": 3, "requested_coordinates": 3, "unreachable_coordinates": []},
        CurriculumSignalSpec(1, 1, 1, 1.0, 0.0, 1),
        cases,
    )
    references = []
    for expected, example in zip(cases, examples, strict=True):
        record = _identified(
            {
                "state_id": expected.state_id,
                "run_seed": expected.run_seed,
                "decision_type": example.decision_type,
                "decision_index": 0,
                "source_state_hash": expected.expected_state_hash,
                "model_input": example.representation.as_dict(),
                "target": "deliberately unparseable: the preflight must not inspect lessons",
            },
            "record_id",
        )
        case = _identified(
            {
                "state_id": expected.state_id,
                "status": "completed",
                "record": record,
                "batch": {"path": "missing-teacher-batch.json"},
            },
            "case_id",
        )
        path = tmp_path / f"{expected.state_id}.json"
        path.write_text(json.dumps(case))
        references.append(
            {
                "state_id": expected.state_id,
                "path": path.name,
                "case_id": case["case_id"],
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
        if example.decision_type != "combat":
            path.unlink()  # Noncombat bodies are outside this compatibility check.
    dataset = _identified(
        {
            "state_set": _identified(state_set.as_dict(), "state_set_id"),
            "objective": config.foundation.document["objective"],
            "cases": references,
        },
        "dataset_id",
    )
    (tmp_path / "dataset.json").write_text(json.dumps(dataset))
    recipe = copy.deepcopy(config.document)
    recipe.update(validation_path="dataset.json", validation_dataset_id=dataset["dataset_id"])
    return CombatPolicyConfig.from_mapping(_identified(recipe, "config_id"))


def test_preflight_binds_all_public_combat_inputs_without_loading_teacher_batches(
    tmp_path: Path,
) -> None:
    config = _public_preflight_dataset(tmp_path)
    result = preflight_combat_validation_bindings(config=config, project_root=tmp_path)
    assert result["source_records"] == 3
    assert result["combat_states"] == result["bound_combat_states"] == 2
    assert result["selection_kind_counts"] == {"0": 1, "20": 1}
    assert all(
        result[k] == 0
        for k in (
            "binding_failures",
            "labels_analyzed",
            "teacher_batches_opened",
            "optimizer_steps",
            "games_replayed",
        )
    )


@pytest.mark.parametrize("broken", ["unsupported", "changed_case", "missing_case"])
def test_preflight_preserves_failures_and_identifies_the_saved_state(
    tmp_path: Path, broken: str
) -> None:
    config = _public_preflight_dataset(
        tmp_path, selection_kind=16 if broken == "unsupported" else 20
    )
    path = tmp_path / "seed-6-combat-0.json"
    if broken == "changed_case":
        path.write_text(path.read_text() + " ")
    elif broken == "missing_case":
        path.unlink()
    with pytest.raises(ValueError, match=r"failed \(1/2\): seed-6-combat-0"):
        preflight_combat_validation_bindings(config=config, project_root=tmp_path)


def test_unsupported_validation_stops_before_large_source_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _public_preflight_dataset(tmp_path, selection_kind=16)
    _, inputs = _extended_inputs()
    monkeypatch.setattr(
        "spireshift.combat_policy.load_combat_foundation_report", lambda *args: inputs.audit
    )
    study = SimpleNamespace(
        collection=SimpleNamespace(runner=SimpleNamespace(run_offset=312), seeds=range(192)),
        document={"prior_train_prefix_stop": 312, "prior_seed_sources": []},
    )
    monkeypatch.setattr(
        "spireshift.combat_policy.load_starting_repeatability_config", lambda *args: study
    )

    def forbidden(**kwargs: Any) -> None:
        pytest.fail("A public binding failure must stop before the large source audit")

    monkeypatch.setattr("spireshift.combat_policy.load_combat_foundation_inputs", forbidden)
    with pytest.raises(ValueError, match="preflight failed"):
        load_combat_policy_inputs(
            config=config,
            project_root=tmp_path,
            upstream_root=tmp_path,
            split_manifest=load_split_manifest(
                Path("manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json")
            ),
            ruleset=RULESET,
            objective=load_objective(Path("configs/default.toml")),
        )


def test_extended_recipe_preserves_all_frozen_training_and_audit_settings() -> None:
    old = load_combat_policy_config(CONFIG_PATH)
    new = load_combat_policy_config(EXTENDED_CONFIG_PATH)
    assert {k: v for k, v in old.document.items() if k not in {"schema_version", "config_id"}} == {
        k: v
        for k, v in new.document.items()
        if k not in {"schema_version", "config_id", "residual_layout"}
    }
    assert new.residual_layout.schema_version == TRANSFORM_LAYOUT_SCHEMA
    assert old.residual_layout.schema_version == SELECTION_LAYOUT_SCHEMA
    bad = copy.deepcopy(new.document)
    bad["residual_layout"]["ruleset_manifest_id"] = "sha256:" + "1" * 64
    with pytest.raises(ValueError, match="audited provenance"):
        CombatPolicyConfig.from_mapping(_identified(bad, "config_id"))


def _inputs(
    *, epochs: int = 4, reject: bool = False
) -> tuple[CombatPolicyConfig, CombatPolicyInputs]:
    recipe = copy.deepcopy(load_combat_policy_config(CONFIG_PATH).document)
    foundation = recipe["foundation_config"]
    foundation["layout"] = LAYOUT.as_dict()
    foundation["complete_run_subfolds"] = {"fit": [1, 2], "selection": [3, 4]}
    foundation["analysis"].update(
        minimum_fit_signal_runs=1,
        minimum_selection_signal_runs=1,
        minimum_fit_card_ids=1,
        minimum_fit_floor_bins=1,
    )
    example = _example(1)
    # A small accepted toy parent prefers the best candidate, but is underconfident.
    desired = (-1.0, 2.0, -1.0, 1.0)
    weights: dict[int, float] = {}
    for f, score in zip(example.candidate_features, desired, strict=True):
        for i, v in f.items():
            weights[i] = weights.get(i, 0) + 0.0001 * score * v
    training = ProductionTrainingConfig(epochs=2, vector_dimension=128, interaction_dimension=256)
    parent = _identified(
        {
            "schema_version": "production-model-checkpoint-v2",
            "model_type": "sparse-pairwise-curriculum-multihead-v2",
            "representation_encoder_id": "mechanics-compositional-v1",
            "vectorizer_id": "signed-sha256-feature-hash-v1",
            "ruleset_manifest_id": RULESET.manifest_id,
            "objective_id": "terminal-victory-v1",
            "split_manifest_id": foundation["split_manifest_id"],
            "train_dataset_id": foundation["dataset_id"],
            "training_config": training.as_dict(),
            "heads": {
                "policy": {
                    "target": "paired-preference-confidence-v1",
                    "weights": _weights_as_list(weights),
                },
                "terminal_value": {
                    "status": "blocked",
                    "reason": "all_zero_terminal_victory_evidence",
                    "weights": [],
                },
                "tactical_death_risk": {
                    "target": "terminal_defeat_within_32_decisions",
                    "bias": 0.125,
                    "weights": [{"index": 1, "value": 0.3}],
                },
                "maximum_floor_distribution": {
                    "target": "candidate-maximum-floor-survival-v1",
                    "thresholds": [{"floor": 5, "bias": 0.2, "weights": []}],
                },
            },
        },
        "model_id",
    )
    parent_report = _identified(
        {
            "validation_dataset_id": recipe["validation_dataset_id"],
            "held_out_metrics": {
                "policy": {"soft_target_baseline": {"weighted_pairwise_cross_entropy": 1.0}},
                "tactical_death_risk": {"frozen_test_metric": 0.2},
                "maximum_floor_distribution": {"frozen_test_metric": 0.1},
                "terminal_value": None,
            },
            "terminal_value_status": {"status": "blocked"},
        },
        "report_id",
    )
    foundation.update(model_id=parent["model_id"], training_report_id=parent_report["report_id"])
    recipe["frozen_parent_metrics"] = _frozen_metrics(parent_report)
    foundation = _identified(foundation, "config_id")
    recipe["foundation_config"] = foundation
    recipe["optimization"]["epochs"] = epochs
    if reject:
        recipe["limits"]["minimum_preference_loss_improvement"] = 0.99
    anchors = tuple(_example(s) for s in range(1, 5))
    provisional = CombatPolicyConfig.from_mapping(_identified(recipe, "config_id"))
    audit = _identified(
        analyze_combat_foundation(
            examples=anchors,
            config=provisional.foundation,
            parent_weights=production_model_from_checkpoint(parent).policy_weights,
        ),
        "report_id",
    )
    recipe["foundation_report_id"] = audit["report_id"]
    config = CombatPolicyConfig.from_mapping(_identified(recipe, "config_id"))
    return config, CombatPolicyInputs(
        parent,
        parent_report,
        audit,
        training,
        anchors,
        (_example(5), _example(6), _example(5, combat=False)),
        {
            "scope": "content_addressed_seed_metadata_no_case_replay",
            "prior_inventories": [],
            "excluded_seed_count": 504,
            "fresh_seeds": recipe["fresh_confirmation"]["seeds"],
            "disjoint": True,
        },
    )


def test_soft_paired_gradient_matches_finite_difference() -> None:
    example = _example(1)
    pair = {"left": 0, "right": 1, "left_preference_probability": 0.75}
    r = CombatRecord(example, ({0: 1.0}, {1: 1.0}), (0.2, -0.1), (pair,))
    recipe = {"anchor_strength": 0.3, "proximal_strength": 0.1}
    weights = {0: 0.15, 1: -0.04}
    from spireshift.models import _binary_cross_entropy, _sigmoid, _softmax

    def loss(w: dict[int, float]) -> float:
        scores = tuple(a + _dot(w, f) for a, f in zip(r.parent_scores, r.features, strict=True))
        probs = _softmax(scores)
        return (
            _binary_cross_entropy(_sigmoid(scores[0] - scores[1]), 0.75)
            - 0.3
            * sum(p * math.log(q) for p, q in zip(_softmax(r.parent_scores), probs, strict=True))
            + 0.05 * sum(v * v for v in w.values())
        )

    g = _gradient((r,), weights, recipe)
    for index in weights:
        plus, minus = dict(weights), dict(weights)
        plus[index] += 1e-6
        minus[index] -= 1e-6
        assert g[index] == pytest.approx((loss(plus) - loss(minus)) / 2e-6, abs=1e-8)


def test_correlated_states_and_pairs_do_not_inflate_seed_weight() -> None:
    config, inputs = _inputs()
    records = _records(inputs.anchors, config, {})
    repeated = records + (
        replace(records[0], example=replace(records[0].example, state_id="additional")),
    )
    weights = _pair_weights(repeated)
    for seed in range(1, 5):
        assert sum(
            sum(weights[r.example.state_id]) for r in repeated if r.example.run_seed == seed
        ) == pytest.approx(0.25)


def test_real_training_math_keeps_parent_heads_and_noncombat_exact() -> None:
    config, inputs = _inputs()
    result = train_combat_policy_inputs(inputs=inputs, config=config)
    assert result.report["selected_epoch"] > 0
    assert result.report["candidate_eligible"] is True
    assert result.report["serialization_checks"]["noncombat_predictions_unchanged"] == 1
    assert result.checkpoint["heads"] == inputs.parent_checkpoint["heads"]
    parent, head = combat_checkpoint_parent(result.checkpoint)
    assert parent == inputs.parent_checkpoint and head.weights
    assert (
        result.report["held_out_metrics"]["tactical_death_risk"]
        == inputs.parent_report["held_out_metrics"]["tactical_death_risk"]
    )
    assert result.report["checkpoint_promoted"] is False
    assert result.report["adaptive_controller_allowed"] is False
    ProductionCheckpointPolicy(
        checkpoint=result.checkpoint, training_report=result.report, ruleset=RULESET
    )


def test_failed_advancement_saves_exact_parent_fallback_and_blocks_play() -> None:
    config, inputs = _inputs(reject=True)
    result = train_combat_policy_inputs(inputs=inputs, config=config)
    assert result.report["selected_epoch"] == 0 and result.report["candidate_eligible"] is False
    assert result.checkpoint["combat_policy_residual"]["head"]["weights"] == []
    a = production_model_from_checkpoint(inputs.parent_checkpoint)
    b = production_model_from_checkpoint(result.checkpoint)
    assert all(
        a.predict(x.representation) == b.predict(x.representation) for x in inputs.validation
    )
    with pytest.raises(ValueError, match="advancement"):
        ProductionCheckpointPolicy(
            checkpoint=result.checkpoint, training_report=result.report, ruleset=RULESET
        )


def test_validation_never_updates_weights_or_selects_epochs() -> None:
    config, inputs = _inputs()
    first = train_combat_policy_inputs(inputs=inputs, config=config)
    changed = tuple(
        replace(x, mean_progress_utilities=tuple(reversed(x.mean_progress_utilities)))
        for x in inputs.validation
    )
    second = train_combat_policy_inputs(inputs=replace(inputs, validation=changed), config=config)
    assert first.checkpoint == second.checkpoint
    assert first.report["training_history"] == second.report["training_history"]
    assert first.report["selected_epoch"] == second.report["selected_epoch"]
    assert first.report["validation_checks"] != second.report["validation_checks"]
    assert second.report["candidate_eligible"] is False


def test_optimizer_sees_fitting_seeds_only(monkeypatch: pytest.MonkeyPatch) -> None:
    config, inputs = _inputs()
    calls: list[set[int]] = []
    original = _gradient

    def observed(
        records: tuple[CombatRecord, ...], weights: dict[int, float], recipe: dict[str, Any]
    ) -> dict[int, float]:
        calls.append({r.example.run_seed for r in records})
        return original(records, weights, recipe)

    monkeypatch.setattr("spireshift.combat_policy._gradient", observed)
    train_combat_policy_inputs(inputs=inputs, config=config)
    assert calls == [{1, 2}] * 4


@pytest.mark.parametrize(
    "mutation",
    [
        "weights",
        "epoch",
        "eligibility",
        "readiness",
        "checks",
        "selected_head",
        "counter",
        "frozen_metrics",
    ],
)
def test_reidentified_tampering_is_rejected(mutation: str) -> None:
    config, inputs = _inputs()
    result = train_combat_policy_inputs(inputs=inputs, config=config)
    checkpoint, report = copy.deepcopy(result.checkpoint), copy.deepcopy(result.report)
    if mutation == "weights":
        checkpoint["heads"]["policy"]["weights"].append({"index": 383, "value": 100.0})
    elif mutation == "epoch":
        report["selected_epoch"] = 0
    elif mutation == "eligibility":
        report["candidate_eligible"] = False
    elif mutation == "readiness":
        report["foundation_ready"] = True
    elif mutation == "checks":
        report["training_history"][0]["checks"]["advancement"] = not report["training_history"][0][
            "checks"
        ]["advancement"]
    elif mutation == "selected_head":
        report["selected_head_id"] = manifest_identifier({"wrong": "head"})
    elif mutation == "frozen_metrics":
        report["held_out_metrics"]["tactical_death_risk"] = {"invented_improvement": 0}
    else:
        report["games_replayed"] = 1
    checkpoint = _identified(checkpoint, "model_id")
    report = _identified(report, "report_id")
    with pytest.raises(ValueError):
        validate_combat_policy_report(report, checkpoint=checkpoint)


def test_nonempty_head_fails_unsupported_combat_empty_head_preserves_parent() -> None:
    config, inputs = _inputs()
    features = inputs.anchors[0].representation
    # A missing public layout is unsupported; it cannot silently become a parent-policy action.
    malformed = replace(features, global_features=())
    with pytest.raises(ValueError):
        CombatPolicyHead(LAYOUT, 8192, {0: 0.2}).scores(malformed)
    assert CombatPolicyHead(LAYOUT, 8192, {}).scores(malformed) == (0.0,) * 4


def test_frozen_config_keeps_original_guards_and_reserves_disjoint_fresh_runs() -> None:
    config = load_combat_policy_config(CONFIG_PATH)
    assert config.document["optimization"]["epochs"] == 40
    assert config.document["limits"] == {
        "maximum_pair_loss_increase": 0.01,
        "maximum_accuracy_drop": 0.02,
        "maximum_regret_increase": 0.0002,
        "maximum_mean_total_variation": 0.05,
        "minimum_preference_loss_improvement": 0.001,
    }
    assert (
        config.document["foundation_report_id"]
        == "sha256:57666476aa7c42ce76cb46a44e9eb422ab7bfb21abf4b752e8cb0110ab3948fd"
    )
    assert config.document["fresh_confirmation"]["run_offset"] == 504
    assert len(config.document["fresh_confirmation"]["seeds"]) == 32
    assert (
        config.foundation.document["objective"]
        == load_objective(Path("configs/default.toml")).as_dict()
    )
    assert config.foundation.document["analysis"]["pairwise_noise_floor"] == 0.25


def test_failed_data_gate_stops_before_source_loading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, inputs = _inputs()
    audit = copy.deepcopy(inputs.audit)
    audit["decision"]["pilot_data_sufficient"] = False
    audit = _identified(audit, "report_id")
    d = copy.deepcopy(config.document)
    d["foundation_report_id"] = audit["report_id"]
    config = CombatPolicyConfig.from_mapping(_identified(d, "config_id"))
    monkeypatch.setattr("spireshift.combat_policy.load_combat_foundation_report", lambda *a: audit)

    def forbidden(**kwargs: Any) -> None:
        pytest.fail("Full source loading must not follow a failed data gate")

    monkeypatch.setattr("spireshift.combat_policy.load_combat_foundation_inputs", forbidden)
    with pytest.raises(ValueError, match="passing owner data audit"):
        load_combat_policy_inputs(
            config=config,
            project_root=tmp_path,
            upstream_root=tmp_path,
            split_manifest=load_split_manifest(
                Path("manifests/splits/mock-v1-seeds-000000-000999-v1.json")
            ),
            ruleset=RULESET,
            objective=load_objective(Path("configs/default.toml")),
        )


def test_cli_atomic_outputs_and_cached_display_no_training(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config, inputs = _inputs()
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config.document))
    result = train_combat_policy_inputs(inputs=inputs, config=config)
    output = tmp_path / "model"
    output.mkdir()
    (output / "checkpoint.json").write_text(json.dumps(result.checkpoint))
    (output / "training-report.json").write_text(json.dumps(result.report))

    def forbidden(**kwargs: Any) -> None:
        pytest.fail("Cached display must not re-audit data or retrain")

    monkeypatch.setattr("spireshift.combat_policy.load_combat_policy_inputs", forbidden)
    assert main(["model", "show-combat-policy-training", str(output), "--config", str(path)]) == 0
    displayed = json.loads(capsys.readouterr().out)
    assert (
        displayed["source_inputs_reaudited"] is False
        and displayed["optimizer_steps_this_command"] == 0
    )
    metrics = tmp_path / "metrics.json"
    monkeypatch.setenv(EXPERIMENT_METRICS_ENV, str(metrics))
    assert not metrics.exists()
    assert load_production_model_checkpoint(output / "checkpoint.json") == result.checkpoint
    assert (
        load_production_training_report(
            output / "training-report.json", checkpoint=result.checkpoint
        )
        == result.report
    )


def test_cli_owner_training_publishes_and_conflicts_stop_before_source_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config, inputs = _inputs()
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config.document))
    output = tmp_path / "model"
    metrics = tmp_path / "metrics.json"
    monkeypatch.setenv(EXPERIMENT_METRICS_ENV, str(metrics))
    calls = []

    def prepared(**kwargs: Any) -> CombatPolicyInputs:
        calls.append(kwargs)
        return inputs

    monkeypatch.setattr("spireshift.combat_policy.load_combat_policy_inputs", prepared)
    arguments = [
        "model",
        "train-combat-policy",
        str(path),
        "--split-manifest",
        "manifests/splits/mock-v1-seeds-000000-000999-v1.json",
        "--manifest",
        "manifests/patches/mock-v1.json",
        "--upstream-root",
        str(tmp_path),
        "--output-dir",
        str(output),
    ]
    assert main(arguments) == 0 and len(calls) == 1
    saved_metrics = json.loads(metrics.read_text())
    assert all(
        saved_metrics[field] == 0 for field in ("trajectories", "simulations", "transitions")
    )
    checkpoint = load_production_model_checkpoint(output / "checkpoint.json")
    report = load_production_training_report(output / "training-report.json", checkpoint=checkpoint)
    assert report["candidate_eligible"] is True
    original = (output / "checkpoint.json").read_bytes()
    assert main(arguments) == 1 and len(calls) == 1
    assert (output / "checkpoint.json").read_bytes() == original
    assert "display it instead" in capsys.readouterr().out


def test_cli_failed_preflight_records_zero_games_and_publishes_no_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _ = _extended_inputs()
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config.document))
    metrics = tmp_path / "metrics.json"
    monkeypatch.setenv(EXPERIMENT_METRICS_ENV, str(metrics))

    def failure(**kwargs: Any) -> None:
        raise ValueError("Combat validation binding preflight failed")

    monkeypatch.setattr("spireshift.combat_policy.load_combat_policy_inputs", failure)
    output = tmp_path / "model"
    assert (
        main(
            [
                "model",
                "train-combat-policy",
                str(path),
                "--split-manifest",
                "manifests/splits/mock-v1-seeds-000000-000999-v1.json",
                "--manifest",
                "manifests/patches/mock-v1.json",
                "--upstream-root",
                str(tmp_path),
                "--output-dir",
                str(output),
            ]
        )
        == 1
    )
    saved = json.loads(metrics.read_text())
    assert all(saved[k] == 0 for k in ("trajectories", "simulations", "transitions"))
    assert not output.exists()


@pytest.mark.parametrize("wrong", ["overlap", "bad_normalization", "implicit_launch"])
def test_bad_training_scope_config_is_rejected(wrong: str) -> None:
    config, _ = _inputs()
    d = copy.deepcopy(config.document)
    if wrong == "overlap":
        d["fresh_confirmation"]["seeds"] = [1, 2]
        d["fresh_confirmation"]["run_count"] = 2
    elif wrong == "bad_normalization":
        d["optimization"]["normalization"] = "count_every_pair_as_independent"
    else:
        d["fresh_confirmation"]["launch"] = "start_after_training"
    with pytest.raises(ValueError):
        CombatPolicyConfig.from_mapping(_identified(d, "config_id"))


def test_owner_script_rotates_attempts_caches_and_preserves_partial(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "bin").mkdir()
    script = tmp_path / "scripts/train.sh"
    script.write_text(Path("scripts/train-combat-policy-v1.sh").read_text())
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
    (resources / "combat-policy-base-v9-train-v1-attempt-1.json").write_text("{}")
    subprocess.run(["bash", str(script)], env=env, check=True, capture_output=True)
    assert "attempt-2.json" in log.read_text() and "--max-wall-seconds 1800" in log.read_text()
    assert EXTENDED_CONFIG_PATH.name in log.read_text()
    assert log.read_text().count("resources run") == 1
    assert "evaluate" not in log.read_text() and "--extra evangambit" not in log.read_text()
    output = tmp_path / "artifacts/models/sts2-v0.107.1-base-v9"
    output.mkdir(parents=True)
    (output / "checkpoint.json").write_text("{}")
    log.write_text("")
    failed = subprocess.run(["bash", str(script)], env=env, capture_output=True)
    assert failed.returncode == 1 and log.read_text() == ""
    (output / "training-report.json").write_text("{}")
    subprocess.run(["bash", str(script)], env=env, check=True, capture_output=True)
    assert (
        "show-combat-policy-training" in log.read_text() and "resources run" not in log.read_text()
    )


@pytest.mark.parametrize("extended", [False, True])
def test_schema_contracts_accept_frozen_recipe_and_toy_training_artifacts(extended: bool) -> None:
    resources = [
        (
            f"https://spireshift.dev/schemas/{path.name}",
            Resource.from_contents(json.loads(path.read_text())),
        )
        for path in Path("schemas").glob("*.json")
    ]
    registry: Registry[Any] = Registry().with_resources(resources)
    config, inputs = _extended_inputs() if extended else _inputs()
    result = train_combat_policy_inputs(inputs=inputs, config=config)
    prediction = production_model_from_checkpoint(result.checkpoint).predict(
        inputs.validation[0].representation
    )
    assert prediction.source_action_ids == tuple(
        c.source_action_id for c in inputs.validation[0].representation.candidates
    )
    config_version = "v2" if extended else "v1"
    for name, document in (
        (f"combat-policy-training-config-{config_version}", config.document),
        ("production-model-checkpoint-v9", result.checkpoint),
        ("production-model-training-report-v9", result.report),
    ):
        schema = json.loads(Path(f"schemas/{name}.json").read_text())
        Draft202012Validator(schema, registry=registry).validate(document)
