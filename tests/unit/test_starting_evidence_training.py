from __future__ import annotations

import copy
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from test_starting_evidence import _Policy as StartingPolicy
from test_starting_evidence import _StartingEnvironment
from test_trajectory_policy import _build_package, _write

from spireshift import starting_evidence_training as training
from spireshift import trajectory_policy as policy
from spireshift.agents.learned import ProductionCheckpointPolicy
from spireshift.cli import main
from spireshift.core.manifest import manifest_identifier
from spireshift.core.types import Observation, Transition
from spireshift.production_models import (
    load_production_model_checkpoint,
    load_production_training_report,
    production_model_from_checkpoint,
)
from spireshift.splits import SplitName
from spireshift.starting_evidence import (
    StartingEvidenceConfig,
    collect_starting_option_evidence,
    verify_starting_option_evidence,
)
from spireshift.starting_option_training import prepare_starting_option_space
from spireshift.starting_options import StartingOptionConfig, load_starting_option_config
from spireshift.trajectory_search import TrajectorySearchConfig


def _package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, mode: str = "normal"
) -> dict[str, Any]:
    original = _build_package(tmp_path, monkeypatch)
    old_kwargs = original["kwargs"]
    parent = original["parent"]
    parent_report = copy.deepcopy(original["parent_report"])
    split = old_kwargs["split_manifest"]
    seeds = set(split.seeds(SplitName.TRAIN)[8:16])
    evidence_groups = policy._folds(
        seeds, {"selection_fraction": 0.25, "selection_salt": "trajectory-policy-selection-v1"}
    )

    class Environment(_StartingEnvironment):
        victory_option = 2 if mode == "victory" else None

        def __init__(self) -> None:
            super().__init__()
            self.extra_step = False

        def reset(self, seed: int) -> Observation:
            self.extra_step = False
            return super().reset(seed)

        def observe(self) -> Observation:
            original_observation = super().observe()
            public = copy.deepcopy(original_observation.public_state)
            if self.seed in evidence_groups["selection"]:
                public["neow_options"] = [132, 22, 33]
            if self.choice is not None and mode in {"ties", "activity", "insufficient"}:
                public["floor"] = 5 if mode == "insufficient" or self.choice != 1 else 18
                if mode == "insufficient":
                    public["act"] = "overgrowth"
            if mode == "activity" and self.choice == 2 and not self.extra_step:
                public["gold"] = 98
            if mode == "victory":
                public["victory"] = self.terminal and self.choice == 2
            return Observation(
                original_observation.schema_version,
                original_observation.patch_id,
                original_observation.decision_type,
                public,
                manifest_identifier(public).removeprefix("sha256:"),
            )

        def step(self, action: Any) -> Transition:
            if mode == "activity" and self.choice == 2 and not self.extra_step:
                source = self.observe()
                self.extra_step = True
                return Transition(source, action, self.observe(), 0.0, False, False)
            return super().step(action)

    fixed_policy = StartingPolicy(split.manifest_id)
    fixed_policy.model_id = parent["model_id"]
    fixed_policy.policy_id = f"production-checkpoint-policy-v1:{parent['model_id']}"
    runner = TrajectorySearchConfig(
        split_manifest_id=split.manifest_id,
        ruleset_manifest_id=Environment.ruleset.manifest_id,
        model_id=parent["model_id"],
        training_report_id=parent_report["report_id"],
        run_offset=8,
        run_count=8,
        generations=1,
        beam_width=3,
        mutations_per_parent=2,
        workers=1,
        maximum_decisions_per_run=8,
        cycle_repetition_threshold=3,
        liveness_tail_length=4,
        no_op_fallback_threshold=2,
        mutation_salt="evidence-policy-test",
        milestones=old_kwargs["search_config"].milestones,
        frontier_ranking=old_kwargs["search_config"].frontier_ranking,
    )
    evidence_doc = {
        "schema_version": "starting-option-evidence-config-v1",
        "encoder_id": "starting-ancient-public-option-v1",
        "trajectory_config": runner.as_dict(),
        "selection_fraction": 0.25,
        "selection_salt": "trajectory-policy-selection-v1",
        "complete_run_subfolds": evidence_groups,
        "minimum_runs": {"fit": 2, "selection": 2, "strong_selection": 2},
    }
    evidence_doc["config_id"] = manifest_identifier(evidence_doc)
    evidence_config = StartingEvidenceConfig.from_mapping(evidence_doc)
    directory = tmp_path / "exhaustive"
    evidence = collect_starting_option_evidence(
        environment_factory=Environment,
        ruleset=Environment.ruleset,
        policy=cast(ProductionCheckpointPolicy, fixed_policy),
        split_manifest=split,
        training_report_id=parent_report["report_id"],
        config=evidence_config,
        objective=old_kwargs["objective"],
        output_directory=directory,
    )
    anchor_seeds = set(split.seeds(SplitName.TRAIN)[:8])
    original_groups = policy._folds(anchor_seeds, original["recipe"])
    prior_wrapper = {
        "schema_version": "starting-option-policy-training-config-v1",
        "encoder_id": "starting-ancient-public-option-v1",
        "dimension": 4096,
        "trajectory_recipe": original["recipe"],
    }
    prior_wrapper["config_id"] = manifest_identifier(prior_wrapper)
    assignment = {
        "schema_version": "production-model-training-report-v7",
        "trajectory_finetuning": {
            "recipe": original["recipe"],
            "complete_run_subfolds": original_groups,
        },
        "starting_option_training": {"config": prior_wrapper},
    }
    assignment["report_id"] = manifest_identifier(assignment)
    assignment_path = tmp_path / "assignment.json"
    _write(assignment_path, assignment)

    def reports(path: Path, **kwargs: Any) -> dict[str, Any]:
        if path == assignment_path:
            return copy.deepcopy(assignment)
        if path == old_kwargs["parent_report_path"]:
            return copy.deepcopy(parent_report)
        return load_production_training_report(path, **kwargs)

    monkeypatch.setattr(training, "load_production_training_report", reports)
    monkeypatch.setattr(training, "_load_curriculum_examples", original["curriculum_loader"])
    recipe = copy.deepcopy(original["recipe"])
    recipe["schema_version"] = training.RECIPE_SCHEMA
    recipe["inputs"] = {
        k: v
        for k, v in recipe["inputs"].items()
        if k not in {"collection_id", "search_report_id", "search_config_id"}
    }
    recipe["inputs"].update(
        evidence_report_id=evidence["report_id"],
        evidence_config_id=evidence_config.config_id,
        anchor_assignment_report_id=assignment["report_id"],
        anchor_assignment_config_id=original["recipe"]["config_id"],
    )
    recipe["anchor_complete_run_subfolds"] = original_groups
    recipe["evidence_complete_run_subfolds"] = evidence_groups
    recipe["config_id"] = manifest_identifier({k: v for k, v in recipe.items() if k != "config_id"})
    wrapper = {
        "schema_version": "starting-option-policy-training-config-v2",
        "encoder_id": "starting-ancient-public-option-v1",
        "dimension": 4096,
        "evidence_recipe": recipe,
    }
    wrapper["config_id"] = manifest_identifier(wrapper)
    kwargs = {
        key: old_kwargs[key]
        for key in (
            "parent_checkpoint_path",
            "parent_report_path",
            "train_report_path",
            "validation_report_path",
            "split_manifest",
            "ruleset",
            "objective",
        )
    }
    kwargs.update(
        config=StartingOptionConfig.from_mapping(wrapper),
        evidence_config=evidence_config,
        evidence_path=directory / "starting-option-evidence.json",
        anchor_assignment_report_path=assignment_path,
    )
    return {
        "kwargs": kwargs,
        "parent": parent,
        "evidence": evidence,
        "assignment": assignment,
        "root": tmp_path,
        "environment": Environment,
    }


