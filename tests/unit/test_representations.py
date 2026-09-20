from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.adapters.sts2mcp import Sts2McpStateProjector
from spireshift.cli import main
from spireshift.core.manifest import load_patch_manifest, manifest_identifier
from spireshift.core.types import DecisionType, LegalAction, Observation
from spireshift.representations import (
    ENCODER_ID,
    FeatureSemantic,
    build_model_input,
    vectorize_model_input,
)

MANIFEST_PATH = Path("manifests/patches/sts2-v0.107.1-sts2mcp-55e0648.json")
CORPUS_PATH = Path("tests/fixtures/live/public-state-corpus-v1.json")
MODEL_FIXTURE_PATH = Path("tests/fixtures/model-input-v1.json")
VECTOR_FIXTURE_PATH = Path("tests/fixtures/vectorized-model-input-v1.json")


def _state_hash(public_state: dict[str, Any]) -> str:
    encoded = json.dumps(
        public_state,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _observation(public_state: dict[str, Any]) -> Observation:
    return Observation(
        schema_version="observation-v1",
        patch_id="mock-v1",
        decision_type=DecisionType.COMBAT,
        public_state=public_state,
        state_hash=_state_hash(public_state),
    )


def _live_snapshots() -> list[tuple[str, object]]:
    document = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    fixtures = document["fixtures"]
    assert isinstance(fixtures, list)
    manifest = load_patch_manifest(MANIFEST_PATH)
    projector = Sts2McpStateProjector(manifest)
    snapshots: list[tuple[str, object]] = []
    for raw_fixture in fixtures:
        fixture = cast(dict[str, Any], raw_fixture)
        snapshots.append(
            (
                cast(str, fixture["fixture_id"]),
                projector.project(fixture["source"], bridge_version=manifest.adapter.version),
            )
        )
    return snapshots


def test_mock_representation_and_vectorization_are_deterministic() -> None:
    environment = MockSpireEnvironment()
    observation = environment.reset(7)
    actions = environment.legal_actions()

    first = build_model_input(environment.ruleset, observation, actions)
    second = build_model_input(environment.ruleset, observation, actions)
    first_vector = vectorize_model_input(first, dimension=256)

    assert first == second
    assert first.representation_hash == manifest_identifier(first.body_dict())
    assert first.model_feature_digest() == second.model_feature_digest()
    assert [candidate.source_action_id for candidate in first.candidates] == [
        action.action_id for action in actions
    ]
    assert first.action_mask == (True, True)
    assert first_vector == vectorize_model_input(second, dimension=256)
    assert all(0 <= entry.index < 256 for entry in first_vector.state)


def test_source_action_ids_are_decode_handles_not_model_features() -> None:
    environment = MockSpireEnvironment()
    observation = environment.reset(1)
    first_actions = (
        LegalAction("source-a", "choose_path", {"risk": "low"}),
        LegalAction("source-b", "choose_path", {"risk": "high"}),
    )
    renamed_actions = (
        LegalAction("unseen-handle-1", "choose_path", {"risk": "low"}),
        LegalAction("unseen-handle-2", "choose_path", {"risk": "high"}),
    )

    first = build_model_input(environment.ruleset, observation, first_actions)
    renamed = build_model_input(environment.ruleset, observation, renamed_actions)
    first_vector = vectorize_model_input(first, dimension=256)
    renamed_vector = vectorize_model_input(renamed, dimension=256)

    assert first.representation_hash != renamed.representation_hash
    assert first.model_feature_digest() == renamed.model_feature_digest()
    assert first_vector.state == renamed_vector.state
    assert first_vector.candidates == renamed_vector.candidates
    assert first_vector.source_action_ids != renamed_vector.source_action_ids
    assert "source_action_id" not in json.dumps(first.model_dict())


def test_rich_state_is_grouped_into_resources_entities_and_candidate_features() -> None:
    public_state: dict[str, Any] = {
        "state_type": "monster",
        "run": {"act": 1, "floor": 4, "ascension": 10},
        "player": {
            "hp": 55,
            "max_hp": 80,
            "gold": 99,
            "energy": 3,
            "deck": [
                {
                    "id": "NEW_PATCH_CARD",
                    "cost": 1,
                    "base_damage": 6,
                    "upgraded": False,
                }
            ],
            "relics": [{"id": "NEW_PATCH_RELIC", "counter": 2}],
            "potions": [{"id": "NEW_PATCH_POTION", "slot": 0, "damage": 20}],
        },
        "battle": {
            "round": 2,
            "turn": "player",
            "enemies": [
                {
                    "entity_id": "NEW_PATCH_ENEMY",
                    "hp": 35,
                    "block": 2,
                    "intent": "attack",
                    "intent_damage": 11,
                    "statuses": [{"id": "weak", "amount": 1}],
                }
            ],
        },
    }
    actions = (
        LegalAction(
            "opaque-action-handle",
            "play_card",
            {
                "card_index": 0,
                "target": "NEW_PATCH_ENEMY",
                "cost": 1,
                "base_damage": 6,
            },
        ),
        LegalAction("end-turn-handle", "end_turn", {}),
    )
    ruleset = MockSpireEnvironment.ruleset

    representation = build_model_input(ruleset, _observation(public_state), actions)

    resource_paths = {".".join(feature.path) for feature in representation.persistent_resources}
    assert {"player.hp", "player.max_hp", "player.gold"} <= resource_paths
    assert any(path.startswith("player.deck.") for path in resource_paths)
    assert any(path.startswith("player.relics.") for path in resource_paths)
    assert any(path.startswith("player.potions.") for path in resource_paths)
    assert "battle.enemies.hp" not in resource_paths
    assert {entity.entity_type for entity in representation.entities} >= {
        "player",
        "card",
        "relic",
        "potion",
        "enemy",
        "status",
    }
    card = next(entity for entity in representation.entities if entity.entity_type == "card")
    assert card.indices == (0,)
    assert {feature.semantic for feature in card.features} >= {
        FeatureSemantic.IDENTITY,
        FeatureSemantic.MECHANIC,
    }
    enemy = next(entity for entity in representation.entities if entity.entity_type == "enemy")
    enemy_hp = next(feature for feature in enemy.features if feature.path[-1] == "hp")
    assert enemy_hp.semantic is FeatureSemantic.MECHANIC
    candidate = representation.candidates[0]
    candidate_semantics = {feature.semantic for feature in candidate.features}
    assert FeatureSemantic.LOCATOR in candidate_semantics
    assert FeatureSemantic.MECHANIC in candidate_semantics
    assert candidate.source_action_id == "opaque-action-handle"
    assert candidate.action_kind == "play_card"


def test_every_checked_live_fixture_has_a_well_formed_model_input() -> None:
    snapshots = _live_snapshots()
    decision_types: set[str] = set()
    candidate_count = 0

    for _, raw_snapshot in snapshots:
        snapshot = cast(Any, raw_snapshot)
        representation = build_model_input(
            snapshot.ruleset,
            snapshot.observation,
            snapshot.legal_actions,
        )
        vector = vectorize_model_input(representation, dimension=256)
        decision_types.add(representation.decision_type)
        candidate_count += len(representation.candidates)

        assert representation.representation_hash == manifest_identifier(representation.body_dict())
        assert len(representation.candidates) == len(snapshot.legal_actions)
        assert len(representation.action_mask) == len(snapshot.legal_actions)
        assert vector.source_action_ids == tuple(
            action.action_id for action in snapshot.legal_actions
        )
        assert len(vector.candidates) == len(snapshot.legal_actions)
        assert all(
            0 <= entry.index < vector.dimension
            for entries in (vector.state, *vector.candidates)
            for entry in entries
        )

    assert len(snapshots) == 19
    assert candidate_count > 40
    assert {
        "menu",
        "path",
        "combat",
        "combat_selection",
        "reward",
        "event",
        "rest_site",
        "shop",
        "treasure",
        "card_selection",
        "relic_selection",
        "mini_game",
        "terminal",
    } <= decision_types


def test_checked_model_fixtures_match_the_live_combat_projection() -> None:
    snapshot = next(
        cast(Any, raw_snapshot)
        for fixture_id, raw_snapshot in _live_snapshots()
        if fixture_id == "combat-monster-targets-and-potions"
    )
    representation = build_model_input(
        snapshot.ruleset,
        snapshot.observation,
        snapshot.legal_actions,
    )

    assert representation.as_dict() == json.loads(MODEL_FIXTURE_PATH.read_text())
    assert vectorize_model_input(representation, dimension=256).as_dict() == json.loads(
        VECTOR_FIXTURE_PATH.read_text()
    )


def test_representation_rejects_stale_duplicate_and_privileged_inputs() -> None:
    environment = MockSpireEnvironment()
    observation = environment.reset(1)
    duplicate_actions = (
        LegalAction("same", "choose_path", {"risk": "low"}),
        LegalAction("same", "choose_path", {"risk": "high"}),
    )
    stale = Observation(
        schema_version=observation.schema_version,
        patch_id=observation.patch_id,
        decision_type=observation.decision_type,
        public_state=observation.public_state,
        state_hash="0" * 64,
    )
    privileged_state = copy.deepcopy(observation.public_state)
    privileged_state["rng_state"] = 123
    privileged_action = LegalAction("future", "choose_path", {"future_reward": 1})

    with pytest.raises(ValueError, match="state hash"):
        build_model_input(environment.ruleset, stale, environment.legal_actions())
    with pytest.raises(ValueError, match="unique"):
        build_model_input(environment.ruleset, observation, duplicate_actions)
    with pytest.raises(ValueError, match="Privileged feature"):
        build_model_input(
            environment.ruleset,
            _observation(privileged_state),
            environment.legal_actions(),
        )
    with pytest.raises(ValueError, match="Privileged feature"):
        build_model_input(environment.ruleset, observation, (privileged_action,))


def test_vector_dimension_has_a_defensive_minimum() -> None:
    environment = MockSpireEnvironment()
    representation = build_model_input(
        environment.ruleset,
        environment.reset(1),
        environment.legal_actions(),
    )

    with pytest.raises(ValueError, match="at least 64"):
        vectorize_model_input(representation, dimension=63)

    assert representation.model_dict()["encoder_id"] == ENCODER_ID


def test_cli_writes_a_vectorized_mock_input(tmp_path: Path) -> None:
    output = tmp_path / "vector.json"

    result = main(
        [
            "represent",
            "mock",
            "--seed",
            "7",
            "--vectorized",
            "--dimension",
            "256",
            "--output",
            str(output),
        ]
    )
    document = json.loads(output.read_text(encoding="utf-8"))

    assert result == 0
    assert document["schema_version"] == "vectorized-model-input-v1"
    assert document["dimension"] == 256
    assert len(document["candidates"]) == 2
