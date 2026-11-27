"""Finite same-game feature comparison; original numerical kernels stay pinned.

Three encodings, three paired training seeds, separate PPO/teacher learners.
Only the teacher sees oracle labels. This never launches native games or admits
synthetic/recovered data to production PPO.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_policy import FullRunModel, score_features
from spireshift.full_run_ppo_math import Adam, Sample, fit_round, log_softmax
from spireshift.native_action_context import MODES, ActionContextModel, encode, initialize
from spireshift.native_conditional_control import SOURCES as PREVIOUS_SOURCES
from spireshift.native_conditional_control import TASK, output_path, passed, teach_round
from spireshift.native_conditional_control import load_config as load_previous
from spireshift.native_learning_control import public_input
from spireshift.native_value_credit import ValueRun, cross_fitted_predictions, public_value_features
from spireshift.training_objective import TrainingScoreSpec

SOURCES = (*PREVIOUS_SOURCES, "native_action_context.py", "native_action_context_study.py")
HELD_HP = (16, 24, 64, 72)
LIMITS = {
    "wall_seconds": 240,
    "cpu_seconds": 240,
    "resident_memory_bytes": 1000000000,
    "storage_bytes": 40000000,
}


def catalog(
    model: ActionContextModel, score: TrainingScoreSpec, *, hide_hp: bool = False
) -> dict[tuple[bool, bool, int], Any]:
    result = {}
    for high in (False, True):
        for reverse in (False, True):
            for stage in range(6):
                public = public_input(TASK, high, stage, reverse, hide_hp=hide_hp)
                rows, state = encode(public, model, score)
                features, potential = public_value_features(public, score)
                if potential:
                    raise ValueError("Synthetic comparison cannot acquire progress rewards")
                result[high, reverse, stage] = (rows, state, features)
    return result


def collect(
    model: ActionContextModel,
    data: dict[tuple[bool, bool, int], Any],
    settings: dict[str, Any],
    seed: int,
    index: int,
    episodes: int,
) -> tuple[list[Sample], list[int], dict[str, Any]]:
    rng = random.Random(f"synthetic-ppo-v1|{seed}|{index}")
    tables = {
        key: (
            *value,
            log_softmax(
                score_features(cast(FullRunModel, model.actor), value[0]), settings["temperature"]
            ),
        )
        for key, value in data.items()
    }
    runs: list[ValueRun] = []
    samples: list[Sample] = []
    labels: list[int] = []
    outcomes: list[dict[str, Any]] = []
    for episode in range(episodes):
        high, reverse = bool(rng.getrandbits(1)), bool(rng.getrandbits(1))
        decisions = []
        action = -1
        optimal = max((0, 1), key=lambda a: TASK.probability(high, a))
        for stage in range(6):
            rows, state, features, logs = tables[high, reverse, stage]
            draw, cumulative, selected = rng.random(), 0.0, len(rows) - 1
            for i, lp in enumerate(logs):
                cumulative += math.exp(lp)
                if draw < cumulative:
                    selected = i
                    break
            if not stage:
                action = 1 - selected if reverse else selected
            decisions.append((rows, state, features, logs, selected))
            labels.append((1 - optimal if reverse else optimal) if not stage else 0)
        victory = float(rng.random() < TASK.probability(high, action))
        identifier = (index - 1) * episodes + episode
        runs.append(
            ValueRun(
                identifier,
                index,
                victory,
                tuple(d[2] for d in decisions),
                (0.0,) * 6,
                tuple(model.value(d[1]) for d in decisions),
                tuple(len(d[0]) for d in decisions),
            )
        )
        samples.extend(
            Sample(rows, state, selected, logs[selected], victory, 0.0)
            for rows, state, _, logs, selected in decisions
        )
        outcomes.append(
            {"high_hp": high, "menu_reversed": reverse, "action": action, "victory": bool(victory)}
        )
    predictions, folds = cross_fitted_predictions(
        runs, "public_residual_ridge", 0.001, 4, "native-whole-run-value-crossfit-v1"
    )
    prepared = [
        replace(sample, advantage=sample.target - value)
        for sample, value in zip(
            samples, (v for run in runs for v in predictions[run.seed]), strict=True
        )
    ]
    return (
        prepared,
        labels,
        {
            "complete_synthetic_episodes": episodes,
            "decisions": len(prepared),
            "choice_bearing_decisions": episodes,
            "supervised_labels_supplied_to_PPO": 0,
            "intermediate_rewards": 0,
            "no_self_outcome_fitting": all(
                set(f["fitting_runs"]).isdisjoint(f["predicted_runs"]) for f in folds
            ),
            "outcomes": outcomes,
        },
    )


def evaluate(
    model: ActionContextModel,
    score: TrainingScoreSpec,
    temperature: float,
    *,
    held: bool = False,
    hide_hp: bool = False,
) -> dict[str, Any]:
    results = []
    for hp in HELD_HP if held else (8, 80):
        commit = 0.1 + 0.75 * (hp - 8) / 72
        for reverse in (False, True):
            public = public_input(TASK, hp == 80, reverse=reverse, hide_hp=hide_hp)
            public["context"]["persistent"]["player"]["hp"] = 40 if hide_hp else hp
            rows, _ = encode(public, model, score)
            logs = log_softmax(score_features(cast(FullRunModel, model.actor), rows), temperature)
            action_ids = (1, 0) if reverse else (0, 1)
            p = {a: math.exp(logs[i]) for i, a in enumerate(action_ids)}
            optimal = 0 if commit > 0.55 else 1
            greedy = action_ids[max(range(2), key=lambda i: (logs[i], -i))]
            results.append(
                {
                    "hp": hp,
                    "menu_reversed": reverse,
                    "optimal_action_probability": p[optimal],
                    "greedy_optimal": greedy == optimal,
                    "expected_victory": p[0] * commit + p[1] * 0.55,
                    "optimal_expected_victory": max(commit, 0.55),
                }
            )
    return {
        "states": results,
        "expected_victory": math.fsum(s["expected_victory"] for s in results) / len(results),
        "optimal_expected_victory": math.fsum(s["optimal_expected_victory"] for s in results)
        / len(results),
        "minimum_optimal_action_probability": min(s["optimal_action_probability"] for s in results),
        "greedy_accuracy": sum(s["greedy_optimal"] for s in results) / len(results),
        "held_out_health_values": held,
        "synthetic_episodes_sampled": 0,
    }


def train_pair(
    cfg: dict[str, Any],
    settings: dict[str, Any],
    score: TrainingScoreSpec,
    mode: str,
    seed: int,
    deadline: float,
    output: Path,
) -> dict[str, Any]:
    environment = manifest_identifier({"synthetic_task_v1": TASK.as_dict()})
    initial = initialize(environment, score.spec_id, seed, mode)
    data = catalog(initial, score)
    models = {name: initial for name in ("ppo", "teacher")}
    if seed == 0:
        models["hp_removed_teacher"] = initial
    optimizers = {name: Adam.zero(initial.parameter_count) for name in models}
    curves: dict[str, list[dict[str, Any]]] = {
        name: [
            {
                "round": 0,
                "evaluation": evaluate(
                    m, score, settings["temperature"], hide_hp=name == "hp_removed_teacher"
                ),
            }
        ]
        for name, m in models.items()
    }
    masked = catalog(initial, score, hide_hp=True) if seed == 0 else {}
    work = {
        name: {"optimizer_steps": 0, "sample_decision_presentations": 0, "choice_presentations": 0}
        for name in models
    }
    prefix = f"{mode}-seed-{seed}"
    for index in range(1, cfg["rounds"] + 1):
        if time.monotonic() > deadline:
            raise TimeoutError("Finite action-context comparison wall cap")
        samples, labels, collection = collect(
            models["ppo"], data, settings, seed, index, cfg["episodes_per_round"]
        )
        updated, optimizers["ppo"], ppo = fit_round(
            cast(Any, models["ppo"]), optimizers["ppo"], samples, settings, index
        )
        if not isinstance(updated, ActionContextModel):
            raise ValueError("Original numerical kernel lost the encoding identity")
        models["ppo"] = updated
        ppo["sample_decision_presentations"] = len(samples) * ppo["epochs_completed"]
        ppo["choice_presentations"] = cfg["episodes_per_round"] * ppo["epochs_completed"]
        diagnostics = {"ppo": ppo}
        for name in models:
            if name == "ppo":
                continue
            own = samples
            if name == "hp_removed_teacher":
                own = [
                    replace(
                        samples[i * 6 + stage],
                        rows=masked[o["high_hp"], o["menu_reversed"], stage][0],
                        state=masked[o["high_hp"], o["menu_reversed"], stage][1],
                    )
                    for i, o in enumerate(collection["outcomes"])
                    for stage in range(6)
                ]
            fitted, optimizers[name], diagnostics[name] = teach_round(
                cast(Any, models[name]), optimizers[name], own, labels, settings, index, ppo
            )
            if not isinstance(fitted, ActionContextModel):
                raise ValueError("Teacher lost its encoding identity")
            models[name] = fitted
        for name, diagnostic in diagnostics.items():
            for field in work[name]:
                work[name][field] += diagnostic[field]
            if name != "ppo" and any(diagnostic[field] != ppo[field] for field in work[name]):
                raise ValueError("Within-encoding teacher work differs from PPO")
            if index % 8 == 0 or index == cfg["rounds"]:
                curves[name].append(
                    {
                        "round": index,
                        "evaluation": evaluate(
                            models[name],
                            score,
                            settings["temperature"],
                            hide_hp=name == "hp_removed_teacher",
                        ),
                    }
                )
        body = {
            "mode": mode,
            "seed": seed,
            "round": index,
            "collection": collection,
            "optimizer": diagnostics,
            "supervised_labels_teacher_only": labels,
            "model_ids": {n: m.model_id for n, m in models.items()},
        }
        atomic_json(
            output / f"{prefix}-round-{index:02d}.json",
            {**body, "report_id": manifest_identifier(body)},
        )
        if index % 8 == 0:
            p, t = (curves[n][-1]["evaluation"]["expected_victory"] for n in ("ppo", "teacher"))
            print(
                f"{mode}, seed {seed}, round {index}: PPO {p:.3f}; taught {t:.3f}; "
                f"{optimizers['ppo'].steps} updates each.",
                flush=True,
            )
    results = []
    for name, model in models.items():
        model = ActionContextModel.from_mapping(model.as_dict())
        final = curves[name][-1]["evaluation"]
        results.append(
            {
                "method": name,
                "initial_model_id": initial.model_id,
                "final_model_id": model.model_id,
                "work": work[name],
                "curve": curves[name],
                "final": final,
                "held_out": evaluate(
                    model,
                    score,
                    settings["temperature"],
                    held=True,
                    hide_hp=name == "hp_removed_teacher",
                ),
                "passed": passed(curves[name][0]["evaluation"], final, cfg["acceptance"]),
            }
        )
        atomic_json(output / f"{prefix}-{name}-synthetic-model.json", model.as_dict())
    body = {
        "mode": mode,
        "seed": seed,
        "results": results,
        "parameter_count": initial.parameter_count,
        "core_actor_parameters": initial.actor.parameter_count,
        "core_dimension": initial.actor.dimension,
        "core_hidden_units": initial.actor.hidden_units,
        "game_budget": cfg["rounds"] * cfg["episodes_per_round"],
        "native_episode_data": False,
        "final_only_no_selection": True,
    }
    return {**body, "report_id": manifest_identifier(body)}


def load_config(root: Path, path: Path) -> tuple[dict[str, Any], dict[str, Any], TrainingScoreSpec]:
    cfg = json.loads(path.read_text())
    parent, settings, score = load_previous(root, root / cfg["reference_control"]["path"])
    if (
        cfg.get("schema_version") != "native-action-context-study-config-v1"
        or cfg.get("modes") != list(MODES)
        or cfg.get("training_seeds") != [0, 1, 2]
        or cfg.get("rounds") != 32
        or cfg.get("episodes_per_round") != 64
        or cfg.get("held_out_hp") != list(HELD_HP)
        or cfg.get("held_reward_rule")
        != "commit_linear_0.1_to_0.85_between_HP_8_and_80_decline_0.55"
        or cfg.get("initializer") != "common_zero_hidden_output_no_frozen_layers_v1"
        or cfg.get("resource_limits") != LIMITS
        or cfg.get("objective") != parent["objective"]
        or cfg.get("acceptance") != parent["acceptance"]
        or manifest_identifier(parent) != cfg["reference_control"]["id"]
        or cfg.get("implementation_sha256")
        != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
    ):
        raise ValueError(
            "Freeze modes, source, objective, common initializer, budgets and held contexts"
        )
    return cfg, settings, score


def run_study(root: Path, path: Path) -> dict[str, Any]:
    cfg, settings, score = load_config(root, path)
    output = output_path(root, cfg)
    if output.exists():
        if not (output / "report.json").exists():
            raise FileExistsError("Preserve unfinished action-context evidence")
        cached = identified(output / "report.json")
        if (
            cached["config_id"] != manifest_identifier(cfg)
            or json.loads((output / "config-at-launch.json").read_text()) != cfg
        ):
            raise ValueError("Saved action-context recipe changed")
        for ref in cached["files"]:
            p = output / ref["path"]
            if p.name != ref["path"] or p.is_symlink() or _sha_file(p) != ref["sha256"]:
                raise ValueError("Saved action-context evidence changed")
        return cached
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "config-at-launch.json", cfg)
    started, cpu = time.monotonic(), time.process_time()
    pairs, attempted = [], []
    status, error = "complete", None
    try:
        for seed in cfg["training_seeds"]:
            initials = [
                initialize(
                    manifest_identifier({"synthetic_task_v1": TASK.as_dict()}),
                    score.spec_id,
                    seed,
                    mode,
                )
                for mode in MODES
            ]
            if any(m.weights() != initials[0].weights() for m in initials):
                raise ValueError("Initial numerical weights differ")
            evaluations = [evaluate(m, score, settings["temperature"]) for m in initials]
            if any(e != evaluations[0] for e in evaluations):
                raise ValueError("Initial policies differ")
            for mode in MODES:
                attempted.append((mode, seed))
                pair = train_pair(
                    cfg, settings, score, mode, seed, started + LIMITS["wall_seconds"] - 3, output
                )
                atomic_json(output / f"{mode}-seed-{seed}-pair.json", pair)
                pairs.append(pair)
    except (ValueError, TimeoutError, OSError) as exc:
        status, error = "incomplete", str(exc)
    files = [
        {"path": p.name, "sha256": _sha_file(p)}
        for p in sorted(output.glob("*.json"))
        if p.name != "config-at-launch.json"
    ]
    rounds = [identified(output / ref["path"]) for ref in files if "-round-" in ref["path"]]
    results = [{"mode": p["mode"], "seed": p["seed"], **r} for p in pairs for r in p["results"]]
    checks = {
        "all_nine_pairs_complete": status == "complete" and len(pairs) == 9,
        "same_parameter_count": bool(pairs) and len({p["parameter_count"] for p in pairs}) == 1,
        "within_encoding_work_matched": all(
            all(
                d[k] == r["optimizer"]["ppo"][k]
                for k in (
                    "optimizer_steps",
                    "choice_presentations",
                    "sample_decision_presentations",
                )
            )
            for r in rounds
            for d in r["optimizer"].values()
        ),
        "HP_removed_control_cannot_resolve_context": len(
            [r for r in results if r["method"] == "hp_removed_teacher"]
        )
        == 3
        and all(
            r["final"]["greedy_accuracy"] == 0.5 and r["final"]["expected_victory"] <= 0.55 + 1e-12
            for r in results
            if r["method"] == "hp_removed_teacher"
        ),
    }
    body = {
        "schema_version": "native-action-context-study-v1",
        "config_id": manifest_identifier(cfg),
        "status": status,
        "error": error,
        "checks": checks,
        "integrity_pass": all(checks.values()),
        "results": results,
        "files": files,
        "planned_pairs": 9,
        "completed_pairs": len(pairs),
        "failed_pairs": len(attempted) - len(pairs),
        "not_attempted_pairs": 9 - len(attempted),
        "sampled_synthetic_episodes": sum(
            r["collection"]["complete_synthetic_episodes"] for r in rounds
        ),
        "synthetic_optimizer_steps": sum(
            d["optimizer_steps"] for r in rounds for d in r["optimizer"].values()
        ),
        "unsealed_partial_work_unknown": status != "complete",
        "same_initial_parameters_and_action_probabilities": True,
        "same_game_budget_across_encodings": True,
        "actual_updates_across_encodings_may_differ_due_to_KL_stopping": True,
        "held_out_contexts_used_for_selection": False,
        "baseline_initializer_differs_from_historical_controls": True,
        "wall_seconds": time.monotonic() - started,
        "cpu_seconds": time.process_time() - cpu,
        "games_launched": 0,
        "production_optimizer_steps": 0,
        "native_episodes_opened": 0,
        "checkpoint_promoted": False,
        "base_readiness_passed": False,
        "adaptive_controller_allowed": False,
        "claim_scope": (
            "finite_synthetic_same_game_representation_comparison_not_native_learning_admission"
        ),
    }
    report = {**body, "report_id": manifest_identifier(body)}
    atomic_json(output / "report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    report = run_study(root, root / args.config)
    print(json.dumps({k: v for k, v in report.items() if k not in {"files", "results"}}, indent=2))
    for r in report["results"]:
        print(
            json.dumps(
                {
                    "mode": r["mode"],
                    "seed": r["seed"],
                    "method": r["method"],
                    "final": r["final"],
                    "held_out": r["held_out"],
                    "passed": r["passed"],
                    "work": r["work"],
                }
            )
        )
    return 0 if report["integrity_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
