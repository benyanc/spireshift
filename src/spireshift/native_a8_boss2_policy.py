"""Keep the boss teacher's choices consistent with delivered reward history."""

from __future__ import annotations

import copy
from typing import Any

from spireshift.native_a8_boss_policy import intervention as boss_intervention
from spireshift.native_a8_rescue_policy import Act1Teacher, subject

CONTRACT = "normal_start_act1_boss_teacher_reward_progress_v2"
CONTINUE = ("Skip remaining rewards and continue", "Continue from rewards")
DIAGNOSTIC_DECLINE = "diagnostic_first_card_reward_decline"


def declined(action: dict[str, Any]) -> bool:
    return action.get("history", {}).get("card_reward_declined") is True


def intervention(public: dict[str, Any], indices: list[int], proposed: int) -> tuple[int, str]:
    if public["context"]["interaction"]["kind"] != "reward_claim":
        return boss_intervention(public, indices, proposed)

    actions = public["candidates"]
    remaining = [i for i in indices if not declined(actions[i])]
    if proposed in remaining:
        return boss_intervention(public, remaining, proposed)

    # The public converter marks the exact offer after the native Skip receipt.
    # Reopening it cannot advance the room. Anchor the same reward preferences
    # at the available continuation, so a different card or gold is still legal.
    exit_index = next((i for i in remaining if actions[i]["label"] in CONTINUE), None)
    if exit_index is None:
        claim = next((i for i in remaining if subject(actions[i])[0] == "reward"), None)
        if claim is None:
            raise ValueError("Declined card reward has no current continuation or other reward")
        return claim, "declined_reward_progress"
    selected, _ = boss_intervention(public, remaining, exit_index)
    return selected, "declined_reward_progress"


class RewardSafeBossTeacher(Act1Teacher):
    def replace_choice(
        self,
        frame: dict[str, Any],
        proposal: dict[str, Any],
        indices: list[int],
        selected: int,
        reason: str,
    ) -> dict[str, Any]:
        assert self.pending is not None
        _, _, trial = self.pending
        trial.navigation = copy.deepcopy(self.chooser.navigation)
        trial.navigation.advance(frame["public_input"], selected)
        choice = {
            **proposal,
            "action_index": selected,
            "effective_action_index": indices.index(selected),
            "bound_action_id": frame["actions"][selected]["bound_action_id"],
            "behavior": CONTRACT,
            "reference_action_index": proposal["action_index"],
            "intervention": reason,
            "log_probability": 0.0,
            "policy_log_probability": None,
            "draw_used": False,
            "ordinary_PPO_eligible": False,
        }
        self.pending = frame, choice, trial
        return choice

    def choose(self, frame: dict[str, Any]) -> dict[str, Any]:
        proposal = super().choose(frame)
        if proposal["navigation_only"]:
            return proposal
        public = frame["public_input"]
        _, indices, _ = self.chooser.navigation.view(public)
        selected, reason = intervention(public, indices, proposal["action_index"])
        if selected == proposal["action_index"]:
            return proposal
        return self.replace_choice(frame, proposal, indices, selected, reason)


class DeclineProbe(RewardSafeBossTeacher):
    """One explicitly scripted legal Skip on a disjoint diagnostic normal start."""

    decline_delivered = False

    def choose(self, frame: dict[str, Any]) -> dict[str, Any]:
        proposal = super().choose(frame)
        public = frame["public_input"]
        if (
            self.decline_delivered
            or public["context"]["interaction"]["kind"] != "card_reward_selection"
        ):
            return proposal
        _, indices, _ = self.chooser.navigation.view(public)
        skip = next((i for i in indices if public["candidates"][i]["label"] == "Skip"), None)
        if skip is None:
            return proposal
        return self.replace_choice(frame, proposal, indices, skip, DIAGNOSTIC_DECLINE)

    def acknowledge(self, receipt: dict[str, Any]) -> None:
        assert self.pending is not None
        is_decline = self.pending[1].get("intervention") == DIAGNOSTIC_DECLINE
        super().acknowledge(receipt)
        self.decline_delivered |= is_decline
