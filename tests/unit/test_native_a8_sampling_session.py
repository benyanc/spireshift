from typing import Any

import pytest

from spireshift.native_a8_sampling_session import summarize


@pytest.mark.parametrize(("second_seed", "qualifies"), [("world-b", True), ("world-a", False)])
def test_clear_gate_requires_two_worlds_and_both_initializers(
    second_seed: str, qualifies: bool
) -> None:
    plan: list[dict[str, Any]] = [
        {
            "key": f"p{player}-{arm}",
            "root": f"p{player}-boss-1",
            "seed": seed,
            "draw": 0,
            "player": player,
            "arm": arm,
        }
        for player, seed in ((2, "world-a"), (3, second_seed))
        for arm in ("standard", "sharp")
    ]
    rows: dict[str, Any] = {
        task["key"]: {
            "task": task,
            "outcome": "loss",
            "completed_acts": int(task["arm"] == "sharp"),
            "first_suffix_draw_key": f"draw-{task['root']}",
            "root_input_id": f"menu-{task['root']}",
        }
        for task in plan
    }
    assert summarize(plan, rows)["candidate_for_further_training_collection"] is qualifies
    rows["p3-sharp"]["outcome"] = "capped"
    assert not summarize(plan, rows)["candidate_for_further_training_collection"]
    rows["p3-sharp"]["outcome"] = "loss"
    rows["p3-sharp"]["first_suffix_draw_key"] = "foreign-draw"
    with pytest.raises(ValueError, match="paired draw"):
        summarize(plan, rows)
