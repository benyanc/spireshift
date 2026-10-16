"""Preflight/show two matched owner-run credit arms. This module never launches games."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified, load_learning_config
from spireshift.engine_learning_admission import preflight_native_learning
from spireshift.engine_qualification import _sha_file, load_engine_qualification_config
from spireshift.native_credit_training import CREDIT_ID


def require_matched_recipes(legacy: dict[str, Any], crossfit: dict[str, Any]) -> None:
    if (
        legacy["stage"] != "bounded_policy_only_pilot"
        or legacy.get("development_comparison") != "initial_vs_best_trained"
        or legacy["learning"].get("credit_assignment") is not None
        or crossfit["learning"].get("credit_assignment", {}).get("id") != CREDIT_ID
        or legacy["workspace"] == crossfit["workspace"]
    ):
        raise ValueError("Expected separate legacy/cross-fit arms and a trained-player comparison")
    normalized = []
    for recipe in (legacy, crossfit):
        value = copy.deepcopy(recipe)
        for key in ("workspace", "admission"):
            value.pop(key)
        value["learning"].pop("credit_assignment", None)
        normalized.append(value)
    if normalized[0] != normalized[1]:
        raise ValueError(
            "Matched credit arms differ in something other than the baseline estimator"
        )


def comparison_plan(root: Path, path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    if (
        cfg.get("schema_version") != "native-matched-credit-comparison-config-v1"
        or cfg.get("implementation_sha256") != _sha_file(Path(__file__))
        or set(cfg.get("arms", {})) != {"legacy", "crossfit"}
    ):
        raise ValueError("Expected the frozen finite two-arm comparison")
    q = load_engine_qualification_config(root / cfg["qualification_config"])
    recipes, states = {}, []
    for name in ("legacy", "crossfit"):
        ref = cfg["arms"][name]
        recipe = load_learning_config(root / ref["path"], q)
        if manifest_identifier(recipe) != ref["id"]:
            raise ValueError("Matched arm identity changed")
        recipes[name] = recipe
        workspace = root / recipe["workspace"]
        if workspace.is_symlink():
            raise ValueError("Preserve unexpected comparison workspace links")
        if (workspace / "summary.json").is_file():
            report = identified(workspace / "summary.json")
            if (
                report["config_id"] != ref["id"]
                or report["status"]
                not in {"bounded_pilot_complete", "bounded_pilot_complete_with_failures"}
                or report["planned_games"] != 336
                or report["recorded_games"] != 336
                or report["not_attempted_games"]
                or not all(report["checks"].values())
                or report.get("best_trained_model_id") is None
                or report.get("development_comparison") != "initial_vs_best_trained"
            ):
                raise ValueError("Preserve the incomplete/changed comparison arm for inspection")
            for source, digest in recipe["implementation_sha256"].items():
                if _sha_file(workspace / "source-at-launch" / source) != digest:
                    raise ValueError("Completed arm implementation evidence changed")
            states.append(
                {
                    "name": name,
                    "state": "saved_complete",
                    "report_id": report["report_id"],
                    "panels": [
                        p for p in report["panels"] if p["panel"].startswith("development-")
                    ],
                    "incumbent_model_id": report["selected_model_id"],
                    "best_trained_model_id": report["best_trained_model_id"],
                }
            )
        else:
            if workspace.exists():
                raise ValueError("Preserve unfinished comparison evidence; no automatic resume")
            preflight = preflight_native_learning(q, root / ref["path"])
            if preflight["ready"] is not True:
                raise ValueError("Comparison arm is not ready")
            states.append({"name": name, "state": "ready_not_started", "planned_games": 336})
    require_matched_recipes(recipes["legacy"], recipes["crossfit"])
    return {
        "schema_version": "native-matched-credit-comparison-plan-v1",
        "config_id": manifest_identifier(cfg),
        "arms": states,
        "maximum_planned_games": 672,
        "training_replicates_per_method": 1,
        "sole_treatment": (
            "actor_return_baseline_behavior_critic_vs_whole_run_crossfit_public_ridge"
        ),
        "all_complete_action_families_learnable": True,
        "original_terminal_victory_objective_unchanged": True,
        "games_launched": 0,
        "optimizer_steps": 0,
        "causal_or_general_strength_claim_available": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    print(json.dumps(comparison_plan(root, (root / args.config).resolve()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
