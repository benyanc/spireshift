"""Verify the completed learner audit and summarize its measured limits."""

from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import median
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_capacity_inputs_v2 import context
from spireshift.native_capacity_result_v1 import DEEP_STATUS
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_learning_health_v1 import COMPLETE, RECIPE, load
from spireshift.native_win4_game import write

WORKSPACE = "artifacts/native-learning-health/v1/assessment-v1"
STATUS = "saved_training_health_results_independently_verified"


def assess(root: Path) -> dict[str, Any]:
    cfg, parent = load(root)
    ctx = context(root, parent)
    before = frozen(root, ctx)
    path = root / cfg["workspace"] / "report.json"
    report = identified(path)
    check_sources(root, report["sources"])
    if (
        report["status"] != COMPLETE
        or report["config_id"] != manifest_identifier(cfg)
        or report["source_optimizer_updates"] != 0
        or report["new_games"] != 0
        or report["checkpoints_saved"] != 0
        or report["disposable_copy_updates"] != 32
        or not all(report["frozen_checks"].values())
    ):
        raise ValueError("Require the complete sixteen-cohort diagnostic with no source updates")
    deep_path = root / "artifacts/native-policy-capacity/assessment-public-recount-v1/report.json"
    deep = identified(deep_path)
    check_sources(root, deep["sources"])
    if (
        deep["status"] != DEEP_STATUS
        or deep["raw_public_diagnostics_recounted"] is not True
        or deep["development_games_verified"] != 768
        or deep["verified_units"] != 5120
    ):
        raise ValueError("The complete native public outcome recount must also pass")
    out = root / WORKSPACE
    out.mkdir(parents=True, exist_ok=True)
    target = out / "report.json"
    if target.exists():
        saved = identified(target)
        check_sources(root, saved["sources"])
        return saved
    store = ChunkJournal(root, cfg)
    rows = []
    sources = {
        RECIPE: _sha_file(root / RECIPE),
        str(path.relative_to(root)): _sha_file(path),
        str(deep_path.relative_to(root)): _sha_file(deep_path),
        str(Path(__file__).relative_to(root)): _sha_file(Path(__file__)),
    }
    with store.lock():
        for r in cfg["plan"]["rounds"]:
            for p in (2, 3):
                for method in cfg["plan"]["methods"]:
                    key = f"p{p}-{method}-r{r:03d}"
                    request = {
                        "player": p,
                        "method": method,
                        "round": r,
                        "short": False,
                        "source_assessment": cfg["source_assessment"],
                    }
                    seal = store.completed(key, request)
                    if seal is None:
                        raise ValueError("A declared saved diagnostic cohort is missing")
                    row = seal["result"]
                    if (
                        row["source_partition"] != "train"
                        or row["reconstructed_games"] != 16
                        or row["source_optimizer_updates"] != 0
                        or row["new_games"] != 0
                        or row["checkpoints_saved"] != 0
                        or not row["source_states_and_Adam_unchanged"]
                    ):
                        raise ValueError("A diagnostic used foreign data or changed a source")
                    if len(row["kernel_probes"]) != 4:
                        raise ValueError("Every saved cohort requires all four numerical probes")
                    for check in row["kernel_probes"]:
                        if (
                            not check["responsive"]
                            or not math.isfinite(check["maximum_relative_directional_error"])
                            or check["maximum_relative_directional_error"] > 1e-5
                            or not all(
                                x["correct_direction"] for x in check["advantage_signs"].values()
                            )
                        ):
                            raise ValueError("A numerical policy-gradient probe failed")
                    if not math.isfinite(row["raw_advantage_std"]):
                        raise ValueError("Nonfinite reconstructed action credit")
                    rows.append(row)
                    f = store.path(key) / "done.json"
                    sources[str(f.relative_to(root))] = _sha_file(f)
    if rows != report["cohorts"] or frozen(root, ctx) != before:
        raise ValueError("The saved diagnostic, frozen build or original full Adam changed")
    optimizer = {
        name: {
            "loss_decreased_cohorts": sum(
                row["optimizer_probes"]["one_step_probes"][name]["loss_change"] < 0 for row in rows
            ),
            "median_behavior_kl": median(
                row["optimizer_probes"]["one_step_probes"][name]["joint_behavior_kl"]
                for row in rows
            ),
        }
        for name in ("inherited_Adam", "reset_Adam")
    }
    return write(
        target,
        {
            "status": STATUS,
            "source_report_id": report["report_id"],
            "complete_public_recount_id": deep["report_id"],
            "cohorts_verified": len(rows),
            "source_training_games": sum(row["reconstructed_games"] for row in rows),
            "native_decisions_reconstructed": sum(row["candidate_decisions"] for row in rows),
            "native_victory_targets": sum(row["native_victory_targets"] for row in rows),
            "numerical_gradient_probes_passed": sum(len(row["kernel_probes"]) for row in rows),
            "learned_critic_negative_explained_variance_cohorts": sum(
                row["critic_explained_variance"] < 0 for row in rows
            ),
            "actor_ridge_baseline_negative_explained_variance_cohorts": sum(
                row["cross_fitted_baseline_explained_variance"] < 0 for row in rows
            ),
            "optimizer_probes": optimizer,
            "reset_Adam_larger_kl_cohorts": sum(
                row["optimizer_probes"]["one_step_probes"]["reset_Adam"]["joint_behavior_kl"]
                > row["optimizer_probes"]["one_step_probes"]["inherited_Adam"]["joint_behavior_kl"]
                for row in rows
            ),
            "saturation_by_round_and_method": {
                f"{r}-{m}": [
                    row["geometry"]["mean_hidden_saturation_above_abs_0_95"]
                    for row in rows
                    if row["round"] == r and row["method"] == m
                ]
                for r in cfg["plan"]["rounds"]
                for m in cfg["plan"]["methods"]
            },
            "next_hypothesis": (
                "matched_zero_initial_corrections_raw_versus_per_candidate_hidden_normalization"
            ),
            "normalization_is_established_cause": False,
            "optimizer_reset_strength_gain_established": False,
            "source_optimizer_updates": 0,
            "new_games": 0,
            "checkpoints_saved": 0,
            "frozen_checks": before,
            "promotion_allowed": False,
            "official_live_qualification_granted": False,
            "final_test_worlds_used": False,
            "sources": sources,
        },
    )


if __name__ == "__main__":
    result = assess(Path.cwd())
    print(json.dumps({k: v for k, v in result.items() if k != "sources"}))
