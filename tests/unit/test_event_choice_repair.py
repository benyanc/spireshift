from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from spireshift import full_run_backend_repair as repair
from spireshift.core.manifest import load_patch_manifest, manifest_identifier


def synthetic_inventory(root: Path) -> Path:
    """Synthetic fixtures exercise integrity gates without proprietary captures in CI."""
    directory = root / "tests/fixtures/events"
    directory.mkdir(parents=True)
    entries = []
    for i in range(156):
        if i < 52:
            name, comparison = f"synthetic-{i}-options.json", "initial"
            capture: dict[str, Any] = {}
        elif i < 109:
            name, comparison = f"synthetic-{i}.json", "settled_event_after"
            capture = {"after": {"state_type": "event"}}
        elif i == 109:
            name, comparison = "DenseVegetation-opt1.json", "unsettled_event_after"
            capture = {"after": {"state_type": "event"}}
        else:
            name, comparison = f"synthetic-{i}.json", "other_screen_after"
            capture = {"after": {"state_type": "card_select"}}
        capture["game"] = {"steam_buildid": "23811903", "release": "v0.107.1"}
        path = directory / name
        path.write_text(json.dumps(capture))
        entries.append(
            {
                "path": name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "comparison": comparison,
            }
        )
    body = {
        "schema_version": "event-choice-fixture-inventory-v1",
        "game_version": "v0.107.1",
        "steam_build_id": "23811903",
        "ascension": 8,
        "seed": "ABCDEF",
        "files": entries,
    }
    body["inventory_id"] = manifest_identifier(body)
    path = root / "inventory.json"
    path.write_text(json.dumps(body))
    return path


def resign(path: Path, body: dict[str, Any], key: str) -> None:
    body[key] = manifest_identifier({k: v for k, v in body.items() if k != key})
    path.write_text(json.dumps(body))


def test_capture_inventory_rejects_changed_bytes_and_silent_exclusions(tmp_path: Path) -> None:
    path = synthetic_inventory(tmp_path)
    result = repair.verify_event_choice_inventory(path, tmp_path)
    assert result["coverage"]["initial"] == 52
    body = json.loads(path.read_text())
    body["files"][0]["comparison"] = "other_screen_after"
    resign(path, body, "inventory_id")
    with pytest.raises(ValueError, match="silently excluded"):
        repair.verify_event_choice_inventory(path, tmp_path)
    body["files"][0]["comparison"] = "initial"
    resign(path, body, "inventory_id")
    capture = tmp_path / "tests/fixtures/events" / body["files"][0]["path"]
    capture.write_text(capture.read_text() + " ")
    with pytest.raises(ValueError, match="bytes changed"):
        repair.verify_event_choice_inventory(path, tmp_path)


def test_capture_inventory_requires_all_files_and_matching_game_version(tmp_path: Path) -> None:
    path = synthetic_inventory(tmp_path)
    body = json.loads(path.read_text())
    extra = tmp_path / "tests/fixtures/events/extra.json"
    extra.write_text("{}")
    with pytest.raises(ValueError, match="missing or additional"):
        repair.verify_event_choice_inventory(path, tmp_path)
    extra.unlink()
    capture_path = tmp_path / "tests/fixtures/events" / body["files"][0]["path"]
    capture = json.loads(capture_path.read_text())
    capture["game"]["release"] = "other-version"
    capture_path.write_text(json.dumps(capture))
    body["files"][0]["sha256"] = hashlib.sha256(capture_path.read_bytes()).hexdigest()
    resign(path, body, "inventory_id")
    with pytest.raises(ValueError, match="game version differs"):
        repair.verify_event_choice_inventory(path, tmp_path)


def metadata_parent(path: Path) -> Any:
    if str(path).endswith("event-continuation-v1-retry1/candidate-manifest.json"):
        # CI uses checked metadata; private native payloads are never required.
        value = load_patch_manifest(
            Path("manifests/patches/sts2-v0.107.1-evangambit-event-public-v3-pending.json")
        )
        assert value.engine.revision == "d49c550a400ee6e6e96aaca2fbf88ef090f79ebd"
        return type(
            "Parent",
            (),
            {
                "manifest_id": (
                    "sha256:91d5fd3ef13eaae72fac67547021837097c377f3af1890cbb0797f33df343502"
                ),
                "engine": value.engine,
            },
        )()
    return load_patch_manifest(path)


def test_new_recipe_preserves_prior_configs_and_cannot_authorize_long_work(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(repair, "load_patch_manifest", metadata_parent)
    monkeypatch.setattr(repair, "verify_event_choice_inventory", lambda *args: {})
    recipe_path = Path("configs/backend-repair/sts2-v0.107.1-event-choices-v3.json")
    recipe = repair.load_repair_recipe(recipe_path)
    assert recipe.event_choices and recipe.event_continuation and recipe.public_choices
    assert recipe.test_destination == repair.EVENT_CHOICE_TEST_DESTINATION
    assert repair.EVENT_CHOICE_TEST_CLASS in recipe.test_classes
    assert "EventCaptures" in recipe.test_classes
    assert len(recipe.sources) == 6
    assert recipe.document["minimum_regression_tests"] == 240
    script = Path("scripts/build-event-choices-backend-v1.sh").read_text()
    assert "--max-wall-seconds 240" in script and "--max-cpu-seconds 960" in script
    assert "evolve" not in script and "backend admit" not in script
    assert recipe.path(recipe.document["base_upstream"]) != recipe.candidate
    assert all(u["base_sha256"] != u["repaired_sha256"] for u in recipe.document["test_updates"])

    d = recipe.document.copy()
    d["resource_limits"] = {**d["resource_limits"], "wall_seconds": 600}
    path = tmp_path / "config.json"
    resign(path, d, "config_id")
    with pytest.raises(ValueError, match="cannot authorize a long job"):
        repair.load_repair_recipe(path)
    d["resource_limits"]["wall_seconds"] = 240
    d["test_updates"] = [*d["test_updates"][:-1], {**d["test_updates"][-1], "path": "other.cs"}]
    resign(path, d, "config_id")
    with pytest.raises(ValueError, match="test correction scope differs"):
        repair.load_repair_recipe(path)
