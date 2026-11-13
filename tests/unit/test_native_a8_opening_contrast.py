from typing import Any

from test_native_action_context import model, score
from test_native_live_policy import frame

from spireshift.core.manifest import manifest_identifier
from spireshift.native_a8_coverage_policy import Root
from spireshift.native_a8_opening_contrast import DistinctChooser, summarize
from spireshift.native_context_cache import cached_model


def test_opening_alternatives_exclude_the_first_visible_choice() -> None:
    public = frame()["public_input"]
    menu = public["candidates"]
    menu.extend([dict(menu[1]), {**menu[1], "label": "Observe"}])
    root = Root(
        {
            "source_task": {"seed": "TEST"},
            "root_input_id": manifest_identifier(public),
            "reference_action_index": 0,
        },
        (),
    )
    original = cached_model(model())
    choices = []
    for draw in range(2):
        chooser = DistinctChooser(original, score(), root)
        chooser.seed = f"TEST/OPENING/{draw}"
        chooser.draw = draw
        chooser.armed = True
        choices.append(chooser(public))
        assert sum(chooser.visits.values()) == 1
    a, b = choices
    assert b["previous_alternative_index"] == a["action_index"]
    assert len({menu[i]["label"] for i in (0, a["action_index"], b["action_index"])}) == 3
    assert b["log_probability"] > b["policy_log_probability"]


def test_opening_gate_needs_both_directions_and_encounter_types() -> None:
    plan: list[dict[str, Any]] = [
        {"key": f"p{p}-{i}", "root": f"p{p}-{i}", "player": p, "seed": f"world-{p}-{i}"}
        for p in (2, 3)
        for i in range(3)
    ]
    roots = {
        t["root"]: Root(
            {
                "reference_room_outcome": "reward" if t["key"].endswith("0") else "loss",
                "encounter": "elite" if t["key"].endswith("1") else "normal",
            },
            (),
        )
        for t in plan
    }
    rows: dict[str, Any] = {
        t["key"]: {
            "outcome": "loss",
            "observed_room_outcome": "loss" if t["key"].endswith("0") else "reward",
            "alternative_action_index": 1,
        }
        for t in plan
    }
    assert summarize(plan, rows, roots)["candidate_for_separate_preference_admission"]
    rows["p2-0"]["observed_room_outcome"] = "unresolved"
    assert not summarize(plan, rows, roots)["candidate_for_separate_preference_admission"]
    rows["p2-0"]["observed_room_outcome"] = "loss"
    for root in roots.values():
        root.spec["encounter"] = "normal"
    assert not summarize(plan, rows, roots)["candidate_for_separate_preference_admission"]
