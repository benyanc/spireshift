from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from spireshift.native_interface_controls_audit import consumer_paths
from spireshift.native_interface_controls_inputs import load
from spireshift.native_live_checkpoint_v3 import run
from spireshift.native_shop_policy import ShopNavigation


def test_literal_consumer_audit_tracks_surface_aliases_and_room_fields(tmp_path: Path) -> None:
    path = tmp_path / "consumer.py"
    path.write_text(
        "def view(public):\n"
        '    interaction = public["context"]["interaction"]\n'
        '    surface = interaction["content"]["surface"]\n'
        '    return surface["inventory_open"]\n'
    )
    result = consumer_paths([path])
    assert any(
        row["path"] == "/context/interaction/content/surface/inventory_open" for row in result
    )
    assert all(row["function"] == "view" for row in result)


def test_bad_controls_recipe_stops_before_any_output_or_model_import(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": "wrong"}))
    with pytest.raises(ValueError, match="finite"):
        load(tmp_path, path)
    assert list(tmp_path.iterdir()) == [path]


def test_consumer_audit_tracks_conditional_gets_and_numeric_baseline_requirements(
    tmp_path: Path,
) -> None:
    path = tmp_path / "numeric.py"
    path.write_text(
        "def features(public):\n"
        '    context = public["context"]\n'
        '    player, run = context["persistent"]["player"], context["persistent"]["run"]\n'
        '    content = context["interaction"].get("content", {}).get("context", {})\n'
        '    cp = content.get("player", {}) if True else {}\n'
        '    return _number(cp, "block"), _number(player, "hp"), run["floor"]\n'
    )
    paths = {row["path"] for row in consumer_paths([path])}
    assert "/context/interaction/content/context/player/block" in paths
    assert "/context/persistent/player/hp" in paths
    assert "/context/persistent/run/floor" in paths


def test_saved_only_stage_cannot_be_given_to_live_runner(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="cannot launch"):
        run(tmp_path, {"config": {"stage": "saved_only_checks"}})
    assert list(tmp_path.iterdir()) == []


def test_canonical_closed_open_closed_shop_keeps_navigation_and_strategic_choices() -> None:
    def public(opened: bool, inspected: bool) -> dict[str, Any]:
        candidates: list[dict[str, Any]] = (
            [
                {"verb": "activate", "label": "Open inventory", "subject": None, "arguments": []},
                {"verb": "close", "label": "Leave shop", "subject": None, "arguments": []},
            ]
            if not opened
            else [
                {"verb": "activate", "label": "Buy test item", "subject": {}, "arguments": []},
                {
                    "verb": "cancel",
                    "label": "Close shop inventory",
                    "subject": None,
                    "arguments": [],
                },
            ]
        )
        for candidate in candidates:
            candidate["history"] = {"shop_inspected": inspected}
        return {
            "context": {
                "persistent": {"run": {"act": 1, "floor": 3}},
                "interaction": {
                    "kind": "shop_inventory",
                    "content": {"surface": {"inventory_open": opened}},
                },
            },
            "candidates": candidates,
        }

    navigation = ShopNavigation()
    original = public(False, False)
    _, indices, forced = navigation.view(original)
    assert indices == [0] and forced
    opened = public(True, True)
    _, indices, forced = navigation.view(opened)
    assert indices == [0, 1] and not forced
    closed = public(False, True)
    _, indices, forced = navigation.view(closed)
    assert indices == [1] and not forced
    assert len(original["candidates"]) == len(closed["candidates"]) == 2


def test_interface_controls_contract_and_fault_injection_in_node() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Run explicitly with the pinned bundled Node on native hosts")
    result = subprocess.run(
        [node, "--test", "scripts/engine-interface-controls-v1.test.mjs"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