@pytest.fixture
def package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    return _package(tmp_path, monkeypatch)


def test_verified_evidence_keeps_original_and_new_folds_without_repartitioning(
    package: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(package["environment"], "reset", lambda *a: pytest.fail("Loader replayed"))
    inputs = training.load_starting_evidence_policy_inputs(**package["kwargs"])
    recipe = package["kwargs"]["config"].recipe.document
    assert inputs.runs == {
        k: sorted(
            recipe["anchor_complete_run_subfolds"][k] + recipe["evidence_complete_run_subfolds"][k]
        )
        for k in ("fit", "selection")
    }
    assert inputs.runs != policy._folds(set(inputs.runs["fit"] + inputs.runs["selection"]), recipe)
    assert len(inputs.preferences) == 24
    assert {r["preferred_action_id"] for r in inputs.preference_records} == {
        "evangambit:ancient:1",
        "evangambit:ancient:2",
    }
    assert all(item.weight == 1 for item in inputs.preferences)


@pytest.mark.parametrize(
    "mode,exclusion", [("ties", "tied"), ("activity", "distinct_public_states_on_floor")]
)
def test_ties_and_activity_only_differences_are_excluded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, exclusion: str
) -> None:
    package = _package(tmp_path, monkeypatch, mode=mode)
    inputs = training.load_starting_evidence_policy_inputs(**package["kwargs"])
    assert inputs.exclusions[exclusion] == 8
    assert sum(p.weight > 0 for p in inputs.preferences) == 16


