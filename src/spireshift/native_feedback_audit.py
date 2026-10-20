"""Restartable TRAIN-only feedback audit; no game launches or production updates."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_conditional_control import SOURCES as TEACHING_SOURCES
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_resume import ordered_paths, request_for
from spireshift.native_context_reuse import check_sources
from spireshift.native_exploration_admission import SOURCES as EXPLORATION_SOURCES
from spireshift.native_exploration_plan import plan, validate
from spireshift.native_feedback_metrics import diagnose
from spireshift.native_training_diagnostics import SOURCES as DIAGNOSTIC_SOURCES
from spireshift.training_objective import load_training_score_spec

SOURCES = tuple(
    sorted(
        set(
            (
                *TEACHING_SOURCES,
                *EXPLORATION_SOURCES,
                *DIAGNOSTIC_SOURCES,
                "native_feedback_checks.py",
                "native_feedback_metrics.py",
                "native_feedback_audit.py",
                "native_training_diagnostics.py",
                "native_conditional_control.py",
                "native_optimizer_probe.py",
            )
        )
    )
)


def training_binding(
    binding: dict[str, Any],
    owner: dict[str, Any],
    task: dict[str, Any],
    config_id: str,
    manifest_id: str,
) -> None:
    if (
        owner.get("partition") != "train"
        or owner.get("seed") != binding["native_seed"]
        or owner.get("numerical_seed") != task["numerical_seed"]
        or binding["partition"] != "train"
        or binding["panel_purpose"] != "training"
        or binding["config_id"] != config_id
        or binding["seed_manifest_id"] != manifest_id
    ):
        raise ValueError("Feedback may only consume distinct own-behavior TRAIN games")


def source_cohorts(
    root: Path, cfg: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    ref = cfg["completed_report"]
    report = identified(root / ref["path"])
    recipe_path = root / report["recipe_path"]
    recipe = json.loads(recipe_path.read_text())
    seed_path = root / recipe["seed_manifest"]["path"]
    seeds = identified(seed_path, "manifest_id")
    validate(recipe, seeds)
    parent = json.loads((root / recipe["qualified_parent"]["path"]).read_text())
    if (
        report["report_id"] != ref["id"]
        or report["status"] != "native_rest_exploration_complete"
        or report["completed_units"] != report["maximum_planned_units"]
        or report["games_recorded"] != report["maximum_planned_games"]
        or report["config_id"] != manifest_identifier(recipe)
        or recipe["qualified_parent"]["id"] != manifest_identifier(parent)
        or recipe["seed_manifest"]["id"] != seeds["manifest_id"]
    ):
        raise ValueError("Require the exact completed exploration comparison")
    # Hashes may include evaluation files; no evaluation history is decoded.
    check_sources(root, report["sources"])
    sources = {
        **report["sources"],
        ref["path"]: _sha_file(root / ref["path"]),
        str(recipe_path.relative_to(root)): _sha_file(recipe_path),
        recipe["qualified_parent"]["path"]: _sha_file(root / recipe["qualified_parent"]["path"]),
    }
    source = ChunkJournal(root, recipe)
    completed: dict[str, dict[str, Any]] = {}
    cohorts = []
    seen: set[tuple[int, str, int]] = set()
    owners = {s["id"]: s for s in seeds["seeds"]}
    for task in plan(recipe, seeds):
        if task["kind"] == "collect" and not task["training"]:
            break
        req = request_for(task, completed)
        receipt = source.completed(task["key"], req)
        if receipt is None:
            raise ValueError("Completed source comparison lost a training unit")
        completed[task["key"]] = receipt
        if task["kind"] != "fit":
            continue
        paths = ordered_paths(
            [root / p for k in task["collections"] for p in completed[k]["result"]["paths"]],
            task["round_seed_ids"],
        )
        for path in paths:
            header = json.loads(path.read_text())
            b = header["binding"]
            owner = owners.get(b["seed_id"], {})
            key = task["numerical_seed"], task["arm"]["name"], b["seed_id"]
            if key in seen:
                raise ValueError("Feedback cannot repeat a whole game in the same arm/player")
            training_binding(b, owner, task, report["config_id"], seeds["manifest_id"])
            seen.add(key)
        cohorts.append(
            {
                "key": task["key"],
                "before": completed[task["state"]]["result"],
                "after": receipt["result"],
                "paths": [str(p.relative_to(root)) for p in paths],
                "round": task["round"],
                "numerical_seed": task["numerical_seed"],
                "arm": task["arm"]["name"],
                "uniform_weight": task["arm"]["uniform_weight"],
                "credit_path": str((source.path(task["key"]) / "credit.json").relative_to(root)),
            }
        )
    if len(cohorts) != 16 or sum(len(c["paths"]) for c in cohorts) != 512:
        raise ValueError("Keep the complete 16-batch / 512-TRAIN-game source scope")
    if cfg["stage"] == "short_control":
        cohorts = [c for c in cohorts if c["round"] == 57 and c["arm"] == "standard"]
    return cohorts, parent, sources


def decision(results: list[dict[str, Any]]) -> dict[str, Any]:
    input_pass = all(
        p["candidate_order_equivariant"] and p["all_exercised_facts_distinguished"]
        for r in results
        for p in r["input_checks"]
    )
    teaching_pass = all(
        r["synthetic_teaching_check"]["memorization_criterion_passed"] for r in results
    )
    return {
        "finite_input_checks_passed": input_pass,
        "synthetic_memorization_passed_every_cohort": teaching_pass,
        "credit_baseline_beats_constant_batches": sum(
            r["value_quality"]["credit_baseline_beats_other_fold_constant"] for r in results
        ),
        "batches": len(results),
        "next_step": "repair_measured_input_loss_before_more_native_training"
        if not input_pass
        else "investigate_current_actor_optimization_before_more_native_training"
        if not teaching_pass
        else "qualify_native_counterfactual_combat_lessons_before_larger_training",
        "native_action_quality_established": False,
        "low_Smith_frequency_is_not_a_failure_criterion": True,
        "automatic_training_follows": False,
        "checkpoint_promoted": False,
        "adaptive_controller_allowed": False,
    }


def run(root: Path, path: Path, maximum_units: int | None = None) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    if (
        cfg.get("schema_version") != "native-learning-feedback-config-v1"
        or cfg.get("stage") not in {"short_control", "completed_train_audit"}
        or cfg.get("implementation_sha256")
        != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("entry_sha256")
        != {
            n: _sha_file(root / "scripts" / n)
            for n in ("native-learning-feedback-v1.py", "diagnose-native-learning-feedback-v1.sh")
        }
        or cfg.get("resource_limits")
        != {
            "wall_seconds": 240 if cfg.get("stage") == "short_control" else 900,
            "cpu_seconds": 240 if cfg.get("stage") == "short_control" else 900,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 100000000,
        }
        or maximum_units is not None
        and maximum_units < 1
    ):
        raise ValueError("Freeze feedback sources, finite scope and resource caps")
    start = time.monotonic()
    if cfg["stage"] == "completed_train_audit":
        ref = cfg["control_report"]
        control = identified(root / ref["path"])
        control_cfg = json.loads((root / control["recipe_path"]).read_text())
        if (
            control["report_id"] != ref["id"]
            or control["status"] != "completed_train_feedback_complete"
            or control["stage"] != "short_control"
            or control["completed_batches"] != 2
            or control["games"] != 64
            or control_cfg["implementation_sha256"] != cfg["implementation_sha256"]
            or not control["production_states_unchanged"]
            or not control["decision"]["finite_input_checks_passed"]
        ):
            raise ValueError("Require the matching completed short feedback control")
        check_sources(root, control["sources"])
    cohorts, parent, sources = source_cohorts(root, cfg)
    sources[str(path.relative_to(root))] = _sha_file(path)
    sources.update({f"src/spireshift/{n}": _sha_file(root / "src/spireshift" / n) for n in SOURCES})
    sources.update({f"scripts/{n}": sha for n, sha in cfg["entry_sha256"].items()})
    if cfg["stage"] == "completed_train_audit":
        sources[cfg["control_report"]["path"]] = _sha_file(root / cfg["control_report"]["path"])
    store = ChunkJournal(root, cfg)
    final = store.workspace / "report.json"
    if final.exists():
        saved = identified(final)
        check_sources(root, saved["sources"])
        return saved
    score = load_training_score_spec(root / parent["training_spec"]["path"])
    results: list[dict[str, Any]] = []
    executed = 0
    deadline = start + cfg["resource_limits"]["wall_seconds"] - 10
    with store.lock():
        for cohort in cohorts:
            req = {"cohort": cohort, "analysis": "mixture_feedback_v1"}
            done = store.completed(cohort["key"], req)
            if done is None:
                if maximum_units is not None and executed >= maximum_units:
                    break
                if deadline - time.monotonic() < 90:
                    break
                store.begin(cohort["key"], req)
                result = diagnose(root, cohort, score, parent, deadline)
                done = store.commit(cohort["key"], req, result)
                executed += 1
                print(
                    f"Saved TRAIN batch {len(results) + 1}/{len(cohorts)}: "
                    f"{result['games']} games; credit reconstructed; "
                    "no native games or production updates.",
                    flush=True,
                )
            results.append(done["result"])
            receipt = store.path(cohort["key"]) / "done.json"
            sources[str(receipt.relative_to(root))] = _sha_file(receipt)
            sources.update(done["sources"])
        complete = len(results) == len(cohorts)
        body = {
            "schema_version": "native-learning-feedback-report-v1",
            "config_id": manifest_identifier(cfg),
            "recipe_path": str(path.relative_to(root)),
            "status": "completed_train_feedback_complete" if complete else "paused_between_batches",
            "stage": cfg["stage"],
            "completed_batches": len(results),
            "planned_batches": len(cohorts),
            "games": sum(r["games"] for r in results),
            "decisions": sum(r["decisions"] for r in results),
            "results": results,
            "decision": decision(results) if complete else None,
            "new_native_games": 0,
            "production_optimizer_steps": 0,
            "synthetic_optimizer_steps": sum(
                r["synthetic_teaching_check"]["synthetic_optimizer_steps"] for r in results
            ),
            "production_states_unchanged": all(
                r["synthetic_teaching_check"]["source_model_and_all_Adam_state_unchanged"]
                for r in results
            ),
            "evaluation_histories_decoded": 0,
            "native_action_labels_generated": 0,
            "sources": sources,
            "wall_seconds": time.monotonic() - start,
            "claim_scope": "completed_TRAIN_feedback_and_synthetic_memorization_only",
        }
        check_sources(root, sources)
        report = {**body, "report_id": manifest_identifier(body)}
        if complete:
            atomic_json(final, report)
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--maximum-units", type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        result = run(root, root / args.recipe, args.maximum_units)
        print(
            json.dumps(
                {k: v for k, v in result.items() if k not in {"sources", "results"}}, indent=2
            )
        )
    except (OSError, ValueError, KeyError, TimeoutError) as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
