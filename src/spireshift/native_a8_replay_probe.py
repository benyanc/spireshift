"""Replay a reload-free archive journal using only frozen native public actions."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, deque
from collections.abc import Callable
from dataclasses import replace
from functools import cache
from pathlib import Path
from typing import Any

import psutil

from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_mix_session import MixWorker, admit, unchanged
from spireshift.native_a8_replay_source import Intent, Journal, archive_cards, read
from spireshift.native_a8_rescue_game import bridge, receipt
from spireshift.native_a8_tactical_session import boundary, frozen
from spireshift.native_flow_live_v12 import append
from spireshift.native_flow_verification_v12 import records, same
from spireshift.native_win4_game import write

AREA = "artifacts/native-a8-replay-source"
SAMPLE = "ee2ffb605c67742f"
SOURCE_SHA = "b348c86840e35e9e23547fa380bb377ffe1cf88482e83b7313fae08f84c373df"
CONTROL_SECONDS = 150
FULL_SECONDS = 270
TRACE = "matched-deliveries.jsonl.gz"


class Divergence(ValueError):
    def __init__(self, field: str, archive: Any, native: Any) -> None:
        super().__init__(f"Recorded and native {field} differ")
        self.facts = {"field": field, "archive": archive, "native": native}


def equal(field: str, archive: Any, native: Any) -> None:
    if native != archive:
        raise Divergence(field, archive, native)


def start(frame: dict[str, Any], journal: Journal) -> None:
    state = frame["public_input"]["context"]
    run, player = state["persistent"]["run"], state["persistent"]["player"]
    (deck,) = (r["content"]["cards"] for r in state["reads"] if r["kind"] == "run_deck")
    equal("starting act", (1, journal.act), (run["act"], run["act_definition_id"]))
    equal("starting boss", [journal.boss], [b["definition_id"] for b in run["bosses"]])
    equal(
        "normal start",
        (1, 8, "IRONCLAD", False),
        (run["floor"], run["ascension"], player["character_definition_id"], frame["terminal"]),
    )
    equal(
        "starting HP",
        (journal.starting_hp, journal.header["starting_max_hp"]),
        (player["hp"], player["max_hp"]),
    )
    equal(
        "starting deck",
        sorted(archive_cards(journal.header["starting_deck"]).items()),
        sorted(Counter((c["definition_id"], int(c["is_upgraded"])) for c in deck).items()),
    )


def unique(candidates: list[dict[str, Any]], predicate: Callable[[dict[str, Any]], bool]) -> int:
    matches = [i for i, action in enumerate(candidates) if predicate(action)]
    equal("unique legal action", 1, len(matches))
    return matches[0]


def named(candidates: list[dict[str, Any]], *labels: str) -> int:
    return unique(candidates, lambda action: action["label"] in labels)


def ordered_slots(
    intent: Intent,
    hand: list[dict[str, Any]],
    cards: list[int],
    *,
    legal: dict[int, set[int]] | None = None,
) -> list[int]:
    """Resolve required drawn copies and possible generated or returned copies."""
    wanted = set(cards)
    legal = legal or {}
    names = tuple(c["definition_id"] for c in hand)
    possible: dict[int, set[int]] = {cid: set() for cid in cards}
    returned = dict(intent.returns)
    equal("recorded hand copies", True, wanted <= set(dict(intent.hand)) | returned.keys())
    ranks = {cid: i for i, cid in enumerate(intent.transform_order)}
    enchantments = dict(intent.enchantments)
    unused_copies = Counter(intent.unseen_returns)
    extra_keys = list(unused_copies)
    native_extra_keys = [
        (card["definition_id"], (card.get("existing_enchantment") or {}).get("definition_id"))
        for card in hand
    ]
    extras = [extra_keys.index(key) if key in unused_copies else -1 for key in native_extra_keys]
    upgrades = {
        row["c"]: bool(row["up"])
        for row in intent.record.get("cards", [intent.record])
        if "c" in row and "up" in row
    }

    def fits(cid: int, name: str, slot: int) -> bool:
        return (
            name == names[slot]
            and (cid not in upgrades or hand[slot]["is_upgraded"] == upgrades[cid])
            and (cid not in legal or hand[slot]["entity_id"]["public_slot"] in legal[cid])
            and (
                cid not in enchantments
                or (hand[slot].get("existing_enchantment") or {}).get("definition_id")
                == enchantments[cid]
            )
        )

    @cache
    def complete(
        source: int, native: int, remaining: frozenset[int], last: int, extra: tuple[int, ...]
    ) -> bool:
        result = False
        if native < len(names):
            for cid in remaining:
                step = ranks.get(cid, last)
                if (
                    fits(cid, returned[cid], native)
                    and step >= last
                    and complete(source, native + 1, remaining - {cid}, step, extra)
                ):
                    result = True
                    if cid in wanted:
                        possible[cid].add(hand[native]["entity_id"]["public_slot"])
            unknown = extras[native]
            if unknown >= 0 and extra[unknown]:
                rest = extra[:unknown] + (extra[unknown] - 1,) + extra[unknown + 1 :]
                if complete(source, native + 1, remaining, last, rest):
                    result = True
        if source == len(intent.hand):
            return result or (native == len(names) and wanted.isdisjoint(remaining))
        cid, name = intent.hand[source]
        step = ranks.get(cid, last)
        if (
            native < len(names)
            and fits(cid, name, native)
            and step >= last
            and complete(source + 1, native + 1, remaining, step, extra)
        ):
            result = True
            if cid in wanted:
                possible[cid].add(hand[native]["entity_id"]["public_slot"])
        if (
            cid in intent.generated
            and cid not in wanted
            and complete(source + 1, native, remaining, last, extra)
        ):
            result = True
        return result

    if not complete(0, 0, frozenset(returned), -1, tuple(unused_copies.values())):
        raise Divergence(
            "ordered hand", {"logged": intent.hand, "possible_returns": intent.returns}, list(names)
        )
    for slots in possible.values():
        equal("physical card copy", 1, len(slots))
    return [next(iter(possible[cid])) for cid in cards]


def enemy_target(intent: Intent, owner: dict[str, Any]) -> int:
    enemies = owner["enemies"]
    equal(
        "living enemy definitions",
        sorted(name for _, name in intent.enemies),
        sorted(e["definition_id"] for e in enemies),
    )
    target = intent.record["target_cid"]
    name = dict(intent.enemies)[target]
    source_group = [cid for cid, definition_id in intent.enemies if definition_id == name]
    live_group = [e for e in enemies if e["definition_id"] == name]
    return int(live_group[source_group.index(target)]["entity_id"]["public_slot"])


def arguments(action: dict[str, Any], role: str) -> list[int]:
    return [a["entity"]["public_slot"] for a in action["arguments"] if a["role"] == role]


def same_enchantment(card: dict[str, Any], cid: int, known: dict[int, str | None]) -> bool:
    return (
        cid not in known
        or (card.get("existing_enchantment") or {}).get("definition_id") == known[cid]
    )


def discard_selection(
    context: dict[str, Any], intent: Intent, cards: list[dict[str, Any]]
) -> dict[int, int]:
    for view in context["reads"]:
        if view["kind"] != "combat_piles":
            continue
        for pile in view["content"]["zones"]:
            if pile["zone"] != "discard":
                continue
            visible = {c["entity_id"]["public_slot"] for c in pile["cards"]}
            slots = [c["entity_id"]["public_slot"] for c in cards]
            if visible != set(slots):
                continue
            if [c["definition_id"] for c in cards] == [name for _, name in intent.discard]:
                return {cid: slot for (cid, _), slot in zip(intent.discard, slots, strict=True)}
            # Other effects can add or retrieve unrelated cards without a
            # zone transition in the journal. Match a complete recorded
            # occurrence group only when it has no unplaced copies.
            matches: dict[int, int] = {}
            returning = set(dict(intent.returns))
            enchantments = dict(intent.enchantments)
            for name in {c["id"] for c in intent.record["cards"]}:
                if name in intent.unplaced_cards:
                    continue
                source = [
                    cid for cid, card in intent.discard if card == name and cid not in returning
                ]
                native = [card for card in cards if card["definition_id"] == name]
                if len(source) == len(native) and all(
                    same_enchantment(card, cid, enchantments)
                    for cid, card in zip(source, native, strict=True)
                ):
                    matches.update(
                        (cid, card["entity_id"]["public_slot"])
                        for cid, card in zip(source, native, strict=True)
                    )
            return matches
    return {}


def card_choice(frame: dict[str, Any], intent: Intent) -> tuple[int, bool]:
    public = frame["public_input"]
    interaction = public["context"]["interaction"]
    surface, owner = interaction["content"]["surface"], interaction["content"]["context"]
    row, offer = intent.record, intent.offer
    chosen = row["cards"]
    cards = surface["cards"]
    enchantments = dict(intent.enchantments)
    equal("recorded selection count", row["n_picked"], len(chosen))
    if offer is not None:
        opts = [o for o in offer["options"] if o["presented"] and o["selectable"]]
        source_keys = [(o["option_id"], o["up"]) for o in opts]
        native_keys = [(c["definition_id"], int(c["is_upgraded"])) for c in cards]
        equal(
            "selector contents",
            sorted(source_keys),
            sorted(native_keys),
        )
        # The native removal UI may group curses first. Preserve occurrence
        # order within each definition and upgrade when moving between views.
        by_copy = {
            o["instance_id"]: c
            for o, c in zip(
                sorted(opts, key=lambda o: (o["option_id"], o["up"])),
                sorted(cards, key=lambda c: (c["definition_id"], int(c["is_upgraded"]))),
                strict=True,
            )
        }
        selection = [by_copy[c["c"]]["entity_id"]["public_slot"] for c in chosen]
    elif (
        interaction["kind"] == "card_selection"
        and all(c["c"] in dict(intent.hand + intent.returns) for c in chosen)
        and "player" in owner
        and "hand" in owner["player"]
    ):
        selection = ordered_slots(intent, owner["player"]["hand"], [c["c"] for c in chosen])
    else:
        discard = discard_selection(public["context"], intent, cards)
        selection = []
        for item in chosen:
            if item["c"] in discard:
                selection.append(discard[item["c"]])
                continue
            slots = [
                c["entity_id"]["public_slot"]
                for c in cards
                if (c["definition_id"], int(c["is_upgraded"])) == (item["id"], item["up"])
                and same_enchantment(c, item["c"], enchantments)
            ]
            equal("unique visible selection copy", 1, len(slots))
            selection.append(slots[0])
    by_slot = {c["entity_id"]["public_slot"]: c for c in cards}
    equal(
        "selected cards",
        [(c["id"], c["up"]) for c in chosen],
        [(by_slot[i]["definition_id"], int(by_slot[i]["is_upgraded"])) for i in selection],
    )
    equal(
        "selected enchantments",
        True,
        all(
            same_enchantment(by_slot[slot], card["c"], enchantments)
            for card, slot in zip(chosen, selection, strict=True)
        ),
    )
    candidates = public["candidates"]
    if interaction["kind"] == "native_generated_card_choice":
        if not selection:
            return named(candidates, "Skip"), True
        equal("generated choice count", 1, len(selection))
        return unique(
            candidates,
            lambda a: a["verb"] == "select" and a["subject"]["public_slot"] == selection[0],
        ), True
    equal("selector owner", "card_selection", interaction["kind"])
    if "answer_plan" in surface:
        prefix = [cards[i]["entity_id"]["public_slot"] for i in surface["answer_plan"]["selected"]]
        equal("selected answer prefix", selection[: len(prefix)], prefix)
        if len(prefix) < len(selection):
            slot = selection[len(prefix)]
            return unique(
                candidates, lambda a: a["verb"] == "select" and a["subject"]["public_slot"] == slot
            ), False
        return unique(candidates, lambda a: a["verb"] == "confirm"), True
    return unique(
        candidates, lambda a: a["verb"] == "confirm" and arguments(a, "selected_card") == selection
    ), True


def stage(frame: dict[str, Any], intent: Intent, journal: Journal) -> int | None:
    """Enter the required offer or leave a room the journal records as exited."""
    public = frame["public_input"]
    interaction = public["context"]["interaction"]
    family = interaction["kind"]
    surface = interaction["content"].get("surface", {})
    run = public["context"]["persistent"]["run"]
    candidates = public["candidates"]
    row, kind = intent.record, intent.kind
    here = (run["act"], run["floor"])
    target = (row["act"], row["floor"])
    if here == target:
        if kind in {"buy", "removal_owner"} and (
            family == "shop_room"
            or family == "shop_inventory"
            and surface.get("inventory_open") is False
        ):
            return named(candidates, "Open inventory", "Open shop inventory")
        if kind == "treasure" and family == "treasure_room" and not surface["chest_opened"]:
            return named(candidates, "Open the treasure chest")
        if kind == "card_reward" and family == "reward_claim":
            return unique(
                candidates,
                lambda a: (
                    a["verb"] == "activate"
                    and (a["subject"] or {}).get("properties", {}).get("kind") == "card"
                ),
            )
    if (
        kind in {"visit", "event"}
        and here != target
        and here in journal.exits
        or kind == "event"
        and intent.offer is not None
        and intent.offer.get("event_id") == "THE_ARCHITECT"
        and here in journal.exits
    ):
        labels = {
            "reward_claim": (
                "Continue from rewards",
                "Skip remaining rewards and continue",
                "Skip remaining rewards",
            ),
            "rest_site": ("Proceed to map",),
            "shop_inventory": ("Close shop inventory", "Leave shop"),
            "shop_room": ("Leave shop and open map", "Leave shop"),
            "treasure_room": ("Continue from the treasure room",),
        }.get(family)
        if labels is not None:
            return named(candidates, *labels)
    return None


def match(frame: dict[str, Any], intent: Intent, journal: Journal) -> int | None:
    """Match a recorded input on the current menu, or check a source state boundary."""
    public = frame["public_input"]
    interaction = public["context"]["interaction"]
    run = public["context"]["persistent"]["run"]
    family = interaction["kind"]
    owner = interaction["content"].get("context", {})
    surface = interaction["content"].get("surface", {})
    row, offer, kind = intent.record, intent.offer, intent.kind
    equal("act", row["act"], run["act"])
    equal("floor", row["floor"] - int(kind == "visit"), run["floor"])
    if kind == "potion_event_cost":
        belt = public["context"]["persistent"]["player"]["potions"]
        equal("event potion consumption", False, any(p["definition_id"] == row["id"] for p in belt))
        return None
    if kind == "combat_end":
        next_owner = family == "reward_claim" or (
            family == "event_option"
            and owner.get("event_id") == "THE_ARCHITECT"
            and row["act"] == 3
        )
        equal("combat victory", ("victory", True), (row["result"], next_owner))
        return None
    if kind == "combat_start":
        equal("combat owner", "combat_turn", family)
        expected = [(e["id"], e["hp"], e["max_hp"]) for e in row["enemies"]]
        observed = [(e["definition_id"], e["hp"], e["max_hp"]) for e in owner["enemies"]]
        equal("initial enemies", expected, observed)
        return None

    label = subject_slot = None
    target_slot = None
    own_target = False
    properties: dict[str, Any] = {}
    verb = "activate"
    if kind == "event":
        equal("event owner", "event_option", family)
        if offer is None:
            raise ValueError("Recorded event choice has no matching offer")
        equal("event definition", offer["event_id"], owner["event_id"])
        if offer["event_id"] == "THE_ARCHITECT" and journal.pre_architect_hp is not None:
            equal(
                "pre-Architect HP",
                journal.pre_architect_hp,
                public["context"]["persistent"]["player"]["hp"],
            )
        equal(
            "event menu",
            sorted(
                (o["option_index"], o["label"], o["selectable"])
                for o in offer["options"]
                if o["presented"]
            ),
            sorted((o["index"], o["title"], o["is_enabled"]) for o in surface["options"]),
        )
        properties["index"] = row["option_index"]
        label = row["label"]
    elif kind == "event_proceed":
        equal("event Proceed owner", "event_option", family)
        equal("event definition", row["event_id"], owner["event_id"])
        properties["is_proceed"] = True
    elif kind == "visit":
        equal("map owner", "map_navigation", family)
        if offer is not None:
            equal(
                "map menu",
                sorted(o["option_id"] for o in offer["options"] if o["selectable"]),
                sorted(f"{o['col']},{o['row']}" for o in surface["next_options"]),
            )
        properties["col"], properties["row"] = map(int, row["coord"].split(","))
    elif kind in {"play", "end_turn"}:
        equal("turn owner", "combat_turn", family)
        equal("round", row["turn"] if kind == "play" else row["round"], owner["round"])
        if kind == "play":
            verb = "play"
            properties = {"definition_id": row["id"], "is_upgraded": bool(row["up"])}
            if "target_cid" in row:
                target_slot = enemy_target(intent, owner)
            playable = {
                a["subject"]["public_slot"]
                for a in public["candidates"]
                if a["verb"] == "play"
                and all(a["subject"]["properties"].get(k) == v for k, v in properties.items())
                and arguments(a, "target") == ([] if target_slot is None else [target_slot])
            }
            (subject_slot,) = ordered_slots(
                intent, owner["player"]["hand"], [row["c"]], legal={row["c"]: playable}
            )
        else:
            verb = "end_turn"
    elif kind == "reward":
        equal("reward owner", "reward_claim", family)
        reward_kind = {
            "GoldReward": "gold",
            "PotionReward": "potion",
            "RelicReward": "relic",
            "SpecialCardReward": "card",
        }[row["reward_kind"]]
        expected_reward = (
            f"{row['gold']} Gold"
            if reward_kind == "gold"
            else journal.reward_names[reward_kind, row["id"]]
        )
        reward = [
            r
            for r in surface["rewards"]
            if r["kind"] == reward_kind
            and r["label"].removesuffix(" (stolen back)") == expected_reward
        ]
        equal("unique recorded reward", 1, len(reward))
        subject_slot = reward[0]["entity_id"]["public_slot"]
    elif kind == "card_reward":
        equal("card reward owner", "card_reward_selection", family)
        cards = surface["cards"]
        if offer is not None:
            equal(
                "ordered card rewards",
                [
                    (o["option_id"], o["up"])
                    for o in offer["options"]
                    if o["option_kind"] == "card" and o["selectable"]
                ],
                [(c["definition_id"], int(c["is_upgraded"])) for c in cards],
            )
        if row.get("outcome") == "skip":
            return named(public["candidates"], "Skip")
        equal("reward card", row["id"], cards[row["option_index"]]["definition_id"])
        subject_slot = cards[row["option_index"]]["entity_id"]["public_slot"]
        verb = "select"
    elif kind == "rest":
        equal("rest owner", "rest_site", family)
        properties["index"] = row["option_index"]
        equal(
            "rest choice",
            row["option"],
            surface["options"][row["option_index"]]["option_id"].lower(),
        )
    elif kind == "treasure":
        equal("treasure owner", "treasure_room", family)
        properties["definition_id"] = row["option_id"]
    elif kind in {"buy", "removal_owner"}:
        equal("shop owner", "shop_inventory", family)
        properties["price"] = row["cost_current"]
        if kind == "buy":
            item = row["kind"]
            group = {"card": "cards", "relic": "relics", "potion": "potions"}[item]
            # Archive slots are per item group. The native catalog numbers
            # inventory entries across the whole merchant.
            entry = sorted(surface[group], key=lambda e: e["inventory_index"])[row["slot"]]
            offered = entry.get(item, entry)
            equal("shop item", row["id"], offered.get("definition_id", offered.get("id")))
            subject_slot = entry["entity_id"]["public_slot"]
        else:
            subject_slot = surface["card_removal"]["entity_id"]["public_slot"]
            verb = "open"
    elif kind in {"potion_start", "potion_dropped"}:
        properties["definition_id"] = row["id"]
        if "slot" in row:
            properties["slot"] = row["slot"]
        if kind == "potion_start":
            verb = "use"
            if "target_cid" in row:
                target_slot = enemy_target(intent, owner)
            own_target = row.get("target") == "IRONCLAD"
    else:
        raise ValueError(f"Source record {row['s']} needs an unqualified {kind} mapping")

    candidates = public["candidates"]

    def eligible(action: dict[str, Any]) -> bool:
        subject = action["subject"] or {}
        targets = arguments(action, "target")
        return (
            action["verb"] == verb
            and (label is None or action["label"] == label)
            and (kind != "potion_dropped" or action["label"].startswith("Discard "))
            and (subject_slot is None or subject.get("public_slot") == subject_slot)
            and all(subject.get("properties", {}).get(k) == v for k, v in properties.items())
            and (
                targets == ([] if target_slot is None else [target_slot])
                or own_target
                and len(targets) == 1
                and subject.get("properties", {}).get("target_type") == "AnyPlayer"
            )
        )

    if kind in {"potion_start", "potion_dropped"} and "slot" not in row:
        matching = [i for i, a in enumerate(candidates) if eligible(a)]
        if len(matching) > 1:

            def effect(index: int) -> dict[str, Any]:
                action = candidates[index]
                subject = action["subject"]
                return {
                    "state": subject["state"],
                    "properties": {
                        k: v
                        for k, v in subject["properties"].items()
                        if k not in {"slot", "entity_id"}
                    },
                    "arguments": action["arguments"],
                }

            equal(
                "equivalent potion copies",
                True,
                all(effect(i) == effect(matching[0]) for i in matching),
            )
            return min(matching, key=lambda i: int(candidates[i]["subject"]["properties"]["slot"]))
    return unique(candidates, eligible)


def next_choice(
    frame: dict[str, Any], journal: Journal, cursor: int, end: int
) -> tuple[int | None, int, str]:
    while cursor < end:
        intent = journal.intents[cursor]
        interaction = frame["public_input"]["context"]["interaction"]
        if intent.dialogue_only and interaction["kind"] == "event_option":
            options = interaction["content"]["surface"]["options"]
            if (
                len(options) == 1
                and options[0]["title"] == "Proceed"
                and options[0]["is_enabled"] is True
            ):
                # The immediately following recorded Proceed must still match
                # its exact event owner, location, menu and current binding.
                cursor += 1
                continue
        staged = stage(frame, intent, journal)
        if staged is not None:
            return staged, cursor, "native"
        if intent.kind == "pick":
            public = frame["public_input"]["context"]["persistent"]["run"]
            equal(
                "selector location",
                (intent.record["act"], intent.record["floor"]),
                (public["act"], public["floor"]),
            )
            selected, committed = card_choice(frame, intent)
            return (
                selected,
                cursor + int(committed),
                "native" if committed else "local_answer_factor",
            )
        index = match(frame, intent, journal)
        cursor += 1
        if index is not None:
            return index, cursor, "native"
    return None, cursor, "native"


def victory(frame: dict[str, Any], journal: Journal, ending: dict[str, Any]) -> None:
    state = frame["public_input"]["context"]
    run, player = state["persistent"]["run"], state["persistent"]["player"]
    identity = ending["private_final_identity"]
    equal(
        "native victory",
        (True, True, True, True, True, journal.seed),
        (
            frame["terminal"],
            frame.get("ending", {}).get("victory"),
            ending["native_ending_evidence_agrees"],
            identity["native_game_over"],
            identity["native_victory_room"],
            identity["seed"],
        ),
    )
    equal(
        "final act, floor and maximum HP",
        (3, journal.end["floors"], journal.end["max_hp"]),
        (run["act"], run["floor"], player["max_hp"]),
    )
    (deck,) = (r["content"]["cards"] for r in state["reads"] if r["kind"] == "run_deck")
    equal(
        "final deck",
        sorted(archive_cards(journal.end["final_deck"]).items()),
        sorted(Counter((c["definition_id"], int(c["is_upgraded"])) for c in deck).items()),
    )
    equal(
        "final relics",
        sorted(journal.end["final_relics"]),
        sorted(r["definition_id"] for r in player["relics"]),
    )


def verify(
    ctx: dict[str, Any],
    out: Path,
    journal: Journal,
    end: int,
    deadline: float,
    final_frame: dict[str, Any],
    *,
    log: Path | None = None,
) -> int:
    """Reconstruct each admitted receipt from the worker's raw observation stream."""
    converter = bridge(ctx, log or out / "verify.log")
    observations = iter(records(out / "worker/public-observations.jsonl.gz"))
    raw = iter(records(out / "worker/public-receipts.jsonl.gz"))
    domains = iter(records(out / "worker/answer-plan-deliveries.jsonl.gz"))
    count = 0
    cursor = 0
    try:
        current = next(observations)
        trace = out / TRACE
        for saved in records(trace) if trace.exists() else ():
            frame = converter.project(current["snapshot"], current["reads"], None, deadline)
            if count == 0:
                start(frame, journal)
            index, cursor, domain = next_choice(frame, journal, cursor, end)
            if index is None:
                raise ValueError("A saved delivery follows the end of the replay plan")
            choice = {"action_index": index, "binding_id": frame["binding_id"]}
            current, actual, raw_domain = next(observations), next(raw), next(domains)
            accepted = receipt(frame, choice, domain, current["snapshot"]["snapshot_id"])
            if (
                not same(frame, saved["frame"])
                or not same(choice, saved["choice"])
                or not same(accepted, saved["receipt"])
                or cursor != saved["cursor"]
                or actual["delivery"] != "delivered"
                or actual["snapshot_id"] != accepted["before_snapshot_id"]
                or actual["action"]["bound_action_id"] != accepted["bound_action_id"]
                or actual["successor_snapshot_id"] != accepted["successor_snapshot_id"]
                or raw_domain["delivery_domain"] != domain
                or raw_domain["before_snapshot_id"] != accepted["before_snapshot_id"]
                or raw_domain["action_id"] != accepted["bound_action_id"]
                or raw_domain["successor_snapshot_id"] != accepted["successor_snapshot_id"]
            ):
                raise ValueError("Saved native delivery could not be reconstructed")
            converter.commit(saved["choice"], accepted, deadline)
            count += 1
        if any(next(stream, None) is not None for stream in (raw, domains, observations)):
            raise ValueError("An unverified native delivery remains in the trace")
        final = converter.project(current["snapshot"], current["reads"], None, deadline)
        equal("reconstructed final frame", True, same(final, final_frame))
        converter.close()
    finally:
        converter.stop()
    return count


