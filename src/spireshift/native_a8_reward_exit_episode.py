"""Run both frozen planners with the same native reward-exit verifier."""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from spireshift.native_a8_boss_game import worker
from spireshift.native_a8_ordinary_episode import policy
from spireshift.native_a8_rescue_game import TRACE, bridge, decisions, public_state, receipt
from spireshift.native_a8_rescue_inputs import GAME_LIMITS, ORDERED_PROOF
from spireshift.native_a8_reward_exit import check_delivery, verify_exit
from spireshift.native_a8_tactical_episode import Episode
from spireshift.native_e2e_contract import difference_paths
from spireshift.native_flow_live_v12 import append
from spireshift.native_flow_verification_v12 import records, same
from spireshift.native_win4_game import write


class RewardExitEpisode(Episode):
    def __init__(self, ctx: dict[str, Any], case: dict[str, Any], arm: str, source: Path) -> None:
        super().__init__(ctx, case, None)
        if arm == "ordinary":
            self.policy = policy(ctx, case)
        elif arm != "tactical":
            raise ValueError("Unknown reward-exit comparison arm")
        self.source = source
        self.previous: tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None = None
        self.reward_exit: dict[str, Any] | None = None

    def inspect(self, frame: dict[str, Any], index: int) -> tuple[str | None, list[str]]:
        if index != self.native + self.local:
            raise ValueError("Native observation is outside the current delivery sequence")
        if public_state(frame)[0]["act"] == 2:
            if self.previous is None or not self.progress.boss_observed:
                raise ValueError("Act 2 requires a recorded Act 1 boss fight and reward exit")
            self.reward_exit = verify_exit(self.source, *self.previous, frame, index)
            self.progress.exiting_boss_rewards = True
        return self.observe(frame)

    def acknowledge(
        self, frame: dict[str, Any], choice: dict[str, Any], accepted: dict[str, Any]
    ) -> None:
        super().acknowledge(frame, choice, accepted)
        self.previous = frame, choice, accepted

    def summary(self, frame: dict[str, Any], outcome: str | None) -> dict[str, Any]:
        return {**super().summary(frame, outcome), "act2_reward_exit": self.reward_exit}


def recorded_frames(
    trace: Path, *, interrupted: bool
) -> Iterator[tuple[dict[str, Any] | None, dict[str, Any] | None]]:
    if not interrupted:
        yield from ((frame, delivered) for _, frame, delivered in decisions(trace))
        return
    rows = records(trace)
    for offered in rows:
        delivered = next(rows, {})
        if offered["kind"] != "policy_input" or delivered.get("kind") != "policy_choice":
            raise ValueError("Interrupted trace must end after a complete delivered choice")
        yield offered["frame"], delivered
    yield None, None  # Recover only the separately bound raw successor.


