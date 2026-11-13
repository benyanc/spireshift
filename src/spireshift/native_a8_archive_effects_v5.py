"""Verify archived card movement and effects against the bound native decision."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_archive_batch as batch
from spireshift import native_a8_archive_matching_v2 as owners
from spireshift import native_a8_archive_reward_owners_v4 as previous
from spireshift import native_a8_archive_rewards_v3 as rewards
from spireshift import native_a8_replay_probe as replay
from spireshift import native_a8_replay_source as source
from spireshift.native_a8_replay_source import Intent, Journal
from spireshift.native_compatibility_contract import verified

MATCHER = "native-a8-archive-effects-v5"
STOLEN_CARD_LABEL = "Take your stolen card back."
# Both use mandatory, unfiltered FromHand selection followed by a native exhaust.
MANDATORY_HAND_EXHAUST = {"BRAND", "BURNING_PACT"}
legacy_next_choice = replay.next_choice


def discarded_opening_copies(
    rows: list[dict[str, Any]], plan: tuple[Intent, ...]
) -> dict[int, tuple[tuple[int, str], ...]]:
    """Track verified opening discards until a later record moves the physical copy."""
    moves = {
        intent.record["s"] + offset
        for intent in plan
        if intent.kind == "pick" and "archive_opening" in intent.record
        for offset in range(1, intent.record["n_picked"] + 1)
    }
    hand_checks = {i.record["s"] for i in plan if i.kind in {"pick", "play"}}
    discard: dict[int, str] = {}
    at_choice = {}
    for row in rows:
        tag, step = row["t"], row["s"]
        if tag in {"combat_start", "combat_end"}:
            discard.clear()
        if tag == "play" and row.get("auto") is False:
            # Playing the physical copy again witnesses an unlogged return.
            discard.pop(row["c"], None)
        if discard and step in hand_checks:
            at_choice[step] = tuple(discard.items())
        if step in moves:
            replay.equal("opening discard record", "discard", tag)
            discard[row["c"]] = row["id"]
        elif tag in {"draw", "generate", "exhaust", "play"}:
            discard.pop(row["c"], None)
        elif tag == "transform":
            discard.pop(row["from_c"], None)
        elif tag == "shuffle":
            for cid in row["order_c"]:
                discard.pop(cid, None)
        elif tag == "flush":
            for cid in row["flushed_c"] + row["retained_c"]:
                discard.pop(cid, None)
    return at_choice


def with_discards(intent: Intent, discarded: tuple[tuple[int, str], ...]) -> Intent:
    copies = {cid for cid, _ in discarded}
    return replace(
        intent,
        hand=tuple((cid, name) for cid, name in intent.hand if cid not in copies),
        generated=intent.generated - copies,
        returns=tuple((cid, name) for cid, name in intent.returns if cid not in copies),
        discard=discarded + tuple((cid, name) for cid, name in intent.discard if cid not in copies),
    )


def forced_exhaust(
    rows: list[dict[str, Any]], parent: Intent, pick: Intent, successor: Intent
) -> Intent | None:
    row = pick.record
    if (
        parent.kind != "play"
        or parent.record["id"] not in MANDATORY_HAND_EXHAUST
        or pick.offer is not None
        or row["n_picked"] != 1
        or len(row["cards"]) != 1
        or owners.location(parent.record) != owners.location(row)
    ):
        return None
    (chosen,) = row["cards"]
    start = parent.record["s"]
    effects = rows[row["s"] + 1 : successor.record["s"]]
    if not effects:
        return None
    exhaust = effects[0]
    if (
        (chosen["c"], chosen["id"]) not in parent.hand
        or chosen["c"] == parent.record["c"]
        or exhaust["t"] != "exhaust"
        or (exhaust["c"], exhaust["id"], exhaust["ethereal"]) != (chosen["c"], chosen["id"], False)
        or any(owners.location(effect) != owners.location(row) for effect in effects)
        or any(
            r["t"] in {"draw", "discard", "exhaust", "generate", "transform", "play"}
            for r in rows[start + 1 : row["s"]]
        )
    ):
        return None
    # The source must explain the hand after the effect. A flush immediately
    # before a recorded end turn is the journal's report of that next input.
    safe_effects = {"block", "draw", "energy", "flush", "hp", "intent", "power", "relic_counter"}
    if any(effect["t"] not in safe_effects for effect in effects[1:]):
        return None
    drawn = [r["id"] for r in effects[1:] if r["t"] == "draw"]
    flushes = [r for r in effects[1:] if r["t"] == "flush"]
    if flushes and (successor.kind != "end_turn" or flushes != [effects[-1]]):
        return None
    return Intent(
        "forced_exhaust",
        {**row, "round": parent.record["turn"], "hand_after": drawn, "card": chosen},
    )


def compile_intents(rows: list[dict[str, Any]]) -> tuple[Intent, ...]:
    legacy = previous.compile_intents(rows)
    discards = discarded_opening_copies(rows, legacy)
    plan: list[Intent] = []
    for index, intent in enumerate(legacy):
        if intent.kind in {"play", "pick"} and intent.record["s"] in discards:
            intent = with_discards(intent, discards[intent.record["s"]])
        if intent.kind == "pick" and plan and index + 1 < len(legacy):
            proof = forced_exhaust(rows, plan[-1], intent, legacy[index + 1])
            if proof is not None:
                plan.append(proof)
        plan.append(intent)
    return tuple(plan)


def exhaust_count(context: dict[str, Any], chosen: dict[str, Any]) -> int:
    piles = owners.public_read(context, "combat_piles")
    (exhaust,) = (zone["cards"] for zone in piles["zones"] if zone["zone"] == "exhaust")
    return sum(
        c["definition_id"] == chosen["id"] and c["is_upgraded"] == bool(chosen["up"])
        for c in exhaust
    )


def next_choice(
    frame: dict[str, Any], journal: Journal, cursor: int, end: int
) -> tuple[int | None, int, str]:
    """Consume a forced effect only after its verified native parent action."""
    context = frame["public_input"]["context"]
    interaction = context["interaction"]
    owner = interaction["content"].get("context", {})
    plan = journal.intents
    if (
        cursor < end
        and plan[cursor].kind == "forced_exhaust"
        and interaction["kind"] == "card_selection"
    ):
        cursor += 1
    elif cursor < end and plan[cursor].kind == "forced_exhaust":
        row = plan[cursor].record
        replay.equal(
            "forced selection location",
            owners.location(row),
            owners.location(context["persistent"]["run"]),
        )
        replay.equal(
            "forced exhaust successor",
            ("combat_turn", row["round"], "player", True),
            (
                interaction["kind"],
                owner.get("round"),
                owner.get("turn_owner"),
                owner.get("is_play_phase"),
            ),
        )
        replay.equal("forced exhausted card", 1, exhaust_count(context, row["card"]))
        replay.equal(
            "forced exhaust successor hand",
            row["hand_after"],
            [card["definition_id"] for card in owner["player"]["hand"]],
        )
        cursor += 2  # The exact effect accounts for the archived pick.
    index, following, domain = legacy_next_choice(frame, journal, cursor, end)
    if index is not None and cursor < following < end and plan[following].kind == "forced_exhaust":
        parent, proof = plan[following - 1], plan[following].record
        replay.equal("forced selector parent", ("play", "native"), (parent.kind, domain))
        hand = owner["player"]["hand"]
        if len(hand) == 2 and exhaust_count(context, proof["card"]) == 0:
            _, chosen_slot = replay.ordered_slots(
                parent, hand, [parent.record["c"], proof["card"]["c"]]
            )
            (chosen,) = (card for card in hand if card["entity_id"]["public_slot"] == chosen_slot)
            replay.equal(
                "forced selection upgrade", bool(proof["card"]["up"]), chosen["is_upgraded"]
            )
        else:
            following += 1  # Match the actual selector using the ordinary pick contract.
    return index, following, domain


def stolen_reward(frame: dict[str, Any], intent: Intent, journal: Journal) -> int | None:
    row = intent.record
    context = rewards.reward_owner(frame, row)
    offers = [
        r
        for r in context["interaction"]["content"]["surface"]["rewards"]
        if r["kind"] == "SpecialCardReward"
    ]
    if intent.kind == "restoration_successor":
        previous.match(frame, intent, journal)
        replay.equal("stolen card claim consumed", [], offers)
        return None
    replay.equal(
        "pre-restoration deck",
        sorted(row["restoration_before"]),
        sorted(owners.public_deck(context)),
    )
    replay.equal("unique special-card reward", 1, len(offers))
    (offer,) = offers
    replay.equal(
        "stolen-card reward presentation",
        (STOLEN_CARD_LABEL, STOLEN_CARD_LABEL, True),
        (
            offer["label"],
            offer["description"],
            offer["enabled"],
        ),
    )
    return replay.unique(
        frame["public_input"]["candidates"],
        lambda a: (
            a["verb"] == "activate"
            and a["arguments"] == []
            and (a["subject"] or {}).get("role") == "reward"
            and a["subject"]["public_slot"] == offer["entity_id"]["public_slot"]
            and a["subject"]["properties"] == offer
            and a["subject"]["state"] == {"enabled": True, "visible": True}
        ),
    )


def match(frame: dict[str, Any], intent: Intent, journal: Journal) -> int | None:
    if intent.kind == "restoration_successor" or "restoration_before" in intent.record:
        return stolen_reward(frame, intent, journal)
    return previous.match(frame, intent, journal)


def card_choice(frame: dict[str, Any], intent: Intent) -> tuple[int, bool]:
    owner = frame["public_input"]["context"]["interaction"]["kind"]
    replay.equal(
        "card selector present", True, owner in {"card_selection", "native_generated_card_choice"}
    )
    return owners.card_choice(frame, intent)


@contextmanager
def installed() -> Iterator[None]:
    with (
        previous.installed(),
        patch.multiple(replay, next_choice=next_choice, match=match, card_choice=card_choice),
    ):
        yield


def screen(root: Path, case: dict[str, Any]) -> tuple[Journal | None, dict[str, Any]]:
    if case.get("saved") and case["saved"].get("matcher_contract") != MATCHER:
        return previous.screen(root, case)
    path = verified(root, case["source"])
    try:
        with patch.object(source, "compile_intents", compile_intents):
            journal = source.read(path)
        facts = batch.source_facts(journal)
    except (ValueError, LookupError, TypeError, StopIteration) as exc:
        return None, {"status": "source_rejected", "error": str(exc)}
    replay.equal("declared world", case["seed"], journal.seed)
    return journal, {"status": "source_ready", **facts}
