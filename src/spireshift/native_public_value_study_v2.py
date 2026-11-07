"""Balanced saved-TRAIN public-state value comparison. No native launch or PPO."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, score_episode
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_feedback_audit import SOURCES as FEEDBACK_SOURCES
from spireshift.native_feedback_audit import source_cohorts
from spireshift.native_public_state import public_state_facts
from spireshift.native_public_value import fit_value, paired_errors
from spireshift.native_public_vocabulary import ENCODER, PublicVocabulary
from spireshift.native_shop_policy import ShopNavigation
from spireshift.native_value_credit import (
    ValueRun,
    fit_baseline,
    fold_assignment,
    public_value_features,
)
from spireshift.neural_combat import _numpy
from spireshift.training_objective import TrainingScoreSpec, load_training_score_spec

SOURCES = tuple(
    sorted(
        set(
            (
                *FEEDBACK_SOURCES,
                "native_public_state.py",
                "native_public_value.py",
                "native_public_value_study.py",
                "native_public_value_study_v2.py",
                "native_public_vocabulary.py",
            )
        )
    )
)
SETTINGS = {"hidden": 32, "epochs": 24, "learning_rate": 0.003, "l2": 0.0001, "gradient_clip": 5.0}


def observations(
    root: Path, path: str, score: TrainingScoreSpec
) -> Iterator[tuple[int, float, dict[str, Any]]]:
    """One raw game at a time; only sealed, ordinary TRAIN games offering a choice."""
    p = root / path
    header = json.loads(p.read_text())
    binding = header["binding"]
    if binding.get("partition") != "train" or binding.get("panel_purpose") != "training":
        raise ValueError("Public value study may only open TRAIN histories")
    case = read_native_episode(p, binding)
    if (
        case.get("status") != "terminal"
        or case.get("privileged_fixture") is not False
        or case.get("recovered") is not False
        or case.get("native_ending_evidence_agrees") is not True
    ):
        raise ValueError("Value supervision requires a clean genuine complete game")
    target = score_episode(case, binding["seed_id"], score)["training_return"]
    navigation = ShopNavigation()
    for row in case["decisions"]:
        public, choice = row["public_input"], row["choice"]
        effective, _, forced = navigation.view(public)
        navigation.advance(public, choice["action_index"])
        if not forced and len(effective["candidates"]) > 1:
            yield binding["seed_id"], target, effective


def dataset(
    root: Path,
    cohort: dict[str, Any],
    score: TrainingScoreSpec,
    fold: int,
    folds: int,
    maximum: int,
    deadline: float,
) -> tuple[Any, Any, Any, Any, list[int], list[ValueRun], PublicVocabulary, dict[str, Any]]:
    """Freeze vocabulary on fitting games before encoding any held-game facts."""
    np = _numpy()
    runs: list[ValueRun] = []
    paths = cohort["paths"]
    ids = [json.loads((root / p).read_text())["binding"]["seed_id"] for p in paths]
    if len(set(ids)) != len(ids):
        raise ValueError("Repeated complete game in critic cohort")
    # Same deterministic whole-game assignment as the historical credit predictor.
    dummy = [ValueRun(s, cohort["round"], 0.0, ((0.0,) * 20,), (0.0,), (0.0,), (2,)) for s in ids]
    assignment = fold_assignment(dummy, folds, "native-public-value-whole-game-v1")
    fitting = {s for s in ids if assignment[s] != fold}

    def fitting_games() -> Iterator[Iterator[dict[str, float]]]:
        for path, game in zip(paths, ids, strict=True):
            if time.monotonic() >= deadline:
                raise TimeoutError("Public vocabulary fit reached its finite cap")
            if game in fitting:
                yield (public_state_facts(p) for _, _, p in observations(root, path, score))

    vocabulary = PublicVocabulary.fit(fitting_games(), maximum)
    owners, dense, coarse, potentials, targets = [], [], [], [], []
    coverage: dict[str, Counter[str]] = {"fit": Counter(), "held": Counter()}
    families: Counter[str] = Counter()
    for path in paths:
        if time.monotonic() >= deadline:
            raise TimeoutError("Public-state encoding reached its finite cap")
        values, phis, choices = [], [], []
        seed, target = -1, -1.0
        for seed, target, public in observations(root, path, score):
            facts = public_state_facts(public)
            vector, covered = vocabulary.encode(facts)
            x, phi = public_value_features(public, score)
            owners.append(seed)
            targets.append(target)
            potentials.append(phi)
            dense.append((*x, *vector))
            coarse.append(x)
            values.append(x)
            phis.append(phi)
            choices.append(len(public["candidates"]))
            coverage["fit" if seed in fitting else "held"].update(covered)
            families[public["context"]["interaction"]["kind"]] += 1
        if not values:
            raise ValueError("Clean TRAIN game has no choice-bearing state")
        runs.append(
            ValueRun(
                seed,
                cohort["round"],
                target,
                tuple(values),
                tuple(phis),
                (0.0,) * len(values),
                tuple(choices),
            )
        )
    return (
        np.asarray(dense),
        np.asarray(coarse),
        np.asarray(potentials),
        np.asarray(targets),
        owners,
        runs,
        vocabulary,
        {
            "facts": {k: dict(v) for k, v in coverage.items()},
            "families": dict(families),
            "fitting_games": sorted(fitting),
            "held_games": sorted(set(ids) - fitting),
            "vocabulary_size": len(vocabulary.names),
            "vocabulary_fit_uses_held_games": False,
        },
    )


def compare_fold(
    root: Path,
    cohort: dict[str, Any],
    score: TrainingScoreSpec,
    fold: int,
    cfg: dict[str, Any],
    target_dir: Path,
    deadline: float,
) -> dict[str, Any]:
    np = _numpy()
    x, coarse, phi, y, owners, runs, vocabulary, coverage = dataset(
        root, cohort, score, fold, cfg["folds"], cfg["maximum_vocabulary"], deadline
    )
    fitting = set(coverage["fitting_games"])
    mask = np.asarray([s in fitting for s in owners])
    fitting_runs = [r for r in runs if r.seed in fitting]
    held_runs = [r for r in runs if r.seed not in fitting]
    fit_owners = [s for s in owners if s in fitting]
    held_owners = [s for s in owners if s not in fitting]
    ridge = fit_baseline(fitting_runs, "public_residual_ridge", 0.001)
    constant = fit_baseline(fitting_runs, "constant", 1.0)
    predictions = {
        "current_ridge": np.asarray([p for r in held_runs for p in ridge.predict(r)]),
        "other_game_constant": np.asarray([p for r in held_runs for p in constant.predict(r)]),
        "current_progress": phi[~mask],
    }
    fits = {}
    atomic_json(
        target_dir / "vocabulary.json", {"encoder": ENCODER, "names": list(vocabulary.names)}
    )
    for name, inputs in (("coarse_mlp", coarse), ("structured_mlp", x)):
        model, fit = fit_value(
            inputs[mask],
            coarse[mask],
            phi[mask],
            y[mask],
            fit_owners,
            ridge.weights,
            cfg["fit"],
            20261019 + fold,
            deadline,
        )
        predictions[name] = model.predict(inputs[~mask], coarse[~mask], phi[~mask], held_owners)
        fits[name] = fit
        with (target_dir / f"{name}.npz").open("xb") as stream:
            np.savez_compressed(stream, **model.arrays())
    with (target_dir / "held-predictions.npz").open("xb") as stream:
        np.savez_compressed(stream, owners=np.asarray(held_owners), targets=y[~mask], **predictions)
    return {
        "cohort": cohort["key"],
        "numerical_seed": cohort["numerical_seed"],
        "round": cohort["round"],
        "fold": fold,
        "coverage": coverage,
        "fits": fits,
        "ridge": ridge.as_dict(),
        "held": paired_errors(held_owners, y[~mask], predictions),
        "native_games": 0,
        "actor_optimizer_steps": 0,
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [row for r in results for row in r["held"]["per_game"]]
    methods = tuple(rows[0]["mse"]) if rows else ()
    mse = {m: sum(row["mse"][m] for row in rows) / len(rows) for m in methods}
    return {
        "held_game_predictions": len(rows),
        "equal_game_mse": mse,
        "by_cohort": {
            key: {
                method: sum(
                    row["mse"][method]
                    for r in results
                    if r["cohort"] == key
                    for row in r["held"]["per_game"]
                )
                / sum(r["held"]["games"] for r in results if r["cohort"] == key)
                for method in methods
            }
            for key in sorted({r["cohort"] for r in results})
        },
        "structured_beats_current_ridge": bool(rows)
        and mse["structured_mlp"] < mse["current_ridge"],
        "stronger_native_play_established": False,
        "prediction_target": "declared_bootstrap_return_not_victory_probability",
        "automatic_training_follows": False,
        "checkpoint_promoted": False,
        "adaptive_controller_allowed": False,
    }


def load_config(root: Path, path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    control = cfg.get("stage") == "short_control"
    if (
        cfg.get("schema_version") != "native-public-value-study-config-v2"
        or cfg.get("stage") not in {"short_control", "saved_train_comparison"}
        or cfg.get("fit") != SETTINGS
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
        or cfg.get("entry_sha256")
        != {
            n: _sha_file(root / "scripts" / n)
            for n in ("compare-native-public-value-v2.sh", "native-public-value-v2.py")
        }
        or cfg.get("resource_limits")
        != {
            "wall_seconds": 240 if control else 900,
            "cpu_seconds": 240 if control else 900,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 500000000,
        }
    ):
        raise ValueError("Freeze public-value scope, fitting settings, sources and finite caps")
    return cast(dict[str, Any], cfg)


def run(root: Path, path: Path, maximum_units: int | None = None) -> dict[str, Any]:
    cfg = load_config(root, path)
    if maximum_units is not None and maximum_units < 1:
        raise ValueError("Invalid bounded offline unit count")
    start = time.monotonic()
    audit = identified(root / cfg["source_audit"]["path"])
    if (
        audit["report_id"] != cfg["source_audit"]["id"]
        or audit["status"] != "completed_train_feedback_complete"
    ):
        raise ValueError("Require the completed source TRAIN audit")
    check_sources(root, audit["sources"])
    if cfg["stage"] == "saved_train_comparison":
        control = identified(root / cfg["control_report"]["path"])
        control_cfg = load_config(root, root / control["recipe_path"])
        if (
            control["report_id"] != cfg["control_report"]["id"]
            or control["status"] != "native_public_value_complete"
            or control["stage"] != "short_control"
            or control["completed_folds"] != 2
            or control["summary"]["held_game_predictions"] != 8
            or not control["production_states_unchanged"]
            or control_cfg["implementation_sha256"] != cfg["implementation_sha256"]
        ):
            raise ValueError("Require the matching completed short public-value control")
        check_sources(root, control["sources"])
    cohorts, parent, sources = source_cohorts(
        root, {"completed_report": cfg["completed_report"], "stage": "completed_train_audit"}
    )
    sources.update(
        {
            str(path.relative_to(root)): _sha_file(path),
            cfg["source_audit"]["path"]: _sha_file(root / cfg["source_audit"]["path"]),
        }
    )
    sources.update({f"src/spireshift/{n}": sha for n, sha in cfg["implementation_sha256"].items()})
    sources.update({f"scripts/{n}": sha for n, sha in cfg["entry_sha256"].items()})
    cohorts = [
        dict(c, paths=c["paths"][: cfg["games_per_cohort"]])
        for key in cfg["cohorts"]
        for c in cohorts
        if c["key"] == key
    ]
    if [c["key"] for c in cohorts] != cfg["cohorts"]:
        raise ValueError("Missing frozen TRAIN cohort")
    score = load_training_score_spec(root / parent["training_spec"]["path"])
    if (
        score.spec_id != parent["training_spec"]["id"]
        or score.evaluation_objective.whole_run_budget != 128
        or score.scope.character != "ironclad"
        or score.scope.ascension != 8
    ):
        raise ValueError("Preserve the frozen native A8 objective and whole-run budget")
    store = ChunkJournal(root, cfg)
    final = store.workspace / "report.json"
    if final.exists():
        saved = identified(final)
        check_sources(root, saved["sources"])
        return saved
    deadline = start + cfg["resource_limits"]["wall_seconds"] - 10
    results: list[dict[str, Any]] = []
    new_units = 0
    with store.lock():
        for cohort in cohorts:
            for fold in range(cfg["folds"]):
                key = cohort["key"] + f"-fold-{fold}"
                request = {
                    "cohort": cohort,
                    "fold": fold,
                    "encoder": ENCODER,
                    "treatment": "offline_value_representation_only",
                }
                done = store.completed(key, request)
                if done is None:
                    if (
                        maximum_units is not None and new_units >= maximum_units
                    ) or deadline - time.monotonic() < 90:
                        break
                    target_dir = store.begin(key, request)
                    result = compare_fold(root, cohort, score, fold, cfg, target_dir, deadline)
                    done = store.commit(key, request, result)
                    new_units += 1
                    print(
                        f"Saved value fold {len(results) + 1}/{len(cohorts) * cfg['folds']}: "
                        f"{result['held']['games']} held games; MSE {result['held']['mse']}. "
                        "No games or player changes.",
                        flush=True,
                    )
                results.append(done["result"])
                receipt = store.path(key) / "done.json"
                sources[str(receipt.relative_to(root))] = _sha_file(receipt)
                sources.update(done["sources"])
            if (
                maximum_units is not None and new_units >= maximum_units
            ) or deadline - time.monotonic() < 90:
                break
        check_sources(root, sources)
        complete = len(results) == len(cohorts) * cfg["folds"]
        body = {
            "schema_version": "native-public-value-study-v2",
            "config_id": manifest_identifier(cfg),
            "recipe_path": str(path.relative_to(root)),
            "stage": cfg["stage"],
            "status": "native_public_value_complete" if complete else "clean_pause",
            "completed_folds": len(results),
            "planned_folds": len(cohorts) * cfg["folds"],
            "results": results,
            "summary": summarize(results),
            "sources": sources,
            "source_audit_id": audit["report_id"],
            "training_spec_id": score.spec_id,
            "evaluation_objective": score.evaluation_objective.as_dict(),
            "whole_game_cross_fitting": True,
            "new_games": 0,
            "actor_optimizer_steps": 0,
            "production_states_unchanged": True,
            "evaluation_histories_decoded": 0,
            "teacher_branches_used": 0,
            "game_apps_created": 0,
            "wall_seconds": time.monotonic() - start,
            "claim_scope": "saved_train_policy_specific_whole_game_value_prediction",
        }
        result = {**body, "report_id": manifest_identifier(body)}
        atomic_json(final if complete else store.workspace / "progress.json", result)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--max-units", type=int)
    args = parser.parse_args()
    root = Path.cwd()
    try:
        result = run(root, root / args.recipe, args.max_units)
    except (ValueError, OSError, TimeoutError) as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}, indent=2))
        return 1
    print(
        json.dumps({k: v for k, v in result.items() if k not in {"results", "sources"}}, indent=2)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
