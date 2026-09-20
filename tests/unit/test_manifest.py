import json
from pathlib import Path
from typing import Any

import pytest

from spireshift.adapters.mock import MOCK_PATCH_MANIFEST
from spireshift.core.manifest import (
    freeze_patch_manifest,
    load_patch_manifest,
    verify_installation_identity,
    write_frozen_manifest,
)


def _specification() -> dict[str, Any]:
    return {
        "schema_version": "patch-manifest-v1",
        "admission_status": "pending_conformance",
        "patch": {
            "patch_id": "sts2-test",
            "game_version": "v0.test.1",
            "game_commit": "deadbeef",
            "branch": "test",
            "release_date": "2026-09-19T00:00:00Z",
            "steam_build_id": "42",
        },
        "engine": {
            "component_id": "test-engine",
            "version": "1",
            "revision": "engine-1",
            "source": "https://example.com/engine",
            "digest": {"algorithm": "sha256", "value": "b" * 64},
        },
        "adapter": {
            "component_id": "test-adapter",
            "version": "1",
            "revision": "adapter-1",
            "source": "https://example.com/adapter",
            "digest": {"algorithm": "sha256", "value": "c" * 64},
        },
        "mechanics": [
            {
                "artifact_id": "test-game-assembly",
                "kind": "authoritative-game-assembly",
                "version": "v0.test.1",
                "platform": "macos",
                "architecture": "arm64",
                "digest": {"algorithm": "sha256", "value": "a" * 64},
                "size_bytes": 123,
            }
        ],
        "interface": {
            "observation_schema": "observation-v1",
            "action_schema": "action-v1",
            "information_policy_id": "public-state-v1",
        },
    }


def test_committed_mock_manifest_matches_runtime_ruleset() -> None:
    committed = load_patch_manifest(Path("manifests/patches/mock-v1.json"))
    assert committed == MOCK_PATCH_MANIFEST
    assert (
        committed.ruleset_identity().as_dict() == MOCK_PATCH_MANIFEST.ruleset_identity().as_dict()
    )


def test_freeze_hashes_local_mechanics_without_preserving_path(tmp_path: Path) -> None:
    mechanics = tmp_path / "extracted-mechanics.json"
    mechanics.write_text('{"damage": 6}', encoding="utf-8")
    specification = _specification()
    specification["mechanics"][0] = {
        "artifact_id": "extracted-mechanics",
        "kind": "extracted-mechanics",
        "version": "1",
        "platform": None,
        "architecture": None,
        "local_path": mechanics.name,
    }

    first = freeze_patch_manifest(specification, base_directory=tmp_path)
    mechanics.write_text('{"damage": 7}', encoding="utf-8")
    second = freeze_patch_manifest(specification, base_directory=tmp_path)

    assert first.manifest_id != second.manifest_id
    assert first.mechanics[0].size_bytes == len('{"damage": 6}')
    assert "local_path" not in json.dumps(first.as_dict())
    assert str(tmp_path) not in json.dumps(first.as_dict())


def test_manifest_identity_detects_tampering(tmp_path: Path) -> None:
    manifest = freeze_patch_manifest(_specification())
    path = tmp_path / "patch.json"
    write_frozen_manifest(manifest, path)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["patch"]["game_commit"] = "changed"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError, match="identity mismatch"):
        load_patch_manifest(path)


def test_immutable_write_refuses_different_manifest(tmp_path: Path) -> None:
    path = tmp_path / "patch.json"
    write_frozen_manifest(freeze_patch_manifest(_specification()), path)
    changed = _specification()
    changed["patch"]["game_commit"] = "different"

    with pytest.raises(FileExistsError, match="Refusing to replace"):
        write_frozen_manifest(freeze_patch_manifest(changed), path)


def test_installed_game_must_match_supported_build() -> None:
    installation = json.loads(Path("tests/fixtures/game-installation-v1.json").read_text())
    manifest = freeze_patch_manifest(_specification())
    assert verify_installation_identity(manifest, installation) == ()

    installation["assembly"]["sha256"] = "f" * 64
    errors = verify_installation_identity(manifest, installation)
    assert errors == ("game assembly hash or size does not match a supported build artifact",)


def test_all_committed_patch_manifests_are_content_addressed() -> None:
    manifests = sorted(Path("manifests/patches").glob("*.json"))
    assert manifests
    for path in manifests:
        assert load_patch_manifest(path).manifest_id.startswith("sha256:")
