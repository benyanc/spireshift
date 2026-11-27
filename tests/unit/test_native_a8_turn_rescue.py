from typing import Any

from spireshift.native_a8_turn_rescue import summarize


def test_rescue_gate_counts_worlds_and_requires_resolved_endpoints() -> None:
    plan: list[dict[str, Any]] = [
        {
            "key": f"p{player}-{i}",
            "player": player,
            "seed": f"p{player}-world-{i}",
            "root": f"p{player}-root-{i}",
        }
        for player in (2, 3)
        for i in range(2)
    ]
    rows: dict[str, Any] = {
        task["key"]: {
            "task": task,
            "outcome": "loss",
            "observed_room_outcome": "reward",
            "encounter": "elite" if task["key"].endswith("0") else "normal",
        }
        for task in plan
    }
    assert summarize(plan, rows)["candidate_for_separate_preference_admission"]

    rows["p2-1"]["task"] = {**plan[1], "seed": plan[0]["seed"]}
    assert not summarize(plan, rows)["candidate_for_separate_preference_admission"]

    rows["p2-1"]["task"] = plan[1]
    rows["p2-1"]["observed_room_outcome"] = "unresolved"
    assert not summarize(plan, rows)["candidate_for_separate_preference_admission"]
