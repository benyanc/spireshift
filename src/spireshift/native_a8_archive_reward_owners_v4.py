"""Match co-generated card rewards and purchases with missing archive slots."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from itertools import groupby
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_archive_batch as batch
from spireshift import native_a8_archive_matching_v2 as owners
from spireshift import native_a8_archive_rewards_v3 as rewards
from spireshift import native_a8_replay_probe as replay
from spireshift import native_a8_replay_source as source
from spireshift.native_a8_replay_source import Intent, Journal
from spireshift.native_compatibility_contract import verified

MATCHER = "native-a8-archive-reward-owners-v4"
CARD_LABEL = "Add a card to your deck."
legacy_stage = replay.stage


def card_group(intent: Intent) -> tuple[int, int] | None:
    if intent.kind == "card_reward" and intent.record["t"] == "acquire":
        return owners.location(intent.record)
    return None


def card_sequence(rows: list[dict[str, Any]], claims: list[Intent]) -> list[Intent] | None:
    """Require a single generation sequence and an exact deck effect for each pick."""
    offers = [claim.offer for claim in claims if claim.offer is not None]
    if len(offers) != len(claims):
        return None
    ordered = sorted(offers, key=lambda offer: offer["s"])
    first, last = ordered[0]["s"], ordered[-1]["s"]
    here = owners.location(claims[0].record)
    ids = [offer["decision_id"] for offer in ordered]
    if (
        len(ids) != len(set(ids))
        or rows[first : last + 1] != ordered
        or last >= claims[0].record["s"]
        or any(
            offer["decision_type"] != "card_reward"
            or owners.location(offer) != here
            or offer.get("offer_generation") != 0
            or offer.get("can_reroll") is not False
            for offer in ordered
        )
    ):
        return None
    before = next(
        (r["cards"] for r in reversed(rows[:first]) if r["t"] == "deck"),
        rows[0]["starting_deck"],
    )
    plan = []
    for claim in claims:
        row = claim.record
        completion, deck = rows[row["s"] + 1 : row["s"] + 3]
        if (
            completion["t"] != "resolve"
            or completion["reward_kind"] != "CardReward"
            or owners.location(completion) != here
            or deck["t"] != "deck"
            or owners.location(deck) != here
        ):
            return None
        after = {card["c"]: card for card in deck["cards"]}
        new = after.pop(row["c"], None)
        if (
            new is None
            or new["id"] != row["id"]
            or row["c"] in after
            or after != {card["c"]: card for card in before}
        ):
            return None
        slot = ids.index(row["decision_id"])
        plan.append(
            replace(
                claim,
                record={
                    **row,
                    "queue_count": len(ids),
                    "queue_slot": slot,
                    "queue_deck": owners.source_deck(before),
                },
            )
        )
        ids.pop(slot)
        plan.append(
            Intent(
                "card_queue_successor",
                {
                    **row,
                    "queue_count": len(ids),
                    "queue_deck": owners.source_deck(deck["cards"]),
                },
            )
        )
        before = deck["cards"]
    return plan


def slotless_relics(rows: list[dict[str, Any]]) -> set[int]:
    recorded = set()
    relic = None
    for row in rows:
        if row["t"] == "relic":
            relic = row
        elif row["t"] == "buy":
            if (
                relic is not None
                and row.get("kind") == "relic"
                and "slot" not in row
                and row.get("cost_resource") == "gold"
                and row.get("id") == relic["id"]
                and owners.location(row) == owners.location(relic)
                and type(row.get("cost_current")) is int
                and row["cost_current"] >= 0
                and type(row.get("gold_on_hand")) is int
                and row["gold_on_hand"] >= 0
            ):
                recorded.add(row["s"])
            relic = None
    return recorded


def compile_intents(rows: list[dict[str, Any]]) -> tuple[Intent, ...]:
    purchases = slotless_relics(rows)
    plan = []
    for key, grouped in groupby(rewards.compile_intents(rows), key=card_group):
        claims = list(grouped)
        if key is not None and len(claims) > 1:
            card_plan = card_sequence(rows, claims)
            if card_plan is not None:
                plan.extend(card_plan)
                continue
        for claim in claims:
            if claim.kind == "buy" and claim.record["s"] in purchases:
                claim = replace(claim, record={**claim.record, "slotless_relic": True})
                plan.extend((claim, Intent("relic_purchase_successor", claim.record)))
            else:
                plan.append(claim)
    return tuple(plan)


def read(path: Path) -> Journal:
    with patch.object(source, "compile_intents", compile_intents):
        return source.read(path)


def queued_cards(context: dict[str, Any]) -> list[dict[str, Any]]:
    interaction = context["interaction"]
    if interaction["kind"] != "reward_claim":
        return []
    return [
        reward
        for reward in interaction["content"]["surface"]["rewards"]
        if reward["kind"] == "card" and reward["label"] == CARD_LABEL
    ]


def stage(frame: dict[str, Any], intent: Intent, journal: Journal) -> int | None:
    row = intent.record
    context = frame["public_input"]["context"]
    if (
        intent.kind != "card_reward"
        or "queue_slot" not in row
        or context["interaction"]["kind"] != "reward_claim"
    ):
        return legacy_stage(frame, intent, journal)
    rewards.reward_owner(frame, row)
    deck_effect(context, row)
    available = queued_cards(context)
    replay.equal("recorded card reward count", row["queue_count"], len(available))
    reward = available[row["queue_slot"]]
    replay.equal(
        "native card reward opener", (True, CARD_LABEL), (reward["enabled"], reward["description"])
    )
    slot = reward["entity_id"]["public_slot"]
    return replay.unique(
        frame["public_input"]["candidates"],
        lambda action: (
            action["verb"] == "activate"
            and action["arguments"] == []
            and (action["subject"] or {}).get("role") == "reward"
            and action["subject"]["public_slot"] == slot
            and action["subject"]["properties"] == reward
        ),
    )


def deck_effect(context: dict[str, Any], record: dict[str, Any]) -> None:
    replay.equal(
        "card reward deck", sorted(record["queue_deck"]), sorted(owners.public_deck(context))
    )


def relic_purchase(frame: dict[str, Any], intent: Intent) -> int | None:
    row = intent.record
    context = frame["public_input"]["context"]
    player = context["persistent"]["player"]
    successor = intent.kind == "relic_purchase_successor"
    cost = row["cost_current"]
    replay.equal(
        "merchant location", owners.location(row), owners.location(context["persistent"]["run"])
    )
    replay.equal("merchant gold", row["gold_on_hand"] + (0 if successor else cost), player["gold"])
    replay.equal(
        "merchant relic copies",
        int(successor),
        sum(relic["definition_id"] == row["id"] for relic in player["relics"]),
    )
    if successor:
        return None
    interaction = context["interaction"]
    surface = interaction["content"]["surface"]
    replay.equal(
        "merchant inventory",
        ("shop_inventory", True),
        (interaction["kind"], surface.get("inventory_open")),
    )
    (entry,) = (
        relic
        for relic in surface["relics"]
        if relic["price"] == cost
        and relic["can_purchase"]
        and relic["stocked"]
        and relic["relic"]["definition_id"] == row["id"]
    )
    slot = entry["entity_id"]["public_slot"]
    return replay.unique(
        frame["public_input"]["candidates"],
        lambda action: (
            action["verb"] == "activate"
            and action["arguments"] == []
            and (action["subject"] or {}).get("role") == "relic"
            and action["subject"]["public_slot"] == slot
            and action["subject"]["properties"]["price"] == cost
        ),
    )


def match(frame: dict[str, Any], intent: Intent, journal: Journal) -> int | None:
    row = intent.record
    if "slotless_relic" in row:
        return relic_purchase(frame, intent)
    if "queue_deck" in row:
        context = frame["public_input"]["context"]
        replay.equal(
            "card reward location",
            owners.location(row),
            owners.location(context["persistent"]["run"]),
        )
        deck_effect(context, row)
        if intent.kind == "card_queue_successor":
            replay.equal(
                "remaining card reward offers", row["queue_count"], len(queued_cards(context))
            )
            return None
    return rewards.match(frame, intent, journal)


@contextmanager
def installed() -> Iterator[None]:
    with rewards.installed(), patch.multiple(replay, stage=stage, match=match):
        yield


def screen(root: Path, case: dict[str, Any]) -> tuple[Journal | None, dict[str, Any]]:
    if case.get("saved") and case["saved"].get("matcher_contract") != MATCHER:
        return rewards.screen(root, case)
    path = verified(root, case["source"])
    try:
        journal = read(path)
        facts = batch.source_facts(journal)
    except (ValueError, LookupError, TypeError, StopIteration) as exc:
        return None, {"status": "source_rejected", "error": str(exc)}
    replay.equal("declared world", case["seed"], journal.seed)
    return journal, {"status": "source_ready", **facts}
