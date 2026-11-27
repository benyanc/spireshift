"""Preserve the short-control stop and reuse only its complete collection/fit seals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_combat_intent_model import load as load_state
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_qualified_learning_inputs_v1 import CONTROL_LIMITS, LIMITS, plan
from spireshift.native_qualified_learning_inputs_v1 import context as context

RECIPE = "configs/native-learning/sts2-v0.111.0-a8-qualified-model-only-v2.json"
PARENT = "configs/native-learning/sts2-v0.111.0-a8-qualified-model-only-v1.json"
MODULE = "spireshift.native_qualified_learning_session_v2"
SCHEMA = "native-a8-qualified-model-only-v2"
IMPORTS = tuple(
    key
    for p in (2, 3)
    for key in (*(f"control-{i:04d}-p{p}-learner" for i in (1, 2, 3)), f"fit-p{p}-r001")
)


def implementation(root: Path) -> dict[str, str]:
    previous = json.loads((root / PARENT).read_text())["implementation"]
    names = {
        *previous,
        PARENT,
        "scripts/train-a8-qualified-model-only-v2.sh",
        "src/spireshift/native_qualified_learning_inputs_v2.py",
        "src/spireshift/native_qualified_learning_session_v2.py",
        "tests/unit/test_native_qualified_learning_v2.py",
    }
    return {name: _sha_file(root / name) for name in sorted(names)}


def load(root: Path) -> dict[str, Any]:
    cfg: dict[str, Any] = json.loads((root / RECIPE).read_text())
    parent = json.loads((root / PARENT).read_text())
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["plan"] != plan()
        or cfg["limits"] != LIMITS
        or cfg["control_limits"] != CONTROL_LIMITS
        or cfg["implementation"] != implementation(root)
        or cfg["adopted_control_units"] != list(IMPORTS)
    ):
        raise ValueError("The short-control recovery scope changed")
    for key in (
        "objective",
        "game_limits",
        "settings",
        "credit",
        "training_score_id",
        "starting_states",
        "mixed_assessment",
        "lifecycle_result",
        "environment_id",
    ):
        if cfg[key] != parent[key]:
            raise ValueError("The continuation changed a gameplay, model or learning input")
    check_sources(root, parent["implementation"])
    result = identified(verified(root, cfg["source_control_stop"]))
    if (
        result["schema_version"] != "native-a8-qualified-model-only-v1"
        or result["config_id"]
        != manifest_identifier({**parent, "workspace": parent["control_workspace"]})
        or result["status"] != "stopped_preserving_evidence"
        or result["stop"]
        != {"unit": "reload_control-0001-p2-learner", "error": "ValueError: Invalid chunk key"}
        or set(result["chunk_seals"]) != set(IMPORTS)
        or result["optimizer_updates_on_copies"] != 4
        or not all(result["frozen_checks"].values())
    ):
        raise ValueError("Require the exact pre-reload bookkeeping stop and its eight clean seals")
    check_sources(root, result["sources"])
    verified(root, cfg["mixed_assessment"])
    verified(root, cfg["lifecycle_result"])
    for p in (2, 3):
        state, state_id = load_state(verified(root, cfg["starting_states"][str(p)]))
        if state_id != result["starting_states"][str(p)] or state.model.arm != "shared":
            raise ValueError("The protected starting copy or its full Adam changed")
    old = root / parent["control_workspace"]
    if any((old / "chunks" / f"reload_control-0001-p{p}-learner").exists() for p in (2, 3)):
        raise ValueError("A reload game was already started; preserve it without replay")
    if (root / parent["workspace"] / "chunks").exists():
        raise ValueError("The predecessor full study must remain unstarted")
    for name in ("training", "development", "control", "reload"):
        if cfg["plan"][name] != parent["plan"][name]:
            raise ValueError("Preserve the exact unstarted training and evaluation worlds")
    return cfg