@pytest.mark.parametrize("mode", ["insufficient", "victory"])
def test_unsuitable_evidence_stops_before_any_optimization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    package = _package(tmp_path, monkeypatch, mode=mode)
    monkeypatch.setattr(
        policy, "train_policy_inputs", lambda **kw: pytest.fail("Optimizer started")
    )
    with pytest.raises(ValueError, match="sufficiency|victory"):
        training.train_starting_evidence_policy(**package["kwargs"])


def test_run_normalization_does_not_triple_the_gradient(package: dict[str, Any]) -> None:
    inputs = training.load_starting_evidence_policy_inputs(**package["kwargs"])
    augmented, space = prepare_starting_option_space(
        inputs, package["kwargs"]["ruleset"], package["kwargs"]["config"]
    )
    rows = tuple(p for p in augmented.preferences if p.run_seed in augmented.runs["fit"])
    baseline = production_model_from_checkpoint(inputs.parent_checkpoint).policy_weights
    recipe = package["kwargs"]["config"].recipe.document
    a = policy._gradient(baseline, baseline, rows, (), recipe)
    b = policy._gradient(baseline, baseline, rows * 3, (), recipe)
    assert {k: v for k, v in a.items() if k >= space.offset} == pytest.approx(
        {k: v for k, v in b.items() if k >= space.offset}
    )
    assert policy._preference_metrics(baseline, rows)["effective_weight"] == pytest.approx(6)


def test_fitting_vocabulary_does_not_learn_selection_only_option(package: dict[str, Any]) -> None:
    inputs = training.load_starting_evidence_policy_inputs(**package["kwargs"])
    _, space = prepare_starting_option_space(
        inputs, package["kwargs"]["ruleset"], package["kwargs"]["config"]
    )
    assert space.head.known_option_ids == (11, 22, 33)
    assert space.coverage["selection_preferences"]["unknown_option_ids"] == [132]
    assert space.coverage["fit_preferences"]["unknown_option_ids"] == []


