"""Read the first uninterrupted Act 1 of a Spire Codex Ironclad/A8 journal."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_archive_transitions_v6 as transitions
from spireshift import native_a8_replay_probe as replay
from spireshift.native_a8_replay_source import BUILD, MAX_BYTES, Intent, Journal
from spireshift.native_flow_inputs_v12 import canonical_seed

EXIT = "act1_boss_reward_exit"


@dataclass(frozen=True)
class ActOne:
    journal: Journal
    opening: str
    entry: dict[str, Any]


def read(path: Path) -> ActOne:
    """Use only records available before the first transition into Act 2."""
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Archive journal exceeds the source size bound")
    rows: list[dict[str, Any]] = []
    entry: dict[str, Any] | None = None
    for i, line in enumerate(raw.splitlines()):
        row = json.loads(line)
        if not isinstance(row, dict) or row.get("s") != i:
            raise ValueError("Require contiguous source records through Act 2 entry")
        if i and row["t"] in {"header", "resume", "end"}:
            raise ValueError("The first capture segment ends before Act 2")
        if row["t"] == "act" and row["act"] == 2:
            entry = row
            break
        rows.append(row)
    if entry is None or not rows:
        raise ValueError("No recorded Act 2 entry from the original start")

    first, last = rows[0], rows[-1]
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
        or any(mod.get("affects_gameplay") is not False for mod in first["mods"])
    ):
        raise ValueError("Require one unmodified exact-build Ironclad/A8 normal start")
    (act,) = (r for r in rows if r["t"] == "act")
    (map_,) = (r for r in rows if r["t"] == "map")
    (act_number, floor, boss) = act["act"], entry["floor"], map_["boss"]
    fights = [r for r in rows if r["t"] in {"combat_start", "combat_end"}]
    started, ended = fights[::2], fights[1::2]
    if (
        act_number != 1
        or map_["act"] != 1
        or any(r.get("act", 1) != 1 for r in rows)
        or not fights
        or len(started) != len(ended)
        or any(r["t"] != "combat_start" or r["attempt_id"] != 0 for r in started)
        or any(
            r["t"] != "combat_end" or r["attempt_id"] != 0 or r["result"] != "victory"
            for r in ended
        )
        or [r["combat_id"] for r in started] != [r["combat_id"] for r in ended]
        or len({r["combat_id"] for r in fights}) != len(started)
        or ended[-1]["combat_id"].partition(":")[2] != boss
        or ended[-1]["floor"] != floor
        or (last["t"], last["act"], last["floor"]) != ("room_exit", 1, floor)
    ):
        raise ValueError("Require one recorded victory per fight and the Act 1 boss room exit")
    intents = transitions.compile_intents(rows)
    (opening,) = (
        intent.record["option_id"]
        for intent in intents
        if intent.kind == "event"
        and (intent.offer or {}).get("event_id") == "NEOW"
        and intent.record["floor"] == 1
        and intent.record["option_id"].startswith("NEOW.")
    )
    picks = {i.record["floor"] for i in intents if i.kind == "pick"}
    if any(
        i.kind == "event"
        and i.record["option_id"] == "CRYSTAL_SPHERE.pages.INITIAL.options.PAYMENT_PLAN"
        and i.record["floor"] not in picks
        for i in intents
    ):
        raise ValueError("Crystal Sphere Payment Plan has no recorded grid answer")
    journal = Journal(
        seed=canonical_seed(first["seed"]),
        header=first,
        starting_hp=next(r["hp"] for r in rows[1:] if r["t"] == "hp" and r["dst"] == "player"),
        act=act["name"],
        boss=boss,
        end=entry,
        exits=frozenset((r["act"], r["floor"]) for r in rows if r["t"] == "room_exit"),
        intents=(*intents, Intent(EXIT, last)),
    )
    return ActOne(journal, opening, entry)


@contextmanager
def matching() -> Iterator[None]:
    def match(frame: dict[str, Any], intent: Intent, journal: Journal) -> int | None:
        if intent.kind != EXIT:
            return transitions.match(frame, intent, journal)
        public = frame["public_input"]
        run = public["context"]["persistent"]["run"]
        owner = public["context"]["interaction"]
        replay.equal(
            "boss reward exit location", (1, intent.record["floor"]), (run["act"], run["floor"])
        )
        replay.equal("boss reward owner", "reward_claim", owner["kind"])
        replay.equal("reward kind", "room_rewards", owner["content"]["context"]["reward_kind"])
        return replay.named(
            public["candidates"], "Continue from rewards", "Skip remaining rewards and continue"
        )

    with transitions.installed(), patch.object(replay, "match", match):
        yield
