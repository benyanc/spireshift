"""Isolated native curriculum starts, actual public deliveries and saved replay."""

from __future__ import annotations

import json
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.full_run_experience import atomic_json
from spireshift.native_e2e_contract import difference_paths
from spireshift.native_flow_live_v12 import append
from spireshift.native_flow_verification_v12 import records, same
from spireshift.native_live_policy import LivePolicy
from spireshift.native_shared_transport import JsonLines
from spireshift.native_win2_worker import SCRIPT, WinWorker
from spireshift.native_win_teacher import TeacherPolicy, validate_student_input


def write(path: Path, value: dict[str, Any], key: str = "report_id") -> dict[str, Any]:
    if path.exists():
        raise FileExistsError("Preserve existing curriculum evidence")
    result = {**value, key: manifest_identifier(value)}
    atomic_json(path, result)
    return result


def worker(context: dict[str, Any], path: Path) -> WinWorker:
    return WinWorker(
        context["qualification"],
        context["native"],
        path,
        Path(context["node"]),
        worker_helpers(context["qualification"].root, SCRIPT),
    )


def transform(
    context: dict[str, Any], save: dict[str, Any], case: dict[str, Any], mode: str
) -> dict[str, Any]:
    root = context["qualification"].root
    completed = subprocess.run(
        [context["node"], str(root / "scripts/engine-win-curriculum-save-v1.mjs")],
        input=json.dumps({"save": save, "scenario": case, "mode": mode}),
        text=True,
        capture_output=True,
        cwd=root,
        timeout=20,
        check=True,
    )
    return dict(json.loads(completed.stdout))


def prepare(
    context: dict[str, Any], case: dict[str, Any], target: Path, deadline: float
) -> dict[str, Any]:
    root = context["qualification"].root
    if case["entry"] == "natural":
        return write(
            target / "start.json",
            {
                "scenario": case,
                "seed": case["seed_pool"][0],
                "kind": "natural_training",
                "status": "ready",
                "save_path": None,
                "evaluation_eligible": False,
                "setup_worlds": [],
            },
        )
    attempts = []
    chosen = None
    for index, seed in enumerate(case["seed_pool"]):
        if time.monotonic() > deadline - 30:
            raise TimeoutError("Preparation deadline; preserve without replay")
        native = worker(context, target / f"prepare-{index:02d}")
        try:
            original = native.request("seed_save", seed=seed, profile=case["profile"], timeout=30)[
                "save"
            ]
            shutdown = native.close()
        finally:
            native.stop()
        if shutdown.get("clean_exit") is not True:
            raise ValueError("Preparation shutdown failed")
        act = original["acts"][case["act"] - 1]["id"]
        accepted = act == "ACT." + case["act_definition"]
        attempts.append(
            {
                "seed": seed,
                "native_act_definition": act,
                "accepted": accepted,
                "selection": "first_native_act_identity_match_without_gameplay_outcomes",
            }
        )
        if accepted:
            chosen = seed
            break
    if chosen is None:
        return write(
            target / "start.json",
            {
                "scenario": case,
                "status": "unavailable",
                "setup_worlds": attempts,
                "reason": "declared_native_act_identity_pool_exhausted",
                "evaluation_eligible": False,
            },
        )
    staged = transform(context, original, case, "stage")
    atomic_json(target / "staged.save", staged)
    native = worker(context, target / "generate-native-act")
    try:
        current = native.request("load", seed=chosen, save_json=json.dumps(staged), timeout=30)
        if current["snapshot"]["persistent"]["content"]["run"]["act"] != case["act"]:
            raise ValueError("Staged native act differs from the declared training slot")
        mapped = native.request("save_current", timeout=20)["save"]
        shutdown = native.close()
    finally:
        native.stop()
    if shutdown.get("clean_exit") is not True:
        raise ValueError("Native map-generation shutdown failed")
    selected = transform(context, mapped, case, "entry")
    path = target / "start.save"
    atomic_json(path, selected)
    return write(
        target / "start.json",
        {
            "scenario": case,
            "seed": chosen,
            "status": "ready",
            "kind": "prepared_training_only",
            "save_path": str(path.relative_to(root)),
            "save_sha256": _sha_file(path),
            "native_boss": selected["acts"][case["act"] - 1]["rooms"]["boss_id"],
            "setup_worlds": attempts,
            "enemy_HP_or_energy_or_RNG_edited": False,
            "natural_progress_claimed": False,
            "prior_current_act_history_is_synthetic_training_setup": True,
            "evaluation_eligible": False,
        },
    )


def policy(
    context: dict[str, Any], start: dict[str, Any], variant: str, model: Any | None = None
) -> LivePolicy:
    m = model if model is not None else context["models"][start["scenario"]["player"]]
    if variant in {"reference", "student"}:
        return LivePolicy(m, context["score"], start["seed"])
    return TeacherPolicy(m, context["score"], start["seed"], variant)


