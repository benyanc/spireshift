"""Read-only admission of the completed learning test and its TRAIN-only arrays."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_consequence_config import load_config as old_config
from spireshift.native_consequence_evaluation import tasks
from spireshift.native_context_journal import load_state
from spireshift.native_context_reuse import check_sources
from spireshift.training_objective import load_training_score_spec

SOURCES = (
    "native_action_rankings.py",
    "native_outcome_predictor.py",
    "native_separation_inputs.py",
    "native_rank_audit.py",
    "native_prediction_separation.py",
)
ENTRIES = ("inspect-action-separation-v1.sh", "inspect-action-separation-v1.py")


def load(root: Path, path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    if (
        cfg.get("schema_version") != "native-action-prediction-separation-config-v1"
        or cfg.get("predictor_seed") != 20261022
        or cfg.get("predictor_epochs") != 128
        or cfg.get("maximum_saved_decisions_per_case") != 512
        or cfg.get("implementation_sha256")
        != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("entry_sha256") != {n: _sha_file(root / "scripts" / n) for n in ENTRIES}
        or cfg.get("session_limits")
        != {
            "wall_seconds": 240,
            "cpu_seconds": 480,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 1000000000,
        }
    ):
        raise ValueError("Freeze the saved-only ranking and independent-predictor protocol")
    r = identified(root / cfg["source_report"]["path"])
    a = identified(root / cfg["source_assessment"]["path"])
    if (
        r["report_id"] != cfg["source_report"]["id"]
        or r["status"] != "native_consequence_comparison_complete"
        or r["completed_games"] != 192
        or r["failed_games"]
        or a["report_id"] != cfg["source_assessment"]["id"]
        or a["source_report_id"] != r["report_id"]
        or a["verified_games"] != 192
        or not a["every_saved_trace_ending_score_and_paired_summary_reconstructed"]
        or any(not p["verified_byte_identical"] for p in a["parents"])
    ):
        raise ValueError("Require the completed negative experiment and its sealed result audit")
    check_sources(root, r["sources"])
    old = old_config(root, root / r["recipe_path"])
    if manifest_identifier(old) != r["config_id"]:
        raise ValueError("Historical comparison recipe changed")
    models, adams = {}, {}
    for p in r["parents"]:
        model, adam, sid = load_state(root / p["path"])
        if (
            model.model_id != p["model_id"]
            or sid != p["state_id"]
            or adam.steps != p["optimizer_steps"]
            or _sha_file(root / p["path"]) != p["sha256"]
        ):
            raise ValueError("Preserve both original players and every PPO Adam moment")
        models[p["numerical_seed"], "original"] = model
        adams[p["numerical_seed"]] = adam
    for f in r["final_forks"]:
        model, adam, _ = load_state(root / f["state_path"])
        if model.model_id != f["model_id"] or adam.steps != f["optimizer_steps"]:
            raise ValueError("Preserve all four rejected experimental forks")
        models[f["numerical_seed"], f["arm"]] = model
    score = load_training_score_spec(root / cfg["training_spec"]["path"])
    if score.spec_id != r["training_spec_id"] or score.spec_id != cfg["training_spec"]["id"]:
        raise ValueError("Full-run victory objective and declared bootstrap score must remain")
    for player in (2, 3):
        own = [m for (p, _), m in models.items() if p == player]
        if any(
            (m.mode, m.feature_spec_id, m.actor.dimension, m.actor.input_normalization)
            != (
                own[0].mode,
                own[0].feature_spec_id,
                own[0].actor.dimension,
                own[0].actor.input_normalization,
            )
            for m in own
        ):
            raise ValueError("Compare weights only on the exact same public encoder")
    seeds = identified(root / old["seed_manifest"]["path"], "manifest_id")["seeds"]
    sources = {
        **r["sources"],
        cfg["source_report"]["path"]: _sha_file(root / cfg["source_report"]["path"]),
        cfg["source_assessment"]["path"]: _sha_file(root / cfg["source_assessment"]["path"]),
        str(path.relative_to(root)): _sha_file(path),
    }
    sources.update({f"src/spireshift/{n}": v for n, v in cfg["implementation_sha256"].items()})
    sources.update({f"scripts/{n}": v for n, v in cfg["entry_sha256"].items()})
    return {
        "config": cfg,
        "old": old,
        "report": r,
        "models": models,
        "adams": adams,
        "score": score,
        "tasks": tasks(seeds, False),
        "sources": sources,
    }
