from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from spireshift.core.types import LegalAction, Observation

PUBLIC_NO_OP_FALLBACK_SCHEMA_VERSION = "public-no-op-fallback-v1"


class PublicNoOpActionGuard:
    """Suppress repeatedly unchanged actions while preserving the legal-action contract."""

    controller_id = "public-no-op-action-guard-v1"

    def __init__(self, *, repetition_threshold: int = 2, event_limit: int = 16) -> None:
        if repetition_threshold < 1:
            raise ValueError("No-op fallback repetition threshold must be positive")
        if event_limit < 1:
            raise ValueError("No-op fallback event limit must be positive")
        self.repetition_threshold = repetition_threshold
        self.event_limit = event_limit
        self._unchanged_counts: dict[tuple[str, str], int] = {}
        self._suppressed: dict[str, set[str]] = {}
        self._events: list[dict[str, Any]] = []
        self._invocations = 0
        self._exhausted_state_hashes: set[str] = set()

    def eligible_actions(
        self, observation: Observation, legal_actions: Sequence[LegalAction]
    ) -> tuple[LegalAction, ...]:
        actions = tuple(legal_actions)
        if not actions:
            raise ValueError("No-op fallback cannot filter an empty legal-action set")
        suppressed = self._suppressed.get(observation.state_hash, set())
        if not suppressed:
            return actions
        eligible = tuple(action for action in actions if action.action_id not in suppressed)
        if eligible:
            self._invocations += 1
            return eligible
        self._exhausted_state_hashes.add(observation.state_hash)
        return actions

    def observe_transition(
        self,
        *,
        observation: Observation,
        action: LegalAction,
        next_observation: Observation,
        decision_index: int,
    ) -> None:
        if decision_index < 0:
            raise ValueError("No-op fallback decision index must be non-negative")
        key = (observation.state_hash, action.action_id)
        if observation.state_hash != next_observation.state_hash:
            self._unchanged_counts.pop(key, None)
            return
        count = self._unchanged_counts.get(key, 0) + 1
        self._unchanged_counts[key] = count
        if count != self.repetition_threshold:
            return
        suppressed = self._suppressed.setdefault(observation.state_hash, set())
        if action.action_id in suppressed:
            return
        suppressed.add(action.action_id)
        self._events.append(
            {
                "decision_index": decision_index,
                "state_hash": observation.state_hash,
                "decision_type": observation.decision_type.value,
                "action_id": action.action_id,
                "unchanged_occurrences": count,
            }
        )
        if len(self._events) > self.event_limit:
            del self._events[0]

    def as_dict(self) -> dict[str, Any]:
        suppressed_actions = sum(len(actions) for actions in self._suppressed.values())
        return {
            "schema_version": PUBLIC_NO_OP_FALLBACK_SCHEMA_VERSION,
            "controller_id": self.controller_id,
            "repetition_threshold": self.repetition_threshold,
            "event_limit": self.event_limit,
            "invocations": self._invocations,
            "suppressed_actions": suppressed_actions,
            "exhausted_states": len(self._exhausted_state_hashes),
            "events": list(self._events),
        }
