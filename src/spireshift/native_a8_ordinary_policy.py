"""Extend the pinned tactical teacher to supported ordinary combat turns."""

from __future__ import annotations

from typing import Any

from spireshift.native_a8_tactical_policy import TacticalTeacher, lethal_plan
from spireshift.native_win4_plan import PLAN

CONTRACT = "normal_start_act1_ordinary_lethal_v4"
REASON = "ordinary_lethal_turn"


def ordinary_lethal_plan(public: dict[str, Any], indices: list[int]) -> tuple[int, ...]:
    interaction = public["context"]["interaction"]
    content = interaction["content"]
    combat = content.get("context", {})
    if (
        interaction["kind"] != "combat_turn"
        or combat.get("encounter_type") != "normal"
        or content.get("surface", {}).get("selection_contract") == PLAN
    ):
        return ()

    # Demon Form triggers at turn start. Plating acts at turn boundaries.
    # The current Strength preview and existing enemy block still count.
    player = combat["player"]
    current_turn = {
        **combat,
        "player": {
            **player,
            "statuses": [s for s in player["statuses"] if s["definition_id"] != "DEMON_FORM_POWER"],
        },
        "enemies": [
            {
                **enemy,
                "statuses": [s for s in enemy["statuses"] if s["definition_id"] != "PLATING_POWER"],
            }
            for enemy in combat["enemies"]
        ],
    }
    return lethal_plan(public, indices, current_turn)


class OrdinaryLethalTeacher(TacticalTeacher):
    def choose(self, frame: dict[str, Any]) -> dict[str, Any]:
        proposal = super().choose(frame)
        if proposal["navigation_only"]:
            return proposal
        public = frame["public_input"]
        _, indices, _ = self.chooser.navigation.view(public)
        plan = ordinary_lethal_plan(public, indices)
        if not plan:
            return proposal
        if plan[0] != proposal["action_index"]:
            proposal = self.replace_choice(frame, proposal, indices, plan[0], REASON)
        assert self.pending is not None
        _, _, trial = self.pending
        choice = {
            **proposal,
            "behavior": CONTRACT,
            "tactical_reason": REASON,
            "log_probability": 0.0,
            "policy_log_probability": None,
            "draw_used": False,
            "ordinary_PPO_eligible": False,
        }
        self.pending = frame, choice, trial
        return choice
