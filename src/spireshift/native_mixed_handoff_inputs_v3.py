"""Fresh mixed controls after a preserved rest-exit label matcher stop."""

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
from spireshift.native_mixed_handoff_inputs_v2 import load as parent_plan

RECIPE = "configs/native-compatibility/sts2-v0.111.0-a8-mixed-handoffs-v3.json"
PARENT = "configs/native-compatibility/sts2-v0.111.0-a8-mixed-handoffs-v2.json"
SCHEMA = "native-a8-mixed-handoffs-v3"
MODULE = "spireshift.native_mixed_handoff_session_v3"


def implementation(root: Path) -> dict[str, str]:
    previous = json.loads((root / PARENT).read_text())["implementation"]
    names = {
        *previous,
        PARENT,
        "scripts/check-mixed-handoffs-v3.sh",
        *(
            f"src/spireshift/native_mixed_handoff_{name}_v3.py"
            for name in ("inputs", "checks", "session")
        ),
    }
    return {name: _sha_file(root / name) for name in sorted(names)}


def load(root: Path) -> dict[str, Any]:
    cfg: dict[str, Any] = json.loads((root / RECIPE).read_text())
    previous = parent_plan(root)
    expected = [
        {**row, "seed": f"SP1RESH1FTA8MH3C{i:03}"} for i, row in enumerate(previous["cases"], 1)
    ]
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
        raise ValueError("The rest-exit mixed handoff declaration changed")
    result = identified(verified(root, cfg["harness_parent_result"]))
    if (
        result["config_id"] != manifest_identifier(previous)
        or result["status"] != "blocked_preserving_evidence"
        or result["stop"]
        != {
            "case": "rest-brew-smith-lift-return",
            "error": "ValueError: not enough values to unpack (expected 1, got 0)",
        }
        or result["pairs"]
        or not all(result["frozen_checks"].values())
    ):
        raise ValueError("Require the preserved diagnostic rest prefix and matcher failure")
    area = root / previous["workspace"]
    native = identified(area / "native/report.json")
    check_sources(root, native["sources"])
    frames = list(records(area / "native/rest-brew-smith-lift-return/frames.jsonl.gz"))
    choices = list(records(area / "native/rest-brew-smith-lift-return/choices.jsonl.gz"))
    if (
        len(frames) != 8
        or len(choices) != 7
        or frames[-1]["public_input"]["context"]["interaction"]["content"]["surface"]["can_proceed"]
        is not True
    ):
        raise ValueError("The failed diagnostic prefix has different delivered actions")
    check_sources(root, cfg["game_source_evidence"])
    return cfg
