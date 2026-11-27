"""Inherit the fixed study unchanged and require actual absent-ledger normal-start controls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_qualified_learning_inputs_v3 import RECIPE as _PARENT
from spireshift.native_qualified_learning_inputs_v3 import context as context
from spireshift.native_qualified_learning_readiness_v2 import EXCLUDED
from spireshift.native_qualified_learning_readiness_v2 import RECIPE as READINESS
from spireshift.native_qualified_learning_readiness_v2 import load as load_readiness

PARENT = _PARENT
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-qualified-model-only-v4.json"
MODULE = "spireshift.native_qualified_learning_session_v4"
SCHEMA = "native-a8-qualified-model-only-v4"
SCOPE = (
    "reuse_1217_units_exclude_two_failed_cells_"
    "only_900_unstarted_training_and_128_development_games"
)


def implementation(root: Path) -> dict[str, str]:
    ready = json.loads((root / READINESS).read_text())
    names = {
        *ready["implementation"],
        READINESS,
        "src/spireshift/native_qualified_learning_inputs_v4.py",
        "src/spireshift/native_qualified_learning_session_v4.py",
        "src/spireshift/native_qualified_learning_resume_check_v4.py",
        "scripts/continue-a8-qualified-model-only-v4.sh",
        "tests/unit/test_native_qualified_learning_v4.py",
    }
    return {name: _sha_file(root / name) for name in sorted(names)}


def assessment(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    result = identified(verified(root, cfg["source_assessment"]))
    check_sources(root, result["sources"])
    if (
        result["status"] != "saved_present_and_absent_cursor_cases_verified"
        or result["sealed_training_games"] != 1146
        or len(result["inherited_units"]) != 1217
        or result["inherited_optimizer_updates"] != 3813
        or set(result["excluded_training_requests"]) != set(EXCLUDED)
        or result["preserved_failed_training_games"] != 2
        or result["unstarted_training_games"] != 900
        or result["development_games_started"] != 0
        or any(r["training_admitted"] for r in result["diagnostic_cells"].values())
    ):
        raise ValueError("The saved continuation prefix, exclusions or update lineage changed")
    return result


def load(root: Path) -> dict[str, Any]:
    ready, parent, before = load_readiness(root)
    declaration: dict[str, Any] = json.loads((root / RECIPE).read_text())
    if (
        set(declaration)
        != {
            "schema_version",
            "workspace",
            "parent_recipe",
            "implementation",
            "source_assessment",
            "verifier_controls",
            "excluded_training_units",
            "continuation_scope",
            "resume_check_workspace",
        }
        or declaration["schema_version"] != SCHEMA
        or declaration["workspace"] != "artifacts/native-qualified-learning/study-v4"
        or declaration["resume_check_workspace"]
        != "artifacts/native-qualified-learning/resume-check-v4"
        or verified(root, declaration["parent_recipe"]) != root / PARENT
        or declaration["implementation"] != implementation(root)
        or declaration["excluded_training_units"] != list(EXCLUDED)
        or declaration["continuation_scope"] != SCOPE
    ):
        raise ValueError(
            "The continuation may only change the checker and explicit saved exclusions"
        )
    check_sources(root, declaration["implementation"])
    cfg = {**parent, **declaration}
    proof = assessment(root, cfg)
    if (
        proof["inherited_units"] != before["inherited_units"]
        or proof["base_assessment_id"] != before["report_id"]
        or proof["parent_config_id"] != manifest_identifier(parent)
    ):
        raise ValueError(
            "All inherited games and fits must remain exactly bound to their predecessor"
        )
    control = identified(verified(root, declaration["verifier_controls"]))
    check_sources(root, control["sources"])
    if (
        control["status"] != "saved_and_fresh_normal_start_verifier_controls_passed"
        or control["config_id"] != manifest_identifier(ready)
        or control["saved_assessment_id"] != proof["report_id"]
        or len(control["controls"]) != 2
        or control["optimizer_updates"] != 0
        or not all(control["frozen_checks"].values())
        or not any(not r["selection_cursor_present"] for r in control["controls"])
    ):
        raise ValueError("Require the passing exact fresh normal-start verifier controls")
    return cfg
