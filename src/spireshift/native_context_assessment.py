"""Reconstruct the saved synthetic comparison without collecting or fitting."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.full_run_experience import atomic_json
from spireshift.native_action_context import CROSSED, MODES, ActionContextModel, initialize
from spireshift.native_action_context_study import evaluate, load_config, run_study
from spireshift.native_conditional_control import TASK, passed


def assess(root: Path, path: Path) -> dict[str, Any]:
    cfg, settings, score = load_config(root, path)
    output = root / cfg["workspace"]
    if not (output / "report.json").is_file():
        raise FileNotFoundError("Only a saved complete comparison can be assessed")
    report = run_study(root, path)  # Cached path checks every artifact; never starts fitting here.
    if report["status"] != "complete" or not report["integrity_pass"]:
        raise ValueError("Synthetic context comparison is incomplete")
    results = []
    for row in report["results"]:
        mode, seed, method = row["mode"], row["seed"], row["method"]
        model = ActionContextModel.from_mapping(
            json.loads((output / f"{mode}-seed-{seed}-{method}-synthetic-model.json").read_text())
        )
        initial = initialize(
            manifest_identifier({"synthetic_task_v1": TASK.as_dict()}), score.spec_id, seed, mode
        )
        final = evaluate(
            model, score, settings["temperature"], hide_hp=method == "hp_removed_teacher"
        )
        held = evaluate(
            model, score, settings["temperature"], held=True, hide_hp=method == "hp_removed_teacher"
        )
        if (
            model.model_id != row["final_model_id"]
            or initial.model_id != row["initial_model_id"]
            or model.mode != mode
            or model.parameter_count != 17473
            or final != row["final"]
            or held != row["held_out"]
            or row["passed"] != passed(row["curve"][0]["evaluation"], final, cfg["acceptance"])
        ):
            raise ValueError("Saved context model does not reproduce the reported evaluation")
        results.append(
            {
                "mode": mode,
                "training_seed": seed,
                "method": method,
                "expected_victory": final["expected_victory"],
                "minimum_optimal_probability": final["minimum_optimal_action_probability"],
                "greedy_accuracy": final["greedy_accuracy"],
                "held_expected_victory": held["expected_victory"],
                "held_greedy_accuracy": held["greedy_accuracy"],
                "passed": row["passed"],
                "work": row["work"],
                "final_model_id": model.model_id,
            }
        )
    checks = {
        "all_saved_models_reconstruct_final_and_held_evaluations": len(results) == 21,
        "all_primary_methods_completed_288_updates": all(
            r["work"]["optimizer_steps"] == 288 for r in results
        ),
        "all_crossed_PPO_training_seeds_pass": sum(
            r["mode"] == CROSSED and r["method"] == "ppo" and r["passed"] for r in results
        )
        == 3,
        "all_crossed_PPO_held_contexts_greedily_correct": all(
            r["held_greedy_accuracy"] == 1
            for r in results
            if r["mode"] == CROSSED and r["method"] == "ppo"
        ),
    }
    body = {
        "schema_version": "native-action-context-assessment-v1",
        "report_id_source": report["report_id"],
        "checks": checks,
        "results": results,
        "modes": list(MODES),
        "sealed_files_verified": len(report["files"]),
        "models_reconstructed": len(results),
        "games_launched": 0,
        "optimizer_steps": 0,
        "native_episodes_opened": 0,
        "checkpoint_promoted": False,
        "adaptive_controller_allowed": False,
        "claim_scope": "saved_finite_synthetic_representation_result_not_native_strength",
    }
    return {**body, "report_id": manifest_identifier(body)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    result = assess(root, root / args.config)
    if args.output:
        target = root / args.output
        if target.exists():
            if identified(target) != result:
                raise FileExistsError("Preserve the different saved assessment")
        else:
            atomic_json(target, result)
    print(json.dumps({k: v for k, v in result.items() if k != "results"}, indent=2))
    return 0 if all(result["checks"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
