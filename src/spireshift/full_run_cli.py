"""CLI surface for the separate, whole-run experimental learning path."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from spireshift.adapters.evangambit import EvanGambitBackendError
from spireshift.full_run_a8_admission import admit_a8_candidate
from spireshift.full_run_backend_repair import (
    build_backend_repair,
    load_repair_recipe,
    prepare_backend_repair,
    show_backend_repair,
)
from spireshift.full_run_event_audit import (
    load_event_integration_recipe,
    run_event_integration,
    show_event_integration,
)
from spireshift.full_run_evolution import (
    inspect_evolution,
    load_evolution_config,
    run_full_run_evolution,
)
from spireshift.full_run_policy import load_full_run_model
from spireshift.full_run_ppo import inspect_ppo, load_ppo_config, run_ppo, summarize_ppo
from spireshift.full_run_public_audit import (
    load_integration_recipe,
    run_integration_audit,
    show_integration_audit,
)
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
        "full-run", help="Unified full-run learning and bounded owner-run experiments"
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
    admission = sub.add_parser("admit-a8", help="Verify executed evidence for scoped A8 learning")
    admission.add_argument("config", type=Path)
    admission.add_argument("--game-assembly", type=Path, required=True)
    ppo_preview = sub.add_parser("inspect-ppo-config", help="Read the A8 training recipe; no games")
    ppo_preview.add_argument("config", type=Path)
    for name in ("train-ppo", "show-ppo"):
        command = sub.add_parser(
            name,
            help="A8 sampled outcome learning" if name == "train-ppo" else "Read saved A8 results",
        )
        command.add_argument("config", type=Path)
        command.add_argument("output_dir", type=Path)
        if name == "train-ppo":
            command.add_argument("--resume", action="store_true")
    for name, help_text in (
        ("prepare-backend-repair", "Prepare an isolated source repair without building or playing"),
        ("build-backend-repair", "Capped native repair build; requires the resource wrapper"),
        ("show-backend-repair", "Read a saved native repair result; never admit or train"),
        ("audit-public-integration", "Owner-run replay of failed training prefixes; no training"),
        ("show-public-integration", "Check a saved public integration audit; no game replays"),
        (
            "audit-event-integration",
            "Bounded replay of all failed prefixes with event endpoint checks",
        ),
        ("show-event-integration", "Verify the saved event audit without replaying games"),
    ):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("config", type=Path)


def run_full_run_command(args: argparse.Namespace) -> int:
    try:
        if args.full_run_command == "admit-a8":
            result = admit_a8_candidate(args.config, args.game_assembly)
        elif args.full_run_command == "inspect-ppo-config":
            ppo = load_ppo_config(args.config)
            learning, n = ppo.document["learning"], ppo.document["network"]
            confirmations = sum(
                (i + 1) % learning["confirmation_every"] == 0 or i + 1 == learning["maximum_rounds"]
                for i in range(learning["maximum_rounds"])
            )
            result = {
                "config_id": ppo.config_id,
                "scope": ppo.score.scope.as_dict(),
                "maximum_rounds": learning["maximum_rounds"],
                "sampled_games_per_round": [len(p) for p in learning["rollout_seed_panels"]],
                "maximum_planned_game_attempts": sum(
                    len(p) for p in learning["rollout_seed_panels"]
                )
                + (1 + confirmations) * len(learning["confirmation_train_seeds"])
                + 2 * len(learning["development_seeds"]),
                "actor_parameters": n["dimension"] * n["hidden_units"]
                + 2 * n["hidden_units"]
                + n["dimension"],
                "critic_parameters": n["dimension"] + 1,
                "all_decision_types_trainable": True,
                "permanent_baseline_anchor": False,
                "workers": ppo.document["workers"],
                "per_launch_limits": ppo.document["resource_limits"],
                "games_played": 0,
                "optimizer_steps": 0,
                "final_test_opened": False,
                "automatic_followup": False,
            }
        elif args.full_run_command in {"train-ppo", "show-ppo"}:
            if args.full_run_command == "train-ppo":
                if not os.environ.get(EXPERIMENT_METRICS_ENV):
                    raise ValueError(
                        "A8 training requires job-wide resource caps; "
                        "use the matching owner launcher under scripts/"
                    )
                report = run_ppo(args.config, args.output_dir, resume=args.resume)
            else:
                report = inspect_ppo(args.config, args.output_dir)
            result = summarize_ppo(report, args.output_dir)
        elif args.full_run_command in {
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
        elif args.full_run_command in {"audit-event-integration", "show-event-integration"}:
            event_recipe = load_event_integration_recipe(args.config)
            event_audit = (
                run_event_integration(event_recipe)
                if args.full_run_command == "audit-event-integration"
                else show_event_integration(event_recipe)
            )
            result = {k: v for k, v in event_audit.items() if k != "cases"}
        elif args.full_run_command in {"audit-public-integration", "show-public-integration"}:
            integration = load_integration_recipe(args.config)
            audit = (
                run_integration_audit(integration)
                if args.full_run_command == "audit-public-integration"
                else show_integration_audit(integration)
            )
            result = {k: v for k, v in audit.items() if k != "cases"}
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
        if args.full_run_command == "train-ppo" and result.get("development_status") != "completed":
            return 1  # Saved failures remain available; the resource report must flag this job.
        return 0
    except (OSError, ValueError, KeyError, TypeError, EvanGambitBackendError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, indent=2))
        return 1
