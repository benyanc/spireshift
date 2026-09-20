from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, Self

from spireshift.core.manifest import PatchManifest, freeze_patch_manifest, sha256_digest
from spireshift.core.types import DecisionType, LegalAction, Observation, Transition

MOCK_RULES = {
    "initial_state": {"floor": 0, "strength": 0, "terminal": False, "victory": False},
    "elite_path": {"immediate_death_probability": 0.25, "boss_win_probability": 0.8},
    "safe_path": {"immediate_death_probability": 0.0, "boss_win_probability": 0.2},
    "reward": "binary_terminal_victory",
}
MOCK_INTERFACE = {
    "observation_schema": "observation-v1",
    "action_schema": "action-v1",
    "information_policy_id": "public-state-v1",
}


def mock_patch_manifest() -> PatchManifest:
    rules_digest = sha256_digest(MOCK_RULES)
    interface_digest = sha256_digest(MOCK_INTERFACE)
    return freeze_patch_manifest(
        {
            "schema_version": "patch-manifest-v1",
            "admission_status": "test_only",
            "patch": {
                "patch_id": "mock-v1",
                "game_version": "mock-v1",
                "game_commit": "mock-rules-v1",
                "branch": None,
                "release_date": None,
                "steam_build_id": None,
            },
            "engine": {
                "component_id": "spireshift-mock-engine",
                "version": "1",
                "revision": "mock-rules-v1",
                "source": "spireshift://src/spireshift/adapters/mock.py",
                "digest": {"algorithm": "sha256", "value": rules_digest},
            },
            "adapter": {
                "component_id": "spireshift-mock-adapter",
                "version": "1",
                "revision": "observation-v1/action-v1",
                "source": "spireshift://src/spireshift/adapters/mock.py",
                "digest": {"algorithm": "sha256", "value": interface_digest},
            },
            "mechanics": [
                {
                    "artifact_id": "mock-terminal-victory-rules",
                    "kind": "mechanics-bundle",
                    "version": "1",
                    "platform": None,
                    "architecture": None,
                    "digest": {"algorithm": "sha256", "value": rules_digest},
                    "size_bytes": len(json.dumps(MOCK_RULES, sort_keys=True).encode()),
                }
            ],
            "interface": MOCK_INTERFACE,
        }
    )


MOCK_PATCH_MANIFEST = mock_patch_manifest()


@dataclass(slots=True)
class _MockState:
    floor: int = 0
    strength: int = 0
    terminal: bool = False
    victory: bool = False


class MockSpireEnvironment:
    """A two-decision environment demonstrating full-run versus Act 1 objectives.

    The safe path always reaches the mock boss but wins only 20% of the time. The elite path has a
    25% chance of ending the run immediately, then wins 80% of boss fights. It is worse for the
    intermediate survival metric and better for terminal victory.
    """

    patch_id = "mock-v1"
    ruleset = MOCK_PATCH_MANIFEST.ruleset_identity()

    def __init__(self) -> None:
        self._rng = random.Random()
        self._state = _MockState()

    def reset(self, seed: int) -> Observation:
        self._rng = random.Random(seed)
        self._state = _MockState()
        return self._observation()

    def legal_actions(self) -> Sequence[LegalAction]:
        if self._state.terminal:
            return ()
        if self._state.floor == 0:
            return (
                LegalAction("safe_path", "choose_path", {"risk": "low"}),
                LegalAction("elite_path", "choose_path", {"risk": "high"}),
            )
        return (LegalAction("face_boss", "combat", {}),)

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

        if self._state.floor == 0 and action.action_id == "safe_path":
            self._state.floor = 1
        elif self._state.floor == 0 and action.action_id == "elite_path":
            if self._rng.random() < 0.25:
                self._state.terminal = True
            else:
                self._state.floor = 1
                self._state.strength = 1
        elif self._state.floor == 1 and action.action_id == "face_boss":
            win_probability = 0.8 if self._state.strength else 0.2
            self._state.victory = self._rng.random() < win_probability
            self._state.terminal = True

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
            "floor": self._state.floor,
            "strength": self._state.strength,
            "terminal": self._state.terminal,
            "victory": self._state.victory,
        }
        encoded = json.dumps(public_state, sort_keys=True, separators=(",", ":")).encode()
        state_hash = hashlib.sha256(encoded).hexdigest()
        if self._state.terminal:
            decision_type = DecisionType.TERMINAL
        elif self._state.floor == 0:
            decision_type = DecisionType.PATH
        else:
            decision_type = DecisionType.COMBAT
        return Observation(
            schema_version="observation-v1",
            patch_id=self.patch_id,
            decision_type=decision_type,
            public_state=public_state,
            state_hash=state_hash,
        )
