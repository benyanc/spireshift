import json
from pathlib import Path
from typing import Any

import pytest

from spireshift import native_a8_archive_act1_source as source
from spireshift import native_a8_archive_transitions_v6 as transitions
from spireshift.native_a8_replay_source import BUILD, Intent


def journal(path: Path, *, before_entry: str | None = None) -> None:
    boss = "THE_KIN_BOSS"
    rows: list[dict[str, Any]] = [
        {
            "t": "header",
            "build_id_full": BUILD,
            "replay_version": 7,
            "character": "IRONCLAD",
            "ascension": 8,
            "game_mode": "standard",
            "player_count": 1,
            "floor": 0,
            "act": 1,
            "reloads": 0,
            "full_console": False,
            "modifiers": [],
            "mods": [],
            "seed": "ABCDE",
        },
        {"t": "act", "act": 1, "name": "OVERGROWTH"},
        {"t": "map", "act": 1, "boss": boss},
        {"t": "hp", "act": 1, "hp": 71, "dst": "player"},
        {"t": "combat_start", "act": 1, "combat_id": f"1.17:{boss}", "attempt_id": 0},
        {
            "t": "combat_end",
            "act": 1,
            "combat_id": f"1.17:{boss}",
            "floor": 17,
            "attempt_id": 0,
            "result": "victory",
        },
        {"t": "room_exit", "act": 1, "floor": 17},
        *([] if before_entry is None else [{"t": before_entry, "act": 1}]),
        {"t": "act", "act": 2, "floor": 17, "name": "HIVE"},
        {"t": "resume", "act": 2},
    ]
    path.write_text("\n".join(json.dumps({**row, "s": i}) for i, row in enumerate(rows)))


def test_prefix_ends_at_act2_before_later_reloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "source.ndjson"
    journal(path)

    def compile_act1(rows: list[dict[str, Any]]) -> tuple[Intent, ...]:
        assert {row["act"] for row in rows} == {1}
        assert rows[-1]["t"] == "room_exit"
        return (
            Intent(
                "event",
                {"floor": 1, "option_id": "NEOW.EXAMPLE"},
                {"event_id": "NEOW"},
            ),
        )

    monkeypatch.setattr(transitions, "compile_intents", compile_act1)
    archive = source.read(path)
    assert archive.journal.seed == "ABCDE"
    assert archive.entry["act"] == 2
    assert archive.journal.intents[-1].kind == source.EXIT


@pytest.mark.parametrize("record", ["header", "resume", "end"])
def test_prefix_rejects_segment_change_before_act2(tmp_path: Path, record: str) -> None:
    path = tmp_path / "source.ndjson"
    journal(path, before_entry=record)
    with pytest.raises(ValueError, match="ends before Act 2"):
        source.read(path)
