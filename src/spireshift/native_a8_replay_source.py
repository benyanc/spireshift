"""Read a continuous Spire Codex journal and recover recorded choice intents."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from spireshift.native_flow_inputs_v12 import canonical_seed

BUILD = "v0.111.0+41cef1ea"
MAX_BYTES = 8_000_000


def definition(label: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", label.upper()).strip("_")


@dataclass(frozen=True)
class Intent:
    kind: str
    record: dict[str, Any]
    offer: dict[str, Any] | None = None
    hand: tuple[tuple[int, str], ...] = ()
    enemies: tuple[tuple[int, str], ...] = ()
    generated: frozenset[int] = frozenset()
    returns: tuple[tuple[int, str], ...] = ()
    discard: tuple[tuple[int, str], ...] = ()
    transform_order: tuple[int, ...] = ()
    enchantments: tuple[tuple[int, str | None], ...] = ()
    unseen_returns: tuple[tuple[str, str | None], ...] = ()
    unplaced_cards: tuple[str, ...] = ()
    dialogue_only: bool = False


@dataclass(frozen=True)
class Journal:
    seed: str
    header: dict[str, Any]
    starting_hp: int
    act: str
    boss: str
    end: dict[str, Any]
    exits: frozenset[tuple[int, int]]
    intents: tuple[Intent, ...]
    reward_names: dict[tuple[str, str], str] = field(default_factory=dict)
    pre_architect_hp: int | None = None


def read(path: Path) -> Journal:
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Replay journal exceeds the declared size bound")
    rows = [json.loads(line) for line in raw.splitlines()]
    if not rows or any(not isinstance(r, dict) or r.get("s") != i for i, r in enumerate(rows)):
        raise ValueError("Require contiguous ordered source records")
    first, end = rows[0], rows[-1]
    if (
        first.get("t") != "header"
        or first.get("build_id_full") != BUILD
        or first.get("replay_version") != 7
        or first.get("character") != "IRONCLAD"
        or first.get("ascension") != 8
        or first.get("game_mode") != "standard"
        or first.get("player_count") != 1
        or first.get("floor") != 0
        or first.get("act") != 1
        or first.get("reloads") != 0
        or first.get("full_console") is not False
        or first.get("modifiers") != []
        or any(m.get("affects_gameplay") is not False for m in first["mods"])
        or any(r["t"] in {"header", "resume", "end"} for r in rows[1:-1])
        or end.get("t") != "end"
        or end.get("capture_status") != "complete"
    ):
        raise ValueError("Require one complete exact-build, reload-free solo Ironclad/A8 journal")
    combats = [r for r in rows if r["t"] in {"combat_start", "combat_end"}]
    if any(
        r.get("attempt_id") != 0 or (r["t"] == "combat_end" and r.get("result") != "victory")
        for r in combats
    ):
        raise ValueError("Require one successful source attempt per fight")
    starts = [r["combat_id"] for r in combats if r["t"] == "combat_start"]
    ends = [r["combat_id"] for r in combats if r["t"] == "combat_end"]
    if not starts or starts != ends or len(starts) != len(set(starts)):
        raise ValueError("Require a complete ordered set of source fights")
    acts = [r for r in rows if r["t"] == "act"]
    maps = [r for r in rows if r["t"] == "map"]
    if [r["act"] for r in acts] != [1, 2, 3] or [r["act"] for r in maps] != [1, 2, 3]:
        raise ValueError("The journal must contain all three acts")
    return Journal(
        canonical_seed(first["seed"]),
        first,
        next(r["hp"] for r in rows[1:] if r["t"] == "hp" and r["dst"] == "player"),
        acts[0]["name"],
        maps[0]["boss"],
        end,
        frozenset((r["act"], r["floor"]) for r in rows if r["t"] == "room_exit"),
        compile_intents(rows),
        pre_architect_hp=next(
            (
                r["hp"]
                for r in reversed(rows[combats[-1]["s"] + 1 : -1])
                if r["t"] == "hp" and r["dst"] == "player"
            ),
            None,
        ),
    )


def unlogged_returns(rows: list[dict[str, Any]]) -> tuple[dict[int, dict[int, str]], set[int]]:
    """Find prior physical copies evidenced in a later hand without a draw."""
    turns: dict[int, dict[int, str]] = {}
    unfinished_hands: set[int] = set()
    seen: dict[int, str] = {}
    retained: set[int] = set()
    arrivals: set[int] = set()
    witnesses: set[int] = set()
    start: int | None = None
    flushed = False
    for index, r in enumerate(rows):
        tag = r["t"]
        if tag == "combat_start":
            seen.clear()
            retained.clear()
            arrivals.clear()
            witnesses.clear()
            flushed = False
            start = index
        elif start is not None:
            if tag in {"draw", "generate"}:
                arrivals.add(r["c"])
                seen[r["c"]] = r["id"]
            elif tag == "transform":
                witnesses.add(r["from_c"])
                arrivals.add(r["to_c"])
                seen[r["to_c"]] = r["to_id"]
            elif tag == "play" and r.get("auto") is False and r.get("play_index") == 0:
                witnesses.add(r["c"])
            elif tag == "flush":
                witnesses.update(r["flushed_c"] + r["retained_c"])
                retained = set(r["retained_c"])
                flushed = True
            elif tag == "exhaust" and r.get("ethereal") is True:
                witnesses.add(r["c"])
            elif tag == "combat_end" or (tag == "end_turn" and r["side"] == "player"):
                turns[start] = {
                    cid: seen[cid] for cid in sorted(witnesses - arrivals) if cid in seen
                }
                if tag == "combat_end" and not flushed and turns[start]:
                    unfinished_hands.add(start)
                arrivals, witnesses = set(retained), set()
                retained.clear()
                flushed = False
                start = None if tag == "combat_end" else index
    return turns, unfinished_hands


def compile_intents(rows: list[dict[str, Any]]) -> tuple[Intent, ...]:
    offers = {r["decision_id"]: r for r in rows if r["t"] == "decision"}
    outcomes = {r["decision_id"]: r for r in rows if r["t"] == "rest"}
    purchases = [r for r in rows if r["t"] == "buy"]
    merchants = {
        (r["act"], r["floor"]) for r in rows if r["t"] == "room" and r["kind"] == "merchant"
    }
    removals = {}
    for offered in offers.values():
        here = (offered["act"], offered["floor"])
        if offered["decision_type"] == "deck_select_remove" and here in merchants:
            (service,) = (
                buy
                for buy in purchases
                if (buy["act"], buy["floor"]) == here
                and buy["s"] > offered["s"]
                and "slot" not in buy
                and buy.get("cost_resource") == "gold"
                and offered["gold_on_hand"] - buy["gold_on_hand"] == buy["cost_current"]
            )
            removals[offered["decision_id"]] = service
    removal_records = {buy["s"] for buy in removals.values()}
    returns_by_turn, unfinished_hands = unlogged_returns(rows)
    plan: list[Intent] = []
    visited: set[tuple[int, int]] = set()
    map_offer = None
    hand: dict[int, str] = {}
    discard: dict[int, str] = {}
    unplaced: dict[int, str] = {}
    last_discard: tuple[int, str] | None = None
    seen_cards: set[int] = set()
    generated: set[int] = set()
    returned: dict[int, str] = {}
    transformed: list[int] = []
    deck_enchantments: dict[int, str | None] = {}
    combat_enchantments: dict[int, str | None] = {}
    enemies: dict[int, str] = {}
    defeated: set[int] = set()

    def live_enemies() -> tuple[tuple[int, str], ...]:
        return tuple((cid, name) for cid, name in enemies.items() if cid not in defeated)

    combat = False
    unflushed_discard: dict[int, str] = {}
    for index, r in enumerate(rows):
        tag = r["t"]
        if tag in {"header", "deck"}:
            deck_enchantments = {
                c["c"]: c.get("enchantment")
                for c in r["starting_deck" if tag == "header" else "cards"]
            }
        if tag == "draw_order":
            for cid, deck_cid in zip(r["order_c"], r["order_deck_c"], strict=True):
                if deck_cid in deck_enchantments:
                    combat_enchantments[cid] = deck_enchantments[deck_cid]
        if tag in {"end_turn", "combat_start"}:
            transformed.clear()
        if last_discard and (
            tag in {"end_turn", "flush", "combat_end", "potion_start"}
            or (tag == "play" and r["c"] != last_discard[0])
        ):
            discard[last_discard[0]] = last_discard[1]
            last_discard = None
        location = (r["act"], r["floor"]) if tag == "room" else None
        offer = offers.get(r.get("decision_id"))
        if location is not None and location not in visited:
            visited.add(location)
            if location != (1, 1):
                plan.append(Intent("visit", r, map_offer))
            map_offer = None
        elif tag == "decision" and r["decision_type"] == "rest":
            result = outcomes.get(r["decision_id"])
            if result is None:
                raise ValueError("A rest-site decision lacks a recorded outcome")
            plan.append(Intent("rest", result, r))
        elif tag == "decision" and r["decision_type"] == "deck_select_remove":
            result = removals.get(r["decision_id"])
            if result is not None:
                plan.append(Intent("removal_owner", result, r))
        elif tag == "outcome":
            kind = r.get("decision_type")
            if kind == "event":
                following = rows[index + 1 : index + 3]
                dialogue_only = (
                    r.get("label") == "Continue"
                    and offer is not None
                    and offer["n_presented"] == offer["n_selectable"] == 1
                    and len(following) == 2
                    and following[0]["t"] == "decision"
                    and following[0].get("event_id") == offer["event_id"]
                    and following[0]["n_presented"] == following[0]["n_selectable"] == 1
                    and following[1]["t"] == "outcome"
                    and following[1].get("label") == "Proceed"
                    and following[1]["decision_id"] == following[0]["decision_id"]
                )
                plan.append(Intent("event", r, offer, dialogue_only=dialogue_only))
            elif kind == "card_reward" or (kind is None and r["outcome"] == "skip"):
                plan.append(Intent("card_reward", r, offer))
            elif kind == "treasure":
                plan.append(Intent("treasure", r, offer))
            elif kind == "map_node":
                map_offer = offer
            elif kind not in {"deck_select_upgrade", "deck_select_remove"}:
                raise ValueError(f"Unsupported journal outcome at record {r['s']}: {kind}")
        elif tag == "event_proceed":
            plan.append(Intent(tag, r))
        elif tag == "combat_start":
            combat = True
            hand.clear()
            discard.clear()
            unplaced.clear()
            last_discard = None
            seen_cards.clear()
            combat_enchantments.clear()
            generated.clear()
            returned = dict(returns_by_turn.get(index, {}))
            unflushed_discard.clear()
            enemies = {e["cid"]: e["id"] for e in sorted(r["enemies"], key=lambda e: e["i"])}
            defeated.clear()
            plan.append(Intent(tag, r, enemies=live_enemies()))
        elif tag == "draw" and combat:
            seen_cards.add(r["c"])
            unflushed_discard.pop(r["c"], None)
            if r.get("deck_c") in deck_enchantments:
                combat_enchantments[r["c"]] = deck_enchantments[r["deck_c"]]
            discard.pop(r["c"], None)
            unplaced.pop(r["c"], None)
            returned.pop(r["c"], None)
            hand.pop(r["c"], None)
            generated.discard(r["c"])
            hand[r["c"]] = r["id"]
        elif tag == "transform" and combat and r["from_c"] in hand:
            old, new = r["from_c"], r["to_c"]
            seen_cards.add(new)
            transformed.append(new)
            hand = {
                (new if cid == old else cid): (r["to_id"] if cid == old else name)
                for cid, name in hand.items()
            }
            if old in generated:
                generated.remove(old)
                generated.add(new)
        elif tag == "transform" and combat and r["from_c"] in returned:
            returned.pop(r["from_c"])
            returned[r["to_c"]] = r["to_id"]
            transformed.append(r["to_c"])
        elif tag == "generate" and combat and r["c"] not in hand and r["c"] not in returned:
            hand[r["c"]] = r["id"]
            generated.add(r["c"])
            unplaced[r["c"]] = r["id"]
            seen_cards.add(r["c"])
        elif tag == "upgrade" and combat and r["c"] in seen_cards and r["c"] not in hand:
            # Upgrading a previously seen copy can accompany a move back to hand.
            # Require the observed hand to resolve its presence and position.
            hand[r["c"]] = r["id"]
            generated.add(r["c"])
            returned.pop(r["c"], None)
        elif tag == "exhaust" and combat:
            hand.pop(r["c"], None)
            discard.pop(r["c"], None)
            unplaced.pop(r["c"], None)
            unflushed_discard.pop(r["c"], None)
            returned.pop(r["c"], None)
            generated.discard(r["c"])
        elif tag == "spawn" and combat and r["side"] == "enemy":
            enemies[r["cid"]] = r["id"]
        elif tag == "death" and combat and r.get("removal_prevented") is False:
            if "tgt_cid" in r:
                defeated.add(r["tgt_cid"])
        elif tag == "hp" and combat and r["hp"] > 0 and "dst_cid" in r:
            defeated.discard(r["dst_cid"])
        elif tag == "play" and combat:
            if r.get("auto") is False and r.get("play_index") == 0:
                plan.append(
                    Intent(
                        tag,
                        r,
                        hand=tuple(hand.items()),
                        enemies=live_enemies(),
                        generated=frozenset(generated),
                        returns=tuple(returned.items()),
                        transform_order=tuple(transformed),
                        enchantments=tuple(combat_enchantments.items()),
                        unseen_returns=tuple(
                            (name, combat_enchantments.get(cid))
                            for cid, name in unflushed_discard.items()
                            if cid not in hand and cid not in returned
                        ),
                    )
                )
            hand.pop(r["c"], None)
            unflushed_discard.pop(r["c"], None)
            transformed.clear()
            returned.pop(r["c"], None)
            discard.pop(r["c"], None)
            unplaced.pop(r["c"], None)
            generated.discard(r["c"])
            if r.get("result_pile") == "discard":
                last_discard = (r["c"], r["id"])
        elif tag == "shuffle" and combat:
            for cid in r["order_c"]:
                discard.pop(cid, None)
                hand.pop(cid, None)
                returned.pop(cid, None)
                unplaced.pop(cid, None)
                unflushed_discard.pop(cid, None)
                generated.discard(cid)
            if last_discard and last_discard[0] in r["order_c"]:
                last_discard = None
        elif tag == "flush" and combat:
            known = {**hand, **returned}
            discard.update((cid, known[cid]) for cid in r["flushed_c"] if cid in known)
            for cid in r["flushed_c"]:
                unplaced.pop(cid, None)
            hand = {cid: known[cid] for cid in r["retained_c"]}
            generated.clear()
        elif tag == "end_turn" and r["side"] == "player":
            plan.append(Intent(tag, r))
            returned = dict(returns_by_turn.get(index, {}))
            unflushed_discard = dict(discard) if index in unfinished_hands else {}
        elif tag == "combat_end":
            combat = False
            plan.append(Intent(tag, r))
        elif tag == "potion_start":
            plan.append(Intent(tag, r, enemies=live_enemies()))
        elif tag == "potion_dropped":
            previous = rows[index - 1] if index else {}
            choice = plan[-1] if plan else None
            cost: tuple[str, ...] = ()
            if (
                previous.get("t") == "outcome"
                and choice
                and choice.kind == "event"
                and choice.offer
            ):
                (option,) = (
                    o
                    for o in choice.offer["options"]
                    if o["option_index"] == previous["option_index"]
                )
                cost = tuple(
                    definition(name)
                    for name in re.findall(r"Lose \[gold\](.*?)\[/gold\]", option.get("desc", ""))
                )
            plan.append(Intent("potion_event_cost" if r["id"] in cost else tag, r))
        elif tag == "pick" and r.get("selector") == "human":
            plan.append(
                Intent(
                    tag,
                    r,
                    offer,
                    tuple(hand.items()),
                    generated=frozenset(generated),
                    returns=tuple(returned.items()),
                    discard=tuple(discard.items()),
                    transform_order=tuple(transformed),
                    enchantments=tuple(combat_enchantments.items()),
                    unplaced_cards=tuple(unplaced.values()),
                )
            )
        elif tag == "acquire" and r.get("source") == "reward":
            plan.append(Intent("card_reward", r, offer))
        elif tag == "resolve" and r["reward_kind"] != "CardReward":
            if r["reward_kind"] == "SpecialCardReward":
                granted = next(p for p in reversed(rows[: r["s"]]) if p["t"] == "acquire")
                if granted["source"] != "granted" or granted["floor"] != r["floor"]:
                    raise ValueError("Require a recorded special reward acquisition")
                r = {**r, "id": granted["id"]}
            plan.append(Intent("reward", r, offer))
        elif tag == "buy" and r["s"] not in removal_records:
            plan.append(Intent(tag, r))
    return tuple(plan)


def archive_cards(cards: list[dict[str, Any]]) -> Counter[tuple[str, int]]:
    return Counter((c["id"], c["up"]) for c in cards)
