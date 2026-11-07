"""A patched Host must not inherit the original release's trust or artifact identity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from spireshift import engine_connector as connector
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_native import NativeQualificationConfig
from spireshift.engine_qualification import EngineQualificationConfig, _inventory, _sha_file


def saved_local_tools(tmp_path: Path) -> connector.ConnectorQualificationConfig:
    q = EngineQualificationConfig({"qualification": "synthetic"}, tmp_path)
    root = tmp_path / "artifacts/tools"
    (root / "release/payload").mkdir(parents=True)
    artifact = root / "release/payload/STS2_MCP.dll"
    artifact.write_bytes(b"synthetic local assembly")
    patch = tmp_path / "patches/engine/scoped.patch"
    patch.parent.mkdir(parents=True)
    patch.write_text("synthetic source patch")
    recipe: dict[str, Any] = {"patch": "patches/engine/scoped.patch"}
    recipe_path = tmp_path / "configs/engine-qualification/build.json"
    recipe_path.parent.mkdir(parents=True)
    recipe_path.write_text(json.dumps(recipe))
    identity = {
        "source_revision": "a" * 40,
        "artifact_sha256": _sha_file(artifact),
        "artifact_mvid": "b" * 36,
    }
    built = {
        "status": "local_connector_built_unqualified",
        "qualification_config_id": q.config_id,
        "config_id": manifest_identifier(recipe),
        "source_revision": identity["source_revision"],
        "patch_sha256": _sha_file(patch),
        "fresh_builds": [
            {"sha256": identity["artifact_sha256"], "module_version_id": identity["artifact_mvid"]}
        ]
        * 2,
    }
    built["report_id"] = manifest_identifier(built)
    (tmp_path / "artifacts/build.json").write_text(json.dumps(built))
    value = {
        "toolchain": "artifacts/tools",
        "connector": identity,
        "local_build": {
            "build_config": "configs/engine-qualification/build.json",
            "build_config_id": manifest_identifier(recipe),
            "build_report": "artifacts/build.json",
        },
    }
    config = connector.ConnectorQualificationConfig(value, NativeQualificationConfig({}, q))
    ledger = {
        "config_id": config.config_id,
        "local_build_report": "artifacts/build.json",
        "local_build_report_id": built["report_id"],
        "inventory": _inventory(root),
    }
    ledger["report_id"] = manifest_identifier(ledger)
    (root / "toolchain.json").write_text(json.dumps(ledger))
    return config


def refresh_tool_ledger(config: connector.ConnectorQualificationConfig) -> None:
    root = config.private("toolchain")
    path = root / "toolchain.json"
    ledger = json.loads(path.read_text())
    ledger.pop("report_id")
    ledger["inventory"] = [row for row in _inventory(root) if row["path"] != "toolchain.json"]
    ledger["report_id"] = manifest_identifier(ledger)
    path.write_text(json.dumps(ledger))


@pytest.mark.parametrize("change", ["upstream_seal", "binary", "patch", "different_repeat"])
def test_local_identity_cannot_be_replaced_by_rehashed_inventory(
    tmp_path: Path, change: str
) -> None:
    config = saved_local_tools(tmp_path)
    connector._verify_toolchain(config)
    root = config.private("toolchain")
    if change == "upstream_seal":
        (root / "seal.download").write_text("original release seal")
    elif change == "binary":
        (root / "release/payload/STS2_MCP.dll").write_bytes(b"another assembly")
    elif change == "patch":
        (tmp_path / "patches/engine/scoped.patch").write_text("another patch")
    else:
        path = tmp_path / "artifacts/build.json"
        built = json.loads(path.read_text())
        built.pop("report_id")
        built["fresh_builds"][1]["module_version_id"] = "c" * 36
        built["report_id"] = manifest_identifier(built)
        path.write_text(json.dumps(built))
        path = root / "toolchain.json"
        ledger = json.loads(path.read_text())
        ledger["local_build_report_id"] = built["report_id"]
        path.write_text(json.dumps(ledger))
    refresh_tool_ledger(config)
    with pytest.raises(ValueError, match="Local Host"):
        connector._verify_toolchain(config)


def test_missing_local_host_never_downloads_the_original_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    q = EngineQualificationConfig({"qualification": "synthetic"}, tmp_path)
    config = connector.ConnectorQualificationConfig(
        {"toolchain": "artifacts/not-built", "local_build": {}}, NativeQualificationConfig({}, q)
    )
    monkeypatch.setattr(connector, "_verified_archive", lambda _: None)
    with pytest.raises(ValueError, match="pinned local Host build recipe"):
        connector.prepare_connector_toolchain(config)
    assert not config.private("toolchain").exists()


def test_seen_tutorial_evidence_cannot_qualify_a_fresh_rest_profile() -> None:
    with pytest.raises(ValueError, match="requires the scoped rest fixture"):
        connector._evaluate_connector_checkpoint({}, fresh_rest_tutorial=True)
    result = connector._evaluate_connector_checkpoint(
        {}, rest_bridge=True, fresh_rest_tutorial=True
    )
    assert "fresh_rest_tutorial_dismissed" in result["errors"]
    assert "fresh_rest_progress_absent_before_launch" in result["errors"]
