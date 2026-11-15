"""Normal-start Act 1 outcomes and raw native delivery verification."""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Generator
from hashlib import sha256
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.native_a8_rescue_inputs import CONVERTER, GAME_LIMITS, ORDERED_PROOF
from spireshift.native_a8_rescue_policy import Act1Teacher
from spireshift.native_e2e_contract import difference_paths
from spireshift.native_flow_live_v12 import append
from spireshift.native_flow_verification_v12 import records, same
from spireshift.native_live_policy import LivePolicy
from spireshift.native_shared_transport import JsonLines
from spireshift.native_win4_game import worker, write
from spireshift.native_win4_plan import AnswerPolicy
from spireshift.native_win_teacher import validate_student_input

TRACE = "shared-public.jsonl.gz"


def chooser(ctx: dict[str, Any], case: dict[str, Any], arm: str) -> AnswerPolicy:
    if arm not in {"original", "fitted", "teacher", "confirmation"}:
        raise ValueError("Unknown normal-start arm")
    model = ctx["models"][case["player"], "original" if arm == "original" else "fitted"]
    core = Act1Teacher if arm in {"teacher", "confirmation"} else LivePolicy
    return AnswerPolicy(core(model, ctx["score"], case["seed"]))


def bridge(ctx: dict[str, Any], log: Path) -> JsonLines:
    root = ctx["qualification"].root
    return JsonLines(root, [ctx["node"], str(root / "scripts" / CONVERTER)], log)


