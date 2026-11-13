"""Finite evolution of the public A8 actor, seeded by a completed PPO experiment.

This is an additional hybrid stage, not a from-scratch or equal-total-cost GA claim.
The existing admitted collector and disposable episode workers stay unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import statistics
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_a8_admission import identified_document
from spireshift.full_run_evolution import mutate_genome
from spireshift.full_run_ppo import (
    REPORT_SCHEMA as PPO_REPORT_SCHEMA,
)
from spireshift.full_run_ppo import (
    ExperienceStore,
    PPOConfig,
    bounded_integer,
    bounded_number,
    frozen_json,
    load_actor_critic,
    load_ppo_config,
    paired_summary,
    ppo_protocol,
)
from spireshift.full_run_ppo_math import ActorCritic
from spireshift.full_run_ppo_progress import describe_game, progress_rank
from spireshift.full_run_public_policy import PublicFullRunModel
from spireshift.models import _exact_keys, _mapping
from spireshift.resource_tracking import (
    EXPERIMENT_METRICS_ENV,
    ExperimentMetrics,
    write_experiment_metrics,
)
from spireshift.splits import SplitName
from spireshift.training_objective import RunStatus, TrainingOutcome

CONFIG_SCHEMA = "public-a8-actor-evolution-config-v1"
REPORT_SCHEMA = "public-a8-actor-evolution-report-v1"


def read_case_metadata(root: Path, ref: dict[str, Any]) -> dict[str, Any]:
    path = root / ref["path"]
    if not path.resolve().is_relative_to(root.resolve()) or path.name not in {
        "case.json",
        "failure.json",
    }:
        raise ValueError("Episode reference is outside its experiment")
    case = json.loads(path.read_text())
    body = {k: v for k, v in case.items() if k not in {"case_id", "trace_file_sha256"}}
    if case["case_id"] != ref["case_id"] or case["case_id"] != manifest_identifier(body):
        raise ValueError("Saved episode metadata identity differs")
    return dict(case)


def source_assessment(config: PPOConfig, root: Path) -> dict[str, Any]:
    """Reconcile saved outcome metadata; do not open traces, predict or replay games."""
    report = identified_document(root / "ppo-report.json")
    selection = identified_document(root / "train-selection.json", "selection_id")
    saved_protocol = identified_document(root / "protocol.json", "protocol_id")
    if (
        report["schema_version"] != PPO_REPORT_SCHEMA
        or report["protocol"] != ppo_protocol(config)
        or {k: v for k, v in saved_protocol.items() if k != "protocol_id"} != report["protocol"]
        or report["development_status"] != "completed"
        or report["selection_id"] != selection["selection_id"]
        or report["champion_model_id"] != selection["champion_model_id"]
        or selection["selection_uses_development"] is not False
        or report["final_test_opened"] is not False
    ):
        raise ValueError("Hybrid stage requires a completed, frozen current A8 PPO result")
    cases = {ref["case_id"]: read_case_metadata(root, ref) for ref in report["cases"]}
    if len(cases) != report["experience_cases"]:
        raise ValueError("Source PPO episode denominator differs")
    panels = [report["development"][report[k]] for k in ("initial_model_id", "champion_model_id")]
    expected_seeds = config.document["learning"]["development_seeds"]
    if any(
        p["seeds"] != expected_seeds
        or len(p["case_ids"]) != len(expected_seeds)
        or p["model_id"] != report[k]
        for p, k in zip(panels, ("initial_model_id", "champion_model_id"), strict=True)
    ):
        raise ValueError("Source development panels differ from their frozen seed/model bindings")
    pairs = []
    for seed, a, b in zip(
        expected_seeds, panels[0]["case_ids"], panels[1]["case_ids"], strict=True
    ):
        first, second = cases[a], cases[b]
        if (
            any(c["binding"]["seed"] != seed for c in (first, second))
            or any(c["binding"]["partition"] != "development" for c in (first, second))
            or any(c["binding"]["behavior"] != "greedy_argmax" for c in (first, second))
            or any(
                c["binding"]["model_id"] != p["model_id"]
                for c, p in zip((first, second), panels, strict=True)
            )
            or any(
                c["outcome"]["status"] not in {"terminal_loss", "terminal_victory"}
                for c in (first, second)
            )
        ):
            raise ValueError("Source development comparison is incomplete or unpaired")
        pairs.append((first["outcome"], second["outcome"]))
    differences = [b["maximum_floor"] - a["maximum_floor"] for a, b in pairs]
    mean = statistics.mean(differences)
    se = statistics.stdev(differences) / math.sqrt(len(differences))
    return {
        "source_report_id": report["report_id"],
        "initial_model_id": report["initial_model_id"],
        "ppo_model_id": report["champion_model_id"],
        "source_used_seeds": sorted({c["binding"]["seed"] for c in cases.values()}),
        "paired_development": {
            **report["paired_development"],
            "higher_floor": sum(d > 0 for d in differences),
            "lower_floor": sum(d < 0 for d in differences),
            "equal_floor": sum(d == 0 for d in differences),
            "paired_floor_standard_error": se,
            "approximate_95_percent_floor_interval": [mean - 1.96 * se, mean + 1.96 * se],
            "interval_method": "paired_normal_approximation_auxiliary_diagnostic_only",
        },
        "initial": panels[0]["summary"],
        "ppo": panels[1]["summary"],
        "source_cases": len(cases),
        "source_public_decisions": report["public_decisions"],
        "source_status_counts": {
            status: sum(c["outcome"]["status"] == status for c in cases.values())
            for status in sorted({c["outcome"]["status"] for c in cases.values()})
        },
        "metadata_checked": True,
        "compressed_traces_reaudited": False,
        "games_replayed": 0,
        "optimizer_steps": 0,
        "checkpoint_promoted": False,
        "foundation_readiness_established": False,
    }


@dataclass(frozen=True, slots=True)
class A8EvolutionConfig:
    document: dict[str, Any]
    collector: PPOConfig
    collector_path: Path
    source: dict[str, Any]
    initial: ActorCritic
    ppo: ActorCritic

    @classmethod
    def load(cls, path: Path) -> A8EvolutionConfig:
        d = _mapping(json.loads(path.read_text()), "A8 actor evolution config")
        _exact_keys(
            d,
            {"schema_version", "config_id", "inputs", "evolution", "resource_limits"},
            "A8 actor evolution config",
        )
        if d["schema_version"] != CONFIG_SCHEMA or d["config_id"] != manifest_identifier(
            {k: v for k, v in d.items() if k != "config_id"}
        ):
            raise ValueError("A8 evolution configuration identity differs")
        inputs = _mapping(d["inputs"], "evolution inputs")
        _exact_keys(
            inputs,
            {
                "collector_config",
                "ppo_output",
                "ppo_report_id",
                "additional_inspected_development_seeds",
                "source_resource_reports",
            },
            "evolution inputs",
        )
        ref = _mapping(inputs["collector_config"], "collector config")
        _exact_keys(ref, {"path", "id"}, "collector config")
        collector_path = Path(ref["path"])
        collector = load_ppo_config(collector_path)
        if collector.config_id != ref["id"]:
            raise ValueError("Admitted episode collector configuration differs")
        source_root = Path(inputs["ppo_output"])
        source = source_assessment(collector, source_root)
        if source["source_report_id"] != inputs["ppo_report_id"]:
            raise ValueError("Source PPO result differs")
        resources = inputs["source_resource_reports"]
        if not isinstance(resources, list) or not resources:
            raise ValueError("All prior PPO launch costs must be supplied")
        resource_ids: set[str] = set()
        costs = {"wall_seconds": 0.0, "cpu_seconds": 0.0, "trajectories": 0.0}
        for item in resources:
            resource = identified_document(Path(item["path"]))
            roots = resource["artifacts"]["roots"]
            if (
                resource["report_id"] != item["id"]
                or item["id"] in resource_ids
                or resource["experiment_kind"] != "training"
                or str(source_root.resolve()) not in roots
            ):
                raise ValueError("Prior PPO cost identity or experiment scope differs")
            resource_ids.add(item["id"])
            for key in costs:
                costs[key] += bounded_number(resource["usage"][key], key, 0, 1e13)
        if costs["trajectories"] != source["source_cases"]:
            raise ValueError("Prior PPO launch reports do not reconcile all attempts")
        source["prior_PPO_resources"] = {**costs, "report_ids": sorted(resource_ids)}
        models = [
            load_actor_critic(source_root / "models" / (source[k][7:] + ".json"))
            for k in ("initial_model_id", "ppo_model_id")
        ]
        if [m.model_id for m in models] != [source["initial_model_id"], source["ppo_model_id"]]:
            raise ValueError("Saved PPO source models differ")
        e = _mapping(d["evolution"], "evolution")
        _exact_keys(
            e,
            {
                "population_size",
                "elite_count",
                "maximum_generations",
                "minimum_generations",
                "confirmation_every",
                "plateau_confirmations",
                "generation_train_seeds",
                "confirmation_train_seeds",
                "development_seeds",
                "mutation_scales",
                "mutation_probability",
                "rng_seed",
            },
            "evolution",
        )
        population = bounded_integer(e["population_size"], "population", 4, 64)
        bounded_integer(e["elite_count"], "elites", 2, population - 1)
        generations = bounded_integer(e["maximum_generations"], "generations", 1, 100)
        bounded_integer(e["minimum_generations"], "minimum generations", 1, generations)
        bounded_integer(e["confirmation_every"], "confirmation interval", 1, generations)
        bounded_integer(e["plateau_confirmations"], "plateau confirmations", 1, 100)
        bounded_integer(e["rng_seed"], "rng seed", 0, 2**31 - 1)
        bounded_number(e["mutation_probability"], "mutation probability", 0.01, 1)
        if not isinstance(e["mutation_scales"], list) or not e["mutation_scales"]:
            raise ValueError("At least one mutation scale is required")
        for scale in e["mutation_scales"]:
            bounded_number(scale, "mutation scale", 0.0001, 1)
        panels = e["generation_train_seeds"]
        if not isinstance(panels, list) or len(panels) != generations:
            raise ValueError("Exactly one common seed panel is required per generation")
        seen: set[int] = set(source["source_used_seeds"])
        inspected = inputs["additional_inspected_development_seeds"]
        if not isinstance(inspected, list):
            raise ValueError("Inspected development seed inventory is required")
        for seed in inspected:
            if collector.splits.split_for_seed(seed) != SplitName.VALIDATION:
                raise ValueError("Inspected development inventory crosses partitions")
            seen.add(seed)
        for seeds, split in [(p, SplitName.TRAIN) for p in panels] + [
            (e["confirmation_train_seeds"], SplitName.TRAIN),
            (e["development_seeds"], SplitName.VALIDATION),
        ]:
            if not isinstance(seeds, list) or not 2 <= len(seeds) <= 512:
                raise ValueError("Evolution panels require 2-512 independent complete-run seeds")
            for seed in seeds:
                bounded_integer(seed, "seed", 0, 2**31 - 1)
                if seed in seen or collector.splits.split_for_seed(seed) != split:
                    raise ValueError("Evolution seeds overlap source/inspected data or partitions")
                seen.add(seed)
        limits = _mapping(d["resource_limits"], "resource limits")
        _exact_keys(
            limits,
            {"wall_seconds", "cpu_seconds", "storage_bytes", "memory_bytes"},
            "resource limits",
        )
        for key in limits:
            bounded_integer(limits[key], key, 1, 10**13)
        return cls(d, collector, collector_path, source, models[0], models[1])


def protocol(config: A8EvolutionConfig) -> dict[str, Any]:
    return {
        "config_id": config.document["config_id"],
        "method": "ppo_seeded_whole_actor_weight_evolution",
        "runner_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "mutation_source_sha256": hashlib.sha256(
            Path(__file__).with_name("full_run_evolution.py").read_bytes()
        ).hexdigest(),
        "collector_protocol": ppo_protocol(config.collector),
        "source_report_id": config.source["source_report_id"],
        "source_initial_model_id": config.initial.model_id,
        "source_ppo_model_id": config.ppo.model_id,
        "prior_PPO_resources": config.source["prior_PPO_resources"],
        "critic_mutated": False,
        "actor_parameters_mutable": config.ppo.actor.parameter_count,
        "baseline_proximity_penalty": 0,
        "automatic_followup": False,
        "checkpoint_promoted": False,
        "final_test_opened": False,
        "comparison_scope": "additional_hybrid_stage_not_equal_total_cost_or_from_scratch_GA",
    }


def population(
    config: A8EvolutionConfig, champion: ActorCritic, parents: list[ActorCritic], generation: int
) -> tuple[list[ActorCritic], list[dict[str, Any]]]:
    e = config.document["evolution"]
    rng = random.Random(e["rng_seed"] + generation * 100003)
    models, lineage, seen = [], [], set()
    for model in [champion, config.ppo, config.initial, *parents]:
        if model.model_id not in seen:
            models.append(model)
            lineage.append(
                {"model_id": model.model_id, "parent_model_id": None, "operator": "retained"}
            )
            seen.add(model.model_id)
    models, lineage = models[: e["elite_count"] + 2], lineage[: e["elite_count"] + 2]
    models, lineage = models[: e["population_size"] - 1], lineage[: e["population_size"] - 1]
    seen = {m.model_id for m in models}
    for _ in range(10000):
        if len(models) == e["population_size"]:
            return models, lineage
        parent = rng.choice(parents or [champion])
        scale = rng.choice(e["mutation_scales"])
        actor = mutate_genome(parent.actor, rng, scale, e["mutation_probability"])
        model = ActorCritic(PublicFullRunModel.from_mapping(actor.as_dict()), parent.value_weights)
        if model.model_id in seen:
            continue
        models.append(model)
        seen.add(model.model_id)
        lineage.append(
            {
                "model_id": model.model_id,
                "parent_model_id": parent.model_id,
                "operator": "independent_gaussian_whole_actor",
                "scale": scale,
                "probability": e["mutation_probability"],
            }
        )
    raise ValueError("Mutation could not construct a distinct finite population")


def game_progress(panel: dict[str, Any], store: ExperienceStore) -> str:
    by_id = {c["case_id"]: c for c in store.cases.values()}
    finished = [
        TrainingOutcome.from_mapping(by_id[k]["outcome"])
        for k in panel["case_ids"]
        if by_id[k]["outcome"]["status"] in {RunStatus.LOSS, RunStatus.VICTORY}
    ]
    best = max(finished, key=progress_rank) if finished else None
    s = panel["summary"]
    return (
        f"wins {s['victories']}/{len(panel['seeds'])}; average floor "
        f"{s['mean_maximum_floor']:.2f}; best game "
        f"{describe_game(best) if best else 'no finished games'}; "
        f"{s['failed_runs']} failures/caps"
    )


def run_locked(config: A8EvolutionConfig, output: Path) -> dict[str, Any]:
    p = protocol(config)
    frozen_json(output / "protocol.json", p, "protocol_id")
    e = config.document["evolution"]
    champion, parents = config.ppo, [config.ppo, config.initial]
    generations, plateau, stop = [], 0, "generation_limit"
    write_experiment_metrics(ExperimentMetrics(trajectories=0, simulations=0, transitions=0))
    with ThreadPoolExecutor(max_workers=config.collector.document["workers"]) as executor:
        store = ExperienceStore(config.collector, config.collector_path, output, executor)
        confirmation, _ = store.panel(
            champion,
            e["confirmation_train_seeds"],
            "train",
            round_index=None,
            label="PPO starting-player confirmation",
        )
        for generation, seeds in enumerate(e["generation_train_seeds"]):
            path = output / f"generation-{generation:03d}.json"
            if path.exists():
                saved = identified_document(path, "generation_id")
                if saved["protocol"] != p:
                    raise ValueError("Saved evolution generation belongs to another protocol")
            models, lineage = population(config, champion, parents, generation)
            panels = []
            for index, model in enumerate(models):
                panel, _ = store.panel(
                    model,
                    seeds,
                    "train",
                    round_index=None,
                    label=f"Generation {generation + 1}/{e['maximum_generations']} "
                    f"player {index + 1}/{len(models)}",
                )
                panels.append(panel)
            ranked = sorted(
                range(len(models)),
                key=lambda i: (tuple(panels[i]["summary"]["fitness_rank"]), models[i].model_id),
                reverse=True,
            )
            candidate = models[ranked[0]]
            checked = None
            if (generation + 1) % e["confirmation_every"] == 0 or generation + 1 == e[
                "maximum_generations"
            ]:
                checked, _ = store.panel(
                    candidate,
                    e["confirmation_train_seeds"],
                    "train",
                    round_index=None,
                    label=f"Generation {generation + 1} confirmation",
                )
                if tuple(checked["summary"]["fitness_rank"]) > tuple(
                    confirmation["summary"]["fitness_rank"]
                ):
                    champion, confirmation, plateau = candidate, checked, 0
                else:
                    plateau += 1
            parents = [models[i] for i in ranked[: e["elite_count"]]]
            saved = frozen_json(
                path,
                {
                    "protocol": p,
                    "generation_index": generation,
                    "lineage": lineage,
                    "panels": panels,
                    "candidate_confirmation": checked,
                    "next_parent_ids": [m.model_id for m in parents],
                    "champion_model_id": champion.model_id,
                    "champion_confirmation": confirmation,
                    "plateau_confirmations": plateau,
                },
                "generation_id",
            )
            generations.append(saved)
            print(
                f"Generation {generation + 1} best candidate: "
                f"{game_progress(panels[ranked[0]], store)}.",
                flush=True,
            )
            print(f"Confirmed player: {game_progress(confirmation, store)}.", flush=True)
            if generation + 1 >= e["minimum_generations"] and plateau >= e["plateau_confirmations"]:
                stop = "confirmed_training_plateau"
                break
        selection = frozen_json(
            output / "train-selection.json",
            {
                "protocol": p,
                "champion_model_id": champion.model_id,
                "generation_ids": [g["generation_id"] for g in generations],
                "stop_reason": stop,
                "selection_uses_development": False,
            },
            "selection_id",
        )
        development = {}
        roles = {"initializer": config.initial, "ppo": config.ppo, "evolved": champion}
        for role, model in roles.items():
            if model.model_id not in development:
                panel, _ = store.panel(
                    model,
                    e["development_seeds"],
                    "development",
                    round_index=None,
                    label=f"Fresh frozen development: {role}",
                )
                development[model.model_id] = panel
        cases = sorted(store.cases.values(), key=lambda c: c["case_id"])
        complete = all(d["summary"]["failed_runs"] == 0 for d in development.values())
        return frozen_json(
            output / "evolution-report.json",
            {
                "schema_version": REPORT_SCHEMA,
                "protocol": p,
                "selection_id": selection["selection_id"],
                "generations_completed": len(generations),
                "stop_reason": stop,
                "role_model_ids": {role: m.model_id for role, m in roles.items()},
                "generation_ids": [g["generation_id"] for g in generations],
                "development": development,
                "paired_against_ppo": paired_summary(
                    development[config.ppo.model_id], development[champion.model_id], store
                ),
                "paired_against_initializer": paired_summary(
                    development[config.initial.model_id], development[champion.model_id], store
                ),
                "development_status": "completed"
                if complete
                else "incomplete_with_failed_attempts",
                "experience_cases": len(cases),
                "public_decisions": sum(c["outcome"]["decisions"] for c in cases),
                "all_episode_costs_known": all(c.get("cpu_seconds_known", True) for c in cases),
                "interrupted_or_worker_failed_attempts": sum(
                    c.get("cpu_seconds_known") is False for c in cases
                ),
                "cases": [
                    {
                        "case_id": c["case_id"],
                        "path": str(
                            store.paths[manifest_identifier(c["binding"])[7:]].relative_to(output)
                        ),
                    }
                    for c in cases
                ],
                "champion_checkpoint": str(store.save_model(champion).relative_to(output)),
                "optimizer_steps": 0,
                "foundation_readiness_established": False,
                "checkpoint_promoted": False,
                "final_test_opened": False,
                "automatic_followup": False,
                "training_cost_scope": "additional_evolution_stage_plus_all_prior_PPO_cost",
                "prior_PPO_resources": config.source["prior_PPO_resources"],
            },
            "report_id",
        )


def show(config: A8EvolutionConfig, output: Path) -> dict[str, Any]:
    report = identified_document(output / "evolution-report.json")
    selection = identified_document(output / "train-selection.json", "selection_id")
    if (
        report["schema_version"] != REPORT_SCHEMA
        or report["protocol"] != protocol(config)
        or selection["selection_id"] != report["selection_id"]
        or selection["selection_uses_development"] is not False
        or selection["champion_model_id"] != report["role_model_ids"]["evolved"]
    ):
        raise ValueError("Saved hybrid evolution experiment differs")
    for index, identity in enumerate(report["generation_ids"]):
        if (
            identified_document(output / f"generation-{index:03d}.json", "generation_id")[
                "generation_id"
            ]
            != identity
        ):
            raise ValueError("Saved generation differs")
    for identity in set(report["role_model_ids"].values()):
        if load_actor_critic(output / "models" / (identity[7:] + ".json")).model_id != identity:
            raise ValueError("Saved evolved model differs")
    for ref in report["cases"]:
        read_case_metadata(output, ref)
    return report


def summary(report: dict[str, Any], output: Path) -> dict[str, Any]:
    return {k: v for k, v in report.items() if k not in {"protocol", "cases", "development"}} | {
        "players": {
            role: report["development"][identity]["summary"]
            for role, identity in report["role_model_ids"].items()
        },
        "champion_checkpoint": str((output / report["champion_checkpoint"]).resolve()),
        "cached_read_scope": "identified_metadata_only_not_full_compressed_trace_reaudit",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    try:
        config = A8EvolutionConfig.load(args.config)
        if args.show or (args.output_dir / "evolution-report.json").exists():
            report = show(config, args.output_dir)
        else:
            if not os.environ.get(EXPERIMENT_METRICS_ENV):
                raise ValueError("Evolution requires the resource-capped owner launcher")
            if args.output_dir.exists() and not args.resume:
                raise ValueError("Existing evolution work requires explicit --resume")
            args.output_dir.mkdir(parents=True, exist_ok=True)
            import fcntl

            with (args.output_dir / ".owner-run.lock").open("a") as lock:
                try:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise ValueError("This evolution experiment is already running") from exc
                report = run_locked(config, args.output_dir)
        print(json.dumps(summary(report, args.output_dir), indent=2))
        return int(report["development_status"] != "completed")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
