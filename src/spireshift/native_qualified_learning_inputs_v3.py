"""Resume the exact study with one excluded verifier failure and unchanged learning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_qualified_learning_inputs_v2 import RECIPE as _PARENT
from spireshift.native_qualified_learning_inputs_v2 import context as context
from spireshift.native_qualified_learning_inputs_v2 import load as load_parent
from spireshift.native_qualified_learning_recovery_v1 import FAILED, STATUS

PARENT = _PARENT
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-qualified-model-only-v3.json"
MODULE = "spireshift.native_qualified_learning_session_v3"
SCHEMA = "native-a8-qualified-model-only-v3"


def implementation(root: Path) -> dict[str, str]:
    parent = json.loads((root / PARENT).read_text())
    names = {
        *parent["implementation"],
        PARENT,
        "scripts/continue-a8-qualified-model-only-v3.sh",
        "scripts/engine-card-answer-verify-v2.mjs",
        "scripts/engine-card-answer-verify-v2.test.mjs",
        "tests/unit/test_native_qualified_learning_v3.py",
        "src/spireshift/native_qualified_learning_inputs_v3.py",
        "src/spireshift/native_qualified_learning_session_v3.py",
        "src/spireshift/native_qualified_learning_verification_v2.py",
        "src/spireshift/native_qualified_learning_worker_v2.py",
        "src/spireshift/native_qualified_learning_recovery_v1.py",
    }
    return {name: _sha_file(root / name) for name in sorted(names)}


def assessment(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    result = identified(verified(root, cfg["source_assessment"]))
    check_sources(root, result["sources"])
    parent = json.loads((root / PARENT).read_text())
    chunks = root / parent["workspace"] / "chunks"
    if {path.name for path in chunks.iterdir() if path.is_dir()} != {
        *result["inherited_units"],
        FAILED,
    } or result["parent_config_id"] != manifest_identifier(parent):
        raise ValueError("The predecessor has missing or newly started units; never replay worlds")
    if (
        result["status"] != STATUS
        or result["sealed_training_games"] != 1146
        or len(result["inherited_units"]) != 1217
        or result["inherited_optimizer_updates"] != 3813
        or result["unstarted_training_games"] != 901
        or result["development_games_started"] != 0
        or result["failed_request"]["task"]["key"] != FAILED
        or result["failed_game_diagnostic"]["training_admitted"] is not False
        or not all(result["frozen_checks"].values())
    ):
        raise ValueError("Require the exact saved prefix, full Adam lineage and preserved failure")
    return result


def load(root: Path) -> dict[str, Any]:
    parent = load_parent(root)
    control = identified(root / parent["control_workspace"] / "report.json")
    if control["status"] != "qualified_model_only_collect_fit_reload_verified" or control[
        "config_id"
    ] != manifest_identifier({**parent, "workspace": parent["control_workspace"]}):
        raise ValueError("Require the unchanged parent collect/fit/reload control")
    check_sources(root, control["sources"])
    cfg: dict[str, Any] = json.loads((root / RECIPE).read_text())
    changes = {
        "schema_version",
        "workspace",
        "implementation",
        "source_assessment",
        "excluded_training_units",
        "continuation_scope",
    }
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["workspace"] != "artifacts/native-qualified-learning/study-v3"
        or cfg["implementation"] != implementation(root)
        or cfg["excluded_training_units"] != [FAILED]
        or cfg["continuation_scope"]
        != (
            "reuse_1217_clean_units_exclude_one_failed_cell_"
            "run_only_901_unstarted_training_and_128_development_games"
        )
        or {k: v for k, v in cfg.items() if k not in changes}
        != {k: v for k, v in parent.items() if k not in changes}
    ):
        raise ValueError("The continuation changed gameplay, learning, seeds or fixed evaluation")
    check_sources(root, cfg["implementation"])
    assessment(root, cfg)
    return cfg
