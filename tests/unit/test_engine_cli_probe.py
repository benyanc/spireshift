"""Portable provenance gates; actual native rest cases remain private evidence."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_cli_probe import verify_local_build_report
from spireshift.engine_qualification import load_engine_qualification_config


def build_result() -> tuple[dict[str, Any], dict[str, Any]]:
    config = json.loads(
        Path("configs/engine-qualification/sts2-v0.111.0-cli-build-rest-v2.json").read_text()
    )
    body = {
        "schema_version": "engine-cli-build-v2",
        "status": "candidate_built_unqualified",
        "config_id": manifest_identifier(config),
        "qualification_config_id": config["qualification_config_id"],
        "training_allowed": False,
        "process": {"returncode": 0, "timed_out": False},
        "build": {"repaired": [copy.deepcopy(config["expected_repaired"]) for _ in range(2)]},
    }
    return {**body, "report_id": manifest_identifier(body)}, config


def qualification_config() -> Any:
    return load_engine_qualification_config(
        Path("configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json").resolve()
    )


def reseal(body: dict[str, Any]) -> None:
    body.pop("report_id")
    body["report_id"] = manifest_identifier(body)


def test_exact_local_build_is_returned_without_game_files() -> None:
    report, config = build_result()
    actual = verify_local_build_report(report, config, qualification_config())
    assert actual == config["expected_repaired"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "engine-cli-build-v1"),
        ("status", "candidate_build_incomplete"),
        ("config_id", "another-compiler-config"),
        ("qualification_config_id", "another-game"),
        ("training_allowed", True),
        ("process", {"returncode": 1, "timed_out": False}),
        ("process", {"returncode": 0, "timed_out": True}),
    ],
)
def test_self_consistent_but_ineligible_report_is_refused(field: str, value: Any) -> None:
    report, config = build_result()
    report[field] = value
    reseal(report)
    with pytest.raises(ValueError, match="verified exact local"):
        verify_local_build_report(report, config, qualification_config())


def test_modified_report_cannot_reuse_its_saved_success_digest() -> None:
    report, config = build_result()
    report["build"]["repaired"][0]["artifact_sha256"] = "changed"
    with pytest.raises(ValueError, match="verified exact local"):
        verify_local_build_report(report, config, qualification_config())


@pytest.mark.parametrize("index", [0, 1])
def test_either_build_drifting_is_refused_after_resealing(index: int) -> None:
    report, config = build_result()
    report["build"]["repaired"][index]["godot_stub_sha256"] = "another-stub"
    reseal(report)
    with pytest.raises(ValueError, match="frozen local pins"):
        verify_local_build_report(report, config, qualification_config())


def test_single_build_cannot_claim_reproducibility() -> None:
    report, config = build_result()
    report["build"]["repaired"].pop()
    reseal(report)
    with pytest.raises(ValueError, match="two matching fresh builds"):
        verify_local_build_report(report, config, qualification_config())
