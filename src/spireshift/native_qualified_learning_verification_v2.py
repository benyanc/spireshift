"""Saved normal-start reconstruction using the same qualified executable card domain."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from spireshift.native_a8_head_policy import policy
from spireshift.native_e2e_contract import difference_paths
from spireshift.native_flow_verification_v12 import records, same
from spireshift.native_systematic_selectors_v2 import SelectorBridge
from spireshift.native_win4_game import write

SCRIPT = "scripts/engine-card-answer-verify-v2.mjs"


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
    if (
        variant != "own_policy"
        or start["kind"] != "natural_training"
        or start["save_path"] is not None
        or start.get("diagnostic_only")
        or model is None
    ):
        raise ValueError("Qualified learning verification requires a model-owned normal start")
    root = context["qualification"].root
    converter = SelectorBridge(
        root,
        [context["node"], str(root / "scripts/engine-shared-input-v16.mjs")],
        output / "converter.log",
    )
    observations = iter(records(directory / "worker/public-observations.jsonl.gz"))
    receipts = iter(records(directory / "worker/public-receipts.jsonl.gz"))
    domains = iter(records(directory / "worker/answer-plan-deliveries.jsonl.gz"))
    chooser = policy(context, start, variant, model)
    choice = frame = None
    try:
        for row in records(directory / "shared-public.jsonl.gz"):
            if row["kind"] in {"policy_input", "final_observation"}:
                raw = next(observations)
                frame = converter.project(raw["snapshot"], raw["reads"], None, deadline)
                if difference_paths(frame, row["frame"]):
                    raise ValueError("Public frame differs from its complete native observation")
                if row["kind"] == "policy_input":
                    choice = chooser.choose(frame)
            elif row["kind"] == "policy_choice":
                if choice is None or frame is None or not same(choice, row["choice"]):
                    raise ValueError("Actual choice and its probability did not reconstruct")
                actual = next(receipts)
                if (
                    actual["delivery"] != "delivered"
                    or actual["snapshot_id"] != frame["observation"]["snapshot_id"]
                    or actual["action"]["bound_action_id"] != choice["bound_action_id"]
                    or actual["successor_snapshot_id"] != row["receipt"]["successor_snapshot_id"]
                ):
                    raise ValueError("Choice has no exact actual native receipt")
                domain = next(domains)
                if (
                    domain["before_snapshot_id"] != actual["snapshot_id"]
                    or domain["action_id"] != actual["action"]["bound_action_id"]
                    or domain["successor_snapshot_id"] != actual["successor_snapshot_id"]
                    or domain["delivery_domain"] != row["receipt"].get("delivery_domain")
                ):
                    raise ValueError("Local factors cannot masquerade as native deliveries")
                chooser.acknowledge(row["receipt"])
                converter.commit(choice, row["receipt"], deadline)
                choice = None
            else:
                raise ValueError("Unexpected saved experience record")
        if (
            chooser.pending is not None
            or choice is not None
            or frame is None
            or next(observations, None) is not None
            or next(receipts, None) is not None
            or next(domains, None) is not None
        ):
            raise ValueError("Incomplete or extra saved experience")
        converter.close()
        checked = subprocess.run(
            [context["node"], str(root / SCRIPT), str(directory / "worker")],
            capture_output=True,
            text=True,
            check=False,
            timeout=max(1, min(20, deadline - time.monotonic())),
        )
        if checked.returncode:
            raise ValueError(f"Saved card-answer verification failed: {checked.stderr[-2000:]}")
        proof = json.loads(checked.stdout)
        if (
            proof["contract"] != "qualified_executable_card_answer_verification_v2"
            or proof["native_deliveries"] != chooser.decisions
            or proof["local_factors"] != chooser.local_factors
        ):
            raise ValueError("Atomic answers and internal factors were miscounted")
        write(output / "ordered-answer-raw-verification.json", proof)
        return chooser.decisions
    finally:
        converter.stop()
