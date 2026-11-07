"""Saved-only preflight/show for a finite owner-run actor input-scaling comparison."""

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
from spireshift.native_input_normalization import NONE, QUARTER


def require_matched_recipes(unscaled: dict[str, Any], normalized: dict[str, Any]) -> None:
    if (
        unscaled["stage"] != "bounded_policy_only_pilot"
        or unscaled.get("development_comparison") != "initial_vs_best_trained"
        or unscaled["network"].get("input_normalization", NONE) != NONE
        or unscaled.get("input_normalization_checks") is not None
        or normalized["network"].get("input_normalization") != QUARTER
        or not normalized.get("input_normalization_checks")
        or unscaled["learning"].get("credit_assignment", {}).get("id") != CREDIT_ID
        or unscaled["workspace"] == normalized["workspace"]
    ):
        raise ValueError("Expected unscaled/normalized arms with the same cross-fitted credit")
    documents = []
    for recipe in (unscaled, normalized):
        d = copy.deepcopy(recipe)
        for key in ("workspace", "admission", "input_normalization_checks"):
            d.pop(key, None)
        d["network"].pop("input_normalization", None)
        documents.append(d)
    if documents[0] != documents[1]:
        raise ValueError("Normalization comparison changes something other than input scaling")


def comparison_plan(root: Path, path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    if (
        cfg.get("schema_version") != "native-input-normalization-comparison-config-v1"
        or cfg.get("implementation_sha256") != _sha_file(Path(__file__))
        or set(cfg.get("arms", {})) != {"unscaled", "normalized"}
    ):
        raise ValueError("Expected the frozen finite input-normalization comparison")
    q = load_engine_qualification_config(root / cfg["qualification_config"])
    recipes, states = {}, []
    for name in ("unscaled", "normalized"):
        ref = cfg["arms"][name]
        recipe = load_learning_config(root / ref["path"], q)
        if manifest_identifier(recipe) != ref["id"]:
            raise ValueError("Normalization comparison arm changed")
        recipes[name] = recipe
        workspace = root / recipe["workspace"]
        if workspace.is_symlink():
            raise ValueError("Preserve unexpected comparison workspace links")
        if (workspace / "summary.json").is_file():
            result = identified(workspace / "summary.json")
            if (
                result["config_id"] != ref["id"]
                or result["status"]
                not in {"bounded_pilot_complete", "bounded_pilot_complete_with_failures"}
                or result["planned_games"] != 336
                or result["recorded_games"] != 336
                or result["not_attempted_games"]
                or not all(result["checks"].values())
                or result.get("best_trained_model_id") is None
                or result.get("development_comparison") != "initial_vs_best_trained"
                or result.get("actor_input_normalization")
                != recipe["network"].get("input_normalization", NONE)
            ):
                raise ValueError("Preserve the incomplete/changed normalization arm for inspection")
            for source, digest in recipe["implementation_sha256"].items():
                if _sha_file(workspace / "source-at-launch" / source) != digest:
                    raise ValueError("Normalization experiment launch source changed")
            states.append(
                {
                    "name": name,
                    "state": "saved_complete",
                    "report_id": result["report_id"],
                    "initial_model_id": result["initial_model_id"],
                    "best_trained_model_id": result["best_trained_model_id"],
                    "panels": [
                        p for p in result["panels"] if p["panel"].startswith("development-")
                    ],
                }
            )
        else:
            if workspace.exists():
                raise ValueError("Preserve unfinished comparison evidence; no automatic resume")
            preflight = preflight_native_learning(q, root / ref["path"])
            if preflight["ready"] is not True:
                raise ValueError("Normalization experiment arm is not ready")
            states.append({"name": name, "state": "ready_not_started", "planned_games": 336})
    require_matched_recipes(recipes["unscaled"], recipes["normalized"])
    return {
        "schema_version": "native-input-normalization-comparison-plan-v1",
        "config_id": manifest_identifier(cfg),
        "arms": states,
        "maximum_planned_games": 672,
        "training_replicates_per_method": 1,
        "sole_treatment": "multiply_hashed_actor_features_by_one_quarter",
        "initial_numeric_weights_matched": True,
        "initial_policies_may_differ": True,
        "both_own_initial_and_best_trained_players_evaluated": True,
        "direct_actor_signals_and_critic_inputs_unchanged": True,
        "all_current_legal_actions_learnable": True,
        "games_launched": 0,
        "optimizer_steps": 0,
        "checkpoint_promoted": False,
        "stronger_play_not_yet_established": True,
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