def verify(
    ctx: dict[str, Any],
    case: dict[str, Any],
    arm: str,
    target: Path,
    output: Path,
    cap: list[str],
    deadline: float,
    *,
    interrupted: bool = False,
) -> dict[str, Any]:
    source = target / "worker"
    replay = RewardExitEpisode(ctx, case, arm, source)
    output.mkdir()
    observations = records(source / "public-observations.jsonl.gz")
    receipts = records(source / "public-receipts.jsonl.gz")
    domains = records(source / "answer-plan-deliveries.jsonl.gz")
    converter = bridge(ctx, output / "converter.log")
    try:
        current = next(observations)
        for saved, delivered in recorded_frames(target / TRACE, interrupted=interrupted):
            if current.get("episode") != 1:
                raise ValueError("Saved observation is outside the worker's single mounted episode")
            frame = converter.project(current["snapshot"], current["reads"], None, deadline)
            if saved is not None and difference_paths(frame, saved):
                raise ValueError("Exact public input and menu did not reconstruct")
            outcome, public_cap = replay.inspect(frame, current["index"])
            if delivered is None:
                if set(public_cap) != set(cap) - {"wall", "native_cpu"} or (
                    not cap and outcome is None
                ):
                    raise ValueError("Episode endpoint differs from its public evidence")
                if interrupted and (cap or outcome != "act1_clear" or replay.reward_exit is None):
                    raise ValueError("Interrupted trace lacks a verified final boss reward exit")
                break
            if outcome is not None or public_cap:
                raise ValueError("A choice crossed the Act 1 episode boundary")
            choice = replay.choose(frame)
            index = current["index"]
            current, actual, domain = next(observations), next(receipts), next(domains)
            accepted = receipt(
                frame, choice, domain["delivery_domain"], current["snapshot"]["snapshot_id"]
            )
            check_delivery(actual, domain, accepted, index)
            if not same(choice, delivered["choice"]) or not same(accepted, delivered["receipt"]):
                raise ValueError("Frozen planner choice or native delivery did not reconstruct")
            replay.acknowledge(frame, choice, accepted)
            converter.commit(choice, accepted, deadline)
        else:
            raise ValueError("Missing final observation in the Act 1 replay")
        if any(next(stream, None) is not None for stream in (observations, receipts, domains)):
            raise ValueError("Unexpected raw evidence after the Act 1 endpoint")
        converter.close()
    except StopIteration as exc:
        raise ValueError("Missing raw Act 1 observation or native receipt") from exc
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
            raise ValueError("Ordered answer delivery counts differ from the raw replay")
        write(output / "ordered-answer-raw-verification.json", verified)
    elif replay.local:
        raise ValueError("Missing ordered answer factor evidence")
    if interrupted:
        write(
            output / "recovered-final-observation.json",
            {"frame": frame, "observation_index": current["index"]},
        )
    return replay.summary(frame, outcome)


def verify_loss(ending: dict[str, Any], seed: str) -> None:
    final = ending["private_final_identity"]
    if (
        ending["native_ending_evidence_agrees"] is not True
        or final["seed"] != seed
        or final["act"] != 1
        or final["native_game_over"] is not True
        or final["native_player_dead"] is not True
    ):
        raise ValueError("Act 1 native loss evidence differs")


def play(
    ctx: dict[str, Any], case: dict[str, Any], arm: str, target: Path, deadline: float
) -> dict[str, Any]:
    live = RewardExitEpisode(ctx, case, arm, target / "worker")
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
            raise ValueError("Worker did not mount the declared fresh start")
        write(
            target / "native-start.json",
            {"identity": identity, "process_id": current["native_process_id"]},
        )
        while True:
            frame = converter.project(current["snapshot"], current["reads"], None, boundary)
            outcome, cap = live.inspect(frame, current["index"])
            if current["usage"]["native_cpu_seconds"] > GAME_LIMITS["episode_cpu_seconds"]:
                cap.append("native_cpu")
            if time.monotonic() > boundary - 3:
                cap.append("wall")
            if outcome is not None or cap:
                append(target / TRACE, {"kind": "final_observation", "frame": frame})
                if outcome == "act1_loss":
                    ending = native.request("ending", timeout=15)
                    verify_loss(ending, case["seed"])
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
        raise ValueError("Worker failed clean shutdown after the Act 1 episode")
    replayed = verify(ctx, case, arm, target, target / "verification", cap, deadline)
    if not same(replayed, live.summary(frame, outcome)):
        raise ValueError("Live choice or endpoint differs from its raw reconstruction")
    return write(
        target / "report.json",
        {
            "schema_version": "native-a8-reward-exit-episode-v1",
            "case": case,
            "arm": arm,
            "execution_id": ctx["reward_exit_execution_id"],
            "outcome": "capped" if cap else outcome,
            "cap": cap,
            "shutdown": shutdown,
            "native_ending": ending,
            "usage": current["usage"],
            "optimizer_updates": 0,
            **replayed,
        },
    )
