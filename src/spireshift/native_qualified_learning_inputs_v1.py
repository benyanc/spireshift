"""Bind a sustained model-only learner to exact mixed lifecycle and input evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.native_a8_head_study import SOURCES
from spireshift.native_combat_intent_model import load as load_state
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_mixed_handoff_inputs_v7 import context as qualified_context
from spireshift.native_qualified_learning_worker_v1 import SCRIPT

RECIPE = "configs/native-learning/sts2-v0.111.0-a8-qualified-model-only-v1.json"
MODULE = "spireshift.native_qualified_learning_session_v1"
SCHEMA = "native-a8-qualified-model-only-v1"
PPO_PARENT = "configs/native-learning/sts2-v0.111.0-a8-scoring-heads-v1.json"
MIXED = "configs/native-compatibility/sts2-v0.111.0-a8-mixed-handoffs-v7.json"
LIMITS = {
    "wall_seconds": 86_400,
    "cpu_seconds": 86_400,
    "storage_bytes": 24_000_000_000,
    "resident_memory_bytes": 4_000_000_000,
}
CONTROL_LIMITS = {**LIMITS, "wall_seconds": 275, "cpu_seconds": 600, "storage_bytes": 1_000_000_000}


def plan() -> dict[str, Any]:
    return {
        "rounds": 64,
        "worlds_per_round": 16,
        "development_worlds": 32,
        "minimum_terminal_training_worlds": 12,
        "control_worlds": 3,
        "control_updates_per_copy": 2,
        "initializers": [2, 3],
        "training": [f"SP1RESH1FTA8Q1T{i:04d}" for i in range(1, 1025)],
        "development": [f"SP1RESH1FTA8Q1E{i:03d}" for i in range(1, 33)],
        "control": [f"SP1RESH1FTA8Q1C{i:03d}" for i in range(1, 4)],
        "reload": ["SP1RESH1FTA8Q1R001"],
        "final_selection": "fixed_round_64",
        "training_starts": "fresh_normal_starts_only",
        "replay_imitation_labels": False,
    }


def implementation(root: Path) -> dict[str, str]:
    previous = json.loads((root / MIXED).read_text())["implementation"]
    names = {
        *previous,
        MIXED,
        PPO_PARENT,
        "scripts/train-a8-qualified-model-only-v1.sh",
        "scripts/engine-qualified-learning-worker-v1.test.mjs",
        "tests/unit/test_native_qualified_learning_v1.py",
        *(f"src/spireshift/{name}.py" for name in SOURCES),
        "src/spireshift/native_combat_intent_model.py",
        "src/spireshift/native_a8_card_display_model.py",
        *(
            f"src/spireshift/native_qualified_learning_{name}_v1.py"
            for name in ("worker", "fit", "inputs", "session", "audit")
        ),
    }
    names.update(f"scripts/{name}" for name in worker_helpers(root, SCRIPT))
    return {name: _sha_file(root / name) for name in sorted(names)}


def load(root: Path) -> dict[str, Any]:
    cfg: dict[str, Any] = json.loads((root / RECIPE).read_text())
    parent = json.loads((root / PPO_PARENT).read_text())
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["plan"] != plan()
        or cfg["limits"] != LIMITS
        or cfg["control_limits"] != CONTROL_LIMITS
        or cfg["implementation"] != implementation(root)
        or cfg["workspace"] == cfg["control_workspace"]
    ):
        raise ValueError("The qualified model-only training declaration changed")
    for key in ("objective", "game_limits", "settings", "credit", "training_score_id"):
        if cfg[key] != parent[key]:
            raise ValueError(f"Preserve the declared whole-run objective and PPO {key}")
    proof = identified(verified(root, cfg["mixed_assessment"]))
    if (
        proof["status"] != "twelve_mixed_mechanisms_and_merchant_map_probe_verified"
        or proof["current_main_mechanisms_verified"] != 12
        or proof["additional_merchant_map_effect_probes"] != 1
        or proof["matching_public_states"] != 114
        or proof["actual_sdk_choices_reconstructed"] != 101
        or proof["games_launched"] != 0
        or not all(proof["frozen_checks"].values())
    ):
        raise ValueError("Require the complete saved mixed-owner assessment")
    check_sources(root, proof["sources"])
    lifecycle = identified(verified(root, cfg["lifecycle_result"]))
    if lifecycle["status"] != "verified" or not lifecycle["native_stampede_branches_verified"]:
        raise ValueError("Require the lethal/nonlethal native ending and input controls")
    for player in (2, 3):
        ref = cfg["starting_states"][str(player)]
        state, state_id = load_state(verified(root, ref))
        if (
            state_id != ref["state_id"]
            or state_id
            != lifecycle["saved_learner_inputs"]["copied_state_controls"][str(player)][
                "copied_state_id"
            ]
        ):
            raise ValueError("The frozen shared-head starting copy or full Adam differs")
        if state.model.arm != "shared":
            raise ValueError("This study has one shared scoring head")
    seeds = [
        seed for key in ("training", "development", "control", "reload") for seed in plan()[key]
    ]
    if len(set(seeds)) != len(seeds) or any(canonical_seed(seed) != seed for seed in seeds):
        raise ValueError("All learning and assessment worlds must be canonical and disjoint")
    for path in (root / "configs").rglob("*.json"):
        if path == root / RECIPE:
            continue
        text = path.read_text()
        if any(f'"{seed}"' in text for seed in seeds):
            raise ValueError(
                "A prospective training/evaluation world was declared in another recipe"
            )
    return cfg


def context(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    ctx = qualified_context(root)
    if (
        ctx["environment_id"] != cfg["environment_id"]
        or ctx["score"].spec_id != cfg["training_score_id"]
        or ctx["score"].evaluation_objective.as_dict() != cfg["objective"]
    ):
        raise ValueError("The frozen native environment or training objective changed")
    return ctx
