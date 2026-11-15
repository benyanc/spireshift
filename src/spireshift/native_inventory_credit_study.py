"""Finite saved-TRAIN credit diagnosis; separate sealed policy cohorts, no player fitting."""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_inventory_credit_data import alias_diagnostics, extract
from spireshift.native_inventory_credit_math import (
    METHODS,
    PENALTY,
    SALT,
    credit_diagnostics,
    forecasts,
)
from spireshift.native_inventory_credit_report import restore_forecasts, summarize
from spireshift.native_structured_plan import plan, request
from spireshift.neural_combat import _numpy
from spireshift.training_objective import load_training_score_spec

SOURCES = (
    "native_inventory_credit_features.py",
    "native_inventory_credit_math.py",
    "native_inventory_credit_data.py",
    "native_inventory_credit_report.py",
    "native_inventory_credit_study.py",
    "native_residual_value.py",
    "native_linear_value.py",
    "native_matched_value.py",
    "native_public_value.py",
    "native_value_credit.py",
)
ENTRIES = ("diagnose-native-inventory-credit-v2.py", "diagnose-native-inventory-credit-v2.sh")
COHORTS = tuple(
    f"fit-p{player}-{arm}-r{round:02d}"
    for round in (1, 2)
    for player in (2, 3)
    for arm in ("unchanged", "hashed", "named")
)


