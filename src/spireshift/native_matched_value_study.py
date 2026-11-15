"""Sealed, resumable saved-TRAIN input-masking comparison and fitting curves."""

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
from spireshift.native_feedback_audit import source_cohorts
from spireshift.native_matched_value import (
    ARMS,
    CURVE_STEPS,
    INITIALIZERS,
    PRIMARY_STEP,
    SETTINGS,
    ValuePartition,
    errors,
    fit_pair,
)
from spireshift.native_matched_value_curves import aggregate_curves, write_curves
from spireshift.native_public_value import paired_errors
from spireshift.native_public_value_study_v2 import SOURCES as PRIOR_SOURCES
from spireshift.native_public_value_study_v2 import dataset
from spireshift.native_public_vocabulary import ENCODER
from spireshift.native_value_credit import fit_baseline
from spireshift.neural_combat import _numpy
from spireshift.training_objective import TrainingScoreSpec, load_training_score_spec

SOURCES = tuple(
    sorted(
        {
            *PRIOR_SOURCES,
            "native_matched_value.py",
            "native_matched_value_curves.py",
            "native_matched_value_study.py",
        }
    )
)
ENTRIES = ("compare-native-matched-value-v1.sh", "native-matched-value-v1.py")


def load_config(root: Path, path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    control = cfg.get("stage") == "short_control"
    if (
        cfg.get("schema_version") != "native-matched-input-value-config-v1"
        or cfg.get("stage") not in {"short_control", "saved_train_comparison"}
        or cfg.get("fit") != SETTINGS
        or cfg.get("curve_steps") != list(CURVE_STEPS)
        or cfg.get("primary_step") != PRIMARY_STEP
        or cfg.get("network_initializers") != list(INITIALIZERS)
        or cfg.get("maximum_vocabulary") != 1024
        or cfg.get("folds") != (2 if control else 4)
        or cfg.get("games_per_cohort") != (8 if control else 32)
        or cfg.get("cohorts")
        != (
            ["seed-2-standard-round-057-fit"]
            if control
            else [f"seed-{s}-standard-round-{r:03}-fit" for r in (57, 60) for s in (2, 3)]
        )
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
        raise ValueError("Freeze matched inputs, source bytes, snapshots, initializers and caps")
    return cast(dict[str, Any], cfg)


def prepare(
    root: Path, path: Path
) -> tuple[dict[str, Any], list[dict[str, Any]], TrainingScoreSpec, dict[str, str]]:
    cfg = load_config(root, path)
    prior = identified(root / cfg["prior_comparison"]["path"])
    audit = identified(root / cfg["source_audit"]["path"])
    if (
        prior["report_id"] != cfg["prior_comparison"]["id"]
        or prior["status"] != "native_public_value_complete"
        or prior["completed_folds"] != 16
        or prior["summary"]["held_game_predictions"] != 128
        or not prior["production_states_unchanged"]
        or audit["report_id"] != cfg["source_audit"]["id"]
        or audit["status"] != "completed_train_feedback_complete"
    ):
        raise ValueError("Require the exact completed prior comparison and TRAIN audit")
    check_sources(root, prior["sources"])
    check_sources(root, audit["sources"])
    if cfg["stage"] == "saved_train_comparison":
        control = identified(root / cfg["control_report"]["path"])
        if (
            control["report_id"] != cfg["control_report"]["id"]
            or control["status"] != "native_matched_value_complete"
            or control["stage"] != "short_control"
            or control["completed_fits"] != 6
            or control["summary"]["unique_held_games"] != 8
            or not control["production_states_unchanged"]
            or json.loads((root / control["recipe_path"]).read_text())["implementation_sha256"]
            != cfg["implementation_sha256"]
        ):
            raise ValueError("Require the matching completed short matched-input control")
        check_sources(root, control["sources"])
    cohorts, parent, sources = source_cohorts(
        root, {"completed_report": cfg["completed_report"], "stage": "completed_train_audit"}
    )
    selected = [
        dict(c, paths=c["paths"][: cfg["games_per_cohort"]])
        for key in cfg["cohorts"]
        for c in cohorts
        if c["key"] == key
    ]
    if [c["key"] for c in selected] != cfg["cohorts"]:
        raise ValueError("Missing fixed policy/player TRAIN cohort")
    score = load_training_score_spec(root / parent["training_spec"]["path"])
    if (
        score.spec_id != parent["training_spec"]["id"]
        or score.scope.character != "ironclad"
        or score.scope.ascension != 8
        or score.evaluation_objective.whole_run_budget != 128
    ):
        raise ValueError("Preserve the native A8 score and fixed terminal-victory objective")
    sources.update(prior["sources"])
    sources.update(audit["sources"])
    sources.update({str(path.relative_to(root)): _sha_file(path)})
    for field in ("prior_comparison", "source_audit", "control_report"):
        if field in cfg:
            sources[cfg[field]["path"]] = _sha_file(root / cfg[field]["path"])
    sources.update({f"src/spireshift/{n}": sha for n, sha in cfg["implementation_sha256"].items()})
    sources.update({f"scripts/{n}": sha for n, sha in cfg["entry_sha256"].items()})
    return cfg, selected, score, sources


def encode_fold(
    root: Path,
    cohort: dict[str, Any],
    score: TrainingScoreSpec,
    fold: int,
    cfg: dict[str, Any],
    directory: Path,
    deadline: float,
) -> dict[str, Any]:
    np = _numpy()
    x, coarse, phi, y, owners, runs, vocabulary, coverage = dataset(
        root, cohort, score, fold, cfg["folds"], cfg["maximum_vocabulary"], deadline
    )
    if not np.array_equal(x[:, :20], coarse):
        raise ValueError("Coarse columns are not the identical rich-input prefix")
    fitting = set(coverage["fitting_games"])
    mask = np.asarray([game in fitting for game in owners])
    ridge = fit_baseline([r for r in runs if r.seed in fitting], "public_residual_ridge", 0.001)
    constant = fit_baseline([r for r in runs if r.seed in fitting], "constant", 1.0)
    base = phi + coarse @ np.asarray(ridge.weights)
    arrays = {
        "inputs": x,
        "potential": phi,
        "targets": y,
        "owners": np.asarray(owners),
        "fitting_mask": mask,
        "ridge_base": base,
        "ridge_weights": np.asarray(ridge.weights),
        "constant": np.full(len(owners), constant.weights[0]),
    }
    for selected in (mask, ~mask):
        ValuePartition(
            x[selected],
            y[selected],
            base[selected],
            tuple(int(i) for i in arrays["owners"][selected]),
        ).validate()
    with (directory / "encoded.npz").open("xb") as stream:
        np.savez_compressed(stream, **arrays)
    atomic_json(
        directory / "vocabulary.json", {"encoder": ENCODER, "names": list(vocabulary.names)}
    )
    return {
        "cohort": cohort["key"],
        "fold": fold,
        "coverage": coverage,
        "ridge": ridge.as_dict(),
        "coarse_dimension": 20,
        "encoded_input_dimension": x.shape[1],
        "public_inputs_only": True,
        "native_games": 0,
    }


def compare_pair(
    encoded: Path, directory: Path, cfg: dict[str, Any], seed: int, deadline: float
) -> dict[str, Any]:
    np = _numpy()
    with np.load(encoded, allow_pickle=False) as source:
        arrays = {k: source[k] for k in source.files}
    mask = arrays["fitting_mask"]
    partitions = [
        ValuePartition(
            arrays["inputs"][m],
            arrays["targets"][m],
            arrays["ridge_base"][m],
            tuple(int(i) for i in arrays["owners"][m]),
        )
        for m in (mask, ~mask)
    ]
    fitting, held = partitions
    models, predictions, fit = fit_pair(
        fitting, held, 20, cfg["fit"], tuple(cfg["curve_steps"]), seed, deadline
    )
    for arm, model in models.items():
        with (directory / f"{arm}-final.npz").open("xb") as stream:
            np.savez_compressed(stream, **model, ridge_weights=arrays["ridge_weights"])
    with (directory / "held-predictions.npz").open("xb") as stream:
        np.savez_compressed(
            stream,
            owners=np.asarray(held.owners),
            targets=held.targets,
            current_ridge=held.base,
            other_game_constant=arrays["constant"][~mask],
            **predictions,
        )
    primary = {
        "current_ridge": held.base,
        "other_game_constant": arrays["constant"][~mask],
        **{arm: predictions[f"{arm}_step_{PRIMARY_STEP}"] for arm in ARMS},
    }
    return {
        "fit": fit,
        "primary_step": PRIMARY_STEP,
        "held": {
            "unclipped": paired_errors(list(held.owners), held.targets, primary),
            "clipped": paired_errors(
                list(held.owners), held.targets, {k: np.clip(p, 0, 1) for k, p in primary.items()}
            ),
        },
        "reference_errors": {
            "current_ridge": {
                label: errors(part.base, part)
                for label, part in zip(("fit", "held"), partitions, strict=True)
            }
        },
        "native_games": 0,
        "actor_optimizer_steps": 0,
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    def means(selected: list[dict[str, Any]]) -> dict[str, float]:
        games: dict[tuple[str, int], list[dict[str, float]]] = {}
        for result in selected:
            for row in result["held"]["clipped"]["per_game"]:
                games.setdefault((result["cohort"], row["game"]), []).append(row["mse"])
        methods = tuple(next(iter(games.values()))[0]) if games else ()
        return {
            method: sum(sum(r[method] for r in rows) / len(rows) for rows in games.values())
            / len(games)
            for method in methods
        }

    cohorts = sorted({r["cohort"] for r in results})
    return {
        "unique_held_games": len(
            {(r["cohort"], game) for r in results for game in r["fit"]["held_games"]}
        ),
        "held_forecasts_including_numerical_repeats": sum(
            len(r["fit"]["held_games"]) for r in results
        ),
        "primary_step": PRIMARY_STEP,
        "primary_equal_game_clipped_mse": means(results),
        "by_cohort": {key: means([r for r in results if r["cohort"] == key]) for key in cohorts},
        "by_network_initializer": {
            str(seed): means([r for r in results if r["fit"]["network_initializer"] == seed])
            for seed in INITIALIZERS
        },
        "curves": aggregate_curves(results),
        "curve_snapshots_are_not_epoch_selection": True,
        "prediction_target": "declared_bootstrap_return_not_victory_probability",
        "statistical_scope": "saved_train_development_not_independent_confirmation",
        "folds_and_numerical_repeats_are_not_independent_games": True,
        "stronger_native_play_established": False,
        "automatic_training_follows": False,
        "checkpoint_promoted": False,
        "adaptive_controller_allowed": False,
    }


def run(
    root: Path, path: Path, maximum_units: int | None = None, preflight: bool = False
) -> dict[str, Any]:
    start = time.monotonic()
    cfg, cohorts, score, sources = prepare(root, path)
    if maximum_units is not None and maximum_units < 0:
        raise ValueError("Invalid bounded unit count")
    folds = len(cohorts) * cfg["folds"]
    planned_units = folds * (1 + len(INITIALIZERS))
    store = ChunkJournal(root, cfg)
    final = store.workspace / "report.json"
    if final.exists():
        saved = identified(final)
        if saved["config_id"] != store.config_id:
            raise ValueError("Saved matched-input recipe differs")
        check_sources(root, saved["sources"])
        return saved
    if preflight:
        return {
            "status": "matched_value_preflight_pass",
            "planned_folds": folds,
            "planned_units": planned_units,
            "protected_source_files": len(sources),
            "new_games": 0,
            "numerical_fits": 0,
            "actor_optimizer_steps": 0,
        }
    deadline = start + cfg["resource_limits"]["wall_seconds"] - 10
    results: list[dict[str, Any]] = []
    new_units, encoded_count = 0, 0
    with store.lock():
        stop = False
        for cohort in cohorts:
            for fold in range(cfg["folds"]):
                key = cohort["key"] + f"-fold-{fold}"
                request = {"cohort": cohort, "fold": fold, "encoder": ENCODER}
                encoded = store.completed(key + "-encode", request)
                if encoded is None:
                    if (
                        maximum_units is not None and new_units >= maximum_units
                    ) or deadline - time.monotonic() < 90:
                        stop = True
                        break
                    target = store.begin(key + "-encode", request)
                    result = encode_fold(root, cohort, score, fold, cfg, target, deadline)
                    encoded = store.commit(key + "-encode", request, result)
                    new_units += 1
                    print(f"Prepared matched-input fold {encoded_count + 1}/{folds}.", flush=True)
                encoded_count += 1
                sources.update(encoded["sources"])
                encoded_path = store.path(key + "-encode")
                encoded_receipt = str((encoded_path / "done.json").relative_to(root))
                sources[encoded_receipt] = _sha_file(root / encoded_receipt)
                for seed in INITIALIZERS:
                    fit_key = key + f"-init-{seed}"
                    fit_request = {"encoding_report_id": encoded["report_id"], "initializer": seed}
                    done = store.completed(fit_key, fit_request)
                    if done is None:
                        if (
                            maximum_units is not None and new_units >= maximum_units
                        ) or deadline - time.monotonic() < 90:
                            stop = True
                            break
                        target = store.begin(fit_key, fit_request)
                        result = {
                            "cohort": cohort["key"],
                            "fold": fold,
                            **compare_pair(
                                encoded_path / "encoded.npz", target, cfg, seed, deadline
                            ),
                        }
                        done = store.commit(
                            fit_key,
                            fit_request,
                            result,
                            {encoded_receipt: sources[encoded_receipt]},
                        )
                        new_units += 1
                        print(
                            f"Saved matched pair {len(results) + 1}/{folds * len(INITIALIZERS)}: "
                            f"step {PRIMARY_STEP} withheld error "
                            f"{result['held']['clipped']['mse']}. "
                            "Fitting/error/penalty curves saved; no games or player updates.",
                            flush=True,
                        )
                    results.append(done["result"])
                    sources.update(done["sources"])
                    receipt = store.path(fit_key) / "done.json"
                    sources[str(receipt.relative_to(root))] = _sha_file(receipt)
                if stop:
                    break
            if stop:
                break
        check_sources(root, sources)
        complete = len(results) == folds * len(INITIALIZERS)
        completed_units = encoded_count + len(results)
        destination = final if complete else store.workspace / f"progress-{completed_units:04}.json"
        if destination.exists():
            saved = identified(destination)
            if saved["config_id"] != store.config_id:
                raise ValueError("Saved progress recipe differs")
            check_sources(root, saved["sources"])
            return saved
        outputs = write_curves(store.workspace, results, complete, completed_units)
        sources.update({str(p.relative_to(root)): _sha_file(p) for p in outputs})
        body = {
            "schema_version": "native-matched-input-value-study-v1",
            "config_id": store.config_id,
            "recipe_path": str(path.relative_to(root)),
            "stage": cfg["stage"],
            "status": "native_matched_value_complete" if complete else "clean_pause",
            "completed_encodings": encoded_count,
            "completed_fits": len(results),
            "planned_fits": folds * len(INITIALIZERS),
            "planned_units": planned_units,
            "new_units_this_session": new_units,
            "results": results,
            "summary": summarize(results),
            "sources": sources,
            "curves": [str(p.relative_to(root)) for p in outputs],
            "evaluation_objective": score.evaluation_objective.as_dict(),
            "training_spec_id": score.spec_id,
            "treatment": "mask_extra_standardized_public_inputs_only",
            "matched_architecture_initialization_scaling_optimizer_and_games": True,
            "more_active_inputs_still_change_effective_capacity": True,
            "production_states_unchanged": True,
            "new_games": 0,
            "actor_optimizer_steps": 0,
            "value_optimizer_steps": 2 * cfg["fit"]["epochs"] * len(results),
            "evaluation_histories_decoded": 0,
            "teacher_branches_used": 0,
            "game_apps_created": 0,
            "wall_seconds": time.monotonic() - start,
            "numerical_runtime": {
                "python": platform.python_version(),
                "numpy": importlib.metadata.version("numpy"),
                "matplotlib": importlib.metadata.version("matplotlib"),
            },
            "claim_scope": "matched_saved_train_value_forecast_development_only",
        }
        result = {**body, "report_id": manifest_identifier(body)}
        atomic_json(destination, result)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--max-units", type=int)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    try:
        result = run(Path.cwd(), Path.cwd() / args.recipe, args.max_units, args.preflight)
    except (ValueError, OSError, TimeoutError, ImportError) as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}, indent=2))
        return 1
    print(
        json.dumps({k: v for k, v in result.items() if k not in {"results", "sources"}}, indent=2)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
