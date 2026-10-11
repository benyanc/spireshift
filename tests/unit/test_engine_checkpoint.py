"""Saved input identity and startup batch boundaries, with no real game launches."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from spireshift import engine_starting_bridges as bridges
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_checkpoint import verify_checkpoint_input
from spireshift.engine_connector import _evaluate_connector_checkpoint
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file


def checkpoint_fixture(
    tmp_path: Path,
) -> tuple[EngineQualificationConfig, dict[str, Any], dict[str, Any], Path]:
    qualification = EngineQualificationConfig({"test": "qualification"}, tmp_path)
    attempt = tmp_path / "artifacts/native/attempt"
    attempt.mkdir(parents=True)
    save = attempt / "native-checkpoint.save"
    save.write_text("private synthetic native save")
    snapshot = attempt / "private-starting-snapshot.json"
    snapshot.write_text("{}")
    report_path = attempt / "report.json"
    report = {
        "schema_version": "engine-cli-checkpoint-projection-probe-v1",
        "qualification_config_id": qualification.config_id,
        "status": "checkpoint_public_projection_regression_pass",
        "checks": {
            "frozen_archive_unchanged": True,
            "native_checkpoint_regressions_pass": True,
            "pinned_managed_runtime_unchanged": True,
            "pinned_sdk_tree_unchanged": True,
            "projection_identity_bound": True,
            "same_private_candidate_unchanged": True,
            "shared_profile_unchanged": True,
            "uncapped_successful_process": True,
        },
        "training_allowed": False,
        "probe": {
            "checkpoint": {
                "path": str(save),
                "sha256": _sha_file(save),
                "ascension": 8,
                "content_policy": "native_all_unlocked",
                "seed": "SYNTHETICSEED",
            }
        },
    }
    report["report_id"] = manifest_identifier(report)
    report["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report))
    config = {
        "checkpoint_report": str(report_path.relative_to(tmp_path)),
        "checkpoint_report_id": report["report_id"],
        "seed": "SYNTHETICSEED",
        "snapshot_sha256": _sha_file(snapshot),
    }
    return qualification, config, report, report_path


def test_bound_native_save_and_snapshot_can_be_read_without_launching(tmp_path: Path) -> None:
    qualification, config, _, report_path = checkpoint_fixture(tmp_path)
    result = verify_checkpoint_input(qualification, config)
    assert result["seed"] == "SYNTHETICSEED"
    assert Path(result["checkpoint_path"]).parent == report_path.parent


@pytest.mark.parametrize("changed", ["report", "save", "snapshot"])
def test_changed_saved_evidence_is_rejected_before_shipped_launch(
    tmp_path: Path, changed: str
) -> None:
    qualification, config, report, report_path = checkpoint_fixture(tmp_path)
    if changed == "report":
        report["status"] = "checkpoint_public_projection_regression_incomplete"
        report_path.write_text(json.dumps(report))
    else:
        file = "native-checkpoint.save" if changed == "save" else "private-starting-snapshot.json"
        (report_path.parent / file).write_text("changed bytes")
    with pytest.raises(ValueError):
        verify_checkpoint_input(qualification, config)


@pytest.mark.parametrize(
    "gap", ["training", "ascension", "seed", "checks", "missing_gate", "outside"]
)
def test_rehashed_but_wrong_scope_cannot_admit_a_checkpoint(tmp_path: Path, gap: str) -> None:
    qualification, config, report, report_path = checkpoint_fixture(tmp_path)
    if gap == "training":
        report["training_allowed"] = True
    elif gap == "checks":
        report["checks"] = {}
    elif gap == "missing_gate":
        del report["checks"]["uncapped_successful_process"]
    else:
        checkpoint = report["probe"]["checkpoint"]
        if gap == "outside":
            outside = tmp_path / "outside.save"
            outside.write_text("outside")
            checkpoint.update(path=str(outside), sha256=_sha_file(outside))
        elif gap == "ascension":
            checkpoint["ascension"] = 0
        else:
            checkpoint["seed"] = "OTHERSEED"
    report["report_id"] = manifest_identifier(
        {key: value for key, value in report.items() if key not in {"report_id", "report_path"}}
    )
    config["checkpoint_report_id"] = report["report_id"]
    report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError):
        verify_checkpoint_input(qualification, config)


def named_cases() -> list[dict[str, str]]:
    return [
        {"case_id": f"seed-{seed}-repeat-{repeat}", "seed": f"SYNTHETIC{seed}"}
        for repeat in (1, 2)
        for seed in range(6)
    ]


def test_repeated_startups_are_six_independent_seeds_not_twelve() -> None:
    cases = named_cases()
    assert bridges.validate_bridge_cases({"cases": cases}) == cases
    assert len({case["seed"] for case in cases}) == 6


@pytest.mark.parametrize("gap", ["fewer", "duplicate_id", "one_seed", "bad_seed", "numeric_seed"])
def test_incomplete_or_misleading_batch_is_refused(gap: str) -> None:
    cases: list[Any] = copy.deepcopy(named_cases())
    if gap == "fewer":
        cases.pop()
    elif gap == "duplicate_id":
        cases[1]["case_id"] = cases[0]["case_id"]
    elif gap == "one_seed":
        for case in cases:
            case["seed"] = "ONESEED"
    elif gap == "bad_seed":
        cases[0]["seed"] = "../bad-seed"
    else:
        cases[0]["seed"] = 123
    with pytest.raises(ValueError):
        bridges.validate_bridge_cases({"cases": cases})


def batch_fixture(tmp_path: Path) -> tuple[EngineQualificationConfig, Path]:
    qualification = EngineQualificationConfig({"test": "qualification"}, tmp_path)
    directory = tmp_path / "configs/engine-qualification"
    directory.mkdir(parents=True)
    document: dict[str, Any] = {
        "schema_version": "engine-starting-bridges-config-v1",
        "stage": "owner_native_shipped_starting_inputs_only",
        "qualification_config_id": qualification.config_id,
        "training_allowed": False,
        "max_wall_seconds": 900,
        "successful_payload_policy": "remove_after_verified_success",
        "workspace": "artifacts/startup-batch",
        "cases": named_cases(),
    }
    for role in ("native", "shipped"):
        template = directory / f"{role}.json"
        body = {"test": role, "seed": "ORIGINAL"}
        template.write_text(json.dumps(body))
        document[f"{role}_template"] = str(template.relative_to(tmp_path))
        document[f"{role}_template_id"] = manifest_identifier(body)
    path = directory / "batch.json"
    path.write_text(json.dumps(document))
    return qualification, path


def test_template_drift_is_refused_before_any_native_job(tmp_path: Path) -> None:
    qualification, path = batch_fixture(tmp_path)
    path.with_name("native.json").write_text('{"changed":true}')
    with pytest.raises(ValueError, match="templates changed"):
        bridges.load_starting_bridge_config(qualification, path)
    assert not (tmp_path / "artifacts/startup-batch").exists()


def complete_saved_batch(tmp_path: Path) -> tuple[EngineQualificationConfig, Path, Path]:
    qualification, path = batch_fixture(tmp_path)
    document, planned, templates = bridges.load_starting_bridge_config(qualification, path)
    batch: dict[str, Any] = {
        "schema_version": "engine-starting-bridges-v1",
        "config_id": manifest_identifier(document),
        "qualification_config_id": qualification.config_id,
        "status": "starting_input_comparisons_pass",
        "cases": [],
        "planned_cases": 12,
        "completed_cases": 12,
        "failed_cases": 0,
        "not_attempted_cases": 0,
        "independent_seeds": 6,
        "training_allowed": False,
        "shipped_cross_host_parity": False,
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "repeated_seed_choices_identical": True,
    }
    workspace = tmp_path / document["workspace"]
    for case in planned:
        directory = workspace / case["case_id"]
        _, _, native, _ = checkpoint_fixture(directory)
        attempt = directory / "artifacts/native/attempt"
        snapshot = attempt / "private-starting-snapshot.json"
        options = [{"title": "Synthetic reward", "is_locked": False}]
        snapshot.write_text(
            json.dumps({"interaction": {"content": {"surface": {"options": options}}}})
        )
        config = copy.deepcopy(templates["native"][1])
        config.update(
            seed=case["seed"], workspace=str((directory / "native").relative_to(tmp_path))
        )
        native.update(
            config_id=manifest_identifier(config), qualification_config_id=qualification.config_id
        )
        native["probe"]["checkpoint"]["seed"] = case["seed"]
        native["report_id"] = manifest_identifier(
            {k: v for k, v in native.items() if k not in {"report_id", "report_path"}}
        )
        native_path = directory / "native-report.json"
        native_path.write_text(json.dumps(native))
        shipped_config = copy.deepcopy(templates["shipped"][1])
        shipped_config.update(
            seed=case["seed"],
            checkpoint_report=str(native_path.relative_to(tmp_path)),
            checkpoint_report_id=native["report_id"],
            snapshot_sha256=_sha_file(snapshot),
            workspace=str((directory / "shipped").relative_to(tmp_path)),
            successful_payload_policy="remove_after_verified_success",
        )
        check_names = (
            "loaded_identity",
            "endpoint_owned_by_child",
            "native_continue_offered",
            "native_checkpoint_loaded",
            "complete_public_starting_event",
            "native_A8_seed_preserved",
            "same_starting_public_option_titles_and_availability",
            "profile_path_logged",
            "steam_disabled_observed",
            "shared_profile_unchanged",
            "working_game_unchanged",
            "archive_still_valid",
            "template_unchanged",
            "natural_shutdown",
        )
        shipped: dict[str, Any] = {
            "probe": {"starting_options_comparison": {"managed": options, "shipped": options}},
            "checks": dict.fromkeys(check_names, True),
            "verdict": {"status": "shipped_checkpoint_input_pass", "errors": []},
            "qualification_config_id": qualification.config_id,
            "training_allowed": False,
            "disposable_payload_removed_after_verified_success": True,
        }
        original = directory / "shipped/attempt/report.json"
        original.parent.mkdir(parents=True)
        original.write_text(
            json.dumps(
                {**shipped, "report_id": manifest_identifier(shipped), "report_path": str(original)}
            )
        )
        shipped.update(
            checkpoint_config_id=manifest_identifier(shipped_config),
            checkpoint_report_id=native["report_id"],
            checkpoint_sha256=native["probe"]["checkpoint"]["sha256"],
            private_shipped_report_path=str(original),
        )
        shipped["report_id"] = manifest_identifier(shipped)
        shipped_path = directory / "shipped-report.json"
        shipped_path.write_text(json.dumps(shipped))
        batch["cases"].append(
            {
                **case,
                "native_report": str(native_path.relative_to(tmp_path)),
                "native_report_id": native["report_id"],
                "shipped_report": str(shipped_path.relative_to(tmp_path)),
                "shipped_report_id": shipped["report_id"],
                "starting_options": shipped["probe"]["starting_options_comparison"],
                "status": "shipped_checkpoint_input_pass",
                "disposable_payload_removed_after_verified_success": True,
            }
        )
    batch["report_id"] = manifest_identifier(batch)
    batch_path = workspace / "batch.json"
    batch_path.write_text(json.dumps(batch))
    return qualification, path, batch_path


def test_saved_complete_batch_verification_launches_nothing(tmp_path: Path) -> None:
    qualification, path, _ = complete_saved_batch(tmp_path)
    result = bridges.verify_starting_bridges(qualification, path)
    assert result["verified_cases"] == 12
    assert result["independent_seeds"] == 6
    assert result["games_launched"] == 0
    assert result["training_allowed"] is False


@pytest.mark.parametrize(
    "gap",
    [
        "missing_case",
        "reordered_case",
        "changed_report",
        "changed_snapshot",
        "claimed_cleanup",
        "wrong_options",
        "promotion",
    ],
)
def test_saved_success_cannot_hide_a_changed_case_or_scope(tmp_path: Path, gap: str) -> None:
    qualification, path, batch_path = complete_saved_batch(tmp_path)
    batch = json.loads(batch_path.read_text())
    case = batch["cases"][0]
    if gap == "missing_case":
        batch["cases"].pop()
    elif gap == "reordered_case":
        batch["cases"].reverse()
    elif gap == "changed_report":
        (tmp_path / case["shipped_report"]).write_text("{}")
    elif gap == "changed_snapshot":
        native = json.loads((tmp_path / case["native_report"]).read_text())
        (Path(native["report_path"]).parent / "private-starting-snapshot.json").write_text("{}")
    elif gap == "claimed_cleanup":
        shipped = json.loads((tmp_path / case["shipped_report"]).read_text())
        (Path(shipped["private_shipped_report_path"]).parent / "game").mkdir()
    elif gap == "wrong_options":
        case["starting_options"]["shipped"][0]["title"] = "Different choice"
    else:
        batch["training_allowed"] = True
    batch["report_id"] = manifest_identifier({k: v for k, v in batch.items() if k != "report_id"})
    batch_path.write_text(json.dumps(batch))
    with pytest.raises((ValueError, KeyError)):
        bridges.verify_starting_bridges(qualification, path)


def test_startup_pass_cannot_admit_an_uncompared_combat_prefix() -> None:
    checks = dict.fromkeys(
        (
            "loaded_identity",
            "endpoint_owned_by_child",
            "native_continue_offered",
            "native_checkpoint_loaded",
            "complete_public_starting_event",
            "native_A8_seed_preserved",
            "same_starting_public_option_titles_and_availability",
            "profile_path_logged",
            "steam_disabled_observed",
            "shared_profile_unchanged",
            "working_game_unchanged",
            "archive_still_valid",
            "template_unchanged",
            "natural_shutdown",
        ),
        True,
    )
    assert _evaluate_connector_checkpoint(checks)["errors"] == []
    assert len(_evaluate_connector_checkpoint(checks, journey=True)["errors"]) == 3


def test_failed_native_startup_remains_in_denominator_and_stops_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    qualification, path = batch_fixture(tmp_path)
    jobs = []

    def failed_native(*args: Any, **kwargs: Any) -> dict[str, Any]:
        jobs.append(args[3]["seed"])
        return {"status": "checkpoint_public_projection_regression_incomplete"}

    monkeypatch.setattr(bridges, "_probe_cli_document", failed_native)
    monkeypatch.setattr(
        "spireshift.engine_starting_bridges.shutil.disk_usage",
        lambda _: SimpleNamespace(free=5_000_000_000),
    )
    result = bridges.run_starting_bridges(qualification, path, node=Path("synthetic-node"))
    assert jobs == ["SYNTHETIC0"]
    assert result["status"] == "starting_input_comparisons_incomplete"
    assert (result["completed_cases"], result["failed_cases"], result["not_attempted_cases"]) == (
        0,
        1,
        11,
    )
    assert result["full_run_attempts"] == result["optimizer_steps"] == 0
    assert result["training_allowed"] is False
    assert (tmp_path / "artifacts/startup-batch/seed-0-repeat-1/native-report.json").is_file()
    with pytest.raises(FileExistsError, match="Preserve this batch"):
        bridges.run_starting_bridges(qualification, path, node=Path("synthetic-node"))
    assert len(jobs) == 1
