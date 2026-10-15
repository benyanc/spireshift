"""Bounded actual-engine learning control and policy-only PPO pilot, with explicit admission.

No adaptive search, emulator checkpoint conversion, hidden inputs or automatic follow-up.
All long experiment execution belongs to the owner. Code paths share the same public collector.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import (
    read_native_episode,
    save_native_episode,
    score_episode,
    verified_native_samples,
)
from spireshift.engine_experience_audit import audit_worker_experience
from spireshift.engine_native import (
    _private_path,
    _require_native_launch_support,
    _running_games,
    _shared_snapshot,
)
from spireshift.engine_neural import (
    ENCODER,
    NativeActorCritic,
    fit_native_round,
    initial_actor,
    initialize_native_critic,
    predict,
)
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.engine_run import _run_inputs
from spireshift.engine_worker import LIVENESS_POLICY, EngineWorker, worker_helpers
from spireshift.engine_worker_qualification import immutable_checks, load_worker_config
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Adam
from spireshift.training_objective import load_training_score_spec

IMPLEMENTATION = (
    "engine_learning.py",
    "engine_neural.py",
    "engine_experience.py",
    "engine_experience_audit.py",
    "engine_worker.py",
    "engine_worker_qualification.py",
    "engine_run.py",
    "full_run_ppo_math.py",
    "full_run_policy.py",
    "training_objective.py",
)

FAILURE_POLICY = "record_retire_continue_v1"


def implementation_files(root: Path) -> dict[str, str]:
    return {name: _sha_file(root / "src/spireshift" / name) for name in IMPLEMENTATION}


def identified(path: Path, key: str = "report_id") -> dict[str, Any]:
    doc = json.loads(path.read_text())
    if doc.get(key) != manifest_identifier({k: v for k, v in doc.items() if k != key}):
        raise ValueError(f"Saved evidence identity differs: {path}")
    return dict(doc)


def load_learning_config(path: Path, q: EngineQualificationConfig) -> dict[str, Any]:
    d = json.loads(path.read_text())
    if (
        d.get("schema_version") != "actual-engine-neural-experiment-config-v1"
        or d.get("qualification_config_id") != q.config_id
        or d.get("stage") not in {"short_learning_control", "bounded_policy_only_pilot"}
        or d.get("implementation_sha256") != implementation_files(q.root)
        or d.get("helpers_sha256") != worker_helpers(q.root)
        or d.get("encoder_id") != ENCODER
        or d.get("workers") != 2
        or d.get("maximum_decisions") != 4096
        or d.get("episode_wall_seconds") != 60
        or d.get("adaptive_controller_allowed") is not False
        or d.get("liveness_policy") != LIVENESS_POLICY
    ):
        raise ValueError("Native learning requires its pinned, fixed-A8 implementation and caps")
    wcfg = load_worker_config(q.root / d["worker_qualification_config"], q)
    worker = identified(q.root / d["worker_report"]["path"])
    if (
        worker["report_id"] != d["worker_report"]["id"]
        or worker["config_id"] != manifest_identifier(wcfg)
        or worker["status"] != "worker_isolation_pass"
        or worker["completed_games"] != 12
        or worker["failed_games"]
        or worker["not_attempted_games"]
        or worker["game_apps_created"]
        or not all(worker["checks"].values())
    ):
        raise ValueError("Native worker isolation is not qualified")
    environment = identified(q.root / d["environment_manifest"]["path"], "manifest_id")
    score = load_training_score_spec(q.root / d["training_spec"]["path"])
    if (
        environment["manifest_id"] != d["environment_manifest"]["id"]
        or environment["input_config_id"] != worker["input_config_id"]
        or environment["build_report_id"] != worker["build_report_id"]
        or environment["character"] != "Ironclad"
        or environment["ascension"] != 8
        or environment["profile"] != "native_benchmark_full_v1"
        or environment["encoder_id"] != ENCODER
        or environment.get("liveness_policy") != LIVENESS_POLICY
        or environment["helpers_sha256"] != worker_helpers(q.root)
        or score.spec_id != d["training_spec"]["id"]
        or score.scope.ruleset_manifest_id != environment["manifest_id"]
        or score.scope.character != "ironclad"
        or score.scope.ascension != 8
    ):
        raise ValueError("Native game, public encoder, score or difficulty identities differ")
    seeds = identified(q.root / d["seed_manifest"]["path"], "manifest_id")
    if (
        seeds["manifest_id"] != d["seed_manifest"]["id"]
        or seeds["environment_id"] != environment["manifest_id"]
    ):
        raise ValueError("Native complete-run seed ownership differs")
    rows = seeds["seeds"]
    if (
        len({r["id"] for r in rows}) != len(rows)
        or len({r["seed"] for r in rows}) != len(rows)
        or any(
            type(r["id"]) is not int
            or r["id"] < 0
            or r["partition"] not in {"train", "confirmation", "development", "control"}
            for r in rows
        )
    ):
        raise ValueError("Native seed manifest has duplicates or invalid ownership")
    groups = {
        name: {r["id"] for r in rows if r["partition"] == name}
        for name in ("train", "confirmation", "development", "control")
    }
    panels = d["learning"]["rollout_panels"]
    if (
        not panels
        or not 1 <= len(panels) <= 8
        or any(not p or len(set(p)) != len(p) for p in panels)
    ):
        raise ValueError("Native PPO needs finite nonempty rollout panels")
    train_ids = [i for p in panels for i in p]
    if len(set(train_ids)) != len(train_ids) or not set(train_ids) <= groups["train"]:
        raise ValueError("Native rollout panels cross seed ownership or repeat seeds")
    for key, owner in (
        ("confirmation_seeds", "confirmation"),
        ("development_seeds", "development"),
        ("control_seeds", "control"),
    ):
        selected = d["learning"][key]
        if len(set(selected)) != len(selected) or not set(selected) <= groups[owner]:
            raise ValueError("Native learning crosses complete-run seed ownership")
    network, ppo = d["network"], d["learning"]["ppo"]
    if d.get("failure_policy") != {
        "id": FAILURE_POLICY,
        "maximum_failed_games_per_panel": 0 if d["stage"] == "short_learning_control" else 2,
        "retry_failed_seeds": False,
        "train_on_failed_games": False,
    }:
        raise ValueError("Native learning must declare its bounded per-game failure policy")
    initial_actor(
        environment["manifest_id"], network["dimension"], network["hidden_units"], network["seed"]
    )
    for key in ("epochs", "minibatch_decisions"):
        if type(ppo[key]) is not int or not 1 <= ppo[key] <= 256:
            raise ValueError("Native PPO finite update extent differs")
    for key, low, high in (
        ("clip", 0.01, 0.5),
        ("temperature", 0.05, 2),
        ("entropy_coefficient", 0, 0.1),
        ("value_coefficient", 0.01, 2),
        ("actor_learning_rate", 1e-6, 0.02),
        ("value_learning_rate", 1e-6, 0.02),
        ("gradient_clip", 0.1, 10),
        ("target_kl", 0.001, 0.5),
    ):
        if (
            type(ppo[key]) not in (int, float)
            or not math.isfinite(ppo[key])
            or not low <= ppo[key] <= high
        ):
            raise ValueError("Native PPO numerical setting differs")
    if d["stage"] == "short_learning_control":
        if len(panels) != 1 or len(train_ids) != 2 or len(d["learning"]["control_seeds"]) != 2:
            raise ValueError("Short control is capped at four games and one update")
        if (
            d.get("maximum_wall_seconds") != 180
            or d["learning"]["confirmation_seeds"]
            or d["learning"]["development_seeds"]
        ):
            raise ValueError("Short control cannot open development or exceed three minutes")
    else:
        if d.get("maximum_wall_seconds") != 1800 or d["learning"]["control_seeds"]:
            raise ValueError("Owner pilot needs its fixed thirty-minute cap")
        admission = identified(q.root / d["admission"]["path"])
        if (
            admission["report_id"] != d["admission"]["id"]
            or admission["status"] != "admitted_for_bounded_native_policy_only_pilot"
            or admission["environment_id"] != environment["manifest_id"]
            or admission["implementation_sha256"] != d["implementation_sha256"]
            or admission["worker_report_id"] != worker["report_id"]
            or admission["adaptive_controller_allowed"] is not False
        ):
            raise ValueError("Bounded native learning is not explicitly admitted")
        if (
            any(len(p) != 32 for p in panels)
            or len(panels) != 8
            or len(d["learning"]["confirmation_seeds"]) != 16
            or len(d["learning"]["development_seeds"]) != 16
            or d["learning"]["confirmation_every"] != 4
        ):
            raise ValueError("Owner pilot must retain its finite 336-game denominator")
    _private_path(q.root, d["workspace"])
    return dict(d)


def summarize(cases: list[dict[str, Any]], denominator: int) -> dict[str, Any]:
    complete = [c for c in cases if c["status"] == "terminal"]
    best = max(
        complete,
        key=lambda c: (c["victory"], c["completed_acts"], c["maximum_floor"]),
        default=None,
    )
    return {
        "planned_games": denominator,
        "completed_games": len(complete),
        "failed_games": len(cases) - len(complete),
        "not_attempted_games": denominator - len(cases),
        "wins": sum(c["victory"] for c in complete),
        "mean_floor": sum(c["maximum_floor"] for c in cases) / denominator,
        "best_floor": best["maximum_floor"] if best else 0,
        "best_completed_acts": best["completed_acts"] if best else 0,
        "best_victory": best["victory"] if best else False,
        "decisions": sum(len(c["decisions"]) for c in cases),
        "cpu_seconds": sum(c["cpu_seconds"] for c in cases),
        "failed_cases": [
            {
                "seed": c["seed"],
                "error": c.get("error", "Outcome outside admitted budget"),
                "maximum_floor": c["maximum_floor"],
                "worker_workspace": c.get("worker_workspace"),
                "excluded_from_training": True,
            }
            for c in cases
            if c["status"] != "terminal"
        ],
    }


def run_neural_experiment(
    q: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    _require_native_launch_support()
    if _running_games() or not node.is_file():
        raise ValueError("Close the game and select the local Node runtime")
    d = load_learning_config(path, q)
    wcfg = load_worker_config(q.root / d["worker_qualification_config"], q)
    inputs = _run_inputs(q, q.root / wcfg["base_run_recipe"])
    if inputs["inputs"].get("combat_surface_revision") in {"v3", "v4"}:
        from spireshift.engine_coverage import require_mechanics_coverage

        require_mechanics_coverage(q, inputs, d.get("mechanics_coverage"))
    score = load_training_score_spec(q.root / d["training_spec"]["path"])
    if score.evaluation_objective.as_dict() != inputs["objective"]:
        raise ValueError("Native learner objective differs from the admitted whole-run CPU budget")
    seed_doc = identified(q.root / d["seed_manifest"]["path"], "manifest_id")
    by_id = {r["id"]: r for r in seed_doc["seeds"]}
    output = _private_path(q.root, d["workspace"])
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "config.json", d)
    source = output / "source-at-launch"
    source.mkdir()
    for name in IMPLEMENTATION:
        (source / name).write_bytes((q.root / "src/spireshift" / name).read_bytes())
    shared = Path.home() / "Library/Application Support/SlayTheSpire2"
    before = _shared_snapshot(shared)
    network, learning = d["network"], d["learning"]
    initial = initialize_native_critic(
        initial_actor(
            d["environment_manifest"]["id"],
            network["dimension"],
            network["hidden_units"],
            network["seed"],
        )
    )
    model, selected = initial, initial
    optimizer = Adam.zero(model.parameter_count)
    atomic_json(output / "initial-checkpoint.json", model.as_dict())
    rounds: list[dict[str, Any]] = []
    panels: list[dict[str, Any]] = []
    sample_count = 0
    game_count = 0
    failure: str | None = None
    started = time.monotonic()
    # Leave time for verified shutdown, immutable-input checks and the final report.
    deadline = started + d["maximum_wall_seconds"] - 15

    def collect(
        label: str, ids: list[int], actor: NativeActorCritic, sampled: bool
    ) -> list[dict[str, Any]]:
        nonlocal game_count
        panel = output / label
        panel.mkdir()
        results: list[dict[str, Any]] = []

        def worker_batch(index: int) -> list[dict[str, Any]]:
            worker: EngineWorker | None = None
            batch: list[dict[str, Any]] = []
            segment: list[dict[str, Any]] = []
            generation = 0

            def audit_segment() -> None:
                assert worker is not None
                audit = audit_worker_experience(worker.workspace, segment)
                atomic_json(worker.workspace / "experience-audit.json", audit)

            try:
                for seed_id in ids[index :: d["workers"]]:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Native experiment wall cap")
                    if worker is None:
                        name = f"worker-{index}"
                        if generation:
                            name += f"-generation-{generation}"
                        worker = EngineWorker(q, inputs, panel / name, node, d["helpers_sha256"])
                        segment = []
                    seed = by_id[seed_id]
                    sampling_seed = int.from_bytes(
                        hashlib.sha256(
                            f"{learning['sampling_seed']}|{label}|{seed_id}".encode()
                        ).digest()[:8],
                        "big",
                    )
                    rng = random.Random(sampling_seed) if sampled else None
                    case = worker.episode(
                        seed["seed"],
                        maximum_decisions=d["maximum_decisions"],
                        wall_seconds=min(d["episode_wall_seconds"], deadline - time.monotonic()),
                        cpu_seconds=score.evaluation_objective.whole_run_budget,
                        chooser=partial(
                            predict, actor, rng=rng, temperature=learning["ppo"]["temperature"]
                        ),
                    )
                    case["worker_workspace"] = str(worker.workspace.relative_to(output))
                    if score_episode(case, seed_id, score)["completed"] is not True:
                        case.update(
                            status="failed",
                            error=case.get("error", "Outcome outside admitted budget"),
                        )
                    binding = {
                        "environment_id": d["environment_manifest"]["id"],
                        "config_id": manifest_identifier(d),
                        "seed_manifest_id": d["seed_manifest"]["id"],
                        "seed_id": seed_id,
                        "native_seed": seed["seed"],
                        "partition": seed["partition"],
                        "panel": label,
                        "model_id": actor.model_id,
                        "training_spec_id": score.spec_id,
                        "sampling_seed": sampling_seed,
                        "behavior": "sampled_softmax" if sampled else "greedy",
                    }
                    saved_path = panel / f"case-{seed_id}.json"
                    save_native_episode(saved_path, case, binding)
                    saved = read_native_episode(saved_path, binding)
                    saved["score"] = score_episode(saved, seed_id, score)
                    batch.append(saved)
                    segment.append(saved)
                    if saved["status"] != "terminal":
                        error = saved.get("error", "Outcome outside admitted budget")
                        worker.retire(error)
                        audit_segment()
                        print(
                            f"{label}: seed {seed_id} failed at floor {saved['maximum_floor']}: "
                            f"{error}. Preserved and excluded from training; "
                            "next planned seed follows.",
                            flush=True,
                        )
                        worker = None
                        generation += 1
                if worker is not None and not worker.closed:
                    worker.close()
                    audit_segment()
                return batch
            except (ValueError, TimeoutError, OSError, subprocess.TimeoutExpired) as exc:
                atomic_json(
                    panel / f"worker-{index}-failure.json",
                    {"error": str(exc), "recorded_games": len(batch), "replacement_started": False},
                )
                return batch
            finally:
                if worker is not None:
                    worker.stop()

        with ThreadPoolExecutor(max_workers=d["workers"]) as pool:
            futures = [pool.submit(worker_batch, i) for i in range(d["workers"])]
            for future in futures:
                results.extend(future.result())
        game_count += len(results)
        summary = summarize(results, len(ids))
        summary["panel"] = label
        summary["model_id"] = actor.model_id
        summary["worker_failures"] = len(list(panel.glob("worker-*-failure.json")))
        summary["retired_workers"] = len(list(panel.glob("worker-*/retired.json")))
        panels.append(summary)
        atomic_json(panel / "summary.json", summary)
        print(
            f"{label}: wins {summary['wins']}/{len(ids)}; "
            f"average floor {summary['mean_floor']:.2f}; "
            f"best floor {summary['best_floor']}, {summary['best_completed_acts']} acts; "
            f"failures/missing {summary['failed_games'] + summary['not_attempted_games']}.",
            flush=True,
        )
        if summary["not_attempted_games"] or summary["worker_failures"]:
            raise ValueError("Native panel has missing games or an unauditable worker")
        if summary["failed_games"] > d["failure_policy"]["maximum_failed_games_per_panel"]:
            raise ValueError("Native panel exceeded its declared failed-game allowance")
        return results

    def rank(cases: list[dict[str, Any]]) -> tuple[float, float, float]:
        return (
            sum(c["victory"] for c in cases if c["status"] == "terminal") / len(cases),
            sum(c["score"]["auxiliary_progress_return"] for c in cases) / len(cases),
            sum(c["status"] == "terminal" for c in cases) / len(cases),
        )

    try:
        selection_rank = (-1.0, -1.0, -1.0)
        if d["stage"] == "bounded_policy_only_pilot":
            selection_rank = rank(
                collect("initial-confirmation", learning["confirmation_seeds"], initial, False)
            )
        for index, ids in enumerate(learning["rollout_panels"], 1):
            cases = collect(f"round-{index:03}-sampled", ids, model, True)
            samples = []
            for case in cases:
                if case["status"] != "terminal":
                    continue
                samples.extend(
                    verified_native_samples(
                        case,
                        model,
                        case["score"]["training_return"],
                        learning["ppo"]["temperature"],
                    )
                )
            sample_count += len(samples)
            previous = model
            model, optimizer, diagnostic = fit_native_round(
                model, optimizer, samples, learning["ppo"], index
            )
            # Force the same validation/load path the owner will use on saved checkpoints.
            model = NativeActorCritic.from_mapping(model.as_dict())
            weights = model.weights()
            if model.model_id == previous.model_id or not all(math.isfinite(v) for v in weights):
                raise ValueError("Short native update did not change finite model parameters")
            update = {
                "round": index,
                "completed_training_games": sum(c["status"] == "terminal" for c in cases),
                "excluded_failed_training_games": sum(c["status"] != "terminal" for c in cases),
                "behavior_model_id": previous.model_id,
                "updated_model_id": model.model_id,
                "actor_l2_change": math.sqrt(
                    sum(
                        (a - b) ** 2
                        for a, b in zip(previous.actor.genome, model.actor.genome, strict=True)
                    )
                ),
                "critic_l2_change": math.sqrt(
                    sum(
                        (a - b) ** 2
                        for a, b in zip(previous.value_weights, model.value_weights, strict=True)
                    )
                ),
                "diagnostics": diagnostic,
            }
            rounds.append(update)
            atomic_json(output / f"round-{index:03}-update.json", update)
            atomic_json(output / f"round-{index:03}-checkpoint.json", model.as_dict())
            atomic_json(output / f"round-{index:03}-optimizer.json", optimizer.as_dict())
            if d["stage"] == "short_learning_control":
                selected = model
            elif index % learning["confirmation_every"] == 0:
                candidate_rank = rank(
                    collect(
                        f"round-{index:03}-confirmation",
                        learning["confirmation_seeds"],
                        model,
                        False,
                    )
                )
                if candidate_rank > selection_rank:
                    selected, selection_rank = model, candidate_rank
            print(
                f"Update {index}: {diagnostic['optimizer_steps']} optimizer steps; "
                f"all action families remain trainable.",
                flush=True,
            )
        atomic_json(output / "selected-checkpoint.json", selected.as_dict())
        atomic_json(
            output / "selection-freeze.json",
            {
                "model_id": selected.model_id,
                "selection_partition": "control_only"
                if d["stage"] == "short_learning_control"
                else "confirmation",
                "development_opened": False,
            },
        )
        if d["stage"] == "short_learning_control":
            collect("control-greedy", learning["control_seeds"], selected, False)
        else:
            collect("development-initial", learning["development_seeds"], initial, False)
            collect("development-selected", learning["development_seeds"], selected, False)
    except (ValueError, TimeoutError, OSError) as exc:
        failure = str(exc)
    checks = immutable_checks(q, inputs)
    checks["account_profile_unchanged"] = _shared_snapshot(shared) == before
    if not all(checks.values()):
        failure = "Native learning modified protected inputs or profile"
    body = {
        "schema_version": "actual-engine-neural-experiment-report-v1",
        "config_id": manifest_identifier(d),
        "stage": d["stage"],
        "status": (
            "short_learning_control_pass"
            if d["stage"] == "short_learning_control"
            else (
                "bounded_pilot_complete_with_failures"
                if any(p["failed_games"] for p in panels)
                else "bounded_pilot_complete"
            )
        )
        if failure is None
        else "stopped_incomplete",
        "error": failure,
        "environment_id": d["environment_manifest"]["id"],
        "training_spec_id": score.spec_id,
        "seed_manifest_id": d["seed_manifest"]["id"],
        "implementation_sha256": d["implementation_sha256"],
        "worker_report_id": d["worker_report"]["id"],
        "initial_model_id": initial.model_id,
        "selected_model_id": selected.model_id,
        "planned_games": 4 if d["stage"] == "short_learning_control" else 336,
        "recorded_games": game_count,
        "completed_games": sum(p["completed_games"] for p in panels),
        "failed_games": sum(p["failed_games"] for p in panels),
        "worker_failures": sum(p["worker_failures"] for p in panels),
        "retired_workers": sum(p["retired_workers"] for p in panels),
        "failure_policy": d["failure_policy"],
        "not_attempted_games": (4 if d["stage"] == "short_learning_control" else 336) - game_count,
        "sampled_decisions_verified": sample_count,
        "optimizer_steps": optimizer.steps,
        "rounds": rounds,
        "panels": panels,
        "checks": checks,
        "game_apps_created": 0,
        "wall_seconds": time.monotonic() - started,
        "checkpoint_promoted": False,
        "base_readiness_passed": False,
        "adaptive_controller_allowed": False,
        "terminal_victory_probability_available": False,
        "claim_scope": "public_only_native_A8_bootstrap_learning_pipeline_control"
        if d["stage"] == "short_learning_control"
        else "finite_native_A8_policy_only_bootstrap_pilot",
    }
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(output / "summary.json", result)
    return result
