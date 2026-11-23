"""Explicitly inspected recovery of one pre-controller invalid-seed launch.

This is not a general retry or interrupted-game recovery. The failed rest case
remains blocked. Its exact inventory, empty game logs and absent action journal
are bound by a separately sealed inspection before this reset may run.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import EXE_RELATIVE, _running_games
from spireshift.engine_qualification import ARCHIVE_RECORD, _inventory, _sha_file
from spireshift.engine_working_app import WorkingAppLease, _lock, preflight_working_app
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_win4_game import write

ATTEMPT = (
    "artifacts/native-mixed-mechanics/paired-all-1794762150887237000/"
    "rest/order-heal-smith-dig-lift/official"
)
OWNED = {
    str(Path(EXE_RELATIVE).parent / name)
    for name in (
        "mods/STS2_MCP.conf",
        "mods/STS2_MCP.dll",
        "mods/STS2_MCP.identity",
        "mods/STS2_MCP.json",
        "override.cfg",
    )
}


def validate_inventory(baseline: list[dict[str, Any]], current: list[dict[str, Any]]) -> None:
    base = {row["path"]: row for row in baseline}
    actual = {row["path"]: row for row in current}
    if len(base) != len(baseline) or len(actual) != len(current):
        raise ValueError("Duplicate inventory entries")
    if actual.keys() - base.keys() != OWNED:
        raise ValueError("Unexpected working-app additions or missing connector files")
    for name, row in base.items():
        expected = {**row, "mode": row["mode"] | 0o111} if name == EXE_RELATIVE else row
        if actual.get(name) != expected:
            raise ValueError("Original game bytes or permissions differ from the frozen baseline")


def inspect(ctx: dict[str, Any], output: Path) -> dict[str, Any]:
    root = ctx["qualification"].root
    policy = ctx["working_app"]
    attempt = root / ATTEMPT
    lease = json.loads((policy.slot / "active.json").read_text())
    if (
        lease != json.loads((attempt / "working-app-lease.json").read_text())
        or lease["attempt"] != str(attempt)
        or lease["game"] != str(policy.slot / "game")
        or lease["config_id"] != policy.config_id
    ):
        raise ValueError("This reset applies only to the inspected invalid-seed launch")
    if any((attempt / name).exists() for name in ("live-control.json", "live-public.jsonl.gz")):
        raise ValueError("A controller or action journal exists; separate inspection is required")
    failure = json.loads((attempt / "failure.json").read_text())
    if (
        failure["error"] != "Checkpoint bridge exited without a complete reply: 1"
        or not all(
            failure["checks"][key]
            for key in (
                "working_app_unchanged",
                "frozen_archive_unchanged",
                "personal_profile_unchanged",
            )
        )
        or "Error: Use an already canonical game seed without O or I"
        not in (attempt / "client-stderr.log").read_text()
        or any((attempt / name).stat().st_size for name in ("stdout.log", "stderr.log"))
    ):
        raise ValueError("The exact pre-controller failure evidence is required")
    record = json.loads((ctx["native"]["archive"] / ARCHIVE_RECORD).read_text())
    current = _inventory(policy.slot / "game")
    validate_inventory(record["inventory"], current)
    if lease["baseline_inventory_id"] != manifest_identifier(record["inventory"]):
        raise ValueError("The original working lease has a different baseline")
    sources = {
        str(p.relative_to(root)): _sha_file(p) for p in sorted(attempt.rglob("*")) if p.is_file()
    }
    sources[str((policy.slot / "active.json").relative_to(root))] = _sha_file(
        policy.slot / "active.json"
    )
    return write(
        output,
        {
            "schema_version": "native-selector-official-reset-inspection-v1",
            "status": "inspected_pre_controller_seed_failure",
            "lease": lease,
            "working_inventory": current,
            "baseline_inventory_id": lease["baseline_inventory_id"],
            "sources": sources,
            "failed_case_retried": False,
            "optimizer_updates": 0,
        },
    )


def reset(ctx: dict[str, Any], reference: dict[str, str], output: Path) -> dict[str, Any]:
    root, policy = ctx["qualification"].root, ctx["working_app"]
    if _running_games():
        raise ValueError("Close STS2 before the inspected official test-copy reset")
    with _lock(policy.slot / ".lock"), _lock(policy.pool / ".pool.lock"):
        if not (policy.slot / "active.json").exists():
            preflight_working_app(policy)
            return {"status": "frozen_baseline_ready", "reset_applied": False}
        plan = identified(verified(root, reference))
        if plan["status"] != "inspected_pre_controller_seed_failure":
            raise ValueError("Require the exact reviewed reset inspection")
        check_sources(root, plan["sources"])
        if plan["lease"]["attempt"] != str(root / ATTEMPT):
            raise ValueError("The interrupted worker belongs to another attempt")
        record = json.loads((ctx["native"]["archive"] / ARCHIVE_RECORD).read_text())
        current = _inventory(policy.slot / "game")
        validate_inventory(record["inventory"], current)
        if current != plan["working_inventory"]:
            raise ValueError("The inspected working copy changed; preserve it")
        output.mkdir(parents=True, exist_ok=False)
        for name in sorted(OWNED):
            destination = output / "preserved-additions" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(policy.slot / "game" / name, destination)
        shutil.copy2(policy.slot / "active.json", output / "preserved-active.json")
        atomic_json(output / "before-inventory.json", current)
        lease = WorkingAppLease(
            policy, policy.slot / "game", record["inventory"], root / ATTEMPT, plan["lease"]
        )
        restored = lease.restore(current)
        report = write(
            output / "report.json",
            {
                "status": "inspected_test_copy_restored",
                "inspection_id": plan["report_id"],
                "restoration": restored,
                "reset_applied": True,
                "failed_case_retried": False,
                "original_failure_evidence_unchanged": all(
                    _sha_file(root / name) == digest
                    for name, digest in plan["sources"].items()
                    if name != str((policy.slot / "active.json").relative_to(root))
                ),
                "preserved": {
                    str(p.relative_to(output)): _sha_file(p)
                    for p in sorted(output.rglob("*"))
                    if p.is_file()
                },
            },
        )
        write(root / ATTEMPT / "inspected-selector-reset-v1.json", report)
        return report
