"""Portable provenance gates; actual native rest cases remain private evidence."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_cli_probe import verify_local_build_report, verify_projection_inputs
from spireshift.engine_qualification import (
    EngineQualificationConfig,
    _inventory,
    _sha_file,
    load_engine_qualification_config,
)


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


def projection_inputs(tmp_path: Path) -> tuple[EngineQualificationConfig, dict[str, Any]]:
    """Synthetic MIT files only; never fabricate game qualification evidence."""
    qualification = EngineQualificationConfig(
        document={
            "sources": [{"name": "headless", "commit": "test-source", "path": "artifacts/source"}]
        },
        root=tmp_path,
    )
    files = {
        "artifacts/source/src/managed-player-environment.mjs": "synthetic projection",
        "patches/engine/sts2-headless-player-projection-v1.patch": "synthetic patch",
        "scripts/engine-player-projection.mjs": "synthetic loader",
        "scripts/engine-rest-surface.mjs": "synthetic public surface",
        "scripts/probe-engine-cli-rest.mjs": "synthetic native panel",
        "artifacts/sdk/SDK.js": "synthetic SDK",
    }
    for name, content in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    pins = {
        "source_revision": "test-source",
        "source_sha256": _sha_file(tmp_path / next(iter(files))),
        "patch_sha256": _sha_file(
            tmp_path / "patches/engine/sts2-headless-player-projection-v1.patch"
        ),
        "patched_source_sha256": "synthetic-patched-module",
        "node_modules": "artifacts/sdk",
        "sdk_inventory_id": manifest_identifier({"files": _inventory(tmp_path / "artifacts/sdk")}),
        "helpers_sha256": {
            name: _sha_file(tmp_path / "scripts" / name)
            for name in (
                "engine-player-projection.mjs",
                "engine-rest-surface.mjs",
                "probe-engine-cli-rest.mjs",
            )
        },
    }
    return qualification, {"projection": pins}


def test_projection_dependencies_bind_without_proprietary_files(tmp_path: Path) -> None:
    qualification, document = projection_inputs(tmp_path)
    resolved, inventory = verify_projection_inputs(qualification, document)
    assert resolved["source_revision"] == "test-source"
    assert resolved["node_modules"] == str(tmp_path / "artifacts/sdk")
    assert len(inventory) == 1


@pytest.mark.parametrize(
    "name",
    [
        "artifacts/source/src/managed-player-environment.mjs",
        "patches/engine/sts2-headless-player-projection-v1.patch",
        "scripts/engine-player-projection.mjs",
        "scripts/engine-rest-surface.mjs",
        "scripts/probe-engine-cli-rest.mjs",
        "artifacts/sdk/SDK.js",
    ],
)
def test_any_changed_projection_dependency_is_refused(tmp_path: Path, name: str) -> None:
    qualification, document = projection_inputs(tmp_path)
    (tmp_path / name).write_text("different bytes")
    with pytest.raises(ValueError, match="changed"):
        verify_projection_inputs(qualification, document)


def test_projection_cannot_substitute_another_headless_revision(tmp_path: Path) -> None:
    qualification, document = projection_inputs(tmp_path)
    document["projection"]["source_revision"] = "another-source"
    with pytest.raises(ValueError, match="pinned Headless revision"):
        verify_projection_inputs(qualification, document)
