import copy
import gzip
import json
from pathlib import Path
from typing import Any

import pytest

from spireshift.engine_neural import INPUT_SCHEMA
from spireshift.native_a8_archive_batch import (
    FAMILIES,
    WIN,
    labels,
    recorded_selectors,
    summarize,
    validate_plan,
)
from spireshift.native_flow_verification_v12 import records


def deck_selection(effect: str) -> list[dict[str, Any]]:
    common = {"act": 1, "floor": 4, "decision_id": 7, "decision_type": f"deck_select_{effect}"}
    card = {"option_index": 1, "c": 3, "id": "DEFEND_IRONCLAD", "up": 0}
    change = (
        {"from_c": 3, "from_id": "DEFEND_IRONCLAD", "to_c": 22, "to_id": "IRON_WAVE"}
        if effect == "transform"
        else {"c": 3, "id": "DEFEND_IRONCLAD", "enchantment": "SPIRAL"}
    )
    return [
        {
            **common,
            "t": "decision",
            "s": 0,
            "min_select": 1,
            "max_select": 1,
            "options": [
                {
                    "option_index": 1,
                    "instance_id": 3,
                    "option_id": "DEFEND_IRONCLAD",
                    "up": 0,
                    "presented": True,
                    "selectable": True,
                }
            ],
        },
        {**common, "t": "pick", "s": 1, "selector": "human", "n_picked": 1, "cards": [card]},
        {**common, **change, "t": effect, "s": 2, "option_index": 1},
        {
            **common,
            "t": "outcome",
            "s": 3,
            "outcome": "select",
            "n_selected": 1,
            "selected_option_indices": [1],
        },
    ]


@pytest.mark.parametrize("effect", ["transform", "enchant"])
def test_selector_outcome_keeps_the_exact_recorded_pick(effect: str) -> None:
    rows = deck_selection(effect)
    before = copy.deepcopy(rows)
    (intent,) = recorded_selectors(rows)
    assert intent.kind == "pick"
    assert intent.record == rows[1]
    assert intent.offer == rows[0]
    assert rows == before


@pytest.mark.parametrize("gap", ["wrong_copy", "missing_effect", "different_outcome", "no_pick"])
def test_inconsistent_selector_records_fail_closed(gap: str) -> None:
    rows = deck_selection("transform")
    if gap == "wrong_copy":
        rows[1]["cards"][0]["c"] = 99
    elif gap == "missing_effect":
        rows[2]["t"] = "other"
    elif gap == "different_outcome":
        rows[3]["selected_option_indices"] = [0]
    else:
        rows[1]["t"] = "other"
    with pytest.raises(ValueError, match="Deck selector"):
        recorded_selectors(rows)


def test_reserved_world_cannot_become_a_training_source() -> None:
    cfg: dict[str, Any] = {
        "schema_version": "native-a8-archive-batch-v1",
        "game_build": "v0.111.0+41cef1ea",
        "batch": "test",
        "case_wall_seconds": 120,
        "wall_seconds": 240,
        "development_seeds": ["DEVW0RLD"],
        "final_test_seeds": ["TESTW0RLD"],
        "cases": [
            {
                "run_id": "0123456789abcdef",
                "source": {"path": "artifacts/demo.ndjson", "sha256": "1" * 64},
                "seed": "TRA1NW0RLD",
            }
        ],
    }
    validate_plan(cfg)
    cfg["cases"][0]["seed"] = cfg["final_test_seeds"][0]
    with pytest.raises(ValueError, match="reserved seeds must be distinct"):
        validate_plan(cfg)


def test_only_complete_distinct_wins_count_towards_admission() -> None:
    rows = {
        str(i): {
            "status": WIN,
            "seed": f"W{i}",
            "opening": f"opening-{i % 2}",
            "act1_boss": f"act1-{i % 2}",
            "final_boss": f"final-{i % 2}",
            "by_act": {act: dict.fromkeys(FAMILIES, 1) for act in (1, 2, 3)},
            "deliveries": 60,
            "labels": {"path": f"world-{i}", "sha256": str(i)},
        }
        for i in range(3)
    }
    cfg = {"cases": [1, 2, 3, 4]}
    rows["3"] = {"status": "source_rejected"}
    assert summarize(cfg, rows)["candidate_for_separate_fitting_admission"] is True
    rows["3"] = {"status": "unattempted"}
    assert summarize(cfg, rows)["candidate_for_separate_fitting_admission"] is False
    rows["3"] = {"status": "diverged"}
    rows["2"]["seed"] = rows["1"]["seed"]
    assert summarize(cfg, rows)["candidate_for_separate_fitting_admission"] is False


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row) + "\n")


def public_trace(root: Path, *, incomplete: bool = False) -> None:
    observations: list[dict[str, Any]] = []
    delivered: list[dict[str, Any]] = []
    for i, (act, verb, domain) in enumerate(
        (
            (1, "select", "local_answer_factor"),
            (1, "confirm", "native"),
            (2, "play", "native"),
            (3, "play", "native"),
        )
    ):
        family = "card_selection" if act == 1 else "combat_turn"
        menu = [{"bound_action_id": f"A{i}"}]
        observations.append(
            {
                "snapshot": {
                    "snapshot_id": str(i),
                    "bound_actions": {
                        "status": "incomplete" if incomplete and i == 2 else "complete",
                        "total_count": 1,
                        "actions": menu,
                    },
                }
            }
        )
        delivered.append(
            {
                "frame": {
                    "public_input": {
                        "schema_version": INPUT_SCHEMA,
                        "context": {
                            "persistent": {"run": {"act": act, "floor": i if act > 1 else 1}},
                            "interaction": {"kind": family},
                        },
                        "candidates": [{"verb": verb}],
                    },
                    "actions": [{"raw_index": 0, **menu[0]}],
                    "binding_id": f"B{i}",
                    "terminal": False,
                },
                "choice": {"action_index": 0, "binding_id": f"B{i}"},
                "receipt": {
                    "bound_action_id": f"A{i}",
                    "delivery": "delivered",
                    "delivery_domain": domain,
                    "before_snapshot_id": str(i),
                    "successor_snapshot_id": str(i + 1),
                },
            }
        )
    observations.append({"snapshot": {"snapshot_id": "4"}})
    (root / "worker").mkdir()
    write_rows(root / "worker/public-observations.jsonl.gz", observations)
    write_rows(root / "matched-deliveries.jsonl.gz", delivered)


def test_local_factors_are_grouped_as_one_public_answer(tmp_path: Path) -> None:
    public_trace(tmp_path)
    target = tmp_path / "labels.jsonl.gz"
    result = labels(tmp_path, target, 4)
    assert result["deliveries"] == 4
    assert result["decisions"] == 3
    first, *_ = records(target)
    assert first["family"] == "card_selection"
    assert [f["public_input"]["candidates"][0]["verb"] for f in first["factors"]] == [
        "select",
        "confirm",
    ]
    assert all(set(f) == {"public_input", "action_index"} for f in first["factors"])


def test_partial_public_menu_cannot_supply_labels(tmp_path: Path) -> None:
    public_trace(tmp_path, incomplete=True)
    with pytest.raises(ValueError, match="complete delivered public menu"):
        labels(tmp_path, tmp_path / "labels.jsonl.gz", 4)
