"""Bounded, separately versioned native original-versus-context PPO trial.

Reuse the qualified actual-engine workers, streaming delivery audit and numerical
optimizer. Preserve all historical sources. A short bridge check precedes the
owner-run comparison; neither stage admits bulk learning or adaptive search.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, save_native_episode, score_episode
from spireshift.engine_experience_stream import audit_worker_streaming, compact_case
from spireshift.engine_learning import IMPLEMENTATION, identified, load_learning_config, summarize
from spireshift.engine_mechanics_admission import require_composed_mechanics
from spireshift.engine_native import (
    _private_path,
    _require_native_launch_support,
    _running_games,
    _shared_snapshot,
)
from spireshift.engine_qualification import (
    EngineQualificationConfig,
    _sha_file,
    load_engine_qualification_config,
)
from spireshift.engine_run import _run_inputs
from spireshift.engine_worker import EngineWorker
from spireshift.engine_worker_qualification import (
    immutable_checks,
    load_worker_config,
    worker_script,
)
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Adam, Sample, fit_round
from spireshift.native_action_context import CROSSED, ORIGINAL, ActionContextModel, initialize
from spireshift.native_action_context_study import load_config as load_study
from spireshift.native_context_game import predict, verified_samples
from spireshift.native_value_credit import cross_fitted_predictions, prediction_metrics, value_run
from spireshift.training_objective import TrainingScoreSpec, load_training_score_spec

SOURCES = tuple(
    dict.fromkeys(
        (
            *IMPLEMENTATION,
            "engine_experience_stream.py",
            "native_action_context.py",
            "native_context_game.py",
            "native_context_trial.py",
        )
    )
)
STAGES = ("short_bridge_control", "bounded_native_comparison")


def launch_inputs(q: EngineQualificationConfig, parent: dict[str, Any]) -> dict[str, Any]:
    worker = load_worker_config(q.root / parent["worker_qualification_config"], q)
    inputs = _run_inputs(q, q.root / worker["base_run_recipe"])
    require_composed_mechanics(q, inputs, parent["mechanics_coverage"])
    score = load_training_score_spec(q.root / parent["training_spec"]["path"])
    if score.evaluation_objective.as_dict() != inputs["objective"]:
        raise ValueError("Context trial cannot change the whole-run victory/CPU objective")
    return inputs


def validate_plan(cfg: dict[str, Any], seeds: dict[str, Any]) -> None:
    short = cfg.get("stage") == STAGES[0]
    if (
        cfg.get("schema_version") != "native-action-context-trial-config-v1"
        or cfg.get("stage") not in STAGES
        or cfg.get("modes") != [ORIGINAL, CROSSED]
        or cfg.get("training_seeds") != ([0] if short else [0, 1])
        or cfg.get("rounds") != (1 if short else 4)
        or cfg.get("games_per_round") != (2 if short else 32)
        or cfg.get("evaluation_games") != (2 if short else 16)
        or cfg.get("initializer") != "common_zero_hidden_output_no_frozen_layers_v1"
        or cfg.get("checkpoint_selection") != "final_only"
        or cfg.get("resource_limits")
        != {
            "wall_seconds": 180 if short else 3600,
            "cpu_seconds": 360 if short else 7200,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 1000000000 if short else 6000000000,
        }
    ):
        raise ValueError("Freeze finite native extent, paired encodings, initializer and caps")
    rows = seeds["seeds"]
    train = [r for r in rows if r["partition"] == ("control" if short else "train")]
    evaluation = [r for r in rows if r["partition"] == ("control_eval" if short else "development")]
    repeats = len(cfg["training_seeds"])
    if (
        len(train) != repeats * cfg["rounds"] * cfg["games_per_round"]
        or len(evaluation) != repeats * cfg["evaluation_games"]
        or len(rows) != len(train) + len(evaluation)
        or len({r["id"] for r in rows}) != len(rows)
        or len({r["seed"] for r in rows}) != len(rows)
        or any(type(r["id"]) is not int or not isinstance(r["seed"], str) for r in rows)
    ):
        raise ValueError("Native context seeds cross ownership, repeat or miss the planned games")


def load_trial(
    q: EngineQualificationConfig, path: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    cfg = json.loads(path.read_text())
    if cfg.get("implementation_sha256") != {
        n: _sha_file(q.root / "src/spireshift" / n) for n in SOURCES
    }:
        raise ValueError("Native context implementation changed")
    parent = load_learning_config(q.root / cfg["parent_recipe"]["path"], q)
    if manifest_identifier(parent) != cfg["parent_recipe"]["id"]:
        raise ValueError("Native context parent worker, mechanics or learning rules changed")
    study_cfg, _, _ = load_study(q.root, q.root / cfg["study_config"]["path"])
    if manifest_identifier(study_cfg) != cfg["study_config"]["id"]:
        raise ValueError("Native context synthetic recipe changed")
    study = identified(q.root / cfg["study_report"]["path"])
    projection = identified(q.root / cfg["projection_report"]["path"])
    crossed = [r for r in study["results"] if r["mode"] == CROSSED and r["method"] == "ppo"]
    if (
        study["report_id"] != cfg["study_report"]["id"]
        or not study["integrity_pass"]
        or study["config_id"] != manifest_identifier(study_cfg)
        or len(crossed) != 3
        or not all(r["passed"] for r in crossed)
        or projection["report_id"] != cfg["projection_report"]["id"]
        or not projection["projection_pass"]
    ):
        raise ValueError(
            "Finite context learning/projection evidence must pass before native trial"
        )
    for ref in study["files"]:
        if _sha_file((q.root / cfg["study_report"]["path"]).parent / ref["path"]) != ref["sha256"]:
            raise ValueError("Synthetic study artifact changed")
    for name, digest in projection["sources"].items():
        if _sha_file(q.root / name) != digest:
            raise ValueError("Saved projection source changed")
    seeds = identified(q.root / cfg["seed_manifest"]["path"], "manifest_id")
    if (
        seeds["manifest_id"] != cfg["seed_manifest"]["id"]
        or seeds["environment_id"] != parent["environment_manifest"]["id"]
    ):
        raise ValueError("Native context seeds bind another environment")
    validate_plan(cfg, seeds)
    if cfg["stage"] == STAGES[1]:
        control = identified(q.root / cfg["control_report"]["path"])
        control_cfg = json.loads(
            (q.root / cfg["control_report"]["path"]).with_name("config-at-launch.json").read_text()
        )
        if control_cfg.get("stage") != STAGES[0]:
            raise ValueError("Native context bridge cannot recursively reference a long trial")
        validate_plan(
            control_cfg, identified(q.root / control_cfg["seed_manifest"]["path"], "manifest_id")
        )
        if (
            control["report_id"] != cfg["control_report"]["id"]
            or control["config_id"] != manifest_identifier(control_cfg)
            or control["status"] != "native_context_bridge_control_pass"
            or control["planned_games"] != 8
            or control["games_recorded"] != 8
            or control_cfg["implementation_sha256"] != cfg["implementation_sha256"]
            or any(
                control_cfg[k] != cfg[k]
                for k in ("parent_recipe", "study_report", "study_config", "projection_report")
            )
            or not all(control["checks"].values())
        ):
            raise ValueError("Short native context bridge is not verified")
        for name, digest in control["sources"].items():
            if _sha_file(q.root / name) != digest:
                raise ValueError("Native context bridge evidence changed")
        control_seeds = identified(q.root / control_cfg["seed_manifest"]["path"], "manifest_id")
        if control_seeds["manifest_id"] != control_cfg["seed_manifest"]["id"] or {
            r["seed"] for r in seeds["seeds"]
        } & {r["seed"] for r in control_seeds["seeds"]}:
            raise ValueError("Long native comparison cannot reuse its bridge-control games")
    _private_path(q.root, cfg["workspace"])
    return cfg, parent, seeds


def prepare(
    paths: list[Path],
    model: ActionContextModel,
    score: TrainingScoreSpec,
    settings: dict[str, Any],
    credit: dict[str, Any],
    index: int,
) -> tuple[list[Sample], dict[str, Any]]:
    runs, samples = [], []
    for path in paths:
        header = json.loads(path.read_text())
        binding = header["binding"]
        if (
            binding["partition"] not in {"train", "control"}
            or binding["panel_purpose"] != "training"
            or binding["model_id"] != model.model_id
        ):
            raise ValueError("Evaluation or stale episodes cannot supply context training")
        case = read_native_episode(path, binding)
        if case["status"] != "terminal":
            continue
        case["score"] = score_episode(case, binding["seed_id"], score)
        runs.append(value_run(case, binding["seed_id"], index, score))
        samples.extend(
            verified_samples(
                case, model, score, case["score"]["training_return"], settings["temperature"]
            )
        )
    if len(runs) < 2:
        raise ValueError("Cross-fitted native credit needs two clean independent whole games")
    predictions, folds = cross_fitted_predictions(
        sorted(runs, key=lambda r: r.seed),
        credit["baseline"],
        credit["regularization"],
        min(credit["folds"], len(runs)),
        credit["fold_salt"],
    )
    values = [v for run in runs for v in predictions[run.seed]]
    samples = [replace(s, advantage=s.target - v) for s, v in zip(samples, values, strict=True)]
    body = {
        "round": index,
        "clean_complete_training_games": len(runs),
        "decisions": len(samples),
        "choice_decisions": sum(len(s.rows) > 1 for s in samples),
        "cross_fit": folds,
        "prediction_quality": prediction_metrics(sorted(runs, key=lambda r: r.seed), predictions),
        "no_self_outcome_fitting": all(
            set(f["fitting_runs"]).isdisjoint(f["predicted_runs"]) for f in folds
        ),
        "discount": 1.0,
        "trace_lambda": 1.0,
        "hand_written_HP_rewards": False,
        "oracle_labels": 0,
    }
    return samples, {**body, "report_id": manifest_identifier(body)}


def collect_panel(
    q: EngineQualificationConfig,
    cfg: dict[str, Any],
    parent: dict[str, Any],
    inputs: dict[str, Any],
    seeds: list[dict[str, Any]],
    node: Path,
    output: Path,
    model: ActionContextModel,
    score: TrainingScoreSpec,
    replicate: int,
    label: str,
    training: bool,
    deadline: float,
) -> tuple[list[Path], dict[str, Any], dict[str, str]]:
    output.mkdir(parents=True, exist_ok=False)
    sources: dict[str, str] = {}

    def lane(index: int) -> tuple[list[Path], list[dict[str, Any]]]:
        recorded, outcomes = [], []
        segment: list[Path] = []
        worker: EngineWorker | None = None
        generation = 0

        def audit() -> None:
            assert worker is not None
            report = audit_worker_streaming(worker.workspace, segment, deadline=deadline)
            atomic_json(worker.workspace / "experience-audit.json", report)

        try:
            for seed in seeds[index::2]:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Native context panel wall cap")
                if worker is None:
                    worker = EngineWorker(
                        q,
                        inputs,
                        output / f"worker-{index}-generation-{generation}",
                        node,
                        parent["helpers_sha256"],
                        script=worker_script(parent),
                    )
                    segment = []
                # Neither mode nor checkpoint enters the sampling seed. Paired
                # initial/final evaluation uses the same reserved seeds/draws.
                salt = (
                    f"native-context-rng-v1|{replicate}|"
                    f"{label if training else 'frozen'}|{seed['id']}"
                )
                sampling = int.from_bytes(hashlib.sha256(salt.encode()).digest()[:8], "big")
                case = worker.episode(
                    seed["seed"],
                    maximum_decisions=parent["maximum_decisions"],
                    wall_seconds=min(parent["episode_wall_seconds"], deadline - time.monotonic()),
                    cpu_seconds=score.evaluation_objective.whole_run_budget,
                    chooser=partial(
                        predict,
                        model,
                        score,
                        rng=random.Random(sampling),
                        temperature=parent["learning"]["ppo"]["temperature"],
                    ),
                )
                case["worker_workspace"] = str(worker.workspace.relative_to(output))
                scored = score_episode(case, seed["id"], score)
                if not scored["completed"]:
                    case.update(status="failed", error=case.get("error", "Outside admitted budget"))
                binding = {
                    "environment_id": parent["environment_manifest"]["id"],
                    "config_id": manifest_identifier(cfg),
                    "seed_manifest_id": cfg["seed_manifest"]["id"],
                    "seed_id": seed["id"],
                    "native_seed": seed["seed"],
                    "partition": seed["partition"],
                    "panel": label,
                    "model_id": model.model_id,
                    "training_spec_id": score.spec_id,
                    "sampling_seed": sampling,
                    "behavior": "sampled_softmax",
                    "panel_purpose": "training" if training else "frozen_policy_evaluation",
                }
                saved = output / f"case-{seed['id']}.json"
                save_native_episode(saved, case, binding)
                del case
                verified = read_native_episode(saved, binding)
                compact = compact_case(verified)
                # Reconstruct ALL behavior probabilities even on evaluation.
                if compact["status"] == "terminal":
                    verified_samples(
                        verified,
                        model,
                        score,
                        scored["training_return"],
                        parent["learning"]["ppo"]["temperature"],
                    )
                del verified
                recorded.append(saved)
                segment.append(saved)
                outcomes.append(
                    {**compact, "seed_id": seed["id"], "training_return": scored["training_return"]}
                )
                if compact["status"] != "terminal":
                    worker.retire(compact["error"] or "Native context game failed")
                    audit()
                    worker = None
                    generation += 1
            if worker is not None:
                worker.close()
                audit()
        except (ValueError, OSError, TimeoutError, subprocess.TimeoutExpired) as exc:
            atomic_json(
                output / f"worker-{index}-failure.json",
                {"error": str(exc), "recorded_games": len(recorded)},
            )
        finally:
            if worker is not None:
                worker.stop()
        return recorded, outcomes

    with ThreadPoolExecutor(max_workers=2) as pool:
        lanes = list(pool.map(lane, (0, 1)))
    paths = [p for row, _ in lanes for p in row]
    outcomes = [o for _, row in lanes for o in row]
    summary = {
        **summarize([{**c, "decisions": range(c["decision_count"])} for c in outcomes], len(seeds)),
        "outcomes": outcomes,
        "label": label,
        "model_id": model.model_id,
        "worker_failures": len(list(output.glob("worker-*-failure.json"))),
    }
    atomic_json(output / "summary.json", summary)
    for path in [*paths, *[p.with_suffix(".jsonl.gz") for p in paths], output / "summary.json"]:
        sources[str(path.relative_to(q.root))] = _sha_file(path)
    for path in output.glob("worker-*/experience-audit.json"):
        audit_report = identified(path)
        sources[str(path.relative_to(q.root))] = _sha_file(path)
        sources.update(
            {
                str((path.parent / n).relative_to(q.root)): sha
                for n, sha in audit_report["source_sha256"].items()
            }
        )
    print(
        f"{model.mode}, seed {replicate}, {label}: wins {summary['wins']}/{len(seeds)}; "
        f"average floor {summary['mean_floor']:.2f}; best floor {summary['best_floor']}, "
        f"{summary['best_completed_acts']} acts; failures/missing "
        f"{summary['failed_games'] + summary['not_attempted_games']}.",
        flush=True,
    )
    allowance = 0 if cfg["stage"] == STAGES[0] else 2
    if (
        summary["not_attempted_games"]
        or summary["worker_failures"]
        or summary["failed_games"] > allowance
    ):
        raise ValueError(
            "Native context panel is missing, unauditable or exceeds failed-game allowance"
        )
    return paths, summary, sources


def run(q: EngineQualificationConfig, path: Path, node: Path) -> dict[str, Any]:
    cfg, parent, seeds = load_trial(q, path)
    output = _private_path(q.root, cfg["workspace"])
    if output.exists():
        if not (output / "report.json").is_file():
            raise FileExistsError(
                "Preserve unfinished native context evidence; no restart or replay"
            )
        cached = identified(output / "report.json")
        if cached["config_id"] != manifest_identifier(cfg):
            raise ValueError("Saved native context recipe changed")
        for name, digest in cached["sources"].items():
            if _sha_file(q.root / name) != digest:
                raise ValueError("Saved native context evidence changed")
        return cached
    _require_native_launch_support()
    if _running_games() or not node.is_file():
        raise ValueError("Close the game and select the local Node runtime")
    inputs = launch_inputs(q, parent)
    score = load_training_score_spec(q.root / parent["training_spec"]["path"])
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "config-at-launch.json", cfg)
    sources = {
        str(path.relative_to(q.root)): _sha_file(path),
        str((output / "config-at-launch.json").relative_to(q.root)): _sha_file(
            output / "config-at-launch.json"
        ),
    }
    for n, sha in cfg["implementation_sha256"].items():
        target = output / "source-at-launch" / n
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((q.root / "src/spireshift" / n).read_bytes())
        sources[f"src/spireshift/{n}"] = sha
        sources[str(target.relative_to(q.root))] = _sha_file(target)
    shared = Path.home() / "Library/Application Support/SlayTheSpire2"
    before = _shared_snapshot(shared)
    started = time.monotonic()
    deadline = started + cfg["resource_limits"]["wall_seconds"] - 12
    results = []
    error = None
    steps = games = 0
    short = cfg["stage"] == STAGES[0]
    train = [r for r in seeds["seeds"] if r["partition"] == ("control" if short else "train")]
    evaluation = [
        r for r in seeds["seeds"] if r["partition"] == ("control_eval" if short else "development")
    ]
    try:
        for rep, numerical_seed in enumerate(cfg["training_seeds"]):
            count = cfg["games_per_round"] * cfg["rounds"]
            own_train = train[rep * count : (rep + 1) * count]
            own_eval = evaluation[
                rep * cfg["evaluation_games"] : (rep + 1) * cfg["evaluation_games"]
            ]
            originals = [
                initialize(parent["environment_manifest"]["id"], score.spec_id, numerical_seed, m)
                for m in cfg["modes"]
            ]
            if originals[0].weights() != originals[1].weights():
                raise ValueError("Native context initial numerical parameters differ")
            for initial in originals:
                model = initial
                optimizer = Adam.zero(model.parameter_count)
                arm = output / f"{model.mode}-seed-{numerical_seed}"
                arm.mkdir()
                atomic_json(arm / "initial-model.json", model.as_dict())
                record: dict[str, Any] = {
                    "mode": model.mode,
                    "training_seed": numerical_seed,
                    "initial_model_id": model.model_id,
                    "panels": [],
                    "rounds": [],
                }

                def panel(
                    label: str,
                    rows: list[dict[str, Any]],
                    training: bool,
                    actor: ActionContextModel,
                    arm_path: Path = arm,
                    rep_seed: int = numerical_seed,
                    panel_record: dict[str, Any] = record,
                ) -> list[Path]:
                    nonlocal games
                    paths, summary, seals = collect_panel(
                        q,
                        cfg,
                        parent,
                        inputs,
                        rows,
                        node,
                        arm_path / label,
                        actor,
                        score,
                        rep_seed,
                        label,
                        training,
                        deadline,
                    )
                    panel_record["panels"].append(summary)
                    games += len(paths)
                    sources.update(seals)
                    return paths

                if not short:
                    panel("development-initial", own_eval, False, model)
                for index in range(1, cfg["rounds"] + 1):
                    rows = own_train[
                        (index - 1) * cfg["games_per_round"] : index * cfg["games_per_round"]
                    ]
                    paths = panel(f"round-{index:03d}", rows, True, model)
                    samples, credit = prepare(
                        paths,
                        model,
                        score,
                        parent["learning"]["ppo"],
                        parent["learning"]["credit_assignment"],
                        index,
                    )
                    previous = model.model_id
                    updated, optimizer, diagnostic = fit_round(
                        cast(Any, model), optimizer, samples, parent["learning"]["ppo"], index
                    )
                    if not isinstance(updated, ActionContextModel):
                        raise ValueError("Native optimizer lost action-context encoding identity")
                    model = ActionContextModel.from_mapping(updated.as_dict())
                    steps += diagnostic["optimizer_steps"]
                    atomic_json(arm / f"round-{index:03d}-model.json", model.as_dict())
                    atomic_json(arm / f"round-{index:03d}-credit.json", credit)
                    record["rounds"].append(
                        {
                            "round": index,
                            "before_model_id": previous,
                            "after_model_id": model.model_id,
                            "work": diagnostic,
                            "decisions": len(samples),
                            "clean_training_games": credit["clean_complete_training_games"],
                        }
                    )
                    del samples
                panel("control-final" if short else "development-final", own_eval, False, model)
                record["final_model_id"] = model.model_id
                record["optimizer_steps"] = optimizer.steps
                atomic_json(arm / "result.json", record)
                results.append(record)
    except (ValueError, OSError, TimeoutError, subprocess.TimeoutExpired) as exc:
        error = str(exc)
    # Count every sealed partial-panel attempt, including an arm that failed before return.
    saved_cases = [
        *output.glob("*/round-*/case-*.json"),
        *output.glob("*/development-*/case-*.json"),
        *output.glob("*/control-final/case-*.json"),
    ]
    games = len(saved_cases)
    failed_games = sum(
        json.loads(p.read_text())["episode"]["status"] != "terminal" for p in saved_cases
    )
    for p in output.glob("*/*.json"):
        sources[str(p.relative_to(q.root))] = _sha_file(p)
    # Seal partial panels too; never resume or remove interrupted evidence.
    for p in output.rglob("*"):
        if p.is_file() and not p.is_symlink():
            sources[str(p.relative_to(q.root))] = _sha_file(p)
    checks = immutable_checks(q, inputs)
    checks["account_profile_unchanged"] = _shared_snapshot(shared) == before
    checks["all_planned_arms_complete"] = error is None and len(results) == len(cfg["modes"]) * len(
        cfg["training_seeds"]
    )
    checks["all_recorded_training_used_only_own_clean_on_policy_games"] = error is None
    planned = (
        len(cfg["modes"])
        * len(cfg["training_seeds"])
        * (cfg["rounds"] * cfg["games_per_round"] + cfg["evaluation_games"] * (1 if short else 2))
    )
    checks["original_game_denominator_complete"] = games == planned
    ok = all(checks.values())
    body = {
        "schema_version": "native-action-context-trial-v1",
        "config_id": manifest_identifier(cfg),
        "status": (
            "native_context_bridge_control_pass"
            if short
            else "bounded_native_context_comparison_complete"
        )
        if ok
        else "native_context_comparison_incomplete",
        "error": error,
        "checks": checks,
        "results": results,
        "planned_games": planned,
        "games_recorded": games,
        "completed_games": games - failed_games,
        "failed_games": failed_games,
        "not_attempted_games": planned - games,
        "optimizer_steps": steps,
        "sources": sources,
        "wall_seconds": time.monotonic() - started,
        "unsealed_partial_work_unknown": error is not None,
        "game_apps_created": 0,
        "all_legal_decision_families_learnable": True,
        "native_teacher_or_oracle_labels": 0,
        "checkpoint_promoted": False,
        "base_readiness_passed": False,
        "adaptive_controller_allowed": False,
        "terminal_victory_probability_available": False,
        "claim_scope": (
            "finite_A8_native_final_policy_comparison_not_bulk_learning_or_readiness_admission"
        ),
    }
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(output / "report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("qualification", type=Path)
    parser.add_argument("config", type=Path)
    parser.add_argument("--node", required=True, type=Path)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    q = load_engine_qualification_config(args.qualification)
    if args.preflight:
        cfg, parent, _ = load_trial(q, q.root / args.config)
        launch_inputs(q, parent)
        print(
            json.dumps(
                {
                    "ready": not (q.root / cfg["workspace"]).exists(),
                    "stage": cfg["stage"],
                    "games_launched": 0,
                    "optimizer_steps": 0,
                }
            )
        )
        return 0
    result = run(q, q.root / args.config, args.node)
    print(
        json.dumps({k: v for k, v in result.items() if k not in {"sources", "results"}}, indent=2)
    )
    return 0 if all(result["checks"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
