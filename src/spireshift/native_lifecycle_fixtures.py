"""Exercise native lethal and nonlethal deliveries through the current public adapter."""

from __future__ import annotations

import time
from collections import deque
from pathlib import Path
from typing import Any

from spireshift.native_a8_rescue_game import receipt
from spireshift.native_flow_verification_v12 import records
from spireshift.native_lifecycle_contract import Capture, check_chain, check_frame
from spireshift.native_lifecycle_worker import LifecycleWorker
from spireshift.native_mixed_rest_session import conversion
from spireshift.native_systematic_live_v1 import append

CLASH = "Tried to pop model POWER.STAMPEDE_POWER"
COMBAT = "combat_turn"
STAMP = "STAMPEDE"
STRIKE = "STRIKE_IRONCLAD"
END = "end_turn"
THORNS_DAMAGE = 5
EXPLOSION_DAMAGE = 23
STRIKE_DAMAGE = 6


def choose(frame: dict[str, Any], control: str) -> int:
    candidates = frame["public_input"]["candidates"]
    (index,) = (
        i
        for i, row in enumerate(candidates)
        if (
            row["verb"] == END
            if control == END
            else (row.get("subject") or {}).get("properties", {}).get("definition_id") == control
        )
    )
    return index


def player(frame: dict[str, Any]) -> dict[str, Any]:
    return dict(frame["public_input"]["context"]["persistent"]["player"])


def combat(frame: dict[str, Any]) -> dict[str, Any]:
    owner = frame["public_input"]["context"]["interaction"]
    if owner["kind"] != COMBAT:
        raise ValueError("Require the current playable combat owner")
    return dict(owner["content"]["context"])


def status_amount(entity: dict[str, Any], name: str) -> int:
    values = [row["amount"] for row in entity["statuses"] if row["definition_id"] == name]
    if len(values) > 1 or values and type(values[0]) is not int:
        raise ValueError("Invalid public power count")
    return values[0] if values else 0


def before_thorns(frame: dict[str, Any], hp: int) -> dict[str, Any]:
    context = combat(frame)
    (enemy,) = context["enemies"]
    (intent,) = enemy["intents"]
    actor = context["player"]
    if (
        context["round"] != 2
        or context["is_play_phase"] is not True
        or context["encounter_type"] != "normal"
        or player(frame)["hp"] != hp
        or actor["block"] != 0
        or [card["definition_id"] for card in actor["hand"]] != [STRIKE]
        or status_amount(actor, "STAMPEDE_POWER") != 1
        or enemy["definition_id"] != "SPINY_TOAD"
        or status_amount(enemy, "THORNS_POWER") != THORNS_DAMAGE
        or intent["type"] != "Attack"
        or intent["damage"] != EXPLOSION_DAMAGE
    ):
        raise ValueError("Fixture did not reach the exact Stampede, Strike and Thorns boundary")
    return dict(enemy)


def checked_loss(frame: dict[str, Any], ending: dict[str, Any]) -> dict[str, bool]:
    identity = ending["private_final_identity"]
    facts = {
        "public_loss_and_zero_hp": frame["terminal"] is True
        and frame["ending"]["victory"] is False
        and player(frame)["hp"] == 0,
        "native_loss": ending["native_ending_evidence_agrees"] is True
        and identity["native_game_over"] is True
        and identity["native_player_dead"] is True
        and identity["native_victory_room"] is False
        and identity["native_abandoned"] is False,
        "no_pending_native_actions": all(
            identity[key] is False
            for key in (
                "action_executor_running",
                "pending_host_operation",
                "pending_card_selection",
                "pending_card_reward",
                "pending_reward_set",
                "pending_bundle",
                "pending_abandon_confirmation",
            )
        )
        and identity["pending_potion_discards"] == [],
    }
    if not all(facts.values()):
        raise ValueError(f"Native loss did not settle cleanly: {facts}")
    return facts