def test_file_changed_after_integrity_verification_is_rejected(
    package: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    original = verify_starting_option_evidence

    def changed(path: Path, **kwargs: Any) -> dict[str, Any]:
        verified = original(path, **kwargs)
        case = path.parent / package["evidence"]["cases"][0]["path"]
        case.write_bytes(case.read_bytes() + b"\n")
        return verified

    monkeypatch.setattr(training, "verify_starting_option_evidence", changed)
    with pytest.raises(ValueError, match="changed after saved verification"):
        training.load_starting_evidence_policy_inputs(**package["kwargs"])


def test_training_preserves_all_heads_round_trips_and_verifies_without_optimization(
    package: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    result = training.train_starting_evidence_policy(**package["kwargs"])
    assert result.checkpoint["schema_version"] == training.CHECKPOINT_SCHEMA
    assert result.checkpoint["heads"] == package["parent"]["heads"]
    assert result.report["candidate_eligible"] is True
    assert result.report["trajectory_finetuning"]["selected_epoch"] > 0
    assert result.report["checkpoint_promoted"] is False
    candidate = package["root"] / "result.json"
    report = package["root"] / "report.json"
    _write(candidate, result.checkpoint)
    _write(report, result.report)
    assert load_production_model_checkpoint(candidate) == result.checkpoint
    assert load_production_training_report(report, checkpoint=result.checkpoint) == result.report
    monkeypatch.setattr(
        training, "train_starting_evidence_policy", lambda **kw: pytest.fail("Verifier retrained")
    )
    monkeypatch.setattr(
        package["environment"], "reset", lambda *a: pytest.fail("Verifier replayed")
    )
    verified = training.verify_starting_evidence_policy(
        checkpoint_path=candidate, report_path=report, **package["kwargs"]
    )
    assert verified["valid"] and verified["games_replayed"] == 0
    assert verified["later_validation_decisions_unchanged"] == 4
    assert (
        verified["starting_evidence_training"]["selection_only_ids_covered_by_fitting_anchors"]
        == []
    )


def test_no_advancing_epoch_keeps_zero_residual(package: dict[str, Any]) -> None:
    wrapper = copy.deepcopy(package["kwargs"]["config"].document)
    recipe = wrapper["evidence_recipe"]
    recipe["limits"]["minimum_preference_loss_improvement"] = 10.0
    # The source recipe must carry the same predeclared threshold, never a post-result relaxation.
    assignment = package["assignment"]
    original = assignment["trajectory_finetuning"]["recipe"]
    original["limits"]["minimum_preference_loss_improvement"] = 10.0
    original["config_id"] = manifest_identifier(
        {k: v for k, v in original.items() if k != "config_id"}
    )
    assignment["report_id"] = manifest_identifier(
        {k: v for k, v in assignment.items() if k != "report_id"}
    )
    recipe["inputs"]["anchor_assignment_config_id"] = original["config_id"]
    recipe["inputs"]["anchor_assignment_report_id"] = assignment["report_id"]
    recipe["config_id"] = manifest_identifier({k: v for k, v in recipe.items() if k != "config_id"})
    wrapper["config_id"] = manifest_identifier(
        {k: v for k, v in wrapper.items() if k != "config_id"}
    )
    kwargs = {**package["kwargs"], "config": StartingOptionConfig.from_mapping(wrapper)}
    result = training.train_starting_evidence_policy(**kwargs)
    assert result.report["trajectory_finetuning"]["selected_epoch"] == 0
    assert result.report["candidate_eligible"] is False
    assert result.checkpoint["starting_option_residual"]["head"]["weights"] == []
    assert result.checkpoint["heads"] == package["parent"]["heads"]
    with pytest.raises(ValueError, match="advancement checks"):
        ProductionCheckpointPolicy(
            checkpoint=result.checkpoint,
            training_report=result.report,
            ruleset=kwargs["ruleset"],
        )


@pytest.mark.parametrize("head", ["policy", "terminal_value", "tactical_death_risk"])
def test_modified_original_parent_head_cannot_be_hidden_by_a_new_model_hash(
    package: dict[str, Any], head: str
) -> None:
    result = training.train_starting_evidence_policy(**package["kwargs"])
    result.checkpoint["heads"][head]["weights"].append({"index": 0, "value": 0.25})
    candidate = package["root"] / "tampered.json"
    _write(candidate, result.checkpoint, "model_id")
    with pytest.raises(ValueError, match="Frozen.*changed"):
        load_production_model_checkpoint(candidate)


@pytest.mark.parametrize(
    "field",
    [
        "learning_rate",
        "limits",
        "anchor_complete_run_subfolds",
        "evidence_complete_run_subfolds",
        "inputs",
    ],
)
def test_loader_rejects_recipe_threshold_ownership_or_input_drift(
    package: dict[str, Any], field: str
) -> None:
    wrapper = copy.deepcopy(package["kwargs"]["config"].document)
    recipe = wrapper["evidence_recipe"]
    if field == "learning_rate":
        recipe[field] *= 2
    elif field == "limits":
        recipe[field]["maximum_regret_increase"] += 1
    elif field == "inputs":
        recipe[field]["evidence_report_id"] = manifest_identifier({"wrong": "input"})
    else:
        a = recipe[field]["fit"].pop(0)
        b = recipe[field]["selection"].pop(0)
        recipe[field]["fit"] = sorted(recipe[field]["fit"] + [b])
        recipe[field]["selection"] = sorted(recipe[field]["selection"] + [a])
    recipe["config_id"] = manifest_identifier({k: v for k, v in recipe.items() if k != "config_id"})
    wrapper["config_id"] = manifest_identifier(
        {k: v for k, v in wrapper.items() if k != "config_id"}
    )
    with pytest.raises(ValueError, match="optimization|identities|ownership"):
        training.load_starting_evidence_policy_inputs(
            **{**package["kwargs"], "config": StartingOptionConfig.from_mapping(wrapper)}
        )


def test_verifier_recomputes_metrics_after_outer_hash_tampering(package: dict[str, Any]) -> None:
    result = training.train_starting_evidence_policy(**package["kwargs"])
    candidate = package["root"] / "result.json"
    report = package["root"] / "report.json"
    _write(candidate, result.checkpoint)
    result.report["preference_diagnostics"]["by_run"][
        str(package["kwargs"]["evidence_config"].seeds[0])
    ]["directional_accuracy"] = -1
    _write(report, result.report, "report_id")
    with pytest.raises(ValueError, match="metrics or coverage"):
        training.verify_starting_evidence_policy(
            checkpoint_path=candidate, report_path=report, **package["kwargs"]
        )


def _arguments(package: dict[str, Any], config: Path, candidate: Path, report: Path) -> list[str]:
    kw = package["kwargs"]
    evidence_config = package["root"] / "evidence-config.json"
    _write(evidence_config, kw["evidence_config"].document)
    return [
        str(config),
        str(kw["parent_checkpoint_path"]),
        str(candidate),
        "--parent-report",
        str(kw["parent_report_path"]),
        "--report",
        str(report),
        "--evidence",
        str(kw["evidence_path"]),
        "--evidence-config",
        str(evidence_config),
        "--anchor-assignment-report",
        str(kw["anchor_assignment_report_path"]),
        "--train-report",
        str(kw["train_report_path"]),
        "--validation-report",
        str(kw["validation_report_path"]),
        "--split-manifest",
        "manifests/splits/mock-v1-seeds-000000-000999-v1.json",
        "--ruleset-manifest",
        "unused",
    ]


def test_cli_saved_result_verification_never_loads_engine_or_starts_training(
    package: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    result = training.train_starting_evidence_policy(**package["kwargs"])
    config, candidate, report = (
        package["root"] / name for name in ("config.json", "result.json", "report.json")
    )
    _write(config, package["kwargs"]["config"].document)
    _write(candidate, result.checkpoint)
    _write(report, result.report)
    monkeypatch.setattr(
        "spireshift.cli.load_patch_manifest",
        lambda _: SimpleNamespace(ruleset_identity=lambda: package["kwargs"]["ruleset"]),
    )
    monkeypatch.setattr(
        "spireshift.cli.train_starting_evidence_policy",
        lambda **kw: pytest.fail("Training started"),
    )
    monkeypatch.setattr(
        "spireshift.cli.load_evangambit_backend", lambda *a, **kw: pytest.fail("Engine loaded")
    )
    args = _arguments(package, config, candidate, report)
    assert main(["model", "verify-starting-evidence-policy", *args]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True
    assert main(["model", "finetune-starting-evidence-policy", *args]) == 1
    assert "distinct and new" in json.loads(capsys.readouterr().out)["error"]


def test_owner_script_has_one_job_and_saved_result_and_partial_output_guards(
    tmp_path: Path,
) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    script = scripts / "train-starting-evidence-policy-v1.sh"
    script.write_text(Path("scripts/train-starting-evidence-policy-v1.sh").read_text())
    binary = tmp_path / "bin"
    binary.mkdir()
    uv = binary / "uv"
    uv.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@"\n')
    uv.chmod(0o755)
    environment = {**os.environ, "PATH": str(binary) + os.pathsep + os.environ["PATH"]}
    resources = tmp_path / "artifacts/resources"
    resources.mkdir(parents=True)
    (resources / "starting-evidence-policy-base-v8-train-v1-attempt-1.json").write_text("{}")
    first = subprocess.run(
        ["bash", str(script)], capture_output=True, text=True, env=environment, check=True
    )
    assert first.stdout.count("finetune-starting-evidence-policy") == 1
    assert "attempt-2.json" in first.stdout
    assert first.stdout.count("verify-starting-evidence-policy") == 1
    output = tmp_path / "artifacts/models/sts2-v0.107.1-base-v8"
    output.mkdir(parents=True)
    (output / "checkpoint.json").write_text("{}")
    partial = subprocess.run(["bash", str(script)], capture_output=True, text=True, env=environment)
    assert partial.returncode == 1 and "Incomplete" in partial.stderr and not partial.stdout
    (output / "training-report.json").write_text("{}")
    complete = subprocess.run(
        ["bash", str(script)], capture_output=True, text=True, env=environment, check=True
    )
    assert "verify-starting-evidence-policy" in complete.stdout
    assert (
        "finetune-starting-evidence-policy" not in complete.stdout
        and "resources" not in complete.stdout
    )


def test_json_schemas_validate_frozen_config_and_new_training_artifacts(
    package: dict[str, Any],
) -> None:
    result = training.train_starting_evidence_policy(**package["kwargs"])
    documents = [json.loads(p.read_text()) for p in Path("schemas").glob("*.json")]
    registry: Registry[Any] = Registry().with_resources(
        (d["$id"], Resource.from_contents(d)) for d in documents
    )
    for schema, value in [
        ("starting-option-policy-training-config-v2", package["kwargs"]["config"].document),
        (
            "starting-evidence-policy-training-config-v1",
            package["kwargs"]["config"].recipe.document,
        ),
        (training.CHECKPOINT_SCHEMA, result.checkpoint),
        (training.REPORT_SCHEMA, result.report),
    ]:
        Draft202012Validator(
            json.loads((Path("schemas") / (schema + ".json")).read_text()), registry=registry
        ).validate(value)
    frozen = load_starting_option_config(
        Path("configs/starting-option-policy/sts2-v0.107.1-base-v2-exhaustive-evidence-v1.json")
    )
    assert frozen.recipe.document["epochs"] == 40
    assert frozen.recipe.document["limits"]["maximum_regret_increase"] == 0.0002
    assert len(frozen.recipe.document["evidence_complete_run_subfolds"]["fit"]) == 48
    assert len(frozen.recipe.document["evidence_complete_run_subfolds"]["selection"]) == 16
