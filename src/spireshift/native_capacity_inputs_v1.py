"""One changed model capacity, fixed model-owned learning and fresh A8 comparisons."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_combat_intent_model import load as load_state
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_qualified_learning_inputs_v4 import RECIPE as PARENT
from spireshift.native_qualified_learning_inputs_v4 import context as context
from spireshift.native_qualified_learning_inputs_v4 import load as load_parent
from spireshift.native_qualified_learning_result_v1 import STATUS

RECIPE = "configs/native-learning/sts2-v0.111.0-a8-policy-capacity-v1.json"
MODULE = "spireshift.native_capacity_session_v1"
SCHEMA = "native-a8-policy-capacity-v1"
METHODS = ("standard", "expanded")
EVALUATION = ("reference", *METHODS)
LIMITS = {
    "wall_seconds": 172_800,
    "cpu_seconds": 172_800,
    "storage_bytes": 24_000_000_000,
    "resident_memory_bytes": 4_000_000_000,
}
CONTROL_LIMITS = {
    "wall_seconds": 295,
    "cpu_seconds": 900,
    "storage_bytes": 2_000_000_000,
    "resident_memory_bytes": 4_000_000_000,
}


def plan() -> dict[str, Any]:
    return {
        "rounds": 64,
        "worlds_per_round": 16,
        "initializers": [2, 3],
        "control_worlds": 2,
        "control_updates_per_copy": 2,
        "minimum_terminal_training_worlds": 12,
        "development_worlds": 128,
        "training": [f"SP1RESH1FTA8CP1T{i:04d}" for i in range(1, 1025)],
        "development": [f"SP1RESH1FTA8CP1E{i:03d}" for i in range(1, 129)],
        "control": ["SP1RESH1FTA8CP1C001", "SP1RESH1FTA8CP1C002"],
        "reload": ["SP1RESH1FTA8CP1R001"],
        "final_selection": "fixed_round_64_for_each_method_before_development",
        "training_starts": "fresh_normal_starts_only",
        "replay_imitation_labels": False,
        "evaluation_methods": list(EVALUATION),
        "matched_optimizer_work_claimed": False,
    }


def implementation(root: Path) -> dict[str, str]:
    parent = json.loads((root / PARENT).read_text())
    names = {
        *parent["implementation"],
        PARENT,
        "src/spireshift/native_qualified_learning_result_v1.py",
        "tests/unit/test_native_qualified_learning_result_v1.py",
        "src/spireshift/native_policy_capacity_v1.py",
        "tests/unit/test_native_policy_capacity_v1.py",
        "src/spireshift/native_capacity_inputs_v1.py",
        "src/spireshift/native_capacity_control_v1.py",
        "src/spireshift/native_capacity_session_v1.py",
        "tests/unit/test_native_capacity_study_v1.py",
        "scripts/compare-a8-policy-capacity-v1.sh",
    }
    return {name: _sha_file(root / name) for name in sorted(names)}


def load(root: Path) -> dict[str, Any]:
    parent = load_parent(root)
    declaration: dict[str, Any] = json.loads((root / RECIPE).read_text())
    if (
        set(declaration)
        != {
            "schema_version",
            "workspace",
            "control_workspace",
            "parent_recipe",
            "implementation",
            "source_assessment",
            "starting_states",
            "plan",
            "limits",
            "control_limits",
            "initialization",
        }
        or declaration["schema_version"] != SCHEMA
        or verified(root, declaration["parent_recipe"]) != root / PARENT
        or declaration["workspace"] != "artifacts/native-policy-capacity/study-v1"
        or declaration["control_workspace"] != "artifacts/native-policy-capacity/control-v1"
        or declaration["implementation"] != implementation(root)
        or declaration["plan"] != plan()
        or declaration["limits"] != LIMITS
        or declaration["control_limits"] != CONTROL_LIMITS
        or declaration["initialization"]
        != {
            "standard_hidden_units": 32,
            "expanded_hidden_units": 128,
            "expansion_seeds": {"2": 721002, "3": 721003},
            "new_output_weights": 0.0,
            "new_Adam_moments": 0.0,
            "inherited_weights_and_Adam_exact": True,
            "critic_and_input_encoding": "unchanged",
        }
    ):
        raise ValueError("The declared capacity-only comparison changed")
    check_sources(root, declaration["implementation"])
    result = identified(verified(root, declaration["source_assessment"]))
    if (
        result["status"] != STATUS
        or result["development_games_verified"] != 128
        or result["optimizer_updates_on_copies"] != 7101
        or not all(result["frozen_checks"].values())
    ):
        raise ValueError("Require the independently assessed completed A8 study")
    check_sources(root, result["sources"])
    for p in (2, 3):
        state, state_id = load_state(verified(root, declaration["starting_states"][str(p)]))
        if (
            state_id != result["final_states"][str(p)]
            or state.model.actor.hidden_units != 32
            or state.model.arm != "shared"
        ):
            raise ValueError(
                "Both methods must start from the exact frozen round-64 final/full Adam"
            )
    groups = [set(plan()[k]) for k in ("training", "development", "control", "reload")]
    old = set().union(
        *(parent["plan"][k] for k in ("training", "development", "control", "reload"))
    )
    if len(set.union(*groups)) != sum(map(len, groups)) or not set.union(*groups).isdisjoint(old):
        raise ValueError("The new training, control and development worlds must remain disjoint")
    return {**parent, **declaration}
