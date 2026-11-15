"""Recover recorded owner transitions for the frozen native archive replay."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_archive_batch as batch
from spireshift import native_a8_replay_probe as replay
from spireshift import native_a8_replay_source as source
from spireshift.native_a8_replay_source import Intent, Journal
from spireshift.native_compatibility_contract import verified

MATCHER = "native-a8-archive-owner-matching-v2"
legacy_match = replay.match
legacy_card_choice = replay.card_choice


def location(record: dict[str, Any]) -> tuple[int, int]:
    return record["act"], record["floor"]


def source_deck(cards: list[dict[str, Any]]) -> list[tuple[str, int, str]]:
    return [(c["id"], c["up"], c.get("enchantment") or "") for c in cards]


def public_deck(context: dict[str, Any]) -> list[tuple[str, int, str]]:
    return [
        (
            c["definition_id"],
            int(c["is_upgraded"]),
            (c.get("existing_enchantment") or {}).get("definition_id", ""),
        )
        for c in public_read(context, "run_deck")["cards"]
    ]


def shop_records(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[int, tuple[Intent, ...]]]:
    """Join shop records to the originating transaction, including explicit declines."""
    merchants = {location(r) for r in rows if r["t"] == "room" and r["kind"] == "merchant"}
    offers = {r["decision_id"]: r for r in rows if r["t"] == "decision"}
    outcomes: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        if row["t"] == "outcome" and "decision_id" in row:
            outcomes.setdefault(row["decision_id"], []).append(row)
    normalized = list(rows)
    cancellations: dict[int, tuple[Intent, ...]] = {}
    inventories: dict[tuple[int, int], dict[str, Any]] = {}
    deck = rows[0]["starting_deck"]
    for i, row in enumerate(rows):
        tag = row["t"]
        if tag not in {"deck", "shop", "acquire", "decision"}:
            continue
        here = location(row)
        if tag == "deck":
            deck = row["cards"]
        elif tag == "shop":
            inventories[here] = row
        elif tag == "acquire" and row.get("source") in {"reward", "shop"} and here in merchants:
            stale_reward = row["source"] == "reward"
            offer = offers.get(row.get("decision_id"))
            if stale_reward and offer is not None and location(offer) == here:
                continue  # A current offer retains its own owner.
            buy, successor = rows[i + 1 : i + 3]
            shop = inventories[here]
            stock = [
                card
                for card in shop["cards"]
                if card["slot"] == buy.get("slot")
                and card.get("id") == row["id"]
                and card["stocked"] is True
                and card["cost"] == buy.get("cost_current")
            ]
            before = {c["c"]: c for c in deck}
            after = {c["c"]: c for c in successor.get("cards", [])}
            acquired = after.pop(row["c"], None)
            if (
                buy["t"] != "buy"
                or buy.get("kind") != "card"
                or buy.get("id") != row["id"]
                or successor["t"] != "deck"
                or location(buy) != here
                or location(successor) != here
                or len(stock) != 1
                or buy.get("cost_resource") != "gold"
                or shop["gold"] - buy["cost_current"] != buy["gold_on_hand"]
                or row["c"] in before
                or acquired is None
                or acquired["id"] != row["id"]
                or before != after
            ):
                if stale_reward:
                    raise ValueError(
                        f"Merchant acquisition {row['s']} has no exact purchase witness"
                    )
                continue  # Ordinary purchases retain the existing current-slot binding.
            normalized[i] = {**row, "source": "shop"}
            normalized[i + 1] = {
                **buy,
                "archive_shop_before": {"gold": shop["gold"], "deck": source_deck(deck)},
                "archive_shop_after": {
                    "gold": buy["gold_on_hand"],
                    "deck": source_deck(successor["cards"]),
                    "s": successor["s"],
                },
            }
        elif (
            tag == "decision" and row["decision_type"] == "deck_select_remove" and here in merchants
        ):
            results = outcomes.get(row["decision_id"], [])
            if not any(r["outcome"] == "decline" for r in results):
                continue
            pick = rows[i + 1]
            shop = inventories[here]
            if (
                len(results) != 1
                or location(results[0]) != here
                or results[0]["s"] <= pick["s"]
                or results[0]["n_selected"] != 0
                or results[0]["selected_option_indices"] != []
                or pick["t"] != "pick"
                or location(pick) != here
                or pick["selector"] != "human"
                or pick.get("decision_id", row["decision_id"]) != row["decision_id"]
                or pick.get("decision_type", row["decision_type"]) != row["decision_type"]
                or pick["n_picked"] != 0
                or pick["cards"] != []
                or (row["min_select"], row["max_select"], row["decline_available"]) != (1, 1, True)
                or shop["removal_stocked"] is not True
                or not 0 <= shop["removal_cost"] <= row["gold_on_hand"] == shop["gold"]
            ):
                raise ValueError(f"Shop removal {row['s']} has no exact cancellation witness")
            if any(
                r["t"] in {"remove", "buy"} and r.get("decision_id") == row["decision_id"]
                for r in rows[i + 1 : results[0]["s"]]
            ):
                raise ValueError(
                    f"Shop removal {row['s']} declined with a recorded charge or effect"
                )
            facts = {
                "gold": shop["gold"],
                "deck": source_deck(deck),
                "removal": shop["removal_cost"],
            }
            normalized[i] = {**row, "decision_type": "recorded_shop_removal_decline"}
            cancellations[pick["s"]] = (
                Intent(
                    "removal_owner",
                    {**row, "cost_current": facts["removal"], "archive_shop_before": facts},
                    row,
                ),
                Intent("shop_removal_cancel", {**pick, "archive_shop_before": facts}, row),
                Intent("shop_effect", {**pick, "archive_shop_after": facts}),
            )
    return normalized, cancellations


def opening_effect(
    rows: list[dict[str, Any]], entry: Intent, pick: Intent
) -> dict[str, Any] | None:
    """Recognize a recorded first-turn hand replacement with its ordered effects."""
    row = pick.record
    here = location(entry.record)
    first, chosen = entry.record["s"], row["s"]
    lead = rows[first + 1 : chosen]
    opening = [r for r in lead if r["t"] == "draw"]
    (n, cards) = row["n_picked"], row["cards"]
    if type(n) is not int or n < 0:
        return None
    moves = rows[chosen + 1 : chosen + 1 + 2 * n]
    discarded, drawn = moves[:n], moves[n:]
    hand = {r["c"]: r["id"] for r in opening}
    selected = [(c["c"], c["id"]) for c in cards]
    if (
        pick.offer is not None
        or location(row) != here
        or not opening
        or any(location(r) != here for r in (*lead, *moves))
        or [(r["n"], r["round"], r["side"]) for r in lead if r["t"] == "turn"] != [(1, 1, "player")]
        or any(r.get("turn_start") is not True for r in opening)
        or list(hand.items()) != list(pick.hand)
        or len(opening) != len(hand)
        or n != len(cards)
        or n != len({cid for cid, _ in selected})
        or any(hand.get(cid) != name for cid, name in selected)
        or any(r["t"] != "discard" for r in discarded)
        or [(r["c"], r["id"]) for r in discarded] != selected
        or len(drawn) != n
        or any(r["t"] != "draw" or r.get("turn_start") is not False for r in drawn)
    ):
        return None
    kept = hand.keys() - {cid for cid, _ in selected}
    return {
        "before": list(hand.values()),
        "after": [name for cid, name in hand.items() if cid in kept] + [r["id"] for r in drawn],
        "discarded": [name for _, name in selected],
        "enemies": [(e["id"], e["hp"], e["max_hp"]) for e in entry.record["enemies"]],
        "s": moves[-1]["s"] if moves else chosen,
    }


def compile_intents(rows: list[dict[str, Any]]) -> tuple[Intent, ...]:
    normalized, cancellations = shop_records(rows)
    legacy = batch.recorded_selectors(normalized)
    plan: list[Intent] = []
    for intent in legacy:
        row = intent.record
        if intent.kind == "pick" and row["s"] in cancellations:
            plan.extend(cancellations[row["s"]])
            continue
        if intent.kind == "pick" and plan and plan[-1].kind == "combat_start":
            facts = opening_effect(rows, plan[-1], intent)
            if facts is not None:
                entry = plan.pop()
                plan.append(
                    replace(
                        entry,
                        kind="opening_discard_owner",
                        record={**entry.record, "archive_opening": facts},
                    )
                )
                plan.append(replace(intent, record={**row, "archive_opening": facts}))
                plan.append(
                    Intent(
                        "opening_discard_effect", {**row, "s": facts["s"], "archive_opening": facts}
                    )
                )
                continue
        plan.append(intent)
        if intent.kind == "buy" and "archive_shop_after" in row:
            plan.append(Intent("shop_effect", {**row, "s": row["archive_shop_after"]["s"]}))
    return tuple(plan)


def read(path: Path) -> Journal:
    with patch.object(source, "compile_intents", compile_intents):
        return source.read(path)


def public_read(context: dict[str, Any], kind: str) -> dict[str, Any]:
    (content,) = (r["content"] for r in context["reads"] if r["kind"] == kind)
    return dict(content)


def shop_facts(context: dict[str, Any], expected: dict[str, Any]) -> None:
    replay.equal("shop gold", expected["gold"], context["persistent"]["player"]["gold"])
    replay.equal("shop deck", sorted(expected["deck"]), sorted(public_deck(context)))
    if "removal" in expected:
        service = public_read(context, "shop_catalog")["card_removal"]
        replay.equal(
            "shop removal remains stocked at its price",
            (True, expected["removal"]),
            (service["stocked"], service["price"]),
        )


def opening_owner(context: dict[str, Any], facts: dict[str, Any], *, pending: bool) -> None:
    interaction = context["interaction"]
    owner = interaction["content"]["context"]
    surface = interaction["content"]["surface"]
    hand = owner.get("player", {}).get("hand", [])
    replay.equal(
        "opening decision owner",
        ("card_selection", "combat", 1, "player", False)
        if pending
        else ("combat_turn", "combat", 1, "player", True),
        (
            interaction["kind"],
            owner.get("owner_kind", owner["kind"]),
            owner["round"],
            owner["turn_owner"],
            owner["is_play_phase"],
        ),
    )
    replay.equal(
        "initial enemies",
        facts["enemies"],
        [(e["definition_id"], e["hp"], e["max_hp"]) for e in owner["enemies"]],
    )
    replay.equal(
        "opening hand",
        facts["before" if pending else "after"],
        [card["definition_id"] for card in hand],
    )
    piles = public_read(context, "combat_piles")["zones"]
    (discard,) = (p["cards"] for p in piles if p["zone"] == "discard")
    replay.equal(
        "opening discard",
        Counter() if pending else Counter(facts["discarded"]),
        Counter(card["definition_id"] for card in discard),
    )
    if pending:
        replay.equal(
            "opening selector permissions",
            (0, False, True, True),
            (
                surface["min_select"],
                surface["cancelable"],
                surface["require_manual_confirmation"],
                surface["max_select"] >= len(hand),
            ),
        )
        replay.equal(
            "opening selector hand copies",
            [c["entity_id"] for c in hand],
            [c["entity_id"] for c in surface["cards"]],
        )


def match(frame: dict[str, Any], intent: Intent, journal: Journal) -> int | None:
    kind, row = intent.kind, intent.record
    if "archive_shop_before" not in row and kind not in {
        "shop_effect",
        "opening_discard_owner",
        "opening_discard_effect",
    }:
        return legacy_match(frame, intent, journal)
    context = frame["public_input"]["context"]
    interaction = context["interaction"]
    replay.equal("owner location", location(row), location(context["persistent"]["run"]))
    if kind in {"opening_discard_owner", "opening_discard_effect"}:
        opening_owner(context, row["archive_opening"], pending=kind == "opening_discard_owner")
        return None
    if kind == "shop_removal_cancel":
        owner, surface = (interaction["content"][key] for key in ("context", "surface"))
        replay.equal(
            "shop removal child",
            ("card_selection", "shop", 1, 1, True),
            (
                interaction["kind"],
                owner.get("owner_kind"),
                surface["min_select"],
                surface["max_select"],
                surface["cancelable"],
            ),
        )
        assert intent.offer is not None
        replay.equal(
            "shop removal offered copies",
            sorted(
                (o["option_id"], o["up"])
                for o in intent.offer["options"]
                if o["presented"] and o["selectable"]
            ),
            sorted((c["definition_id"], int(c["is_upgraded"])) for c in surface["cards"]),
        )
        shop_facts(context, row["archive_shop_before"])
        return replay.unique(frame["public_input"]["candidates"], lambda a: a["verb"] == "cancel")
    replay.equal(
        "open shop owner",
        ("shop_inventory", True),
        (interaction["kind"], interaction["content"]["surface"].get("inventory_open")),
    )
    shop_facts(
        context, row["archive_shop_after" if kind == "shop_effect" else "archive_shop_before"]
    )
    return None if kind == "shop_effect" else legacy_match(frame, intent, journal)


def card_choice(frame: dict[str, Any], intent: Intent) -> tuple[int, bool]:
    if "archive_opening" in intent.record:
        opening_owner(
            frame["public_input"]["context"], intent.record["archive_opening"], pending=True
        )
    return legacy_card_choice(frame, intent)


@contextmanager
def installed() -> Iterator[None]:
    """Use the same versioned rules for native play and raw receipt reconstruction."""
    with patch.multiple(replay, match=match, card_choice=card_choice):
        yield


def screen(root: Path, case: dict[str, Any]) -> tuple[Journal | None, dict[str, Any]]:
    if case.get("saved"):
        return batch.screen(root, case)
    path = verified(root, case["source"])
    try:
        journal = read(path)
        facts = batch.source_facts(journal)
    except (ValueError, LookupError, TypeError, StopIteration) as exc:
        return None, {"status": "source_rejected", "error": str(exc)}
    replay.equal("declared world", case["seed"], journal.seed)
    return journal, {"status": "source_ready", **facts}
