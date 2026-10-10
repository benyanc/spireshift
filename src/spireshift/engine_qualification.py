"""Identify and preserve a game build without launching it or admitting a backend."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.doctor import (
    STS2_APP_ID,
    STS2_DIRECTORY_NAME,
    GameCandidate,
    discover_game_candidates,
    inspect_game_installation,
)
from spireshift.full_run_experience import atomic_json

ARCHIVE_RECORD = "frozen-game-archive.json"
GAME_RELATIVE = Path("steamapps/common") / STS2_DIRECTORY_NAME


@dataclass(frozen=True)
class EngineQualificationConfig:
    document: dict[str, Any]
    root: Path

    @property
    def config_id(self) -> str:
        return manifest_identifier(self.document)

    @property
    def target(self) -> dict[str, Any]:
        return dict(self.document["target"])

    def source_path(self, source: dict[str, Any]) -> Path:
        return (self.root / str(source["path"])).resolve()


def load_engine_qualification_config(path: Path) -> EngineQualificationConfig:
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != "engine-qualification-config-v1"
    ):
        raise ValueError("Expected engine-qualification-config-v1")
    if value.get("stage") != "identity_and_preservation_only":
        raise ValueError("This command only identifies and preserves a game build")
    target = value.get("target")
    if not isinstance(target, dict) or target.get("app_id") != STS2_APP_ID:
        raise ValueError("Expected the STS2 app identity")
    for key in ("platform", "architecture", "version", "commit", "authority"):
        if not isinstance(target.get(key), str) or not target[key]:
            raise ValueError(f"Missing target {key}")
    for key in ("executable_sha256", "assembly_sha256", "godotsharp_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(target.get(key, ""))):
            raise ValueError(f"Invalid target {key}")
    if type(target.get("runtime_main_assembly_hash")) is not int:
        raise ValueError("Missing runtime assembly identity")
    files = value.get("required_game_files")
    if (
        not isinstance(files, list)
        or not files
        or any(
            not isinstance(item, str)
            or not item
            or Path(item).is_absolute()
            or ".." in Path(item).parts
            for item in files
        )
    ):
        raise ValueError("Required game files must be relative paths within the game")
    sources = value.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("Expected pinned engine sources")
    names: set[str] = set()
    for source in sources:
        if not isinstance(source, dict) or not all(
            isinstance(source.get(key), str) and source[key]
            for key in ("name", "repository", "path", "commit")
        ):
            raise ValueError("Invalid engine source")
        if source["name"] in names or not re.fullmatch(r"[0-9a-f]{40}", source["commit"]):
            raise ValueError("Engine sources need distinct names and exact commits")
        names.add(source["name"])
    acquisition = value.get("acquisition")
    if not isinstance(acquisition, dict) or not all(
        re.fullmatch(r"[0-9]+", str(acquisition.get(key, "")))
        for key in ("depot_id", "manifest_id", "observed_steam_build_id")
    ):
        raise ValueError("Expected an observed depot/manifest/build identity")
    archive_name = value.get("archive_name")
    if not isinstance(archive_name, str) or not re.fullmatch(r"[a-zA-Z0-9._-]+", archive_name):
        raise ValueError("Invalid archive name")
    if (
        not isinstance(value.get("qualification_required"), list)
        or not value["qualification_required"]
    ):
        raise ValueError("Gameplay qualification must remain separate from identity")
    return EngineQualificationConfig(value, path.resolve().parents[2])


def steam_download_command(config: EngineQualificationConfig) -> str:
    acquisition = config.document["acquisition"]
    return f"download_depot {STS2_APP_ID} {acquisition['depot_id']} {acquisition['manifest_id']}"


def default_archive_path(config: EngineQualificationConfig) -> Path:
    return (
        Path.home()
        / "Library/Application Support/SpireShift/frozen-games"
        / str(config.document["archive_name"])
    )


def downloaded_game_candidates(config: EngineQualificationConfig) -> list[GameCandidate]:
    """Steam console content has no installed-app manifest; never borrow the old one."""
    suffix = Path(f"content/app_{STS2_APP_ID}/depot_{config.document['acquisition']['depot_id']}")
    roots = {
        candidate.path.parent.parent.parent for candidate in discover_game_candidates(environ={})
    }
    paths = {root / suffix for root in roots} | {root / "steamapps" / suffix for root in roots}
    return [GameCandidate(path, "steam_console_depot", None) for path in sorted(paths)]


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_candidate(
    config: EngineQualificationConfig, candidate: GameCandidate
) -> dict[str, Any]:
    try:
        installation = inspect_game_installation(candidate)
        actual: dict[str, Any] = {
            "platform": installation.platform,
            "architecture": installation.architecture,
            "version": installation.version,
            "commit": installation.commit,
            "assembly_sha256": installation.assembly_sha256,
            "runtime_main_assembly_hash": installation.runtime_main_assembly_hash,
            "executable_sha256": _sha_file(installation.executable),
            "godotsharp_sha256": _sha_file(installation.data_directory / "GodotSharp.dll"),
        }
        errors = [
            f"{key} mismatch: found {value!r}; requires {config.target[key]!r}"
            for key, value in actual.items()
            if value != config.target[key]
        ]
        errors.extend(
            f"Required base-game file missing or empty: {name}"
            for name in config.document["required_game_files"]
            if not (candidate.path / name).is_file() or (candidate.path / name).stat().st_size == 0
        )
        return {
            "path": str(candidate.path.resolve()),
            "source": candidate.source,
            "matches_target": not errors,
            "identity": actual,
            "installation": installation.manifest(),
            "errors": errors,
        }
    except (OSError, ValueError) as error:
        return {
            "path": str(candidate.path.resolve()),
            "source": candidate.source,
            "matches_target": False,
            "errors": [str(error)],
        }


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    if result.returncode:
        raise ValueError(f"Cannot inspect engine source: {result.stderr.strip()}")
    return result.stdout.strip()


def inspect_engine_sources(config: EngineQualificationConfig) -> list[dict[str, Any]]:
    results = []
    for source in config.document["sources"]:
        root = config.source_path(source)
        record: dict[str, Any] = {
            "name": source["name"],
            "path": str(root),
            "expected_commit": source["commit"],
        }
        try:
            # Include untracked files: a different host, patch or mod may otherwise be overlooked.
            commit = _git(root, "rev-parse", "HEAD")
            dirty = bool(_git(root, "status", "--porcelain", "--untracked-files=all"))
            record.update(
                commit=commit, dirty=dirty, matches_target=commit == source["commit"] and not dirty
            )
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            record.update(matches_target=False, error=str(error))
        results.append(record)
    return results


def engine_preflight(
    config: EngineQualificationConfig,
    *,
    game_dir: Path | None = None,
) -> dict[str, Any]:
    candidates = (
        [GameCandidate(game_dir.expanduser(), "explicit_game_directory", None)]
        if game_dir is not None
        else [
            GameCandidate(default_archive_path(config) / GAME_RELATIVE, "target_archive", None),
            *downloaded_game_candidates(config),
            *discover_game_candidates(),
        ]
    )
    games = [inspect_candidate(config, candidate) for candidate in candidates]
    matching = [item for item in games if item["matches_target"]]
    sources = inspect_engine_sources(config)
    sources_match = all(item["matches_target"] for item in sources)
    body = {
        "schema_version": "engine-preflight-v1",
        "config_id": config.config_id,
        "status": "identity_ready" if matching and sources_match else "needs_inputs",
        "target": config.target,
        "games": games,
        "sources": sources,
        "matching_game_paths": [item["path"] for item in matching],
        "steam_console_command": steam_download_command(config),
        "archive_destination": str(default_archive_path(config)),
        "next_step": (
            "freeze_or_verify_matching_game"
            if matching and sources_match
            else "prepare_pinned_sources"
            if matching
            else "owner_download_exact_game"
        ),
        "decision": {
            "backend_admitted": False,
            "training_allowed": False,
            "adaptive_controller_allowed": False,
        },
        "qualification_required": config.document["qualification_required"],
        "games_launched": 0,
        "downloads_started": 0,
        "claim_scope": "file_and_source_identity_only_not_gameplay_qualification",
    }
    return {**body, "report_id": manifest_identifier(body)}


def _inventory(root: Path) -> list[dict[str, Any]]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Archive game root must be a real directory")
    rows = []
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise ValueError(f"Symlink cannot be frozen: {path.relative_to(root)}")
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f"Unsupported archive entry: {path.relative_to(root)}")
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": _sha_file(path),
                "bytes": info.st_size,
                "mode": stat.S_IMODE(info.st_mode),
            }
        )
    return rows


def _require_game(config: EngineQualificationConfig, root: Path) -> dict[str, Any]:
    result = inspect_candidate(config, GameCandidate(root, "frozen_game_candidate", None))
    if not result["matches_target"]:
        raise ValueError("Exact game identity required: " + "; ".join(result["errors"]))
    return result


def freeze_game_archive(
    config: EngineQualificationConfig,
    source: Path,
    destination: Path,
) -> dict[str, Any]:
    """Publish a verified base-game copy once; leave explicit failure evidence on interruption."""
    source = source.expanduser().absolute()
    destination = destination.expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Archive already exists; use verify-archive: {destination}")
    if source.is_symlink():
        raise ValueError("Game source must not be a symlink")
    source = source.resolve()
    resolved_destination = destination.resolve()
    if resolved_destination == source or resolved_destination.is_relative_to(source):
        raise ValueError("Archive must be separate from the source game")
    for candidate in discover_game_candidates(environ={}):
        steamapps = candidate.path.parent.parent.resolve()
        if resolved_destination.is_relative_to(steamapps):
            raise ValueError("Archive must be outside Steam-managed steamapps")
    identity = _require_game(config, source)
    inventory = _inventory(source)
    mods = Path(identity["installation"]["game"]["mods_directory"])
    if mods.is_dir() and any(path.is_file() for path in mods.rglob("*")):
        raise ValueError("Freeze an unmodified base game; mod installation is a separate gate")
    destination.mkdir(parents=True, exist_ok=False)
    atomic_json(
        destination / "freeze-in-progress.json",
        {
            "config_id": config.config_id,
            "source": str(source),
            "status": "copying_not_qualified",
            "games_launched": 0,
        },
    )
    try:
        game = destination / GAME_RELATIVE
        game.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, game, copy_function=shutil.copy2, symlinks=True)
        if _inventory(source) != inventory:
            raise ValueError("Source game changed while freezing; partial archive retained")
        if _inventory(game) != inventory:
            raise ValueError("Copied game differs from its source inventory")
        frozen = _require_game(config, game)
        body = {
            "schema_version": "frozen-game-archive-v1",
            "config_id": config.config_id,
            "identity": frozen["identity"],
            "game_relative_path": GAME_RELATIVE.as_posix(),
            "inventory": inventory,
            "tree_id": manifest_identifier(inventory),
            "files": len(inventory),
            "bytes": sum(row["bytes"] for row in inventory),
            "source": str(source),
            "steam_provenance": {
                "app_id": STS2_APP_ID,
                **config.document["acquisition"],
                "scope": "observed_download_request_not_installed_appmanifest",
            },
            "launch_verified": False,
            "save_profile_isolated": False,
            "backend_admitted": False,
            "training_allowed": False,
            "games_launched": 0,
            "claim_scope": "verified_private_file_archive_not_runtime_or_gameplay",
        }
        record = {**body, "archive_id": manifest_identifier(body)}
        atomic_json(destination / ARCHIVE_RECORD, record)
        (destination / "freeze-in-progress.json").unlink()
        return record
    except BaseException as error:
        atomic_json(
            destination / "freeze-failure.json",
            {
                "config_id": config.config_id,
                "status": "failed_partial_archive",
                "error": f"{type(error).__name__}: {error}",
                "training_allowed": False,
            },
        )
        raise


def verify_game_archive(
    config: EngineQualificationConfig,
    archive: Path,
) -> dict[str, Any]:
    archive = archive.expanduser()
    errors: list[str] = []
    try:
        record = json.loads((archive / ARCHIVE_RECORD).read_text(encoding="utf-8"))
        body = {key: value for key, value in record.items() if key != "archive_id"}
        if record.get("archive_id") != manifest_identifier(body):
            errors.append("Archive record digest mismatch")
        if record.get("config_id") != config.config_id:
            errors.append("Archive belongs to another qualification configuration")
        if record.get("game_relative_path") != GAME_RELATIVE.as_posix():
            raise ValueError("Invalid game path in archive record")
        if (archive / "freeze-in-progress.json").exists() or (
            archive / "freeze-failure.json"
        ).exists():
            errors.append("Archive has incomplete or failed freeze evidence")
        game = archive / GAME_RELATIVE
        identity = _require_game(config, game)
        inventory = _inventory(game)
        if inventory != record.get("inventory") or record.get("tree_id") != manifest_identifier(
            inventory
        ):
            errors.append("Archive file content, inventory or permissions changed")
        if identity["identity"] != record.get("identity"):
            errors.append("Archive identity record differs from the current files")
    except (OSError, ValueError, TypeError, AttributeError) as error:
        errors.append(str(error))
    body = {
        "schema_version": "frozen-game-verification-v1",
        "valid": not errors,
        "config_id": config.config_id,
        "archive": str(archive.expanduser().resolve()),
        "errors": errors,
        "games_launched": 0,
        "training_allowed": False,
        "claim_scope": "current_private_archive_integrity_only",
    }
    return {**body, "report_id": manifest_identifier(body)}