def terminal(frame: dict[str, Any], start: dict[str, Any]) -> tuple[bool, bool]:
    if frame["terminal"]:
        if type(frame.get("ending", {}).get("victory")) is not bool:
            raise ValueError("Missing native ending evidence")
        return True, frame["ending"]["victory"]
    if start["kind"] == "prepared_training_only":
        public = frame["public_input"]
        act = public["context"]["persistent"]["run"]["act"]
        if act > start["scenario"]["act"]:
            return True, True
        # The frozen headless Architect completion has an unresolved native UI
        # dependency. This explicitly training-only goal stops at the engine's
        # post-final-boss reward owner, never fabricating a terminal victory.
        if (
            act == start["scenario"]["act"] == 3
            and public["context"]["interaction"]["kind"] == "reward_claim"
            and public["context"]["interaction"]["content"]
            .get("context", {})
            .get("completed_boss_combat")
            is True
        ):
            return True, True
    return False, False


def check_start(frame: dict[str, Any], start: dict[str, Any]) -> None:
    if start["kind"] == "natural_training":
        return
    public = frame["public_input"]
    run = public["context"]["persistent"]["run"]
    case = start["scenario"]
    if run["act"] != case["act"] or run["act_definition_id"] != case["act_definition"]:
        raise ValueError("Prepared start did not restore its actual native act")
    deck = next(
        r["content"]["cards"] for r in public["context"]["reads"] if r["kind"] == "run_deck"
    )
    if Counter(c["definition_id"] for c in deck) != Counter(case["profile"]["deck"]):
        raise ValueError("Prepared native deck differs from the declared training profile")
    if case["entry"] == "boss":
        c = public["context"]["interaction"]["content"]["context"]
        bosses = {b["definition_id"] for b in run["bosses"]}
        if (
            c.get("encounter_type") != "boss"
            or start["native_boss"] != "ENCOUNTER." + case["boss"]
            or case["boss"] not in bosses
        ):
            raise ValueError("Boss curriculum start has no actual native boss owner")


