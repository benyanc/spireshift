"""Bind archived reward claims with corroborating source and successor facts."""

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
from spireshift import native_a8_replay_probe as replay
from spireshift import native_a8_replay_source as source
from spireshift.native_a8_replay_source import Intent, Journal
from spireshift.native_compatibility_contract import verified

MATCHER = "native-a8-archive-reward-matching-v3"


def restored_acquisitions(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[int, tuple[list[dict[str, Any]], list[dict[str, Any]]]]]:
    """Recover a special reward whose acquisition kept an older reward offer ID."""
    normalized = list(rows)
    restored = {}
    offers = {r["decision_id"]: r for r in rows if r["t"] == "decision"}
    removed: dict[int, dict[str, Any]] = {}
    deck = rows[0]["starting_deck"]
    acquisition = None
    for row in rows:
        tag = row["t"]
        if tag == "deck":
            deck = row["cards"]
        elif tag == "remove":
            removed[row["c"]] = row
        elif tag == "acquire":
            acquisition = row
        elif tag == "resolve" and row["reward_kind"] == "SpecialCardReward":
            if not acquisition or acquisition.get("source") != "reward":
                continue  # Preserve the existing direct-grant reader.
            here = owners.location(row)
            offer = offers.get(acquisition.get("decision_id"))
            removal = removed.get(acquisition["c"])
            successor = rows[row["s"] + 1]
            if (
                offer is None
                or owners.location(offer) == here
                or owners.location(acquisition) != here
                or removal is None
                or owners.location(removal) != here
                or removal["s"] >= acquisition["s"]
                or removal["id"] != acquisition["id"]
                or successor["t"] != "deck"
                or owners.location(successor) != here
            ):
                continue
            before = {card["c"]: card for card in deck}
            after = {card["c"]: card for card in successor["cards"]}
            acquired = after.pop(acquisition["c"], None)
            if acquired is None or acquired["id"] != acquisition["id"] or before != after:
                continue
            normalized[acquisition["s"]] = {**acquisition, "source": "granted"}
            restored[row["s"]] = (deck, successor["cards"])
    return normalized, restored


def gold_group(intent: Intent) -> tuple[tuple[int, int], int, int] | None:
    row = intent.record
    if intent.kind == "reward" and row.get("reward_kind") == "GoldReward":
        amount = row.get("gold")
        offer = row.get("decision_id")
        if type(amount) is int and amount > 0 and type(offer) is int:
            return owners.location(row), offer, amount
    return None


def balances(
    rows: list[dict[str, Any]],
    claims: list[Intent],
    amount: int,
) -> list[int] | None:
    result: list[int] = []
    for claim in claims:
        record = claim.record
        effect = rows[record["s"] - 1]
        gold = effect.get("gold")
        if (
            effect["t"] != "gold"
            or owners.location(effect) != owners.location(record)
            or type(gold) is not int
            or gold < amount
            or (result and gold != result[-1] + amount)
        ):
            return None
        result.append(gold)
    return result


def compile_intents(rows: list[dict[str, Any]]) -> tuple[Intent, ...]:
    normalized, restored = restored_acquisitions(rows)
    plan = []
    for key, grouped in groupby(owners.compile_intents(normalized), key=gold_group):
        claims = list(grouped)
        if key is not None and len(claims) > 1:
            _, _, amount = key
            recorded = balances(rows, claims, amount)
            if recorded is not None:
                for number, (claim, after) in enumerate(zip(claims, recorded, strict=True)):
                    remaining = len(claims) - number
                    plan.append(
                        replace(
                            claim,
                            kind="repeated_gold",
                            record={
                                **claim.record,
                                "balance": after - amount,
                                "remaining": remaining,
                            },
                        )
                    )
                    plan.append(
                        Intent(
                            "gold_successor",
                            {
                                **claim.record,
                                "balance": after,
                                "remaining": remaining - 1,
                            },
                        )
                    )
                continue
        for claim in claims:
            before_after = restored.get(claim.record["s"]) if claim.kind == "reward" else None
            if before_after is None:
                plan.append(claim)
            else:
                before, after_cards = before_after
                plan.append(
                    replace(
                        claim,
                        record={
                            **claim.record,
                            "restoration_before": owners.source_deck(before),
                        },
                    )
                )
                plan.append(
                    Intent(
                        "restoration_successor",
                        {
                            **claim.record,
                            "restoration_after": owners.source_deck(after_cards),
                        },
                    )
                )
    return tuple(plan)


