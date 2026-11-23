"""Qualify executable enchant menus without changing the frozen game's callback."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import (
    native_selector_lifecycle_cases,
    native_selector_lifecycle_checks,
    native_selector_paired_inputs,
    native_selector_paired_v2,
    native_selector_paired_v3,
    native_selector_paired_v4,
)
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_verification_v12 import records
from spireshift.native_selector_executable_checks import check_selector

RECIPE = "configs/native-compatibility/sts2-v0.111.0-a8-official-selectors-v5.json"
CONNECTOR = "configs/engine-qualification/sts2-v0.111.0-connector-executable-enchant-v36.json"
SCHEMA = "native-a8-official-selector-comparison-v5"
MODULE = "spireshift.native_selector_paired_v5"
SCRIPT = "engine-selector-paired-worker-v4.mjs"
PARENT_RECIPE = native_selector_paired_v4.RECIPE
ORIGINAL_CONTEXT = native_selector_paired_inputs.context


def cases(root: Path) -> list[dict[str, Any]]:
    previous = json.loads((root / PARENT_RECIPE).read_text())
    result = []
    for i, old in enumerate(previous["cases"], 1):
        row = {**old, "seed": f"SP1RESH1FTA8P5SLC{i:03}"}
        if row["key"] == "shop-ordered-empty":
            row.update(key="shop-minimum-answer", indices=[12])
        result.append(row)
    return result


def implementation(root: Path) -> dict[str, str]:
    previous = json.loads((root / PARENT_RECIPE).read_text())["implementation"]
    names = {
        *previous,
        PARENT_RECIPE,
        "src/spireshift/native_selector_paired_v5.py",
        "src/spireshift/native_selector_executable_checks.py",
        "scripts/compare-official-selectors-v5.sh",
        CONNECTOR,
        "configs/engine-qualification/sts2-v0.111.0-connector-executable-enchant-build-v36.json",
        "patches/engine/sts2-connector-v0.111.0-executable-enchant-v36.patch",
    }
    names.update(f"scripts/{name}" for name in worker_helpers(root, SCRIPT))
    return {name: _sha_file(root / name) for name in sorted(names)}


def empty_answer_audit(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    previous = json.loads((root / PARENT_RECIPE).read_text())
    result = identified(verified(root, cfg["empty_answer_parent_result"]))
    if (
        result["status"] != "blocked_preserving_evidence"
        or result["verified_pairs"] != 4
        or result["config_id"] != manifest_identifier(previous)
        or len(result["pairs"]) != 5
        or not all(result["frozen_checks"].values())
    ):
        raise ValueError("Require the preserved four pairs and uncompleted empty enchant")
    for row in result["pairs"]:
        check_sources(root, row["sources"])
        if not all(row["official"]["checks"].values()):
            raise ValueError("An earlier profile or working app did not reset")
    blocked = result["pairs"][-1]
    if (
        blocked["case"]["key"] != "shop-ordered-empty"
        or blocked["official"]["probe"]["policy_decisions"] != 4
        or blocked["difference"] is not None
    ):
        raise ValueError("The empty-answer stop has a different scope")
    area = root / previous["workspace"]
    official = area / "pairs/shop-ordered-empty/official"
    if "atomic_selection_timeout" not in (official / "stderr.log").read_text():
        raise ValueError("Missing the native empty-confirmation timeout")
    rows = list(records(official / "live-public.jsonl.gz"))
    (accepted,) = [row for row in rows if row["kind"] == "selection_acceptance"]
    if (
        accepted["receipt"]["delivery"] != "delivered"
        or accepted["action"]["verb"] != "confirm"
        or accepted["action"]["arguments"]
        or any(row["kind"] == "atomic_selection_completion" for row in rows)
    ):
        raise ValueError("An empty answer was completed or lacks its exact acceptance")
    text = verified(root, cfg["enchant_completion_source"]).read_text()
    if (
        "if (_selectedCards.Count != 0)" not in text
        or "private void ConfirmSelection(NButton inputEvent)" not in text
        or "_selectedCards.Count >= _prefs.MinSelect && _selectedCards.Count <= _prefs.MaxSelect"
        not in text
    ):
        raise ValueError("Frozen enchant completion source changed")
    return {
        "parent_report_id": result["report_id"],
        "historical_delivered_pair_proofs": 4,
        "historical_blocked_pairs": 1,
        "historical_unattempted_pairs": 1,
        "old_enchant_complete_menu_claim_superseded": True,
        "empty_completion_qualified": False,
        "game_callback_unchanged": True,
    }


def load(root: Path) -> dict[str, Any]:
    cfg: dict[str, Any] = json.loads((root / RECIPE).read_text())
    previous = json.loads((root / PARENT_RECIPE).read_text())
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["cases"] != cases(root)
        or cfg["limits"] != previous["limits"]
        or cfg["implementation"] != implementation(root)
        or cfg["training_allowed"] is not False
        or cfg["enchant_minimum_committable_cards"] != 1
    ):
        raise ValueError("The executable-enchant comparison declaration changed")
    native_selector_paired_v2.parent_audit(root, cfg)
    native_selector_paired_v3.completion_audit(root, cfg)
    native_selector_paired_v4.publication_audit(root, cfg)
    empty_answer_audit(root, cfg)
    check_sources(root, cfg["reward_belt_probe"]["sources"])
    return cfg


def context(root: Path) -> dict[str, Any]:
    with patch.object(native_selector_paired_inputs, "CONNECTOR", CONNECTOR):
        return ORIGINAL_CONTEXT(root)


def main() -> int:
    with (
        patch.multiple(
            native_selector_paired_v2,
            RECIPE=RECIPE,
            SCHEMA=SCHEMA,
            MODULE=MODULE,
            SCRIPT=SCRIPT,
            load=load,
            context=context,
            saved_check=native_selector_paired_v4.saved_check,
        ),
        patch.object(
            native_selector_lifecycle_cases, "reward_case", native_selector_paired_v4.reward_case
        ),
        patch.object(native_selector_lifecycle_cases, "check_selector", check_selector),
        patch.object(native_selector_lifecycle_checks, "check_selector", check_selector),
    ):
        return native_selector_paired_v2.main()


if __name__ == "__main__":
    raise SystemExit(main())
