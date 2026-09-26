from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Self

import pytest

from spireshift.adapters.mock import MOCK_PATCH_MANIFEST
from spireshift.agents.combat_advancement import (
    CombatAdvancementConfig,
    CombatAdvancementPolicy,
)
from spireshift.agents.learned import ProductionPolicyDecision
from spireshift.core.types import DecisionType, LegalAction, Observation, Transition


@dataclass
class _SharedCloneState:
    resamples: int = 0
    reject_resamples: int = 0


class _AdvancementEnvironment:
    patch_id = "mock-v1"
    ruleset = MOCK_PATCH_MANIFEST.ruleset_identity()

    def __init__(
        self,
        *,
        stage: str = "root",
        decision_type: DecisionType = DecisionType.COMBAT,
        shared: _SharedCloneState | None = None,
        incompatible: bool = False,
    ) -> None:
        self.stage = stage
        self.decision_type = decision_type
        self.shared = shared or _SharedCloneState()
        self.incompatible = incompatible

    def reset(self, seed: int) -> Observation:
        del seed
        self.stage = "root"
        return self._observation()

    def legal_actions(self) -> Sequence[LegalAction]:
        if self.stage == "root":
            actions = (
                LegalAction("bad", "card", {}),
                LegalAction("good", "card", {}),
            )
            if self.incompatible:
                return (*actions, LegalAction("private-mismatch", "card", {}))
            return actions
        return (LegalAction("continue", "path", {}),)

    def step(self, action: LegalAction) -> Transition:
        source = self._observation()
        if action not in self.legal_actions():
            raise ValueError("illegal action")
        if self.stage == "root":
            self.stage = "bad-leaf" if action.action_id == "bad" else "good-leaf"
            self.decision_type = DecisionType.PATH
        else:
            self.stage = "terminal"
            self.decision_type = DecisionType.TERMINAL
        return Transition(source, action, self._observation(), 0.0, False, False)

    def clone(self, *, resample_hidden: bool, seed: int | None = None) -> Self:
        del seed
        incompatible = self.incompatible
        if resample_hidden:
            self.shared.resamples += 1
            incompatible = self.shared.resamples <= self.shared.reject_resamples
        return type(self)(
            stage=self.stage,
            decision_type=self.decision_type,
            shared=self.shared,
            incompatible=incompatible,
        )

    def _observation(self) -> Observation:
        public_state = {
            "stage": self.stage,
            "floor": 7,
            "terminal": self.stage == "terminal",
            "victory": False,
        }
        state_hash = hashlib.sha256(
            json.dumps(public_state, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return Observation(
            "observation-v1",
            self.patch_id,
            self.decision_type,
            public_state,
            state_hash,
        )


class _Predictor:
    policy_id = "fake-production-policy"
    model_id = "sha256:" + "1" * 64
    ruleset = MOCK_PATCH_MANIFEST.ruleset_identity()

    def predict(
        self,
        observation: Observation,
        legal_actions: Sequence[LegalAction],
    ) -> ProductionPolicyDecision:
        actions = tuple(legal_actions)
        if observation.public_state["stage"] == "root":
            policy: tuple[float, ...] = (0.9, 0.1)
            floor: tuple[float, ...] = (0.5, 0.5)
            risk: tuple[float, ...] = (0.5, 0.5)
        elif observation.public_state["stage"] == "bad-leaf":
            policy = (1.0,)
            floor = (0.1,)
            risk = (0.9,)
        else:
            policy = (1.0,)
            floor = (0.8,)
            risk = (0.1,)
        selected = max(range(len(actions)), key=lambda index: policy[index])
        return ProductionPolicyDecision(
            representation_hash=observation.state_hash,
            source_action_ids=tuple(action.action_id for action in actions),
            selected_candidate_index=selected,
            selected_action=actions[selected],
            policy=policy,
            terminal_value=None,
            tactical_death_risk=risk,
            maximum_floor_reach={8: floor, 9: floor},
            inference_seconds=0.0,
        )

    def choose_action(
        self,
        observation: Observation,
        legal_actions: Sequence[LegalAction],
    ) -> LegalAction:
        return self.predict(observation, legal_actions).selected_action


def _config(**overrides: object) -> CombatAdvancementConfig:
    values: dict[str, object] = {
        "candidate_worlds": 2,
        "maximum_rollout_steps": 4,
        "maximum_simulated_transitions_per_decision": 16,
        "maximum_public_resample_attempts": 4,
        "public_resample_exhaustion": "policy_only_fallback",
        "progress_weight": 0.8,
        "tactical_survival_weight": 0.2,
        "sampling_salt": "unit-test",
    }
    values.update(overrides)
    return CombatAdvancementConfig(**values)  # type: ignore[arg-type]


def test_combat_search_overrides_base_policy_with_progress_leaf_value() -> None:
    environment = _AdvancementEnvironment()
    observation = environment.reset(0)
    policy = CombatAdvancementPolicy(
        environment=environment,
        base_policy=_Predictor(),
        config=_config(),
    )

    selected = policy.choose_action(observation, environment.legal_actions())

    assert selected.action_id == "good"
    assert policy.last_decision is not None
    assert policy.last_decision.base_action.action_id == "bad"
    assert policy.last_decision.search_action.action_id == "good"
    assert policy.last_decision.search_override_recommended is True
    assert policy.last_decision.search_override_executed is True
    assert policy.last_decision.selection_reason == "search_override"
    assert policy.last_decision.simulated_transitions == 4
    assert policy.last_decision.hidden_worlds == 2
    assert [item.mean_search_value for item in policy.last_decision.candidates] == pytest.approx(
        [0.1, 0.82]
    )
    assert policy.usage().as_dict() == {
        "policy_only_decisions": 0,
        "search_decisions": 1,
        "search_fallback_decisions": 0,
        "simulated_transitions": 4,
        "hidden_worlds": 2,
        "public_resample_attempts": 2,
        "public_resample_failures": 0,
    }


def test_search_rejects_hidden_worlds_that_change_public_legal_actions() -> None:
    shared = _SharedCloneState(reject_resamples=1)
    environment = _AdvancementEnvironment(shared=shared)
    observation = environment.reset(0)
    policy = CombatAdvancementPolicy(
        environment=environment,
        base_policy=_Predictor(),
        config=_config(),
    )

    assert policy.choose_action(observation, environment.legal_actions()).action_id == "good"
    assert policy.last_decision is not None
    assert policy.last_decision.public_resample_attempts == 3
    assert shared.resamples == 3


def test_search_falls_back_to_public_policy_when_compatible_worlds_are_exhausted() -> None:
    shared = _SharedCloneState(reject_resamples=100)
    environment = _AdvancementEnvironment(shared=shared)
    observation = environment.reset(0)
    policy = CombatAdvancementPolicy(
        environment=environment,
        base_policy=_Predictor(),
        config=_config(maximum_public_resample_attempts=2),
    )

    assert policy.choose_action(observation, environment.legal_actions()).action_id == "bad"
    assert policy.last_decision is None
    assert shared.resamples == 2
    assert policy.usage().as_dict() == {
        "policy_only_decisions": 1,
        "search_decisions": 0,
        "search_fallback_decisions": 1,
        "simulated_transitions": 0,
        "hidden_worlds": 0,
        "public_resample_attempts": 2,
        "public_resample_failures": 1,
    }


def test_search_reduces_depth_equally_to_respect_transition_cap() -> None:
    environment = _AdvancementEnvironment()
    observation = environment.reset(0)
    policy = CombatAdvancementPolicy(
        environment=environment,
        base_policy=_Predictor(),
        config=_config(
            candidate_worlds=2,
            maximum_rollout_steps=10,
            maximum_simulated_transitions_per_decision=4,
        ),
    )

    policy.choose_action(observation, environment.legal_actions())

    assert policy.last_decision is not None
    assert policy.last_decision.effective_rollout_steps == 1
    assert policy.last_decision.simulated_transitions == 4


@pytest.mark.parametrize(
    ("selection_mode", "minimum_advantage", "reason"),
    (("shadow", 0.0, "shadow_mode"), ("apply", 0.9, "below_minimum_advantage")),
)
def test_v2_selection_controls_keep_base_action(
    selection_mode: str,
    minimum_advantage: float,
    reason: str,
) -> None:
    environment = _AdvancementEnvironment()
    observation = environment.reset(0)
    policy = CombatAdvancementPolicy(
        environment=environment,
        base_policy=_Predictor(),
        config=_config(
            schema_version="combat-advancement-config-v2",
            selection_mode=selection_mode,
            minimum_search_advantage=minimum_advantage,
        ),
    )

    assert policy.choose_action(observation, environment.legal_actions()).action_id == "bad"
    assert policy.last_decision is not None
    assert policy.last_decision.search_action.action_id == "good"
    assert policy.last_decision.search_override_recommended is True
    assert policy.last_decision.search_override_executed is False
    assert policy.last_decision.selection_reason == reason
    assert policy.policy_id.startswith("combat-advancement-policy-v2:")


def test_noncombat_decisions_delegate_without_sampling() -> None:
    environment = _AdvancementEnvironment(decision_type=DecisionType.PATH)
    observation = environment.reset(0)
    environment.decision_type = DecisionType.PATH
    observation = environment._observation()
    policy = CombatAdvancementPolicy(
        environment=environment,
        base_policy=_Predictor(),
        config=_config(),
    )

    assert policy.choose_action(observation, environment.legal_actions()).action_id == "bad"
    assert policy.last_decision is None
    assert policy.usage().policy_only_decisions == 1
    assert environment.shared.resamples == 0


def test_config_identity_is_verified() -> None:
    config = _config()
    assert CombatAdvancementConfig.from_mapping(config.as_dict()) == config
    tampered = config.as_dict()
    tampered["maximum_rollout_steps"] = 99
    with pytest.raises(ValueError, match="identity mismatch"):
        CombatAdvancementConfig.from_mapping(tampered)


def test_legacy_config_identity_and_policy_version_are_preserved() -> None:
    config = _config()
    assert "selection_mode" not in config.as_dict()
    assert "minimum_search_advantage" not in config.as_dict()
    assert CombatAdvancementConfig.from_mapping(config.as_dict()) == config
    environment = _AdvancementEnvironment()
    policy = CombatAdvancementPolicy(
        environment=environment,
        base_policy=_Predictor(),
        config=config,
    )
    assert policy.policy_id.startswith("combat-advancement-policy-v1:")
