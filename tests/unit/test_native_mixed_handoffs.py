from __future__ import annotations

import copy
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_mixed_handoff_cases_v4 import enter_declared_rest
from spireshift.native_mixed_handoff_checks_v1 import belt_controls
from spireshift.native_mixed_handoff_checks_v2 import rest_menu
from spireshift.native_mixed_handoff_checks_v3 import control_label
from spireshift.native_mixed_handoff_inputs_v1 import cases
from spireshift.native_selector_lifecycle_trace import Trace


def test_mixed_fixture_source_guards_and_nonmutating_setup() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for serialized fixture controls")
    run = subprocess.run(
        [node, "--test", "scripts/engine-mixed-handoff-fixtures-v1.test.mjs"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert run.returncode == 0, run.stdout + run.stderr


def belt_fixture() -> dict[str, Any]:
    bottles = [
        {
            "entity_id": f"physical-{slot}",
            "definition_id": "BLOOD_POTION",
            "name": "Blood Potion",
            "description": "Heal 20%",
            "slot": slot,
        }
        for slot in (0, 1)
    ]
    states = [
        {**row, "can_use": True, "can_discard": True, "target_entity_ids": ["self"]}
        for row in bottles
    ]
    actions = [
        {
            "verb": verb,
            "subject_referent_id": row["entity_id"],
            "arguments": (
                [] if verb == "activate" else [{"role": "target", "referent_id": "self"}]
            ),
        }
        for row in bottles
        for verb in ("activate", "use")
    ]
    return {
        "snapshot": {
            "persistent": {"content": {"player": {"potions": bottles}}},
            "interaction": {"content": {"surface": {"potion_states": states}}},
            "bound_actions": {"actions": actions},
        }
    }


def test_identical_bottles_keep_all_physical_slot_controls() -> None:
    belt_controls(belt_fixture())


@pytest.mark.parametrize(
    "corruption", ["duplicate_discard", "missing_target", "stale_slot", "conflicting_view"]
)
def test_belt_contract_rejects_mixed_owner_corruption(corruption: str) -> None:
    observation = copy.deepcopy(belt_fixture())
    snapshot = observation["snapshot"]
    states = snapshot["interaction"]["content"]["surface"]["potion_states"]
    actions = snapshot["bound_actions"]["actions"]
    if corruption == "duplicate_discard":
        actions.append(copy.deepcopy(actions[0]))
    elif corruption == "missing_target":
        actions[1]["arguments"] = []
    elif corruption == "stale_slot":
        states[1]["slot"] = 0
    else:
        states[0]["description"] = "Different bottle"
    with pytest.raises(ValueError):
        belt_controls(observation)


def test_panel_declares_disjoint_worlds_and_a_short_case_for_each_family() -> None:
    rows = cases()
    assert len(rows) == 12
    assert len({row["seed"] for row in rows}) == 12
    assert all(canonical_seed(row["seed"]) == row["seed"] for row in rows)
    assert {row["family"] for row in rows[:3]} == {"reward", "shop", "rest"}


def rest_fixture() -> Trace:
    current = {
        "snapshot": {
            "persistent": {"content": {"player": {"potions": []}}},
            "interaction": {
                "kind": "rest_site",
                "content": {
                    "surface": {
                        "options": [{"option_id": "HEAL", "is_enabled": True}],
                        "can_leave": False,
                        "potion_states": [],
                    }
                },
            },
            "bound_actions": {"actions": []},
        }
    }
    frame = {
        "public_input": {
            "context": {
                "interaction": {
                    "kind": "rest_site",
                    "content": {
                        "surface": {
                            "options": [{"option_id": "HEAL", "enabled": True}],
                            "can_proceed": False,
                        }
                    },
                },
                "persistent": {"player": {"hp": 31, "max_hp": 80, "relics": [], "potions": []}},
                "reads": [{"kind": "run_deck", "content": {"cards": [], "card_count": 0}}],
            },
            "candidates": [
                {
                    "verb": "activate",
                    "label": "Rest",
                    "arguments": [],
                    "subject": {"properties": {"option_id": "HEAL"}},
                }
            ],
        },
        "actions": [{"bound_action_id": "one-current-action", "raw_index": 0}],
    }
    return cast(Trace, SimpleNamespace(current=current, frame=frame))


def test_rest_checker_binds_native_permissions_to_normalized_learner_fields() -> None:
    rest_menu(rest_fixture(), {"HEAL": True}, False)


@pytest.mark.parametrize("field", ["option", "exit"])
def test_rest_checker_rejects_disagreement_between_raw_and_normalized_permissions(
    field: str,
) -> None:
    trace = rest_fixture()
    raw = trace.current["snapshot"]["interaction"]["content"]["surface"]
    if field == "option":
        raw["options"][0]["is_enabled"] = False
    else:
        raw["can_leave"] = True
    with pytest.raises(ValueError, match="permissions disagree"):
        rest_menu(trace, {"HEAL": True}, False)


def test_rest_exit_uses_the_exact_semantic_binding_despite_display_label_changes() -> None:
    raw: dict[str, Any] = {
        "verb": "close",
        "subject_referent_id": None,
        "arguments": [],
        "label": "Leave rest site",
    }
    candidate = {"verb": "activate", "label": "Proceed to map"}
    match = control_label("Proceed to map")
    assert match(raw, candidate)
    assert not match({**raw, "arguments": [{"role": "target", "referent_id": "stale"}]}, candidate)
    assert not match({**raw, "verb": "activate"}, candidate)
    assert not match(raw, {**candidate, "label": "Abandon run"})


@pytest.mark.parametrize("map_type", ["restsite", "rest_site"])
def test_declared_next_room_is_bound_by_legal_coordinates_and_verified_after_arrival(
    map_type: str,
) -> None:
    current = {
        "snapshot": {
            "interaction": {
                "kind": "map_navigation",
                "content": {
                    "surface": {"next_options": [{"col": 2, "row": 1, "point_type": map_type}]}
                },
            },
            "referents": [
                {"referent_id": "right-coordinate", "properties": {"col": 2, "row": 1}},
                {"referent_id": "wrong-coordinate", "properties": {"col": 4, "row": 1}},
            ],
        }
    }
    trace = SimpleNamespace(current=current)

    def take(matches: Any) -> None:
        assert matches(
            {"verb": "activate", "subject_referent_id": "right-coordinate", "arguments": []}, {}
        )
        assert not matches(
            {"verb": "activate", "subject_referent_id": "wrong-coordinate", "arguments": []}, {}
        )
        trace.current = {"snapshot": {"interaction": {"kind": "rest_site"}}}

    trace.take = take
    enter_declared_rest(cast(Trace, trace))
