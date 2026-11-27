"""Pinned native complete-turn recipe, reusing the unchanged later TRAIN corpus."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_selection_worker import SCRIPT
from spireshift.engine_worker import worker_helpers
from spireshift.native_combat_teacher_data import INFORMATION
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import load_state
from spireshift.native_context_reuse import check_sources
from spireshift.native_later_teacher import SOURCES as LATER_SOURCES
from spireshift.native_later_teacher import load as load_later
from spireshift.native_turn_teacher_policy import CONTRACT, MAX_PLAN_BYTES, MAX_STEPS

GENERATION = "greedy_reference_plus_one_sampled_complete_turn_per_legal_first_action_v1"
SOURCES = tuple(
    sorted(
        set(
            (
                *LATER_SOURCES,
                "native_turn_teacher_policy.py",
                "native_turn_teacher_data.py",
                "native_turn_teacher_branch.py",
                "native_turn_teacher_config.py",
                "native_turn_teacher.py",
                "native_turn_teacher_audit.py",
            )
        )
    )
)
ENTRIES = (
    "native-complete-turn-teacher-v1.py",
    "collect-native-complete-turn-teacher-v1.sh",
    "verify-selection-cursor-v1.mjs",
)


def load(
    root: Path, path: Path
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    cfg = json.loads(path.read_text())
    control = cfg.get("stage") == "short_control"
    if (
        cfg.get("schema_version") != "native-complete-turn-teacher-config-v1"
        or cfg.get("stage") not in {"short_control", "finite_teacher_pilot"}
        or cfg.get("policy_contract") != CONTRACT
        or cfg.get("information_scope") != INFORMATION
        or cfg.get("ordinary_PPO_eligible") is not False
        or cfg.get("proposal_generation") != GENERATION
        or cfg.get("proposal_temperature") != 1.2
        or cfg.get("maximum_turn_decisions") != MAX_STEPS
        or cfg.get("maximum_plan_bytes") != MAX_PLAN_BYTES
        or cfg.get("repeats") != (2 if control else 8)
        or cfg.get("implementation_sha256")
        != {name: _sha_file(root / "src/spireshift" / name) for name in SOURCES}
        or cfg.get("entry_sha256") != {name: _sha_file(root / "scripts" / name) for name in ENTRIES}
        or cfg.get("helpers_sha256") != worker_helpers(root, SCRIPT)
        or cfg.get("session_limits")
        != {
            "wall_seconds": 240 if control else 900,
            "cpu_seconds": 480 if control else 1800,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 2000000000 if control else 4000000000,
        }
    ):
        raise ValueError(
            "Freeze complete-turn generation, scope, exact source bytes and finite caps"
        )
    parent_path = root / cfg["source_recipe"]["path"]
    parent, corpus, roots, sources = load_later(root, parent_path)
    if manifest_identifier(parent) != cfg["source_recipe"]["id"] or any(
        cfg[k] != parent[k]
        for k in (
            "roots_report",
            "qualification",
            "qualification_id",
            "node",
            "native_inputs",
            "temperature",
            "helpers_sha256",
        )
    ):
        raise ValueError("Keep the original later public TRAIN worlds, players and native inputs")
    if parent["stage"] != "finite_teacher_pilot":
        raise ValueError("The complete-turn source is the full frozen later-root curriculum")
    if control:
        roots = [
            min(
                (r for r in roots if r["numerical_seed"] == n),
                key=lambda r: (
                    len(r["public_input"]["candidates"]),
                    len(r["prefix"]),
                    r["root_id"],
                ),
            )
            for n in (2, 3)
        ]
    if not control:
        passed = identified(root / cfg["control_report"]["path"])
        old = json.loads((root / passed["recipe_path"]).read_text())
        if (
            passed["report_id"] != cfg["control_report"]["id"]
            or passed["status"] != "native_complete_turn_teacher_complete"
            or passed["failed_branches"]
            or passed["skipped_branches"]
            or not passed["duplicate_public_traces_identical"]
            or not passed["all_turn_boundaries_replayed_exactly"]
            or old["stage"] != "short_control"
            or not all(c["comparison_complete"] for c in passed["cases"])
            or any(
                old[k] != cfg[k]
                for k in (
                    "implementation_sha256",
                    "entry_sha256",
                    "helpers_sha256",
                    "source_recipe",
                    "roots_report",
                    "qualification",
                    "qualification_id",
                    "node",
                    "native_inputs",
                    "temperature",
                    "proposal_temperature",
                    "proposal_generation",
                    "policy_contract",
                    "information_scope",
                    "maximum_turn_decisions",
                    "maximum_plan_bytes",
                )
            )
        ):
            raise ValueError(
                "Exact complete-turn replay and repeated-trace native control must pass"
            )
        check_sources(root, passed["sources"])
        sources[cfg["control_report"]["path"]] = _sha_file(root / cfg["control_report"]["path"])
        checked = identified(root / cfg["control_audit"]["path"])
        if (
            checked["report_id"] != cfg["control_audit"]["id"]
            or checked["source_report_id"] != passed["report_id"]
            or checked["auditor_sha256"]
            != cfg["implementation_sha256"]["native_turn_teacher_audit.py"]
            or checked["branch_receipts_verified"] != passed["completed_units"]
            or any(
                checked[k] is not True
                for k in (
                    "turn_boundaries_and_plans_reconstructed",
                    "all_action_tables_exactly_reconstructed",
                    "proposal_selection_outcome_blind",
                    "continuation_probabilities_reconstructed",
                    "original_players_and_full_Adam_unchanged",
                )
            )
        ):
            raise ValueError(
                "Saved complete-turn control choices, plans and probabilities must reconstruct"
            )
        sources[cfg["control_audit"]["path"]] = _sha_file(root / cfg["control_audit"]["path"])
    sources.update(
        {
            str(path.relative_to(root)): _sha_file(path),
            **{f"src/spireshift/{n}": sha for n, sha in cfg["implementation_sha256"].items()},
            **{f"scripts/{n}": sha for n, sha in cfg["entry_sha256"].items()},
        }
    )
    return cfg, corpus, roots, sources


def load_models(root: Path, corpus: dict[str, Any]) -> dict[int, CachedContextModel]:
    models = {}
    for ref in corpus["models"]:
        model, adam, identity = load_state(root / ref["state_path"])
        if (
            identity != ref["state_id"]
            or adam.steps != ref["optimizer_steps"]
            or model.actor.environment_id != corpus["environment_manifest"]["id"]
            or model.feature_spec_id != corpus["training_spec"]["id"]
        ):
            raise ValueError(
                "Preserve the original environment, score, weights and every Adam moment"
            )
        models[ref["numerical_seed"]] = model
    return models
