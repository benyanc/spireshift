"""Fresh mixed controls after the zero-choice raw/canonical checker stop."""

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
from spireshift.native_mixed_handoff_inputs_v1 import (
    LIMITS,
    SHORT_LIMITS,
)
from spireshift.native_mixed_handoff_inputs_v1 import (
    context as context,
)

RECIPE = "configs/native-compatibility/sts2-v0.111.0-a8-mixed-handoffs-v2.json"
PARENT = "configs/native-compatibility/sts2-v0.111.0-a8-mixed-handoffs-v1.json"
SCHEMA = "native-a8-mixed-handoffs-v2"
MODULE = "spireshift.native_mixed_handoff_session_v2"


def implementation(root: Path) -> dict[str, str]:
    previous = json.loads((root / PARENT).read_text())["implementation"]
    names = {
        *previous,
        PARENT,
        "scripts/check-mixed-handoffs-v2.sh",
        *(
            f"src/spireshift/native_mixed_handoff_{name}_v2.py"
            for name in ("inputs", "checks", "session")
        ),
    }
    return {name: _sha_file(root / name) for name in sorted(names)}


def load(root: Path) -> dict[str, Any]:
    cfg: dict[str, Any] = json.loads((root / RECIPE).read_text())
    previous = json.loads((root / PARENT).read_text())
    expected = [
        {**row, "seed": f"SP1RESH1FTA8MH2C{i:03}"} for i, row in enumerate(previous["cases"], 1)
    ]
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["cases"] != expected
        or cfg["implementation"] != implementation(root)
        or cfg["limits"] != LIMITS
        or cfg["short_limits"] != SHORT_LIMITS
        or cfg["short_case_keys"] != previous["short_case_keys"]
        or cfg["training_allowed"] is not False
        or cfg["optimizer_updates"] != 0
    ):
        raise ValueError("The fresh mixed handoff recipe changed")
    parent = identified(verified(root, cfg["harness_parent_result"]))
    if (
        parent["config_id"] != manifest_identifier(previous)
        or parent["status"] != "blocked_preserving_evidence"
        or parent["mode"] != "native"
        or parent["stop"] != {"case": "rest-brew-smith-lift-return", "error": "KeyError: 'enabled'"}
        or not all(parent["frozen_checks"].values())
        or parent["pairs"]
    ):
        raise ValueError("Require the exact zero-choice checker failure")
    area = root / previous["workspace"]
    native = identified(area / "native/report.json")
    check_sources(root, native["sources"])
    frames = list(records(area / "native/rest-brew-smith-lift-return/frames.jsonl.gz"))
    if (
        len(native["cases"]) != 2
        or len(frames) != 1
        or (area / "native/rest-brew-smith-lift-return/choices.jsonl.gz").exists()
    ):
        raise ValueError("The rest failure delivered gameplay or has different native history")
    check_sources(root, cfg["game_source_evidence"])
    assessment = identified(verified(root, cfg["selector_assessment"]))
    if assessment["report_id"] != cfg["selector_assessment_id"]:
        raise ValueError("The current selector baseline changed")
    return cfg
