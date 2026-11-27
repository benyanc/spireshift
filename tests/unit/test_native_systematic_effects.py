from __future__ import annotations

import copy
import gzip
import json
from pathlib import Path
from typing import Any

import pytest

from spireshift.native_systematic_effects_v1 import counter_boundary, upgrade_effect


def card_frame(cards: list[tuple[str, bool]], selected: str = "STRIKE") -> dict[str, Any]:
    return {
        "public_input": {
            "context": {
                "reads": [
                    {
                        "kind": "run_deck",
                        "content": {
                            "cards": [
                                {"definition_id": name, "is_upgraded": upgraded}
                                for name, upgraded in cards
                            ]
                        },
                    }
                ]
            },
            "candidates": [
                {
                    "verb": "confirm",
                    "arguments": [{"entity": {"properties": {"definition_id": selected}}}],
                }
            ],
        }
    }


def test_smith_requires_the_selected_card_to_upgrade_and_preserves_deck_membership() -> None:
    case = {"instructions": ["SMITH", "confirm_card", "proceed"]}
    before = card_frame([("STRIKE", False), ("DEFEND", False)])
    after = card_frame([("STRIKE", True), ("DEFEND", False)])
    result = upgrade_effect(case, [before, before, after, after])
    assert result["upgraded_definition"] == "STRIKE"
    wrong = card_frame([("STRIKE", False), ("DEFEND", True)])
    with pytest.raises(ValueError, match="different card"):
        upgrade_effect(case, [before, before, wrong, wrong])
    extra = card_frame([("STRIKE", True), ("DEFEND", False), ("BASH", False)])
    with pytest.raises(ValueError, match="exactly one"):
        upgrade_effect(case, [before, before, extra, extra])


@pytest.mark.parametrize("value", [None, 0, "true"])
def test_smith_does_not_guess_missing_or_untyped_upgrade_flags(value: Any) -> None:
    frame = card_frame([("STRIKE", False)])
    frame["public_input"]["context"]["reads"][0]["content"]["cards"][0]["is_upgraded"] = value
    with pytest.raises(ValueError, match="upgrade facts"):
        upgrade_effect({"instructions": ["SMITH", "confirm_card"]}, [frame, frame, frame])


def test_actual_activation_display_must_withhold_snapshot_authority(tmp_path: Path) -> None:
    directory = tmp_path / "official"
    directory.mkdir()
    path = directory / "live-public.jsonl.gz"
    row: dict[str, Any] = {
        "kind": "observed",
        "snapshot": {
            "status": "settling",
            "persistent": {
                "content": {"player": {"relics": [{"definition_id": "HAPPY_FLOWER", "counter": 3}]}}
            },
            "bound_actions": {"actions": []},
        },
    }

    def write(value: dict[str, Any]) -> None:
        with gzip.open(path, "wt") as stream:
            stream.write(json.dumps(value) + "\n")

    write(row)
    assert counter_boundary(tmp_path)["activation_frames_observed"] == 1
    changed = copy.deepcopy(row)
    changed["snapshot"]["status"] = "interactive"
    write(changed)
    with pytest.raises(ValueError, match="authority"):
        counter_boundary(tmp_path)
    changed["snapshot"]["status"] = "settling"
    changed["snapshot"]["bound_actions"]["actions"] = [{"verb": "end_turn"}]
    write(changed)
    with pytest.raises(ValueError, match="authority"):
        counter_boundary(tmp_path)
