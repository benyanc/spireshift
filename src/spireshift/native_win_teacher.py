"""Declared public-only heuristic teachers; no future state or fixture metadata."""

from __future__ import annotations

import copy
import math
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import validate_public_input
from spireshift.native_live_policy import LivePolicy
from spireshift.native_win_plan import TEACHERS

POWERS = {
    "INFLAME": 16.0,
    "DEMON_FORM": 22.0,
    "BARRICADE": 38.0,
    "FEEL_NO_PAIN": 15.0,
    "DARK_EMBRACE": 17.0,
    "CORRUPTION": 34.0,
}


def validate_student_input(public: dict[str, Any]) -> None:
    validate_public_input(public)
    forbidden = {
        "rng_state",
        "save_json",
        "save_path",
        "scenario",
        "seed_pool",
        "teacher_outcome",
        "future_observation",
        "private_setup_identity",
    }

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if forbidden & value.keys() or any(str(k).startswith("private_") for k in value):
                raise ValueError("Private curriculum setup/teacher data reached student input")
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(public)


def number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def card_stats(properties: dict[str, Any]) -> dict[str, Any]:
    result = dict(properties.get("stats") or {})
    for key, view in properties.get("public_card_views", {}).items():
        if key.startswith("interaction:") and isinstance(view, dict):
            result.update(view.get("stats") or {})
    return {str(k).lower(): v for k, v in result.items()}


def card_value(properties: dict[str, Any]) -> float:
    card = properties.get("card", properties)
    stats = card_stats(card)
    damage = max(number(stats.get(k)) for k in ("damage", "calculateddamage"))
    block = number(stats.get("block"))
    value = damage + block + 5 * number(stats.get("cards"))
    value += POWERS.get(card.get("definition_id", ""), 0.0)
    if card.get("rarity") == "Basic":
        value -= 5
    if card.get("type") in {"Curse", "Status"}:
        value -= 50
    return value / max(1, number(card.get("cost"), 1))


