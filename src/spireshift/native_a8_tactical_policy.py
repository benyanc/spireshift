"""Bounded combat planning from the current public menu on the frozen A8 build."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from spireshift.native_a8_boss2_policy import RewardSafeBossTeacher
from spireshift.native_a8_boss_policy import entity_slot
from spireshift.native_a8_combat_branch_policy import intent_damage
from spireshift.native_a8_rescue_policy import subject
from spireshift.native_win4_plan import PLAN
from spireshift.native_win_teacher import card_stats

CONTRACT = "normal_start_act1_tactical_teacher_v3"
GIANT = "WATERFALL_GIANT"
STEAM = "STEAM_ERUPTION_POWER"
DYING_HP = 999_999_999
VULNERABLE = "VULNERABLE_POWER"
ATTACKS = {
    "ANGER",
    "BASH",
    "BLUDGEON",
    "BREAKTHROUGH",
    "HEMOKINESIS",
    "IRON_WAVE",
    "POMMEL_STRIKE",
    "STRIKE_IRONCLAD",
    "THUNDERCLAP",
    "TWIN_STRIKE",
}
PLAYER_POWERS = {
    "DEXTERITY_POWER",
    "FRAIL_POWER",
    "NO_DRAW_POWER",
    "STRENGTH_POWER",
    VULNERABLE,
    "WEAK_POWER",
}
ENEMY_POWERS = {VULNERABLE, "WEAK_POWER", "STRENGTH_POWER", "DEMISE_POWER", STEAM}
BLOCK_CARDS = {"DEFEND_IRONCLAD", "FLAME_BARRIER", "GHOSTLY_ARMOR", "IRON_WAVE", "SHRUG_IT_OFF"}
DRAW_CARDS = {"BATTLE_TRANCE", "POMMEL_STRIKE", "SHRUG_IT_OFF"}
MAX_STATES = 2048
MAX_PLAYS = 6


def status(creature: dict[str, Any], name: str) -> int:
    return int(next((s["amount"] for s in creature["statuses"] if s["definition_id"] == name), 0))


def cost(card: dict[str, Any]) -> int:
    value = str(card.get("cost"))
    return int(value) if value.isdecimal() else 99


@dataclass(frozen=True, slots=True)
class Attack:
    index: int
    slot: int
    cost: int
    damage: int
    hits: int
    hp_cost: int
    vulnerable: int
    targets: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Turn:
    energy: int
    hp: int
    # Per foe: remaining health, block and whether it takes Vulnerable damage.
    foes: tuple[tuple[int, int, bool], ...]
    used: frozenset[int] = frozenset()
    choices: tuple[int, ...] = ()


def attacks(
    public: dict[str, Any], indices: list[int], enemies: list[dict[str, Any]]
) -> list[Attack]:
    result = []
    enemy_slots = [entity_slot(enemy) for enemy in enemies]
    for index in indices:
        action = public["candidates"][index]
        card = subject(action)[1]
        identity = card.get("definition_id")
        slot = entity_slot(card)
        if (
            action["verb"] != "play"
            or identity not in ATTACKS
            or slot is None
            or card.get("existing_enchantment") is not None
            or card.get("star_cost") not in (None, 0, "0")
            or cost(card) == 99
        ):
            continue
        stats = card_stats(card)
        damage = stats.get("damage")
        if type(damage) is not int or damage <= 0:
            continue
        if identity in {"BREAKTHROUGH", "THUNDERCLAP"}:
            targets = tuple(range(len(enemies)))
        else:
            slots = [
                entity_slot(arg["entity"]["properties"])
                for arg in action["arguments"]
                if arg["role"] == "target"
            ]
            if len(slots) != 1 or slots[0] is None or slots[0] not in enemy_slots:
                continue
            targets = (enemy_slots.index(slots[0]),)
        result.append(
            Attack(
                index,
                slot,
                cost(card),
                damage,
                2 if identity == "TWIN_STRIKE" else 1,
                int(stats.get("hploss", 0)),
                int(stats.get("vulnerablepower", 0)),
                targets,
            )
        )
    return sorted(result, key=lambda a: (not a.vulnerable, a.hp_cost, a.cost, a.index))


def advance(turn: Turn, attack: Attack) -> Turn | None:
    if (
        attack.slot in turn.used
        or attack.cost > turn.energy
        or attack.hp_cost >= turn.hp
        or not any(turn.foes[i][0] > 0 for i in attack.targets)
    ):
        return None
    foes = list(turn.foes)
    for i in attack.targets:
        hp, block, vulnerable = foes[i]
        if hp <= 0:
            continue
        hit = attack.damage * 3 // 2 if vulnerable else attack.damage
        damage = hit * attack.hits
        foes[i] = (
            max(0, hp - max(0, damage - block)),
            max(0, block - damage),
            vulnerable or attack.vulnerable > 0,
        )
    return Turn(
        turn.energy - attack.cost,
        turn.hp - attack.hp_cost,
        tuple(foes),
        turn.used | {attack.slot},
        (*turn.choices, attack.index),
    )


def lethal_plan(
    public: dict[str, Any], indices: list[int], combat: dict[str, Any]
) -> tuple[int, ...]:
    enemies = combat["enemies"]
    hero = public["context"]["persistent"]["player"]
    if (
        not enemies
        or any(enemy["max_hp"] == DYING_HP for enemy in enemies)
        or any(s["definition_id"] not in ENEMY_POWERS for e in enemies for s in e["statuses"])
        or any(s["definition_id"] not in PLAYER_POWERS for s in combat["player"]["statuses"])
        or any(r["definition_id"] == "PEN_NIB" for r in hero["relics"])
    ):
        return ()
    # The hand previews include the player's current modifiers. Apply target
    # Vulnerable and block here, without counting draws or hidden successors.
    start = Turn(
        combat["player"]["energy"],
        hero["hp"],
        tuple((e["hp"], e["block"], status(e, VULNERABLE) > 0) for e in enemies),
    )
    available = attacks(public, indices, enemies)
    queue = deque([start])
    seen = {(start.energy, start.hp, start.foes, start.used)}
    best = start
    while queue:
        turn = queue.popleft()
        if len(turn.choices) >= MAX_PLAYS:
            continue
        for attack in available:
            successor = advance(turn, attack)
            if successor is None:
                continue
            if all(hp == 0 for hp, _, _ in successor.foes):
                if successor.hp == start.hp:
                    return successor.choices
                if not best.choices or successor.hp > best.hp:
                    best = successor
                continue
            key = (successor.energy, successor.hp, successor.foes, successor.used)
            if key not in seen:
                if len(seen) >= MAX_STATES:
                    return best.choices
                seen.add(key)
                queue.append(successor)
    return best.choices


def block_value(card: dict[str, Any]) -> int:
    if card.get("definition_id") not in BLOCK_CARDS or card.get("existing_enchantment") is not None:
        return 0
    return int(card_stats(card).get("block", 0))


def pile_cards(context: dict[str, Any], zone_name: str) -> list[dict[str, Any]]:
    return [
        card
        for read in context["reads"]
        if read["kind"] == "combat_piles"
        for zone in read["content"]["zones"]
        if zone["zone"] == zone_name
        for card in zone["cards"]
    ]


def block_plan(
    plays: dict[int, dict[str, Any]], energy: int, needed: int
) -> tuple[int, tuple[int, ...]]:
    """Maximize useful block from distinct visible cards, then save energy."""
    if needed <= 0:
        return 0, ()
    plans: dict[int, tuple[int, tuple[int, ...]]] = {0: (0, ())}
    seen: set[int] = set()
    for index in sorted(plays, key=lambda i: (-block_value(plays[i]), i)):
        card = plays[index]
        gain, price, slot = block_value(card), cost(card), entity_slot(card)
        if gain <= 0 or price == 99 or slot is None or slot in seen:
            continue
        seen.add(slot)
        for spent, (total, choices) in tuple(plans.items()):
            combined = spent + price
            if combined <= energy and total + gain > plans.get(combined, (-1, ()))[0]:
                plans[combined] = (total + gain, (*choices, index))
    spent = min(plans, key=lambda price: (-min(needed, plans[price][0]), price))
    return plans[spent]


def giant_tactics(
    public: dict[str, Any], indices: list[int], combat: dict[str, Any], headbutt: bool
) -> tuple[int, str] | None:
    context = public["context"]
    interaction = context["interaction"]
    candidates = public["candidates"]
    enemy = combat["enemies"][0]
    dying = enemy["max_hp"] == DYING_HP
    if interaction["kind"] == "card_selection" and headbutt:
        choices = {
            i: candidates[i]["arguments"][0]["entity"]["properties"]
            for i in indices
            if candidates[i]["verb"] == "confirm" and len(candidates[i]["arguments"]) == 1
        }
        best = max(choices, key=lambda i: (block_value(choices[i]), -i), default=None)
        if best is not None and block_value(choices[best]) > 0:
            return best, "giant_prepare_block"
    if interaction["kind"] != "combat_turn":
        return None
    end = next((i for i in indices if candidates[i]["verb"] == "end_turn"), None)
    if end is None:
        return None
    plays = {i: subject(candidates[i])[1] for i in indices if candidates[i]["verb"] == "play"}
    potions = {
        subject(candidates[i])[1].get("definition_id"): i
        for i in reversed(indices)
        if candidates[i]["verb"] == "use"
    }
    block = combat["player"]["block"]
    energy = combat["player"]["energy"]
    hp = context["persistent"]["player"]["hp"]
    death_blow = intent_damage(enemy, "DeathBlow")
    incoming = intent_damage(enemy)
    gain, guards = block_plan(plays, energy, incoming - block)
    discard = pile_cards(context, "discard")
    topdeck = next((i for i, c in plays.items() if c["definition_id"] == "HEADBUTT"), None)
    if death_blow:
        if hp + block + gain <= death_blow:
            for potion in ("BLOCK_POTION", "BLOOD_POTION"):
                if potion in potions:
                    return potions[potion], "giant_death_blow_potion"
            draw = next(
                (
                    i
                    for i, card in plays.items()
                    if card.get("definition_id") in DRAW_CARDS and energy > cost(card)
                ),
                None,
            )
            if draw is not None and status(combat["player"], "NO_DRAW_POWER") == 0:
                if (
                    topdeck is not None
                    and energy > cost(plays[topdeck]) + cost(plays[draw])
                    and any(c["definition_id"] in BLOCK_CARDS for c in discard)
                ):
                    return topdeck, "giant_prepare_block"
                return draw, "giant_draw_defense"
        if guards:
            return guards[0], "giant_block_death_blow"
        if hp + block > death_blow:
            return end, "giant_survive_death_blow"
        return end, "giant_death_blow_end_turn"
    if dying:
        # Block expires across the stun. A known Headbutt target can supply
        # next-turn block without assuming an order for the public draw pile.
        if (
            hp <= status(enemy, STEAM)
            and topdeck is not None
            and any(c["definition_id"] in BLOCK_CARDS for c in discard)
        ):
            return topdeck, "giant_prepare_block"
        return end, "giant_wait_for_death_blow"

    lethal = lethal_plan(public, indices, combat)
    if lethal:
        # A direct trigger avoids the ordinary intent and another Steam
        # Eruption increase. The next native menu decides how to survive it.
        return lethal[0], "giant_trigger_death_blow"
    if guards:
        # Spend on Vulnerable setup only when the entire defense still fits.
        if len(guards) == 1:
            available = energy - cost(plays[guards[0]])
            bash = next(
                (
                    i
                    for i, card in plays.items()
                    if card["definition_id"] == "BASH"
                    and cost(card) <= available
                    and enemy["hp"] > 3 * card_stats(card).get("damage", 0) // 2
                ),
                None,
            )
            if bash is not None:
                return bash, "giant_setup_with_block_reserved"
        return guards[0], "giant_preserve_hp"
    return None


def tactical_choice(
    public: dict[str, Any], indices: list[int], *, headbutt: bool = False
) -> tuple[int, str] | None:
    interaction = public["context"]["interaction"]
    if interaction["content"].get("surface", {}).get("selection_contract") == PLAN:
        return None
    combat = interaction["content"].get("context", {})
    encounter = combat.get("encounter_type")
    if encounter == "elite" and interaction["kind"] == "combat_turn":
        plan = lethal_plan(public, indices, combat)
        return (plan[0], "elite_lethal_turn") if plan else None
    if encounter == "boss" and [e["definition_id"] for e in combat.get("enemies", [])] == [GIANT]:
        return giant_tactics(public, indices, combat, headbutt)
    return None


class TacticalTeacher(RewardSafeBossTeacher):
    headbutt = False

    def choose(self, frame: dict[str, Any]) -> dict[str, Any]:
        proposal = super().choose(frame)
        if proposal["navigation_only"]:
            return proposal
        public = frame["public_input"]
        _, indices, _ = self.chooser.navigation.view(public)
        planned = tactical_choice(public, indices, headbutt=self.headbutt)
        if planned is None:
            return proposal
        selected, reason = planned
        if selected != proposal["action_index"]:
            proposal = self.replace_choice(frame, proposal, indices, selected, reason)
        assert self.pending is not None
        _, _, trial = self.pending
        choice = {
            **proposal,
            "behavior": CONTRACT,
            "tactical_reason": reason,
            "log_probability": 0.0,
            "policy_log_probability": None,
            "draw_used": False,
            "ordinary_PPO_eligible": False,
        }
        self.pending = frame, choice, trial
        return choice

    def acknowledge(self, receipt: dict[str, Any]) -> None:
        assert self.pending is not None
        frame, choice, _ = self.pending
        action = frame["public_input"]["candidates"][choice["action_index"]]
        super().acknowledge(receipt)
        self.headbutt = (
            receipt["delivery_domain"] == "native"
            and action["verb"] == "play"
            and subject(action)[1].get("definition_id") == "HEADBUTT"
        )
