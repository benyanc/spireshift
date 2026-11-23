"""Bind the corrected startup property and retain the unused continuation worlds."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_mixed_handoff_inputs_v1 import context as parent_context
from spireshift.native_mixed_handoff_inputs_v5 import adapter
from spireshift.native_mixed_handoff_inputs_v5 import load as previous_plan

RECIPE = "configs/native-compatibility/sts2-v0.111.0-a8-mixed-handoffs-v6.json"
PARENT = "configs/native-compatibility/sts2-v0.111.0-a8-mixed-handoffs-v5.json"
SCHEMA = "native-a8-mixed-handoffs-v6"
MODULE = "spireshift.native_mixed_handoff_session_v6"


def implementation(root: Path) -> dict[str, str]:
    previous = json.loads((root / PARENT).read_text())["implementation"]
    names = {
        *previous,
        PARENT,
        "mod/SpireShift.HeadlessMerchantOverlayV2/SpireShift.HeadlessMerchantOverlayV2.csproj",
        "mod/SpireShift.HeadlessMerchantOverlayV2/MerchantOverlay.cs",
        "scripts/check-mixed-handoffs-v6.sh",
        "src/spireshift/native_mixed_handoff_inputs_v6.py",
        "src/spireshift/native_mixed_handoff_session_v6.py",
    }
    return {name: _sha_file(root / name) for name in sorted(names)}


def load(root: Path) -> dict[str, Any]:
    cfg: dict[str, Any] = json.loads((root / RECIPE).read_text())
    previous = previous_plan(root)
    expected = [{**row} for row in previous["cases"]]
    expected[0]["seed"] = "SP1RESH1FTA8MH6F001"
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["cases"] != expected
        or cfg["implementation"] != implementation(root)
        or cfg["limits"] != previous["limits"]
        or cfg["short_limits"] != previous["short_limits"]
        or cfg["short_case_keys"] != previous["short_case_keys"]
        or cfg["native_imports"] != previous["native_imports"]
        or cfg["training_allowed"] is not False
        or cfg["optimizer_updates"] != 0
    ):
        raise ValueError("The corrected merchant startup declaration changed")
    stopped = identified(verified(root, cfg["startup_stop"]))
    if (
        stopped["config_id"] != manifest_identifier(previous)
        or stopped["status"] != "blocked_preserving_evidence"
        or stopped["mode"] != "native"
        or stopped["pairs"]
        or stopped["stop"]
        != {
            "case": "merchant-map-use",
            "error": (
                "ValueError: Native worker failed: JSON-line process exited before replying "
                "(code=null, signal=SIGABRT)."
            ),
        }
        or not all(stopped["frozen_checks"].values())
    ):
        raise ValueError("Require the preserved startup refusal before world initialization")
    native = identified(verified(root, cfg["original_native_result"]))
    parent = identified(verified(root, cfg["parent_result"]))
    if native["report_id"] != parent["native_report_id"] or native["stop"] is not None:
        raise ValueError("The original native control inventory changed")
    check_sources(root, native["sources"])
    check_sources(root, cfg["game_source_evidence"])
    adapter(root, cfg)
    return cfg


def context(root: Path) -> dict[str, Any]:
    cfg = load(root)
    ctx = parent_context(root)
    built = adapter(root, cfg)
    if ctx["lifecycle_adapter"] != built["original_lifecycle_adapter"]:
        raise ValueError("The original card lifecycle adapter changed")
    return {**ctx, "lifecycle_adapter": built["adapter"]}
