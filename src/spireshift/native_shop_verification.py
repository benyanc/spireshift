"""Unchanged raw reconstruction plus exact native shop-task proof chains."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spireshift.native_chest_ending_verification import verify_host as verify_ending
from spireshift.native_flow_verification_v12 import records, same
from spireshift.native_shared_transport import JsonLines


def verify_shop_proofs(
    root: Path, node: str, directory: Path, output: Path, deadline: float
) -> int:
    verifier = JsonLines(
        root,
        [node, str(root / "scripts/engine-shop-task-verify-v1.mjs")],
        output / "shop-task-proof.log",
    )
    receipts: dict[str, dict[str, Any]] = {}
    started: dict[str, dict[str, Any]] = {}
    completed: set[str] = set()
    proved: set[str] = set()
    observed: dict[str, Any] | None = None
    sequence = 0
    try:
        for row in records(directory / "live-public.jsonl.gz"):
            if row["kind"] == "observed":
                observed = row["snapshot"]
            if "receipt" in row and row["kind"] != "shop_lifecycle_proof":
                receipt = row["receipt"]
                if isinstance(receipt, dict) and "request_id" in receipt:
                    receipts[receipt["request_id"]] = receipt
                    if ";native_shop_task_started:" in receipt.get("detail", ""):
                        started[receipt["request_id"]] = receipt
            if row["kind"] != "shop_lifecycle_proof":
                continue
            accepted = row["accepted_receipt"]
            key = accepted["request_id"]
            current = receipts.get(row["receipt_request_id"])
            if (
                key not in started
                or not same(started[key], accepted)
                or key in completed
                or current is None
                or current["delivery"] != "delivered"
                or current["attribution"]["runtime_instance_id"]
                != accepted["attribution"]["runtime_instance_id"]
                or observed is None
                or observed["snapshot_id"] != row["successor_snapshot_id"]
            ):
                raise ValueError(
                    "Shop proof is not bound to its actual accepted task and current delivery"
                )
            sequence += 1
            verifier.send(
                {
                    "request_id": sequence,
                    "receipt": accepted,
                    "proof": row["proof"],
                    "successor": observed,
                }
            )
            response = verifier.receive(deadline)
            if response.get("ok") is not True or not same(response.get("value"), row["progress"]):
                raise ValueError("Native shop task completion/owned child proof rejected")
            proved.add(key)
            if row["progress"]["completed"]:
                completed.add(key)
        if started.keys() != proved or proved != completed:
            raise ValueError("Missing final native shop task completion evidence")
        verifier.close()
        return len(completed)
    finally:
        verifier.stop()


def verify_host(
    root: Path,
    context: dict[str, Any],
    case: dict[str, Any],
    host: str,
    directory: Path,
    output: Path,
    deadline: float,
) -> int:
    count = verify_ending(root, context, case, host, directory, output, deadline)
    if host == "official":
        verify_shop_proofs(root, context["config"]["node"], directory, output, deadline)
    return count
