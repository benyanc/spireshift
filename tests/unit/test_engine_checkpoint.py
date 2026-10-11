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
