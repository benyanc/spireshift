from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from spireshift.adapters.sts2mcp import (
    BridgeVersionError,
    InformationBoundaryError,
    LiveStateError,
    Sts2McpHttpTransport,
    Sts2McpLiveStateAdapter,
    Sts2McpStateProjector,
)
from spireshift.core.manifest import load_patch_manifest

MANIFEST_PATH = Path("manifests/patches/sts2-v0.107.1-sts2mcp-55e0648.json")
SOURCE_FIXTURE = Path("tests/fixtures/sts2mcp-menu-source-v0.4.0.json")


class FakeReadTransport:
    def __init__(self, state: dict[str, object], *, version: str = "0.4.0") -> None:
        self.state = state
        self.version = version
        self.state_reads = 0

    def bridge_version(self) -> str:
        return self.version

    def read_singleplayer_state(self) -> dict[str, object]:
        self.state_reads += 1
        return copy.deepcopy(self.state)


def _source_fixture() -> dict[str, object]:
    value = json.loads(SOURCE_FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _projector() -> Sts2McpStateProjector:
    return Sts2McpStateProjector(load_patch_manifest(MANIFEST_PATH))


def _matching_installation() -> dict[str, object]:
    return {
        "platform": "macos",
        "architecture": "arm64",
        "release": {
            "version": "v0.107.1",
            "commit": "59260271",
            "steam_build_id": "23811903",
        },
        "assembly": {
            "sha256": "e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18",
            "size_bytes": 9363456,
        },
    }


def test_menu_snapshot_is_public_versioned_and_deterministic() -> None:
    source = _source_fixture()
    projector = _projector()

    first = projector.project(source, bridge_version="0.4.0")
    second = projector.project(source, bridge_version="0.4.0")

    assert first.as_dict() == second.as_dict()
    assert first.ruleset.patch_id == "sts2-v0.107.1-59260271"
    assert first.observation.schema_version == "observation-v1"
    assert first.observation.decision_type.value == "menu"
    assert first.action_coverage_status == "ready"
    assert [action.payload for action in first.legal_actions] == [
        {"option": "IRONCLAD"},
        {"option": "back"},
    ]
    assert "seed" not in json.dumps(first.observation.public_state).casefold()
    assert first.omitted_source_paths == ("source.lobby.seed",)


def test_running_bridge_version_must_match_manifest_before_state_read() -> None:
    transport = FakeReadTransport(_source_fixture(), version="0.4.1")
    adapter = Sts2McpLiveStateAdapter(
        load_patch_manifest(MANIFEST_PATH),
        _matching_installation(),
        transport,
    )

    with pytest.raises(BridgeVersionError, match="version mismatch"):
        adapter.snapshot()

    assert transport.state_reads == 0


def test_game_identity_must_match_before_bridge_contact() -> None:
    transport = FakeReadTransport(_source_fixture())
    installation = _matching_installation()
    release = installation["release"]
    assert isinstance(release, dict)
    release["version"] = "v0.999.0"

    with pytest.raises(LiveStateError, match="game version mismatch"):
        Sts2McpLiveStateAdapter(
            load_patch_manifest(MANIFEST_PATH),
            installation,
            transport,
        )

    assert transport.state_reads == 0


def test_unaudited_top_level_field_fails_closed() -> None:
    source = _source_fixture()
    source["native_debug_state"] = {"value": 1}

    with pytest.raises(InformationBoundaryError, match="unaudited top-level"):
        _projector().project(source, bridge_version="0.4.0")


def test_privileged_nested_rng_field_fails_closed() -> None:
    source = _source_fixture()
    source["lobby"] = {"rng_state": 123}

    with pytest.raises(InformationBoundaryError, match="forbidden privileged state"):
        _projector().project(source, bridge_version="0.4.0")


def test_combat_actions_expand_visible_targets_and_potions() -> None:
    source: dict[str, object] = {
        "state_type": "monster",
        "run": {"act": 1, "floor": 1, "ascension": 0},
        "battle": {
            "round": 1,
            "turn": "player",
            "is_play_phase": True,
            "enemies": [
                {"entity_id": "JAW_WORM_0", "hp": 40},
                {"entity_id": "LOUSE_0", "hp": 12},
            ],
        },
        "player": {
            "hp": 80,
            "hand": [
                {"index": 0, "can_play": True, "target_type": "AnyEnemy"},
                {"index": 1, "can_play": True, "target_type": "Self"},
            ],
            "potions": [{"slot": 0, "can_use_in_combat": True, "target_type": "None"}],
        },
    }

    snapshot = _projector().project(source, bridge_version="0.4.0")

    assert snapshot.action_coverage_status == "ready"
    assert [(action.kind, action.payload) for action in snapshot.legal_actions] == [
        ("play_card", {"card_index": 0, "target": "JAW_WORM_0"}),
        ("play_card", {"card_index": 0, "target": "LOUSE_0"}),
        ("play_card", {"card_index": 1}),
        ("use_potion", {"slot": 0}),
        ("discard_potion", {"slot": 0}),
        ("end_turn", {}),
    ]


def test_http_transport_rejects_non_local_origins() -> None:
    with pytest.raises(ValueError, match="local HTTP origin"):
        Sts2McpHttpTransport("https://example.com")
