"""Versioned inputs for six official/native selector lifecycle controls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_mixed_rest_session
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.native_a8_feedback_session import inputs
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_selector_lifecycle_suite import cases as native_cases
from spireshift.native_selector_lifecycle_suite import load as native_plan
from spireshift.native_selector_paired_worker import SCRIPT

RECIPE = "configs/native-compatibility/sts2-v0.111.0-a8-official-selectors-v1.json"
CONNECTOR = "configs/engine-qualification/sts2-v0.111.0-connector-ordered-answers-v33.json"
SCHEMA = "native-a8-official-selector-comparison-v1"
MODULE = "spireshift.native_selector_paired_session"


def cases() -> list[dict[str, Any]]:
    rows = native_cases()
    ordered = [rows[i] for i in (3, 1, 0, 2, 4, 5)]
    return [{**case, "seed": f"SP1RESH1FTA8PSLC{i:03}"} for i, case in enumerate(ordered, 1)]


def implementation(root: Path) -> dict[str, str]:
    paths = {
        f"src/spireshift/native_selector_paired_{name}.py"
        for name in ("inputs", "worker", "contract", "session")
    }
    paths.update(
        {
            "src/spireshift/native_selector_official_reset.py",
            "src/spireshift/native_systematic_session_v1.py",
            "src/spireshift/native_mixed_rest_session.py",
            "src/spireshift/native_selector_lifecycle_cases.py",
            "src/spireshift/native_selector_lifecycle_checks.py",
            "src/spireshift/native_selector_lifecycle_trace.py",
            "src/spireshift/native_lifecycle_contract.py",
            "src/spireshift/native_lifecycle_worker.py",
            "scripts/compare-official-selectors-v1.sh",
            CONNECTOR,
            "configs/engine-qualification/sts2-v0.111.0-connector-ordered-answers-build-v33.json",
            "patches/engine/sts2-connector-v0.111.0-ordered-answers-v33.patch",
        }
    )
    for script in (SCRIPT, "engine-selector-official-v1.mjs", "engine-shared-input-v17.mjs"):
        paths.update(f"scripts/{name}" for name in worker_helpers(root, script))
    return {name: _sha_file(root / name) for name in sorted(paths)}


def load(root: Path) -> dict[str, Any]:
    cfg: dict[str, Any] = json.loads((root / RECIPE).read_text())
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["cases"] != cases()
        or cfg["implementation"] != implementation(root)
        or cfg["limits"]
        != {
            "wall_seconds": 1200,
            "cpu_seconds": 2400,
            "storage_bytes": 1_000_000_000,
            "resident_memory_bytes": 4_000_000_000,
        }
        or cfg["training_allowed"] is not False
        or any(canonical_seed(case["seed"]) != case["seed"] for case in cfg["cases"])
    ):
        raise ValueError("The frozen paired selector recipe or execution sources changed")
    previous = identified(verified(root, cfg["native_result"]))
    if previous["status"] != "verified" or previous["config_id"] != manifest_identifier(
        native_plan(root)
    ):
        raise ValueError("Require the saved complete native selector suite")
    for case in previous["cases"]:
        check_sources(root, case["sources"])
    return cfg


def context(root: Path) -> dict[str, Any]:
    _, ctx, *_ = inputs(root)
    native_config = ctx["config"]
    with patch.object(native_mixed_rest_session, "CONNECTOR", CONNECTOR):
        ctx = native_mixed_rest_session.official_context(ctx)
    # Reuse the already reproduced cleanup adapter without rebuilding old evidence.
    parent = identified(verified(root, native_plan(root)["parent_result"]))
    adapter = parent["adapter"]
    if _sha_file(Path(adapter["path"])) != adapter["sha256"]:
        raise ValueError("The qualified native cleanup adapter changed")
    return {**ctx, "config": native_config, "lifecycle_adapter": adapter}