def public_state(frame: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    ctx = frame["public_input"]["context"]
    return ctx["persistent"]["run"], ctx["persistent"]["player"], ctx["interaction"]


class Progress:
    """Recognize the first native Act 2 entry through the actual Act 1 boss rewards."""

    def __init__(self) -> None:
        self.initial: str | None = None
        self.boss_observed = False
        self.exiting_boss_rewards = False

    def observe(self, frame: dict[str, Any]) -> str | None:
        run, player, interaction = public_state(frame)
        owner = interaction["content"].get("context", {})
        if self.initial is None:
            if (
                run["act"] != 1
                or run["floor"] != 1
                or run["ascension"] != 8
                or player["character_definition_id"] != "IRONCLAD"
                or interaction["kind"] != "event_option"
                or owner.get("event_id") != "NEOW"
                or frame["terminal"]
            ):
                raise ValueError("Expected a fresh, playable Ironclad/A8 Neow start")
            self.initial = manifest_identifier(frame["public_input"])
        if run["act"] == 2:
            if (
                not self.boss_observed
                or not self.exiting_boss_rewards
                or frame["terminal"]
                or player["hp"] <= 0
            ):
                raise ValueError("Act 2 requires delivered Act 1 boss rewards and a living player")
            return "act1_clear"
        if run["act"] != 1:
            raise ValueError("Unexpected act in a normal-start Act 1 run")
        self.boss_observed |= (
            interaction["kind"] == "combat_turn" and owner.get("encounter_type") == "boss"
        )
        if frame["terminal"]:
            if frame.get("ending", {}).get("victory") is not False or player["hp"] != 0:
                raise ValueError("Act 1 ending requires an explicit native loss")
            return "act1_loss"
        return None

    def delivered(self, frame: dict[str, Any], index: int, domain: str) -> None:
        _, _, interaction = public_state(frame)
        self.exiting_boss_rewards = (
            domain == "native"
            and interaction["kind"] == "reward_claim"
            and interaction["content"].get("context", {}).get("completed_boss_combat") is True
            and frame["public_input"]["candidates"][index]["label"] == "Continue from rewards"
        )


def receipt(
    frame: dict[str, Any], choice: dict[str, Any], domain: str, successor: str
) -> dict[str, Any]:
    return {
        "binding_id": frame["binding_id"],
        "delivery": "delivered",
        "delivery_domain": domain,
        "bound_action_id": frame["actions"][choice["action_index"]]["bound_action_id"],
        "runtime_instance_id": frame["observation"]["runtime_instance_id"],
        "before_snapshot_id": frame["observation"]["snapshot_id"],
        "successor_snapshot_id": successor,
    }


def decisions(path: Path) -> Generator[tuple[int, dict[str, Any], dict[str, Any] | None]]:
    """Yield each offered frame with its delivered choice, then exactly one final frame."""
    rows = enumerate(records(path), 1)
    for line, row in rows:
        if row["kind"] == "final_observation":
            if next(rows, None) is not None:
                raise ValueError("Unexpected public evidence after the final observation")
            yield line, row["frame"], None
            return
        chosen = next(rows, (0, {}))[1]
        if row["kind"] != "policy_input" or chosen.get("kind") != "policy_choice":
            raise ValueError("Expected one delivered choice for each playable menu")
        yield line, row["frame"], chosen
    raise ValueError("Public journal ended before its final observation")


def verify(
    ctx: dict[str, Any], case: dict[str, Any], arm: str, target: Path, deadline: float
) -> dict[str, Any]:
    root = ctx["qualification"].root
    out = target / "verification"
    out.mkdir()
    plan, progress = chooser(ctx, case, arm), Progress()
    observation = iter(records(target / "worker/public-observations.jsonl.gz"))
    receipts = iter(records(target / "worker/public-receipts.jsonl.gz"))
    domains = iter(records(target / "worker/answer-plan-deliveries.jsonl.gz"))
    converter = bridge(ctx, out / "converter.log")
    semantic = sha256()
    natural = None
    try:
        current = next(observation)
        for _, saved_frame, saved in decisions(target / TRACE):
            frame = converter.project(current["snapshot"], current["reads"], None, deadline)
            if difference_paths(frame, saved_frame):
                raise ValueError("Exact public input and menu did not reconstruct")
            natural = progress.observe(frame)
            if saved is None:
                semantic.update(frame["input_digest"].encode())
                break
            if natural is not None:
                raise ValueError("An Act 1 run delivered an action beyond its declared endpoint")
            choice = plan.choose(frame)
            current, actual, domain = next(observation), next(receipts), next(domains)
            accepted = receipt(
                frame, choice, domain["delivery_domain"], current["snapshot"]["snapshot_id"]
            )
            if (
                not same(choice, saved["choice"])
                or not same(accepted, saved["receipt"])
                or actual["delivery"] != "delivered"
                or actual["snapshot_id"] != accepted["before_snapshot_id"]
                or actual["action"]["bound_action_id"] != accepted["bound_action_id"]
                or actual["successor_snapshot_id"] != accepted["successor_snapshot_id"]
                or domain["before_snapshot_id"] != accepted["before_snapshot_id"]
                or domain["action_id"] != accepted["bound_action_id"]
                or domain["successor_snapshot_id"] != accepted["successor_snapshot_id"]
            ):
                raise ValueError(
                    "Policy choice, successor or native delivery failed reconstruction"
                )
            plan.acknowledge(accepted)
            converter.commit(choice, accepted, deadline)
            progress.delivered(frame, choice["action_index"], accepted["delivery_domain"])
            semantic.update(
                json.dumps(
                    [
                        frame["input_digest"],
                        choice["action_index"],
                        choice.get("reference_action_index"),
                        choice.get("intervention"),
                        accepted["delivery_domain"],
                    ],
                    separators=(",", ":"),
                ).encode()
            )
        if plan.pending is not None or any(
            next(stream, None) is not None for stream in (observation, receipts, domains)
        ):
            raise ValueError("Unexpected or incomplete raw Act 1 evidence")
        converter.close()
    except StopIteration as exc:
        raise ValueError("Missing raw Act 1 observation or delivery") from exc
    finally:
        converter.stop()
    if (target / "worker/selection-cursor.jsonl.gz").exists():
        checked = subprocess.run(
            [ctx["node"], str(root / "scripts" / ORDERED_PROOF), str(target / "worker")],
            capture_output=True,
            text=True,
            check=True,
            timeout=max(1, min(20, deadline - time.monotonic())),
        )
        proof = json.loads(checked.stdout)
        if (
            proof["native_deliveries"] != plan.decisions
            or proof["local_factors"] != plan.local_factors
        ):
            raise ValueError("Ordered answer delivery count differs")
        write(out / "ordered-answer-raw-verification.json", proof)
    return {
        "initial_public_input_id": progress.initial,
        "natural_act1_outcome": natural,
        "actual_boss_combat_observed": progress.boss_observed,
        "verified_native_deliveries": plan.decisions,
        "local_answer_factors": plan.local_factors,
        "semantic_trajectory_sha256": semantic.hexdigest(),
    }


def play(
    ctx: dict[str, Any],
    case: dict[str, Any],
    arm: str,
    target: Path,
    deadline: float,
    *,
    choices: int = GAME_LIMITS["maximum_decisions"],
) -> dict[str, Any]:
    target.mkdir()
    plan, progress = chooser(ctx, case, arm), Progress()
    boundary = min(deadline - 8, time.monotonic() + GAME_LIMITS["episode_wall_seconds"])
    native = worker(ctx, target / "worker")
    converter = None
    ending = None
    try:
        converter = bridge(ctx, target / "converter.log")
        current = native.request("mount", seed=case["seed"], timeout=25)
        identity = current["private_start_identity"]
        if (
            current["episode"] != 1
            or current["reset"] is not False
            or identity["seed"] != case["seed"]
            or identity["started_with_neow"] is not True
        ):
            raise ValueError("Normal-start worker did not mount its declared fresh world")
        write(
            target / "native-start.json",
            {
                "identity": identity,
                "process_id": current["native_process_id"],
                "episode": current["episode"],
            },
        )
        while True:
            frame = converter.project(current["snapshot"], current["reads"], None, boundary)
            validate_student_input(frame["public_input"])
            natural = progress.observe(frame)
            _, player, interaction = public_state(frame)
            round_number = interaction["content"].get("context", {}).get("round", 0)
            usage = current["usage"]
            limits = {
                "native_cpu": usage["native_cpu_seconds"] > GAME_LIMITS["episode_cpu_seconds"],
                "wall": time.monotonic() > boundary - 3,
                "choices": plan.decisions >= choices,
                "combat_rounds": round_number > GAME_LIMITS["maximum_rounds_per_fight"],
            }
            cap = [reason for reason, hit in limits.items() if hit]
            if cap and plan.planning:
                raise ValueError("Unfinished atomic answer at a limit; preserve without replay")
            if cap or natural is not None:
                append(target / TRACE, {"kind": "final_observation", "frame": frame})
                if natural == "act1_loss":
                    ending = native.request("ending", timeout=15)
                    final_identity = ending["private_final_identity"]
                    if (
                        ending["native_ending_evidence_agrees"] is not True
                        or final_identity["act"] != 1
                        or final_identity["seed"] != case["seed"]
                        or final_identity["native_game_over"] is not True
                        or final_identity["native_player_dead"] is not True
                    ):
                        raise ValueError("Act 1 native ending proof disagrees")
                break
            append(target / TRACE, {"kind": "policy_input", "frame": frame})
            choice = plan.choose(frame)
            delivered = native.request(
                "step",
                snapshot_id=current["snapshot"]["snapshot_id"],
                action_index=frame["actions"][choice["action_index"]]["raw_index"],
                timeout=20,
            )
            accepted = receipt(
                frame, choice, delivered["delivery_domain"], delivered["snapshot"]["snapshot_id"]
            )
            plan.acknowledge(accepted)
            converter.commit(choice, accepted, boundary)
            progress.delivered(frame, choice["action_index"], accepted["delivery_domain"])
            append(target / TRACE, {"kind": "policy_choice", "choice": choice, "receipt": accepted})
            current = delivered
        shutdown = native.close()
        converter.close()
    finally:
        if converter is not None:
            converter.stop()
        native.stop()
    if (
        shutdown.get("clean_exit") is not True
        or shutdown.get("runtime_errors")
        or shutdown["episodes"] != 1
    ):
        raise ValueError("Act 1 worker shutdown failed; preserve the attempt")
    raw = verify(ctx, case, arm, target, deadline)
    if (
        raw["verified_native_deliveries"] != plan.decisions
        or raw["local_answer_factors"] != plan.local_factors
        or raw["natural_act1_outcome"] != natural
        or raw["initial_public_input_id"] != progress.initial
    ):
        raise ValueError("Raw reconstruction disagrees with native gameplay")
    return write(
        target / "report.json",
        {
            "schema_version": "native-a8-act1-normal-start-episode-v1",
            "case": case,
            "arm": arm,
            "model_id": plan.model.model_id,
            "outcome": "capped" if cap else natural,
            "cap": cap,
            "final_hp": player["hp"],
            "native_terminal": frame["terminal"],
            "native_ending": ending,
            "usage": usage,
            "shutdown": shutdown,
            "optimizer_updates": 0,
            **raw,
        },
    )
