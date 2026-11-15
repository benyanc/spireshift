"""Finite native transition trees; answers and history never enter student inputs."""

from __future__ import annotations

from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import validate_public_input

FAMILIES = ("vulnerable_then_attack", "dexterity_then_block")
ARMS = ("learned", "exact")
CONTRACT = "privileged_native_delayed_terminal_goal_v1"
HORIZON = 3


def key(prefix: list[int]) -> str:
    return "root" if not prefix else "-".join(map(str, prefix))


def ending(
    family: str, root: dict[str, Any], current: dict[str, Any], depth: int
) -> tuple[bool, int, str]:
    """Observe actual native boundaries; intermediate steps earn no reward."""
    hp = current["context"]["persistent"]["player"]["hp"]
    interaction = current["context"]["interaction"]
    if hp <= 0:
        return True, 0, "native_death"
    if family == FAMILIES[0] and interaction["kind"] == "reward_claim":
        return True, 1, "native_encounter_won"
    if family not in FAMILIES or interaction["kind"] != "combat_turn":
        raise ValueError("Unexpected owner in the declared finite delayed task")
    before = root["context"]["interaction"]["content"]["context"]["round"]
    after = interaction["content"]["context"]["round"]
    if after > before:
        return True, int(family == FAMILIES[1]), "native_enemy_turn_finished"
    if depth >= HORIZON:
        return True, 0, "declared_action_horizon"
    return False, 0, "continue"


def qualify(tree: dict[str, Any]) -> dict[str, Any]:
    if tree.get("contract") != CONTRACT or tree.get("family") not in FAMILIES:
        raise ValueError("Require the explicit diagnostic contract and task")
    nodes, family = tree["nodes"], tree["family"]
    if "root" not in nodes or len(nodes) > 40:
        raise ValueError("Missing root or unbounded native tree")
    successful: list[list[int]] = []
    seen: set[str] = set()

    def visit(name: str, prefix: list[int]) -> None:
        if name != key(prefix) or name in seen:
            raise ValueError("Tree paths cycle or alias another native history")
        seen.add(name)
        node = nodes[name]
        validate_public_input(node["public_input"])
        public = node["public_input"]
        if manifest_identifier(public) != node["public_input_id"] or node["prefix"] != prefix:
            raise ValueError("Changed public input or prefix")
        expected = ending(family, nodes["root"]["public_input"], public, len(prefix))
        if (node["terminal"], node["outcome"], node["boundary"]) != expected:
            raise ValueError("Diagnostic goal must reproduce from native public effects")
        if node["terminal"]:
            if node["children"]:
                raise ValueError("Terminal native diagnostic node has extra choices")
            if node["outcome"]:
                successful.append(prefix)
        else:
            if public["context"]["persistent"]["run"]["ascension"] != 8:
                raise ValueError("Delayed fixture must use A8")
            children = node["children"]
            if not 1 <= len(children) <= 4 or len(children) != len(public["candidates"]):
                raise ValueError("Every current native legal action needs an observed successor")
            for action, child in enumerate(children):
                visit(child, [*prefix, action])

    visit("root", [])
    first = {p[0] for p in successful}
    minimum = 2 if family == FAMILIES[0] else 3
    if (
        seen != set(nodes)
        or not successful
        or min(map(len, successful)) < minimum
        or len(first) != 1
        or any(nodes[c]["terminal"] for c in nodes["root"]["children"] if nodes[c]["outcome"])
    ):
        raise ValueError("Need a genuinely delayed, uniquely useful first move and complete tree")
    return {
        "nodes": len(nodes),
        "native_edges": len(nodes) - 1,
        "minimum_success_actions": min(map(len, successful)),
        "successful_paths": successful,
        "successful_first_action": next(iter(first)),
        "every_legal_action_observed": True,
        "immediate_successes": 0,
    }
