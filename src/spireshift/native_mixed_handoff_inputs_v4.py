"""Reuse two complete native controls and finish the corrected rest handoff scope."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_verification_v12 import records
from spireshift.native_mixed_handoff_inputs_v3 import load as parent_plan

RECIPE = "configs/native-compatibility/sts2-v0.111.0-a8-mixed-handoffs-v4.json"
PARENT = "configs/native-compatibility/sts2-v0.111.0-a8-mixed-handoffs-v3.json"
SCHEMA = "native-a8-mixed-handoffs-v4"
MODULE = "spireshift.native_mixed_handoff_session_v4"


def implementation(root: Path) -> dict[str, str]:
    previous = json.loads((root / PARENT).read_text())["implementation"]
    names = {
        *previous,
        PARENT,
        "scripts/check-mixed-handoffs-v4.sh",
        *(
            f"src/spireshift/native_mixed_handoff_{name}_v4.py"
            for name in ("inputs", "cases", "session")
        ),
    }
    return {name: _sha_file(root / name) for name in sorted(names)}


def load(root: Path) -> dict[str, Any]:
    cfg: dict[str, Any] = json.loads((root / RECIPE).read_text())
    previous = parent_plan(root)
    expected = [{**row} for row in previous["cases"]]
    expected[2]["seed"] = "SP1RESH1FTA8MH4C003"
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["cases"] != expected
        or cfg["implementation"] != implementation(root)
        or cfg["limits"] != previous["limits"]
        or cfg["short_limits"] != previous["short_limits"]
        or cfg["short_case_keys"] != previous["short_case_keys"]
        or cfg["training_allowed"] is not False
        or cfg["optimizer_updates"] != 0
    ):
        raise ValueError("The coordinate-bound mixed handoff declaration changed")
    result = identified(verified(root, cfg["harness_parent_result"]))
    if (
        result["config_id"] != manifest_identifier(previous)
        or result["status"] != "blocked_preserving_evidence"
        or result["stop"] != {"case": "rest-brew-smith-lift-return", "error": "StopIteration: "}
        or result["pairs"]
        or not all(result["frozen_checks"].values())
    ):
        raise ValueError("Require the exact preserved map-type matcher failure")
    area = root / previous["workspace"]
    native = identified(area / "native/report.json")
    check_sources(root, native["sources"])
    frames = list(records(area / "native/rest-brew-smith-lift-return/frames.jsonl.gz"))
    if len(frames) != 9 or frames[-1]["source_family"] != "map_navigation":
        raise ValueError("The diagnostic rest prefix has different native progress")
    if len(cfg["native_imports"]) != 2:
        raise ValueError("Require exactly the two unaffected completed native controls")
    for expected_case, ref in zip(expected[:2], cfg["native_imports"], strict=True):
        seal = identified(verified(root, ref))
        if seal["status"] != "verified" or seal["case"] != expected_case:
            raise ValueError("The imported native seal has a different fixture or outcome")
    check_sources(root, cfg["game_source_evidence"])
    return cfg
