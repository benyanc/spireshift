"""Launch blockers cannot consume a retry or hide attempted-case denominators."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import spireshift.engine_bundle_bridge as bridge
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file


@pytest.fixture
def batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[EngineQualificationConfig, Path, Path, Path]:
    qualification = EngineQualificationConfig({}, tmp_path)
    directory = tmp_path / "configs"
    directory.mkdir()
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in bridge.HELPERS:
        (scripts / name).write_text("pinned helper")
    template = {
        "schema_version": "engine-bundle-bridge-config-v1",
        "stage": "natural_Neow_bundle_choice_differential_only",
        "qualification_config_id": qualification.config_id,
        "bridge_revision": "v3",
        "training_allowed": False,
        "helpers_sha256": {name: _sha_file(scripts / name) for name in bridge.HELPERS},
    }
    (directory / "template.json").write_text(json.dumps(template))
    document: dict[str, Any] = {
        "schema_version": "engine-bundle-bridges-config-v1",
        "stage": "owner_repeated_natural_bundle_differentials_only",
        "qualification_config_id": qualification.config_id,
        "training_allowed": False,
        "max_wall_seconds": 900,
        "template": "configs/template.json",
        "template_id": manifest_identifier(template),
        "workspace": "artifacts/bundle-retry-v2",
        "cases": [
            {
                "case_id": f"seed-{seed}-pack-{index}-repeat-{repeat}",
                "seed": f"SEED{seed}",
                "index": index,
            }
            for seed in (1, 2)
            for index in (0, 1)
            for repeat in (1, 2)
        ],
    }
    path = directory / "batch.json"
    path.write_text(json.dumps(document))
    node = tmp_path / "node"
    node.write_text("test executable")
    node.chmod(0o700)
    monkeypatch.setattr(bridge, "_require_native_launch_support", lambda: None)
    monkeypatch.setattr(bridge, "_running_games", lambda: [])
    monkeypatch.setattr(
        "spireshift.engine_bundle_bridge.shutil.disk_usage",
        lambda path: SimpleNamespace(free=10_000_000_000),
    )
    monkeypatch.setattr(bridge, "_verify_bundle_prerequisites", lambda *args: {"verified": True})

    def no_launch(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("Preflight must never launch a native or shipped game")

    monkeypatch.setattr(bridge, "_probe_cli_document", no_launch)
    monkeypatch.setattr(bridge, "_probe_connector_private", no_launch)
    return qualification, path, node, tmp_path / document["workspace"]


def test_passing_preflight_allocates_no_batch_or_game(
    batch: tuple[EngineQualificationConfig, Path, Path, Path],
) -> None:
    qualification, path, node, workspace = batch
    before = sorted(qualification.root.rglob("*"))
    result = bridge.preflight_bundle_bridges(qualification, path, node=node)
    assert result["status"] == "bundle_preflight_pass"
    assert result["games_launched"] == 0
    assert result["workspace_created"] is False
    assert result["prerequisites"] == {"verified": True}
    assert not workspace.exists()
    assert sorted(qualification.root.rglob("*")) == before


@pytest.mark.parametrize(
    "blocker", ["space", "running_game", "missing_input", "changed_input", "node"]
)
def test_blocker_leaves_retry_available_and_previous_failure_unchanged(
    batch: tuple[EngineQualificationConfig, Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    blocker: str,
) -> None:
    qualification, path, node, workspace = batch
    previous = qualification.root / "artifacts/previous-v1/batch.json"
    previous.parent.mkdir(parents=True)
    previous.write_text('{"status":"bundle_comparisons_incomplete","completed_cases":0}')
    original = previous.read_bytes()
    if blocker == "space":
        monkeypatch.setattr(
            "spireshift.engine_bundle_bridge.shutil.disk_usage",
            lambda path: SimpleNamespace(free=3_499_999_999),
        )
    elif blocker == "running_game":
        monkeypatch.setattr(bridge, "_running_games", lambda: [123])
    elif blocker == "node":
        node.chmod(0o600)
    elif blocker == "changed_input":
        (qualification.root / "scripts" / next(iter(bridge.HELPERS))).write_text("changed")
    else:

        def missing(*args: Any) -> Any:
            raise FileNotFoundError("Pinned candidate was removed")

        monkeypatch.setattr(bridge, "_verify_bundle_prerequisites", missing)
    with pytest.raises((ValueError, OSError)):
        bridge.compare_bundle_bridges(qualification, path, node=node)
    assert not workspace.exists()
    assert previous.read_bytes() == original


def test_existing_failed_retry_is_never_overwritten(
    batch: tuple[EngineQualificationConfig, Path, Path, Path],
) -> None:
    qualification, path, node, workspace = batch
    workspace.mkdir(parents=True)
    previous = workspace / "batch.json"
    previous.write_text("preserve failed attempt")
    with pytest.raises(FileExistsError, match="no automatic resume"):
        bridge.preflight_bundle_bridges(qualification, path, node=node)
    assert previous.read_text() == "preserve failed attempt"


@pytest.mark.parametrize("failure", ["mismatch", "space_between_cases"])
def test_started_batch_stops_at_first_problem_and_counts_unattempted_cases(
    batch: tuple[EngineQualificationConfig, Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    qualification, path, node, workspace = batch
    attempted = []

    def comparison(*args: Any, **kwargs: Any) -> dict[str, Any]:
        attempted.append(kwargs["override"]["seed"])
        if failure == "space_between_cases":
            monkeypatch.setattr(
                "spireshift.engine_bundle_bridge.shutil.disk_usage",
                lambda path: SimpleNamespace(free=0),
            )
        return {
            "status": "bundle_action_comparison_pass"
            if failure == "space_between_cases"
            else "bundle_comparison_incomplete"
        }

    monkeypatch.setattr(bridge, "compare_bundle_bridge", comparison)
    result = bridge.compare_bundle_bridges(qualification, path, node=node)
    assert len(attempted) == 1
    assert result["status"] == "bundle_comparisons_incomplete"
    assert result["completed_cases"] == int(failure == "space_between_cases")
    assert result["failed_cases"] == int(failure == "mismatch")
    assert result["not_attempted_cases"] == 7
    assert len(result["cases"]) == 1
    assert result["preflight"]["games_launched"] == 0
    assert json.loads((workspace / "batch.json").read_text()) == result
    assert not (workspace / "in-progress.json").exists()
    assert not (workspace / "case-02-config.json").exists()
