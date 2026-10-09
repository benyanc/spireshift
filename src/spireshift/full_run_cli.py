"""CLI surface for the separate, whole-run experimental learning path."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from spireshift.full_run_backend_repair import (
    build_backend_repair,
    load_repair_recipe,
    prepare_backend_repair,
    show_backend_repair,
)
from spireshift.full_run_evolution import (
    inspect_evolution,
    load_evolution_config,
    run_full_run_evolution,
)
from spireshift.full_run_policy import load_full_run_model
from spireshift.resource_tracking import EXPERIMENT_METRICS_ENV


def summarize_evolution(result: dict[str, Any], root: Path) -> dict[str, Any]:
    initial = result["initial_model_id"]
    champion = result["champion_model_id"]
    return {
        "report_id": result["report_id"],
        "report_path": str((root / "evolution-report.json").resolve()),
        "generations_completed": result["generations_completed"],
        "stop_reason": result["stop_reason"],
        "initial_model_id": initial,
        "champion_model_id": champion,
        "initial": result["development"][initial]["summary"],
        "champion": result["development"][champion]["summary"],
        "paired": {k: v for k, v in result["paired_development"].items() if k != "pairs"},
        "experience_cases": result["experience_cases"],
        "public_decisions": result["public_decisions"],
        "recorded_episode_cpu_seconds": result["recorded_episode_cpu_seconds"],
        "all_episode_costs_known": result["all_episode_costs_known"],
        "interrupted_or_worker_failed_attempts": result["interrupted_or_worker_failed_attempts"],
        "champion_checkpoint": str((root / result["champion_checkpoint"]).resolve()),
        "checkpoint_promoted": False,
        "foundation_readiness_established": False,
        "automatic_followup": False,
        "final_test_opened": False,
    }


def add_full_run_parser(commands: Any) -> None:
    parser = commands.add_parser(
        "full-run", help="Unified full-run policy and bounded owner-run evolution"
    )
    sub = parser.add_subparsers(dest="full_run_command", required=True)
    preview = sub.add_parser(
        "inspect-config", help="Inspect the frozen pilot without games or training"
    )
    preview.add_argument("config", type=Path)
    evolve = sub.add_parser("evolve", help="Owner-run evolution; requires the resource wrapper")
    evolve.add_argument("config", type=Path)
    evolve.add_argument("output_dir", type=Path)
    evolve.add_argument("--resume", action="store_true")
    show = sub.add_parser("show", help="Read a completed pilot without games or training")
    show.add_argument("config", type=Path)
    show.add_argument("output_dir", type=Path)
    model = sub.add_parser("inspect-model", help="Inspect a unified model without playing")
    model.add_argument("checkpoint", type=Path)
    for name, help_text in (
        ("prepare-backend-repair", "Prepare an isolated source repair without building or playing"),
        ("build-backend-repair", "Owner-run native repair build; requires the resource wrapper"),
        ("show-backend-repair", "Read a saved native repair result; never admit or train"),
    ):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("config", type=Path)


def run_full_run_command(args: argparse.Namespace) -> int:
    try:
        if args.full_run_command in {
            "prepare-backend-repair",
            "build-backend-repair",
            "show-backend-repair",
        }:
            recipe = load_repair_recipe(args.config)
            operation = {
                "prepare-backend-repair": prepare_backend_repair,
                "build-backend-repair": build_backend_repair,
                "show-backend-repair": show_backend_repair,
            }[args.full_run_command]
            result = operation(recipe)
        elif args.full_run_command == "inspect-model":
            model = load_full_run_model(args.checkpoint)
            result = {
                "model_id": model.model_id,
                "inputs": model.dimension,
                "hidden_units": model.hidden_units,
                "trainable_parameters": model.parameter_count,
                "outputs_per_legal_candidate": 1,
                "terminal_value_available": False,
                "all_decision_families_trainable": True,
                "games_replayed": 0,
            }
        elif args.full_run_command == "inspect-config":
            config = load_evolution_config(args.config)
            e = config.document["evolution"]
            maximum_games = e["population_size"] * sum(len(p) for p in e["generation_train_seeds"])
            maximum_games += 3 * sum(len(p) for p in e["confirmation_train_seeds"])
            maximum_games += 2 * len(e["development_seeds"])
            n = config.document["network"]
            result = {
                "config_id": config.config_id,
                "training_spec_id": config.score.spec_id,
                "split_manifest_id": config.splits.manifest_id,
                "network": {
                    "inputs": n["dimension"],
                    "hidden_units": n["hidden_units"],
                    "trainable_parameters": n["dimension"] * n["hidden_units"]
                    + 2 * n["hidden_units"]
                    + n["dimension"],
                },
                "population_size": e["population_size"],
                "maximum_generations": e["maximum_generations"],
                "maximum_planned_game_attempts": maximum_games,
                "workers": config.document["workers"],
                "resource_limits": config.document["resource_limits"],
                "all_decision_families_trainable": True,
                "final_test_opened": False,
                "automatic_followup": False,
                "games_replayed": 0,
            }
        elif args.full_run_command == "show":
            result = summarize_evolution(
                inspect_evolution(args.config, args.output_dir), args.output_dir
            )
        else:
            if not os.environ.get(EXPERIMENT_METRICS_ENV):
                raise ValueError(
                    "Use scripts/evolve-full-run-policy-v1.sh for job-wide resource caps"
                )
            result = summarize_evolution(
                run_full_run_evolution(args.config, args.output_dir, resume=args.resume),
                args.output_dir,
            )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, indent=2))
        return 1
