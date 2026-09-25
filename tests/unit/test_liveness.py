from __future__ import annotations

import hashlib

import pytest

from spireshift.core.types import DecisionType, LegalAction, Observation
from spireshift.liveness import PublicNoOpActionGuard


def _observation(decision_type: DecisionType, label: str) -> Observation:
    return Observation(
        schema_version="observation-v1",
        patch_id="mock-v1",
        decision_type=decision_type,
        public_state={"label": label},
        state_hash=hashlib.sha256(label.encode()).hexdigest(),
    )


@pytest.mark.parametrize(
    "decision_type",
    [
        DecisionType.PATH,
        DecisionType.COMBAT,
        DecisionType.REWARD,
        DecisionType.RELIC_SELECTION,
        DecisionType.SHOP,
    ],
)
def test_public_no_op_guard_suppresses_repeated_action_across_decision_types(
    decision_type: DecisionType,
) -> None:
    guard = PublicNoOpActionGuard(repetition_threshold=2, event_limit=4)
    observation = _observation(decision_type, decision_type.value)
    actions = (LegalAction("first", "choose", {}), LegalAction("second", "choose", {}))

    assert guard.eligible_actions(observation, actions) == actions
    guard.observe_transition(
        observation=observation,
        action=actions[0],
        next_observation=observation,
        decision_index=0,
    )
    assert guard.eligible_actions(observation, actions) == actions
    guard.observe_transition(
        observation=observation,
        action=actions[0],
        next_observation=observation,
        decision_index=1,
    )

    assert guard.eligible_actions(observation, actions) == (actions[1],)
    evidence = guard.as_dict()
    assert evidence["invocations"] == 1
    assert evidence["suppressed_actions"] == 1
    assert evidence["exhausted_states"] == 0
    assert evidence["events"] == [
        {
            "decision_index": 1,
            "state_hash": observation.state_hash,
            "decision_type": decision_type.value,
            "action_id": "first",
            "unchanged_occurrences": 2,
        }
    ]


def test_public_no_op_guard_never_returns_an_empty_action_set() -> None:
    guard = PublicNoOpActionGuard(repetition_threshold=1, event_limit=2)
    observation = _observation(DecisionType.RELIC_SELECTION, "reward")
    action = LegalAction("only", "choose", {})
    guard.observe_transition(
        observation=observation,
        action=action,
        next_observation=observation,
        decision_index=0,
    )

    assert guard.eligible_actions(observation, (action,)) == (action,)
    assert guard.as_dict()["exhausted_states"] == 1


def test_public_no_op_guard_does_not_suppress_state_changing_actions() -> None:
    guard = PublicNoOpActionGuard(repetition_threshold=1, event_limit=2)
    observation = _observation(DecisionType.COMBAT, "before")
    next_observation = _observation(DecisionType.COMBAT, "after")
    action = LegalAction("play", "combat", {})
    guard.observe_transition(
        observation=observation,
        action=action,
        next_observation=next_observation,
        decision_index=0,
    )

    assert guard.eligible_actions(observation, (action,)) == (action,)
    assert guard.as_dict()["suppressed_actions"] == 0
