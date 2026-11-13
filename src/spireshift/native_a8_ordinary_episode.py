"""Run and independently reconstruct episodes for the ordinary-fight extension."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from spireshift.native_a8_boss_game import worker
from spireshift.native_a8_ordinary_policy import OrdinaryLethalTeacher
from spireshift.native_a8_rescue_game import TRACE, bridge, decisions, receipt
from spireshift.native_a8_rescue_inputs import GAME_LIMITS, ORDERED_PROOF
from spireshift.native_a8_tactical_episode import Episode
from spireshift.native_e2e_contract import difference_paths
from spireshift.native_flow_live_v12 import append
from spireshift.native_flow_verification_v12 import records, same
from spireshift.native_win4_game import write
from spireshift.native_win4_plan import AnswerPolicy


def policy(ctx: dict[str, Any], case: dict[str, Any]) -> AnswerPolicy:
    return AnswerPolicy(
        OrdinaryLethalTeacher(ctx["models"][case["player"], "fitted"], ctx["score"], case["seed"])
    )


def plan(ctx: dict[str, Any], case: dict[str, Any]) -> Episode:
    episode = Episode(ctx, case, None)
    episode.policy = policy(ctx, case)
    return episode


def verify(
    ctx: dict[str, Any], case: dict[str, Any], target: Path, cap: list[str], deadline: float
) -> dict[str, Any]:
    replay = plan(ctx, case)
    out = target / "verification"
    out.mkdir()
    source = target / "worker"
    observations = records(source / "public-observations.jsonl.gz")
    receipts = records(source / "public-receipts.jsonl.gz")
    domains = records(source / "answer-plan-deliveries.jsonl.gz")
    converter = bridge(ctx, out / "converter.log")
    try:
        current = next(observations)
        for _, saved, delivered in decisions(target / TRACE):
            frame = converter.project(current["snapshot"], current["reads"], None, deadline)
            if difference_paths(frame, saved):
                raise ValueError("Ordinary-fight public frame differs from the raw observation")
            outcome, public_cap = replay.observe(frame)
            if delivered is None:
                if set(public_cap) != set(cap) - {"wall", "native_cpu"} or (
                    not cap and outcome is None
                ):
                    raise ValueError("Ordinary-fight endpoint differs from its public evidence")
                break
            if outcome is not None or public_cap:
                raise ValueError("A choice crossed the ordinary-fight episode boundary")
            choice = replay.choose(frame)
            current, actual, domain = next(observations), next(receipts), next(domains)
            accepted = receipt(
                frame, choice, domain["delivery_domain"], current["snapshot"]["snapshot_id"]
            )
            if (
                not same(choice, delivered["choice"])
                or not same(accepted, delivered["receipt"])
                or actual["delivery"] != "delivered"
                or actual["snapshot_id"] != accepted["before_snapshot_id"]
                or actual["action"]["bound_action_id"] != accepted["bound_action_id"]
                or actual["successor_snapshot_id"] != accepted["successor_snapshot_id"]
                or domain["before_snapshot_id"] != accepted["before_snapshot_id"]
                or domain["action_id"] != accepted["bound_action_id"]
                or domain["successor_snapshot_id"] != accepted["successor_snapshot_id"]
            ):
                raise ValueError("Ordinary-fight choice or native delivery did not reconstruct")
            replay.acknowledge(frame, choice, accepted)
            converter.commit(choice, accepted, deadline)
        if any(next(stream, None) is not None for stream in (observations, receipts, domains)):
            raise ValueError("Unexpected ordinary-fight evidence after its endpoint")
        converter.close()
    except StopIteration as exc:
        raise ValueError("Missing ordinary-fight observation or native receipt") from exc
    finally:
        converter.stop()
    if (source / "selection-cursor.jsonl.gz").exists():
        proof = subprocess.run(
            [ctx["node"], str(ctx["qualification"].root / "scripts" / ORDERED_PROOF), str(source)],
            capture_output=True,
            text=True,
            check=True,
            timeout=max(1, min(20, deadline - time.monotonic())),
        )
        verified = json.loads(proof.stdout)
        if (
            verified["native_deliveries"] != replay.native
            or verified["local_factors"] != replay.local
        ):
            raise ValueError("Ordinary-fight ordered answer delivery counts differ")
        write(out / "ordered-answer-raw-verification.json", verified)
    return replay.summary(frame, outcome)


def play(
    ctx: dict[str, Any], case: dict[str, Any], target: Path, deadline: float
) -> dict[str, Any]:
    live = plan(ctx, case)
    boundary = min(deadline - 20, time.monotonic() + GAME_LIMITS["episode_wall_seconds"])
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
            raise ValueError("Ordinary-fight worker did not mount the declared fresh start")
        write(
            target / "native-start.json",
            {"identity": identity, "process_id": current["native_process_id"]},
        )
        while True:
            frame = converter.project(current["snapshot"], current["reads"], None, boundary)
            outcome, cap = live.observe(frame)
            if current["usage"]["native_cpu_seconds"] > GAME_LIMITS["episode_cpu_seconds"]:
                cap.append("native_cpu")
            if time.monotonic() > boundary - 3:
                cap.append("wall")
            if outcome is not None or cap:
                append(target / TRACE, {"kind": "final_observation", "frame": frame})
                if outcome == "act1_loss":
                    ending = native.request("ending", timeout=15)
                    final = ending["private_final_identity"]
                    if (
                        ending["native_ending_evidence_agrees"] is not True
                        or final["seed"] != case["seed"]
                        or final["act"] != 1
                        or final["native_game_over"] is not True
                        or final["native_player_dead"] is not True
                    ):
                        raise ValueError("Ordinary-fight native ending proof differs")
                break
            choice = live.choose(frame)
            append(target / TRACE, {"kind": "policy_input", "frame": frame})
            current = native.request(
                "step",
                snapshot_id=frame["observation"]["snapshot_id"],
                action_index=frame["actions"][choice["action_index"]]["raw_index"],
                timeout=min(20, max(1, boundary - time.monotonic())),
            )
            accepted = receipt(
                frame, choice, current["delivery_domain"], current["snapshot"]["snapshot_id"]
            )
            live.acknowledge(frame, choice, accepted)
            converter.commit(choice, accepted, boundary)
            append(target / TRACE, {"kind": "policy_choice", "choice": choice, "receipt": accepted})
        shutdown = native.close()
        converter.close()
    finally:
        if converter is not None:
            converter.stop()
        native.stop()
    if (
        shutdown["clean_exit"] is not True
        or shutdown["runtime_errors"]
        or shutdown["episodes"] != 1
    ):
        raise ValueError("Ordinary-fight worker shutdown failed")
    verified = verify(ctx, case, target, cap, deadline)
    if not same(verified, live.summary(frame, outcome)):
        raise ValueError("Ordinary-fight live result differs from its raw reconstruction")
    return write(
        target / "report.json",
        {
            "schema_version": "native-a8-ordinary-episode-v1",
            "case": case,
            "execution_id": ctx["ordinary_execution_id"],
            "outcome": "capped" if cap else outcome,
            "cap": cap,
            "shutdown": shutdown,
            "native_ending": ending,
            "usage": current["usage"],
            "optimizer_updates": 0,
            **verified,
        },
    )
