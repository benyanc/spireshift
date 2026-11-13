"""Fixed Act 1 teacher on the delivered fitted-policy interface."""

from __future__ import annotations

import copy
from typing import Any

from spireshift.native_live_policy import LivePolicy
from spireshift.native_win4_plan import PLAN
from spireshift.native_win_teacher import card_stats, number, score_action

CONTRACT = "normal_start_act1_survival_teacher_v1"


def subject(action: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    item = action.get("subject") or {}
    return item.get("role"), item.get("properties", {})


def discard(action: dict[str, Any]) -> bool:
    return subject(action)[0] == "potion" and (
        action["verb"] == "discard" or action["label"].startswith("Discard ")
    )


def intervention(
    public: dict[str, Any], indices: list[int], proposed: int
) -> tuple[int, str | None]:
    """Choose on the current effective menu. No manufactured action or hidden state."""
    context = public["context"]
    interaction = context["interaction"]
    family = interaction["kind"]
    content = interaction["content"]
    if content.get("surface", {}).get("selection_contract") == PLAN:
        return proposed, None

    actions = public["candidates"]
    player = context["persistent"]["player"]
    hp, max_hp = player["hp"], player["max_hp"]
    low = hp * 2 <= max_hp
    proposed_action = actions[proposed]

    def rank(candidates: list[int]) -> int:
        return max(candidates, key=lambda i: (score_action(public, i, "defensive"), -i))

    if family == "combat_turn":
        costs = {
            i: number(card_stats(subject(actions[i])[1]).get("hploss"))
            for i in indices
            if actions[i]["verb"] == "play"
        }
        safe = [i for i in indices if costs.get(i, 0) < hp and not discard(actions[i])]
        if not safe:
            return proposed, None
        lethal = costs.get(proposed, 0) >= hp
        if subject(proposed_action)[0] == "potion" and proposed_action["verb"] == "use":
            return proposed, None
        plays = [i for i in safe if actions[i]["verb"] in {"play", "end_turn"}]
        selected = (
            max(
                plays,
                key=lambda i: (
                    score_action(public, i, "defensive") - costs.get(i, 0) * (6 if low else 2),
                    -i,
                ),
            )
            if plays
            else rank(safe)
        )
        if lethal:
            return selected, "hp_spend"
        if actions[selected]["verb"] == "end_turn":
            combat = content.get("context", {})
            incoming = sum(
                number(
                    intent.get("total_damage"),
                    number(intent.get("damage")) * number(intent.get("hits"), 1),
                )
                for enemy in combat.get("enemies", [])
                for intent in enemy.get("intents", [])
            )
            exposed = incoming - number(combat.get("player", {}).get("block"))
            uses = [
                i
                for i in safe
                if actions[i]["verb"] == "use" and subject(actions[i])[0] == "potion"
            ]
            if exposed >= hp and uses:
                return max(
                    uses,
                    key=lambda i: (
                        subject(actions[i])[1].get("definition_id") == "BLOCK_POTION",
                        -i,
                    ),
                ), "potion"
        if selected != proposed:
            reason = (
                "potion"
                if discard(proposed_action)
                else "hp_spend"
                if low and costs.get(proposed, 0) > costs.get(selected, 0)
                else "combat"
            )
            return selected, reason
        return proposed, None

    if family == "rest_site" and low and subject(proposed_action)[1].get("option_id") == "SMITH":
        heals = [i for i in indices if subject(actions[i])[1].get("option_id") == "HEAL"]
        if heals:
            return heals[0], "rest"
    if family == "reward_claim" and (
        discard(proposed_action)
        or proposed_action["label"] == "Skip remaining rewards and continue"
    ):
        potions = [i for i in indices if subject(actions[i])[1].get("kind") == "potion"]
        if potions and len(player["potions"]) < player["max_potion_slots"]:
            return potions[0], "potion"
    if discard(proposed_action):
        keep = [i for i in indices if not discard(actions[i])]
        if keep:
            return rank(keep), "potion"
    if family == "event_option" and subject(proposed_action)[1].get("will_kill_player") is True:
        alternatives = [
            i for i in indices if subject(actions[i])[1].get("will_kill_player") is not True
        ]
        if alternatives:
            return rank(alternatives), "event"
    if (
        family == "map_navigation"
        and low
        and subject(proposed_action)[1].get("point_type") == "elite"
    ):
        paths = [
            i
            for i in indices
            if subject(actions[i])[1].get("point_type")
            in {
                "restsite",
                "rest_site",
                "monster",
                "unknown",
                "shop",
                "treasure",
            }
        ]
        if paths:
            return rank(paths), "route"
    return proposed, None


class Act1Teacher(LivePolicy):
    def choose(self, frame: dict[str, Any]) -> dict[str, Any]:
        proposal = super().choose(frame)
        if proposal["navigation_only"]:
            return proposal
        public = frame["public_input"]
        _, indices, _ = self.chooser.navigation.view(public)
        old = proposal["action_index"]
        selected, reason = intervention(public, indices, old)
        if selected == old:
            return proposal
        assert self.pending is not None and reason is not None
        _, _, trial = self.pending
        # Only the delivered selection commits navigation. The matched draw slot
        # belongs to the observed menu and advances once for either action.
        trial.navigation = copy.deepcopy(self.chooser.navigation)
        trial.navigation.advance(public, selected)
        choice = {
            **proposal,
            "action_index": selected,
            "effective_action_index": indices.index(selected),
            "bound_action_id": frame["actions"][selected]["bound_action_id"],
            "behavior": CONTRACT,
            "reference_action_index": old,
            "intervention": reason,
            "log_probability": 0.0,
            "policy_log_probability": None,
            "draw_used": False,
            "ordinary_PPO_eligible": False,
        }
        self.pending = frame, choice, trial
        return choice
