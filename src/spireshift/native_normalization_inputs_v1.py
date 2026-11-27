"""A matched conditioning test on fresh, model-owned normal-start A8 games."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_capacity_inputs_v1 import CONTROL_LIMITS, LIMITS
from spireshift.native_capacity_inputs_v2 import RECIPE as PARENT
from spireshift.native_capacity_inputs_v2 import context as context
from spireshift.native_capacity_inputs_v2 import load as load_parent
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_learning_health_result_v1 import STATUS as AUDIT_STATUS
from spireshift.native_normalized_actor_v1 import EPSILON, METHODS
from spireshift.native_normalized_actor_v1 import load as load_state

RECIPE = "configs/native-learning/sts2-v0.111.0-a8-hidden-normalization-v1.json"
MODULE = "spireshift.native_normalization_session_v1"
SCHEMA = "native-a8-hidden-normalization-v1"
EVALUATION = ("reference", *METHODS)
INHERITED = (
    "environment_id",
    "training_score_id",
    "objective",
    "game_limits",
    "credit",
    "settings",
    "mixed_assessment",
    "lifecycle_result",
)


def plan() -> dict[str, Any]:
    return {
        "rounds": 64,
        "worlds_per_round": 16,
        "initializers": [2, 3],
        "control_worlds": 2,
        "control_updates_per_copy": 2,
        "minimum_terminal_training_worlds": 12,
        "development_worlds": 128,
        "training": [f"SP1RESH1FTA8N1T{i:04d}" for i in range(1, 1025)],
        "development": [f"SP1RESH1FTA8N1E{i:03d}" for i in range(1, 129)],
        "control": ["SP1RESH1FTA8N1C001", "SP1RESH1FTA8N1C002"],
        "reload": ["SP1RESH1FTA8N1R001"],
        "final_selection": "fixed_round_64_for_each_method_before_development",
        "training_starts": "fresh_normal_starts_only",
        "replay_imitation_labels": False,
        "evaluation_methods": list(EVALUATION),
        "matched_optimizer_work_claimed": False,
        "inherited_training_units": 0,
        "geometry_samples_per_world": 4,
        "primary_endpoint": "genuine_full_run_native_victory",
    }


def initialization() -> dict[str, Any]:
    return {
        "reference_actor": "exact_frozen_pre_capacity_round_64_shared_actor",
        "reference_actor_trainable": False,
        "correction_hidden_units": 32,
        "methods": list(METHODS),
        "correction_seeds": {"2": 251102, "3": 251103},
        "correction_output_and_linear_weights": 0.0,
        "correction_Adam_moments_and_clock": 0,
        "critic_weights_and_full_Adam": "exact_source_copy_then_trainable",
        "initial_logits": "exact_source_for_both_methods",
        "normalization_axis": "hidden_units_within_each_candidate",
        "normalization_epsilon": EPSILON,
        "learned_gain_or_bias_after_normalization": False,
        "normalization_training_and_inference": "identical",
        "correction_logit_bound": None,
        "action_families": "all_legal_actions_model_owned",
        "objective_credit_and_PPO": "unchanged",
    }


def implementation(root: Path) -> dict[str, str]:
    names = {
        *json.loads((root / PARENT).read_text())["implementation"],
        PARENT,
        "src/spireshift/native_learning_health_result_v1.py",
        "src/spireshift/native_normalized_actor_v1.py",
        "src/spireshift/native_normalization_inputs_v1.py",
        "src/spireshift/native_normalization_fit_v1.py",
        "src/spireshift/native_normalization_session_v1.py",
        "tests/unit/test_native_normalized_actor_v1.py",
        "tests/unit/test_native_normalization_study_v1.py",
        "scripts/compare-a8-hidden-normalization-v1.sh",
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
        or declaration["workspace"] != "artifacts/native-hidden-normalization/study-v1"
        or declaration["control_workspace"] != "artifacts/native-hidden-normalization/control-v1"
        or declaration["implementation"] != implementation(root)
        or declaration["plan"] != plan()
        or declaration["limits"] != LIMITS
        or declaration["control_limits"] != CONTROL_LIMITS
        or declaration["initialization"] != initialization()
        or declaration["starting_states"] != parent["starting_states"]
    ):
        raise ValueError("The matched raw/normalized scoring correction declaration changed")
    check_sources(root, declaration["implementation"])
    audit = identified(verified(root, declaration["source_assessment"]))
    check_sources(root, audit["sources"])
    if (
        audit["status"] != AUDIT_STATUS
        or audit["cohorts_verified"] != 16
        or audit["source_training_games"] != 256
        or audit["numerical_gradient_probes_passed"] != 64
        or audit["source_optimizer_updates"] != 0
        or audit["new_games"] != 0
        or not all(audit["frozen_checks"].values())
    ):
        raise ValueError("Require the completed saved credit and numerical learner assessment")
    for p in (2, 3):
        state, _ = load_state(verified(root, declaration["starting_states"][str(p)]))
        if state.model.actor.hidden_units != 32 or state.model.arm != "shared":
            raise ValueError("Require the exact two plain frozen shared source finals/full Adam")
    groups = [set(plan()[k]) for k in ("training", "development", "control", "reload")]
    old = set().union(
        *(parent["plan"][k] for k in ("training", "development", "control", "reload"))
    )
    if len(set.union(*groups)) != sum(map(len, groups)) or not set.union(*groups).isdisjoint(old):
        raise ValueError("The fresh training, development and control partitions must be disjoint")
    return {**{k: parent[k] for k in INHERITED}, **declaration}
