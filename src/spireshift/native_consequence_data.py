"""Observed combat consequences, never tactical rewards or ordinary PPO targets.

One original hidden world owns every related plan, decision and policy stream.
Repeated streams are averaged for the run-return label, not duplicated as combat
examples. Only current public state and the delivered action become model inputs.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import validate_public_input
from spireshift.native_action_context import encode
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_turn_teacher_policy import POST_COMBAT, boundary, room
from spireshift.native_value_credit import public_value_features
from spireshift.neural_combat import _numpy
from spireshift.training_objective import TrainingScoreSpec

TARGETS = (
    "recorded_continuation_full_run_return",
    "next_public_hp_delta",
    "next_public_enemy_hp_sum_delta",
    "next_turn_hp_delta",
    "encounter_exit_hp_delta",
    "encounter_alive_exit",
    "next_public_potion_count_delta",
)
CONTRACT = "public_combat_action_observed_consequences_not_rewards_v1"


def number(value: Any, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"Missing/nonfinite observed consequence: {label}")
    return float(value)


def player(public: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = public["context"]["persistent"]["player"]
    maximum = number(result["max_hp"], "max_hp")
    if maximum <= 0 or number(result["hp"], "hp") < 0:
        raise ValueError("Observed combat HP needs a positive public maximum")
    if not isinstance(result["potions"], list):
        raise ValueError("Observe the public potion belt; do not guess empty inventory")
    return result


def context(public: dict[str, Any]) -> dict[str, Any]:
    value: dict[str, Any] = public["context"]["interaction"].get("content", {}).get("context", {})
    return value


def alive_exit(public: dict[str, Any], origin: dict[str, Any]) -> bool:
    return room(public) != room(origin) or context(public).get("kind") in POST_COMBAT


def encounter_end(case: dict[str, Any], start: int) -> int | None:
    rows = case["decisions"]
    origin = rows[start]["public_input"]
    end = next(
        (i for i in range(start + 1, len(rows)) if alive_exit(rows[i]["public_input"], origin)),
        None,
    )
    if end is None and (
        case["victory"]
        or case["maximum_floor"] != room(origin)[1]
        or not case["private_final_identity"]["native_game_over"]
        or not case["private_final_identity"]["native_player_dead"]
    ):
        raise ValueError("Missing observed encounter exit or genuine terminal combat death")
    return end


def turn_end(rows: list[dict[str, Any]], index: int, stop: int) -> int | None:
    """Nested and end-turn-triggered menus remain inside the measured turn."""
    origin = rows[index]["public_input"]
    sent = origin["candidates"][rows[index]["choice"]["action_index"]]["verb"] == "end_turn"
    for j in range(index + 1, min(stop + 1, len(rows))):
        public = rows[j]["public_input"]
        if boundary(origin, public, end_turn_sent=sent) is not None:
            return j
        sent |= public["candidates"][rows[j]["choice"]["action_index"]]["verb"] == "end_turn"
    return None


def examples(
    case: dict[str, Any], root: dict[str, Any], plan_id: str, mean_return: float
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Current-fight combat-turn decisions only; prefix replay is never training data.

    Later-turn/encounter targets describe the recorded continuation, not the
    causal effect of this action alone or a new health-maximizing objective.
    An opened selection is the next public step, not necessarily a resolved card.
    """
    if (
        case.get("status") != "terminal"
        or case.get("recovered") is not False
        or case.get("privileged_fixture") is not False
        or case.get("native_ending_evidence_agrees") is not True
        or case.get("privileged_fixed_world_teacher") is not True
        or case.get("student_inputs_public_only") is not True
        or not 0 <= mean_return <= 1
        or not math.isfinite(mean_return)
    ):
        raise ValueError("Consequence examples require sealed, clean, scoped teacher episodes")
    rows, start = case["decisions"], len(root["prefix"])
    if rows[start]["public_input"] != root["public_input"]:
        raise ValueError("Consequence episode starts at another public root")
    end = encounter_end(case, start)
    stop = len(rows) if end is None else end
    exit_hp = 0.0 if end is None else number(player(rows[end]["public_input"])["hp"], "exit hp")
    output, nested = [], 0
    for i in range(start, stop):
        public = rows[i]["public_input"]
        if public["context"]["interaction"]["kind"] != "combat_turn":
            if context(public).get("kind") != "selection":
                raise ValueError("Unknown public owner inside the measured encounter")
            nested += 1
            continue
        validate_public_input(public)
        current, combat = player(public), context(public)
        hp, maximum = number(current["hp"], "hp"), number(current["max_hp"], "max_hp")
        action = rows[i]["choice"]["action_index"]
        if type(action) is not int or not 0 <= action < len(public["candidates"]):
            raise ValueError("Chosen action is outside the current public menu")
        successor = rows[i + 1]["public_input"] if i + 1 < len(rows) else None
        last_hp = 0.0 if successor is None else number(player(successor)["hp"], "successor hp")
        turn = turn_end(rows, i, stop)
        turn_hp = (
            0.0 if turn is None else number(player(rows[turn]["public_input"])["hp"], "turn hp")
        )
        if turn is None and end is not None:
            raise ValueError("An alive encounter exit must complete the observed turn")
        enemy_delta, enemy_mask = 0.0, False
        if (
            successor is not None
            and successor["context"]["interaction"]["kind"] == "combat_turn"
            and room(successor) == room(public)
        ):
            enemies, following = combat["enemies"], context(successor)["enemies"]
            scale = max(1.0, math.fsum(number(e["max_hp"], "enemy max HP") for e in enemies))
            before = math.fsum(number(e["hp"], "enemy HP") for e in enemies)
            after = math.fsum(number(e["hp"], "successor enemy HP") for e in following)
            enemy_delta, enemy_mask = (after - before) / scale, True
        potion_mask = successor is not None
        potion_delta = (
            (len(player(successor)["potions"]) - len(current["potions"]))
            / max(1.0, number(current["max_potion_slots"], "potion slots"))
            if successor is not None
            else 0.0
        )
        targets = (
            mean_return,
            (last_hp - hp) / maximum,
            enemy_delta,
            (turn_hp - hp) / maximum,
            (exit_hp - hp) / maximum,
            float(end is not None),
            potion_delta,
        )
        body = {
            "source_seed_id": root["source_seed_id"],
            "numerical_seed": root["numerical_seed"],
            "plan_id": plan_id,
            "decision_index": i,
            "public_input": public,
            "public_input_id": manifest_identifier(public),
            "action_index": action,
            "targets": list(targets),
            "target_mask": [True, True, enemy_mask, True, True, True, potion_mask],
            "label_endpoints": {
                "next_public": i + 1 if successor is not None else "terminal_death",
                "next_turn": turn if turn is not None else "terminal_death",
                "encounter_exit": end if end is not None else "terminal_death",
            },
        }
        output.append(body)
    if not output:
        raise ValueError("A usable root must supply observed combat decisions")
    return output, {
        "source_seed_id": root["source_seed_id"],
        "plan_id": plan_id,
        "combat_decisions": len(output),
        "nested_decisions_resolved_not_standalone_inputs": nested,
        "prefix_decisions_excluded": start,
        "observed_alive_encounter_exit": end is not None,
        "public_encounter_exit_hp": exit_hp,
    }


