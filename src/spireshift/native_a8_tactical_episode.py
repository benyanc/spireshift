"""Isolated tactical-teacher episodes and streaming raw receipt verification."""

from __future__ import annotations

import json
import subprocess
import time
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from spireshift.engine_worker import _EpisodeLiveness
from spireshift.native_a8_boss2_game import liveness_limit
from spireshift.native_a8_boss_game import worker
from spireshift.native_a8_boss_policy import boss_choice
from spireshift.native_a8_combat_branch_policy import intent_damage
from spireshift.native_a8_combat_branches import require_exact_menu
from spireshift.native_a8_rescue_game import (
    TRACE,
    Progress,
    bridge,
    decisions,
    public_state,
    receipt,
)
from spireshift.native_a8_rescue_inputs import GAME_LIMITS, ORDERED_PROOF
from spireshift.native_a8_rescue_policy import subject
from spireshift.native_a8_tactical_policy import STEAM, TacticalTeacher, status, tactical_choice
from spireshift.native_e2e_contract import difference_paths
from spireshift.native_flow_live_v12 import append
from spireshift.native_flow_verification_v12 import records, same
from spireshift.native_win4_game import write
from spireshift.native_win4_plan import AnswerPolicy
from spireshift.native_win_teacher import validate_student_input


class Episode:
    def __init__(self, ctx: dict[str, Any], case: dict[str, Any], trace: Path | None) -> None:
        self.case = case
        self.history = decisions(trace) if trace is not None else None
        self.policy = (
            AnswerPolicy(
                TacticalTeacher(ctx["models"][case["player"], "fitted"], ctx["score"], case["seed"])
            )
            if trace is None
            else None
        )
        self.progress = Progress()
        self.liveness = _EpisodeLiveness()
        self.anchor: dict[str, Any] | None = None
        self.steps: list[dict[str, Any]] = []
        self.native = self.local = self.prefix = 0
        self.digest = sha256()
        self.interventions: Counter[str] = Counter()
        self.death_blow: dict[str, Any] | None = None

    def observe(self, frame: dict[str, Any]) -> tuple[str | None, list[str]]:
        validate_student_input(frame["public_input"])
        natural = self.progress.observe(frame)
        run, player, interaction = public_state(frame)
        combat = interaction["content"].get("context", {})
        if self.anchor is not None:
            if run["act"] != 1 or run["floor"] != self.case["floor"]:
                raise ValueError("Saved tactical diagnostic left its exact combat")
            if (
                natural is None
                and interaction["kind"] == "reward_claim"
                and combat.get("reward_kind") == "room_rewards"
                and player["hp"] > 0
            ):
                natural = "fight_win"
            elif natural == "act1_loss":
                natural = "fight_loss"
        caps = {
            "choices": self.native >= GAME_LIMITS["maximum_decisions"],
            "public_liveness": natural is None and liveness_limit(self.liveness, frame),
            "combat_rounds": combat.get("round", 0) > GAME_LIMITS["maximum_rounds_per_fight"],
        }
        return natural, [reason for reason, hit in caps.items() if hit]

    def choose(self, frame: dict[str, Any]) -> dict[str, Any]:
        if self.policy is not None:
            return self.policy.choose(frame)
        assert self.history is not None
        public = frame["public_input"]
        actions = public["candidates"]
        domain = "native"
        if self.anchor is None:
            line, source, delivered = next(self.history, (0, {}, None))
            if delivered is None:
                raise ValueError("Saved trace ended before the tactical anchor")
            require_exact_menu(frame, source, line)
            selected = delivered["choice"]["action_index"]
            if line < self.case["line"]:
                domain = delivered["receipt"]["delivery_domain"]
                return {
                    "action_index": selected,
                    "binding_id": frame["binding_id"],
                    "stage": "saved_prefix",
                    "expected_domain": domain,
                }
            if line != self.case["line"] or frame["input_digest"] != self.case["input_digest"]:
                raise ValueError("Saved tactical anchor differs")
            self.anchor = {
                "line": line,
                "input_digest": frame["input_digest"],
                "saved_action": actions[selected]["label"],
                "saved_index": selected,
            }
            self.history.close()
        _, _, interaction = public_state(frame)
        combat = interaction["content"].get("context", {})
        if (
            interaction["kind"] not in {"combat_turn", "card_selection"}
            or combat.get("encounter_type") != self.case["encounter"]
            or [enemy["definition_id"] for enemy in combat.get("enemies", [])]
            != [self.case["enemy"]]
        ):
            raise ValueError("Saved tactical diagnostic lost its native combat owner")
        indices = list(range(len(actions)))
        headbutt = bool(self.steps and self.steps[-1]["card"] == "HEADBUTT")
        picked = tactical_choice(public, indices, headbutt=headbutt)
        if picked is None and interaction["kind"] == "combat_turn":
            end = next(i for i in indices if actions[i]["verb"] == "end_turn")
            picked = (boss_choice(public, indices, end), "existing_boss_turn")
        if picked is None:
            raise ValueError("Diagnostic encountered an unsupported child owner")
        selected, reason = picked
        if not self.steps and selected == self.anchor["saved_index"]:
            raise ValueError("New planner made the saved losing choice at the anchor")
        return {
            "action_index": selected,
            "binding_id": frame["binding_id"],
            "stage": "combat_branch",
            "expected_domain": domain,
            "tactical_reason": reason,
        }

    def acknowledge(
        self, frame: dict[str, Any], choice: dict[str, Any], accepted: dict[str, Any]
    ) -> None:
        domain = accepted["delivery_domain"]
        if self.policy is not None:
            self.policy.acknowledge(accepted)
        elif domain != choice["expected_domain"] or domain not in {"native", "local_answer_factor"}:
            raise ValueError("Saved tactical delivery differs from its required domain")
        self.native += domain == "native"
        self.local += domain == "local_answer_factor"
        index = choice["action_index"]
        self.progress.delivered(frame, index, domain)
        reason = choice.get("tactical_reason")
        if reason and domain == "native":
            self.interventions[reason] += 1
        self.digest.update(
            json.dumps(
                [frame["input_digest"], index, reason, domain],
                separators=(",", ":"),
            ).encode()
        )
        if choice.get("stage") == "saved_prefix":
            self.prefix += 1
        if self.anchor is None:
            return
        _, hero, interaction = public_state(frame)
        combat = interaction["content"]["context"]
        action = frame["public_input"]["candidates"][index]
        enemy = combat["enemies"][0]
        block = combat["player"].get("block")
        self.steps.append(
            {
                "round": combat["round"],
                "hp": hero["hp"],
                "block": block,
                "enemy_hp": enemy["hp"],
                "steam_eruption": status(enemy, STEAM),
                "action": action["label"],
                "card": subject(action)[1].get("definition_id"),
                "reason": reason,
            }
        )
        blow = intent_damage(enemy, "DeathBlow")
        if blow and action["verb"] == "end_turn":
            self.death_blow = {"damage": blow, "hp_before": hero["hp"], "block_before": block}

    def summary(self, frame: dict[str, Any], outcome: str | None) -> dict[str, Any]:
        if self.policy is not None and self.policy.pending is not None:
            raise ValueError("Unacknowledged tactical choice at the episode boundary")
        if self.history is not None and (self.anchor is None or not self.steps or outcome is None):
            raise ValueError("A saved combat diagnostic requires a complete native fight")
        run, player, _ = public_state(frame)
        semantic = self.digest.copy()
        semantic.update(frame["input_digest"].encode())
        return {
            "initial_public_input_id": self.progress.initial,
            "actual_boss_combat_observed": self.progress.boss_observed,
            "verified_native_deliveries": self.native,
            "local_answer_factors": self.local,
            "semantic_trajectory_sha256": semantic.hexdigest(),
            "tactical_deliveries": dict(self.interventions),
            "natural_outcome": outcome,
            "final_floor": run["floor"],
            "final_hp": player["hp"],
            "diagnostic": {
                "root": self.anchor,
                "exact_prefix_choices": self.prefix,
                "steps": self.steps,
                "death_blow": self.death_blow,
            }
            if self.anchor
            else None,
        }

    def close(self) -> None:
        if self.history is not None:
            self.history.close()


