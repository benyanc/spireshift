"""Bounded natural-run qualification, with an explicit terminal/presentation boundary."""

from __future__ import annotations

from typing import Any

from spireshift.native_flow_verification_v12 import same

METADATA_ONLY_CHOICE_FIELDS = {"model_id", "binding_id"}


def difference_paths(left: Any, right: Any, path: str = "") -> list[str]:
    """JSON numbers share a domain, while false/zero and null/missing stay distinct."""
    if type(left) in (int, float) and type(right) in (int, float):
        return [] if left == right else [path]
    if isinstance(left, dict) and isinstance(right, dict):
        result = []
        for key in sorted(left.keys() | right.keys()):
            next_path = f"{path}/{key}"
            result.extend(
                [next_path]
                if key not in left or key not in right
                else difference_paths(left[key], right[key], next_path)
            )
        return result
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        return [
            item
            for index, (a, b) in enumerate(zip(left, right, strict=True))
            for item in difference_paths(a, b, f"{path}/{index}")
        ]
    return [] if type(left) is type(right) and left == right else [path]


def equivalent_replayed_choice(current: dict[str, Any], historical: dict[str, Any]) -> bool:
    """Only version metadata may differ; all action, RNG and numerical fields compare."""
    return same(
        {k: v for k, v in current.items() if k not in METADATA_ONLY_CHOICE_FIELDS},
        {k: v for k, v in historical.items() if k not in METADATA_ONLY_CHOICE_FIELDS},
    )


def terminal_facts(frame: dict[str, Any]) -> dict[str, Any]:
    ending = frame.get("ending")
    if not isinstance(ending, dict):
        raise ValueError("Missing explicit native ending")
    if (
        frame.get("terminal") is not True
        or frame.get("source_family") != "game_over"
        or frame.get("terminal_actions_are_presentation") is not True
        or type(ending.get("victory")) is not bool
        or frame["ending"].get("basis")
        not in {"native_public_explicit_terminal_boolean", "shipped_public_RunHistory_Win_context"}
    ):
        raise ValueError("A cap, HP estimate or incomplete observation is not a native ending")
    context = frame["public_input"]["context"]
    persistent = context["persistent"]
    if (
        context["interaction"]["kind"] != "game_over"
        or persistent.get("scope") != "active_single_player_run"
        or persistent.get("run", {}).get("ascension") != 8
        or not any(read["kind"] == "run_deck" for read in context["reads"])
    ):
        raise ValueError("Incomplete ending public facts")
    return {
        "victory": frame["ending"]["victory"],
        "persistent": persistent,
        "reads": context["reads"],
    }


def compare_observations(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> dict[str, Any]:
    matched = 0
    difference = None
    ending_equal = False
    terminal_graph_differences: list[str] = []
    for index, (native, official) in enumerate(zip(left, right, strict=False)):
        if native["terminal"] or official["terminal"]:
            if native["terminal"] is not True or official["terminal"] is not True:
                difference = {"index": index, "paths": ["/terminal"]}
                break
            paths = difference_paths(terminal_facts(native), terminal_facts(official))
            terminal_graph_differences = difference_paths(
                native["public_input"], official["public_input"]
            )
            if paths:
                difference = {"index": index, "paths": paths}
            else:
                ending_equal = True
            break
        paths = difference_paths(native["public_input"], official["public_input"])
        menus_equal = [a["key"] for a in native["actions"]] == [
            a["key"] for a in official["actions"]
        ]
        if paths or not menus_equal:
            difference = {"index": index, "paths": paths, "menu_keys_equal": menus_equal}
            break
        matched += 1
    complete = (
        bool(left)
        and bool(right)
        and len(left) == len(right)
        and left[-1]["terminal"] is True
        and right[-1]["terminal"] is True
        and difference is None
        and ending_equal
        and matched == len(left) - 1
    )
    return {
        "matching_policy_inputs": matched,
        "first_difference": difference,
        "native_observations": len(left),
        "official_observations": len(right),
        "explicit_ending_facts_equal": ending_equal,
        "complete_workflow_equal": complete,
        "later_divergent_states_realigned": False,
        "terminal_UI_presentation_graph_equality_required": False,
        "terminal_full_graph_equal": ending_equal and not terminal_graph_differences,
        "terminal_graph_difference_paths_retained": terminal_graph_differences,
        "terminal_persistent_state_and_all_public_reads_equality_required": True,
    }