def prepare(root: Path, path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    if (
        cfg.get("schema_version") != "native-inventory-credit-diagnosis-config-v1"
        or cfg.get("cohorts") != list(COHORTS)
        or cfg.get("methods") != list(METHODS)
        or cfg.get("inventory_regularization") != PENALTY
        or cfg.get("folds") != 4
        or cfg.get("fold_salt") != SALT
        or cfg.get("session_limits")
        != {
            "wall_seconds": 900,
            "cpu_seconds": 900,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 500000000,
        }
        or cfg.get("implementation_sha256")
        != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("entry_sha256") != {n: _sha_file(root / "scripts" / n) for n in ENTRIES}
    ):
        raise ValueError("Freeze the finite inventory-credit diagnosis and implementation")
    report = identified(root / cfg["source_report"]["path"])
    audit = identified(root / cfg["source_audit"]["path"])
    if (
        report["report_id"] != cfg["source_report"]["id"]
        or report["status"] != "native_structured_comparison_complete"
        or report["games_recorded"] != 640
        or report["failed_games"] != 0
        or audit["report_id"] != cfg["source_audit"]["id"]
        or audit["source_report_id"] != report["report_id"]
        or audit["games_verified"] != 640
        or not audit["original_full_states_and_Adam_unchanged"]
    ):
        raise ValueError("Require the completed, audited, unchanged structured-input experiment")
    source = json.loads((root / report["recipe_path"]).read_text())
    if manifest_identifier(source) != report["config_id"]:
        raise ValueError("Source recipe identity differs")
    score = load_training_score_spec(root / source["training_spec"]["path"])
    if (
        score.spec_id != source["training_spec"]["id"]
        or score.scope.character != "ironclad"
        or score.scope.ascension != 8
        or score.evaluation_objective.primary != "terminal_victory"
        or score.evaluation_objective.whole_run_budget != 128
    ):
        raise ValueError("Preserve Ironclad/A8, the bootstrap target and full-victory objective")
    manifest = identified(root / source["seed_manifest"]["path"], "manifest_id")
    if manifest["manifest_id"] != source["seed_manifest"]["id"]:
        raise ValueError("Saved TRAIN manifest differs")
    sources = dict(report["sources"])
    sources.update(audit["sources"])
    for ref in (cfg["source_report"], cfg["source_audit"]):
        sources[ref["path"]] = _sha_file(root / ref["path"])
    sources[str(path.relative_to(root))] = _sha_file(path)
    sources.update({f"src/spireshift/{n}": s for n, s in cfg["implementation_sha256"].items()})
    sources.update({f"scripts/{n}": s for n, s in cfg["entry_sha256"].items()})
    check_sources(root, sources)
    done: dict[str, dict[str, Any]] = {}
    tasks: dict[str, dict[str, Any]] = {}
    for task in plan(source, manifest["seeds"]):
        if task["kind"] == "evaluate":
            break  # No evaluation episode is decoded or supplies a fitting target.
        rel = f"{source['workspace']}/chunks/{task['key']}/done.json"
        if rel not in sources:
            raise ValueError("Source TRAIN unit lacks the completed audit seal")
        sealed = identified(root / rel)
        if sealed["config_id"] != report["config_id"] or sealed[
            "request_id"
        ] != manifest_identifier(request(task, done)):
            raise ValueError("Source cohort predecessor or training ownership changed")
        done[task["key"]] = sealed["result"]
        if task["kind"] == "fit":
            tasks[task["key"]] = task
    if set(tasks) != set(COHORTS):
        raise ValueError("Do not choose successful source cohorts after inspecting errors")
    return {
        "config": cfg,
        "source": source,
        "score": score,
        "done": done,
        "tasks": tasks,
        "sources": sources,
        "source_report": report,
    }


def analyze(
    root: Path, context: dict[str, Any], key: str, directory: Path, deadline: float
) -> dict[str, Any]:
    started = time.monotonic()
    task, done = context["tasks"][key], context["done"]
    model_id = done[task["state"]]["model_id"]
    paths = [p for collection in task["collections"] for p in done[collection]["paths"]]
    data, names, metadata = extract(
        root, task, context["source"], model_id, paths, context["score"], directory, deadline
    )
    atomic_json(directory / "metadata.json", metadata)
    prediction, forecast = forecasts(data, names, task["round"], directory, deadline)
    credit = credit_diagnostics(data, prediction)
    source_dir = root / context["source"]["workspace"] / "chunks" / key
    original_credit = json.loads((source_dir / "credit.json").read_text())
    original_work = json.loads((source_dir / "work.json").read_text())
    if (
        forecast["coarse_folds"] != original_credit["cross_fit"]
        or metadata["decisions"] != original_credit["decisions"]
        or metadata["choice_decisions"] != original_credit["choice_decisions"]
        or len(metadata["outcomes"]) != 32
        or original_credit["clean_complete_training_games"] != 32
        or any(
            not math.isclose(credit[f"production_{k}"], original_work[k], rel_tol=0, abs_tol=1e-12)
            for k in ("raw_advantage_mean", "raw_advantage_std")
        )
        or any(
            not math.isclose(
                forecast["current_prediction_metrics"][k], value, rel_tol=0, abs_tol=1e-12
            )
            for k, value in original_credit["prediction_quality"].items()
            if type(value) in (int, float)
        )
    ):
        raise ValueError("The original production credit does not reconstruct")
    np = _numpy()
    with (directory / "forecasts.npz").open("xb") as handle:
        np.savez_compressed(handle, **prediction)
    restoration = restore_forecasts(directory, metadata, forecast["coarse_folds"], task["round"])
    result = {
        "cohort": key,
        "player": task["player"],
        "arm": task["arm"],
        "round": task["round"],
        "behavior_model_id": model_id,
        "outcomes": metadata["outcomes"],
        "decisions": metadata["decisions"],
        "choice_decisions": metadata["choice_decisions"],
        "inventory_coverage": {
            k: metadata[k]
            for k in (
                "distinct_owned_card_definitions",
                "distinct_owned_relic_definitions",
                "rows_with_public_relic_counter_view",
            )
        },
        "forecast": forecast,
        "credit": credit,
        "aliases": alias_diagnostics(data),
        "original_production_folds_coefficients_metrics_and_credit_reproduced": True,
        "saved_model_restoration": restoration,
        "wall_seconds": time.monotonic() - started,
        "games_launched": 0,
        "player_Adam_updates": 0,
    }
    atomic_json(directory / "result.json", result)
    return result


def run(
    root: Path, path: Path, *, max_new_cohorts: int | None = None, session_seconds: int = 900
) -> dict[str, Any]:
    started = time.monotonic()
    if (
        type(session_seconds) is not int
        or not 180 <= session_seconds <= 900
        or (
            max_new_cohorts is not None
            and (type(max_new_cohorts) is not int or not 1 <= max_new_cohorts <= len(COHORTS))
        )
    ):
        raise ValueError("Use a finite positive cohort count and 3–15 minute session cap")
    context = prepare(root, path)
    cfg = context["config"]
    store = ChunkJournal(root, cfg)
    deadline = started + session_seconds - 10
    completed, new = [], 0
    with store.lock():
        final = store.workspace / "report.json"
        if final.exists():
            final_report = identified(final)
            if final_report["config_id"] != store.config_id:
                raise ValueError("Completed diagnosis belongs to another recipe")
            check_sources(root, final_report["sources"])
            return final_report
        generated: dict[str, str] = {}
        for key in COHORTS:
            task = context["tasks"][key]
            req = {"source_report_id": context["source_report"]["report_id"], "task": task}
            cached = store.completed(key, req)
            if cached is not None:
                completed.append(cached["result"])
                generated.update(cached["sources"])
                generated[str((store.path(key) / "done.json").relative_to(root))] = _sha_file(
                    store.path(key) / "done.json"
                )
                continue
            if time.monotonic() + 120 >= deadline or (
                max_new_cohorts is not None and new >= max_new_cohorts
            ):
                break
            directory = store.begin(key, req)
            row = analyze(root, context, key, directory, deadline)
            cached = store.commit(key, req, row)
            generated.update(cached["sources"])
            generated[str((directory / "done.json").relative_to(root))] = _sha_file(
                directory / "done.json"
            )
            completed.append(row)
            new += 1
            mse = row["forecast"]["prediction"]["mse"]
            print(
                f"Saved credit diagnosis {len(completed)}/12: {key}; 32 games; "
                f"withheld MSE current {mse['current']:.6g}, inventory {mse['deck_relic']:.6g}; "
                "original player/Adam updates 0.",
                flush=True,
            )
        check_sources(root, context["sources"])
        body = {
            "schema_version": "native-inventory-credit-diagnosis-v1",
            "status": "native_inventory_credit_diagnosis_complete"
            if len(completed) == 12
            else "paused_between_sealed_cohorts",
            "config_id": store.config_id,
            "recipe_path": str(path.relative_to(root)),
            "source_report_id": context["source_report"]["report_id"],
            "completed_cohorts": len(completed),
            "planned_cohorts": 12,
            "new_cohorts_this_session": new,
            "cohorts": completed,
            "summary": summarize(completed),
            "sources": {**context["sources"], **generated},
            "objective": context["score"].evaluation_objective.as_dict(),
            "training_spec_id": context["score"].spec_id,
            "original_full_states_and_Adam_unchanged": True,
            "evaluation_decisions_or_outcomes_used_for_fitting": False,
            "raw_episode_histories_retained_at_once": 1,
            "games_launched": 0,
            "player_Adam_updates": 0,
            "game_apps_created": 0,
            "production_baseline_changed": False,
            "checkpoint_promoted": False,
            "adaptive_controller_allowed": False,
            "automatic_training_follows": False,
            "session_wall_seconds": time.monotonic() - started,
        }
        report = {**body, "report_id": manifest_identifier(body)}
        sessions = store.workspace / "sessions"
        sessions.mkdir(exist_ok=True)
        atomic_json(sessions / f"session-{len(list(sessions.glob('*.json'))) + 1:03d}.json", report)
        if len(completed) == 12:
            atomic_json(final, report)
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--max-new-cohorts", type=int)
    parser.add_argument("--session-seconds", type=int, default=900)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        report = run(
            root,
            root / args.recipe,
            max_new_cohorts=args.max_new_cohorts,
            session_seconds=args.session_seconds,
        )
    except (ValueError, OSError, TimeoutError) as exc:
        print(json.dumps({"status": "stopped_preserving_credit_evidence", "error": str(exc)}))
        return 1
    print(
        json.dumps({k: v for k, v in report.items() if k not in {"sources", "cohorts"}}, indent=2)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
