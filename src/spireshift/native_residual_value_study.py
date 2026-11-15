"""Sealed, restartable rich-correction comparison; original players/Adam are read-only."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import time
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_linear_value import INNER_FOLDS, REGULARIZATION, SALT
from spireshift.native_linear_value_study import COHORTS
from spireshift.native_linear_value_study import prepare as prepare_parent
from spireshift.native_matched_value import ValuePartition, errors, parameter_digest
from spireshift.native_public_value import paired_errors
from spireshift.native_residual_value import (
    BASELINE_REGULARIZATION,
    METHOD,
    CorrectedValue,
    nested_correction,
    select_correction,
)
from spireshift.native_residual_value_curves import write_curves
from spireshift.neural_combat import _numpy
from spireshift.training_objective import TrainingScoreSpec

SOURCES = (
    "native_residual_value.py",
    "native_residual_value_curves.py",
    "native_residual_value_study.py",
)
ENTRIES = ("compare-native-residual-value-v1.sh", "native-residual-value-v1.py")
PARENT_ID = "sha256:8c52d32d034bf591c7ceaff0665aecdada306ac37891c033a66e0b4a584671c1"
PARENT_RECIPE = "configs/native-controls/linear-value-comparison-v1.json"


def load_config(root: Path, path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    control = cfg.get("stage") == "short_control"
    if (
        cfg.get("schema_version") != "native-residual-value-config-v1"
        or cfg.get("stage") not in {"short_control", "saved_train_comparison"}
        or cfg.get("regularization") != list(REGULARIZATION)
        or cfg.get("coarse_regularization") != BASELINE_REGULARIZATION
        or cfg.get("no_correction_candidate") is not True
        or cfg.get("correction_intercept") != 0.0
        or cfg.get("inner_folds") != INNER_FOLDS
        or cfg.get("inner_salt") != SALT
        or cfg.get("cohorts") != (COHORTS[:1] if control else COHORTS)
        or cfg.get("outer_folds") != ([0] if control else [0, 1, 2, 3])
        or cfg.get("parent_comparison", {}).get("id") != PARENT_ID
        or cfg.get("parent_recipe") != PARENT_RECIPE
        or cfg.get("implementation_sha256")
        != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("entry_sha256") != {n: _sha_file(root / "scripts" / n) for n in ENTRIES}
        or cfg.get("resource_limits")
        != {
            "wall_seconds": 240 if control else 900,
            "cpu_seconds": 240 if control else 900,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 500000000,
        }
    ):
        raise ValueError(
            "Freeze correction grid, baseline, whole-game splits, source bytes and caps"
        )
    return cast(dict[str, Any], cfg)


def prepare(
    root: Path, path: Path
) -> tuple[dict[str, Any], list[dict[str, Any]], TrainingScoreSpec, dict[str, str]]:
    cfg = load_config(root, path)
    _, inherited_units, score, sources = prepare_parent(root, root / cfg["parent_recipe"])
    parent_path = root / cfg["parent_comparison"]["path"]
    parent = identified(parent_path)
    if (
        parent["report_id"] != PARENT_ID
        or parent["status"] != "native_linear_value_complete"
        or parent["stage"] != "saved_train_comparison"
        or parent["completed_folds"] != 16
        or parent["summary"]["unique_held_games"] != 128
        or parent["training_spec_id"] != score.spec_id
        or not parent["production_states_unchanged"]
        or parent["new_games"] != 0
    ):
        raise ValueError("Require the completed unchanged linear comparison and original target")
    sources.update(parent["sources"])
    sources[str(parent_path.relative_to(root))] = _sha_file(parent_path)
    check_sources(root, sources)
    if cfg["stage"] == "saved_train_comparison":
        control_path = root / cfg["control_report"]["path"]
        control = identified(control_path)
        if (
            control["report_id"] != cfg["control_report"]["id"]
            or control["status"] != "native_residual_value_complete"
            or control["stage"] != "short_control"
            or control["completed_folds"] != 1
            or not control["production_states_unchanged"]
            or json.loads((root / control["recipe_path"]).read_text())["implementation_sha256"]
            != cfg["implementation_sha256"]
        ):
            raise ValueError("Require the matching completed real-input correction control")
        check_sources(root, control["sources"])
        sources[str(control_path.relative_to(root))] = _sha_file(control_path)
    units = [
        u
        for u in inherited_units
        if u["cohort"] in cfg["cohorts"] and u["fold"] in cfg["outer_folds"]
    ]
    sources[str(path.relative_to(root))] = _sha_file(path)
    sources.update({f"src/spireshift/{n}": s for n, s in cfg["implementation_sha256"].items()})
    sources.update({f"scripts/{n}": s for n, s in cfg["entry_sha256"].items()})
    return cfg, units, score, sources


def compare_fold(
    root: Path, unit: dict[str, Any], directory: Path, cfg: dict[str, Any], deadline: float
) -> dict[str, Any]:
    np = _numpy()
    with np.load(root / unit["encoded"] / "encoded.npz", allow_pickle=False) as source:
        arrays = {name: source[name] for name in source.files}
    mask, owners = arrays["fitting_mask"], arrays["owners"]
    if (
        mask.dtype.kind != "b"
        or mask.shape != owners.shape
        or sorted(set(owners[mask].tolist())) != sorted(unit["fitting_games"])
        or sorted(set(owners[~mask].tolist())) != sorted(unit["held_games"])
        or len(set(owners[mask].tolist())) != 24
        or len(set(owners[~mask].tolist())) != 8
    ):
        raise ValueError("Cached game ownership differs from the sealed outer split")
    fitting, held = (
        ValuePartition(
            arrays["inputs"][m],
            arrays["targets"][m],
            arrays["potential"][m],
            tuple(int(i) for i in owners[m]),
        )
        for m in (mask, ~mask)
    )
    model, predictions, report = nested_correction(
        fitting,
        held,
        tuple(cfg["regularization"]),
        cfg["inner_folds"],
        cfg["inner_salt"],
        deadline,
    )
    # Old fitted offsets are checked only AFTER selection, never fed into inner fits.
    cached = arrays["ridge_base"][~mask]
    maximum_error = float(np.max(np.abs(predictions["current_ridge"] - cached)))
    if not np.array_equal(np.asarray(model.baseline.weights), arrays["ridge_weights"]):
        raise ValueError("Refitted coarse baseline weights differ from the original algorithm")
    if not np.allclose(predictions["current_ridge"], cached, rtol=0, atol=1e-14):
        raise ValueError("Refitted baseline forecasts differ from the sealed reference")
    report["original_coarse_weights_bitwise_identical"] = True
    report["original_coarse_forecast_maximum_roundoff"] = maximum_error
    report["off_returns_identical_baseline_forecasts"] = True
    with (directory / "selected-model.npz").open("xb") as stream:
        np.savez_compressed(stream, **model.arrays())
    with (directory / "held-predictions.npz").open("xb") as stream:
        np.savez_compressed(stream, owners=owners[~mask], targets=held.targets, **predictions)
    return {"cohort": unit["cohort"], "fold": unit["fold"], **report}


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    def means(rows: list[dict[str, Any]]) -> dict[str, float]:
        games = [g for r in rows for g in r["held"]["clipped"]["per_game"]]
        return (
            {m: sum(g["mse"][m] for g in games) / len(games) for m in games[0]["mse"]}
            if games
            else {}
        )

    keys = [(r["cohort"], g) for r in results for g in r["held_games"]]
    if len(set(keys)) != len(keys):
        raise ValueError("A whole game was counted twice in outer validation")
    return {
        "unique_held_games": len(keys),
        "primary_equal_game_clipped_mse": means(results),
        "by_cohort": {
            c: means([r for r in results if r["cohort"] == c])
            for c in sorted({r["cohort"] for r in results})
        },
        "selected_rich_regularization": [r["selected"]["regularization"] for r in results],
        "no_correction_folds": sum(not r["selected"]["correction_enabled"] for r in results),
        "baseline_preserved_in_all_folds": all(
            r["original_coarse_weights_bitwise_identical"] for r in results
        ),
        "independent_training_players": len(
            {r["cohort"].split("-standard-round-")[0] for r in results}
        ),
        "statistical_scope": "reused_saved_train_development_nested_whole_game_validation",
        "cohorts_not_pooled_for_fitting": True,
        "folds_are_not_independent_training_replicates": True,
        "prediction_target": "declared_bootstrap_return_not_victory_probability",
        "fresh_confirmation_required_before_adoption": True,
        "stronger_native_play_established": False,
    }


def run(
    root: Path, path: Path, maximum_units: int | None = None, preflight: bool = False
) -> dict[str, Any]:
    start = time.monotonic()
    cfg, units, score, sources = prepare(root, path)
    if maximum_units is not None and maximum_units < 0:
        raise ValueError("Invalid bounded unit count")
    store = ChunkJournal(root, cfg)
    final = store.workspace / "report.json"
    if final.exists():
        saved = identified(final)
        if saved["config_id"] != store.config_id:
            raise ValueError("Saved correction recipe differs")
        check_sources(root, saved["sources"])
        return saved
    if preflight:
        return {
            "status": "residual_value_preflight_pass",
            "planned_folds": len(units),
            "protected_source_files": len(sources),
            "new_games": 0,
            "actor_optimizer_steps": 0,
            "baseline_solves": 0,
            "correction_solves": 0,
        }
    deadline = start + cfg["resource_limits"]["wall_seconds"] - 10
    results: list[dict[str, Any]] = []
    new_units = 0
    with store.lock():
        for unit in units:
            key = unit["cohort"] + f"-fold-{unit['fold']}-correction"
            done = store.completed(key, unit)
            if done is None:
                if (
                    maximum_units is not None and new_units >= maximum_units
                ) or deadline - time.monotonic() < 90:
                    break
                target = store.begin(key, unit)
                tick = time.monotonic()
                result = compare_fold(root, unit, target, cfg, deadline)
                result["wall_seconds"] = time.monotonic() - tick
                done = store.commit(key, unit, result)
                new_units += 1
                print(
                    f"Saved baseline-preserving fold {len(results) + 1}/{len(units)}: "
                    f"rich correction lambda {result['selected']['regularization']}; "
                    f"withheld error {result['held']['clipped']['mse']}.",
                    flush=True,
                )
            results.append(done["result"])
            sources.update(done["sources"])
            receipt = store.path(key) / "done.json"
            sources[str(receipt.relative_to(root))] = _sha_file(receipt)
        check_sources(root, sources)
        complete = len(results) == len(units)
        destination = final if complete else store.workspace / f"progress-{len(results):04}.json"
        if destination.exists():
            saved = identified(destination)
            check_sources(root, saved["sources"])
            return saved
        outputs = write_curves(store.workspace, results, complete, len(results))
        sources.update({str(p.relative_to(root)): _sha_file(p) for p in outputs})
        body = {
            "schema_version": "native-residual-value-study-v1",
            "config_id": store.config_id,
            "recipe_path": str(path.relative_to(root)),
            "stage": cfg["stage"],
            "status": "native_residual_value_complete" if complete else "clean_pause",
            "completed_folds": len(results),
            "planned_folds": len(units),
            "new_units_this_session": new_units,
            "summary": summarize(results),
            "results": results,
            "sources": sources,
            "curves": [str(p.relative_to(root)) for p in outputs],
            "evaluation_objective": score.evaluation_objective.as_dict(),
            "training_spec_id": score.spec_id,
            "production_states_unchanged": True,
            "new_games": 0,
            "actor_optimizer_steps": 0,
            "value_optimizer_steps": 0,
            "baseline_solves": len(results) * (cfg["inner_folds"] + 1),
            "correction_solves": sum(
                cfg["inner_folds"] * len(REGULARIZATION) + int(r["selected"]["correction_enabled"])
                for r in results
            ),
            "evaluation_histories_decoded": 0,
            "game_apps_created": 0,
            "checkpoint_promoted": False,
            "adaptive_controller_allowed": False,
            "automatic_training_follows": False,
            "wall_seconds": time.monotonic() - start,
            "numerical_runtime": {
                "python": platform.python_version(),
                "numpy": importlib.metadata.version("numpy"),
            },
            "claim_scope": "saved_train_baseline_preserving_rich_correction_development_only",
        }
        result = {**body, "report_id": manifest_identifier(body)}
        atomic_json(destination, result)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--max-units", type=int)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    try:
        if args.verify and (args.max_units is not None or args.preflight):
            raise ValueError("Saved-only verification cannot request fitting or preflight")
        result = (
            verify(Path.cwd(), Path.cwd() / args.recipe)
            if args.verify
            else run(Path.cwd(), Path.cwd() / args.recipe, args.max_units, args.preflight)
        )
    except (ValueError, OSError, TimeoutError, ImportError) as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}, indent=2))
        return 1
    print(
        json.dumps({k: v for k, v in result.items() if k not in {"results", "sources"}}, indent=2)
    )
    return 0


def verify(root: Path, path: Path) -> dict[str, Any]:
    """Reconstruct selected forecasts, losses and choices without fitting or new games."""
    np = _numpy()
    cfg, units, _, sources = prepare(root, path)
    store = ChunkJournal(root, cfg)
    final = identified(store.workspace / "report.json")
    if final["status"] != "native_residual_value_complete" or final["config_id"] != store.config_id:
        raise ValueError("Require the matching complete correction comparison")
    check_sources(root, final["sources"])
    results = []
    for unit in units:
        key = unit["cohort"] + f"-fold-{unit['fold']}-correction"
        receipt = store.completed(key, unit)
        if receipt is None:
            raise ValueError("Missing saved correction fold")
        result = receipt["result"]
        directory = store.path(key)
        with (
            np.load(directory / "selected-model.npz", allow_pickle=False) as saved,
            np.load(directory / "held-predictions.npz", allow_pickle=False) as forecasts,
            np.load(root / unit["encoded"] / "encoded.npz", allow_pickle=False) as cached,
        ):
            model = CorrectedValue.restore({k: saved[k] for k in saved.files})
            held_mask = ~cached["fitting_mask"]
            held = ValuePartition(
                cached["inputs"][held_mask],
                cached["targets"][held_mask],
                cached["potential"][held_mask],
                tuple(int(x) for x in cached["owners"][held_mask]),
            )
            fit_mask = ~held_mask
            fitting = ValuePartition(
                cached["inputs"][fit_mask],
                cached["targets"][fit_mask],
                cached["potential"][fit_mask],
                tuple(int(x) for x in cached["owners"][fit_mask]),
            )
            off = CorrectedValue(model.baseline, None, model.input_dimension)
            reconstructed = {"current_ridge": off.predict(held), METHOD: model.predict(held)}
            if (
                not all(np.array_equal(v, forecasts[k]) for k, v in reconstructed.items())
                or not np.array_equal(forecasts["targets"], held.targets)
                or not np.array_equal(forecasts["owners"], np.asarray(held.owners))
                or not np.array_equal(saved["baseline_weights"], cached["ridge_weights"])
                or model.baseline.as_dict() != result["baseline"]
                or parameter_digest(model.arrays()) != result["selected"]["parameter_digest"]
            ):
                raise ValueError("Saved correction model or predictions do not reconstruct")
            chosen = select_correction(result["inner"], tuple(cfg["regularization"]))
            if (None, *cfg["regularization"])[chosen] != result["selected"]["regularization"]:
                raise ValueError("Saved whole-game correction selection differs")
            actual = {
                "unclipped": paired_errors(list(held.owners), held.targets, reconstructed),
                "clipped": paired_errors(
                    list(held.owners),
                    held.targets,
                    {k: np.clip(v, 0, 1) for k, v in reconstructed.items()},
                ),
            }
            rich = model.correction
            penalty = (
                0.0
                if rich is None
                else rich.regularization * float(rich.coefficients @ rich.coefficients)
            )
            fit_errors = errors(model.forecast(fitting.inputs, fitting.base), fitting)
            if actual != result["held"] or any(
                not np.isclose(a, b, rtol=1e-12, atol=1e-15)
                for a, b in (
                    (fit_errors["mse"], result["selected"]["fitting_mse"]),
                    (fit_errors["clipped_mse"], result["selected"]["fitting_clipped_mse"]),
                    (penalty, result["selected"]["correction_penalty"]),
                    (
                        fit_errors["mse"] + penalty,
                        result["selected"]["regularized_correction_loss"],
                    ),
                )
            ):
                raise ValueError("Saved correction errors or separate penalties differ")
        results.append(result)
    if results != final["results"] or summarize(results) != final["summary"]:
        raise ValueError("Saved correction report population differs")
    check_sources(root, sources)
    body = {
        "schema_version": "native-residual-value-saved-verification-v1",
        "analysis_report_id": final["report_id"],
        "models_verified": len(results),
        "predictions_bitwise_reconstructed": True,
        "selection_and_separate_fitting_errors_and_penalties_verified": True,
        "protected_source_files_verified": len(final["sources"]),
        "both_players_and_all_Adam_states_unchanged": True,
        "new_fits": 0,
        "new_games": 0,
        "optimizer_steps": 0,
    }
    return {**body, "report_id": manifest_identifier(body)}


if __name__ == "__main__":
    raise SystemExit(main())
