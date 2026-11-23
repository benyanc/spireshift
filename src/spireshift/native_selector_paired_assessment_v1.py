"""Reconstruct the six current selector proofs without launching either host."""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

from spireshift import native_selector_paired_v5, native_selector_paired_v6
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_verification_v12 import records
from spireshift.native_selector_paired_contract import PairedPolicy, audit
from spireshift.native_win4_game import write


def assess(root: Path, result_path: Path, output: Path) -> dict[str, Any]:
    cfg = native_selector_paired_v6.load(root)
    parent = native_selector_paired_v6.parent_audit(root, cfg)
    result = identified(result_path)
    if (
        result["status"] != "verified"
        or result["mode"] != "full"
        or result["config_id"] != manifest_identifier(cfg)
        or result["verified_pairs"] != 2
        or result["planned_pairs"] != 2
        or len(result["pairs"]) != 2
        or [row["case"] for row in result["pairs"]] != cfg["cases"]
        or result["environment_id"] != parent["environment_id"]
        or not all(result["frozen_checks"].values())
        or result["optimizer_updates"] != 0
        or result["stop"] is not None
    ):
        raise ValueError("Require the two exact clean continuation pairs")
    ctx = native_selector_paired_v5.context(root)
    before = frozen(root, ctx)
    proofs = []
    parent_workspace = str((root / cfg["startup_parent_result"]["path"]).parent.relative_to(root))
    bindings = [
        *((parent_workspace, row) for row in parent["pairs"]),
        *((cfg["workspace"], row) for row in result["pairs"]),
    ]
    for workspace, row in bindings:
        check_sources(root, row["sources"])
        if (
            row["status"] != "verified"
            or not all(row["official"]["checks"].values())
            or row["official"]["working_app"]["restored"] is not True
        ):
            raise ValueError("A current pair lacks a clean official reset")
        # Bind every fixture to its own version's native seal.
        native = root / workspace / "native" / row["case"]["key"]
        case = identified(native / "report.json")
        if case["report_id"] != row["native_case_report_id"] or case["case"] != row["case"]:
            raise ValueError("The native case does not own this paired proof")
        official = root / workspace / "pairs" / row["case"]["key"] / "official"
        policy = PairedPolicy(
            list(records(native / "frames.jsonl.gz")),
            [item["choice"]["action_index"] for item in records(native / "choices.jsonl.gz")],
        )
        policy.frames = [
            item["frame"]
            for item in records(official / "live-public.jsonl.gz")
            if item["kind"] in {"policy_input", "diagnostic_successor"}
        ]
        proof = audit(ctx, official, policy, time.monotonic() + 40)
        proofs.append(
            {
                "case": row["case"],
                "pair_report_id": row["report_id"],
                **row["native_effects"],
                **proof,
                "official_atomic_commits": row["official"]["probe"]["atomic_selections"],
                "official_selection_ui_steps": row["official"]["probe"]["selection_ui_steps"],
                "clean_shutdown_and_reset": True,
            }
        )
    check_sources(root, cfg["implementation"])
    if frozen(root, ctx) != before:
        raise ValueError("Frozen inputs changed during saved-only reconstruction")
    return write(
        output,
        {
            "schema_version": "native-official-selector-saved-assessment-v1",
            "status": "six_current_selector_mechanisms_verified",
            "source": {
                "path": str(result_path.relative_to(root)),
                "sha256": _sha_file(result_path),
            },
            "parent_report_id": parent["report_id"],
            "continuation_report_id": result["report_id"],
            "environment_id": result["environment_id"],
            "verified_mechanisms": 6,
            "linked_panel": {"slots": 7, "verified": 6, "startup_failed": 1, "unattempted": 0},
            "separate_prelaunch_process_scan_abort_retained": True,
            "pairs": proofs,
            "actual_sdk_deliveries_verified": sum(
                p["actual_sdk_deliveries_verified"] for p in proofs
            ),
            "matching_public_states": sum(p["matching_states"] for p in proofs),
            "frozen_checks": before,
            "games_launched_by_assessment": 0,
            "optimizer_updates": 0,
            "training_allowed": False,
            "official_live_qualification_granted": False,
            "full_game_playing_strength_evaluated": False,
            "automatic_follow_up": False,
            "scope": "declared_privileged_shop_and_reward_selector_chains_only",
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path.cwd()
    report = assess(root, args.result.resolve(), args.output.resolve())
    print(report["status"], report["report_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
