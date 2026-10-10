"""Separate identity, acquisition and bounded native checks; never starts training."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from spireshift.engine_candidate import build_cli_candidate
from spireshift.engine_cli_probe import probe_cli_rest
from spireshift.engine_connector import (
    load_connector_qualification_config,
    prepare_connector_toolchain,
    probe_connector_menu,
)
from spireshift.engine_download import (
    download_exact_game,
    download_plan,
    load_engine_download_config,
)
from spireshift.engine_native import (
    bootstrap_native_profile,
    inspect_model_registry,
    load_native_qualification_config,
)
from spireshift.engine_qualification import (
    default_archive_path,
    engine_preflight,
    freeze_game_archive,
    load_engine_qualification_config,
    steam_download_command,
    verify_game_archive,
)
from spireshift.engine_source import inspect_game_source
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
        "download-command",
        "download-plan",
        "download-game",
        "bootstrap-profile",
        "model-inventory",
        "prepare-connector",
        "probe-connector-menu",
        "build-cli-candidate",
        "probe-cli-rest",
        "inspect-game-source",
    ):
        command = sub.add_parser(name)
        command.add_argument("config", type=Path)
        if name in ("download-plan", "download-game"):
            command.add_argument("downloader_config", type=Path)
        if name in ("bootstrap-profile", "model-inventory"):
            command.add_argument("native_config", type=Path)
        if name in ("prepare-connector", "probe-connector-menu"):
            command.add_argument("connector_config", type=Path)
        if name == "probe-connector-menu":
            command.add_argument("--node", required=True, type=Path)
        if name == "build-cli-candidate":
            command.add_argument("candidate_config", type=Path)
            command.add_argument("--node", required=True, type=Path)
        if name == "probe-cli-rest":
            command.add_argument("probe_config", type=Path)
            command.add_argument("--node", required=True, type=Path)
        if name == "inspect-game-source":
            command.add_argument("source_config", type=Path)
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
        if args.engine_command == "download-plan":
            result = download_plan(load_engine_download_config(args.downloader_config, config))
            code = 0
        elif args.engine_command == "build-cli-candidate":
            result = build_cli_candidate(config, args.candidate_config, args.node)
            code = 0 if result["status"] == "candidate_built_unqualified" else 1
        elif args.engine_command == "probe-cli-rest":
            result = probe_cli_rest(config, args.probe_config, args.node)
            code = 0 if result["status"] == "rest_native_regression_pass" else 1
        elif args.engine_command == "inspect-game-source":
            result = inspect_game_source(config, args.source_config)
            code = 0 if result["status"] == "private_source_extraction_complete" else 1
        elif args.engine_command in ("prepare-connector", "probe-connector-menu"):
            connector = load_connector_qualification_config(args.connector_config, config)
            if args.engine_command == "prepare-connector":
                result = prepare_connector_toolchain(connector)
                code = 0
            else:
                result = probe_connector_menu(connector, node=args.node)
                code = 0 if result["verdict"]["status"] == "shipped_connector_menu_pass" else 1
        elif args.engine_command in ("bootstrap-profile", "model-inventory"):
            native = load_native_qualification_config(args.native_config, config)
            if args.engine_command == "bootstrap-profile":
                result = bootstrap_native_profile(native)
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
        if args.engine_command == "prepare-connector":
            displayed = {key: value for key, value in result.items() if key != "inventory"}
            displayed["verified_toolchain_files"] = len(result["inventory"])
        elif args.engine_command == "probe-connector-menu":
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
        elif args.engine_command == "probe-cli-rest":
            displayed = {
                key: value
                for key, value in result.items()
                if key not in {"probe", "shared_profile_sentinel"}
            }
            displayed["native_checks"] = result["probe"].get("gates", {})
            displayed["error"] = result["probe"].get("error")
        elif args.engine_command == "inspect-game-source":
            displayed = {key: value for key, value in result.items() if key != "inventory"}
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
