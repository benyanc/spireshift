from __future__ import annotations

from typing import Any

import pytest

from spireshift.native_a8_rescue_curriculum import assess
from spireshift.native_a8_rescue_game import Progress
from spireshift.native_a8_rescue_inputs import CONTROL, cases


def frame(act: int, family: str, owner: dict[str, Any], label: str) -> dict[str, Any]:
    return {
        "terminal": False,
        "public_input": {
            "context": {
                "persistent": {
                    "run": {"act": act, "floor": 1, "ascension": 8},
                    "player": {"character_definition_id": "IRONCLAD", "hp": 10},
                },
                "interaction": {"kind": family, "content": {"context": owner}},
            },
            "candidates": [{"label": label}],
        },
    }


def test_act2_requires_boss_combat_and_native_boss_reward_continue() -> None:
    progress = Progress()
    start = frame(1, "event_option", {"event_id": "NEOW"}, "Continue")
    boss = frame(1, "combat_turn", {"encounter_type": "boss"}, "Play Strike")
    rewards = frame(1, "reward_claim", {"completed_boss_combat": True}, "Continue from rewards")
    act2 = frame(2, "map_navigation", {}, "Enter next act")

    assert progress.observe(start) is None
    with pytest.raises(ValueError, match="delivered Act 1 boss rewards"):
        progress.observe(act2)
    assert progress.observe(boss) is None
    assert progress.observe(rewards) is None
    progress.delivered(rewards, 0, "local_answer_factor")
    with pytest.raises(ValueError, match="delivered Act 1 boss rewards"):
        progress.observe(act2)
    progress.delivered(rewards, 0, "native")
    assert progress.observe(act2) == "act1_clear"


def test_qualification_requires_both_initializers_and_a_complete_clear_advantage() -> None:
    worlds = cases()
    assert len({c["seed"] for group in worlds.values() for c in group} | {CONTROL["seed"]}) == 21
    planned = worlds["qualify"]
    rows: list[dict[str, Any]] = [
        {
            "case": c,
            "outcomes": {
                "original": "act1_loss",
                "fitted": "act1_loss",
                "teacher": "act1_clear" if i < 2 else "act1_loss",
            },
            "strict_rescue_confirmed": i < 2,
            "label_reasons": [],
        }
        for i, c in enumerate(planned)
    ]
    assert assess("qualify", planned, rows)["passed"]
    assert not assess("qualify", planned, rows[:-1])["passed"]
    rows[1]["strict_rescue_confirmed"] = False
    assert not assess("qualify", planned, rows)["passed"]
    rows[1]["strict_rescue_confirmed"] = True
    rows[2]["outcomes"]["teacher"] = "capped"
    result = assess("qualify", planned, rows)
    assert result["outcomes_by_arm"]["teacher"] == {"act1_clear": 2, "act1_loss": 5, "capped": 1}
    assert not result["passed"]


def test_collection_needs_delivered_target_coverage_on_confirmed_rescues() -> None:
    planned = cases()["collect"]
    rows: list[dict[str, Any]] = [
        {
            "case": c,
            "outcomes": {
                "original": "act1_loss",
                "fitted": "act1_loss",
                "teacher": "act1_clear" if i < 3 else "act1_loss",
            },
            "strict_rescue_confirmed": i < 3,
            "label_file": {"sha256": str(i)} if i < 3 else None,
            "label_reasons": [["hp_spend"], ["potion"], ["rest"]][i] if i < 3 else [],
        }
        for i, c in enumerate(planned)
    ]
    assert assess("collect", planned, rows)["passed"]
    rows[2]["label_reasons"] = ["potion"]
    assert not assess("collect", planned, rows)["passed"]
