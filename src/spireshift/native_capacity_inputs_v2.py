"""Continue the fixed capacity experiment after a source-grounded potion queue repair."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_capacity_inputs_v1 import RECIPE as PARENT
from spireshift.native_capacity_inputs_v1 import context as original_context
from spireshift.native_capacity_inputs_v1 import load as load_parent
from spireshift.native_capacity_recovery_v1 import FAILED, STATUS
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_potion_queue_control_v1 import STATUS as CONTROL
from spireshift.native_potion_queue_smoke_v1 import STATUS as PRODUCTION_CONTROL
from spireshift.native_potion_queue_v1 import with_adapter

RECIPE = "configs/native-learning/sts2-v0.111.0-a8-policy-capacity-v2.json"
MODULE = "spireshift.native_capacity_session_v2"
SCHEMA = "native-a8-policy-capacity-v2"


def implementation(root: Path) -> dict[str, str]:
    names = {
        *json.loads((root / PARENT).read_text())["implementation"],
        PARENT,
        "src/spireshift/native_capacity_recovery_v1.py",
        "src/spireshift/native_potion_queue_v1.py",
        "src/spireshift/native_potion_queue_control_v1.py",
        "src/spireshift/native_capacity_inputs_v2.py",
        "src/spireshift/native_capacity_session_v2.py",
        "src/spireshift/native_capacity_resume_check_v2.py",
        "src/spireshift/native_potion_queue_smoke_v1.py",
        "scripts/engine-potion-queue-control-v2.mjs",
        "scripts/continue-a8-policy-capacity-v2.sh",
        "tests/unit/test_native_capacity_recovery_v1.py",
        "tests/unit/test_native_potion_queue_v1.py",
        *(
            str(p.relative_to(root))
            for p in (root / "mod/SpireShift.HeadlessPotionQueue").glob("*.*")
        ),
    }
    return {name: _sha_file(root / name) for name in sorted(names)}


def assessment(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    result = identified(verified(root, cfg["prefix_assessment"]))
    check_sources(root, result["sources"])
    if (
        result["status"] != STATUS
        or result["sealed_training_games"] != 633
        or result["sealed_fits"] != 39
        or len(result["inherited_units"]) != 673
        or result["inherited_optimizer_updates"] != 2429
        or result["failed_request"]["task"]["key"] != FAILED
        or result["failed_game"]["training_admitted"] is not False
        or result["unstarted_training_games"] != 3462
        or result["unstarted_development_games"] != 768
        or not all(result["frozen_checks"].values())
    ):
        raise ValueError(
            "Require the exact sealed capacity prefix, failure and complete Adam lineages"
        )
    return result


def load(root: Path) -> dict[str, Any]:
    parent = load_parent(root)
    declaration: dict[str, Any] = json.loads((root / RECIPE).read_text())
    if (
        set(declaration)
        != {
            "schema_version",
            "workspace",
            "parent_recipe",
            "implementation",
            "prefix_assessment",
            "queue_controls",
            "production_controls",
            "excluded_training_units",
        }
        or declaration["schema_version"] != SCHEMA
        or declaration["workspace"] != "artifacts/native-policy-capacity/study-v2"
        or verified(root, declaration["parent_recipe"]) != root / PARENT
        or declaration["implementation"] != implementation(root)
        or declaration["excluded_training_units"] != [FAILED]
    ):
        raise ValueError("The capacity continuation scope changed")
    check_sources(root, declaration["implementation"])
    cfg = {**parent, **declaration}
    proof = assessment(root, cfg)
    if proof["parent_config_id"] != manifest_identifier(parent):
        raise ValueError("The sealed predecessor experiment changed")
    old = root / parent["workspace"] / "chunks"
    if {p.name for p in old.iterdir()} != {*proof["inherited_units"], FAILED}:
        raise ValueError("Historical units changed; never replay or erase failed work")
    control = identified(verified(root, declaration["queue_controls"]))
    check_sources(root, control["sources"])
    adapter = with_adapter(root, original_context(root, cfg))["lifecycle_adapter"]
    if (
        control["status"] != CONTROL
        or [r["case"] for r in control["cases"]]
        != ["player-choice", "end-turn-choice", "noncombat"]
        or control["adapter_sha256"] != adapter["sha256"]
        or not all(control["frozen_checks"].values())
        or control["optimizer_updates"] != 0
    ):
        raise ValueError(
            "Require actual potion effects, queued-child handoffs and pre-enqueue rejection"
        )
    production = identified(verified(root, declaration["production_controls"]))
    check_sources(root, production["sources"])
    if (
        production["status"] != PRODUCTION_CONTROL
        or production["adapter_sha256"] != adapter["sha256"]
        or [row["hidden_units"] for row in production["games"]] != [32, 128]
        or any(row["outcome"] not in {"win", "loss"} for row in production["games"])
        or production["optimizer_updates"] != 0
        or not all(production["frozen_checks"].values())
    ):
        raise ValueError("Require fresh normal-start production controls for both policy widths")
    return cfg


def context(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    return with_adapter(root, original_context(root, cfg))
