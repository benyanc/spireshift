"""Normal-start reward-safe qualification episodes and independent raw replay."""

from __future__ import annotations

import json
import subprocess
import time
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from spireshift.engine_worker import _EpisodeLiveness
from spireshift.native_a8_boss2_policy import DeclineProbe, RewardSafeBossTeacher
from spireshift.native_a8_boss_game import chooser as prior_chooser
from spireshift.native_a8_boss_game import worker
from spireshift.native_a8_rescue_game import (
    TRACE,
    Progress,
    bridge,
    decisions,
    public_state,
    receipt,
)
from spireshift.native_a8_rescue_inputs import GAME_LIMITS, ORDERED_PROOF
from spireshift.native_e2e_contract import difference_paths
from spireshift.native_flow_live_v12 import append
from spireshift.native_flow_verification_v12 import records, same
from spireshift.native_win4_game import write
from spireshift.native_win4_plan import AnswerPolicy
from spireshift.native_win_teacher import validate_student_input


def chooser(ctx: dict[str, Any], case: dict[str, Any], arm: str) -> AnswerPolicy:
    if arm not in {"boss", "confirmation", "decline_probe"}:
        return prior_chooser(ctx, case, arm)
    if arm == "decline_probe" and case not in ctx["reward_config"]["control_worlds"]:
        raise ValueError("Scripted Skip is restricted to the declared diagnostic starts")
    core = DeclineProbe if arm == "decline_probe" else RewardSafeBossTeacher
    model = ctx["models"][case["player"], "fitted"]
    return AnswerPolicy(core(model, ctx["score"], case["seed"]))


def liveness_limit(liveness: _EpisodeLiveness, frame: dict[str, Any]) -> bool:
    try:
        liveness.observe(frame["input_digest"])
    except ValueError:
        return True
    return False


def verify(
    ctx: dict[str, Any], case: dict[str, Any], arm: str, target: Path, deadline: float
) -> dict[str, Any]:
    root = ctx["qualification"].root
    out = target / "verification"
    out.mkdir()
    plan, progress = chooser(ctx, case, arm), Progress()
    liveness = _EpisodeLiveness()
    observation = iter(records(target / "worker/public-observations.jsonl.gz"))
    receipts = iter(records(target / "worker/public-receipts.jsonl.gz"))
    domains = iter(records(target / "worker/answer-plan-deliveries.jsonl.gz"))
    converter = bridge(ctx, out / "converter.log")
    semantic = sha256()
    natural = None
    interventions: Counter[str] = Counter()
    try:
        current = next(observation)
        for _, saved_frame, saved in decisions(target / TRACE):
            frame = converter.project(current["snapshot"], current["reads"], None, deadline)
            if difference_paths(frame, saved_frame):
                raise ValueError("Exact public input and menu did not reconstruct")
            natural = progress.observe(frame)
            liveness_hit = natural is None and liveness_limit(liveness, frame)
            if saved is None:
                semantic.update(frame["input_digest"].encode())
                break
            if natural is not None or liveness_hit:
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
            if accepted["delivery_domain"] == "native" and "intervention" in choice:
                interventions[choice["intervention"]] += 1
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
        "native_interventions": dict(interventions),
        "public_liveness_limit_reproduced": liveness_hit,
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
    liveness = _EpisodeLiveness()
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
            run, player, interaction = public_state(frame)
            round_number = interaction["content"].get("context", {}).get("round", 0)
            usage = current["usage"]
            limits = {
                "native_cpu": usage["native_cpu_seconds"] > GAME_LIMITS["episode_cpu_seconds"],
                "wall": time.monotonic() > boundary - 3,
                "choices": plan.decisions >= choices,
                "public_liveness": natural is None and liveness_limit(liveness, frame),
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
        or raw["public_liveness_limit_reproduced"] != ("public_liveness" in cap)
    ):
        raise ValueError("Raw reconstruction disagrees with native gameplay")
    return write(
        target / "report.json",
        {
            "schema_version": "native-a8-act1-boss-normal-start-episode-v2",
            "execution_id": ctx["execution_id"],
            "case": case,
            "arm": arm,
            "model_id": plan.model.model_id,
            "outcome": "capped" if cap else natural,
            "cap": cap,
            "final_hp": player["hp"],
            "final_floor": run["floor"],
            "native_terminal": frame["terminal"],
            "native_ending": ending,
            "usage": usage,
            "shutdown": shutdown,
            "optimizer_updates": 0,
            **raw,
        },
    )