def checked_survival(
    frame: dict[str, Any], later: dict[str, Any], before_hp: int, enemy_hp: int
) -> dict[str, Any]:
    next_turn = combat(frame)
    (target,) = next_turn["enemies"]
    later_turn = combat(later)
    (same_target,) = later_turn["enemies"]
    if (
        next_turn["round"] != 3
        or next_turn["is_play_phase"] is not True
        or player(frame)["hp"] != before_hp - THORNS_DAMAGE - EXPLOSION_DAMAGE
        or target["hp"] != enemy_hp - STRIKE_DAMAGE
        or status_amount(target, "THORNS_POWER") != 0
        or later_turn["round"] != next_turn["round"]
        or same_target["hp"] != target["hp"] - STRIKE_DAMAGE
        or player(later)["hp"] != player(frame)["hp"]
    ):
        raise ValueError("Nonlethal Thorns, explosion or the next legal Strike differs")
    return {
        "round": 3,
        "hp": player(frame)["hp"],
        "thorns_damage": THORNS_DAMAGE,
        "enemy_attack_damage": EXPLOSION_DAMAGE,
        "subsequent_strike_damage": STRIKE_DAMAGE,
    }


def last_native_action(directory: Path) -> dict[str, Any]:
    (last,) = deque(
        (
            row
            for row in records(directory / "private-transcript.jsonl.gz")
            if row["request"]["cmd"] == "action"
        ),
        maxlen=1,
    )
    return last


def baseline_diagnostic(directory: Path, error: ValueError) -> dict[str, Any]:
    last = last_native_action(directory)
    if (
        CLASH not in str(error)
        or last["request"]["action"] != END
        or last["response"]["decision"] != "game_over"
        or last["response"]["player"]["hp"] != 0
    ):
        raise ValueError(
            "Unrepaired worker did not reproduce the recorded choice-stack failure"
        ) from error
    return {"status": "expected_cleanup_failure_reproduced", "denied_terminal_seal": True}


def stampede_case(
    ctx: dict[str, Any],
    case: dict[str, Any],
    seed: str,
    directory: Path,
    deadline: float,
) -> dict[str, Any]:
    directory.mkdir()
    worker_dir = directory / "worker"
    baseline = case.get("baseline", False)
    host = {**ctx, "lifecycle_adapter": None} if baseline else ctx
    worker = LifecycleWorker(host, worker_dir, fixture=True)
    bridge = conversion(ctx, directory / "converter.log")
    captures: list[Capture] = []
    choices: list[int] = []
    try:
        worker.request("mount", seed=seed, timeout=20)
        current = worker.request("combat_fixture", hp=case["hp"], timeout=20)
        controls = [STAMP, END, case["trigger"]]
        if case["outcome"] == "playable":
            controls.append(STRIKE)
        for step in (*controls, None):
            frame = bridge.project(current["snapshot"], current["reads"], None, deadline)
            captures.append((current, frame))
            check_frame(captures[-1])
            append(directory / "frames.jsonl.gz", frame)
            if step is None:
                break
            if len(choices) == 2:
                enemy = before_thorns(frame, case["hp"])
            index = choose(frame, step)
            try:
                current = worker.request(
                    "step",
                    snapshot_id=frame["observation"]["snapshot_id"],
                    action_index=frame["actions"][index]["raw_index"],
                    timeout=min(18, max(0.1, deadline - time.monotonic())),
                )
            except ValueError as failure:
                if baseline and len(choices) == 2:
                    return baseline_diagnostic(worker_dir, failure)
                raise
            if current["delivery_domain"] != "native":
                raise ValueError("Diagnostic choice did not reach native execution")
            choice = {"binding_id": frame["binding_id"], "action_index": index}
            ack = receipt(frame, choice, "native", current["snapshot"]["snapshot_id"])
            bridge.commit(choice, ack, deadline)
            choices.append(index)
        if baseline:
            raise ValueError("Unrepaired control unexpectedly passed")
        trace = check_chain(captures, choices, records(worker_dir / "public-receipts.jsonl.gz"))
        if case["outcome"] == "loss":
            effects = checked_loss(captures[-1][1], worker.request("ending", timeout=10))
        else:
            effects = checked_survival(captures[-2][1], captures[-1][1], case["hp"], enemy["hp"])
        shutdown = worker.close()
        if not shutdown["clean_exit"] or shutdown["runtime_errors"]:
            raise ValueError("The diagnostic native worker did not exit cleanly")
        bridge.close()
        return {**trace, "status": "verified", "effects": effects, "clean_exit": True}
    finally:
        bridge.stop()
        worker.stop()
