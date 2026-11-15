from __future__ import annotations

import copy
import json
import math
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from test_starting_evidence import _collect, _StartingEnvironment
from test_starting_evidence import package as package

from spireshift.cli import main
from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import load_objective
from spireshift.core.types import Observation
from spireshift.resource_tracking import ExperimentMetrics
from spireshift.splits import SplitName
from spireshift.starting_evidence import (
    FILENAME as EVIDENCE_FILENAME,
)
from spireshift.starting_evidence import (
    StartingEvidenceConfig,
    load_verified_starting_option_evidence,
)
from spireshift.starting_repeatability import (
    CONFIG_SCHEMA,
    FILENAME,
    LEVELS,
    REPORT_SCHEMA,
    StartingRepeatabilityConfig,
    _confirmation,
    _decision,
    _direction,
    _pair_rows,
    _run_interval,
    _strata,
    analyze_starting_repeatability,
    load_starting_repeatability_config,
    load_starting_repeatability_report,
    prepare_starting_repeatability,
)
from spireshift.trajectory_policy import _folds
from spireshift.trajectory_search import TRAJECTORY_SELECTION_RANK_ORDER


def _identified(value: dict[str, Any], field: str) -> dict[str, Any]:
    return {**value, field: manifest_identifier({k: v for k, v in value.items() if k != field})}


@pytest.fixture
def study(tmp_path: Path, request: pytest.FixtureRequest) -> dict[str, Any]:
    source = request.getfixturevalue("package")
    historical = _collect(tmp_path / "historical", source)
    fresh = copy.deepcopy(source["config"].document)
    r = fresh["trajectory_config"]
    r["run_offset"] = 4
    r["config_id"] = manifest_identifier({k: v for k, v in r.items() if k != "config_id"})
    fresh["complete_run_subfolds"] = _folds(set(source["split"].seeds(SplitName.TRAIN)[4:8]), fresh)
    fresh = _identified(fresh, "config_id")
    fresh_package = {**source, "config": StartingEvidenceConfig.from_mapping(fresh)}
    prior = _identified(
        {
            "schema_version": "trajectory-mutation-preference-collection-v1",
            "cases": [{"run_seed": s} for s in source["config"].seeds],
            "partition": "train",
            "split_manifest_id": source["split"].manifest_id,
            "ruleset_manifest_id": _StartingEnvironment.ruleset.manifest_id,
            "objective_id": "terminal-victory-v1",
        },
        "collection_id",
    )
    (tmp_path / "prior.json").write_text(json.dumps(prior))
    body = {
        "schema_version": CONFIG_SCHEMA,
        "objective_id": "terminal-victory-v1",
        "historical_evidence_path": f"historical/{EVIDENCE_FILENAME}",
        "historical_report_id": historical["report_id"],
        "historical_config": source["config"].document,
        "collection_config": fresh,
        "prior_train_prefix_stop": 4,
        "prior_seed_sources": [
            {
                "path": "prior.json",
                "kind": "trajectory_preference_collection",
                "source_id": prior["collection_id"],
            }
        ],
        "analysis": {
            "matching_levels": list(LEVELS),
            "minimum_discovery_strict_runs": 1,
            "minimum_discovery_majority": 2 / 3,
            "minimum_confirmed_groups": 1,
            "minimum_confirmation_runs": 1,
            "minimum_strong_confirmation_runs": 1,
            "alpha": 0.05,
            "uncertainty_method": "independent_run_hoeffding_v1",
            "primary_level": "encoded_context",
            "primary_target": "strong",
            "stop_rule": "one_cohort_no_automatic_extension",
        },
        "resource_limits": {
            "wall_seconds": 1800,
            "cpu_seconds": 7200,
            "storage_bytes": 1000000000,
            "memory_bytes": 4000000000,
        },
    }
    config = StartingRepeatabilityConfig.from_mapping(_identified(body, "config_id"))
    return {"root": tmp_path, "package": source, "fresh_package": fresh_package, "config": config}


def _prepare(study: dict[str, Any]) -> Any:
    return prepare_starting_repeatability(
        config=study["config"],
        project_root=study["root"],
        split_manifest=study["package"]["split"],
        ruleset=_StartingEnvironment.ruleset,
        objective=load_objective(Path("configs/default.toml")),
    )


