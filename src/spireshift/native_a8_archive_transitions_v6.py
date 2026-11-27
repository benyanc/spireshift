"""Reconcile recorded effects at the first playable turn and special reward claims."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_archive_batch as batch
from spireshift import native_a8_archive_effects_v5 as previous
from spireshift import native_a8_replay_probe as replay
from spireshift import native_a8_replay_source as source
from spireshift.native_a8_archive_matching_v2 import location, source_deck
from spireshift.native_a8_replay_source import Intent, Journal
from spireshift.native_compatibility_contract import verified

MATCHER = "native-a8-archive-transitions-v6"
POPPER = "FESTIVE_POPPER"
FIRST_TURN_DAMAGE = 9


def direct_restorations(
    rows: list[dict[str, Any]],
) -> dict[int, tuple[list[dict[str, Any]], list[dict[str, Any]]]]:
    """Prove a special grant restores the same physical copy removed in this combat."""
    deck = {c["c"]: c for c in rows[0]["starting_deck"]}
    removed: dict[int, tuple[dict[str, Any], dict[str, Any]]] = {}
    result = {}
    for index, row in enumerate(rows):
        tag = row["t"]
        if tag == "combat_start":
            removed.clear()
        elif tag == "deck":
            deck = {c["c"]: c for c in row["cards"]}
        elif tag == "remove" and row["c"] in deck:
            card = deck[row["c"]]
            if row["id"] == card["id"]:
                removed[row["c"]] = (row, card)
        elif tag == "resolve" and row.get("reward_kind") == "SpecialCardReward":
            if not 0 < index < len(rows) - 1:
                continue
            acquisition = rows[index - 1]
            successor = rows[index + 1]
            if (
                acquisition["t"] != "acquire"
                or acquisition.get("source") != "granted"
                or acquisition["c"] not in removed
                or successor["t"] != "deck"
            ):
                continue
            removal, card = removed[acquisition["c"]]
            after = {c["c"]: c for c in successor["cards"]}
            restored = after.pop(card["c"], None)
            if (
                all(location(r) == location(row) for r in (removal, acquisition, successor))
                and acquisition["id"] == card["id"]
                and acquisition["c"] not in deck
                and restored in (card, {**card, "added_floor": row["floor"]})
                and after == deck
                and len(after) + 1 == len(successor["cards"])
            ):
                result[row["s"]] = (list(deck.values()), successor["cards"])
    return result


def settled_enemies(
    start: dict[str, Any], effects: list[dict[str, Any]]
) -> list[dict[str, Any]] | None:
    """Apply recorded nonlethal first-turn damage to exact enemy copies."""
    if any(location(row) != location(start) for row in effects):
        return None
    enemies = {e["cid"]: e for e in start["enemies"]}
    hits: dict[int, int] = {}
    first_turn = False
    for row in effects:
        tag = row["t"]
        if tag == "turn":
            if first_turn or (row["side"], row["round"], row["n"]) != ("player", 1, 1):
                return None
            first_turn = True
        elif tag in {"death", "spawn", "play", "potion_start"} or (
            tag == "hp" and row.get("dst_cid") in enemies
        ):
            return None
        elif tag == "hit":
            cid = row.get("dst_cid")
            if (
                not first_turn
                or type(cid) is not int
                or cid not in enemies
                or cid in hits
                or row.get("dst") != enemies[cid]["id"]
                or row.get("src") != "player"
                or row.get("card") is not None
                or row.get("dmg_type") != ["unpowered"]
                or row.get("blocked") != 0
                or row.get("dmg") != FIRST_TURN_DAMAGE
                or row.get("killed") is not False
                or enemies[cid]["hp"] <= FIRST_TURN_DAMAGE
            ):
                return None
            hits[cid] = row["dmg"]
    if not hits:
        return None
    return [{**e, "hp": e["hp"] - hits.get(e["cid"], 0)} for e in start["enemies"]]


def compile_intents(rows: list[dict[str, Any]]) -> tuple[Intent, ...]:
    restored = direct_restorations(rows)
    popper = next((row["s"] for row in rows if row["t"] == "relic" and row["id"] == POPPER), None)
    prior = previous.compile_intents(rows)
    plan = []
    for index, intent in enumerate(prior):
        row = intent.record
        s = row["s"]
        if intent.kind == "reward" and s in restored:
            before, after = restored[s]
            plan.append(replace(intent, record={**row, "restoration_before": source_deck(before)}))
            plan.append(
                Intent("restoration_successor", {**row, "restoration_after": source_deck(after)})
            )
            continue
        if (
            intent.kind == "combat_start"
            and popper is not None
            and popper < s
            and index + 1 < len(prior)
        ):
            first = prior[index + 1]
            if first.kind in {"play", "end_turn", "potion_start", "potion_dropped"}:
                enemies = settled_enemies(row, rows[s + 1 : first.record["s"]])
                if enemies is not None:
                    intent = replace(
                        intent, record={**row, "enemies": enemies, "first_turn_relic": POPPER}
                    )
        plan.append(intent)
    return tuple(plan)


def match(frame: dict[str, Any], intent: Intent, journal: Journal) -> int | None:
    if relic := intent.record.get("first_turn_relic"):
        context = frame["public_input"]["context"]
        owner = context["interaction"]["content"]["context"]
        replay.equal(
            "settled first turn",
            (1, "player", True),
            (
                owner.get("round"),
                owner.get("turn_owner"),
                owner.get("is_play_phase"),
            ),
        )
        replay.equal(
            "first-turn relic ownership",
            1,
            sum(r["definition_id"] == relic for r in context["persistent"]["player"]["relics"]),
        )
    return previous.match(frame, intent, journal)


@contextmanager
def installed() -> Iterator[None]:
    with previous.installed(), patch.object(replay, "match", match):
        yield


def screen(root: Path, case: dict[str, Any]) -> tuple[Journal | None, dict[str, Any]]:
    if case.get("saved"):
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