def known_selector_stop(
    ctx: dict[str, Any],
    prior: Path,
    out: Path,
    previous: dict[str, Any],
    journal: Journal,
    deadline: float,
) -> dict[str, Any]:
    """Prove the failed cleanup followed an acknowledged menu and an unsent choice."""
    worker = prior / "worker"
    stop = previous["stop"]
    if (
        previous["clean_shutdown"] is not False
        or stop["kind"] != "pick"
        or (stop.get("mismatch") or {}).get("field") != "unique visible selection copy"
        or not stop.get("shutdown_error")
        or previous["verified_native_deliveries"] != previous["acknowledged_before_stop"]
    ):
        raise ValueError("Preserve the previous unresolved delivery without replay")
    identity = json.loads((worker / "identity.json").read_text())
    marker = json.loads((worker / "active.json").read_text())
    if any(
        psutil.pid_exists(pid)
        for pid in (identity["runtime_identity"]["process_id"], marker["owner_process"])
    ):
        raise ValueError("The previous worker or its owner still exists")
    (quit_row,) = deque(records(worker / "private-transcript.jsonl.gz"), maxlen=1)
    if (
        quit_row["request"] != {"cmd": "quit"}
        or quit_row["response"]["type"] != "error"
        or "ActionExecutor did not stop during cleanup" not in quit_row["response"]["message"]
    ):
        raise ValueError("Require the explicit previous native cleanup failure")
    frame = identified(prior / "last-frame.json")
    frame.pop("report_id")
    count = verify(
        ctx,
        prior,
        journal,
        len(journal.intents),
        deadline,
        frame,
        log=out / "previous-prefix-verification.log",
    )
    equal("previous acknowledged deliveries", previous["verified_native_deliveries"], count)
    cursor = previous["source_intents_consumed"]
    intent = journal.intents[cursor]
    equal("previous unsent source selection", stop["source_record"], intent.record["s"])
    index, committed = card_choice(frame, intent)
    return write(
        out / "previous-stop-audit.json",
        {
            "previous_report_id": previous["report_id"],
            "raw_deliveries_reconstructed": count,
            "source_record": intent.record["s"],
            "corrected_candidate": frame["public_input"]["candidates"][index]["label"],
            "corrected_candidate_commits_selection": committed,
            "selection_submitted": False,
            "native_quit_returned_explicit_error": True,
            "native_and_owner_processes_gone": True,
            "prior_profile_reusable": False,
        },
    )


