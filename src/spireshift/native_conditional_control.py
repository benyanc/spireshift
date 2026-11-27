"""Matched-work direct teaching versus PPO on the existing synthetic HP task.

Only the synthetic teacher receives optimal-action labels. They never enter public
inputs or PPO credit. No game, native episode or production checkpoint is opened.
Historical pinned numerical code and the earlier negative control stay unchanged.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.engine_learning import identified
from spireshift.engine_neural import (
    NativeActorCritic,
    encode_public_input,
    fit_native_round,
    initial_actor,
    initialize_native_critic,
)
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_policy import FullRunModel, score_features, score_gradient
from spireshift.full_run_ppo_math import Adam, Sample, log_softmax, loss_gradient
from spireshift.native_input_normalization import QUARTER
from spireshift.native_learning_control import SOURCES as KNOWN_SOURCES
from spireshift.native_learning_control import TASKS, collect_round, evaluate, public_input
from spireshift.native_learning_control import load_config as load_known_config
from spireshift.neural_combat import _numpy
from spireshift.training_objective import TrainingScoreSpec

SOURCES = (*KNOWN_SOURCES, "native_conditional_control.py")
TASK = TASKS[2]
SCHEDULE = "replay_realized_PPO_epoch_minibatch_schedule_v1"


def teaching_examples(
    model: NativeActorCritic,
    samples: Sequence[Sample],
    collection: dict[str, Any],
    *,
    hide_hp: bool = False,
) -> tuple[list[Sample], list[int]]:
    """Bind oracle labels to the same public contexts and actual candidate order.

    The terminal outcome and PPO's sampled action do not determine the label. The
    masked control keeps these labels but removes HP coherently from every input.
    """
    block = TASK.delay_steps + 1
    if len(samples) != block * len(collection["outcomes"]):
        raise ValueError("Teaching examples lost an episode or continuation menu")
    examples, labels = [], []
    for index, outcome in enumerate(collection["outcomes"]):
        high = outcome["high_hp"]
        if type(high) is not bool:
            raise ValueError("Synthetic HP context must be public and boolean")
        start = samples[index * block]
        matches = [
            reverse
            for reverse in (False, True)
            if encode_public_input(
                public_input(TASK, high, reverse=reverse),
                model.actor.dimension,
                model.actor.input_normalization,
            )
            == (start.rows, start.state)
        ]
        if len(matches) != 1:
            raise ValueError("Cannot bind the teacher to the exact public candidate order")
        reverse = matches[0]
        optimal = max((0, 1), key=lambda a: TASK.probability(high, a))
        for stage in range(block):
            sample = samples[index * block + stage]
            source = encode_public_input(
                public_input(TASK, high, stage, reverse),
                model.actor.dimension,
                model.actor.input_normalization,
            )
            if source != (sample.rows, sample.state):
                raise ValueError("Teacher and PPO must use the same ordered public inputs")
            rows, state = encode_public_input(
                public_input(TASK, high, stage, reverse, hide_hp=hide_hp),
                model.actor.dimension,
                model.actor.input_normalization,
            )
            examples.append(replace(sample, rows=rows, state=state))
            labels.append((1 - optimal if reverse else optimal) if not stage else 0)
    return examples, labels


def teaching_gradient(
    model: NativeActorCritic,
    samples: Sequence[Sample],
    labels: Sequence[int],
    settings: dict[str, Any],
) -> tuple[float, tuple[float, ...], dict[str, float]]:
    """Mean cross-entropy plus unchanged entropy/diagnostic-value losses.

    Forced menus have zero actor derivative but remain in the denominator, exactly
    as in PPO. All actor layers and the diagnostic critic use the original Adam.
    """
    if not samples or len(samples) != len(labels):
        raise ValueError("Teacher requires one legal label per supplied decision")
    np = _numpy()
    rows = tuple(row for s in samples for row in s.rows)
    logits = score_features(cast(FullRunModel, model.actor), rows)
    dz = np.zeros(len(rows), dtype=np.float64)
    offset, ce = 0, 0.0
    zero_credit = []
    for sample, label in zip(samples, labels, strict=True):
        if type(label) is not int or not 0 <= label < len(sample.rows):
            raise ValueError("Oracle label is outside the supplied legal menu")
        logp = log_softmax(logits[offset : offset + len(sample.rows)], settings["temperature"])
        p = np.exp(logp)
        p[label] -= 1.0
        dz[offset : offset + len(p)] = p / settings["temperature"] / len(samples)
        ce -= logp[label] / len(samples)
        # Preserve the sampled terminal target for the diagnostic critic. Zero
        # advantage removes reward-driven actor credit; labels train only CE.
        zero_credit.append(replace(sample, advantage=0.0, old_log_probability=logp[sample.action]))
        offset += len(p)
    regularizer, base, diagnostic = loss_gradient(
        cast(Any, model),
        zero_credit,
        clip=settings["clip"],
        entropy_coefficient=settings["entropy_coefficient"],
        value_coefficient=settings["value_coefficient"],
        temperature=settings["temperature"],
    )
    actor = score_gradient(cast(FullRunModel, model.actor), rows, dz)
    gradient = tuple(a + b for a, b in zip(actor, base[: len(actor)], strict=True))
    return (
        ce + regularizer,
        (*gradient, *base[len(actor) :]),
        {
            "cross_entropy": ce,
            "entropy": diagnostic["entropy"],
            "value_loss": diagnostic["value_loss"],
        },
    )


def teach_round(
    model: NativeActorCritic,
    optimizer: Adam,
    samples: Sequence[Sample],
    labels: Sequence[int],
    settings: dict[str, Any],
    round_index: int,
    ppo_work: dict[str, Any],
    *,
    frozen_actor: bool = False,
) -> tuple[NativeActorCritic, Adam, dict[str, Any]]:
    epochs = ppo_work["epochs_completed"]
    batches = math.ceil(len(samples) / settings["minibatch_decisions"])
    if (
        not samples
        or len(samples) != len(labels)
        or type(epochs) is not int
        or not 1 <= epochs <= settings["epochs"]
        or ppo_work["optimizer_steps"] != epochs * batches
        or ppo_work["sampled_decisions"] != len(samples)
    ):
        raise ValueError("Teacher must replay PPO's actual complete epoch/minibatch schedule")
    indices = list(range(len(samples)))
    rng, initial_steps = random.Random(round_index), optimizer.steps
    losses, norms = [], []
    decisions = choices = 0
    for _ in range(epochs):
        rng.shuffle(indices)
        for start in range(0, len(indices), settings["minibatch_decisions"]):
            positions = indices[start : start + settings["minibatch_decisions"]]
            batch = [samples[i] for i in positions]
            loss, gradient, _ = teaching_gradient(
                model, batch, [labels[i] for i in positions], settings
            )
            updated, optimizer, norm = optimizer.update(
                cast(Any, model),
                gradient,
                actor_rate=0.0 if frozen_actor else settings["actor_learning_rate"],
                value_rate=settings["value_learning_rate"],
                maximum_norm=settings["gradient_clip"],
            )
            model = cast(NativeActorCritic, updated)
            losses.append(loss)
            norms.append(norm)
            decisions += len(batch)
            choices += sum(len(s.rows) > 1 for s in batch)
    return (
        model,
        optimizer,
        {
            "optimizer_steps": optimizer.steps - initial_steps,
            "epochs_completed": epochs,
            "sample_decision_presentations": decisions,
            "choice_presentations": choices,
            "mean_loss": math.fsum(losses) / len(losses),
            "mean_gradient_norm": math.fsum(norms) / len(norms),
            "schedule": SCHEDULE,
            "teacher_KL_does_not_select_extra_work": True,
            "actor_frozen": frozen_actor,
        },
    )


def passed(initial: dict[str, Any], final: dict[str, Any], criteria: dict[str, Any]) -> bool:
    return bool(
        final["minimum_optimal_action_probability"]
        >= criteria["minimum_optimal_action_probability"]
        and final["expected_victory"] - initial["expected_victory"]
        >= criteria["minimum_exact_victory_gain"]
    )


def paired_seed(
    cfg: dict[str, Any],
    settings: dict[str, Any],
    score: TrainingScoreSpec,
    seed: int,
    deadline: float,
    output: Path | None = None,
) -> dict[str, Any]:
    environment = manifest_identifier({"synthetic_task_v1": TASK.as_dict()})
    initial = initialize_native_critic(
        initial_actor(environment, 512, 32, seed, input_normalization=QUARTER)
    )
    models = {name: initial for name in ("ppo", "direct_teaching")}
    if seed == 0:
        models.update(hp_removed=initial, frozen_actor=initial)
    optimizers = {name: Adam.zero(initial.parameter_count) for name in models}
    evaluations: dict[str, list[dict[str, Any]]] = {
        name: [
            {
                "round": 0,
                "evaluation": evaluate(
                    m, TASK, settings["temperature"], hide_hp=name == "hp_removed"
                ),
            }
        ]
        for name, m in models.items()
    }
    work = {
        name: {"optimizer_steps": 0, "sample_decision_presentations": 0, "choice_presentations": 0}
        for name in models
    }
    round_refs = []
    for index in range(1, cfg["rounds"] + 1):
        if time.monotonic() >= deadline:
            raise TimeoutError("Finite conditional-learning comparison reached its wall cap")
        samples, collection = collect_round(
            models["ppo"], TASK, score, settings, seed, index, cfg["episodes_per_round"]
        )
        examples, labels = teaching_examples(initial, samples, collection)
        before = {name: m.model_id for name, m in models.items()}
        models["ppo"], optimizers["ppo"], ppo = fit_native_round(
            models["ppo"], optimizers["ppo"], samples, settings, index
        )
        ppo["sample_decision_presentations"] = len(samples) * ppo["epochs_completed"]
        ppo["choice_presentations"] = cfg["episodes_per_round"] * ppo["epochs_completed"]
        diagnostics = {"ppo": ppo}
        for name in models:
            if name == "ppo" or name == "frozen_actor" and index > cfg["frozen_actor_rounds"]:
                continue
            own, targets = (
                teaching_examples(initial, samples, collection, hide_hp=True)
                if name == "hp_removed"
                else (examples, labels)
            )
            models[name], optimizers[name], diagnostics[name] = teach_round(
                models[name],
                optimizers[name],
                own,
                targets,
                settings,
                index,
                ppo,
                frozen_actor=name == "frozen_actor",
            )
        for name, diagnostic in diagnostics.items():
            for field in work[name]:
                work[name][field] += diagnostic[field]
            if name != "ppo" and any(diagnostic[field] != ppo[field] for field in work[name]):
                raise ValueError("Paired actual optimizer work differs")
            if (
                index % 8 == 0
                or index == cfg["rounds"]
                or name == "frozen_actor"
                and index == cfg["frozen_actor_rounds"]
            ):
                evaluations[name].append(
                    {
                        "round": index,
                        "evaluation": evaluate(
                            models[name],
                            TASK,
                            settings["temperature"],
                            hide_hp=name == "hp_removed",
                        ),
                    }
                )
        body = {
            "schema_version": "synthetic-conditional-round-v1",
            "training_seed": seed,
            "round": index,
            "behavior_model_id": before["ppo"],
            "public_input_id": manifest_identifier(
                [{"rows": s.rows, "state": s.state} for s in samples]
            ),
            "collection": collection,
            "supervised_labels_teacher_only": labels,
            "optimizer": diagnostics,
            "updated_model_ids": {name: models[name].model_id for name in diagnostics},
        }
        record = {**body, "report_id": manifest_identifier(body)}
        if output is not None:
            filename = f"seed-{seed}-round-{index:02d}.json"
            atomic_json(output / filename, record)
            round_refs.append({"path": filename, "sha256": _sha_file(output / filename)})
        if index % 8 == 0 or index == cfg["rounds"]:
            p, t = (evaluations[n][-1]["evaluation"] for n in ("ppo", "direct_teaching"))
            print(
                f"Synthetic HP seed {seed}, round {index}/{cfg['rounds']}: "
                f"PPO expected win {p['expected_victory']:.3f}; "
                f"taught {t['expected_victory']:.3f}; {optimizers['ppo'].steps} updates each.",
                flush=True,
            )
    methods = []
    for name, model in models.items():
        last = evaluations[name][-1]["evaluation"]
        methods.append(
            {
                "name": name,
                "initial_model_id": initial.model_id,
                "final_model_id": model.model_id,
                "actor_unchanged": initial.actor.genome == model.actor.genome,
                "critic_unchanged": initial.value_weights == model.value_weights,
                "work": work[name],
                "curve": evaluations[name],
                "final": last,
                "passed_learning_criterion": passed(
                    evaluations[name][0]["evaluation"], last, cfg["acceptance"]
                ),
            }
        )
    body = {
        "schema_version": "synthetic-conditional-pair-v1",
        "training_seed": seed,
        "methods": methods,
        "round_files": round_refs,
        "sampled_synthetic_episodes": cfg["rounds"] * cfg["episodes_per_round"],
        "same_initial_weights_and_public_inputs": True,
        "paired_actual_work_equal": work["ppo"] == work["direct_teaching"],
        "teacher_uses_extra_oracle_information": True,
        "same_CPU_or_information_budget_claimed": False,
        "final_only_no_checkpoint_selection": True,
    }
    return {**body, "report_id": manifest_identifier(body)}


def load_config(root: Path, path: Path) -> tuple[dict[str, Any], dict[str, Any], TrainingScoreSpec]:
    cfg = json.loads(path.read_text())
    if (
        cfg.get("schema_version") != "synthetic-native-conditional-comparison-config-v1"
        or cfg.get("task") != json.loads(json.dumps(TASK.as_dict()))
        or cfg.get("training_seeds") != [0, 1, 2]
        or cfg.get("rounds") != 32
        or cfg.get("episodes_per_round") != 64
        or cfg.get("frozen_actor_rounds") != 4
        or cfg.get("teaching_schedule") != SCHEDULE
        or cfg.get("teacher_receives_optimal_action_labels") is not True
        or cfg.get("ppo_receives_optimal_action_labels") is not False
        or cfg.get("implementation_sha256")
        != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("resource_limits")
        != {
            "wall_seconds": 180,
            "cpu_seconds": 180,
            "resident_memory_bytes": 1000000000,
            "storage_bytes": 20000000,
        }
    ):
        raise ValueError(
            "Freeze conditional task, matched work, information boundary, sources and caps"
        )
    reference, settings, score = load_known_config(root, root / cfg["reference_control"]["path"])
    objective = ObjectiveSpec.from_mapping(cfg["objective"])
    if (
        manifest_identifier(reference) != cfg["reference_control"]["id"]
        or cfg["objective"] != reference["objective"]
        or objective.objective_id != "terminal-victory-v1"
        or cfg.get("acceptance") != reference["acceptance"]
    ):
        raise ValueError("Conditional comparison changed the reference settings or objective")
    return cfg, settings, score


def output_path(root: Path, cfg: dict[str, Any]) -> Path:
    p = Path(cfg["workspace"])
    if (
        p.is_absolute()
        or ".." in p.parts
        or p.parts[:2] != ("artifacts", "synthetic-learning")
        or len(p.parts) != 3
    ):
        raise ValueError("Use a separate synthetic artifact workspace")
    result = root / p
    if result.resolve() != root.resolve() / p or result.is_symlink():
        raise ValueError("Synthetic output cannot alias another directory")
    return result


def run_comparison(root: Path, path: Path) -> dict[str, Any]:
    cfg, settings, score = load_config(root, path)
    output = output_path(root, cfg)
    if output.exists():
        if not (output / "report.json").is_file():
            raise FileExistsError("Preserve interrupted comparison; no automatic restart")
        cached = identified(output / "report.json")
        if (
            cached["config_id"] != manifest_identifier(cfg)
            or json.loads((output / "config-at-launch.json").read_text()) != cfg
        ):
            raise ValueError("Cached comparison belongs to changed inputs")
        for ref in cached["files"]:
            p = Path(ref["path"])
            if (
                p.name != str(p)
                or (output / p).is_symlink()
                or _sha_file(output / p) != ref["sha256"]
            ):
                raise ValueError("Saved conditional evidence changed")
        return cached
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "config-at-launch.json", cfg)
    started, cpu = time.monotonic(), time.process_time()
    pairs, files = [], []
    attempted_seeds = []
    status, error = "complete", None
    try:
        for seed in cfg["training_seeds"]:
            attempted_seeds.append(seed)
            pair = paired_seed(
                cfg,
                settings,
                score,
                seed,
                started + cfg["resource_limits"]["wall_seconds"] - 3,
                output,
            )
            filename = f"seed-{seed}.json"
            atomic_json(output / filename, pair)
            files.extend(pair["round_files"])
            files.append({"path": filename, "sha256": _sha_file(output / filename)})
            pairs.append(pair)
    except (ValueError, TimeoutError, OSError) as exc:
        status, error = "incomplete", str(exc)
    # Include a failed pair's sealed prefix too. Unsealed work is explicitly
    # unknown after interruption; it must not be presented as zero work or a
    # completed pair, and no interrupted setting is silently restarted.
    files = [{"path": p.name, "sha256": _sha_file(p)} for p in sorted(output.glob("seed-*.json"))]
    sealed_rounds = [identified(output / ref["path"]) for ref in files if "-round-" in ref["path"]]
    controls = [
        m for p in pairs for m in p["methods"] if m["name"] in {"hp_removed", "frozen_actor"}
    ]
    checks = {
        "all_three_pairs_complete": status == "complete" and len(pairs) == 3,
        "paired_actual_work_equal": len(pairs) == 3
        and all(p["paired_actual_work_equal"] for p in pairs),
        "hp_removed_cannot_resolve_context": any(
            m["name"] == "hp_removed"
            and m["final"]["greedy_accuracy"] == 0.5
            and m["final"]["expected_victory"] <= 0.55 + 1e-12
            and m["work"]["optimizer_steps"] > 0
            for m in controls
        ),
        "frozen_actor_control_executes_optimizer": any(
            m["name"] == "frozen_actor"
            and m["actor_unchanged"]
            and not m["critic_unchanged"]
            and m["work"]["optimizer_steps"] > 0
            and m["final"] == m["curve"][0]["evaluation"]
            for m in controls
        ),
    }
    results = [
        {
            "seed": p["training_seed"],
            **{
                k: m[k]
                for k in (
                    "name",
                    "initial_model_id",
                    "final_model_id",
                    "work",
                    "final",
                    "passed_learning_criterion",
                )
            },
        }
        for p in pairs
        for m in p["methods"]
    ]
    passes = {
        name: sum(r["passed_learning_criterion"] for r in results if r["name"] == name)
        for name in ("ppo", "direct_teaching")
    }
    body = {
        "schema_version": "synthetic-native-conditional-comparison-v1",
        "config_id": manifest_identifier(cfg),
        "status": status,
        "error": error,
        "checks": checks,
        "comparison_integrity_pass": all(checks.values()),
        "passing_training_seeds": passes,
        "results": results,
        "files": files,
        "planned_training_pairs": len(cfg["training_seeds"]),
        "completed_training_pairs": len(pairs),
        "failed_training_pairs": len(attempted_seeds) - len(pairs),
        "not_attempted_training_pairs": len(cfg["training_seeds"]) - len(attempted_seeds),
        "sealed_rounds": len(sealed_rounds),
        "sampled_synthetic_episodes": sum(
            r["collection"]["complete_synthetic_episodes"] for r in sealed_rounds
        ),
        "synthetic_optimizer_steps": sum(
            d["optimizer_steps"] for r in sealed_rounds for d in r["optimizer"].values()
        ),
        "unsealed_partial_work_unknown": status != "complete",
        "work_counts_are_lower_bounds_if_incomplete": True,
        "wall_seconds": time.monotonic() - started,
        "cpu_seconds": time.process_time() - cpu,
        "teacher_uses_extra_oracle_information": True,
        "same_CPU_or_information_budget_claimed": False,
        "held_out_generalization_claimed": False,
        "objective": cfg["objective"],
        "games_launched": 0,
        "native_episodes_opened": 0,
        "production_optimizer_steps": 0,
        "production_checkpoints_written": 0,
        "game_apps_created": 0,
        "checkpoint_promoted": False,
        "base_readiness_passed": False,
        "adaptive_controller_allowed": False,
        "claim_scope": (
            "synthetic_HP_conditional_learning_with_matched_optimizer_work"
            "_not_native_skill_or_method_superiority"
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
    try:
        report = run_comparison(root, root / args.config)
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), flush=True)
        return 1
    print(json.dumps({k: v for k, v in report.items() if k != "files"}, indent=2), flush=True)
    return 0 if report["status"] == "complete" and report["comparison_integrity_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
