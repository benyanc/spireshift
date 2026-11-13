"""Finite saved-TRAIN independent-game gradient/batch checks; no gameplay or optimizer."""

from __future__ import annotations

import argparse
import gc
import json
import math
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode
from spireshift.engine_native import _private_path
from spireshift.engine_neural import NativeActorCritic
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_gradient_checks import (
    batch_gradient,
    batch_size_checks,
    game_gradient,
    production_gradient_check,
)
from spireshift.native_normalization_comparison import require_matched_recipes
from spireshift.native_pilot_assessment import SavedFiles, _case, _worker_audits
from spireshift.training_objective import load_training_score_spec

SOURCES = (
    "native_gradient_checks.py",
    "native_gradient_study.py",
    "engine_neural.py",
    "engine_experience.py",
    "native_value_credit.py",
    "full_run_policy.py",
    "full_run_ppo_math.py",
    "native_pilot_assessment.py",
    "native_input_normalization.py",
    "native_normalization_comparison.py",
)


def train_panel(
    recipe: dict[str, Any], index: int, seeds: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    if type(index) is not int or index not in (1, 8):
        raise ValueError("Only predeclared first/last TRAIN rounds may be inspected")
    ids = recipe["learning"]["rollout_panels"][index - 1]
    if (
        len(set(ids)) != len(ids)
        or len(ids) != 32
        or any(s not in seeds or seeds[s]["partition"] != "train" for s in ids)
    ):
        raise ValueError("Gradient pool requires 32 distinct TRAIN games; reserved games excluded")
    return {"name": f"round-{index:03}-sampled", "partition": "train", "ids": ids}


def run_study(root: Path, config_path: Path) -> dict[str, Any]:
    cfg = json.loads(config_path.read_text())
    if (
        cfg.get("schema_version") != "native-independent-gradient-study-config-v1"
        or cfg.get("rounds") != [1, 8]
        or cfg.get("batch_sizes") != [4, 8, 16, 32, 64, 128]
        or cfg.get("partitions") != 32
        or cfg.get("partition_salt") != 20261017
        or cfg.get("implementation_sha256")
        != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
        or set(cfg.get("experiments", {})) != {"unscaled", "normalized"}
    ):
        raise ValueError("Freeze the finite saved-TRAIN gradient study and implementation")
    output = _private_path(root, cfg["workspace"])
    if output.exists() or output.is_symlink():
        raise FileExistsError("Preserve previous gradient evidence; no automatic overwrite")
    output.mkdir(parents=True, exist_ok=False)
    files = SavedFiles(root, 230)
    files.pin(config_path)
    for name, digest in cfg["implementation_sha256"].items():
        if files.pin(root / "src/spireshift" / name) != digest:
            raise ValueError("Gradient study implementation changed")
    recipes, reports = {}, []
    for arm in ("unscaled", "normalized"):
        ref = cfg["experiments"][arm]
        recipe = files.read(root / ref["path"])
        if manifest_identifier(recipe) != ref["id"]:
            raise ValueError("Gradient study source recipe differs")
        recipes[arm] = recipe
    require_matched_recipes(recipes["unscaled"], recipes["normalized"])
    verified_runs = verified_decisions = 0
    for arm, recipe in recipes.items():
        pilot = _private_path(root, recipe["workspace"])
        summary = files.read(pilot / "summary.json", "report_id")
        if (
            summary["status"] != "bounded_pilot_complete"
            or summary["config_id"] != manifest_identifier(recipe)
            or summary["completed_games"] != 336
            or summary["failed_games"]
            or summary["not_attempted_games"]
            or summary["worker_failures"]
            or summary["game_apps_created"]
            or not all(v is True for v in summary["checks"].values())
            or files.read(pilot / "config.json") != recipe
        ):
            raise ValueError("Study needs the complete immutable source experiment")
        for name, digest in recipe["implementation_sha256"].items():
            if files.pin(pilot / "source-at-launch" / name) != digest:
                raise ValueError("Source-at-launch evidence changed")
        score = load_training_score_spec(root / recipe["training_spec"]["path"])
        files.pin(root / recipe["training_spec"]["path"])
        seeds = files.read(root / recipe["seed_manifest"]["path"], "manifest_id")
        if (
            score.spec_id != recipe["training_spec"]["id"]
            or seeds["manifest_id"] != recipe["seed_manifest"]["id"]
        ):
            raise ValueError("Gradient seed or score identity differs")
        by_id = {s["id"]: s for s in seeds["seeds"]}
        for index in cfg["rounds"]:
            panel = train_panel(recipe, index, by_id)
            ids = panel["ids"]
            folder = pilot / panel["name"]
            path = pilot / (
                "initial-checkpoint.json" if index == 1 else f"round-{index - 1:03}-checkpoint.json"
            )
            model = NativeActorCritic.from_mapping(files.read(path))
            update = files.read(pilot / f"round-{index:03}-update.json")
            credit = files.read(pilot / f"round-{index:03}-credit.json", "report_id")
            settings = recipe["learning"]["ppo"]
            if (
                update != summary["rounds"][index - 1]
                or update["behavior_model_id"] != model.model_id
                or update["credit_report_id"] != credit["report_id"]
                or model.actor.environment_id != recipe["environment_manifest"]["id"]
                or model.actor.input_normalization
                != recipe["network"].get("input_normalization", "none")
            ):
                raise ValueError("Gradient cohort model or update binding differs")
            scope = manifest_identifier(
                {
                    "recipe": manifest_identifier(recipe),
                    "model": model.model_id,
                    "temperature": settings["temperature"],
                    "score": score.spec_id,
                    "partition": "train",
                    "round": index,
                }
            )
            games, samples, outcomes = [], [], []
            # Preserve production's deterministic worker-lane concatenation order.
            ordered = [
                s for lane in range(recipe["workers"]) for s in ids[lane :: recipe["workers"]]
            ]
            for seed in ordered:
                if by_id[seed]["partition"] != "train":
                    raise ValueError("Reserved games cannot enter gradient diagnostics")
                path = folder / f"case-{seed}.json"
                outcomes.append(
                    _case(files, path, recipe, panel, by_id[seed], model.model_id, score)
                )
                binding = json.loads(path.read_text())["binding"]
                case = read_native_episode(path, binding)
                g, batch = game_gradient(
                    model, case, seed, index, score, settings["temperature"], scope
                )
                games.append(g)
                samples.extend(batch)
            _worker_audits(files, pilot, recipe, outcomes)
            full = batch_gradient(games, settings["entropy_coefficient"])
            if full.folds != credit["baseline_models"] or any(
                not math.isclose(
                    full.summary[k], update["diagnostics"][k], rel_tol=0, abs_tol=1e-12
                )
                for k in ("raw_advantage_mean", "raw_advantage_std")
            ):
                raise ValueError("Full original-batch credit/normalization does not reconstruct")
            reference = production_gradient_check(model, games, samples, settings)
            checks = batch_size_checks(
                games,
                cfg["batch_sizes"],
                cfg["partitions"],
                cfg["partition_salt"],
                settings["entropy_coefficient"],
            )
            row = {
                "arm": arm,
                "round": index,
                "scope_id": scope,
                "behavior_model_id": model.model_id,
                "source_report_id": summary["report_id"],
                "pool_seeds": ordered,
                "source_credit_report_id": credit["report_id"],
                "production_reference": reference,
                **checks,
            }
            reports.append(row)
            atomic_json(output / f"{arm}-round-{index:03}.json", row)
            verified_runs += len(games)
            verified_decisions += len(samples)
            print(
                json.dumps(
                    {
                        "arm": arm,
                        "round": index,
                        "games": len(games),
                        "reference": reference,
                        "data_agreement": [
                            {"games_per_group": c["games_per_group"], **c["data_agreement"]}
                            for c in checks["disjoint_group_curves"]
                        ],
                    }
                ),
                flush=True,
            )
            del games, samples, case, g, batch
            gc.collect()
    body = {
        "schema_version": "native-independent-gradient-study-v1",
        "config_id": manifest_identifier(cfg),
        "cohorts": reports,
        "verified_training_games": verified_runs,
        "verified_training_decisions": verified_decisions,
        "controls_pass": all(c["production_reference"]["passed"] for c in reports),
        "cohorts_never_pooled": True,
        "groups_refit_their_own_baselines": True,
        "confirmation_or_development_episodes_opened": 0,
        "sources": files.sources(),
        "games_launched": 0,
        "optimizer_steps": 0,
        "production_checkpoints_written": 0,
        "checkpoint_promoted": False,
        "base_readiness_passed": False,
        "adaptive_controller_allowed": False,
        "claim_scope": (
            "saved_TRAIN_behavior_gradient_and_correlated_finite_pool_batch_controls"
            "_not_gameplay_improvement"
        ),
        "next_step": "measure_larger_independent_frozen_policy_TRAIN_pool",
    }
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(output / "config-at-launch.json", cfg)
    for name in SOURCES:
        (output / name).write_bytes((root / "src/spireshift" / name).read_bytes())
    atomic_json(output / "report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    result = run_study(root, (root / args.config).resolve())
    print(
        json.dumps({k: v for k, v in result.items() if k not in {"sources", "cohorts"}}, indent=2)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