def probe(
    root: Path, journal: Journal, source: Path, *, control: bool, attempt: int
) -> dict[str, Any]:
    seconds = CONTROL_SECONDS if control else FULL_SECONDS
    deadline = time.monotonic() + seconds
    base = admit(root)
    ctx = base.ctx
    limits = base.cfg["game_limits"]
    end = len(journal.intents)
    if control:
        end = next(
            i
            for i, intent in enumerate(journal.intents)
            if intent.kind == "visit" and intent.record["floor"] == 9
        )
    if _running_games():
        raise ValueError("Close STS2 and wait for any other native worker")
    before = frozen(root, ctx)
    locale = ctx["native"]["localization"] / "localization_eng"
    names = {
        (kind, key.removesuffix(".title")): value
        for kind in ("potion", "relic", "card")
        for key, value in json.loads((locale / f"{kind}s.json").read_text()).items()
        if key.endswith(".title")
    }
    journal = replace(journal, reward_names=names)
    profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
    boundary(root, ctx, before, profile)
    name = "archive-control" if control else "archive-qualification"
    out = root / AREA / SAMPLE / f"{name}-v{attempt}"
    implementation = {
        name: _sha_file(Path(__file__).with_name(name))
        for name in (Path(__file__).name, "native_a8_replay_source.py")
    }
    previous = None
    prior = out
    if not control and attempt > 1:
        prior = out.with_name(f"{name}-v{attempt - 1}")
        previous = identified(prior / "report.json")
        previous_config = identified(prior / "config.json", key="config_id")
        if (
            previous["config_id"] != previous_config["config_id"]
            or previous["status"] != "stopped_preserving_evidence"
            or not all(previous["frozen_checks"].values())
            or previous_config["implementation"] == implementation
        ):
            raise ValueError("Require a revised matcher after a known clean stop")
    out.mkdir(parents=True, exist_ok=False)
    prior_audit = None
    if previous is not None and previous["stop"]["delivery_uncertain"]:
        prior_audit = known_selector_stop(ctx, prior, out, previous, journal, deadline)["report_id"]
    config = write(
        out / "config.json",
        {
            "schema_version": "native-a8-archive-replay-v1",
            "source": f"https://spire-codex.com/runs/{SAMPLE}/replay",
            "source_sha256": SOURCE_SHA,
            "seed": journal.seed,
            "objective": base.cfg["objective"],
            "environment_id": ctx["environment_id"],
            "implementation": implementation,
            "source_prefix_intents": end,
            "maximum_deliveries": limits["maximum_decisions"],
            "wall_seconds": seconds,
            "native_cpu_seconds": limits["episode_cpu_seconds"],
            "previous_stop_audit_id": prior_audit,
        },
        key="config_id",
    )
    native = MixWorker({**ctx, "execution_id": config["config_id"]}, out / "worker")
    converter = bridge(ctx, out / "converter.log")
    delivered = 0
    stop: dict[str, Any] | None = None
    frame: dict[str, Any] | None = None
    pending = False
    cursor = 0
    ending = None
    clean_shutdown = False
    try:
        current = native.request("mount", seed=journal.seed, timeout=25)
        frame = converter.project(current["snapshot"], current["reads"], None, deadline)
        start(frame, journal)
        while cursor < end:
            if (
                delivered >= limits["maximum_decisions"]
                or native.cpu_seconds() >= limits["episode_cpu_seconds"]
            ):
                raise ValueError("Replay reached its native choice or CPU guard")
            index, next_cursor, domain = next_choice(frame, journal, cursor, end)
            if index is None:
                cursor = next_cursor
                break
            choice = {"action_index": index, "binding_id": frame["binding_id"]}
            limit = min(15, deadline - time.monotonic() - 20)
            if limit <= 0:
                raise TimeoutError("Prefix deadline reached")
            pending = True
            current = native.request(
                "step",
                snapshot_id=current["snapshot"]["snapshot_id"],
                action_index=frame["actions"][index]["raw_index"],
                timeout=limit,
            )
            equal("delivery domain", domain, current["delivery_domain"])
            accepted = receipt(frame, choice, domain, current["snapshot"]["snapshot_id"])
            converter.commit(choice, accepted, deadline)
            append(
                out / TRACE,
                {
                    "frame": frame,
                    "choice": choice,
                    "receipt": accepted,
                    "cursor": next_cursor,
                },
            )
            delivered += 1
            pending = False
            cursor = next_cursor
            frame = converter.project(current["snapshot"], current["reads"], None, deadline)
        if not control:
            ending = native.request("ending", timeout=10)
            victory(frame, journal, ending)
            if ending["usage"]["native_cpu_seconds"] > limits["episode_cpu_seconds"]:
                raise ValueError("Native terminal exceeded the replay CPU guard")
    except (ValueError, LookupError, TimeoutError, OSError) as exc:
        intent = journal.intents[cursor] if cursor < end else None
        stop = {
            "error": str(exc),
            "source_record": intent.record["s"] if intent else None,
            "kind": intent.kind if intent else "ending",
            "mismatch": exc.facts if isinstance(exc, Divergence) else None,
            "delivery_uncertain": pending,
        }
    finally:
        converter.stop()
        try:
            if pending:
                native.retire("Preserve an uncertain replay action")
            else:
                shutdown = native.close()
                clean_shutdown = shutdown["clean_exit"] and not shutdown.get("runtime_errors")
        except (ValueError, TimeoutError, OSError) as exc:
            stop = {
                **(stop or {}),
                "shutdown_error": str(exc),
                "delivery_uncertain": True,
            }
        finally:
            native.stop()
    if frame is not None:
        write(out / "last-frame.json", frame)
    if not clean_shutdown and stop is None:
        stop = {"error": "Native shutdown did not verify", "delivery_uncertain": True}
    reconstructed = (
        None if pending or frame is None else verify(ctx, out, journal, end, deadline, frame)
    )
    if reconstructed is not None:
        equal("receipt count", delivered, reconstructed)
    unchanged(base, before, deadline)
    boundary(root, ctx, before, profile)
    equal("source digest", SOURCE_SHA, _sha_file(source))
    return write(
        out / "report.json",
        {
            "schema_version": config["schema_version"],
            "config_id": config["config_id"],
            "status": "stopped_preserving_evidence"
            if stop
            else ("archive_prefix_verified" if control else "native_archive_victory_verified"),
            "source_sha256": SOURCE_SHA,
            "environment_id": ctx["environment_id"],
            "source_intents": len(journal.intents),
            "source_intents_consumed": cursor,
            "verified_native_deliveries": reconstructed,
            "acknowledged_before_stop": delivered,
            "clean_shutdown": clean_shutdown,
            "stop": stop,
            "frozen_checks": before,
            "genuine_native_victory": not control and stop is None,
            "native_ending": ending,
            "optimizer_updates": 0,
            "training_admission_granted": False,
            "automatic_follow_up": False,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true", help="Launch the bounded native prefix")
    modes.add_argument("--run", action="store_true", help="Launch the full native replay")
    parser.add_argument("--attempt", type=int, default=1, choices=range(1, 25))
    args = parser.parse_args()
    root = Path.cwd()
    source = root / AREA / f"qualification-{SAMPLE}.ndjson"
    equal("source digest", SOURCE_SHA, _sha_file(source))
    journal = read(source)
    if args.check or args.run:
        report = probe(root, journal, source, control=args.check, attempt=args.attempt)
        print(json.dumps(report))
        return int(report["stop"] is not None) * 2
    print(
        json.dumps(
            {
                "seed": journal.seed,
                "intents": len(journal.intents),
                "archive_terminal_reason": journal.end["terminal_reason"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
