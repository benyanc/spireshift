"""Short fresh native ordered-answer controls; no curriculum collection or learning."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.native_shared_transport import JsonLines
from spireshift.native_win4_game import policy, worker, write
from spireshift.native_win4_inputs import RECIPE, binding, frozen_checks, load


def fixture(ctx: dict[str, Any], mode: str, out: Path, deadline: float) -> dict[str, Any]:
    out.mkdir()
    root = ctx["qualification"].root
    native = worker(ctx, out / "worker")
    bridge = JsonLines(
        root,
        [ctx["node"], str(root / "scripts/engine-shared-input-v16.mjs")],
        out / "converter.log",
    )
    seed = f"SP1RESH1FTWPLAN{ctx['config']['plan_control_generation']}{mode.upper()}"
    player = 3 if mode.endswith("3") else 2
    chooser = policy(
        ctx,
        {"seed": seed, "scenario": {"player": player}},
        "scaling" if mode.startswith("teacher") else "reference",
    )
    factors: list[dict[str, Any]] = []
    chosen: list[int] = []
    try:
        current = native.request(
            "diagnostic_combat",
            diagnostic_only=True,
            seed=seed,
            deck=["STRIKE_IRONCLAD"] * 12,
            relics=["BURNING_BLOOD", "GAMBLING_CHIP", "BAG_OF_PREPARATION"],
            potions=[],
            timeout=30,
        )
        initial = None
        for number in range(20):
            frame = bridge.project(current["snapshot"], current["reads"], None, deadline)
            surface = frame["public_input"]["context"]["interaction"]["content"].get("surface", {})
            if surface.get("selection_contract") != "factorized_ordered_card_answer_v1":
                if number == 0:
                    raise ValueError("Fresh Gambling Chip did not expose the compact source")
                break
            initial = initial or surface
            prefix = surface["answer_plan"]["selected"]
            if mode in {"ordered", "empty"}:
                if mode == "ordered" and number < 2:
                    desired = [4, 1][number]
                    slot = surface["cards"][desired]["entity_id"]["public_slot"]
                    index = next(
                        i
                        for i, c in enumerate(frame["public_input"]["candidates"])
                        if c["verb"] == "select" and c["subject"]["public_slot"] == slot
                    )
                else:
                    index = next(
                        i
                        for i, c in enumerate(frame["public_input"]["candidates"])
                        if c["verb"] == "confirm"
                    )
                choice = {
                    "action_index": index,
                    "binding_id": frame["binding_id"],
                    "bound_action_id": frame["actions"][index]["bound_action_id"],
                }
            else:
                choice = chooser.choose(frame)
                index = choice["action_index"]
            bind = frame["actions"][index]
            successor = native.request(
                "step",
                snapshot_id=current["snapshot"]["snapshot_id"],
                action_index=bind["raw_index"],
                timeout=20,
            )
            receipt = {
                "binding_id": frame["binding_id"],
                "delivery": "delivered",
                "delivery_domain": successor["delivery_domain"],
                "bound_action_id": bind["bound_action_id"],
                "runtime_instance_id": frame["observation"]["runtime_instance_id"],
                "before_snapshot_id": frame["observation"]["snapshot_id"],
                "successor_snapshot_id": successor["snapshot"]["snapshot_id"],
            }
            if mode not in {"ordered", "empty"}:
                chooser.acknowledge(receipt)
            bridge.commit(choice, receipt, deadline)
            factors.append({"frame": frame, "choice": choice, "receipt": receipt})
            if successor["delivery_domain"] == "native":
                chosen = prefix
            current = successor
        else:
            raise ValueError("Ordered answer did not terminate in n+1 factors")
        shutdown = native.close()
        bridge.close()
    finally:
        bridge.stop()
        native.stop()
    if shutdown.get("clean_exit") is not True or chooser.planning:
        raise ValueError("Native answer did not finish cleanly")
    raw = subprocess.run(
        [ctx["node"], str(root / "scripts/engine-ordered-plan-verify-v1.mjs"), str(out / "worker")],
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    proof = json.loads(raw.stdout)
    if proof["ordered_answer_native_commits"] != 1 or proof["native_deliveries"] != 1:
        raise ValueError("One logical answer must commit to native exactly once")
    if mode == "ordered" and chosen != [4, 1]:
        raise ValueError("Native physical-card order changed")
    if mode == "empty" and chosen:
        raise ValueError("Empty answer changed")
    # Recompute every frozen-policy factor and its joint probability from saved
    # public inputs in a new policy instance. Scripted cases verify exact operands.
    write(out / "answer-proof.json", {"factors": factors, "training_labels_allowed": False})
    factors = json.loads((out / "answer-proof.json").read_text())["factors"]
    replay = policy(
        ctx,
        {"seed": seed, "scenario": {"player": player}},
        "scaling" if mode.startswith("teacher") else "reference",
    )
    if mode not in {"ordered", "empty"}:
        for f in factors:
            if replay.choose(f["frame"]) != f["choice"]:
                raise ValueError("Frozen numerical factor/probability failed saved reconstruction")
            replay.acknowledge(f["receipt"])
        if replay.decisions != 1 or replay.planning:
            raise ValueError("Internal factors counted as game decisions")
    return write(
        out / "report.json",
        {
            "mode": mode,
            "raw": proof,
            "ordered_native_indices": chosen,
            "policy_decisions": 1,
            "shutdown": shutdown,
            "optimizer_updates": 0,
            "training_labels_allowed": False,
        },
    )


def control(root: Path) -> dict[str, Any]:
    began = time.monotonic()
    ctx = load(root, root / RECIPE, require_control=False)
    before = frozen_checks(ctx)
    generation = ctx["config"]["plan_control_generation"]
    out = root / f"artifacts/native-win-curriculum/plan-control-v{generation}"
    out.mkdir(parents=True, exist_ok=False)
    values = [
        fixture(ctx, mode, out / mode, began + 260)
        for mode in ["ordered", "empty", "reference2", "reference3", "teacher2", "teacher3"]
    ]
    if (root / ctx["config"]["workspace"]).exists():
        raise ValueError("Main curriculum unexpectedly started")
    return write(
        out / "report.json",
        {
            "schema_version": "native-curriculum-ordered-plan-control-v1",
            "status": "compact_answer_and_continuation_verified",
            "implementation_id": manifest_identifier(ctx["config"]["implementation"]),
            "launch_binding_id": binding(ctx["config"]),
            "checks": {
                "native_Gambling_Chip_ordered_and_empty_answers": True,
                "both_original_numerical_initializers_and_teacher_modes": True,
                "all_conditional_choices_and_joint_probabilities_reconstruct": True,
                "one_native_commit_per_answer_no_native_prefix_actions": True,
                "clean_shutdown_and_originals_frozen": True,
                "main_unstarted_zero_updates": True,
            },
            "native_answers": len(values),
            "local_factors": sum(v["raw"]["local_factors"] for v in values),
            "checks_before": before,
            "checks_after": frozen_checks(ctx),
            "optimizer_updates": 0,
            "main_started": False,
            "sources": {k: v for k, v in ctx["sources"].items() if k != RECIPE},
            "evidence": {
                str(p.relative_to(root)): _sha_file(p) for p in out.rglob("*") if p.is_file()
            },
        },
    )


if __name__ == "__main__":
    result = control(Path.cwd())
    print(json.dumps({k: v for k, v in result.items() if k not in {"sources", "evidence"}}))
