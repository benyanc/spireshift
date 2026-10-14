"""Separate identity, acquisition and bounded native checks; never starts training."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from spireshift.engine_bundle_bridge import (
    compare_bundle_bridge,
    compare_bundle_bridges,
    preflight_bundle_bridges,
    verify_bundle_bridges,
)
from spireshift.engine_candidate import build_cli_candidate
from spireshift.engine_checkpoint import probe_shipped_checkpoint
from spireshift.engine_cli_probe import probe_cli_rest
from spireshift.engine_combat_bridge import (
    compare_combat_bridge,
    compare_combat_bridges,
    preflight_combat_bridges,
    verify_combat_bridges,
)
from spireshift.engine_connector import (
    load_connector_qualification_config,
    prepare_connector_toolchain,
    probe_connector_menu,
)
from spireshift.engine_connector_build import build_connector_candidate
from spireshift.engine_download import (
    download_exact_game,
    download_plan,
    load_engine_download_config,
)
from spireshift.engine_journey import probe_shipped_journey
from spireshift.engine_journey_bridges import run_journey_bridges
from spireshift.engine_journey_verification import verify_journey_bridges
from spireshift.engine_localization import extract_native_localization
from spireshift.engine_mode_audit import audit_mode_references
from spireshift.engine_native import (
    _verified_archive,
    bootstrap_native_profile,
    inspect_model_registry,
    load_native_qualification_config,
)
from spireshift.engine_profile_bridge import (
    compare_profile_bridge,
    compare_profile_bridges,
    preflight_profile_bridges,
    verify_profile_bridges,
)
from spireshift.engine_progression import run_native_progression, verify_native_progression
from spireshift.engine_progression_bridge import (
    audit_saved_progression,
    compare_progression_bridges,
    preflight_progression_bridges,
    verify_progression_bridges,
)
from spireshift.engine_qualification import (
    default_archive_path,
    engine_preflight,
    freeze_game_archive,
    load_engine_qualification_config,
    steam_download_command,
    verify_game_archive,
)
from spireshift.engine_rest_bridge import compare_rest_bridge, compare_rest_bridges
from spireshift.engine_rest_verification import verify_rest_bridges
from spireshift.engine_reward_bridge import (
    compare_reward_bridge,
    compare_reward_bridges,
    preflight_reward_bridges,
    verify_reward_bridges,
)
from spireshift.engine_reward_generation import check_native_reward_generation
from spireshift.engine_run import preflight_native_run, probe_native_run, verify_native_run
from spireshift.engine_run_discovery import discover_runs, verify_discovery_runs
from spireshift.engine_shop_bridge import compare_shop_bridge, compare_shop_bridges
from spireshift.engine_shop_verification import verify_shop_bridge, verify_shop_bridges
from spireshift.engine_source import inspect_game_source
from spireshift.engine_starting_bridges import run_starting_bridges, verify_starting_bridges
from spireshift.engine_startup import compare_new_run, verify_new_run
from spireshift.engine_working_app import load_working_app_policy, working_app_inventory
from spireshift.full_run_experience import atomic_json


def add_engine_parser(commands: Any) -> None:
    engine = commands.add_parser(
        "engine", help="Identify, preserve and separately qualify actual-game inputs"
    )
    sub = engine.add_subparsers(dest="engine_command", required=True)
    for name in (
        "preflight",
        "freeze",
        "verify-archive",
        "inventory-working-apps",
        "download-command",
        "download-plan",
        "download-game",
        "bootstrap-profile",
        "model-inventory",
        "prepare-connector",
        "probe-connector-menu",
        "probe-shipped-checkpoint",
        "probe-shipped-journey",
        "compare-starting-bridges",
        "verify-starting-bridges",
        "compare-journey-bridges",
        "verify-journey-bridges",
        "compare-rest-bridge",
        "compare-shop-bridge",
        "compare-shop-bridges",
        "compare-bundle-bridge",
        "compare-bundle-bridges",
        "preflight-bundle-bridges",
        "verify-bundle-bridges",
        "compare-reward-bridge",
        "compare-reward-bridges",
        "preflight-reward-bridges",
        "verify-reward-bridges",
        "compare-profile-bridge",
        "compare-combat-bridge",
        "compare-combat-bridges",
        "preflight-combat-bridges",
        "verify-combat-bridges",
        "compare-profile-bridges",
        "preflight-profile-bridges",
        "verify-profile-bridges",
        "compare-rest-bridges",
        "verify-rest-bridges",
        "verify-shop-bridge",
        "verify-shop-bridges",
        "build-cli-candidate",
        "build-connector-candidate",
        "probe-cli-rest",
        "probe-cli-shop",
        "probe-cli-combat",
        "probe-cli-combat-bridge",
        "probe-cli-bundle",
        "probe-cli-bundle-bridge",
        "probe-cli-reward-bridge",
        "probe-cli-checkpoint",
        "probe-cli-journey",
        "preflight-native-run",
        "probe-native-run",
        "verify-native-run",
        "compare-new-run",
        "preflight-new-run",
        "verify-new-run",
        "discover-natural-runs",
        "preflight-natural-discovery",
        "verify-natural-discovery",
        "check-native-progression",
        "verify-native-progression",
        "compare-progression-bridges",
        "preflight-progression-bridges",
        "verify-progression-bridges",
        "audit-saved-progression",
        "probe-cli-rest-bridge",
        "probe-cli-shop-bridge",
        "inspect-game-source",
        "audit-mode-references",
        "check-native-reward-generation",
        "extract-game-text",
    ):
        command = sub.add_parser(name)
        command.add_argument("config", type=Path)
        if name in {"check-native-progression", "verify-native-progression"}:
            command.add_argument("progression_config", type=Path)
        if name == "audit-saved-progression":
            command.add_argument("progression_config", type=Path)
            command.add_argument("--node", required=True, type=Path)
        if name in {
            "compare-progression-bridges",
            "preflight-progression-bridges",
            "verify-progression-bridges",
        }:
            command.add_argument("progression_config", type=Path)
            command.add_argument("--node", required=True, type=Path)
        if name in ("download-plan", "download-game"):
            command.add_argument("downloader_config", type=Path)
        if name in ("bootstrap-profile", "model-inventory"):
            command.add_argument("native_config", type=Path)
        if name in {"bootstrap-profile", "probe-connector-menu"}:
            command.add_argument("--working-app-config", type=Path)
        if name in ("prepare-connector", "probe-connector-menu"):
            command.add_argument("connector_config", type=Path)
        if name in {
            "compare-starting-bridges",
            "verify-starting-bridges",
            "compare-journey-bridges",
            "verify-journey-bridges",
            "compare-rest-bridge",
            "compare-shop-bridge",
            "compare-shop-bridges",
            "compare-bundle-bridge",
            "compare-bundle-bridges",
            "preflight-bundle-bridges",
            "verify-bundle-bridges",
            "compare-reward-bridge",
            "compare-reward-bridges",
            "preflight-reward-bridges",
            "verify-reward-bridges",
            "compare-profile-bridge",
            "compare-combat-bridge",
            "compare-combat-bridges",
            "preflight-combat-bridges",
            "verify-combat-bridges",
            "compare-profile-bridges",
            "preflight-profile-bridges",
            "verify-profile-bridges",
            "compare-rest-bridges",
            "verify-rest-bridges",
            "verify-shop-bridge",
            "verify-shop-bridges",
        }:
            command.add_argument("bridge_config", type=Path)
        if name in {
            "compare-starting-bridges",
            "compare-journey-bridges",
            "verify-journey-bridges",
            "compare-rest-bridge",
            "compare-shop-bridge",
            "compare-shop-bridges",
            "compare-bundle-bridge",
            "compare-bundle-bridges",
            "preflight-bundle-bridges",
            "verify-bundle-bridges",
            "compare-reward-bridge",
            "compare-reward-bridges",
            "preflight-reward-bridges",
            "verify-reward-bridges",
            "compare-profile-bridge",
            "compare-combat-bridge",
            "compare-combat-bridges",
            "preflight-combat-bridges",
            "verify-combat-bridges",
            "compare-profile-bridges",
            "preflight-profile-bridges",
            "verify-profile-bridges",
            "compare-rest-bridges",
            "verify-rest-bridges",
            "verify-shop-bridge",
            "verify-shop-bridges",
        }:
            command.add_argument("--node", required=True, type=Path)
        if name == "probe-shipped-checkpoint":
            command.add_argument("checkpoint_config", type=Path)
            command.add_argument("--node", required=True, type=Path)
        if name == "probe-shipped-journey":
            command.add_argument("journey_config", type=Path)
            command.add_argument("--node", required=True, type=Path)
        if name == "probe-connector-menu":
            command.add_argument("--node", required=True, type=Path)
        if name == "build-cli-candidate":
            command.add_argument("candidate_config", type=Path)
            command.add_argument("--node", required=True, type=Path)
        if name == "build-connector-candidate":
            command.add_argument("candidate_config", type=Path)
        if name in {
            "probe-cli-rest",
            "probe-cli-shop",
            "probe-cli-combat",
            "probe-cli-combat-bridge",
            "probe-cli-bundle",
            "probe-cli-bundle-bridge",
            "probe-cli-reward-bridge",
            "probe-cli-checkpoint",
            "probe-cli-journey",
            "probe-cli-rest-bridge",
            "probe-cli-shop-bridge",
        }:
            command.add_argument("probe_config", type=Path)
            command.add_argument("--node", required=True, type=Path)
        if name in {
            "discover-natural-runs",
            "preflight-natural-discovery",
            "verify-natural-discovery",
        }:
            command.add_argument("discovery_config", type=Path)
            command.add_argument("--node", required=True, type=Path)
        if name == "extract-game-text":
            command.add_argument("text_config", type=Path)
        if name == "inspect-game-source":
            command.add_argument("source_config", type=Path)
        if name == "audit-mode-references":
            command.add_argument("audit_config", type=Path)
        if name == "check-native-reward-generation":
            command.add_argument("reward_config", type=Path)
        if name in {"preflight-native-run", "probe-native-run"}:
            command.add_argument("run_config", type=Path)
            command.add_argument("--node", required=True, type=Path)
        if name == "verify-native-run":
            command.add_argument("report", type=Path)
        if name in {"compare-new-run", "preflight-new-run", "verify-new-run"}:
            command.add_argument("run_config", type=Path)
            command.add_argument("--node", required=True, type=Path)
        if name == "download-game":
            command.add_argument("--qr", action="store_true")
        if name in ("preflight", "freeze"):
            command.add_argument("--game-dir", type=Path)
        if name == "freeze":
            command.add_argument("--destination", type=Path)
        if name == "verify-archive":
            command.add_argument("archive", type=Path)
        if name not in ("download-command", "download-game"):
            command.add_argument("--output", type=Path)


def run_engine_command(args: argparse.Namespace) -> int:
    try:
        config = load_engine_qualification_config(args.config)
        working_app = (
            load_working_app_policy(args.working_app_config, config)
            if getattr(args, "working_app_config", None) is not None
            else None
        )
        if args.engine_command == "download-command":
            print(steam_download_command(config))
            return 0
        if args.engine_command == "download-game":
            download_config = load_engine_download_config(args.downloader_config, config)
            result = download_exact_game(download_config, qr=args.qr)
            print(json.dumps(result, indent=2))
            return 0 if result["status"] == "downloaded_identity_matches" else 1
        if args.output is not None and (args.output.exists() or args.output.is_symlink()):
            raise FileExistsError(f"Refusing to overwrite an existing result: {args.output}")
        if args.engine_command == "inventory-working-apps":
            result = working_app_inventory(config)
            code = 0
        elif args.engine_command == "preflight-native-run":
            result = preflight_native_run(config, args.run_config, node=args.node)
            code = 0 if result["ready_for_diagnostic"] else 1
        elif args.engine_command == "probe-native-run":
            result = probe_native_run(config, args.run_config, node=args.node)
            code = 0 if result["status"] == "candidate_terminal" else 1
        elif args.engine_command == "verify-native-run":
            result = verify_native_run(config, args.report)
            code = 0
        elif args.engine_command == "check-native-progression":
            result = run_native_progression(config, args.progression_config)
            code = 0 if result["status"] == "native_progression_pass" else 1
        elif args.engine_command == "verify-native-progression":
            result = verify_native_progression(config, args.progression_config)
            code = 0
        elif args.engine_command == "preflight-progression-bridges":
            result = preflight_progression_bridges(config, args.progression_config, node=args.node)
            code = 0
        elif args.engine_command == "compare-progression-bridges":
            result = compare_progression_bridges(config, args.progression_config, node=args.node)
            code = 0 if result["status"] == "progression_comparisons_pass" else 1
        elif args.engine_command == "verify-progression-bridges":
            result = verify_progression_bridges(config, args.progression_config, node=args.node)
            code = 0
        elif args.engine_command == "audit-saved-progression":
            result = audit_saved_progression(config, args.progression_config, node=args.node)
            code = 0
        elif args.engine_command == "compare-new-run":
            result = compare_new_run(config, args.run_config, node=args.node)
            code = (
                0
                if result["status"] in {"normal_start_comparison_pass", "natural_shipped_run_pass"}
                else 1
            )
        elif args.engine_command == "preflight-new-run":
            result = compare_new_run(config, args.run_config, node=args.node, preflight=True)
            code = 0 if result["ready_for_diagnostic"] else 1
        elif args.engine_command == "verify-new-run":
            result = verify_new_run(config, args.run_config, node=args.node)
            code = 0
        elif args.engine_command in {"discover-natural-runs", "preflight-natural-discovery"}:
            preflight = args.engine_command == "preflight-natural-discovery"
            result = discover_runs(
                config, args.discovery_config, node=args.node, preflight=preflight
            )
            code = (
                0
                if result.get("ready_for_diagnostic") is True
                or result.get("status") == "discovery_complete"
                else 1
            )
            if not preflight:
                result = {key: value for key, value in result.items() if key != "cases"}
        elif args.engine_command == "verify-natural-discovery":
            result = verify_discovery_runs(config, args.discovery_config, node=args.node)
            code = 0 if result["valid"] else 1
        elif args.engine_command == "download-plan":
            result = download_plan(load_engine_download_config(args.downloader_config, config))
            code = 0
        elif args.engine_command == "compare-starting-bridges":
            result = run_starting_bridges(config, args.bridge_config, node=args.node)
            code = 0 if result["status"] == "starting_input_comparisons_pass" else 1
        elif args.engine_command == "verify-starting-bridges":
            result = verify_starting_bridges(config, args.bridge_config)
            code = 0
        elif args.engine_command == "compare-journey-bridges":
            result = run_journey_bridges(config, args.bridge_config, node=args.node)
            code = 0 if result["status"] == "first_combat_comparisons_pass" else 1
        elif args.engine_command == "verify-journey-bridges":
            result = verify_journey_bridges(config, args.bridge_config, node=args.node)
            code = 0
        elif args.engine_command in {"verify-shop-bridge", "verify-shop-bridges"}:
            result = (
                verify_shop_bridge
                if args.engine_command == "verify-shop-bridge"
                else verify_shop_bridges
            )(config, args.bridge_config, node=args.node)
            code = 0
        elif args.engine_command == "verify-rest-bridges":
            result = verify_rest_bridges(config, args.bridge_config, node=args.node)
            code = 0
        elif args.engine_command == "verify-reward-bridges":
            result = verify_reward_bridges(config, args.bridge_config, node=args.node)
            code = 0
        elif args.engine_command == "preflight-reward-bridges":
            result = preflight_reward_bridges(config, args.bridge_config, node=args.node)
            code = 0
        elif args.engine_command in {"compare-combat-bridge", "compare-combat-bridges"}:
            result = (
                compare_combat_bridge
                if args.engine_command == "compare-combat-bridge"
                else compare_combat_bridges
            )(config, args.bridge_config, node=args.node)
            code = (
                0
                if result["status"] in {"combat_comparison_pass", "combat_comparisons_pass"}
                else 1
            )
        elif args.engine_command == "preflight-combat-bridges":
            result = preflight_combat_bridges(config, args.bridge_config, node=args.node)
            code = 0
        elif args.engine_command == "verify-combat-bridges":
            result = verify_combat_bridges(config, args.bridge_config, node=args.node)
            code = 0
        elif args.engine_command in {"compare-profile-bridge", "compare-profile-bridges"}:
            result = (
                compare_profile_bridge
                if args.engine_command == "compare-profile-bridge"
                else compare_profile_bridges
            )(config, args.bridge_config, node=args.node)
            code = (
                0
                if result["status"] in {"profile_comparison_pass", "profile_comparisons_pass"}
                else 1
            )
        elif args.engine_command == "preflight-profile-bridges":
            result = preflight_profile_bridges(config, args.bridge_config, node=args.node)
            code = 0
        elif args.engine_command == "verify-profile-bridges":
            result = verify_profile_bridges(config, args.bridge_config, node=args.node)
            code = 0
        elif args.engine_command in {"compare-reward-bridge", "compare-reward-bridges"}:
            result = (
                compare_reward_bridge
                if args.engine_command == "compare-reward-bridge"
                else compare_reward_bridges
            )(config, args.bridge_config, node=args.node)
            code = (
                0
                if result["status"] in {"reward_action_comparison_pass", "reward_comparisons_pass"}
                else 1
            )
        elif args.engine_command == "verify-bundle-bridges":
            result = verify_bundle_bridges(config, args.bridge_config, node=args.node)
            code = 0
        elif args.engine_command == "preflight-bundle-bridges":
            result = preflight_bundle_bridges(config, args.bridge_config, node=args.node)
            code = 0
        elif args.engine_command in {"compare-rest-bridge", "compare-rest-bridges"}:
            result = (
                compare_rest_bridge
                if args.engine_command == "compare-rest-bridge"
                else compare_rest_bridges
            )(config, args.bridge_config, node=args.node)
            code = (
                0
                if result["status"] in {"rest_action_comparison_pass", "rest_comparisons_pass"}
                else 1
            )
        elif args.engine_command in {"compare-bundle-bridge", "compare-bundle-bridges"}:
            comparison = (
                compare_bundle_bridge
                if args.engine_command == "compare-bundle-bridge"
                else compare_bundle_bridges
            )
            result = comparison(config, args.bridge_config, node=args.node)
            code = (
                0
                if result["status"] in {"bundle_action_comparison_pass", "bundle_comparisons_pass"}
                else 1
            )
        elif args.engine_command in {"compare-shop-bridge", "compare-shop-bridges"}:
            result = (
                compare_shop_bridge
                if args.engine_command == "compare-shop-bridge"
                else compare_shop_bridges
            )(config, args.bridge_config, node=args.node)
            code = (
                0
                if result["status"] in {"shop_action_comparison_pass", "shop_comparisons_pass"}
                else 1
            )
        elif args.engine_command == "probe-shipped-checkpoint":
            result = probe_shipped_checkpoint(config, args.checkpoint_config, node=args.node)
            code = 0 if result["verdict"]["status"] == "shipped_checkpoint_input_pass" else 1
        elif args.engine_command == "probe-shipped-journey":
            result = probe_shipped_journey(config, args.journey_config, node=args.node)
            code = 0 if result["status"] == "first_combat_prefix_pass" else 1
        elif args.engine_command == "build-cli-candidate":
            result = build_cli_candidate(config, args.candidate_config, args.node)
            code = 0 if result["status"] == "candidate_built_unqualified" else 1
        elif args.engine_command == "audit-mode-references":
            result = audit_mode_references(config, args.audit_config)
            code = 0
        elif args.engine_command == "check-native-reward-generation":
            result = check_native_reward_generation(config, args.reward_config)
            code = 0
        elif args.engine_command == "build-connector-candidate":
            result = build_connector_candidate(config, args.candidate_config)
            code = 0
        elif args.engine_command in {
            "probe-cli-rest",
            "probe-cli-shop",
            "probe-cli-combat",
            "probe-cli-combat-bridge",
            "probe-cli-bundle",
            "probe-cli-bundle-bridge",
            "probe-cli-reward-bridge",
            "probe-cli-checkpoint",
            "probe-cli-journey",
            "probe-cli-rest-bridge",
            "probe-cli-shop-bridge",
        }:
            result = probe_cli_rest(
                config,
                args.probe_config,
                args.node,
                panel=args.engine_command.removeprefix("probe-cli-").replace("-", "_"),
            )
            code = (
                0
                if result["status"]
                in {
                    "rest_native_regression_pass",
                    "rest_public_projection_regression_pass",
                    "rest_bridge_public_projection_regression_pass",
                    "shop_bridge_public_projection_regression_pass",
                    "journey_public_projection_regression_pass",
                    "shop_native_regression_pass",
                    "shop_public_projection_regression_pass",
                    "combat_native_regression_pass",
                    "combat_public_projection_regression_pass",
                    "combat_bridge_public_projection_regression_pass",
                    "bundle_public_projection_regression_pass",
                    "bundle_bridge_public_projection_regression_pass",
                    "reward_bridge_public_projection_regression_pass",
                    "checkpoint_public_projection_regression_pass",
                }
                else 1
            )
        elif args.engine_command == "extract-game-text":
            text_config = json.loads(args.text_config.read_text())
            if (
                text_config.get("schema_version") != "engine-native-text-config-v1"
                or text_config.get("qualification_config_id") != config.config_id
                or text_config.get("training_allowed") is not False
            ):
                raise ValueError("Expected an exact frozen native text extraction configuration")
            native = load_native_qualification_config(
                config.root / text_config["native_config"], config
            )
            archive, _ = _verified_archive(native)
            result = extract_native_localization(
                config, archive, Path(text_config["directory"]), text_config["pack_sha256"]
            )
            code = 0
        elif args.engine_command == "inspect-game-source":
            result = inspect_game_source(config, args.source_config)
            code = 0 if result["status"] == "private_source_extraction_complete" else 1
        elif args.engine_command in ("prepare-connector", "probe-connector-menu"):
            connector = load_connector_qualification_config(args.connector_config, config)
            if args.engine_command == "prepare-connector":
                result = prepare_connector_toolchain(connector)
                code = 0
            else:
                result = probe_connector_menu(
                    connector,
                    node=args.node,
                    **({"working_app": working_app} if working_app is not None else {}),
                )
                code = 0 if result["verdict"]["status"] == "shipped_connector_menu_pass" else 1
        elif args.engine_command in ("bootstrap-profile", "model-inventory"):
            native = load_native_qualification_config(args.native_config, config)
            if args.engine_command == "bootstrap-profile":
                result = bootstrap_native_profile(
                    native, **({"working_app": working_app} if working_app is not None else {})
                )
                code = 0 if result["verdict"]["status"] == "native_profile_bootstrap_pass" else 1
            else:
                result = inspect_model_registry(native)
                code = 0
        elif args.engine_command == "preflight":
            result = engine_preflight(config, game_dir=args.game_dir)
            code = 0 if result["status"] == "identity_ready" else 2
        elif args.engine_command == "freeze":
            destination = args.destination or default_archive_path(config)
            if destination.exists() or destination.is_symlink():
                # Re-running verifies existing bytes; it never displays stale success or overwrites.
                result = verify_game_archive(config, destination)
                code = 0 if result["valid"] else 1
            else:
                preflight = engine_preflight(config, game_dir=args.game_dir)
                if not preflight["matching_game_paths"]:
                    raise ValueError(
                        "The exact game is missing. Run the current owner acquisition helper "
                        "in docs/actual-engine-v0.111.0.md; beta downloads require "
                        "the correct branch."
                    )
                record = freeze_game_archive(
                    config,
                    Path(preflight["matching_game_paths"][0]),
                    destination,
                )
                result = {
                    "archive_id": record["archive_id"],
                    "archive": str(destination),
                    "files": record["files"],
                    "bytes": record["bytes"],
                    "launch_verified": False,
                    "training_allowed": False,
                    "games_launched": 0,
                }
                code = 0
        else:
            result = verify_game_archive(config, args.archive)
            code = 0 if result["valid"] else 1
        if args.output is not None:
            atomic_json(args.output, result)
        displayed = result
        if args.engine_command in {"prepare-connector", "extract-game-text"}:
            displayed = {key: value for key, value in result.items() if key != "inventory"}
            displayed["verified_toolchain_files"] = len(result["inventory"])
        elif args.engine_command in {
            "probe-connector-menu",
            "probe-shipped-checkpoint",
            "probe-shipped-journey",
        }:
            displayed = {key: value for key, value in result.items() if key != "probe"}
        elif args.engine_command == "build-cli-candidate":
            displayed = {
                key: value
                for key, value in result.items()
                if key not in {"private_candidate_inventory", "build"}
            }
            displayed["build_detail"] = {
                key: value for key, value in result["build"].items() if key != "report"
            }
        elif args.engine_command in {
            "probe-cli-rest",
            "probe-cli-shop",
            "probe-cli-combat",
            "probe-cli-combat-bridge",
            "probe-cli-bundle",
            "probe-cli-bundle-bridge",
            "probe-cli-reward-bridge",
            "probe-cli-checkpoint",
            "probe-cli-journey",
            "probe-cli-rest-bridge",
            "probe-cli-shop-bridge",
        }:
            displayed = {
                key: value
                for key, value in result.items()
                if key not in {"probe", "shared_profile_sentinel"}
            }
            gates = result["probe"].get("gates", {})
            displayed["native_checks"] = (
                {
                    "passed": sum(value is True for value in gates.values()),
                    "total": len(gates),
                    "failed": [key for key, value in gates.items() if value is not True],
                }
                if "projection" in result["schema_version"]
                else gates
            )
            if "canonical_delivery" in result["probe"]:
                displayed["canonical_delivery"] = result["probe"]["canonical_delivery"]
            displayed["error"] = result["probe"].get("error")
        elif args.engine_command == "inspect-game-source":
            displayed = {key: value for key, value in result.items() if key != "inventory"}
        elif args.engine_command == "compare-new-run":
            displayed = {key: value for key, value in result.items() if key != "shipped_report"}
            shipped = result["shipped_report"]
            displayed.update(
                error=shipped["probe"].get("error"),
                wall_seconds=shipped["process"]["wall_seconds"],
                app_copies_created=shipped["working_app"]["app_copies_created"],
                fixed_app_reset_verified=shipped["working_app"]["restored"],
            )
        print(json.dumps(displayed, indent=2))
        return code
    except subprocess.TimeoutExpired:
        print(
            json.dumps(
                {
                    "status": "stopped",
                    "error": "The current engine stage reached its wall-time cap; "
                    "partial private evidence remains. No next stage follows.",
                }
            )
        )
        return 1
    except KeyboardInterrupt:
        print(
            json.dumps(
                {
                    "status": "stopped",
                    "error": "The current engine stage was interrupted; partial "
                    "private evidence remains. No next stage follows.",
                }
            )
        )
        return 130
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, indent=2))
        return 1
