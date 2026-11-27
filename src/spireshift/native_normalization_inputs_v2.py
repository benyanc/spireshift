"""Continue only unstarted normalization cells after exact native deferral checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_deferred_potion_control_v1 import STATUS as CONTROL
from spireshift.native_deferred_potions_v1 import with_adapter
from spireshift.native_normalization_inputs_v1 import RECIPE as PARENT
from spireshift.native_normalization_inputs_v1 import context as original_context
from spireshift.native_normalization_inputs_v1 import load as load_parent
from spireshift.native_normalization_recovery_v1 import FAILED, STATUS

RECIPE = "configs/native-learning/sts2-v0.111.0-a8-hidden-normalization-v2.json"
MODULE = "spireshift.native_normalization_session_v2"
SCHEMA = "native-a8-hidden-normalization-v2"


def implementation(root: Path) -> dict[str, str]:
    names = {
        *json.loads((root / PARENT).read_text())["implementation"],
        PARENT,
        "src/spireshift/native_normalization_recovery_v1.py",
        "src/spireshift/native_deferred_potions_v1.py",
        "src/spireshift/native_deferred_potion_control_v1.py",
        "src/spireshift/native_deferred_potion_smoke_v1.py",
        "src/spireshift/native_normalization_inputs_v2.py",
        "src/spireshift/native_normalization_session_v2.py",
        "src/spireshift/native_normalization_restore_v2.py",
        "src/spireshift/native_sealed_continuation_v1.py",
        "scripts/engine-deferred-potion-control-v1.mjs",
        "scripts/continue-a8-hidden-normalization-v2.sh",
        "tests/unit/test_native_deferred_potions_v1.py",
        "tests/unit/test_native_normalization_continuation_v2.py",
        *(
            str(p.relative_to(root))
            for p in (root / "mod/SpireShift.HeadlessDeferredPotions").glob("*.*")
        ),
    }
    return {name: _sha_file(root / name) for name in sorted(names)}


def assessment(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    proof = identified(verified(root, cfg["prefix_assessment"]))
    check_sources(root, proof["sources"])
    if (
        proof["status"] != STATUS
        or proof["sealed_training_games"] != 3984
        or proof["sealed_fits"] != 249
        or proof["inherited_optimizer_updates"] != 15252
        or len(proof["inherited_units"]) != 4234
        or proof["failed_request"]["task"]["key"] != FAILED
        or proof["failed_game"]["training_admitted"] is not False
        or len(proof["capped_training_units"]) != 1
        or proof["unstarted_training_games"] != 111
        or proof["unstarted_development_games"] != 768
        or not all(proof["frozen_checks"].values())
    ):
        raise ValueError("Require the exact source prefix, full Adam and preserved failure")
    return proof


def load(root: Path) -> dict[str, Any]:
    parent = load_parent(root)
    decl: dict[str, Any] = json.loads((root / RECIPE).read_text())
    if (
        set(decl)
        != {
            "schema_version",
            "workspace",
            "parent_recipe",
            "implementation",
            "prefix_assessment",
            "deferred_controls",
            "production_controls",
            "excluded_training_units",
        }
        or decl["schema_version"] != SCHEMA
        or decl["workspace"] != "artifacts/native-hidden-normalization/study-v2"
        or verified(root, decl["parent_recipe"]) != root / PARENT
        or decl["implementation"] != implementation(root)
        or decl["excluded_training_units"] != [FAILED]
    ):
        raise ValueError("The normalization continuation scope changed")
    check_sources(root, decl["implementation"])
    cfg = {**parent, **decl}
    proof = assessment(root, cfg)
    if proof["parent_config_id"] != manifest_identifier(parent):
        raise ValueError("The frozen source study declaration changed")
    if {p.name for p in (root / parent["workspace"] / "chunks").iterdir()} != {
        *proof["inherited_units"],
        FAILED,
    }:
        raise ValueError("Historical attempts changed; never replay or erase them")
    adapter = with_adapter(root, original_context(root, parent))["lifecycle_adapter"]
    control = identified(verified(root, decl["deferred_controls"]))
    check_sources(root, control["sources"])
    if (
        control["status"] != CONTROL
        or control["adapter_sha256"] != adapter["sha256"]
        or len(control["legacy_cases"]) != 3
        or len(control["opening_cases"]) != 2
        or control["optimizer_updates"] != 0
        or not all(control["frozen_checks"].values())
    ):
        raise ValueError(
            "Require exact pre-ID acceptance, effects, child handoffs and negative controls"
        )
    production = identified(verified(root, decl["production_controls"]))
    check_sources(root, production["sources"])
    if (
        production["status"] != "deferred_potions_production_learner_controls_verified"
        or production["adapter_sha256"] != adapter["sha256"]
        or len(production["games"]) != 2
        or any(row["outcome"] not in {"win", "loss"} for row in production["games"])
        or production["optimizer_updates"] != 0
        or not all(production["frozen_checks"].values())
    ):
        raise ValueError("Require fresh production learner checks under both correction methods")
    return cfg


def context(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    return with_adapter(root, original_context(root, cfg))
