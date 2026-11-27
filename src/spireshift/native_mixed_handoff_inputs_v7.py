"""Adopt exact verified pairs after a type-only test annotation amendment."""

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

RECIPE = "configs/native-compatibility/sts2-v0.111.0-a8-mixed-handoffs-v7.json"
PARENT = "configs/native-compatibility/sts2-v0.111.0-a8-mixed-handoffs-v6.json"
SCHEMA = "native-a8-mixed-handoffs-v7"
MODULE = "spireshift.native_mixed_handoff_session_v7"
TEST = "tests/unit/test_native_merchant_overlay.py"


def implementation(root: Path) -> dict[str, str]:
    previous = json.loads((root / PARENT).read_text())["implementation"]
    names = {
        *previous,
        PARENT,
        "scripts/check-mixed-handoffs-v7.sh",
        "src/spireshift/native_mixed_handoff_inputs_v7.py",
        "src/spireshift/native_mixed_handoff_session_v7.py",
        "tests/unit/test_native_merchant_overlay_adoption.py",
    }
    return {name: _sha_file(root / name) for name in sorted(names)}


def check_test_amendment(root: Path, cfg: dict[str, Any], parent: dict[str, Any]) -> None:
    original = verified(root, cfg["original_test"])
    if _sha_file(original) != parent["implementation"][TEST]:
        raise ValueError("The original qualification test snapshot changed")
    expected = original.read_text().replace(
        "from typing import cast", "from typing import Any, cast", 1
    )
    expected = expected.replace("    raw = {", "    raw: dict[str, Any] = {", 1)
    if expected == original.read_text() or (root / TEST).read_text() != expected:
        raise ValueError("Only the declared type annotation may differ from the executed scope")
    check_sources(
        root, {name: sha for name, sha in parent["implementation"].items() if name != TEST}
    )


def load(root: Path) -> dict[str, Any]:
    cfg: dict[str, Any] = json.loads((root / RECIPE).read_text())
    parent = json.loads((root / PARENT).read_text())
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["cases"] != parent["cases"]
        or cfg["implementation"] != implementation(root)
        or cfg["limits"] != parent["limits"]
        or cfg["short_limits"] != parent["short_limits"]
        or cfg["short_case_keys"] != parent["short_case_keys"]
        or cfg["training_allowed"] is not False
        or cfg["optimizer_updates"] != 0
    ):
        raise ValueError("The saved-pair adoption scope changed")
    check_test_amendment(root, cfg, parent)
    result = identified(verified(root, cfg["qualified_short_result"]))
    if (
        result["status"] != "short_controls_verified"
        or result["verified_pairs"] != 2
        or result["config_id"] != manifest_identifier(parent)
        or result["stop"] is not None
        or not all(result["frozen_checks"].values())
    ):
        raise ValueError("Require the two exact qualified merchant-map pairs")
    native = identified(verified(root, cfg["qualified_native_controls"]))
    if (
        native["status"] != "native_controls_verified"
        or native["config_id"] != manifest_identifier(parent)
        or [row["case"] for row in native["cases"]] != cfg["cases"]
    ):
        raise ValueError("The verified native continuation controls changed")
    check_sources(root, native["sources"])
    check_sources(root, cfg["game_source_evidence"])
    adapter(root, cfg)
    return cfg


def context(root: Path) -> dict[str, Any]:
    cfg = load(root)
    ctx = parent_context(root)
    built = adapter(root, cfg)
    if ctx["lifecycle_adapter"] != built["original_lifecycle_adapter"]:
        raise ValueError("The original lifecycle source changed")
    return {**ctx, "lifecycle_adapter": built["adapter"]}
