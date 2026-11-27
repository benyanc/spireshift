"""Qualify one current potion view across reward capacity and selection owners."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import (
    native_selector_lifecycle_cases,
    native_selector_paired_inputs,
    native_selector_paired_v2,
    native_selector_paired_v3,
)
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_verification_v12 import records
from spireshift.native_win4_game import write

RECIPE = "configs/native-compatibility/sts2-v0.111.0-a8-official-selectors-v4.json"
CONNECTOR = "configs/engine-qualification/sts2-v0.111.0-connector-reward-belt-v35.json"
SCHEMA = "native-a8-official-selector-comparison-v4"
MODULE = "spireshift.native_selector_paired_v4"
SCRIPT = "engine-selector-paired-worker-v3.mjs"
PARENT_RECIPE = native_selector_paired_v3.RECIPE
ORIGINAL_CONTEXT = native_selector_paired_inputs.context
ORIGINAL_SAVED_CHECK = native_selector_paired_v2.saved_check
ORIGINAL_REWARD_CASE = native_selector_lifecycle_cases.reward_case


def implementation(root: Path) -> dict[str, str]:
    previous = json.loads((root / PARENT_RECIPE).read_text())["implementation"]
    names = {
        *previous,
        PARENT_RECIPE,
        "src/spireshift/native_selector_paired_v4.py",
        "scripts/compare-official-selectors-v4.sh",
        CONNECTOR,
        "configs/engine-qualification/sts2-v0.111.0-connector-reward-belt-build-v35.json",
        "patches/engine/sts2-connector-v0.111.0-reward-belt-v35.patch",
    }
    for script in (SCRIPT, "engine-reward-belt-audit-v1.mjs"):
        names.update(f"scripts/{name}" for name in worker_helpers(root, script))
    return {name: _sha_file(root / name) for name in sorted(names)}


def publication_audit(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    previous = json.loads((root / PARENT_RECIPE).read_text())
    result = identified(verified(root, cfg["reward_parent_result"]))
    if (
        result["status"] != "blocked_preserving_evidence"
        or result["verified_pairs"] != 1
        or result["config_id"] != manifest_identifier(previous)
        or len(result["pairs"]) != 2
        or not all(result["frozen_checks"].values())
    ):
        raise ValueError("Require the preserved ordered pass and reward publication stop")
    passed, blocked = result["pairs"]
    for row in (passed, blocked):
        check_sources(root, row["sources"])
        if not all(row["official"]["checks"].values()):
            raise ValueError("A parent official profile or reset was not verified")
    if (
        passed["status"] != "verified"
        or passed["official"]["probe"]["atomic_selections"] != 1
        or passed["official"]["probe"]["local_answer_factors"] != 2
        or not passed["paired"]["all_public_reads_reconstructed"]
        or blocked["case"]["key"] != "reward-card-take"
        or blocked["official"]["probe"]["policy_decisions"] != 2
        or blocked["official"]["probe"]["error"]
        != "Conflicting current public entity facts: interaction/surface/potion_states/0/can_use"
    ):
        raise ValueError("The preserved reward conflict has a different scope")
    native = identified(root / previous["workspace"] / "native/report.json")
    check_sources(root, native["sources"])
    return {
        "parent_report_id": result["report_id"],
        "historical_verified_pairs": 1,
        "historical_blocked_pairs": 1,
        "historical_unattempted_pairs": 4,
        "ordered_native_completion_proven": True,
        "both_personal_profiles_and_resets_verified": True,
    }


def load(root: Path) -> dict[str, Any]:
    cfg: dict[str, Any] = json.loads((root / RECIPE).read_text())
    previous = json.loads((root / PARENT_RECIPE).read_text())
    expected = [
        {**case, "seed": f"SP1RESH1FTA8P4SLC{i:03}"} for i, case in enumerate(previous["cases"], 1)
    ]
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["cases"] != expected
        or cfg["limits"] != previous["limits"]
        or cfg["implementation"] != implementation(root)
        or cfg["training_allowed"] is not False
        or cfg["diagnostic_potion_drop_probability"] != 1
    ):
        raise ValueError("The separately declared reward-belt comparison changed")
    native_selector_paired_v2.parent_audit(root, cfg)
    native_selector_paired_v3.completion_audit(root, cfg)
    publication_audit(root, cfg)
    check_sources(root, cfg["reward_belt_probe"]["sources"])
    return cfg


def context(root: Path) -> dict[str, Any]:
    with patch.object(native_selector_paired_inputs, "CONNECTOR", CONNECTOR):
        return ORIGINAL_CONTEXT(root)


def saved_check(root: Path, cfg: dict[str, Any], node: str, output: Path) -> dict[str, Any]:
    inventory = ORIGINAL_SAVED_CHECK(root, cfg, node, output.with_stem(output.stem + "-inventory"))
    previous = json.loads((root / PARENT_RECIPE).read_text())
    area = root / previous["workspace"]
    result = subprocess.run(
        [
            node,
            str(root / "scripts/engine-reward-belt-audit-v1.mjs"),
            str(area / "native/reward-card-take"),
            str(area / "pairs/reward-card-take/official"),
            str(verified(root, cfg["reward_belt_probe"]["project"])),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
        timeout=40,
    )
    proof = json.loads(result.stdout.strip().splitlines()[-1])
    if not proof["corrected_complete_reward_input_matches_native"] or proof["games_launched"] != 0:
        raise ValueError("The corrected capacity/belt view does not match the saved native input")
    return write(
        output,
        {
            "schema_version": "native-a8-selector-shared-inventory-audit-v1",
            "config_id": manifest_identifier(cfg),
            "inventory_audit_id": inventory["report_id"],
            **publication_audit(root, cfg),
            **proof,
        },
    )


def reward_case(
    ctx: dict[str, Any], case: dict[str, Any], area: Path, deadline: float
) -> dict[str, Any]:
    result = ORIGINAL_REWARD_CASE(ctx, case, area, deadline)
    offered = next(
        row["snapshot"]["interaction"]["content"]["surface"]
        for row in records(area / "worker/public-observations.jsonl.gz")
        if row["snapshot"]["interaction"]["kind"] == "reward_claim"
    )
    if (
        offered["potion_slots_full"] is not True
        or len(offered["discardable_potions"]) != 2
        or not any(
            row["kind"] == "potion" and row["enabled"] is False for row in offered["rewards"]
        )
    ):
        raise ValueError("The declared full-belt potion-reward branch was not exercised")
    return {**result, "potion_capacity_branch_verified": True}


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
            saved_check=saved_check,
        ),
        patch.object(native_selector_lifecycle_cases, "reward_case", reward_case),
    ):
        return native_selector_paired_v2.main()


if __name__ == "__main__":
    raise SystemExit(main())
