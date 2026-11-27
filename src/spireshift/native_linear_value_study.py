"""Restartable nested whole-game ridge comparison using sealed saved TRAIN inputs."""

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
from spireshift.native_linear_value import (
    ARMS,
    INNER_FOLDS,
    REGULARIZATION,
    SALT,
    nested_pair,
)
from spireshift.native_linear_value_curves import write_curves
from spireshift.native_matched_value import ValuePartition
from spireshift.native_public_value import paired_errors
from spireshift.neural_combat import _numpy
from spireshift.training_objective import TrainingScoreSpec, load_training_score_spec

SOURCES = (
    "native_linear_value.py",
    "native_linear_value_curves.py",
    "native_linear_value_study.py",
)
ENTRIES = ("compare-native-linear-value-v1.sh", "native-linear-value-v1.py")
COHORTS = [f"seed-{s}-standard-round-{r:03}-fit" for r in (57, 60) for s in (2, 3)]
PARENT_ID = "sha256:759c8fa5e9a23b16fb2b6cd5e06834d8e9ec909e9aec5fb6aaa6db5a313ba49c"


def load_config(root: Path, path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    control = cfg.get("stage") == "short_control"
    if (
        cfg.get("schema_version") != "native-linear-value-config-v1"
        or cfg.get("stage") not in {"short_control", "saved_train_comparison"}
        or cfg.get("regularization") != list(REGULARIZATION)
        or cfg.get("inner_folds") != INNER_FOLDS
        or cfg.get("inner_salt") != SALT
        or cfg.get("cohorts") != (COHORTS[:1] if control else COHORTS)
        or cfg.get("outer_folds") != ([0] if control else [0, 1, 2, 3])
        or cfg.get("parent_comparison", {}).get("id") != PARENT_ID
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
        raise ValueError("Freeze linear grid, whole-game folds, source bytes, scope and caps")
    return cast(dict[str, Any], cfg)


def prepare(
    root: Path, path: Path
) -> tuple[dict[str, Any], list[dict[str, Any]], TrainingScoreSpec, dict[str, str]]:
    cfg = load_config(root, path)
    parent_path = root / cfg["parent_comparison"]["path"]
    parent = identified(parent_path)
    if (
        parent["report_id"] != cfg["parent_comparison"]["id"]
        or parent["status"] != "native_matched_value_complete"
        or parent["completed_encodings"] != 16
        or parent["completed_fits"] != 48
        or parent["summary"]["unique_held_games"] != 128
        or not parent["production_states_unchanged"]
        or parent["new_games"] != 0
    ):
        raise ValueError("Require the completed sealed 128-TRAIN-game matched comparison")
    sources = dict(parent["sources"])
    sources[str(parent_path.relative_to(root))] = _sha_file(parent_path)
    check_sources(root, sources)
    score = load_training_score_spec(root / cfg["training_spec"]["path"])
    if (
        score.spec_id != cfg["training_spec"]["id"]
        or score.spec_id != parent["training_spec_id"]
        or score.evaluation_objective.as_dict() != parent["evaluation_objective"]
        or score.scope.character != "ironclad"
        or score.scope.ascension != 8
        or score.evaluation_objective.whole_run_budget != 128
    ):
        raise ValueError("Preserve the A8 bootstrap target and terminal-victory objective")
    if cfg["stage"] == "saved_train_comparison":
        control = identified(root / cfg["control_report"]["path"])
        if (
            control["report_id"] != cfg["control_report"]["id"]
            or control["status"] != "native_linear_value_complete"
            or control["stage"] != "short_control"
            or control["completed_folds"] != 1
            or not control["production_states_unchanged"]
            or json.loads((root / control["recipe_path"]).read_text())["implementation_sha256"]
            != cfg["implementation_sha256"]
        ):
            raise ValueError("Require the matching completed real-input linear control")
        check_sources(root, control["sources"])
        sources[cfg["control_report"]["path"]] = _sha_file(root / cfg["control_report"]["path"])
    units = []
    for cohort in cfg["cohorts"]:
        for fold in cfg["outer_folds"]:
            key = f"{cohort}-fold-{fold}-encode"
            encoded = parent_path.parent / "chunks" / key
            receipt = identified(encoded / "done.json")
            if (
                receipt["config_id"] != parent["config_id"]
                or receipt["key"] != key
                or receipt["result"]["cohort"] != cohort
                or receipt["result"]["fold"] != fold
                or receipt["result"]["coverage"]["vocabulary_fit_uses_held_games"] is not False
            ):
                raise ValueError("Inherited encoding has another whole-game provenance")
            for name in ("done.json", "encoded.npz", "vocabulary.json"):
                relative = str((encoded / name).relative_to(root))
                if sources.get(relative) != _sha_file(encoded / name):
                    raise ValueError("Inherited input cache is not sealed by its completed parent")
            units.append(
                {
                    "cohort": cohort,
                    "fold": fold,
                    "encoded": str(encoded.relative_to(root)),
                    "encoding_report_id": receipt["report_id"],
                    "fitting_games": receipt["result"]["coverage"]["fitting_games"],
                    "held_games": receipt["result"]["coverage"]["held_games"],
                }
            )
    sources.update({str(path.relative_to(root)): _sha_file(path)})
    sources.update({f"src/spireshift/{n}": s for n, s in cfg["implementation_sha256"].items()})
    sources.update({f"scripts/{n}": s for n, s in cfg["entry_sha256"].items()})
    sources[cfg["training_spec"]["path"]] = _sha_file(root / cfg["training_spec"]["path"])
    return cfg, units, score, sources


def compare_fold(
    root: Path, unit: dict[str, Any], directory: Path, cfg: dict[str, Any], deadline: float
) -> dict[str, Any]:
    np = _numpy()
    with np.load(root / unit["encoded"] / "encoded.npz", allow_pickle=False) as source:
        arrays = {name: source[name] for name in source.files}
    mask = arrays["fitting_mask"]
    owners = arrays["owners"]
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
    models, predictions, report = nested_pair(
        fitting,
        held,
        tuple(cfg["regularization"]),
        cfg["inner_folds"],
        cfg["inner_salt"],
        deadline,
    )
    for arm, model in models.items():
        with (directory / f"{arm}.npz").open("xb") as stream:
            np.savez_compressed(stream, **model.arrays())
    # The old outer-fit ridge is a frozen comparison only, never an inner offset.
    predictions["current_ridge"] = arrays["ridge_base"][~mask]
    predictions["other_game_constant"] = arrays["constant"][~mask]
    with (directory / "held-predictions.npz").open("xb") as stream:
        np.savez_compressed(stream, owners=owners[~mask], targets=held.targets, **predictions)
    report["held"] = {
        "unclipped": paired_errors(list(held.owners), held.targets, predictions),
        "clipped": paired_errors(
            list(held.owners), held.targets, {k: np.clip(v, 0, 1) for k, v in predictions.items()}
        ),
    }
    return {"cohort": unit["cohort"], "fold": unit["fold"], **report}


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    def means(rows: list[dict[str, Any]]) -> dict[str, float]:
        games = [game for r in rows for game in r["held"]["clipped"]["per_game"]]
        if not games:
            return {}
        return {
            method: sum(g["mse"][method] for g in games) / len(games) for method in games[0]["mse"]
        }

    keys = [(r["cohort"], g) for r in results for g in r["held_games"]]
    if len(set(keys)) != len(keys):
        raise ValueError("A whole game was counted twice in outer validation")
    return {
        "unique_held_games": len(keys),
        "primary_equal_game_clipped_mse": means(results),
        "by_cohort": {
            key: means([r for r in results if r["cohort"] == key])
            for key in sorted({r["cohort"] for r in results})
        },
        "selected_regularization": {
            arm: [r["selected"][arm]["regularization"] for r in results] for arm in ARMS
        },
        "statistical_scope": "reused_saved_train_development_nested_whole_game_validation",
        "independent_training_players": len(
            {r["cohort"].split("-standard-round-")[0] for r in results}
        ),
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
            raise ValueError("Saved linear recipe differs")
        check_sources(root, saved["sources"])
        return saved
    if preflight:
        return {
            "status": "linear_value_preflight_pass",
            "planned_folds": len(units),
            "protected_source_files": len(sources),
            "new_games": 0,
            "actor_optimizer_steps": 0,
            "linear_solves": 0,
        }
    deadline = start + cfg["resource_limits"]["wall_seconds"] - 10
    results: list[dict[str, Any]] = []
    new_units = 0
    with store.lock():
        for unit in units:
            key = unit["cohort"] + f"-fold-{unit['fold']}-linear"
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
                    f"Saved whole-game linear fold {len(results) + 1}/{len(units)}: "
                    f"selected ridge strengths "
                    f"{ {arm: result['selected'][arm]['regularization'] for arm in ARMS} }; "
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
            "schema_version": "native-linear-value-study-v1",
            "config_id": store.config_id,
            "recipe_path": str(path.relative_to(root)),
            "stage": cfg["stage"],
            "status": "native_linear_value_complete" if complete else "clean_pause",
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
            "linear_solves": len(results) * 2 * (cfg["inner_folds"] * len(REGULARIZATION) + 1),
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
            "claim_scope": "nested_saved_train_public_linear_value_development_only",
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
