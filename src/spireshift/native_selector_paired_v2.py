"""Preserve the first failed pair and qualify shared physical inventory identity."""

from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_selector_paired_session, native_selector_paired_worker
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_verification_v12 import records
from spireshift.native_selector_paired_inputs import RECIPE as PARENT_RECIPE
from spireshift.native_selector_paired_inputs import context
from spireshift.native_selector_paired_inputs import load as parent_plan
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

RECIPE = "configs/native-compatibility/sts2-v0.111.0-a8-official-selectors-v2.json"
SCHEMA = "native-a8-official-selector-comparison-v2"
MODULE = "spireshift.native_selector_paired_v2"
SCRIPT = "engine-selector-paired-worker-v2.mjs"


class PairedWorker(native_selector_paired_worker.PairedWorker):
    def __init__(self, ctx: dict[str, Any], target: Path) -> None:
        with patch.object(native_selector_paired_worker, "SCRIPT", SCRIPT):
            super().__init__(ctx, target)


def implementation(root: Path) -> dict[str, str]:
    previous = json.loads((root / PARENT_RECIPE).read_text())["implementation"]
    paths = {
        *previous,
        PARENT_RECIPE,
        "src/spireshift/native_selector_paired_v2.py",
        "scripts/compare-official-selectors-v2.sh",
    }
    for script in (SCRIPT, "engine-owned-inventory-audit-v1.mjs"):
        paths.update(f"scripts/{name}" for name in worker_helpers(root, script))
    return {name: _sha_file(root / name) for name in sorted(paths)}


def parent_audit(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    original = parent_plan(root)
    result = identified(verified(root, cfg["parent_result"]))
    resources = identified(verified(root, cfg["parent_resources"]))
    if (
        result["status"] != "blocked_preserving_evidence"
        or result["mode"] != "full"
        or result["config_id"] != manifest_identifier(original)
        or result["verified_pairs"] != 0
        or result["planned_pairs"] != 6
        or len(result["pairs"]) != 1
        or not all(result["frozen_checks"].values())
        or resources["status"] != "failed"
        or resources["exit_code"] != 2
        or resources["cap"] is not None
    ):
        raise ValueError("Require the preserved stopped official selector comparison")
    pair = result["pairs"][0]
    check_sources(root, pair["sources"])
    if (
        pair["case"]["key"] != "shop-ordered"
        or pair["difference"]["decision"] != 2
        or pair["difference"]["first_difference"]["all_difference_paths"]
        != ["/context/reads/1/content/relics/2/relic/entity_id/public_slot"]
        or not pair["difference"]["first_difference"]["menu_keys_equal"]
        or pair["official"]["probe"]["policy_decisions"] != 2
        or not all(pair["official"]["checks"].values())
        or pair["official"]["working_app"]["restored"] is not True
    ):
        raise ValueError("The saved stop differs from the exact catalog identity regression")
    area = root / original["workspace"]
    native = identified(area / "native/report.json")
    check_sources(root, native["sources"])
    if native["report_id"] != result["native_report_id"] or len(native["cases"]) != 6:
        raise ValueError("Missing the six sealed native controls")
    official = area / "pairs/shop-ordered/official"
    frames = [
        row for row in records(official / "live-public.jsonl.gz") if row["kind"] == "policy_input"
    ]
    receipts = [
        row for row in records(official / "live-public.jsonl.gz") if row["kind"] == "receipt"
    ]
    # Exclude the startup Continue receipt. The two owned policy choices remain
    # verified diagnostic deliveries, without imputing the native suffix.
    delivered = {row["before_snapshot_id"]: row for row in receipts}
    if len(frames) != 3:
        raise ValueError("Missing the last unsubmitted official menu")
    for before, after in zip(frames[:2], frames[1:3], strict=True):
        raw = delivered[before["snapshot"]["snapshot_id"]]
        sdk, action = raw["receipt"], raw["action"]
        if (
            sdk["delivery"] != "delivered"
            or sdk["action"]["bound_action_id"] != action["bound_action_id"]
            or sdk["action"]["verb"] != action["verb"]
            or sdk["attribution"]["runtime_instance_id"]
            != before["snapshot"]["session"]["runtime_instance_id"]
            or before["snapshot"]["sequence"] >= after["snapshot"]["sequence"]
            or action not in before["snapshot"]["bound_actions"]["actions"]
        ):
            raise ValueError("The saved official prefix lacks an exact current SDK receipt")
    return {
        "parent_report_id": result["report_id"],
        "historical_pairs": 6,
        "historical_verified_pairs": 0,
        "historical_blocked_pairs": 1,
        "historical_unattempted_pairs": 5,
        "official_deliveries_verified": 2,
        "official_offered_frames_verified": 3,
        "clean_shutdown_and_reset": True,
    }


def load(root: Path) -> dict[str, Any]:
    cfg: dict[str, Any] = json.loads((root / RECIPE).read_text())
    original = parent_plan(root)
    cases = [
        {**case, "seed": f"SP1RESH1FTA8P2SLC{i:03}"} for i, case in enumerate(original["cases"], 1)
    ]
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["cases"] != cases
        or cfg["implementation"] != implementation(root)
        or cfg["limits"] != original["limits"]
        or cfg["training_allowed"] is not False
    ):
        raise ValueError("The versioned inventory-identity comparison changed")
    parent_audit(root, cfg)
    return cfg


def saved_check(root: Path, cfg: dict[str, Any], node: str, output: Path) -> dict[str, Any]:
    facts = parent_audit(root, cfg)
    original = parent_plan(root)
    source = root / original["workspace"]
    result = subprocess.run(
        [
            node,
            str(root / "scripts/engine-owned-inventory-audit-v1.mjs"),
            str(source / "native/shop-ordered"),
            str(source / "pairs/shop-ordered/official"),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    proof = json.loads(result.stdout.strip().splitlines()[-1])
    if proof.get("corrected_frames_matching_official") != 3 or proof.get("games_launched") != 0:
        raise ValueError("The corrected saved prefix did not exactly match")
    return write(
        output,
        {
            "schema_version": "native-a8-selector-identity-saved-audit-v1",
            "config_id": manifest_identifier(cfg),
            **facts,
            **proof,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("native", "short", "full"), nargs="?", default="full")
    parser.add_argument("--execute", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path.cwd()
    cfg = load(root)
    area = _private_path(root, cfg["workspace"])
    area.mkdir(parents=True, exist_ok=True)
    if args.mode == "full" and args.execute is None:
        attempt = time.time_ns()
        tracked = run_tracked_command(
            command=[
                "uv",
                "run",
                "--no-sync",
                "python",
                "-B",
                "-m",
                MODULE,
                "full",
                "--execute",
                str(attempt),
            ],
            working_directory=root,
            experiment_kind=ExperimentKind.OTHER,
            report_path=area / f"resources-{attempt}.json",
            artifact_roots=[area],
            limits=ResourceLimits(**cfg["limits"]),
        )
        print(json.dumps(tracked.report))
        return 0 if tracked.exit_code == 0 and tracked.report["cap"] is None else 2
    with (area / "session.lock").open("ab") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ctx = context(root)
        saved_check(root, cfg, ctx["node"], area / f"saved-audit-{time.time_ns()}.json")
        with patch.multiple(
            native_selector_paired_session,
            PairedWorker=PairedWorker,
            SCHEMA=SCHEMA,
            context=lambda _: ctx,
        ):
            result = native_selector_paired_session.run(root, cfg, area, args.mode)
    print(
        json.dumps(
            {key: result[key] for key in ("status", "mode", "verified_pairs", "stop", "report_id")}
        )
    )
    return 0 if result["status"] == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