def encode_examples(
    values: list[dict[str, Any]], model: CachedContextModel, score: TrainingScoreSpec
) -> dict[str, Any]:
    np = _numpy()
    full, blind, potentials = [], [], []
    for v in values:
        # Provenance, plan identity, endpoints, targets and future observations are
        # never accepted by the public encoder; only this current public graph is.
        rows, _ = encode(v["public_input"], model, score)
        dense = np.zeros((len(rows), model.actor.dimension), dtype=np.float64)
        for j, row in enumerate(rows):
            for k, amount in row.items():
                dense[j, k] = amount
        full.append(dense[v["action_index"]])
        blind.append(dense.mean(axis=0))  # current legal-menu mean, blind to chosen action
        potentials.append(public_value_features(v["public_input"], score)[1])
    result = {
        "inputs": np.asarray(full),
        "action_blind": np.asarray(blind),
        "targets": np.asarray([v["targets"] for v in values], dtype=np.float64),
        "mask": np.asarray([v["target_mask"] for v in values], dtype=np.bool_),
        "owners": np.asarray([v["source_seed_id"] for v in values], dtype=np.int64),
        "plans": np.asarray([v["plan_id"] for v in values]),
        "public_input_ids": np.asarray([v["public_input_id"] for v in values]),
        "actions": np.asarray([v["action_index"] for v in values], dtype=np.int64),
        "indices": np.asarray([v["decision_index"] for v in values], dtype=np.int64),
        "potential": np.asarray(potentials),
    }
    if any(
        not np.isfinite(result[k]).all() for k in ("inputs", "action_blind", "targets", "potential")
    ):
        raise ValueError("Nonfinite encoded consequence data")
    return result


def group_weights(owners: Any, plans: Any, mask: Any) -> Any:
    """Each available source world, then plan, then valid decision has equal mass."""
    np = _numpy()
    if owners.ndim != 1 or plans.shape != owners.shape or mask.shape != (len(owners), len(TARGETS)):
        raise ValueError("Keep source/plan ownership with every consequence target")
    weights = np.zeros(mask.shape, dtype=np.float64)
    for head in range(len(TARGETS)):
        valid = mask[:, head]
        worlds = sorted(set(owners[valid].tolist()))
        for world in worlds:
            own = valid & (owners == world)
            counts = Counter(plans[own].tolist())
            for plan, count in counts.items():
                weights[own & (plans == plan), head] = 1 / len(worlds) / len(counts) / count
    return weights
