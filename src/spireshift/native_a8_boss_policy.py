"""Deck preparation and bounded public-menu planning for the Act 1 boss."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from spireshift.native_a8_rescue_policy import Act1Teacher, subject
from spireshift.native_win4_plan import PLAN
from spireshift.native_win_teacher import POWERS, card_stats, number

CONTRACT = "normal_start_act1_boss_teacher_v1"
BEAM_WIDTH = 12
PLAN_DEPTH = 4
MAX_MOVES = 18
SCALING = {"RAMPAGE": 10.0, "DEMON_FORM": 22.0, "INFLAME": 17.0}
HP_CARDS = {"BLOOD_WALL", "BLOODLETTING", "BREAKTHROUGH", "HEMOKINESIS", "OFFERING"}


def description(card: dict[str, Any]) -> str:
    return next(
        (
            str(view["description"])
            for view in card.get("public_card_views", {}).values()
            if view.get("description")
        ),
        "",
    )


def direct_damage(card: dict[str, Any], stats: dict[str, Any]) -> float:
    damage = max(number(stats.get("damage")), number(stats.get("calculateddamage")))
    # This card's frozen visible text says twice; the exported damage is per hit.
    return damage * (2 if card.get("definition_id") == "TWIN_STRIKE" else 1)


def reward_value(card: dict[str, Any], deck: list[dict[str, Any]], hp: int) -> float:
    stats = card_stats(card)
    ident = str(card.get("definition_id", ""))
    attack_count = sum(c.get("type") == "Attack" and c.get("rarity") != "Basic" for c in deck)
    cost = number(card.get("cost"), 2)
    damage = direct_damage(card, stats)
    if ident in {"WHIRLWIND", "SWORD_BOOMERANG"}:
        damage *= 2
    area = "all enemies" in description(card).lower()
    block = number(stats.get("block"))
    draw = max(number(stats.get(k)) for k in ("cards", "draw", "carddraw"))
    power = SCALING.get(ident, 0.0)
    if ident == "INFERNO" and sum(c.get("definition_id") in HP_CARDS for c in deck) >= 2:
        power = 9.0
    value = damage * (1.2 if attack_count < 3 else 1.0) * (1.2 if area else 1.0)
    value += block * (0.9 if hp < 30 else 0.65) + 2.5 * draw
    value += 1.7 * number(stats.get("vulnerablepower")) + power
    value -= number(stats.get("hploss")) * (2.2 if hp < 30 else 1.0)
    if card.get("type") in {"Curse", "Status"}:
        return -100.0
    repeats = sum(1 for c in deck if c.get("definition_id") == ident)
    return value / (0.65 + 0.55 * cost) - 2 * repeats


def reward_choice(public: dict[str, Any], indices: list[int], proposed: int) -> int:
    context = public["context"]
    actions = public["candidates"]
    hp = context["persistent"]["player"]["hp"]
    deck: list[dict[str, Any]] = next(
        (r["content"]["cards"] for r in context["reads"] if r["kind"] == "run_deck"), []
    )
    offered = [
        i for i in indices if actions[i]["verb"] == "select" and subject(actions[i])[0] == "card"
    ]
    if not offered:
        return proposed
    selected = max(offered, key=lambda i: (reward_value(subject(actions[i])[1], deck, hp), -i))
    if reward_value(subject(actions[selected])[1], deck, hp) >= 7:
        return selected
    return next((i for i in indices if actions[i]["label"] == "Skip"), proposed)


@dataclass(frozen=True)
class Move:
    index: int
    slot: int
    cost: float
    consumes_remaining_energy: bool
    energy: float
    hp_loss: float
    block: float
    damage: tuple[float, ...]
    value: float
    setup: float


@dataclass(frozen=True)
class Turn:
    choices: tuple[int, ...]
    used: frozenset[int]
    energy: float
    hp: float
    block: float
    foes: tuple[tuple[float, float], ...]
    value: float = 0.0


def entity_slot(row: dict[str, Any]) -> int | None:
    slot = (row.get("entity_id") or {}).get("public_slot")
    return slot if type(slot) is int else None


def moves(
    actions: list[dict[str, Any]],
    indices: list[int],
    enemies: list[dict[str, Any]],
    round_number: int,
) -> list[Move]:
    result = []
    for i in indices:
        action = actions[i]
        if action["verb"] != "play":
            continue
        card = subject(action)[1]
        slot = entity_slot(card)
        if slot is None:
            continue
        stats = card_stats(card)
        views = card.get("public_card_views", {})
        target_type = next(
            (v.get("target_type") for k, v in views.items() if k.startswith("interaction:")),
            None,
        )
        targets = {
            entity_slot(a.get("entity", {}).get("properties", {}))
            for a in action["arguments"]
            if a.get("role") in {"target", "enemy"}
        }
        damage = direct_damage(card, stats)
        ident = str(card.get("definition_id", ""))
        draw = max(number(stats.get(k)) for k in ("cards", "draw", "carddraw"))
        scaling = SCALING.get(ident, 0) if ident != "RAMPAGE" else 4
        if ident not in SCALING and card.get("type") == "Power":
            scaling = POWERS.get(ident, 0) * 0.55
        if round_number > 4 and card.get("type") == "Power":
            scaling *= 0.5
        vulnerable = min(3.0, number(stats.get("vulnerablepower")))
        # Prioritize setup before spending energy. Re-read the real result for
        # dynamic damage, draws, Vulnerable and any nested selection.
        setup = min(2.5, 0.45 * scaling + 0.7 * vulnerable + draw)
        random_damage = min(damage, 6) if ident == "SWORD_BOOMERANG" else 0
        result.append(
            Move(
                i,
                slot,
                number(card.get("cost"), 99),
                card.get("cost") == "X",
                max(0.0, number(stats.get("energy"))),
                max(0.0, number(stats.get("hploss"))),
                max(0.0, number(stats.get("block"))),
                tuple(
                    damage if target_type == "AllEnemies" or entity_slot(e) in targets else 0.0
                    for e in enemies
                ),
                scaling + 2 * draw + 1.8 * vulnerable + random_damage,
                setup,
            )
        )
    return result


def advance(turn: Turn, move: Move) -> Turn | None:
    cost = turn.energy if move.consumes_remaining_energy else move.cost
    if move.slot in turn.used or cost > turn.energy or move.hp_loss >= turn.hp:
        return None
    if move.consumes_remaining_energy and cost <= 0:
        return None
    damage = tuple(
        amount * cost if move.consumes_remaining_energy else amount for amount in move.damage
    )
    if any(damage) and not any(
        amount > 0 and hp > 0 for amount, (hp, _) in zip(damage, turn.foes, strict=True)
    ):
        return None
    foes = tuple(
        (max(0.0, hp - max(0.0, amount - block)), max(0.0, block - amount))
        for (hp, block), amount in zip(turn.foes, damage, strict=True)
    )
    return Turn(
        (*turn.choices, move.index),
        turn.used | {move.slot},
        turn.energy - cost + move.energy,
        turn.hp - move.hp_loss,
        turn.block + move.block,
        foes,
        turn.value + move.value + (move.setup if not turn.choices and turn.energy > cost else 0),
    )


def boss_choice(public: dict[str, Any], indices: list[int], proposed: int) -> int:
    context = public["context"]
    combat = context["interaction"]["content"]["context"]
    player = context["persistent"]["player"]
    hp = float(player["hp"])
    enemies = combat["enemies"]
    actions = public["candidates"]
    start = Turn(
        (),
        frozenset(),
        combat["player"]["energy"],
        hp,
        combat["player"]["block"],
        tuple((e["hp"], e["block"]) for e in enemies),
    )
    danger = tuple(
        sum(
            number(
                intent.get("total_damage"),
                number(intent.get("damage")) * number(intent.get("hits"), 1),
            )
            for intent in e["intents"]
        )
        for e in enemies
    )

    def exposure(turn: Turn) -> float:
        return max(
            0.0,
            sum(d for (remaining, _), d in zip(turn.foes, danger, strict=True) if remaining > 0)
            - turn.block,
        )

    def score(turn: Turn) -> float:
        damage = sum(
            h0 - h + 0.15 * (b0 - b) + (8 + 0.3 * threat if h <= 0 < h0 else 0)
            for (h0, b0), (h, b), threat in zip(start.foes, turn.foes, danger, strict=True)
        )
        lost = hp - turn.hp + exposure(turn)
        health_cost = lost * (1.8 if hp <= 22 else 1.25)
        if exposure(turn) >= turn.hp:
            health_cost += 200 + 4 * (exposure(turn) - turn.hp)
        return damage + turn.value - health_cost

    plays = moves(actions, indices, enemies, combat["round"])
    playable = [(move, turn) for move in plays if (turn := advance(start, move)) is not None]
    ordered = sorted(playable, key=lambda pair: (-score(pair[1]), pair[0].index))[:MAX_MOVES]
    beam = [start]
    best = start
    for _ in range(PLAN_DEPTH):
        successors = [
            next_turn
            for turn in beam
            for move, _ in ordered
            if (next_turn := advance(turn, move)) is not None
        ]
        if not successors:
            break
        distinct: dict[tuple[Any, ...], Turn] = {}
        for turn in sorted(successors, key=lambda item: (-score(item), item.choices)):
            key = (turn.used, turn.energy, turn.hp, turn.block, turn.foes)
            distinct.setdefault(key, turn)
            if len(distinct) >= BEAM_WIDTH:
                break
        beam = list(distinct.values())
        if score(beam[0]) > score(best) + 1e-6:
            best = beam[0]

    uses = {
        subject(actions[i])[1].get("definition_id"): i
        for i in reversed(indices)
        if actions[i]["verb"] == "use" and subject(actions[i])[0] == "potion"
    }
    if exposure(best) > 4 and "BLOCK_POTION" in uses:
        return uses["BLOCK_POTION"]
    if hp * 4 <= player["max_hp"] * 3 and "BLOOD_POTION" in uses:
        return uses["BLOOD_POTION"]
    if combat["round"] <= 2 and sum(e["hp"] for e in enemies) >= 40:
        for potion in ("STRENGTH_POTION", "DEXTERITY_POTION", "LIQUID_BRONZE", "POWER_POTION"):
            if potion in uses:
                return uses[potion]
    if best.choices:
        # Keep an already proposed useful potion. The next menu contains its
        # actual effect or the generated choice owned by the potion.
        return proposed if proposed in uses.values() else best.choices[0]
    return proposed


def intervention(public: dict[str, Any], indices: list[int], proposed: int) -> tuple[int, str]:
    interaction = public["context"]["interaction"]
    content = interaction["content"]
    context = content.get("context", {})
    family = interaction["kind"]
    actions = public["candidates"]
    if content.get("surface", {}).get("selection_contract") == PLAN:
        return proposed, ""
    if (
        family == "reward_claim"
        and actions[proposed]["label"] == "Skip remaining rewards and continue"
    ):
        for kind in ("card", "gold"):
            offered = [i for i in indices if subject(actions[i])[1].get("kind") == kind]
            if offered:
                return offered[0], "boss_preparation"
    if actions[proposed]["verb"] != "use" and (
        family == "card_reward_selection"
        or family == "native_generated_card_choice"
        and context.get("encounter_type") == "boss"
    ):
        return reward_choice(public, indices, proposed), "boss_preparation"
    if family == "combat_turn" and context.get("encounter_type") == "boss":
        return boss_choice(public, indices, proposed), "boss_turn"
    return proposed, ""


class BossTeacher(Act1Teacher):
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
        assert self.pending is not None
        _, _, trial = self.pending
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
