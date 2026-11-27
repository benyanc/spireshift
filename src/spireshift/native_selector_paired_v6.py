"""Finish the two selector controls after an inspected zero-input startup stall."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import (
    native_selector_lifecycle_cases,
    native_selector_lifecycle_checks,
    native_selector_paired_session,
    native_selector_paired_v2,
    native_selector_paired_v4,
    native_selector_paired_v5,
    native_selector_startup_reset,
)
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_verification_v12 import records
from spireshift.native_selector_executable_checks import check_selector
from spireshift.native_selector_paired_contract import PairedPolicy, audit
from spireshift.native_win4_game import write

RECIPE = "configs/native-compatibility/sts2-v0.111.0-a8-official-selectors-v6.json"
SCHEMA = "native-a8-official-selector-comparison-v6"
MODULE = "spireshift.native_selector_paired_v6"
PARENT_RECIPE = native_selector_paired_v5.RECIPE


def cases(root: Path) -> list[dict[str, Any]]:
    previous = json.loads((root / PARENT_RECIPE).read_text())
    minimum, reward = previous["cases"][4:]
    return [{**minimum, "seed": "SP1RESH1FTA8P6SLC005"}, reward]


def implementation(root: Path) -> dict[str, str]:
    previous = json.loads((root / PARENT_RECIPE).read_text())["implementation"]
    names = {
        *previous,
        PARENT_RECIPE,
        "src/spireshift/native_selector_paired_v6.py",
        "src/spireshift/native_selector_startup_reset.py",
        "scripts/compare-official-selectors-v6.sh",
    }
    return {name: _sha_file(root / name) for name in sorted(names)}


def parent_audit(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    previous = native_selector_paired_v5.load(root)
    result = identified(verified(root, cfg["startup_parent_result"]))
    inspection = identified(verified(root, cfg["inspected_reset"]))
    if (
        result["config_id"] != manifest_identifier(previous)
        or result["status"] != "blocked_preserving_evidence"
        or result["verified_pairs"] != 4
        or result["planned_pairs"] != 6
        or len(result["pairs"]) != 4
        or not all(result["frozen_checks"].values())
        or result["stop"]["case"] != "shop-minimum-answer"
        or result["stop"]["error"]
        != "ValueError: Official worker shutdown/integrity unverified; preserve its active lease"
        or inspection["status"] != "inspected_zero_action_asset_loading_stall"
        or inspection["lease"]["attempt"] != str(root / native_selector_startup_reset.ATTEMPT)
        or inspection["gameplay_inputs_delivered"] != 0
    ):
        raise ValueError("Require the four current paired proofs and exact startup-only stop")
    native = identified(root / previous["workspace"] / "native/report.json")
    check_sources(root, native["sources"])
    if native["report_id"] != result["native_report_id"]:
        raise ValueError("The preserved native preparation changed")
    for case, row in zip(previous["cases"][:4], result["pairs"], strict=True):
        check_sources(root, row["sources"])
        if (
            row["case"] != case
            or row["status"] != "verified"
            or row["config_id"] != result["config_id"]
            or not all(row["official"]["checks"].values())
            or row["official"]["working_app"]["restored"] is not True
            or row["paired"]["equal"] is not True
            or row["paired"]["all_public_reads_reconstructed"] is not True
        ):
            raise ValueError("A preserved current pair lacks its complete menu/effect/reset proof")
    return result


def load(root: Path) -> dict[str, Any]:
    cfg: dict[str, Any] = json.loads((root / RECIPE).read_text())
    previous = json.loads((root / PARENT_RECIPE).read_text())
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["cases"] != cases(root)
        or cfg["limits"] != previous["limits"]
        or cfg["implementation"] != implementation(root)
        or cfg["training_allowed"] is not False
        or cfg["linked_planned_slots"] != 7
        or cfg["historical_startup_failure_retained"] is not True
    ):
        raise ValueError("The two-case continuation declaration changed")
    parent_audit(root, cfg)
    return cfg


def saved_check(root: Path, cfg: dict[str, Any], node: str, output: Path) -> dict[str, Any]:
    regression = native_selector_paired_v4.saved_check(
        root, cfg, node, output.with_stem(output.stem + "-regressions")
    )
    previous = json.loads((root / PARENT_RECIPE).read_text())
    result = parent_audit(root, cfg)
    ctx = native_selector_paired_v5.context(root)
    proofs = []
    for row in result["pairs"]:
        source = root / previous["workspace"] / "native" / row["case"]["key"]
        directory = root / previous["workspace"] / "pairs" / row["case"]["key"] / "official"
        policy = PairedPolicy(
            list(records(source / "frames.jsonl.gz")),
            [item["choice"]["action_index"] for item in records(source / "choices.jsonl.gz")],
        )
        policy.frames = [
            item["frame"]
            for item in records(directory / "live-public.jsonl.gz")
            if item["kind"] in {"policy_input", "diagnostic_successor"}
        ]
        proofs.append(
            {"case": row["case"]["key"], **audit(ctx, directory, policy, time.monotonic() + 40)}
        )
    return write(
        output,
        {
            "schema_version": "native-selector-current-four-pair-saved-audit-v1",
            "config_id": manifest_identifier(cfg),
            "parent_report_id": result["report_id"],
            "regression_report_id": regression["report_id"],
            "imported_current_pair_proofs": proofs,
            "historical_startup_failures": 1,
            "remaining_controls": 2,
            "games_launched": 0,
        },
    )


def main() -> int:
    with (
        patch.multiple(
            native_selector_paired_v2,
            RECIPE=RECIPE,
            SCHEMA=SCHEMA,
            MODULE=MODULE,
            SCRIPT=native_selector_paired_v5.SCRIPT,
            load=load,
            context=native_selector_paired_v5.context,
            saved_check=saved_check,
        ),
        patch.object(native_selector_paired_session, "reset", native_selector_startup_reset.reset),
        patch.object(
            native_selector_lifecycle_cases, "reward_case", native_selector_paired_v4.reward_case
        ),
        patch.object(native_selector_lifecycle_cases, "check_selector", check_selector),
        patch.object(native_selector_lifecycle_checks, "check_selector", check_selector),
    ):
        return native_selector_paired_v2.main()


if __name__ == "__main__":
    raise SystemExit(main())
