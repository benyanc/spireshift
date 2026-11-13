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
from test_starting_evidence_training import _arguments, _package
from test_trajectory_policy import _write

from spireshift import starting_evidence_diagnostic as diagnosis
from spireshift import starting_evidence_training as training
from spireshift import trajectory_policy as policy
from spireshift.cli import main
from spireshift.core.manifest import manifest_identifier
from spireshift.models import _dot, _softmax
from spireshift.production_models import production_model_from_checkpoint
from spireshift.starting_option_training import prepare_starting_option_space
from spireshift.starting_options import (
    ENCODER_ID,
    StartingOptionConfig,
    _context,
    starting_option_feature_tokens,
    starting_option_ids,
)
from spireshift.trajectory_diagnostic import _contrast


def _freeze_no_update(package: dict[str, Any]) -> None:
    wrapper = copy.deepcopy(package["kwargs"]["config"].document)
    wrapper["evidence_recipe"]["limits"]["minimum_preference_loss_improvement"] = 10.0
    assignment = package["assignment"]
    original = assignment["trajectory_finetuning"]["recipe"]
    original["limits"]["minimum_preference_loss_improvement"] = 10.0
    original["config_id"] = manifest_identifier(
        {k: v for k, v in original.items() if k != "config_id"}
    )
    prior = assignment["starting_option_training"]["config"]
    prior["trajectory_recipe"] = original
    prior["config_id"] = manifest_identifier({k: v for k, v in prior.items() if k != "config_id"})
    assignment["report_id"] = manifest_identifier(
        {k: v for k, v in assignment.items() if k != "report_id"}
    )
    recipe = wrapper["evidence_recipe"]
    recipe["inputs"].update(
        anchor_assignment_report_id=assignment["report_id"],
        anchor_assignment_config_id=original["config_id"],
    )
    recipe["config_id"] = manifest_identifier({k: v for k, v in recipe.items() if k != "config_id"})
    wrapper["config_id"] = manifest_identifier(
        {k: v for k, v in wrapper.items() if k != "config_id"}
    )
    package["kwargs"]["config"] = StartingOptionConfig.from_mapping(wrapper)
    _write(package["kwargs"]["anchor_assignment_report_path"], assignment)


@pytest.fixture
def package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    package = _package(tmp_path, monkeypatch)
    _freeze_no_update(package)
    result = training.train_starting_evidence_policy(**package["kwargs"])
    assert result.report["candidate_eligible"] is False
    assert result.report["trajectory_finetuning"]["selected_epoch"] == 0
    kw = package["kwargs"]
    paths = {
        "config": tmp_path / "config.json",
        "parent_checkpoint": kw["parent_checkpoint_path"],
        "checkpoint": tmp_path / "candidate.json",
        "--parent-report": kw["parent_report_path"],
        "--report": tmp_path / "candidate-report.json",
        "--evidence": kw["evidence_path"],
        "--evidence-config": tmp_path / "evidence-config.json",
        "--anchor-assignment-report": kw["anchor_assignment_report_path"],
        "--train-report": kw["train_report_path"],
        "--validation-report": kw["validation_report_path"],
        "--split-manifest": Path("manifests/splits/mock-v1-seeds-000000-000999-v1.json"),
        "--ruleset-manifest": tmp_path / "ruleset.json",
    }
    _write(paths["config"], kw["config"].document)
    _write(paths["--evidence-config"], kw["evidence_config"].document)
    _write(paths["checkpoint"], result.checkpoint)
    _write(paths["--report"], result.report)
    paths["--ruleset-manifest"].write_text("{}")

    def fake_manifest(_: Path) -> SimpleNamespace:
        return SimpleNamespace(ruleset_identity=lambda: kw["ruleset"])

    monkeypatch.setattr(diagnosis, "load_patch_manifest", fake_manifest)
    monkeypatch.setattr("spireshift.cli.load_patch_manifest", fake_manifest)
    command = ["uv", "run", "spireshift", "model", "finetune-starting-evidence-policy"]
    command += [str(paths[key]) for key in ("config", "parent_checkpoint", "checkpoint")]
    for flag, path in paths.items():
        if flag.startswith("--"):
            command.extend([flag, str(path)])
    resource = {
        "schema_version": "experiment-resources-v1",
        "experiment_kind": "training",
        "working_directory": str(Path.cwd()),
        "command": command,
        "status": "completed",
        "exit_code": 0,
        "cap": None,
        "usage": {
            "wall_seconds": 1.0,
            "cpu_seconds": 1.0,
            "cpu_hours": 1.0 / 3600,
            "gpu_seconds": None,
            "gpu_hours": None,
        },
        "limits": {},
        "hardware": {},
        "artifacts": {"roots": [str(tmp_path)]},
    }
    resource["report_id"] = manifest_identifier(resource)
    resource_path = tmp_path / "resources.json"
    _write(resource_path, resource)
    config_doc = {
        "schema_version": diagnosis.CONFIG_SCHEMA,
        "objective_id": "terminal-victory-v1",
        "training_config_id": kw["config"].document["config_id"],
        "candidate_model_id": result.checkpoint["model_id"],
        "candidate_report_id": result.report["report_id"],
        "resource_report_id": resource["report_id"],
    }
    config_doc["config_id"] = manifest_identifier(config_doc)
    config = diagnosis.StartingEvidenceDiagnosticConfig.from_mapping(config_doc)
    _write(tmp_path / "diagnostic-config.json", config_doc)
    package.update(
        result=result,
        paths=paths,
        resource=resource,
        config=config,
        diagnostic_kwargs={
            **kw,
            "diagnostic_config": config,
            "checkpoint_path": paths["checkpoint"],
            "report_path": paths["--report"],
            "resource_report_path": resource_path,
            "source_paths": paths,
        },
    )
    return package


