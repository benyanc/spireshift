"""New declared natural collections and privileged fixed-root teacher branches.

The ordinary CLI56, worker24, converter16, layout12 and Connector31 stay frozen.
Only exact visible observations reach the policy. Branch outcomes are diagnostic
teacher labels, never hidden policy features or ordinary PPO experience.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_chest_worker import ChestWorker
from spireshift.full_run_experience import atomic_json
from spireshift.native_curriculum_policy import ForcedPolicy, action_logs
from spireshift.native_e2e_contract import difference_paths
from spireshift.native_flow_live_v12 import append
from spireshift.native_flow_verification_v12 import records, same
from spireshift.native_live_policy import LivePolicy
from spireshift.native_natural_data import ending, resources
from spireshift.native_render_endings import converter_cpu_seconds, native_run, process_cpu_seconds
from spireshift.native_shared_transport import JsonLines
from spireshift.native_shop_verification import verify_host
from spireshift.native_turn_teacher_policy import round_number


def adapter_context(context: dict[str, Any]) -> dict[str, Any]:
    p = context["config"]["plan"]
    return {
        **context,
        "config": {
            **context["parent_config"],
            **{
                k: p[k]
                for k in ["maximum_decisions", "maximum_pair_wall_seconds", "whole_run_cpu_seconds"]
            },
        },
    }


def collect_game(
    context: dict[str, Any], case: dict[str, Any], target: Path, deadline: float
) -> dict[str, Any]:
    root = context["qualification"].root
    adapted = adapter_context(context)
    value = native_run(
        adapted,
        case,
        target / "native",
        LivePolicy(context["models"][case["player"]], context["score"], case["seed"]),
        min(deadline, time.monotonic() + 150),
    )
    if value["shutdown"]["clean_exit"] is not True:
        raise ValueError("Source-game shutdown unverified; preserve and stop")
    count = 0
    if value["status"] == "native_natural_ending_pass":
        checks = target / "raw-verification"
        checks.mkdir()
        count = verify_host(root, adapted, case, "native", target / "native", checks, deadline)
        if count != value["policy_decisions"]:
            raise ValueError("Source game did not independently reconstruct every actual delivery")
    return {
        "kind": "natural_source",
        "case": case,
        "status": value["status"],
        "deliveries": count,
        "native": value,
        "directory": str((target / "native").relative_to(root)),
    }


def _ack(
    frame: dict[str, Any], choice: dict[str, Any], successor: dict[str, Any]
) -> dict[str, Any]:
    return {
        "binding_id": frame["binding_id"],
        "delivery": "delivered",
        "bound_action_id": choice["bound_action_id"],
        "runtime_instance_id": frame["observation"]["runtime_instance_id"],
        "before_snapshot_id": frame["observation"]["snapshot_id"],
        "successor_snapshot_id": successor["snapshot"]["snapshot_id"],
    }


def verify_branch(
    context: dict[str, Any], target: Path, teacher: LivePolicy, deadline: float
) -> int:
    root = context["qualification"].root
    converter = JsonLines(
        root,
        [context["parent_config"]["node"], str(root / "scripts/engine-shared-input-v16.mjs")],
        target / "raw-verification.log",
    )
    observations = iter(records(target / "worker/public-observations.jsonl.gz"))
    receipts = iter(records(target / "worker/public-receipts.jsonl.gz"))
    choice = frame = None
    try:
        for row in records(target / "shared-public.jsonl.gz"):
            if row["kind"] in {"policy_input", "final_observation"}:
                raw = next(observations)
                frame = converter.project(raw["snapshot"], raw["reads"], None, deadline)
                if difference_paths(frame, row["frame"]):
                    raise ValueError("Teacher frame differs from its complete raw observation")
                if row["kind"] == "policy_input" and not frame["terminal"]:
                    choice = teacher.choose(frame)
            elif row["kind"] == "policy_choice":
                actual = next(receipts)
                if frame is None or choice is None or not same(choice, row["choice"]):
                    raise ValueError("Teacher choice or explicit legal plan changed")
                if (
                    actual["delivery"] != "delivered"
                    or actual["snapshot_id"] != frame["observation"]["snapshot_id"]
                    or actual["action"]["bound_action_id"] != choice["bound_action_id"]
                    or actual["successor_snapshot_id"] != row["receipt"]["successor_snapshot_id"]
                ):
                    raise ValueError("Teacher label is not bound to its actual native receipt")
                teacher.acknowledge(row["receipt"])
                converter.commit(choice, row["receipt"], deadline)
                choice = None
        if (
            choice is not None
            or next(observations, None) is not None
            or next(receipts, None) is not None
        ):
            raise ValueError("Extra raw observation, receipt or unacknowledged teacher action")
        converter.close()
        return teacher.decisions
    finally:
        converter.stop()


def branch(
    context: dict[str, Any],
    source: dict[str, Any],
    target: Path,
    deadline: float,
    *,
    proposal: list[dict[str, Any]],
    candidate: int,
    model: Any | None = None,
    original: Any | None = None,
) -> dict[str, Any]:
    root = context["qualification"].root
    p = context["config"]["plan"]
    chosen_model = model if model is not None else context["models"][source["player"]]
    forced = [*source["prefix"], *proposal]
    atomic_json(
        target / "declared-branch.json",
        {
            "root_id": source["root_id"],
            "candidate": candidate,
            "forced": forced,
            "privileged_fixed_world_diagnostic": True,
        },
    )
    policy = ForcedPolicy(chosen_model, context["score"], source["world"], forced, original)
    started = time.monotonic()
    boundary = min(deadline - 15, started + p["branch_wall_seconds"])
    worker = ChestWorker(
        context["qualification"],
        context["native"],
        target / "worker",
        Path(context["parent_config"]["node"]),
        context["native_helpers"],
    )
    converter = JsonLines(
        root,
        [context["parent_config"]["node"], str(root / "scripts/engine-shared-input-v16.mjs")],
        target / "converter.log",
    )
    cpu_started = process_cpu_seconds()
    steps: list[dict[str, Any]] = []
    rounds: set[int] = set()
    status, outcome, reached, final_frame = "complete", None, False, None
    shutdown: dict[str, Any] = {"clean_exit": False}
    try:
        current = worker.request(
            "mount", seed=source["world"], timeout=min(25, boundary - time.monotonic())
        )
        while True:
            frame = converter.project(current["snapshot"], current["reads"], None, boundary)
            public = frame["public_input"]
            if policy.decisions == len(source["prefix"]):
                if not same(public, source["public_input"]):
                    raise ValueError("New branch did not reach its exact declared public root")
                reached = True
            if reached:
                outcome = ending(source["public_input"], public)
                if frame["source_family"] == "combat_turn":
                    rounds.add(round_number(public))
            cpu = (
                worker.cpu_seconds()
                + converter_cpu_seconds(converter)
                + process_cpu_seconds()
                - cpu_started
            )
            capped = (
                time.monotonic() >= boundary - 3
                or cpu > 128
                or policy.decisions >= 384
                or len(steps) >= p["branch_maximum_decisions"]
                or len(rounds) > p["branch_maximum_rounds"]
            )
            if outcome is not None or capped:
                status = "capped" if capped else "complete"
                final_frame = frame
                append(
                    target / "shared-public.jsonl.gz", {"kind": "final_observation", "frame": frame}
                )
                if frame["terminal"]:
                    worker.request("ending", timeout=min(15, boundary - time.monotonic()))
                break
            choice = policy.choose(frame)
            if reached and choice["combat_owned"] is not True:
                raise ValueError("A teacher branch lost its declared combat/nested input owner")
            append(target / "shared-public.jsonl.gz", {"kind": "policy_input", "frame": frame})
            if reached:
                steps.append(
                    {
                        "public_input": public,
                        "public_input_id": manifest_identifier(public),
                        "action_index": choice["action_index"],
                        "log_probabilities": action_logs(chosen_model, public, context["score"]),
                    }
                )
            binding = frame["actions"][choice["action_index"]]
            successor = worker.request(
                "step",
                snapshot_id=current["snapshot"]["snapshot_id"],
                action_index=binding["raw_index"],
                timeout=min(20, boundary - time.monotonic()),
            )
            receipt = _ack(frame, choice, successor)
            policy.acknowledge(receipt)
            converter.commit(choice, receipt, boundary)
            append(
                target / "shared-public.jsonl.gz",
                {"kind": "policy_choice", "choice": choice, "receipt": receipt},
            )
            current = successor
        shutdown = worker.close()
        converter.close()
    finally:
        converter.stop()
        worker.stop()
    if not reached or shutdown["clean_exit"] is not True or final_frame is None:
        raise ValueError("Teacher root or native shutdown unverified")
    if status == "complete" and policy.decisions < len(forced):
        raise ValueError("A declared confirmation/edited prefix was truncated")
    delivered = verify_branch(
        context,
        target,
        ForcedPolicy(chosen_model, context["score"], source["world"], forced, original),
        deadline,
    )
    if delivered != policy.decisions:
        raise ValueError("Teacher delivery count changed")
    body = {
        "schema_version": "native-varied-teacher-branch-v1",
        "root_id": source["root_id"],
        "world": source["world"],
        "partition": source["partition"],
        "candidate": candidate,
        "status": status,
        "outcome": outcome if status == "complete" else None,
        "resources": resources(final_frame["public_input"]),
        "steps": steps,
        "actual_deliveries_verified": delivered,
        "clean_shutdown": True,
        "wall_seconds": time.monotonic() - started,
        "privileged_fixed_world_teacher": True,
        "ordinary_PPO_eligible": False,
        "student_inputs_public_only": True,
        "game_apps_created": 0,
    }
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(target / "branch.json", result)
    return result
