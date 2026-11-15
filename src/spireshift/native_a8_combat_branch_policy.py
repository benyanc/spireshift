"""Public-menu decisions for the two sealed Act 1 combat diagnostics."""

from __future__ import annotations

from typing import Any

from spireshift.native_a8_boss_policy import boss_choice, direct_damage
from spireshift.native_a8_rescue_policy import subject
from spireshift.native_win_teacher import card_stats

EEL_ATTACKS = ("Play Thunderclap+", "Play Strike on Terror Eel", "Play Strike on Terror Eel")
DEFEND = "DEFEND_IRONCLAD"


def intent_damage(enemy: dict[str, Any], kind: str | None = None) -> int:
    return sum(
        intent.get("total_damage", intent.get("damage", 0) * intent.get("hits", 1))
        for intent in enemy["intents"]
        if kind is None or intent["type"] == kind
    )


def eel_choice(public: dict[str, Any], combat: dict[str, Any], step: int) -> int:
    if step >= len(EEL_ATTACKS):
        raise ValueError("The three Eel attacks did not reach native rewards")
    choices = [
        i
        for i, action in enumerate(public["candidates"])
        if action["verb"] == "play"
        and action["label"] == EEL_ATTACKS[step]
        and subject(action)[1]["cost"] == "1"
    ]
    if (
        combat["round"] != 9
        or combat["player"]["energy"] != 3 - step
        or combat["enemies"][0]["hp"] != (25, 15, 6)[step]
        or len(choices) != (1, 2, 1)[step]
    ):
        raise ValueError("The Eel attack sequence lost an expected legal copy or damage result")
    if step == 0:
        strikes = {
            subject(action)[1]["entity_id"]["public_slot"]
            for action in public["candidates"]
            if action["verb"] == "play"
            and action["label"] == EEL_ATTACKS[1]
            and subject(action)[1]["cost"] == "1"
        }
        if len(strikes) != 2:
            raise ValueError("The Eel root must offer two distinct one-energy Strikes")
    return choices[0]


def giant_choice(public: dict[str, Any], combat: dict[str, Any], previous: str | None) -> int:
    candidates = public["candidates"]
    if public["context"]["interaction"]["kind"] == "card_selection":
        if previous != "Play Headbutt on Waterfall Giant" or any(
            a["verb"] != "confirm" or len(a["arguments"]) != 1 for a in candidates
        ):
            raise ValueError("Unexpected child owner during the Giant defense branch")
        cards = [a["arguments"][0]["entity"]["properties"] for a in candidates]

        def retrieval(index: int) -> tuple[float, float, int]:
            card = cards[index]
            stats = card_stats(card)
            block = float(stats.get("block", 0)) if combat["round"] >= 4 else 0.0
            attack = direct_damage(card, stats) / (1 + float(card["cost"]))
            return block, attack, -index

        return max(range(len(candidates)), key=retrieval)

    enemy = combat["enemies"][0]
    end_turn = next(i for i, a in enumerate(candidates) if a["verb"] == "end_turn")
    plays = {i: subject(a)[1] for i, a in enumerate(candidates) if a["verb"] == "play"}
    incoming = intent_damage(enemy)
    block = combat["player"]["block"]
    blocks = {i: card_stats(card).get("block", 0) for i, card in plays.items()}
    best_block = max(blocks, key=lambda i: (blocks[i], -i), default=end_turn)
    if block < incoming and blocks.get(best_block, 0) > 0:
        return best_block

    # The native dying phase advertises the temporary HP pool and the stun or
    # Death Blow. Only play an attack here for its public draw/retrieval effect.
    if enemy["max_hp"] == 999_999_999:
        piles = next(
            r["content"]["zones"] for r in public["context"]["reads"] if r["kind"] == "combat_piles"
        )
        discard_has_defend = any(
            card["definition_id"] == DEFEND
            for p in piles
            if p["zone"] == "discard"
            for card in p["cards"]
        )
        headbutt = next((i for i, c in plays.items() if c["definition_id"] == "HEADBUTT"), None)
        pommel = next((i for i, c in plays.items() if c["definition_id"] == "POMMEL_STRIKE"), None)
        energy = combat["player"]["energy"]
        if not incoming and headbutt is not None and discard_has_defend:
            return headbutt
        hp = public["context"]["persistent"]["player"]["hp"]
        if incoming >= hp + block and pommel is not None and energy >= 2:
            if headbutt is not None and discard_has_defend and energy >= 3:
                return headbutt
            return pommel
        return end_turn

    attacks = [i for i in plays if blocks[i] == 0]
    return boss_choice(public, [end_turn, *attacks], end_turn)
