from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from spireshift.native_a8_feedback_credit import (
    RoomEvidence,
    classify_rooms,
    room_advantages,
    with_room_credit,
)
from spireshift.native_a8_own_ppo import Decision


def frame(
    floor: int, kind: str, *, hp: int = 20, choices: int = 2, **details: str
) -> dict[str, Any]:
    return {
        "candidates": [{} for _ in range(choices)],
        "context": {
            "persistent": {"run": {"act": 1, "floor": floor}, "player": {"hp": hp}},
            "interaction": {"kind": kind, "content": {"context": details}},
        },
    }


def test_only_native_combat_completion_and_terminal_death_supply_credit() -> None:
    evidence = classify_rooms(
        [
            frame(2, "combat_turn", encounter_type="normal"),
            frame(2, "reward_claim", reward_kind="potion_pickup"),
            frame(3, "combat_turn", encounter_type="normal"),
            frame(3, "combat_turn", encounter_type="normal", choices=1),
            frame(3, "reward_claim", reward_kind="room_rewards"),
            frame(4, "combat_turn", encounter_type="elite"),
        ],
        {
            "public_input": frame(4, "run_end", hp=0),
            "terminal": True,
            "ending": {"victory": False},
        },
    )
    assert evidence == RoomEvidence(
        [(1, 2), None, (1, 3), None, None, (1, 4)],
        {(1, 3): ("normal", True), (1, 4): ("elite", False)},
    )


def test_repeated_combat_at_the_same_floor_and_caps_supply_no_outcome() -> None:
    fight = frame(2, "combat_turn", encounter_type="normal")
    evidence = classify_rooms(
        [fight, frame(2, "reward_claim", reward_kind="room_rewards"), fight],
        {"public_input": fight, "terminal": False},
    )
    assert evidence.outcomes == {}


def test_room_credit_excludes_the_current_world_and_preserves_critic_targets() -> None:
    room, boss = (1, 2), (1, 3)
    raw, counts = room_advantages(
        [
            RoomEvidence([room, None, boss], {room: ("normal", True), boss: ("boss", False)}),
            RoomEvidence([room], {room: ("normal", False)}),
            RoomEvidence([room], {room: ("normal", True)}),
        ]
    )
    assert counts == {"normal": {"reward_reached": 2, "terminal_loss": 1}}
    assert raw == [0.5, None, None, -1.0, 0.5]
    base = [Decision((), (), -0.5, 0.25, value) for value in (0.1, 0.2, 0.3, -0.2, -0.1)]
    changed = with_room_credit(base, raw)
    assert [d.target for d in changed] == [d.target for d in base]
    assert changed[1:3] == base[1:3]
    assert changed[0].advantage > base[0].advantage
    assert changed[3].advantage < base[3].advantage


def test_native_ending_and_confirmation_bindings() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Run the public binding tests with the bundled Node on native hosts")
    result = subprocess.run(
        [node, "--test", "scripts/engine-combat-feedback-v1.test.mjs"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
