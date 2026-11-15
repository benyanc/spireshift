"""Match recorded selector cancellation and native automatic upgrade effects."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_archive_act1_source as act1
from spireshift import native_a8_archive_transitions_v6 as transitions
from spireshift import native_a8_replay_probe as replay
from spireshift.native_a8_archive_matching_v2 import location, public_deck, source_deck
from spireshift.native_a8_replay_source import Intent, Journal

REST_OPEN = "rest_upgrade_open"
REST_CANCEL = "rest_upgrade_cancel"
REST_RETURN = "rest_upgrade_cancelled"
AUTO_UPGRADE = "automatic_combat_upgrade"
prior_compile = transitions.compile_intents


def rest_cancellation(
    rows: list[dict[str, Any]], rest: Intent, pick: Intent
) -> tuple[Intent, ...] | None:
    if (
        rest.kind != "rest"
        or rest.offer is None
        or pick.kind != "pick"
        or pick.record["cards"]
        or pick.record["n_picked"] != 0
        or pick.record["selector"] != "human"
    ):
        return None
    row, offer, answer = rest.record, rest.offer, pick.record
    slot = answer["s"]
    if not 1 <= slot < len(rows) - 1:
        return None
    selector, decline = rows[slot - 1], rows[slot + 1]
    if (
        selector.get("decision_type") != "deck_select_upgrade"
        or selector["t"] != "decision"
        or selector.get("decline_available") is not True
        or decline["t"] != "outcome"
        or decline.get("decision_type") != "deck_select_upgrade"
        or decline.get("decision_id") != selector["decision_id"]
        or decline.get("outcome") != "decline"
        or decline.get("selected_option_indices") != []
        or decline.get("n_selected") != 0
        or row["option"] == "smith"
        or slot - 2 != offer["s"]
        or slot + 1 >= row["s"]
        or any(location(x) != location(row) for x in (offer, selector, answer, decline))
        or any(
            r["t"] != "hp" or r.get("dst") != "player" or r.get("src") != row["option"]
            for r in rows[slot + 2 : row["s"]]
        )
    ):
        return None
    (smith,) = (
        x
        for x in offer["options"]
        if x["option_id"] == "smith" and x["presented"] and x["selectable"]
    )
    preceding = rows[: offer["s"]]
    deck = next(
        (r["cards"] for r in reversed(preceding) if r["t"] == "deck"), rows[0]["starting_deck"]
    )
    hp = next(r["hp"] for r in reversed(preceding) if r["t"] == "hp" and r["dst"] == "player")
    facts = {
        **row,
        "s": selector["s"],
        "option": "smith",
        "option_index": smith["option_index"],
        "original_deck": source_deck(deck),
        "original_hp": hp,
        "original_gold": selector["gold_on_hand"],
    }
    return (
        Intent(REST_OPEN, facts, offer),
        replace(pick, kind=REST_CANCEL, record={**facts, "s": slot}, offer=selector),
        Intent(REST_RETURN, {**facts, "s": decline["s"]}, offer),
        rest,
    )


def automatic_upgrade(rows: list[dict[str, Any]], parent: Intent, pick: Intent) -> Intent | None:
    if (
        parent.kind != "play"
        or parent.record["id"] != "ARMAMENTS"
        or parent.record["up"] != 0
        or pick.kind != "pick"
        or pick.record["n_picked"] != 1
        or len(pick.record["cards"]) != 1
    ):
        return None
    card = pick.record["cards"][0]
    if not 0 <= pick.record["s"] < len(rows) - 1:
        return None
    effect = rows[pick.record["s"] + 1]
    if (
        card["up"] != 0
        or effect["t"] != "upgrade"
        or (effect["c"], effect["id"]) != (card["c"], card["id"])
        or location(effect) != location(parent.record)
        or location(pick.record) != location(parent.record)
    ):
        return None
    return replace(
        pick,
        kind=AUTO_UPGRADE,
        record={**pick.record, "cards": [{**card, "up": 1}], "round": parent.record["turn"]},
    )


def compile_intents(rows: list[dict[str, Any]]) -> tuple[Intent, ...]:
    prior = prior_compile(rows)
    revised: list[Intent] = []
    cursor = 0
    while cursor < len(prior):
        intent = prior[cursor]
        if cursor + 1 < len(prior):
            following = prior[cursor + 1]
            cancellation = rest_cancellation(rows, intent, following)
            if cancellation is not None:
                revised.extend(cancellation)
                cursor += 2
                continue
            if effect := automatic_upgrade(rows, intent, following):
                revised.extend((intent, effect, following))
                cursor += 2
                continue
        revised.append(intent)
        cursor += 1
    return tuple(revised)


def read(path: Path) -> act1.ActOne:
    with patch.object(transitions, "compile_intents", compile_intents):
        return act1.read(path)


def player_facts(frame: dict[str, Any], intent: Intent) -> None:
    context = frame["public_input"]["context"]
    state = context["persistent"]
    player = state["player"]
    row = intent.record
    replay.equal("rest location", location(row), location(state["run"]))
    replay.equal(
        "rest player around selector",
        (row["original_hp"], row["original_gold"], sorted(row["original_deck"])),
        (player["hp"], player["gold"], sorted(public_deck(context))),
    )


def rest_facts(frame: dict[str, Any], intent: Intent) -> None:
    owner = frame["public_input"]["context"]["interaction"]
    assert intent.offer is not None
    expected = [
        (option["option_index"], option["option_id"], option["selectable"])
        for option in intent.offer["options"]
        if option["presented"]
    ]
    replay.equal("rest owner", "rest_site", owner["kind"])
    native = [
        (option["index"], option["option_id"].lower(), option["enabled"])
        for option in owner["content"]["surface"]["options"]
    ]
    replay.equal("rest menu after selector", expected, native)


def cancel_upgrade(frame: dict[str, Any], intent: Intent) -> int:
    public = frame["public_input"]
    owner = public["context"]["interaction"]
    assert intent.offer is not None
    replay.equal("upgrade selection owner", "card_selection", owner["kind"])
    surface = owner["content"]["surface"]
    replay.equal(
        "upgrade selector bounds and cancellation",
        (intent.offer["min_select"], intent.offer["max_select"], True),
        (surface["min_select"], surface["max_select"], surface["cancelable"]),
    )
    replay.equal(
        "upgrade choices",
        sorted(
            (card["option_id"], card["up"])
            for card in intent.offer["options"]
            if card["presented"] and card["selectable"]
        ),
        sorted((card["definition_id"], int(card["is_upgraded"])) for card in surface["cards"]),
    )
    return replay.unique(public["candidates"], lambda candidate: candidate["verb"] == "cancel")


def verify_upgrade(frame: dict[str, Any], intent: Intent) -> None:
    context = frame["public_input"]["context"]
    owner = context["interaction"]
    combat = owner["content"]["context"]
    row = intent.record
    replay.equal("upgrade location", location(row), location(context["persistent"]["run"]))
    replay.equal(
        "upgrade successor",
        ("combat_turn", row["round"], "player", True),
        (owner["kind"], combat.get("round"), combat.get("turn_owner"), combat.get("is_play_phase")),
    )
    (card,) = row["cards"]
    replay.ordered_slots(intent, combat["player"]["hand"], [card["c"]])


@contextmanager
def matching() -> Iterator[None]:
    with act1.matching():
        base_match, base_choice = replay.match, replay.next_choice

        def match(frame: dict[str, Any], intent: Intent, journal: Journal) -> int | None:
            if intent.kind in {REST_OPEN, REST_CANCEL, REST_RETURN}:
                player_facts(frame, intent)
                if intent.kind == REST_CANCEL:
                    return cancel_upgrade(frame, intent)
                rest_facts(frame, intent)
                if intent.kind == REST_RETURN:
                    return None
                intent = replace(intent, kind="rest")
            return base_match(frame, intent, journal)

        def next_choice(
            frame: dict[str, Any], journal: Journal, cursor: int, end: int
        ) -> tuple[int | None, int, str]:
            if cursor < end and journal.intents[cursor].kind == AUTO_UPGRADE:
                owner = frame["public_input"]["context"]["interaction"]["kind"]
                if owner == "card_selection":
                    cursor += 1
                else:
                    verify_upgrade(frame, journal.intents[cursor])
                    cursor += 2
            index, following, domain = base_choice(frame, journal, cursor, end)
            if index is not None and cursor < following < end:
                effect = journal.intents[following]
                if effect.kind == AUTO_UPGRADE:
                    parent = journal.intents[following - 1]
                    (card,) = effect.record["cards"]
                    player = frame["public_input"]["context"]["interaction"]["content"]["context"][
                        "player"
                    ]
                    before = replace(
                        parent,
                        record={**parent.record, "cards": [parent.record, {**card, "up": 0}]},
                    )
                    replay.equal("upgrade parent", ("play", "native"), (parent.kind, domain))
                    replay.ordered_slots(before, player["hand"], [parent.record["c"], card["c"]])
            return index, following, domain

        with patch.multiple(replay, match=match, next_choice=next_choice):
            yield
