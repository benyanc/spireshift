"""Qualify corrected selector execution after the preserved accepted-only macro."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_selector_paired_inputs, native_selector_paired_v2
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_verification_v12 import records
from spireshift.native_systematic_live_v1 import compare_frames

RECIPE = "configs/native-compatibility/sts2-v0.111.0-a8-official-selectors-v3.json"
CONNECTOR = "configs/engine-qualification/sts2-v0.111.0-connector-ordered-completion-v34.json"
SCHEMA = "native-a8-official-selector-comparison-v3"
MODULE = "spireshift.native_selector_paired_v3"
ORIGINAL_CONTEXT = native_selector_paired_inputs.context
PARENT_RECIPE = native_selector_paired_v2.RECIPE


def implementation(root: Path) -> dict[str, str]:
    previous = json.loads((root / PARENT_RECIPE).read_text())["implementation"]
    names = {
        *previous,
        PARENT_RECIPE,
        "src/spireshift/native_selector_paired_v3.py",
        "scripts/compare-official-selectors-v3.sh",
        CONNECTOR,
        "configs/engine-qualification/sts2-v0.111.0-connector-ordered-completion-build-v34.json",
        "patches/engine/sts2-connector-v0.111.0-ordered-completion-v34.patch",
    }
    return {name: _sha_file(root / name) for name in sorted(names)}


def completion_audit(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    previous = json.loads((root / PARENT_RECIPE).read_text())
    result = identified(verified(root, cfg["completion_parent_result"]))
    if (
        result["status"] != "blocked_preserving_evidence"
        or result["verified_pairs"] != 0
        or result["config_id"] != manifest_identifier(previous)
        or len(result["pairs"]) != 1
        or not all(result["frozen_checks"].values())
    ):
        raise ValueError("Require the preserved incomplete Connector33 macro")
    pair = result["pairs"][0]
    check_sources(root, pair["sources"])
    official = pair["official"]
    if (
        pair["difference"] is not None
        or not all(official["checks"].values())
        or official["probe"]["policy_decisions"] != 6
        or official["probe"]["local_answer_factors"] != 2
        or official["probe"]["atomic_selections"] != 0
    ):
        raise ValueError("The stopped macro has a different ownership or completion history")
    area = root / previous["workspace"]
    source = area / "pairs/shop-ordered/official"
    if (
        "InvalidOperationException: Incomplete ordered answer card domain"
        not in (source / "stderr.log").read_text()
    ):
        raise ValueError("Missing the exact publication-versus-execution validation failure")
    rows = list(records(source / "live-public.jsonl.gz"))
    offered = [row["frame"] for row in rows if row["kind"] == "policy_input"]
    native = list(records(area / "native/shop-ordered/frames.jsonl.gz"))
    if len(offered) != 7 or not compare_frames(native[:7], offered)["equal"]:
        raise ValueError("The seven complete offered menus do not independently match")
    (accepted,) = [row for row in rows if row["kind"] == "selection_acceptance"]
    if (
        accepted["receipt"]["delivery"] != "delivered"
        or accepted["action"]["verb"] != "confirm"
        or accepted["before_snapshot_id"] != offered[-1]["observation"]["snapshot_id"]
        or any(row["kind"] == "atomic_selection_completion" for row in rows)
    ):
        raise ValueError("The macro was not an unqualified accepted-only confirmation")
    native_result = identified(area / "native/report.json")
    check_sources(root, native_result["sources"])
    return {
        "parent_report_id": result["report_id"],
        "matching_offered_frames": 7,
        "acknowledged_choices": 6,
        "verified_zero_native_input_factors": 2,
        "accepted_macro_completion_qualified": False,
        "clean_shutdown_and_reset": True,
    }


def load(root: Path) -> dict[str, Any]:
    cfg: dict[str, Any] = json.loads((root / RECIPE).read_text())
    previous = json.loads((root / PARENT_RECIPE).read_text())
    expected = [
        {**case, "seed": f"SP1RESH1FTA8P3SLC{i:03}"} for i, case in enumerate(previous["cases"], 1)
    ]
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["cases"] != expected
        or cfg["limits"] != previous["limits"]
        or cfg["implementation"] != implementation(root)
        or cfg["training_allowed"] is not False
    ):
        raise ValueError("The separately frozen completion recipe changed")
    native_selector_paired_v2.parent_audit(root, cfg)
    completion_audit(root, cfg)
    return cfg


def context(root: Path) -> dict[str, Any]:
    with patch.object(native_selector_paired_inputs, "CONNECTOR", CONNECTOR):
        return ORIGINAL_CONTEXT(root)


def main() -> int:
    # Reuse the serial runner, SDK delivery checks and immutable worker unchanged.
    with patch.multiple(
        native_selector_paired_v2,
        RECIPE=RECIPE,
        SCHEMA=SCHEMA,
        MODULE=MODULE,
        load=load,
        context=context,
    ):
        return native_selector_paired_v2.main()


if __name__ == "__main__":
    raise SystemExit(main())
