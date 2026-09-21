from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, Self

from spireshift.core.manifest import PatchManifest, freeze_patch_manifest, sha256_digest
from spireshift.core.types import DecisionType, LegalAction, Observation, Transition

CONTINUATION_WIN_PROBABILITIES = {
    "preserve_hp": 0.35,
    "take_damage_for_power": 0.72,
    "spend_potion_for_relic": 0.82,
}
TACTICAL_MOCK_RULES = {
    "scenario": "post-combat resources change terminal-victory probability",
    "continuation_win_probabilities": CONTINUATION_WIN_PROBABILITIES,
    "reward": "binary_terminal_victory",
}
TACTICAL_MOCK_INTERFACE = {
    "observation_schema": "observation-v1",
    "action_schema": "action-v1",
    "information_policy_id": "public-state-v1",
}


def tactical_mock_patch_manifest() -> PatchManifest:
    rules_digest = sha256_digest(TACTICAL_MOCK_RULES)
    interface_digest = sha256_digest(TACTICAL_MOCK_INTERFACE)
    return freeze_patch_manifest(
        {
            "schema_version": "patch-manifest-v1",
            "admission_status": "test_only",
            "patch": {
                "patch_id": "tactical-handoff-mock-v1",
                "game_version": "tactical-handoff-mock-v1",
                "game_commit": "tactical-handoff-rules-v1",
                "branch": None,
                "release_date": None,
                "steam_build_id": None,
            },
            "engine": {
                "component_id": "spireshift-tactical-handoff-mock-engine",
                "version": "1",
                "revision": "tactical-handoff-rules-v1",
                "source": "spireshift://src/spireshift/adapters/tactical_mock.py",
                "digest": {"algorithm": "sha256", "value": rules_digest},
            },
            "adapter": {
                "component_id": "spireshift-tactical-handoff-mock-adapter",
                "version": "1",
                "revision": "observation-v1/action-v1",
                "source": "spireshift://src/spireshift/adapters/tactical_mock.py",
                "digest": {"algorithm": "sha256", "value": interface_digest},
            },
            "mechanics": [
                {
                    "artifact_id": "mock-tactical-to-run-rules",
                    "kind": "mechanics-bundle",
                    "version": "1",
                    "platform": None,
                    "architecture": None,
                    "digest": {"algorithm": "sha256", "value": rules_digest},
                    "size_bytes": len(json.dumps(TACTICAL_MOCK_RULES, sort_keys=True).encode()),
                }
            ],
            "interface": TACTICAL_MOCK_INTERFACE,
        }
    )


TACTICAL_MOCK_PATCH_MANIFEST = tactical_mock_patch_manifest()


@dataclass(slots=True)
class _TacticalState:
    stage: str = "combat"
    hp: int = 70
    max_hp: int = 80
    gold: int = 120
    potion_charges: int = 1
    permanent_power: int = 0
    relic_counter: int = 0
    relics: tuple[str, ...] = ()
    selected_tradeoff: str | None = None
    terminal: bool = False
    victory: bool = False


class TacticalHandoffMockEnvironment:
    """A public-information fixture where local HP and full-run value disagree."""

    patch_id = "tactical-handoff-mock-v1"
    ruleset = TACTICAL_MOCK_PATCH_MANIFEST.ruleset_identity()

    def __init__(self) -> None:
        self._rng = random.Random()
        self._state = _TacticalState()

    def reset(self, seed: int) -> Observation:
        self._rng = random.Random(seed)
        self._state = _TacticalState()
        return self._observation()

    def legal_actions(self) -> Sequence[LegalAction]:
        if self._state.terminal:
            return ()
        if self._state.stage == "combat":
            return (
                LegalAction("preserve_hp", "play_card", {"plan": "defend"}),
                LegalAction(
                    "take_damage_for_power",
                    "play_card",
                    {"plan": "scale", "expected_hp_cost": 28},
                ),
                LegalAction(
                    "spend_potion_for_relic",
                    "use_potion",
                    {"potion_slot": 0, "plan": "secure_relic"},
                ),
            )
        return (LegalAction("continue_run", "take_reward", {"choice": "skip"}),)

    def clone(self, *, resample_hidden: bool, seed: int | None = None) -> Self:
        cloned = type(self)()
        cloned._state = replace(self._state)
        if resample_hidden:
            cloned._rng = random.Random(0 if seed is None else seed)
        else:
            cloned._rng.setstate(self._rng.getstate())
        return cloned

    def step(self, action: LegalAction) -> Transition:
        observation = self._observation()
        legal = {candidate.action_id: candidate for candidate in self.legal_actions()}
        if action.action_id not in legal:
            raise ValueError(f"Illegal action: {action.action_id}")

        if self._state.stage == "combat":
            self._state.selected_tradeoff = action.action_id
            self._state.stage = "post_combat"
            if action.action_id == "take_damage_for_power":
                self._state.hp = 42
                self._state.permanent_power = 2
            elif action.action_id == "spend_potion_for_relic":
                self._state.hp = 60
                self._state.potion_charges = 0
                self._state.relics = ("ember_core",)
                self._state.relic_counter = 1
        else:
            assert self._state.selected_tradeoff is not None
            probability = CONTINUATION_WIN_PROBABILITIES[self._state.selected_tradeoff]
            self._state.victory = self._rng.random() < probability
            self._state.terminal = True
            self._state.stage = "terminal"

        next_observation = self._observation()
        reward = 1.0 if self._state.victory else 0.0
        return Transition(
            observation=observation,
            action=legal[action.action_id],
            next_observation=next_observation,
            reward=reward,
            terminal=self._state.terminal,
            victory=self._state.victory,
        )

    def _observation(self) -> Observation:
        public_state: dict[str, Any] = {
            "combat": {
                "enemy_hp": 24 if self._state.stage == "combat" else 0,
                "turn": 4,
            },
            "player": {
                "hp": self._state.hp,
                "max_hp": self._state.max_hp,
                "gold": self._state.gold,
                "potions": (
                    []
                    if self._state.potion_charges == 0
                    else [{"id": "fire_potion", "charges": self._state.potion_charges}]
                ),
                "deck": [
                    {"id": "strike", "upgrades": 0},
                    {"id": "defend", "upgrades": 1},
                    {"id": "scaling_engine", "upgrades": 0},
                ],
                "relics": [
                    {"id": relic, "counter": self._state.relic_counter}
                    for relic in self._state.relics
                ],
            },
            "run": {
                "act": 2,
                "floor": 20,
                "room_type": self._state.stage,
                "permanent_power": self._state.permanent_power,
                "relic_counter": self._state.relic_counter,
                "next_options": [
                    {"id": "elite", "revealed": True},
                    {"id": "rest", "revealed": True},
                ],
            },
            "terminal": self._state.terminal,
            "victory": self._state.victory,
        }
        encoded = json.dumps(public_state, sort_keys=True, separators=(",", ":")).encode()
        state_hash = hashlib.sha256(encoded).hexdigest()
        if self._state.terminal:
            decision_type = DecisionType.TERMINAL
        elif self._state.stage == "combat":
            decision_type = DecisionType.COMBAT
        else:
            decision_type = DecisionType.REWARD
        return Observation(
            schema_version="observation-v1",
            patch_id=self.patch_id,
            decision_type=decision_type,
            public_state=public_state,
            state_hash=state_hash,
        )