def _analyze(study: dict[str, Any], factory: Any = _StartingEnvironment) -> dict[str, Any]:
    directory = study["root"] / "output/evidence"
    _collect(directory, study["fresh_package"], factory=factory)
    report, cases = load_verified_starting_option_evidence(
        directory / EVIDENCE_FILENAME,
        config=study["config"].collection,
        split_manifest=study["package"]["split"],
        ruleset=_StartingEnvironment.ruleset,
    )
    return analyze_starting_repeatability(_prepare(study), report, cases)


def test_verified_end_to_end_no_replay_and_selection_never_fits(
    study: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _analyze(study)
    monkeypatch.setattr(_StartingEnvironment, "reset", lambda *a: pytest.fail("Analysis replayed"))
    inputs = _prepare(study)
    fresh, cases = load_verified_starting_option_evidence(
        study["root"] / "output/evidence" / EVIDENCE_FILENAME,
        config=study["config"].collection,
        split_manifest=study["package"]["split"],
        ruleset=_StartingEnvironment.ruleset,
    )
    assert analyze_starting_repeatability(inputs, fresh, cases) == report
    roles = report["complete_run_roles"]
    assert set(roles["historical_fit"]).isdisjoint(roles["excluded_historical_selection"])
    assert {r["run_seed"] for r in report["comparisons"] if r["role"] == "historical_fit"} == set(
        roles["historical_fit"]
    )
    assert report["collection_summary"]["candidate_denominator"] == 12
    assert report["historical_fitting_inventory"]["comparisons"] == 9
    assert (
        report["decision"]["status"] == "inconclusive"
    )  # Four games cannot give strong confidence.
    assert report["decision"]["automatic_training_allowed"] is False
    assert report["checkpoint_promoted"] is False and report["optimizer_steps"] == 0
    assert report["games_replayed_by_analysis"] == 0


def _row(seed: int, role: str, sign: int, menu: tuple[int, ...] = (11, 22, 33)) -> dict[str, Any]:
    ctx = manifest_identifier({"act": "overgrowth"})
    return {
        "run_seed": seed,
        "role": role,
        "option_pair": [11, 22],
        "ordered_menu": list(menu),
        "encoded_context_id": ctx,
        "full_menu_id": manifest_identifier({"ctx": ctx, "menu": sorted(menu)}),
        "exact_public_state_id": manifest_identifier({"ctx": ctx, "menu": list(menu)}),
        "strong_sign": sign,
        "all_eligible_sign": sign,
        "floor_sign": sign,
        "deciding_rank_component": "maximum_floor" if sign else None,
        "comparison_id": manifest_identifier({"seed": seed, "menu": menu}),
        "paired_rank_differences": {
            k: sign if k == "maximum_floor" else 0 for k in TRAJECTORY_SELECTION_RANK_ORDER
        },
    }


def test_opposing_floor_lessons_separate_full_menus_from_encoded_context(
    study: dict[str, Any],
) -> None:
    plan = study["config"].document["analysis"]
    rows = [_row(1, "discovery", 1), _row(2, "discovery", -1, (11, 22, 44))]
    encoded = _strata(rows, "encoded_context", plan)
    assert len(encoded) == 1 and encoded[0]["floor_direction_disagreement_in_discovery"] is True
    assert encoded[0]["discovery_targets"]["strong"]["direction"] is None
    assert len(_strata(rows, "full_menu", plan)) == 2
    ordered = [_row(1, "discovery", 1), _row(2, "discovery", -1, (33, 22, 11))]
    assert len(_strata(ordered, "full_menu", plan)) == 1  # ID sets, not execution positions.
    assert len(_strata(ordered, "exact_public_state", plan)) == 2


def test_confirmation_outcomes_cannot_change_discovery_targets(study: dict[str, Any]) -> None:
    plan = {**study["config"].document["analysis"], "minimum_discovery_strict_runs": 3}
    rows = [_row(i, "discovery", 1) for i in range(3)] + [
        _row(i, "confirmation", -1) for i in range(10, 20)
    ]
    groups = _strata(rows, "encoded_context", plan)
    assert groups[0]["discovery_targets"]["strong"]["direction"] == 1
    result = _confirmation(rows, groups, "encoded_context", "strong", plan)
    assert result["interval"]["mean_agreement"] == 0
    assert result["interval"]["independent_runs"] == 10
    assert all(r["discovery_direction"] == 1 for r in result["observations"])
    assert _direction(rows[:2], "strong", plan)["direction"] is None


def test_uncertainty_counts_whole_runs_and_retains_ties(study: dict[str, Any]) -> None:
    interval = _run_interval({1: [1, 1, 1], 2: [0]}, 0.05)
    assert interval["independent_runs"] == 2 and interval["mean_agreement"] == 0.5
    assert _run_interval({1: [1] * 9, 2: [0] * 3}, 0.05) == interval
    fifty = _run_interval({i: [1] for i in range(50)}, 0.05)
    assert fifty["interval"][0] == pytest.approx(1 - math.sqrt(math.log(40) / 100))
    plan = study["config"].document["analysis"]
    rows = [_row(1, "discovery", 1), _row(2, "confirmation", 0)]
    result = _confirmation(
        rows, _strata(rows, "encoded_context", plan), "encoded_context", "strong", plan
    )
    assert result["interval"]["mean_agreement"] == 0.5 and result["covered_strong_runs"] == 0


@pytest.mark.parametrize(
    "score,expected", [(1.0, "supported"), (0.0, "unsupported"), (0.5, "inconclusive")]
)
def test_frozen_decision_requires_uncertainty_and_strong_coverage(
    study: dict[str, Any],
    score: float,
    expected: str,
) -> None:
    plan = study["config"].document["analysis"]
    primary = {
        "confirmed_groups": 5,
        "covered_strong_runs": 50,
        "interval": _run_interval({i: [score] for i in range(50)}, 0.05),
    }
    assert _decision(primary, {"failed_runs": 0}, plan)["status"] == expected
    assert _decision(primary, {"failed_runs": 1}, plan)["status"] == "inconclusive"
    assert (
        _decision({**primary, "covered_strong_runs": 0}, {"failed_runs": 0}, plan)["status"]
        == "inconclusive"
    )


def test_victory_priority_over_floor_and_failed_cases_remain(study: dict[str, Any]) -> None:
    class Winning(_StartingEnvironment):
        victory_option = 2

    report = _analyze(study, Winning)
    pair = next(
        r
        for r in report["comparisons"]
        if r["role"] != "historical_fit" and r["option_pair"] == [22, 33]
    )
    assert pair["strong_sign"] == -1 and pair["floor_sign"] == 1
    assert pair["deciding_rank_component"] == "victory" and report["terminal_victories"] == 4


def test_failures_keep_all_configured_denominators(study: dict[str, Any]) -> None:
    class Failing(_StartingEnvironment):
        def step(self, action: Any) -> Any:
            raise RuntimeError("mock failure")

    report = _analyze(study, Failing)
    assert report["collection_summary"]["benchmark_denominator"] == 4
    assert report["collection_summary"]["candidate_denominator"] == 12
    assert report["collection_summary"]["failed_runs"] == 4
    assert not any(r["role"] != "historical_fit" for r in report["comparisons"])
    assert report["decision"]["status"] == "inconclusive"
    assert report["decision"]["coverage_checks"]["all_fresh_runs_terminal_and_complete"] is False


@pytest.mark.parametrize("alter", ["overlap", "source_id", "public_path", "objective"])
def test_preflight_rejects_source_and_ownership_changes(study: dict[str, Any], alter: str) -> None:
    doc = copy.deepcopy(study["config"].document)
    if alter == "overlap":
        prior = json.loads((study["root"] / "prior.json").read_text())
        prior["cases"].append({"run_seed": study["config"].collection.seeds[0]})
        prior = _identified(prior, "collection_id")
        (study["root"] / "prior.json").write_text(json.dumps(prior))
        doc["prior_seed_sources"][0]["source_id"] = prior["collection_id"]
    elif alter == "source_id":
        doc["prior_seed_sources"][0]["source_id"] = manifest_identifier({"wrong": "source"})
    elif alter == "public_path":
        doc["prior_seed_sources"][0]["path"] = "../outside.json"
    else:
        doc["objective_id"] = "floor-maximization"
    with pytest.raises(ValueError):
        study["config"] = StartingRepeatabilityConfig.from_mapping(_identified(doc, "config_id"))
        _prepare(study)


def test_pair_extraction_rejects_duplicates_and_reversed_menu_indices(
    study: dict[str, Any],
) -> None:
    inputs = _prepare(study)
    case = inputs.historical_cases[0]
    with pytest.raises(ValueError, match="duplicate"):
        _pair_rows([case, case], {case["run_seed"]: "discovery"})
    original = _pair_rows([case], {case["run_seed"]: "discovery"})
    assert [r["option_pair"] for r in original] == [[11, 22], [11, 33], [22, 33]]
    assert original[2]["strong_sign"] == 1


def test_cli_saved_collection_analyzes_without_backend_and_cached_show_no_sources(
    study: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _collect(study["root"] / "output/evidence", study["fresh_package"])
    path = study["root"] / "config.json"
    path.write_text(json.dumps(study["config"].document))
    monkeypatch.setattr(
        "spireshift.cli.load_patch_manifest",
        lambda _: SimpleNamespace(ruleset_identity=lambda: _StartingEnvironment.ruleset),
    )
    monkeypatch.setattr(
        "spireshift.cli.load_evangambit_backend", lambda *a, **k: pytest.fail("Backend loaded")
    )
    monkeypatch.setattr(
        "spireshift.cli.load_production_model_checkpoint",
        lambda _: {"model_id": study["config"].collection.runner.model_id},
    )
    monkeypatch.setattr(
        "spireshift.cli.load_production_training_report",
        lambda *a, **k: {"report_id": study["config"].collection.runner.training_report_id},
    )
    args = [
        "model",
        "study-starting-repeatability",
        str(path),
        "unused-checkpoint",
        "--report",
        "unused-report",
        "--split-manifest",
        "manifests/splits/mock-v1-seeds-000000-000999-v1.json",
        "--upstream-root",
        "unused-upstream",
        "--manifest",
        "unused-manifest",
        "--project-root",
        str(study["root"]),
        "--output-dir",
        str(study["root"] / "output"),
        "--resume",
    ]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["source_integrity_verified"] is True
    study_path = study["root"] / "output" / FILENAME
    raw = study_path.read_bytes()
    assert main(args) == 1 and study_path.read_bytes() == raw
    capsys.readouterr()
    monkeypatch.setattr(
        "spireshift.cli.prepare_starting_repeatability",
        lambda **k: pytest.fail("Sources reaudited"),
    )
    assert (
        main(["model", "show-starting-repeatability", str(study_path), "--config", str(path)]) == 0
    )
    assert json.loads(capsys.readouterr().out)["source_inputs_reaudited"] is False
    changed = json.loads(raw)
    changed["decision"]["status"] = "supported"
    changed = _identified(changed, "report_id")
    study_path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="decision"):
        load_starting_repeatability_report(study_path, study["config"])


def test_config_and_report_schemas_and_production_seed_window(study: dict[str, Any]) -> None:
    docs = [json.loads(p.read_text()) for p in Path("schemas").glob("*.json")]
    registry = Registry().with_resources((d["$id"], Resource.from_contents(d)) for d in docs)
    report = _analyze(study)
    production = load_starting_repeatability_config(
        Path("configs/starting-repeatability/sts2-v0.107.1-base-v2-train-v1.json")
    )
    for name, doc in [
        (CONFIG_SCHEMA, study["config"].document),
        (CONFIG_SCHEMA, production.document),
        (REPORT_SCHEMA, report),
    ]:
        schema = json.loads((Path("schemas") / f"{name}.json").read_text())
        Draft202012Validator(schema, registry=registry).validate(doc)
    assert (
        len(production.collection.seeds) == 192 and production.collection.runner.run_offset == 312
    )
    assert len(production.collection.document["complete_run_subfolds"]["selection"]) == 48
    assert production.document["analysis"]["minimum_discovery_strict_runs"] == 3
    assert production.document["analysis"]["minimum_strong_confirmation_runs"] == 12
    assert production.collection.seeds[0] == 389


def test_owner_script_resumes_missing_work_and_completed_rerun_only_displays(
    tmp_path: Path,
) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    script = scripts / "study-starting-repeatability-v1.sh"
    script.write_text(Path("scripts/study-starting-repeatability-v1.sh").read_text())
    binary = tmp_path / "bin"
    binary.mkdir()
    uv = binary / "uv"
    uv.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@"\n')
    uv.chmod(0o755)
    env = {**os.environ, "PATH": str(binary) + os.pathsep + os.environ["PATH"]}
    resources = tmp_path / "artifacts/resources"
    resources.mkdir(parents=True)
    old = resources / "starting-repeatability-base-v2-train-v1-attempt-1.json"
    old.write_text("{}")
    first = subprocess.run(
        ["bash", str(script)], env=env, capture_output=True, text=True, check=True
    )
    assert "attempt-2.json" in first.stdout and "--resume" in first.stdout
    assert (
        "study-starting-repeatability" in first.stdout
        and "--max-wall-seconds\n1800" in first.stdout
    )
    assert "train-curriculum" not in first.stdout and "finetune" not in first.stdout
    output = tmp_path / "artifacts/repeatability/sts2-v0.107.1-base-v2-train-v1"
    output.mkdir(parents=True)
    (output / FILENAME).write_text("{}")
    second = subprocess.run(
        ["bash", str(script)], env=env, capture_output=True, text=True, check=True
    )
    assert "show-starting-repeatability" in second.stdout and "resources" not in second.stdout
    assert old.read_text() == "{}"


def test_cli_resumes_only_missing_cases_and_counts_new_work(
    study: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def interrupted(done: int, total: int) -> None:
        raise RuntimeError("toy interruption")

    directory = study["root"] / "output/evidence"
    with pytest.raises(RuntimeError, match="toy interruption"):
        _collect(directory, study["fresh_package"], progress=interrupted)
    saved = list((directory / "cases").glob("*.json"))
    assert len(saved) == 1
    saved_bytes = saved[0].read_bytes()
    saved_seed = json.loads(saved_bytes)["run_seed"]
    resets = []

    class Resumed(_StartingEnvironment):
        def reset(self, seed: int) -> Observation:
            resets.append(seed)
            return super().reset(seed)

    path = study["root"] / "config.json"
    path.write_text(json.dumps(study["config"].document))
    monkeypatch.setattr(
        "spireshift.cli.load_patch_manifest",
        lambda _: SimpleNamespace(ruleset_identity=lambda: Resumed.ruleset),
    )
    monkeypatch.setattr(
        "spireshift.cli.load_production_model_checkpoint",
        lambda _: {"model_id": study["config"].collection.runner.model_id},
    )
    monkeypatch.setattr(
        "spireshift.cli.load_production_training_report",
        lambda *a, **k: {"report_id": study["config"].collection.runner.training_report_id},
    )
    monkeypatch.setattr(
        "spireshift.cli.ProductionCheckpointPolicy", lambda **k: study["package"]["policy"]
    )
    monkeypatch.setattr(
        "spireshift.cli.load_evangambit_backend", lambda *a, **k: SimpleNamespace(factory=Resumed)
    )
    metrics: list[ExperimentMetrics] = []
    monkeypatch.setattr("spireshift.cli.write_experiment_metrics", metrics.append)
    assert (
        main(
            [
                "model",
                "study-starting-repeatability",
                str(path),
                "unused-checkpoint",
                "--report",
                "unused-report",
                "--split-manifest",
                "manifests/splits/mock-v1-seeds-000000-000999-v1.json",
                "--upstream-root",
                "unused",
                "--manifest",
                "unused",
                "--project-root",
                str(study["root"]),
                "--output-dir",
                str(study["root"] / "output"),
                "--resume",
            ]
        )
        == 0
    )
    assert saved_seed not in resets and saved[0].read_bytes() == saved_bytes
    assert set(resets) == set(study["config"].collection.seeds) - {saved_seed}
    assert metrics[0].trajectories == 9 and metrics[0].transitions == 18
    output = capsys.readouterr().out
    assert json.loads(output[output.index("{") :])["completed_runs"] == 4


def test_real_pair_extraction_uses_option_identity_after_menu_permutation(
    study: dict[str, Any],
) -> None:
    class Permuted(_StartingEnvironment):
        def observe(self) -> Observation:
            observed = super().observe()
            public = {
                **observed.public_state,
                "neow_options": [33, 22, 11] if self.seed % 2 else [11, 22, 33],
            }
            return Observation(
                observed.schema_version,
                observed.patch_id,
                observed.decision_type,
                public,
                manifest_identifier(public).removeprefix("sha256:"),
            )

    report = _analyze(study, Permuted)
    pairs = [
        r
        for r in report["comparisons"]
        if r["role"] != "historical_fit" and r["option_pair"] == [11, 33]
    ]
    assert len(pairs) == 4
    for row in pairs:
        assert row["strong_sign"] == (1 if row["run_seed"] % 2 else -1)
        assert row["paired_rank_differences"]["maximum_floor"] == (2 if row["run_seed"] % 2 else -2)
