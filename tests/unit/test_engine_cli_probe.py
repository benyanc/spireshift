"""Portable provenance gates; actual native rest cases remain private evidence."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_cli_probe import (
    verify_local_build_report,
    verify_probe_runtime,
    verify_projection_inputs,
)
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


@pytest.mark.parametrize(
    "dependency", ["engine-selection-shop-surface.mjs", "probe-engine-cli-shop.mjs"]
)
def test_new_interaction_revision_cannot_omit_its_extra_dependencies(
    tmp_path: Path, dependency: str
) -> None:
    qualification, document = projection_inputs(tmp_path)
    document["public_projection_revision"] = "selection_shop_v2"
    for name in ["engine-selection-shop-surface.mjs", "probe-engine-cli-shop.mjs"]:
        file = tmp_path / "scripts" / name
        file.write_text("synthetic new dependency")
        document["projection"]["helpers_sha256"][name] = _sha_file(file)
    document["projection"]["helpers_sha256"].pop(dependency)
    with pytest.raises(ValueError, match="dependency changed"):
        verify_projection_inputs(qualification, document)


def test_unknown_interaction_revision_is_not_treated_as_the_old_projection(tmp_path: Path) -> None:
    qualification, document = projection_inputs(tmp_path)
    document["public_projection_revision"] = "future-unverified"
    with pytest.raises(ValueError, match="Unknown public interaction"):
        verify_projection_inputs(qualification, document)


def combat_projection_inputs(tmp_path: Path) -> tuple[EngineQualificationConfig, dict[str, Any]]:
    qualification, document = projection_inputs(tmp_path)
    document["public_projection_revision"] = "combat_v4"
    patch = tmp_path / "patches/engine/sts2-headless-player-projection-v2.patch"
    patch.write_text("synthetic unordered read hook")
    document["projection"]["patch_sha256"] = _sha_file(patch)
    for name in [
        "engine-selection-shop-surface.mjs",
        "probe-engine-cli-shop.mjs",
        "engine-combat-surface.mjs",
        "probe-engine-cli-combat.mjs",
    ]:
        file = tmp_path / "scripts" / name
        file.write_text("synthetic " + name)
        document["projection"]["helpers_sha256"][name] = _sha_file(file)
    return qualification, document


def test_combat_inputs_require_the_bound_unordered_read_hook(tmp_path: Path) -> None:
    qualification, document = combat_projection_inputs(tmp_path)
    resolved, _ = verify_projection_inputs(qualification, document)
    assert resolved["patch"].endswith("player-projection-v2.patch")
    document["projection"]["patch_sha256"] = _sha_file(
        tmp_path / "patches/engine/sts2-headless-player-projection-v1.patch"
    )
    with pytest.raises(ValueError, match="hook patch changed"):
        verify_projection_inputs(qualification, document)


@pytest.mark.parametrize("dependency", ["engine-combat-surface.mjs", "probe-engine-cli-combat.mjs"])
def test_combat_helper_changes_or_missing_pins_are_refused(tmp_path: Path, dependency: str) -> None:
    qualification, document = combat_projection_inputs(tmp_path)
    document["projection"]["helpers_sha256"].pop(dependency)
    with pytest.raises(ValueError, match="dependency changed"):
        verify_projection_inputs(qualification, document)


def test_managed_runtime_is_bound_separately_from_the_build_sdk(tmp_path: Path) -> None:
    qualification, _ = projection_inputs(tmp_path)
    runtime = tmp_path / "artifacts/runtime"
    runtime.mkdir()
    (runtime / "dotnet").write_text("synthetic executable")
    (runtime / "CoreLib.dll").write_text("synthetic dependency")
    document: dict[str, Any] = {
        "managed_runtime_version": "9.0.7",
        "managed_runtime": {
            "directory": "artifacts/runtime",
            "version": "9.0.7",
            "roll_forward": "LatestPatch",
            "inventory_id": manifest_identifier({"files": _inventory(runtime)}),
            "dotnet_sha256": _sha_file(runtime / "dotnet"),
        },
    }
    path, inventory = verify_probe_runtime(qualification, document)
    assert path == runtime
    assert inventory is not None and len(inventory) == 2
    (runtime / "CoreLib.dll").write_text("another runtime")
    with pytest.raises(ValueError, match="runtime files changed"):
        verify_probe_runtime(qualification, document)


@pytest.mark.parametrize("field", ["version", "roll_forward"])
def test_runtime_substitution_or_roll_forward_drift_is_refused(tmp_path: Path, field: str) -> None:
    qualification, _ = projection_inputs(tmp_path)
    document: dict[str, Any] = {
        "managed_runtime_version": "9.0.7",
        "managed_runtime": {"version": "9.0.7", "roll_forward": "LatestPatch"},
    }
    document["managed_runtime"][field] = "unqualified"
    with pytest.raises(ValueError, match="game-matching managed runtime"):
        verify_probe_runtime(qualification, document)