def read(path: Path) -> Journal:
    with patch.object(source, "compile_intents", compile_intents):
        return source.read(path)


def reward_owner(frame: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = frame["public_input"]["context"]
    interaction = context["interaction"]
    replay.equal(
        "reward location", owners.location(record), owners.location(context["persistent"]["run"])
    )
    replay.equal("reward owner", "reward_claim", interaction["kind"])
    return context


def gold_choice(frame: dict[str, Any], intent: Intent) -> int | None:
    record = intent.record
    context = reward_owner(frame, record)
    surface = context["interaction"]["content"]["surface"]
    label = f"{record['gold']} Gold"
    matches = [
        row
        for row in surface["rewards"]
        if row["kind"] == "gold" and row["label"].removesuffix(" (stolen back)") == label
    ]
    replay.equal("remaining gold occurrences", record["remaining"], len(matches))
    replay.equal(
        "recorded gold balance", record["balance"], context["persistent"]["player"]["gold"]
    )
    if intent.kind == "gold_successor":
        return None
    for reward in matches:
        replay.equal(
            "ordinary equivalent gold reward",
            {"kind": "gold", "label": label, "description": label, "enabled": True},
            {k: v for k, v in reward.items() if k != "entity_id"},
        )
    slots = [r["entity_id"]["public_slot"] for r in matches]
    replay.equal("distinct native gold bindings", len(matches), len(set(slots)))
    candidates = frame["public_input"]["candidates"]

    def binding(reward: dict[str, Any]) -> int:
        return replay.unique(
            candidates,
            lambda a: (
                a["verb"] == "activate"
                and a["arguments"] == []
                and (a["subject"] or {}).get("role") == "reward"
                and a["subject"]["public_slot"] == reward["entity_id"]["public_slot"]
                and a["subject"]["properties"] == reward
                and a["subject"]["state"] == {"enabled": True, "visible": True}
            ),
        )

    indices = [binding(reward) for reward in matches]
    return indices[0]


def match(frame: dict[str, Any], intent: Intent, journal: Journal) -> int | None:
    if intent.kind in {"repeated_gold", "gold_successor"}:
        return gold_choice(frame, intent)
    if intent.kind == "restoration_successor":
        context = reward_owner(frame, intent.record)
        replay.equal(
            "restored reward deck",
            sorted(intent.record["restoration_after"]),
            sorted(owners.public_deck(context)),
        )
        return None
    if "restoration_before" in intent.record:
        context = reward_owner(frame, intent.record)
        replay.equal(
            "pre-restoration deck",
            sorted(intent.record["restoration_before"]),
            sorted(owners.public_deck(context)),
        )
    return owners.match(frame, intent, journal)


@contextmanager
def installed() -> Iterator[None]:
    with patch.multiple(replay, match=match, card_choice=owners.card_choice):
        yield


def screen(root: Path, case: dict[str, Any]) -> tuple[Journal | None, dict[str, Any]]:
    saved = case.get("saved")
    if saved and "matcher_contract" not in saved:
        return batch.screen(root, case)
    path = verified(root, case["source"])
    readers = {MATCHER: read, owners.MATCHER: owners.read}
    reader = readers[saved["matcher_contract"]] if saved else read
    try:
        journal = reader(path)
        facts = batch.source_facts(journal)
    except (ValueError, LookupError, TypeError, StopIteration) as exc:
        return None, {"status": "source_rejected", "error": str(exc)}
    replay.equal("declared world", case["seed"], journal.seed)
    return journal, {"status": "source_ready", **facts}
