"""Inspected reset of the exact zero-action v5 asset-loading stall."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games
from spireshift.engine_qualification import ARCHIVE_RECORD, _inventory, _sha_file
from spireshift.engine_working_app import WorkingAppLease, _lock, preflight_working_app
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_verification_v12 import records
from spireshift.native_selector_official_reset import OWNED, validate_inventory
from spireshift.native_win4_game import write

ATTEMPT = "artifacts/native-official-selectors/v5/comparison-v1/pairs/shop-minimum-answer/official"


def zero_action_startup(rows: list[dict[str, Any]], control: dict[str, Any]) -> None:
    if (
        control["policy_decisions"] != 0
        or control["presentation_steps"] != 0
        or control["shutdown_requested"] is not False
        or not rows
        or any(row["kind"] != "observed" for row in rows)
        or any(
            row["snapshot"]["interaction"]["kind"] != "no_action"
            or row["snapshot"]["status"] != "settling"
            for row in rows
        )
    ):
        raise ValueError("This reset requires only startup observations and zero delivered inputs")


def inspect(ctx: dict[str, Any], output: Path) -> dict[str, Any]:
    root, policy = ctx["qualification"].root, ctx["working_app"]
    attempt = root / ATTEMPT
    failure = json.loads((attempt / "failure.json").read_text())
    if (
        failure["checks"]["natural_shutdown"] is not False
        or not all(value for key, value in failure["checks"].items() if key != "natural_shutdown")
        or "timed out after 45 seconds" not in failure["error"]
    ):
        raise ValueError("The failed worker is not the inspected startup-only stall")
    zero_action_startup(
        list(records(attempt / "live-public.jsonl.gz")),
        json.loads((attempt / "live-control.json").read_text()),
    )
    lease = json.loads((policy.slot / "active.json").read_text())
    if (
        lease != json.loads((attempt / "working-app-lease.json").read_text())
        or lease["attempt"] != str(attempt)
        or lease["game"] != str(policy.slot / "game")
        or lease["config_id"] != policy.config_id
    ):
        raise ValueError("This test copy belongs to another interrupted worker")
    archive = json.loads((ctx["native"]["archive"] / ARCHIVE_RECORD).read_text())
    current = _inventory(policy.slot / "game")
    validate_inventory(archive["inventory"], current)
    if manifest_identifier(archive["inventory"]) != lease["baseline_inventory_id"]:
        raise ValueError("Frozen baseline identity changed")
    sources = {
        str(path.relative_to(root)): _sha_file(path)
        for path in sorted(attempt.rglob("*"))
        if path.is_file()
    }
    sources[str((policy.slot / "active.json").relative_to(root))] = _sha_file(
        policy.slot / "active.json"
    )
    return write(
        output,
        {
            "schema_version": "native-selector-startup-reset-inspection-v1",
            "status": "inspected_zero_action_asset_loading_stall",
            "lease": lease,
            "working_inventory": current,
            "sources": sources,
            "original_attempt_stays_failed": True,
            "gameplay_inputs_delivered": 0,
        },
    )


def reset(ctx: dict[str, Any], reference: dict[str, str], output: Path) -> dict[str, Any]:
    root, policy = ctx["qualification"].root, ctx["working_app"]
    if _running_games():
        raise ValueError("Close STS2 before the inspected startup reset")
    with _lock(policy.slot / ".lock"), _lock(policy.pool / ".pool.lock"):
        if not (policy.slot / "active.json").exists():
            preflight_working_app(policy)
            return {"status": "frozen_baseline_ready", "reset_applied": False}
        plan = identified(verified(root, reference))
        if plan["status"] != "inspected_zero_action_asset_loading_stall" or plan["lease"][
            "attempt"
        ] != str(root / ATTEMPT):
            raise ValueError("Require this exact separate startup inspection")
        check_sources(root, plan["sources"])
        current = _inventory(policy.slot / "game")
        archive = json.loads((ctx["native"]["archive"] / ARCHIVE_RECORD).read_text())
        validate_inventory(archive["inventory"], current)
        if current != plan["working_inventory"]:
            raise ValueError("The inspected test copy changed")
        output.mkdir(parents=True, exist_ok=False)
        for name in sorted(OWNED):
            destination = output / "preserved-additions" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(policy.slot / "game" / name, destination)
        shutil.copy2(policy.slot / "active.json", output / "preserved-active.json")
        atomic_json(output / "before-inventory.json", current)
        lease = WorkingAppLease(
            policy, policy.slot / "game", archive["inventory"], root / ATTEMPT, plan["lease"]
        )
        restoration = lease.restore(current)
        return write(
            output / "report.json",
            {
                "status": "inspected_startup_test_copy_restored",
                "inspection_id": plan["report_id"],
                "restoration": restoration,
                "reset_applied": True,
                "original_attempt_stays_failed": True,
                "original_evidence_unchanged": all(
                    _sha_file(root / name) == digest
                    for name, digest in plan["sources"].items()
                    if name != str((policy.slot / "active.json").relative_to(root))
                ),
            },
        )