def score_action(public: dict[str, Any], index: int, variant: str) -> float:
    if variant not in TEACHERS:
        raise ValueError("Unknown prospectively declared teacher")
    action = public["candidates"][index]
    interaction = public["context"]["interaction"]
    family = interaction["kind"]
    content = interaction["content"]
    combat = content.get("context", {})
    persistent = public["context"]["persistent"]["player"]
    hp = number(persistent.get("hp"))
    maximum = max(1, number(persistent.get("max_hp"), 80))
    ratio = hp / maximum
    subject = action.get("subject") or {}
    properties = subject.get("properties", {})
    verb = action["verb"]
    label = str(action.get("label") or subject.get("label") or "").lower()
    if family == "combat_turn":
        if verb == "end_turn":
            return 0.0
        if "discard" in verb or "discard" in label:
            return -100.0
        stats = card_stats(properties)
        ident = properties.get("definition_id", "")
        enemies = combat.get("enemies", [])
        incoming = sum(
            number(i.get("total_damage"), number(i.get("damage")) * number(i.get("hits"), 1))
            for e in enemies
            for i in e.get("intents", [])
            if isinstance(i, dict)
        )
        player_block = number(combat.get("player", {}).get("block"))
        statuses = {
            p.get("definition_id"): number(p.get("amount"))
            for p in combat.get("player", {}).get("statuses", [])
        }
        retains_block = statuses.get("BARRICADE_POWER", 0) > 0
        needed = max(0.0, incoming - player_block)
        damage = max(number(stats.get(k)) for k in ("damage", "calculateddamage"))
        if ident == "WHIRLWIND":
            energy = number(combat.get("player", {}).get("energy"))
            if energy <= 0:
                return -50.0
            damage *= energy * len(enemies)
        if ident == "SWORD_BOOMERANG":
            damage *= max(3.0, number(stats.get("repeats"), 3))
        block = number(stats.get("block"))
        if ident == "ENTRENCH":
            block = player_block
        draw = max(number(stats.get(k)) for k in ("cards", "draw", "carddraw"))
        target: dict[str, Any] = next(
            (
                a.get("entity", {}).get("properties", {})
                for a in action.get("arguments", [])
                if a.get("role") in {"target", "enemy"}
            ),
            {},
        )
        target_hp = number(target.get("hp", target.get("current_hp")), 9999)
        damage_weight = 1.4 if variant == "balanced" else 1.1 if variant == "scaling" else 0.9
        block_weight = 2.6 if variant == "defensive" else 1.8
        value = damage_weight * min(damage, target_hp) + block_weight * min(block, needed)
        if retains_block:
            value += block * (2.0 if variant == "scaling" else 1.0)
        value += 5 * draw + 0.05 * block
        if 0 < target_hp <= damage:
            value += 30 + min(incoming, 30)
        if needed >= hp:
            value += 50 * min(block, needed) / max(1, needed)
        power = POWERS.get(ident, 0.0)
        if ident == "DEMON_FORM" and number(combat.get("round")) > 3:
            power *= 0.2
        value += power * (1.7 if variant == "scaling" else 1.0)
        # Visible fixed card semantics supplement exported dynamic native numbers.
        if ident in {"BATTLE_TRANCE", "POMMEL_STRIKE", "SHRUG_IT_OFF"}:
            value += 9 if ident == "BATTLE_TRANCE" else 4
        if ident == "OFFERING":
            value += 30 if hp > 15 else -30
        # Build/double block before converting it to damage. Re-score against
        # the new native hand and current energy after every accepted action.
        if ident == "BODY_SLAM" and any(
            (a.get("subject") or {}).get("properties", {}).get("definition_id") == "ENTRENCH"
            for a in public["candidates"]
        ):
            value -= min(80, player_block * 1.5)
        if ident in {"BURNING_PACT", "SECOND_WIND", "FIEND_FIRE"}:
            value -= 5  # Do not exhaust future resources merely to empty the hand.
        if subject.get("role") == "potion":
            value += 25 if ratio < 0.45 or combat.get("encounter_type") == "boss" else -30
        return value + 0.1
    if family == "map_navigation":
        kind = properties.get("point_type", "")
        return {
            "rest_site": 16 if ratio < 0.65 else 6,
            "shop": 10 if number(persistent.get("gold")) > 150 else 1,
            "treasure": 14,
            "unknown": 7,
            "event": 7,
            "monster": 8,
            "elite": 10 if ratio > 0.85 else -3,
            "boss": 20,
            "ancient": 15,
        }.get(kind, 1)
    if family == "rest_site":
        return {"HEAL": 20 if ratio < 0.7 else 1, "SMITH": 12}.get(properties.get("option_id"), 0)
    if family == "card_reward_selection":
        return card_value(properties) if properties.get("definition_id") else 3.0
    if family == "shop_inventory":
        if not properties:
            return 2.0
        if properties.get("affordable") is False or properties.get("can_purchase") is False:
            return -1000.0
        value = card_value(properties)
        if subject.get("role") == "relic":
            value = 20
        return value - number(properties.get("price")) / 12
    if family == "event_option":
        if properties.get("will_kill_player") is True:
            return -10000
        if properties.get("is_proceed") is True:
            return 1
        return 10 + (5 if "heal" in label and ratio < 0.65 else 0)
    if "selection" in family:
        card = properties
        if not card:
            card = next(
                (
                    a.get("entity", {}).get("properties", {})
                    for a in action.get("arguments", [])
                    if a.get("role") == "selected_card"
                ),
                {},
            )
        purpose = str(content.get("surface", {}).get("purpose", "")).lower()
        return (
            -card_value(card)
            if any(x in purpose for x in ("remove", "exhaust"))
            else card_value(card)
        )
    if family == "reward_claim":
        if properties.get("enabled") is False or (
            properties.get("kind") == "card"
            and action.get("history", {}).get("card_reward_declined") is True
        ):
            return -1000.0
        return 2 if subject == {} else 12
    if family == "treasure_room":
        return 10 if verb in {"open", "activate", "select", "confirm"} else 1
    return 2 if verb in {"confirm", "activate", "select", "open"} else 1


class TeacherPolicy(LivePolicy):
    def __init__(self, model: Any, score: Any, seed: str, variant: str) -> None:
        super().__init__(model, score, seed)
        if variant not in TEACHERS:
            raise ValueError("Unknown teacher variant")
        self.variant = variant

    def choose(self, frame: dict[str, Any]) -> dict[str, Any]:
        if self.failed or self.pending is not None or frame.get("terminal") is not False:
            raise ValueError("Teacher requires a current nonterminal acknowledged menu")
        public = frame["public_input"]
        validate_student_input(public)
        trial = copy.deepcopy(
            self.chooser, {id(self.model): self.model, id(self.score): self.score}
        )
        combat_owned = trial.combat(public)
        effective, indices, forced = trial.navigation.view(public)
        selected = max(
            range(len(indices)), key=lambda i: (score_action(effective, i, self.variant), -i)
        )
        action = indices[selected]
        result = {
            "action_index": action,
            "effective_action_index": selected,
            "public_input_id": manifest_identifier(public),
            "model_id": self.model.model_id,
            "binding_id": frame["binding_id"],
            "bound_action_id": frame["actions"][action]["bound_action_id"],
            "behavior": "public_curriculum_teacher_v1",
            "teacher_variant": self.variant,
            "navigation_only": forced,
            "combat_owned": combat_owned,
            "log_probability": 0.0,
            "ordinary_PPO_eligible": False,
            "student_inputs_public_only": True,
            "optimizer_updates": 0,
        }
        trial.navigation.advance(public, action)
        self.pending = frame, result, trial
        return result
