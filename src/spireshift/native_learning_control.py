"""Small synthetic end-to-end controls for the unchanged native PPO learner.

These are artificial, fully specified environments, not native game episodes.
Only sampled terminal outcomes train the actor; analytic solutions are used for
evaluation. No game, saved native trajectory, or production checkpoint is opened.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.engine_neural import (
    INPUT_SCHEMA,
    NativeActorCritic,
    encode_public_input,
    fit_native_round,
    initial_actor,
    initialize_native_critic,
)
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_policy import FullRunModel, score_features
from spireshift.full_run_ppo_math import Adam, Sample, log_softmax
from spireshift.native_input_normalization import QUARTER
from spireshift.native_value_credit import (
    ValueRun,
    cross_fitted_predictions,
    public_value_features,
)
from spireshift.training_objective import TrainingScoreSpec, load_training_score_spec

SOURCES = (
    "native_learning_control.py",
    "engine_neural.py",
    "full_run_policy.py",
    "full_run_ppo_math.py",
    "native_value_credit.py",
    "native_input_normalization.py",
    "training_objective.py",
    "core/objective.py",
)


@dataclass(frozen=True)
class Task:
    name: str
    delay_steps: int
    # Rows are low/high public HP; columns are commit/decline.
    terminal_probabilities: tuple[tuple[float, float], tuple[float, float]]

    def probability(self, high_hp: bool, action: int) -> float:
        if type(action) is not int or action not in (0, 1):
            raise ValueError("Synthetic action outside its complete legal menu")
        return self.terminal_probabilities[int(high_hp)][action]

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "delay_steps": self.delay_steps,
            "terminal_probabilities_low_high_commit_decline": self.terminal_probabilities,
            "public_context_probabilities": [0.5, 0.5],
            "intermediate_rewards": 0,
            "terminal_reward": "binary_victory_only",
        }


TASKS = (
    Task("immediate", 0, ((0.0, 1.0), (0.0, 1.0))),
    Task("delayed", 5, ((0.0, 1.0), (0.0, 1.0))),
    Task("contextual_risk", 5, ((0.10, 0.55), (0.85, 0.55))),
)


def public_input(
    task: Task, high_hp: bool, stage: int = 0, reverse: bool = False, *, hide_hp: bool = False
) -> dict[str, Any]:
    if type(stage) is not int or not 0 <= stage <= task.delay_steps:
        raise ValueError("Synthetic stage is outside the finite task")
    candidates: list[dict[str, Any]] = [
        {"verb": verb, "label": label, "arguments": [], "subject": None}
        for verb, label in (("play", "Commit"), ("skip", "Decline"))
    ]
    if stage:
        candidates = [{"verb": "confirm", "label": "Continue", "arguments": [], "subject": None}]
    if reverse:
        candidates.reverse()
    return {
        "schema_version": INPUT_SCHEMA,
        "context": {
            "persistent": {
                "run": {"act": 1, "floor": 0},
                "player": {
                    "hp": 40 if hide_hp else (80 if high_hp else 8),
                    "max_hp": 80,
                    "gold": 0,
                    "relics": [],
                    "potions": [],
                },
            },
            "interaction": {"kind": "event_option", "synthetic_task": task.name, "stage": stage},
            "reads": [{"kind": "run_deck", "content": {"card_count": 0}}],
        },
        "candidates": candidates,
    }


def policy_logs(
    model: NativeActorCritic, public: dict[str, Any], temperature: float
) -> tuple[tuple[dict[int, float], ...], tuple[float, ...], tuple[float, ...]]:
    rows, state = encode_public_input(
        public, model.actor.dimension, model.actor.input_normalization
    )
    return (
        rows,
        state,
        log_softmax(score_features(cast(FullRunModel, model.actor), rows), temperature),
    )


def evaluate(
    model: NativeActorCritic, task: Task, temperature: float, *, hide_hp: bool = False
) -> dict[str, Any]:
    """Exact finite-state expectation; no sampled evaluation rewards or fitting."""
    states = []
    for high in (False, True):
        for reverse in (False, True):
            _, _, logs = policy_logs(
                model, public_input(task, high, reverse=reverse, hide_hp=hide_hp), temperature
            )
            action_ids = (1, 0) if reverse else (0, 1)
            probabilities = {action: math.exp(logs[i]) for i, action in enumerate(action_ids)}
            optimal = max((0, 1), key=lambda a: task.probability(high, a))
            greedy = action_ids[max(range(2), key=lambda i: (logs[i], -i))]
            states.append(
                {
                    "high_hp": high,
                    "menu_reversed": reverse,
                    "optimal_action_probability": probabilities[optimal],
                    "greedy_optimal": greedy == optimal,
                    "expected_victory": math.fsum(
                        probabilities[a] * task.probability(high, a) for a in (0, 1)
                    ),
                }
            )
    return {
        "states": states,
        "expected_victory": math.fsum(s["expected_victory"] for s in states) / len(states),
        "optimal_expected_victory": math.fsum(
            max(task.terminal_probabilities[int(high)]) for high in (False, True)
        )
        / 2,
        "minimum_optimal_action_probability": min(s["optimal_action_probability"] for s in states),
        "greedy_accuracy": sum(s["greedy_optimal"] for s in states) / len(states),
        "synthetic_episodes_sampled": 0,
    }


def collect_round(
    model: NativeActorCritic,
    task: Task,
    score: TrainingScoreSpec,
    settings: dict[str, Any],
    seed: int,
    round_index: int,
    episodes: int,
) -> tuple[list[Sample], dict[str, Any]]:
    """Fresh on-policy play, terminal outcomes, whole-game cross-fitted credit.

    The numerical learner sees public inputs and the realized binary terminal
    outcome only. The analytic optimal action never supplies a label or advantage.
    Stage>0 menus have one legal action and remain in advantage normalization.
    """
    rng = random.Random(f"synthetic-ppo-v1|{seed}|{round_index}")
    cached = {}
    for high in (False, True):
        for reverse in (False, True):
            for stage in range(task.delay_steps + 1):
                p = public_input(task, high, stage, reverse)
                rows, state, logs = policy_logs(model, p, settings["temperature"])
                features, potential = public_value_features(p, score)
                if potential != 0:
                    raise ValueError(
                        "Synthetic terminal-only tasks cannot acquire progress shaping"
                    )
                cached[high, reverse, stage] = (rows, state, logs, features)
    runs: list[ValueRun] = []
    samples: list[Sample] = []
    outcomes: list[dict[str, Any]] = []
    for episode in range(episodes):
        high, reverse = bool(rng.getrandbits(1)), bool(rng.getrandbits(1))
        decisions = []
        first_action = -1
        for stage in range(task.delay_steps + 1):
            rows, state, logs, features = cached[high, reverse, stage]
            draw, cumulative, selected = rng.random(), 0.0, len(rows) - 1
            for i, logp in enumerate(logs):
                cumulative += math.exp(logp)
                if draw < cumulative:
                    selected = i
                    break
            if not stage:
                first_action = (1 - selected) if reverse else selected
            decisions.append((rows, state, logs, features, selected))
        # No reward, label, terminal random draw or optimal choice is available
        # to an earlier decision. All forced continuation steps finish first.
        outcome = float(rng.random() < task.probability(high, first_action))
        identifier = (round_index - 1) * episodes + episode
        run = ValueRun(
            identifier,
            round_index,
            outcome,
            tuple(d[3] for d in decisions),
            (0.0,) * len(decisions),
            tuple(model.value(d[1]) for d in decisions),
            tuple(len(d[0]) for d in decisions),
        )
        runs.append(run)
        samples.extend(
            Sample(rows, state, selected, logs[selected], outcome, 0.0)
            for rows, state, logs, _, selected in decisions
        )
        outcomes.append({"high_hp": high, "action": first_action, "victory": bool(outcome)})
    predictions, folds = cross_fitted_predictions(
        runs, "public_residual_ridge", 0.001, 4, "native-whole-run-value-crossfit-v1"
    )
    offset, prepared = 0, []
    for run in runs:
        for value in predictions[run.seed]:
            prepared.append(replace(samples[offset], advantage=run.target - value))
            offset += 1
    return prepared, {
        "complete_synthetic_episodes": episodes,
        "decisions": len(prepared),
        "choice_bearing_decisions": episodes,
        "forced_continuations": len(prepared) - episodes,
        "outcomes": outcomes,
        "folds": [
            {k: fold[k] for k in ("fold", "fitting_runs", "predicted_runs")} for fold in folds
        ],
        "no_self_outcome_fitting": all(
            set(f["fitting_runs"]).isdisjoint(f["predicted_runs"]) for f in folds
        ),
        "supervised_action_labels": 0,
        "intermediate_rewards": 0,
    }


def learn_task(
    task: Task,
    score: TrainingScoreSpec,
    settings: dict[str, Any],
    *,
    seed: int,
    rounds: int,
    episodes: int,
    deadline: float,
    frozen_actor: bool = False,
) -> dict[str, Any]:
    environment_id = manifest_identifier({"synthetic_task_v1": task.as_dict()})
    model = initialize_native_critic(
        initial_actor(environment_id, 512, 32, seed, input_normalization=QUARTER)
    )
    initial, initial_actor_genome = model.model_id, model.actor.genome
    optimizer = Adam.zero(model.parameter_count)
    own_settings = {**settings, **({"actor_learning_rate": 0.0} if frozen_actor else {})}
    curve: list[dict[str, Any]] = [
        {"round": 0, "evaluation": evaluate(model, task, settings["temperature"])}
    ]
    updates = []
    for index in range(1, rounds + 1):
        if time.monotonic() >= deadline:
            raise TimeoutError("Short synthetic learning control reached its wall cap")
        samples, collection = collect_round(model, task, score, settings, seed, index, episodes)
        previous = model.model_id
        model, optimizer, diagnostic = fit_native_round(
            model, optimizer, samples, own_settings, index
        )
        updates.append(
            {
                "round": index,
                "behavior_model_id": previous,
                "updated_model_id": model.model_id,
                "collection": collection,
                "optimizer": diagnostic,
            }
        )
        if index % 8 == 0 or index == rounds:
            curve.append(
                {"round": index, "evaluation": evaluate(model, task, settings["temperature"])}
            )
            print(
                f"Synthetic {task.name}, seed {seed}, round {index}/{rounds}: "
                f"expected win {curve[-1]['evaluation']['expected_victory']:.3f}. "
                f"{'Frozen actor control.' if frozen_actor else 'Toy task only.'}",
                flush=True,
            )
    final = curve[-1]["evaluation"]
    return {
        "task": task.name,
        "training_seed": seed,
        "frozen_actor": frozen_actor,
        "initial_model_id": initial,
        "final_model_id": model.model_id,
        "actor_unchanged": model.actor.genome == initial_actor_genome,
        "complete_synthetic_episodes": rounds * episodes,
        "synthetic_optimizer_steps": optimizer.steps,
        "learning_curve": curve,
        "updates": updates,
        "final": final,
        "hp_removed_negative_control": (
            evaluate(model, task, settings["temperature"], hide_hp=True)
            if task.name == "contextual_risk"
            else None
        ),
        "final_only_no_checkpoint_selection": True,
        "production_checkpoint_written": False,
    }


def load_config(root: Path, path: Path) -> tuple[dict[str, Any], dict[str, Any], TrainingScoreSpec]:
    cfg = json.loads(path.read_text())
    if (
        cfg.get("schema_version") != "synthetic-native-ppo-control-config-v1"
        or cfg.get("tasks") != json.loads(json.dumps([t.as_dict() for t in TASKS]))
        or cfg.get("training_seeds") != [0, 1, 2]
        or cfg.get("rounds") != 32
        or cfg.get("episodes_per_round") != 64
        or cfg.get("frozen_actor_rounds") != 4
        or cfg.get("implementation_sha256")
        != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("acceptance")
        != {"minimum_optimal_action_probability": 0.75, "minimum_exact_victory_gain": 0.10}
    ):
        raise ValueError("Freeze the finite synthetic tasks, scope, criteria and implementation")
    objective = ObjectiveSpec.from_mapping(cfg["objective"])
    if objective.objective_id != "terminal-victory-v1" or objective.whole_run_budget != 128:
        raise ValueError("Synthetic binary endings cannot change the production objective")
    recipe = json.loads((root / cfg["reference_recipe"]["path"]).read_text())
    score = load_training_score_spec(root / recipe["training_spec"]["path"])
    if (
        manifest_identifier(recipe) != cfg["reference_recipe"]["id"]
        or score.spec_id != recipe["training_spec"]["id"]
        or recipe["network"]["dimension"] != 512
        or recipe["network"]["hidden_units"] != 32
        or recipe["network"]["input_normalization"] != QUARTER
        or cfg["resource_limits"]
        != {
            "wall_seconds": 180,
            "cpu_seconds": 180,
            "resident_memory_bytes": 1000000000,
            "storage_bytes": 20000000,
        }
    ):
        raise ValueError("Synthetic control requires the unchanged normalized learner and caps")
    return cfg, recipe["learning"]["ppo"], score


def run_control(root: Path, config_path: Path) -> dict[str, Any]:
    cfg, settings, score = load_config(root, config_path)
    relative = Path(cfg["workspace"])
    if relative.is_absolute() or ".." in relative.parts or relative.parts[:1] != ("artifacts",):
        raise ValueError("Synthetic output must be a separate artifacts directory")
    output = root / relative
    if output.is_symlink() or output.resolve() != root.resolve() / relative:
        raise ValueError("Synthetic output cannot alias another workspace")
    result_path = output / "report.json"
    if output.exists():
        if not result_path.is_file():
            raise FileExistsError("Preserve interrupted synthetic evidence; no automatic restart")
        report: dict[str, Any] = json.loads(result_path.read_text())
        if report.get("config_id") != manifest_identifier(cfg) or report.get(
            "report_id"
        ) != manifest_identifier({k: v for k, v in report.items() if k != "report_id"}):
            raise ValueError("Saved synthetic result changed")
        return report
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "config-at-launch.json", cfg)
    started, cpu = time.monotonic(), time.process_time()
    arms: list[dict[str, Any]] = []
    status, error = "complete", None
    try:
        for task in TASKS:
            for seed in cfg["training_seeds"]:
                arm = learn_task(
                    task,
                    score,
                    settings,
                    seed=seed,
                    rounds=cfg["rounds"],
                    episodes=cfg["episodes_per_round"],
                    deadline=started + cfg["resource_limits"]["wall_seconds"],
                )
                arms.append(arm)
                atomic_json(output / f"{task.name}-seed-{seed}.json", arm)
        frozen = learn_task(
            TASKS[1],
            score,
            settings,
            seed=0,
            rounds=cfg["frozen_actor_rounds"],
            episodes=cfg["episodes_per_round"],
            deadline=started + cfg["resource_limits"]["wall_seconds"],
            frozen_actor=True,
        )
        arms.append(frozen)
        atomic_json(output / "delayed-frozen-actor.json", frozen)
    except (ValueError, TimeoutError, OSError) as exc:
        status, error = "incomplete", str(exc)
    criteria = cfg["acceptance"]
    results = [
        {
            "task": arm["task"],
            "seed": arm["training_seed"],
            "expected_victory_gain": (
                arm["final"]["expected_victory"]
                - arm["learning_curve"][0]["evaluation"]["expected_victory"]
            ),
            "passed": (
                arm["final"]["minimum_optimal_action_probability"]
                >= criteria["minimum_optimal_action_probability"]
                and arm["final"]["expected_victory"]
                - arm["learning_curve"][0]["evaluation"]["expected_victory"]
                >= criteria["minimum_exact_victory_gain"]
            ),
        }
        for arm in arms
        if not arm["frozen_actor"]
    ]
    negative = [a for a in arms if a["frozen_actor"]]
    checks = {
        "all_planned_arms_complete": len(arms) == 10 and status == "complete",
        "all_predeclared_learning_thresholds": len(results) == 9
        and all(r["passed"] for r in results),
        "frozen_actor_and_performance_unchanged": len(negative) == 1
        and negative[0]["actor_unchanged"]
        and negative[0]["final"] == negative[0]["learning_curve"][0]["evaluation"],
        "hp_removed_control_at_most_unconditional_optimum": len(arms) == 10
        and all(
            a["hp_removed_negative_control"]["expected_victory"] <= 0.55 + 1e-12
            and a["hp_removed_negative_control"]["greedy_accuracy"] == 0.5
            for a in arms
            if a["task"] == "contextual_risk"
        ),
    }
    body = {
        "schema_version": "synthetic-native-ppo-control-v1",
        "config_id": manifest_identifier(cfg),
        "status": status,
        "error": error,
        "checks": checks,
        "learning_control_pass": all(checks.values()),
        "results": results,
        "complete_synthetic_episodes": sum(a["complete_synthetic_episodes"] for a in arms),
        "synthetic_optimizer_steps": sum(a["synthetic_optimizer_steps"] for a in arms),
        "wall_seconds": time.monotonic() - started,
        "cpu_seconds": time.process_time() - cpu,
        "production_optimizer_steps": 0,
        "games_launched": 0,
        "game_apps_created": 0,
        "native_episodes_opened": 0,
        "production_checkpoints_written": 0,
        "checkpoint_promoted": False,
        "base_readiness_passed": False,
        "adaptive_controller_allowed": False,
        "claim_scope": "synthetic_terminal_only_tasks_with_native_numerical_learner_not_STS2_skill",
        "objective": cfg["objective"],
        "native_score_parameters_used_for_baseline_features_only": True,
        "native_wrapper_and_engine_transition_coverage": False,
    }
    report = {**body, "report_id": manifest_identifier(body)}
    atomic_json(result_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        report = run_control(root, root / args.config)
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), flush=True)
        return 1
    print(json.dumps(report, indent=2), flush=True)
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
