"""Finite saved-TRAIN-only, whole-run cross-fitting control for native value/credit.

No workers, native launches, actor updates or confirmation/development episodes.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_learning_diagnosis import run_diagnosis
from spireshift.native_value_credit import (
    action_advantages,
    cross_fitted_predictions,
    prediction_metrics,
    redistribute_terminal_return,
    value_run,
)
from spireshift.training_objective import load_training_score_spec


def run_study(root: Path, config_path: Path) -> dict[str, Any]:
    cfg = json.loads(config_path.read_text())
    if (
        cfg.get("schema_version") != "native-value-credit-study-config-v1"
        or cfg.get("selection_rounds") != [1, 2, 3, 4]
        or cfg.get("audit_rounds") != [5, 6, 7, 8]
        or cfg.get("folds") != 4
        or cfg.get("regularization_grid") != [0.001, 0.01, 0.1, 1.0]
        or cfg.get("trace_lambdas") != [1.0, 0.95]
        or cfg.get("implementation_sha256")
        != {
            name: _sha_file(root / "src/spireshift" / name)
            for name in (
                "native_value_credit.py",
                "native_value_study.py",
                "native_learning_diagnosis.py",
            )
        }
    ):
        raise ValueError("Value study must freeze its finite train-only comparisons")
    output = _private_path(root, cfg["workspace"])
    if output.exists() or output.is_symlink():
        raise FileExistsError("Preserve the saved value study; no silent overwrite")
    experiment = root / cfg["experiment"]["path"]
    exp = json.loads(experiment.read_text())
    if manifest_identifier(exp) != cfg["experiment"]["id"]:
        raise ValueError("Value study source experiment differs")
    pilot = _private_path(root, exp["workspace"])
    if output == pilot or pilot in output.parents or output in pilot.parents:
        raise ValueError("Value study cannot alter the source pilot")
    audit = run_diagnosis(root, experiment, output / "source-audit")
    score = load_training_score_spec(root / exp["training_spec"]["path"])
    by_round = []
    for index, seeds in enumerate(exp["learning"]["rollout_panels"], 1):
        runs = []
        for seed in seeds:
            path = pilot / f"round-{index:03}-sampled/case-{seed}.json"
            binding = json.loads(path.read_text())["binding"]
            runs.append(value_run(read_native_episode(path, binding), seed, index, score))
        by_round.append(runs)
    candidates = [("constant", 1.0), ("behavior_critic", 1.0)] + [
        ("public_residual_ridge", rate) for rate in cfg["regularization_grid"]
    ]
    comparisons: list[dict[str, Any]] = []
    models: dict[str, list[dict[str, Any]]] = {}
    predictions: dict[str, dict[int, tuple[float, ...]]] = {}
    for kind, rate in candidates:
        key = f"{kind}:{rate:g}"
        reports, models[key], predictions[key] = [], [], {}
        for index, runs in enumerate(by_round, 1):
            folds: list[dict[str, Any]]
            if kind == "behavior_critic":
                predicted, folds = {r.seed: r.behavior_values for r in runs}, []
            else:
                predicted, folds = cross_fitted_predictions(
                    runs, kind, rate, cfg["folds"], cfg["fold_salt"]
                )
            models[key].append({"round": index, "folds": folds})
            predictions[key].update(predicted)
            reports.append({"round": index, **prediction_metrics(runs, predicted)})
        comparisons.append(
            {
                "name": key,
                "kind": kind,
                "regularization": rate,
                "rounds": reports,
                "selection_mse": math.fsum(
                    r["mse"] for r in reports if r["round"] in cfg["selection_rounds"]
                )
                / 4,
                "audit_mse": math.fsum(
                    r["mse"] for r in reports if r["round"] in cfg["audit_rounds"]
                )
                / 4,
            }
        )
    # This selection is made before reading any audit metrics into the selector.
    eligible = [c for c in comparisons if c["kind"] in {"constant", "public_residual_ridge"}]
    selected = min(eligible, key=lambda c: (c["selection_mse"], c["name"]))
    constant = next(c for c in comparisons if c["kind"] == "constant")
    audit_ratio = selected["audit_mse"] / constant["audit_mse"]
    better_rounds = sum(
        row["mse"] < ref["mse"]
        for row, ref in zip(selected["rounds"][4:], constant["rounds"][4:], strict=True)
    )
    gate = selected["kind"] == "public_residual_ridge" and audit_ratio < 0.95 and better_rounds >= 3
    credit = []
    for runs in by_round:
        for run in runs:
            rewards = redistribute_terminal_return(run.target, run.potentials)
            if not math.isclose(math.fsum(rewards), run.target - run.potentials[0], abs_tol=1e-12):
                raise ValueError("Credit redistribution changed the whole-run score")
            values = predictions[selected["name"]][run.seed]
            mc = action_advantages(run.target, run.potentials, values, 1.0)
            if any(
                not math.isclose(a, run.target - v, abs_tol=1e-12)
                for a, v in zip(mc, values, strict=True)
            ):
                raise ValueError("Full trace credit differs from original Monte Carlo advantage")
            trace = action_advantages(run.target, run.potentials, values, 0.95)
            credit.append(
                {
                    "seed": run.seed,
                    "round": run.round,
                    "decisions": len(values),
                    "original_return": run.target,
                    "initial_potential": run.potentials[0],
                    "redistributed_return": math.fsum(rewards),
                    "monte_carlo_equivalence_pass": True,
                    "lambda_095_mean_absolute_difference": math.fsum(
                        abs(a - b) for a, b in zip(trace, mc, strict=True)
                    )
                    / len(mc),
                }
            )
    sources = {**audit["sources"], str(config_path.relative_to(root)): _sha_file(config_path)}
    sources.update(
        {
            str(Path("src/spireshift") / name): digest
            for name, digest in cfg["implementation_sha256"].items()
        }
    )
    for name, digest in sources.items():
        if _sha_file(root / name) != digest:
            raise ValueError("A source changed during the value study")
    body = {
        "schema_version": "native-value-credit-study-v1",
        "config_id": manifest_identifier(cfg),
        "source_report_id": audit["source_report_id"],
        "source_audit_id": audit["report_id"],
        "training_runs": audit["training_runs"],
        "training_decisions": audit["training_decisions"],
        "comparisons": comparisons,
        "selected_baseline": selected["name"],
        "selected_audit_mse_over_cross_fitted_constant": audit_ratio,
        "audit_rounds_improved": better_rounds,
        "value_control_pass": gate,
        "credit_equivalence_checked_runs": len(credit),
        "lambda_less_than_one_is_biased_and_not_admitted": True,
        "fold_models": models,
        "credit_checks": credit,
        "sources": sources,
        "confirmation_or_development_episodes_opened": 0,
        "games_launched": 0,
        "actor_optimizer_steps": 0,
        "checkpoint_promoted": False,
        "training_allowed": False,
        "claim_scope": (
            "saved_train_only_within_round_whole_run_cross_fitted_baseline_control"
            "_not_gameplay_improvement"
        ),
        "next_step": "prepare_matched_native_credit_comparison"
        if gate
        else "repair_value_prediction_before_short_trace_bootstrapping",
    }
    result = {**body, "report_id": manifest_identifier(body)}
    for name in cfg["implementation_sha256"]:
        (output / name).write_bytes((root / "src/spireshift" / name).read_bytes())
    atomic_json(output / "config-at-launch.json", cfg)
    atomic_json(output / "report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    result = run_study(root, (root / args.config).resolve())
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"sources", "comparisons", "fold_models", "credit_checks"}
            },
            indent=2,
        )
    )
    for row in result["comparisons"]:
        print(row["name"], "selection MSE", row["selection_mse"], "audit MSE", row["audit_mse"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