def verify(
    ctx: dict[str, Any],
    case: dict[str, Any],
    trace: Path | None,
    target: Path,
    deadline: float,
    cap: list[str],
) -> dict[str, Any]:
    out = target / "verification"
    out.mkdir()
    plan = Episode(ctx, case, trace)
    observations = iter(records(target / "worker/public-observations.jsonl.gz"))
    receipts = iter(records(target / "worker/public-receipts.jsonl.gz"))
    domains = iter(records(target / "worker/answer-plan-deliveries.jsonl.gz"))
    converter = bridge(ctx, out / "converter.log")
    try:
        current = next(observations)
        for _, recorded, delivered in decisions(target / TRACE):
            frame = converter.project(current["snapshot"], current["reads"], None, deadline)
            if difference_paths(frame, recorded):
                raise ValueError("Tactical public menu failed raw reconstruction")
            natural, public_caps = plan.observe(frame)
            if delivered is None:
                if set(public_caps) != set(cap) - {"wall", "native_cpu"} or (
                    not cap and natural is None
                ):
                    raise ValueError("Tactical endpoint or public cap differs")
                break
            if natural is not None or public_caps:
                raise ValueError("An action crossed the tactical episode boundary")
            choice = plan.choose(frame)
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
                raise ValueError(
                    "Tactical action, domain or successor differs from the raw receipts"
                )
            plan.acknowledge(frame, choice, accepted)
            converter.commit(choice, accepted, deadline)
        if any(next(stream, None) is not None for stream in (observations, receipts, domains)):
            raise ValueError("Unexpected raw tactical evidence after the final observation")
        converter.close()
    except StopIteration as exc:
        raise ValueError("Missing tactical observation or delivery") from exc
    finally:
        converter.stop()
        plan.close()
    if (target / "worker/selection-cursor.jsonl.gz").exists():
        checked = subprocess.run(
            [
                ctx["node"],
                str(ctx["qualification"].root / "scripts" / ORDERED_PROOF),
                str(target / "worker"),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=max(1, min(20, deadline - time.monotonic())),
        )
        proof = json.loads(checked.stdout)
        if proof["native_deliveries"] != plan.native or proof["local_factors"] != plan.local:
            raise ValueError("Ordered tactical selection deliveries differ")
        write(out / "ordered-answer-raw-verification.json", proof)
    return plan.summary(frame, natural)


def play(
    ctx: dict[str, Any],
    case: dict[str, Any],
    target: Path,
    deadline: float,
    *,
    trace: Path | None = None,
) -> dict[str, Any]:
    plan = Episode(ctx, case, trace)
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
            raise ValueError("Tactical worker did not mount its declared normal start")
        write(
            target / "native-start.json",
            {"identity": identity, "process_id": current["native_process_id"]},
        )
        while True:
            frame = converter.project(current["snapshot"], current["reads"], None, boundary)
            natural, cap = plan.observe(frame)
            if current["usage"]["native_cpu_seconds"] > GAME_LIMITS["episode_cpu_seconds"]:
                cap.append("native_cpu")
            if time.monotonic() > boundary - 3:
                cap.append("wall")
            if natural is not None or cap:
                append(target / TRACE, {"kind": "final_observation", "frame": frame})
                if natural in {"act1_loss", "fight_loss"}:
                    ending = native.request("ending", timeout=15)
                    final = ending["private_final_identity"]
                    if (
                        ending["native_ending_evidence_agrees"] is not True
                        or final["seed"] != case["seed"]
                        or final["act"] != 1
                        or final["native_game_over"] is not True
                        or final["native_player_dead"] is not True
                    ):
                        raise ValueError("Tactical native loss evidence differs")
                break
            choice = plan.choose(frame)
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
            plan.acknowledge(frame, choice, accepted)
            converter.commit(choice, accepted, boundary)
            append(target / TRACE, {"kind": "policy_choice", "choice": choice, "receipt": accepted})
        shutdown = native.close()
        converter.close()
    finally:
        plan.close()
        if converter is not None:
            converter.stop()
        native.stop()
    if (
        shutdown["clean_exit"] is not True
        or shutdown["runtime_errors"]
        or shutdown["episodes"] != 1
    ):
        raise ValueError("Tactical native worker failed clean shutdown")
    raw = verify(ctx, case, trace, target, deadline, cap)
    if not same(raw, plan.summary(frame, natural)):
        raise ValueError("Live tactical choices or endpoint differ from raw verification")
    return write(
        target / "report.json",
        {
            "schema_version": "native-a8-tactical-episode-v1",
            "case": case,
            "execution_id": ctx["execution_id"],
            "outcome": "capped" if cap else natural,
            "cap": cap,
            "shutdown": shutdown,
            "native_ending": ending,
            "usage": current["usage"],
            "optimizer_updates": 0,
            **raw,
        },
    )