def episode(
    context: dict[str, Any],
    start: dict[str, Any],
    variant: str,
    target: Path,
    deadline: float,
    *,
    model: Any | None = None,
) -> dict[str, Any]:
    root, limits = context["qualification"].root, context["config"]["plan"]
    chooser = policy(context, start, variant, model)
    native = worker(context, target / "worker")
    converter = JsonLines(
        root,
        [context["node"], str(root / "scripts/engine-shared-input-v16.mjs")],
        target / "converter.log",
    )
    boundary = min(deadline - 8, time.monotonic() + limits["episode_wall_seconds"])
    status, success, final = "complete", False, None
    families: set[str] = set()
    shutdown: dict[str, Any] = {"clean_exit": False}
    native_ending = None
    initial_id = None
    boss_combat_observed = False
    try:
        if start["kind"] == "natural_training":
            current = native.request("mount", seed=start["seed"], timeout=25)
        else:
            path = root / start["save_path"]
            if _sha_file(path) != start["save_sha256"]:
                raise ValueError("Prepared start changed; never replay uncertain data")
            current = native.request(
                "load", seed=start["seed"], save_json=path.read_text(), timeout=25
            )
        first = True
        while True:
            frame = converter.project(current["snapshot"], current["reads"], None, boundary)
            validate_student_input(frame["public_input"])
            combat = frame["public_input"]["context"]["interaction"]["content"].get("context", {})
            boss_combat_observed |= combat.get("encounter_type") == "boss"
            if first:
                check_start(frame, start)
                initial_id = manifest_identifier(frame["public_input"])
                first = False
            ended, success = terminal(frame, start)
            if (
                ended
                and success
                and start["kind"] == "prepared_training_only"
                and not boss_combat_observed
            ):
                raise ValueError("Prepared success requires an actual native boss-combat prefix")
            round_number = (
                frame["public_input"]["context"]["interaction"]["content"]
                .get("context", {})
                .get("round", 0)
            )
            capped = (
                time.monotonic() > boundary - 3
                or chooser.decisions >= limits["maximum_decisions"]
                or current["usage"]["native_cpu_seconds"] > limits["episode_cpu_seconds"]
                or round_number > limits["maximum_rounds_per_fight"]
            )
            if ended or capped:
                status = "capped" if capped else "complete"
                final = frame
                append(
                    target / "shared-public.jsonl.gz", {"kind": "final_observation", "frame": frame}
                )
                if frame["terminal"]:
                    native_ending = native.request("ending", timeout=15)
                    if native_ending["native_ending_evidence_agrees"] is not True:
                        raise ValueError("Native ending proof disagrees")
                break
            families.add(frame["source_family"])
            append(target / "shared-public.jsonl.gz", {"kind": "policy_input", "frame": frame})
            choice = chooser.choose(frame)
            binding = frame["actions"][choice["action_index"]]
            successor = native.request(
                "step",
                snapshot_id=current["snapshot"]["snapshot_id"],
                action_index=binding["raw_index"],
                timeout=20,
            )
            receipt = {
                "binding_id": frame["binding_id"],
                "delivery": "delivered",
                "bound_action_id": binding["bound_action_id"],
                "runtime_instance_id": frame["observation"]["runtime_instance_id"],
                "before_snapshot_id": frame["observation"]["snapshot_id"],
                "successor_snapshot_id": successor["snapshot"]["snapshot_id"],
            }
            chooser.acknowledge(receipt)
            converter.commit(choice, receipt, boundary)
            append(
                target / "shared-public.jsonl.gz",
                {"kind": "policy_choice", "choice": choice, "receipt": receipt},
            )
            current = successor
        shutdown = native.close()
        converter.close()
    finally:
        converter.stop()
        native.stop()
    if final is None or shutdown.get("clean_exit") is not True or shutdown.get("runtime_errors"):
        raise ValueError("Curriculum execution/shutdown incomplete; preserve the attempt")
    result = {
        "schema_version": "native-win-curriculum-episode-v1",
        "status": status,
        "scenario_key": start["scenario"]["key"],
        "start_id": start["report_id"],
        "seed": start["seed"],
        "partition": start["scenario"]["partition"],
        "variant": variant,
        "model_id": chooser.model.model_id,
        "initial_public_input_id": initial_id,
        "kind": start["kind"],
        "policy_decisions": chooser.decisions,
        "curriculum_success": status == "complete" and success,
        "full_run_win": start["kind"] == "natural_training" and status == "complete" and success,
        "native_terminal": final["terminal"],
        "actual_boss_combat_observed": boss_combat_observed,
        "prepared_goal_is_normal_start_terminal_victory": False,
        "native_ending": native_ending,
        "ending_hp": final["public_input"]["context"]["persistent"]["player"]["hp"],
        "families": sorted(families),
        "shutdown": shutdown,
        "optimizer_updates": 0,
        "ordinary_PPO_eligible": False,
        "full_game_evaluation": False,
        "student_inputs_public_only": True,
        "game_apps_created": 0,
        "directory": str(target.relative_to(root)),
    }
    verify = target / "verification"
    verify.mkdir()
    count = verify_episode(context, start, variant, target, verify, deadline, model=model)
    if count != chooser.decisions:
        raise ValueError("Raw reconstruction disagrees with actual curriculum delivery")
    result["actual_deliveries_independently_verified"] = count
    return write(target / "report.json", result)


def verify_episode(
    context: dict[str, Any],
    start: dict[str, Any],
    variant: str,
    directory: Path,
    output: Path,
    deadline: float,
    *,
    model: Any | None = None,
) -> int:
    root = context["qualification"].root
    converter = JsonLines(
        root,
        [context["node"], str(root / "scripts/engine-shared-input-v16.mjs")],
        output / "converter.log",
    )
    observations = iter(records(directory / "worker/public-observations.jsonl.gz"))
    receipts = iter(records(directory / "worker/public-receipts.jsonl.gz"))
    chooser = policy(context, start, variant, model)
    choice = frame = None
    try:
        for row in records(directory / "shared-public.jsonl.gz"):
            if row["kind"] in {"policy_input", "final_observation"}:
                raw = next(observations)
                frame = converter.project(raw["snapshot"], raw["reads"], None, deadline)
                if difference_paths(frame, row["frame"]):
                    raise ValueError(
                        "Curriculum public frame differs from complete native observation"
                    )
                if row["kind"] == "policy_input":
                    choice = chooser.choose(frame)
            elif row["kind"] == "policy_choice":
                if choice is None or frame is None or not same(choice, row["choice"]):
                    raise ValueError("Actual curriculum choice/probability did not reconstruct")
                actual = next(receipts)
                if (
                    actual["delivery"] != "delivered"
                    or actual["snapshot_id"] != frame["observation"]["snapshot_id"]
                    or actual["action"]["bound_action_id"] != choice["bound_action_id"]
                    or actual["successor_snapshot_id"] != row["receipt"]["successor_snapshot_id"]
                ):
                    raise ValueError("Curriculum label has no exact actual native receipt")
                chooser.acknowledge(row["receipt"])
                converter.commit(choice, row["receipt"], deadline)
                choice = None
        if (
            chooser.pending is not None
            or choice is not None
            or frame is None
            or next(observations, None) is not None
            or next(receipts, None) is not None
        ):
            raise ValueError("Incomplete or extra curriculum evidence")
        converter.close()
        return chooser.decisions
    finally:
        converter.stop()
