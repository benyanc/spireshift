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


class PolicyOnlyBudgetController:
    controller_id = "policy-only-controller-v1"

    def choose_tier(self, observation: Observation, remaining_budget: int) -> BudgetTier:
        del observation
        if remaining_budget < BudgetTier.POLICY_ONLY.nominal_cost:
            raise RuntimeError("Whole-run compute budget exhausted")
        return BudgetTier.POLICY_ONLY
