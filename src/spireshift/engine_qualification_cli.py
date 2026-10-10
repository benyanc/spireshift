"""Small CLI for actual-engine prerequisites; never starts game or training processes."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from spireshift.engine_download import (
    download_exact_game,
    download_plan,
    load_engine_download_config,
)
from spireshift.engine_qualification import (
    default_archive_path,
    engine_preflight,
    freeze_game_archive,
    load_engine_qualification_config,
    steam_download_command,
    verify_game_archive,
)
from spireshift.full_run_experience import atomic_json


def add_engine_parser(commands: Any) -> None:
    engine = commands.add_parser(
        "engine", help="Identify and preserve actual-game inputs; no games"
    )
    sub = engine.add_subparsers(dest="engine_command", required=True)
    for name in (
        "preflight",
        "freeze",
        "verify-archive",
        "download-command",
        "download-plan",
        "download-game",
    ):
        command = sub.add_parser(name)
        command.add_argument("config", type=Path)
        if name in ("download-plan", "download-game"):
            command.add_argument("downloader_config", type=Path)
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
        print(json.dumps(result, indent=2))
        return code
    except subprocess.TimeoutExpired:
        print(
            json.dumps(
                {
                    "status": "stopped",
                    "error": "Download reached its wall-time cap; "
                    "partial content remains. Re-run the same owner helper to validate/resume.",
                }
            )
        )
        return 1
    except KeyboardInterrupt:
        print(
            json.dumps(
                {
                    "status": "stopped",
                    "error": "Owner stopped the download; partial "
                    "content remains. Re-run the same helper to validate/resume.",
                }
            )
        )
        return 130
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, indent=2))
        return 1
