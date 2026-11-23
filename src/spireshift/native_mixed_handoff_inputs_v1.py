"""Frozen scope for potion replacement, restocking and mixed rest handoffs."""

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
from spireshift.native_selector_paired_v5 import context as context

RECIPE = "configs/native-compatibility/sts2-v0.111.0-a8-mixed-handoffs-v1.json"
SCRIPT = "engine-mixed-handoffs-worker-v1.mjs"
SCHEMA = "native-a8-mixed-handoffs-v1"
MODULE = "spireshift.native_mixed_handoff_session_v1"
PARENT = "configs/native-compatibility/sts2-v0.111.0-a8-official-selectors-v6.json"
LIMITS = {
    "wall_seconds": 1800,
    "cpu_seconds": 3600,
    "storage_bytes": 1_000_000_000,
    "resident_memory_bytes": 4_000_000_000,
}
SHORT_LIMITS = {**LIMITS, "wall_seconds": 270, "cpu_seconds": 600}


def cases() -> list[dict[str, Any]]:
    deck = ["STRIKE_IRONCLAD", "DEFEND_IRONCLAD", "BASH"]
    belt = ["BLOOD_POTION", "FOUL_POTION"]
    brew = ["ENTROPIC_BREW", "FOUL_POTION"]
    tent = ["MINIATURE_TENT", "REGAL_PILLOW"]
    rows: list[dict[str, Any]] = [
        dict(key="reward-discard-left", family="reward", replacement="discard", slot=0, take=True),
        dict(key="courier-potion-restock", family="shop", operation="potion", courier=True),
        dict(
            key="rest-brew-smith-lift-return",
            family="rest",
            operation="return",
            relics=[*tent, "GIRYA"],
            girya=2,
            second_rest=True,
            belt=brew,
        ),
        dict(
            key="reward-discard-right", family="reward", replacement="discard", slot=1, take=False
        ),
        dict(key="reward-use-replace", family="reward", replacement="use", slot=0, take=False),
        dict(key="courier-card-restock", family="shop", operation="card", courier=True),
        dict(key="ordinary-potion-stock", family="shop", operation="potion", courier=False),
        dict(
            key="courier-relic-child",
            family="shop",
            operation="relic",
            courier=True,
            kifuda=True,
            deck=(deck * 5)[:13],
        ),
        dict(
            key="rest-cook-brew",
            family="rest",
            operation="cook",
            relics=[*tent, "MEAT_CLEAVER"],
            deck=["STRIKE_IRONCLAD", "DEFEND_IRONCLAD", "ASCENDERS_BANE"],
            belt=brew,
        ),
        dict(
            key="rest-no-tent-brew",
            family="rest",
            operation="single",
            relics=["REGAL_PILLOW"],
            belt=brew,
        ),
        dict(
            key="rest-pillow-cap",
            family="rest",
            operation="cap",
            relics=[*tent, "SHOVEL"],
            hp=77,
            belt=brew,
        ),
        dict(
            key="rest-spent-girya-brew",
            family="rest",
            operation="spent",
            relics=[*tent, "GIRYA"],
            girya=3,
            deck=["ASCENDERS_BANE"],
            belt=brew,
        ),
    ]
    return [
        {
            "seed": f"SP1RESH1FTA8MHC{i:03}",
            "hp": 31,
            "deck": deck,
            "belt": belt,
            "relics": ["THE_COURIER"] if row.get("courier") else [],
            **row,
        }
        for i, row in enumerate(rows, 1)
    ]


def implementation(root: Path) -> dict[str, str]:
    previous = json.loads((root / PARENT).read_text())["implementation"]
    names = {
        *previous,
        PARENT,
        "scripts/check-mixed-handoffs-v1.sh",
        *(
            f"src/spireshift/native_mixed_handoff_{name}_v1.py"
            for name in ("inputs", "worker", "checks", "cases", "session")
        ),
    }
    names.update(f"scripts/{name}" for name in worker_helpers(root, SCRIPT))
    return {name: _sha_file(root / name) for name in sorted(names)}


def load(root: Path) -> dict[str, Any]:
    cfg: dict[str, Any] = json.loads((root / RECIPE).read_text())
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["cases"] != cases()
        or cfg["implementation"] != implementation(root)
        or cfg["short_case_keys"] != [row["key"] for row in cases()[:3]]
        or cfg["training_allowed"] is not False
        or cfg["optimizer_updates"] != 0
        or cfg["limits"] != LIMITS
        or cfg["short_limits"] != SHORT_LIMITS
    ):
        raise ValueError("The mixed handoff scope or pinned implementation changed")
    parent = identified(verified(root, cfg["selector_assessment"]))
    if (
        parent["status"] != "six_current_selector_mechanisms_verified"
        or parent["verified_mechanisms"] != 6
    ):
        raise ValueError("Require the exact current six-selector saved assessment")
    check_sources(root, cfg["game_source_evidence"])
    if parent["report_id"] != cfg["selector_assessment_id"]:
        raise ValueError("The selector baseline identity changed")
    if (
        manifest_identifier(json.loads((root / PARENT).read_text()))
        != cfg["selector_parent_config_id"]
    ):
        raise ValueError("The qualified selector adapter declaration changed")
    return cfg
