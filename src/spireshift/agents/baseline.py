from __future__ import annotations

from collections.abc import Sequence

from spireshift.core.types import BudgetTier, DecisionType, LegalAction, Observation


class TerminalVictoryPolicy:
    """A transparent baseline that prefers terminal win probability over Act 1 survival."""

    policy_id = "terminal-victory-baseline-v1"

    def choose_action(
        self, observation: Observation, legal_actions: Sequence[LegalAction]
    ) -> LegalAction:
        by_id = {action.action_id: action for action in legal_actions}
        if "elite_path" in by_id:
            return by_id["elite_path"]
        if "face_boss" in by_id:
            return by_id["face_boss"]
        if not legal_actions:
            raise ValueError("Policy cannot act without legal actions")
        return legal_actions[0]


class SearchRolloutPolicy(TerminalVictoryPolicy):
    """Deterministic search continuation that completes multi-select states."""

    policy_id = "terminal-victory-search-rollout-v1"

    def choose_action(
        self, observation: Observation, legal_actions: Sequence[LegalAction]
    ) -> LegalAction:
        if observation.decision_type is DecisionType.CARD_SELECTION:
            if not legal_actions:
                raise ValueError("Policy cannot act without legal actions")
            return legal_actions[-1]
        return super().choose_action(observation, legal_actions)


class ProgressBootstrapPolicy(TerminalVictoryPolicy):
    """Public-state curriculum policy for collecting non-degenerate STS2 labels.

    This policy is deliberately versioned separately from the terminal-victory baseline. Its
    choices may be used to bootstrap representations and a cheap policy, but they are never
    reported as terminal-victory reward or readiness evidence.
    """

    policy_id = "public-progress-bootstrap-v1"

    # Taken from the pinned EvanGambit ``starter-aggressive`` lower-bound policy. Keeping the
    # small table here avoids importing backend-private state or its optional training stack.
    _STARTER_AGGRESSIVE_PRIORITY = (30, 472, 13, 358, 508, 519, 18, 433, 137)
    _HAND_ID_INDICES = tuple(range(8, 28, 2))

    def choose_action(
        self, observation: Observation, legal_actions: Sequence[LegalAction]
    ) -> LegalAction:
        if not legal_actions:
            raise ValueError("Policy cannot act without legal actions")
        if observation.decision_type in {
            DecisionType.CARD_SELECTION,
            DecisionType.COMBAT_SELECTION,
        }:
            return legal_actions[-1]
        if observation.decision_type is DecisionType.COMBAT:
            aggressive = self._starter_aggressive_action(observation, legal_actions)
            return aggressive if aggressive is not None else legal_actions[-1]
        if observation.decision_type is DecisionType.REST_SITE:
            hp = _public_integer(observation, "player_hp")
            maximum = _public_integer(observation, "player_max_hp")
            preferred = 0 if hp is not None and maximum and hp * 2 < maximum else 1
            selected = _action_index(legal_actions, preferred)
            return selected if selected is not None else legal_actions[0]
        if observation.decision_type is DecisionType.PATH:
            selected = self._preferred_map_action(observation, legal_actions)
            return selected if selected is not None else legal_actions[0]
        return legal_actions[0]

    def _starter_aggressive_action(
        self,
        observation: Observation,
        legal_actions: Sequence[LegalAction],
    ) -> LegalAction | None:
        raw = observation.public_state.get("observation_vector")
        if not isinstance(raw, list):
            return None
        hand_ids = [
            raw[index]
            for index in self._HAND_ID_INDICES
            if index < len(raw) and isinstance(raw[index], int) and not isinstance(raw[index], bool)
        ]
        by_index = {
            index: action
            for action in legal_actions
            for index in [_payload_integer(action, "action_index")]
            if index is not None
        }
        for card_id in self._STARTER_AGGRESSIVE_PRIORITY:
            for hand_index, observed_id in enumerate(hand_ids):
                if observed_id == card_id and hand_index in by_index:
                    return by_index[hand_index]
        return None

    def _preferred_map_action(
        self,
        observation: Observation,
        legal_actions: Sequence[LegalAction],
    ) -> LegalAction | None:
        choices = observation.public_state.get("map_choices")
        if not isinstance(choices, list):
            return None
        # Elite and relic nodes expose useful high-upside curriculum states. A low-HP run prefers
        # a rest node first, but otherwise does not silently turn the final objective into survival.
        hp = _public_integer(observation, "player_hp")
        maximum = _public_integer(observation, "player_max_hp")
        priorities = (3, 2, 5) if hp is not None and maximum and hp * 3 < maximum else (2, 5, 1)
        by_index = {
            index: action
            for action in legal_actions
            for index in [_payload_integer(action, "action_index")]
            if index is not None
        }
        for node_type in priorities:
            for index, choice in enumerate(choices):
                if (
                    isinstance(choice, dict)
                    and choice.get("node_type") == node_type
                    and index in by_index
                ):
                    return by_index[index]
        return None


def _payload_integer(action: LegalAction, key: str) -> int | None:
    value = action.payload.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _action_index(actions: Sequence[LegalAction], index: int) -> LegalAction | None:
    return next(
        (action for action in actions if _payload_integer(action, "action_index") == index),
        None,
    )


def _public_integer(observation: Observation, key: str) -> int | None:
    value = observation.public_state.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


class PolicyOnlyBudgetController:
    controller_id = "policy-only-controller-v1"

    def choose_tier(self, observation: Observation, remaining_budget: int) -> BudgetTier:
        del observation
        if remaining_budget < BudgetTier.POLICY_ONLY.nominal_cost:
            raise RuntimeError("Whole-run compute budget exhausted")
        return BudgetTier.POLICY_ONLY