def test_saved_audit_reconciles_without_optimizer_engine_or_file_mutation(
    package: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = package["paths"]
    before = {str(p): p.read_bytes() for p in paths.values() if p.exists()}
    monkeypatch.setattr(
        policy, "train_policy_inputs", lambda **kw: pytest.fail("Optimizer started")
    )
    monkeypatch.setattr(
        training, "train_starting_evidence_policy", lambda **kw: pytest.fail("Retrained")
    )
    monkeypatch.setattr(package["environment"], "reset", lambda *a: pytest.fail("Game replayed"))
    report = diagnosis.diagnose_starting_evidence_policy(**package["diagnostic_kwargs"])
    assert report["reconciliation_pass"] and report["optimizer_steps"] == 0
    assert report["validation_interpretation"] == "unchanged_epoch_zero_fallback"
    assert report["verification"]["later_validation_decisions_unchanged"] == 4
    assert (
        report["complete_run_subfolds"]["evidence"]
        == package["kwargs"]["config"].recipe.document["evidence_complete_run_subfolds"]
    )
    assert (
        len(report["learning_curve"]["epochs"])
        == package["kwargs"]["config"].recipe.document["epochs"]
    )
    assert report["coverage"]["selection_preferences"]["unknown_option_ids"] == [132]
    assert report["fitting_gradient"]["selection_contributes_to_gradient"] is False
    assert report["checkpoint_promoted"] is False and report["games_replayed"] == 0
    assert before == {str(p): p.read_bytes() for p in paths.values() if p.exists()}
    repeated = diagnosis.diagnose_starting_evidence_policy(**package["diagnostic_kwargs"])
    assert report == repeated


def test_semantic_tokens_keep_inference_hashes_and_fallback_exactly(
    package: dict[str, Any],
) -> None:
    inputs = training.load_starting_evidence_policy_inputs(**package["kwargs"])
    inputs, space = prepare_starting_option_space(
        inputs, package["kwargs"]["ruleset"], package["kwargs"]["config"]
    )
    for record in inputs.preference_records:
        representation = policy._preference_representation(record, package["kwargs"]["ruleset"])
        tokens = starting_option_feature_tokens(representation, space.head.known_option_ids)
        expected = []
        options = starting_option_ids(representation)
        assert options is not None
        for identity, candidate in zip(options, tokens, strict=True):
            # Reconstruct the pre-audit encoder independently, including its zero-value tokens.
            category = str(identity) if identity in space.head.known_option_ids else "unknown"
            original = {
                json.dumps(
                    [ENCODER_ID, "ancient_option_id", category, key], separators=(",", ":")
                ): value
                for key, value in _context(representation).items()
            }
            assert candidate == {key: value for key, value in original.items() if value}
            values: dict[int, float] = {}
            for token, value in original.items():
                digest = hashlib.sha256(token.encode()).digest()
                index = int.from_bytes(digest[:8], "big") % space.head.dimension
                values[index] = values.get(index, 0) + (1 if digest[8] & 1 else -1) * value
            expected.append({k: v for k, v in sorted(values.items()) if v})
        assert space.head.features(representation) == tuple(expected)
    selection = next(
        r
        for p, r in zip(inputs.preferences, inputs.preference_records, strict=True)
        if p.run_seed in inputs.runs["selection"]
    )
    representation = policy._preference_representation(selection, package["kwargs"]["ruleset"])
    assert all(
        json.loads(token)[2] == "unknown"
        for token in starting_option_feature_tokens(representation, space.head.known_option_ids)[0]
    )


def test_gradient_decomposition_keeps_complete_run_normalization_and_exposes_opposition() -> None:
    strong = policy._Preference(1, "maximum_floor", "event", 1.0, {12: 1.0}, {12: -1.0}, ())
    weak = policy._Preference(
        1, "enemy_hp_defeated_fraction_ppm", "event", 0.25, {12: -1.0}, {12: 1.0}, ()
    )
    other = replace(strong, run_seed=2)
    rows = (strong, weak, other)
    recipe = {"preference_strength": 1.0, "anchor_strength": 2.0, "proximal_strength": 0.1}
    parts = diagnosis._gradient_components(rows, {}, recipe, 10)
    repeated = diagnosis._gradient_components(rows * 3, {}, recipe, 10)
    for key in parts:
        assert repeated[key] == pytest.approx(parts[key])
    full = diagnosis._sum_gradients(list(parts.values()))
    assert full == pytest.approx(
        diagnosis._residual(policy._gradient({}, {}, rows, (), recipe), 10)
    )
    assert diagnosis._cosine(
        parts["maximum_floor"], parts["enemy_hp_defeated_fraction_ppm"]
    ) == pytest.approx(-1.0)


def test_conflicts_are_fitting_only_and_distinguish_semantic_aliases_from_hash_aliases() -> None:
    def row(seed: int, direction: int, *, semantic: str = "a", fold: str = "fit") -> dict[str, Any]:
        return {
            "comparison_id": str(seed),
            "run_seed": seed,
            "semantic_direction": direction,
            "semantic_contrast_id": semantic,
            "hashed_contrast_id": "shared",
            "rank_component": "maximum_floor",
            "source_state_hash": str(seed),
            "subfold": fold,
            "training_weight": 1.0,
            "residual_contrast_coordinates": 2,
            "parent_margin": 0.0,
        }

    rows = [row(1, 1), row(2, -1), row(3, -1, fold="selection"), row(4, 1, semantic="b")]
    conflicts = diagnosis._feature_conflicts(rows)
    assert conflicts["opposing_semantic_groups"][0]["independent_runs"] == [1, 2]
    assert conflicts["incompatible_parent_adjusted_groups"] == 1
    assert len(conflicts["different_semantics_same_hashed_contrast"]) == 1
    assert "3" not in conflicts["different_semantics_same_hashed_contrast"][0]["comparison_ids"]
    assert diagnosis._key({"a": 0.5, "b": -0.5})[0] == diagnosis._key({"b": 0.5, "a": -0.5})[0]
    assert diagnosis._key({"a": 0.5, "b": -0.5})[1] == -diagnosis._key({"b": 0.5, "a": -0.5})[1]


def test_opposing_labels_can_remain_compatible_after_frozen_parent_offsets() -> None:
    rows = [
        {
            "comparison_id": str(seed),
            "run_seed": seed,
            "semantic_direction": sign,
            "semantic_contrast_id": "same",
            "hashed_contrast_id": "same_hash",
            "rank_component": "maximum_floor",
            "source_state_hash": str(seed),
            "subfold": "fit",
            "training_weight": 1.0,
            "residual_contrast_coordinates": 2,
            "parent_margin": 2.0,
        }
        for seed, sign in [(1, 1), (2, -1)]
    ]
    result = diagnosis._feature_conflicts(rows)
    assert len(result["opposing_semantic_groups"]) == 1
    assert result["incompatible_parent_adjusted_groups"] == 0
    group = result["opposing_semantic_groups"][0]
    assert group["parent_adjusted_lower_bound"] == -2.0
    assert group["parent_adjusted_upper_bound"] == 2.0
    for row in rows:
        row["parent_margin"] = -2.0
    assert diagnosis._feature_conflicts(rows)["incompatible_parent_adjusted_groups"] == 1


def test_anchor_conflicts_and_local_kl_curvature_match_independent_finite_difference(
    package: dict[str, Any],
) -> None:
    inputs = training.load_starting_evidence_policy_inputs(**package["kwargs"])
    inputs, space = prepare_starting_option_space(
        inputs, package["kwargs"]["ruleset"], package["kwargs"]["config"]
    )
    p, record = next(
        (p, r)
        for p, r in zip(inputs.preferences, inputs.preference_records, strict=True)
        if p.run_seed in inputs.runs["fit"] and p.weight > 0
    )
    representation = policy._preference_representation(record, package["kwargs"]["ruleset"])
    fit_index = next(i for i, a in enumerate(inputs.anchors) if a.run_seed in inputs.runs["fit"])
    ids = record["candidate_action_ids"]
    utilities = [0.5] * 3
    utilities[ids.index(record["preferred_action_id"])] = 0.0
    utilities[ids.index(record["disfavored_action_id"])] = 1.0
    anchor = replace(
        inputs.anchors[fit_index],
        representation=representation,
        candidate_features=p.candidates,
        mean_progress_utilities=tuple(utilities),
    )
    anchors = list(inputs.anchors)
    anchors[fit_index] = anchor
    inputs = replace(inputs, anchors=tuple(anchors))
    gradient = diagnosis._residual(_contrast(p.preferred, p.disfavored), space.offset)
    recipe = space.config.recipe.document
    rows = diagnosis._preference_rows(
        inputs, space, {}, package["kwargs"]["ruleset"], {"full": gradient}
    )
    output = diagnosis._anchor_diagnosis(inputs, space, {}, rows, gradient, recipe)
    assert output["opposed_semantic_targets"] >= 1
    assert output["anchor_gradient_at_parent"] == 0
    norm = math.sqrt(sum(v * v for v in gradient.values()))
    descent = {k: -v / norm for k, v in gradient.items()}
    fitting = [a for a in inputs.anchors if a.run_seed in inputs.runs["fit"]]
    counts = {
        seed: sum(a.run_seed == seed for a in fitting) for seed in {a.run_seed for a in fitting}
    }

    def kl(t: float) -> float:
        total = 0.0
        for a in fitting:
            logits = tuple(
                t * _dot(descent, diagnosis._residual(f, space.offset))
                for f in a.candidate_features
            )
            parent = [1 / len(logits)] * len(logits)
            current = _softmax(logits)
            total += (
                recipe["anchor_strength"]
                / counts[a.run_seed]
                / len(counts)
                * sum(p * math.log(p / q) for p, q in zip(parent, current, strict=True))
            )
        return total

    epsilon = 0.0001
    finite_difference = (kl(epsilon) + kl(-epsilon) - 2 * kl(0)) / epsilon**2
    assert output["anchor_curvature_along_unit_preference_descent"] == pytest.approx(
        finite_difference, rel=1e-5, abs=1e-7
    )
    assert {a["run_seed"] for a in output["teacher_margin_directions"]} <= set(inputs.runs["fit"])


@pytest.mark.parametrize("change", ["count", "ownership", "loss", "nonfinite"])
def test_recorded_history_inventory_and_arithmetic_are_independently_checked(
    package: dict[str, Any], change: str
) -> None:
    inputs = training.load_starting_evidence_policy_inputs(**package["kwargs"])
    fit = tuple(p for p in inputs.preferences if p.weight > 0 and p.run_seed in inputs.runs["fit"])
    parent = production_model_from_checkpoint(inputs.parent_checkpoint).policy_weights
    metric = policy._preference_metrics(parent, fit)
    if change == "count":
        metric["records"] += 1
    if change == "ownership":
        metric["by_run"]["999"] = metric["by_run"].pop(next(iter(metric["by_run"])))
    if change == "loss":
        metric["weighted_pair_loss"] += 0.1
    if change == "nonfinite":
        metric["weighted_pair_loss"] = float("nan")
    with pytest.raises(ValueError, match="reconcile|invalid"):
        diagnosis._metric_inventory(metric, fit)


@pytest.mark.parametrize("change", ["identity", "command", "status", "path"])
def test_resource_or_source_binding_mismatch_stops_audit(
    package: dict[str, Any], change: str
) -> None:
    args = copy.copy(package["diagnostic_kwargs"])
    if change == "path":
        args["source_paths"] = {**args["source_paths"], "--evidence": Path("wrong-evidence")}
    else:
        resource = copy.deepcopy(package["resource"])
        if change == "identity":
            resource["usage"]["wall_seconds"] = 2.0
        if change == "command":
            resource["command"][4] = "evaluate-curriculum"
        if change == "status":
            resource["status"] = "failed"
        if change != "identity":
            resource["report_id"] = manifest_identifier(
                {k: v for k, v in resource.items() if k != "report_id"}
            )
            doc = {**package["config"].document, "resource_report_id": resource["report_id"]}
            doc["config_id"] = manifest_identifier(
                {k: v for k, v in doc.items() if k != "config_id"}
            )
            args["diagnostic_config"] = diagnosis.StartingEvidenceDiagnosticConfig.from_mapping(doc)
        _write(args["resource_report_path"], resource)
    with pytest.raises(ValueError, match="identity|command|completed|source paths"):
        diagnosis.diagnose_starting_evidence_policy(**args)


def test_cli_guard_and_cached_display_do_not_repeat_the_full_audit(
    package: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config = package["root"] / "diagnostic-config.json"
    output = package["root"] / "diagnostic.json"
    args = _arguments(
        package,
        package["paths"]["config"],
        package["paths"]["checkpoint"],
        package["paths"]["--report"],
    )
    args[-1] = str(package["paths"]["--ruleset-manifest"])
    args += [
        "--diagnostic-config",
        str(config),
        "--resource-report",
        str(package["diagnostic_kwargs"]["resource_report_path"]),
        "--output",
        str(output),
    ]
    monkeypatch.setattr(
        "spireshift.cli.load_evangambit_backend", lambda *a, **kw: pytest.fail("Engine loaded")
    )
    assert main(["model", "diagnose-starting-evidence-policy", *args]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["optimizer_steps"] == 0 and summary["reconciliation_pass"]
    monkeypatch.setattr(
        training,
        "load_starting_evidence_policy_inputs",
        lambda **kw: pytest.fail("Sources loaded again"),
    )
    assert main(["model", "diagnose-starting-evidence-policy", *args]) == 1
    assert "new and differ" in json.loads(capsys.readouterr().out)["error"]
    assert (
        main(
            [
                "model",
                "show-starting-evidence-diagnosis",
                str(output),
                "--diagnostic-config",
                str(config),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["source_inputs_reaudited"] is False
    output.write_bytes(output.read_bytes() + b" ")  # Whitespace does not change semantic identity.
    report = json.loads(output.read_text())
    report["games_replayed"] = 1
    _write(output, report, "report_id")
    with pytest.raises(ValueError, match="claim"):
        diagnosis.load_starting_evidence_diagnostic_report(output, package["config"])


def test_schema_and_frozen_production_diagnostic_bindings(package: dict[str, Any]) -> None:
    report = diagnosis.diagnose_starting_evidence_policy(**package["diagnostic_kwargs"])
    documents = [json.loads(p.read_text()) for p in Path("schemas").glob("*.json")]
    registry: Registry[Any] = Registry().with_resources(
        (d["$id"], Resource.from_contents(d)) for d in documents
    )
    for name, value in [
        (diagnosis.CONFIG_SCHEMA, package["config"].document),
        (diagnosis.REPORT_SCHEMA, report),
    ]:
        Draft202012Validator(
            json.loads((Path("schemas") / f"{name}.json").read_text()), registry=registry
        ).validate(value)
    frozen = diagnosis.load_starting_evidence_diagnostic_config(
        Path("configs/starting-evidence-diagnostic/sts2-v0.107.1-base-v8-v1.json")
    )
    assert (
        frozen.document["candidate_report_id"]
        == "sha256:da8125f404051f2251273e7ac91ff75eeacb5250f5c5fc1105fbe3f7cffebd6f"
    )


def test_owner_script_preserves_results_and_runs_only_one_saved_data_job(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    script = scripts / "diagnose-starting-evidence-policy-v1.sh"
    script.write_text(Path("scripts/diagnose-starting-evidence-policy-v1.sh").read_text())
    binary = tmp_path / "bin"
    binary.mkdir()
    uv = binary / "uv"
    uv.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@"\n')
    uv.chmod(0o755)
    environment = {**os.environ, "PATH": str(binary) + os.pathsep + os.environ["PATH"]}
    resources = tmp_path / "artifacts/resources"
    resources.mkdir(parents=True)
    (resources / "starting-evidence-base-v8-diagnostic-v1-attempt-1.json").write_text("{}")
    first = subprocess.run(
        ["bash", str(script)], capture_output=True, text=True, env=environment, check=True
    )
    assert (
        "attempt-2.json" in first.stdout
        and first.stdout.count("diagnose-starting-evidence-policy") == 1
    )
    assert not any(
        command in first.stdout
        for command in (
            "finetune",
            "search-run-trajectories",
            "discover-states",
            "evaluate-curriculum",
        )
    )
    output = (
        tmp_path
        / "artifacts/diagnostics/sts2-v0.107.1-base-v8-starting-evidence-v1/diagnostic.json"
    )
    output.parent.mkdir(parents=True)
    output.write_text("{}")
    completed = subprocess.run(
        ["bash", str(script)], capture_output=True, text=True, env=environment, check=True
    )
    assert (
        "show-starting-evidence-diagnosis" in completed.stdout
        and "resources" not in completed.stdout
    )
