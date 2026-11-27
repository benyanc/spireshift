"""Preserve the merchant-map stop and declare disjoint replacement controls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_mixed_handoff_inputs_v1 import context as parent_context
from spireshift.native_mixed_handoff_inputs_v4 import load as parent_plan

RECIPE = "configs/native-compatibility/sts2-v0.111.0-a8-mixed-handoffs-v5.json"
PARENT = "configs/native-compatibility/sts2-v0.111.0-a8-mixed-handoffs-v4.json"
SCHEMA = "native-a8-mixed-handoffs-v5"
MODULE = "spireshift.native_mixed_handoff_session_v5"


def cases(previous: dict[str, Any]) -> list[dict[str, Any]]:
    replacement = {**previous["cases"][5], "seed": "SP1RESH1FTA8MH5C006"}
    probe = {
        **replacement,
        "key": "merchant-map-use",
        "seed": "SP1RESH1FTA8MH5F001",
        "operation": "merchant_map_use",
        "courier": False,
        "relics": [],
    }
    return [probe, replacement, *previous["cases"][6:]]


def implementation(root: Path) -> dict[str, str]:
    previous = json.loads((root / PARENT).read_text())["implementation"]
    names = {
        *previous,
        PARENT,
        "mod/SpireShift.HeadlessActionLifecycle/StartupHook.cs",
        "mod/SpireShift.HeadlessMerchantOverlay/SpireShift.HeadlessMerchantOverlay.csproj",
        "mod/SpireShift.HeadlessMerchantOverlay/MerchantOverlay.cs",
        "scripts/check-mixed-handoffs-v5.sh",
        "scripts/engine-merchant-overlay-audit-v1.mjs",
        "scripts/engine-merchant-overlay-surface-v1.test.mjs",
        "src/spireshift/native_merchant_overlay_checks_v1.py",
        "src/spireshift/native_mixed_handoff_worker_v2.py",
        "src/spireshift/native_mixed_handoff_inputs_v5.py",
        "src/spireshift/native_mixed_handoff_session_v5.py",
        "tests/unit/test_native_merchant_overlay.py",
    }
    names.update(
        f"scripts/{name}" for name in worker_helpers(root, "engine-mixed-handoffs-worker-v2.mjs")
    )
    return {name: _sha_file(root / name) for name in sorted(names)}


def adapter(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    result = identified(verified(root, cfg["adapter_build"]))
    if result["report_id"] != cfg["adapter_build_id"] or result["builds"] != 2:
        raise ValueError("Require the exact reproducible merchant overlay adapter")
    ref = result["adapter"]
    if _sha_file(Path(ref["path"])) != ref["sha256"]:
        raise ValueError("The merchant overlay assembly changed")
    return result


def load(root: Path) -> dict[str, Any]:
    cfg: dict[str, Any] = json.loads((root / RECIPE).read_text())
    previous = parent_plan(root)
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["cases"] != cases(previous)
        or cfg["implementation"] != implementation(root)
        or cfg["limits"] != previous["limits"]
        or cfg["short_limits"] != previous["short_limits"]
        or cfg["short_case_keys"] != [row["key"] for row in cases(previous)[:2]]
        or cfg["training_allowed"] is not False
        or cfg["optimizer_updates"] != 0
    ):
        raise ValueError("The merchant overlay scope or implementation changed")
    parent = identified(verified(root, cfg["parent_result"]))
    if (
        parent["config_id"] != manifest_identifier(previous)
        or parent["status"] != "blocked_preserving_evidence"
        or parent["verified_pairs"] != 5
        or parent["planned_pairs"] != 12
        or parent["stop"]
        != {"case": "courier-card-restock", "reason": "public_input_or_lifecycle_mismatch"}
        or not all(parent["frozen_checks"].values())
    ):
        raise ValueError("Require the exact preserved five-pass/one-blocked/six-missing result")
    check_sources(root, cfg["game_source_evidence"])
    for expected, ref in zip(previous["cases"][6:], cfg["native_imports"], strict=True):
        row = identified(verified(root, ref))
        if row["status"] != "verified" or row["case"] != expected:
            raise ValueError("The unstarted official counterpart has a different native control")
    adapter(root, cfg)
    return cfg


def context(root: Path) -> dict[str, Any]:
    cfg = load(root)
    ctx = parent_context(root)
    built = adapter(root, cfg)
    if ctx["lifecycle_adapter"] != built["original_lifecycle_adapter"]:
        raise ValueError("The original lifecycle adapter changed")
    return {**ctx, "lifecycle_adapter": built["adapter"]}
