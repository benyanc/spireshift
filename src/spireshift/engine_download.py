"""Owner-started acquisition of an exact beta manifest into an isolated directory."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.doctor import GameCandidate
from spireshift.engine_qualification import EngineQualificationConfig, inspect_candidate


@dataclass(frozen=True)
class EngineDownloadConfig:
    document: dict[str, Any]
    qualification: EngineQualificationConfig

    @property
    def config_id(self) -> str:
        return manifest_identifier(self.document)

    @property
    def tool_directory(self) -> Path:
        return self.qualification.root / "artifacts/engine-tools/depotdownloader-3.4.0-macos-arm64"

    @property
    def work_directory(self) -> Path:
        return (
            self.qualification.root
            / "artifacts/engine-downloads"
            / str(self.qualification.document["archive_name"])
        )

    @property
    def game_directory(self) -> Path:
        return self.work_directory / "game"


def load_engine_download_config(
    path: Path, qualification: EngineQualificationConfig
) -> EngineDownloadConfig:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != "engine-download-config-v1":
        raise ValueError("Expected engine-download-config-v1")
    if value.get("qualification_config_id") != qualification.config_id:
        raise ValueError("Download configuration does not match the exact qualification inputs")
    if value.get("branch") != "public-beta":
        raise ValueError("The observed target manifest belongs to public-beta")
    for key, maximum in (
        ("login_id", 2**32 - 1),
        ("max_downloads", 16),
        ("max_wall_seconds", 7200),
    ):
        if type(value.get(key)) is not int or not 0 < value[key] <= maximum:
            raise ValueError(f"Invalid download {key}")
    downloader = value.get("downloader")
    if not isinstance(downloader, dict) or (
        downloader.get("release") != "DepotDownloader_3.4.0"
        or downloader.get("url")
        != "https://github.com/SteamRE/DepotDownloader/releases/download/"
        "DepotDownloader_3.4.0/DepotDownloader-macos-arm64.zip"
        or type(downloader.get("archive_bytes")) is not int
        or not 0 < downloader["archive_bytes"] <= 50_000_000
        or not re.fullmatch(r"[0-9a-f]{40}", str(downloader.get("source_commit", "")))
        or any(
            not re.fullmatch(r"[0-9a-f]{64}", str(downloader.get(key, "")))
            for key in ("archive_sha256", "executable_sha256")
        )
    ):
        raise ValueError("Expected pinned official macOS arm64 downloader inputs")
    return EngineDownloadConfig(value, qualification)


def _ensure_private_path(path: Path, root: Path) -> None:
    """Never follow a private-artifact symlink into an installed game or archive."""
    path.relative_to(root)
    current = path
    while current != root:
        if current.is_symlink():
            raise ValueError(f"Refusing a symlink in the acquisition path: {current}")
        current = current.parent


def _sha(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def prepare_downloader(config: EngineDownloadConfig) -> Path:
    """Bounded tool setup only; it never authenticates or requests game content."""
    directory = config.tool_directory
    _ensure_private_path(directory, config.qualification.root)
    directory.mkdir(parents=True, exist_ok=True)
    binary = directory / "DepotDownloader"
    specification = config.document["downloader"]
    if binary.exists() or binary.is_symlink():
        if binary.is_symlink() or _sha(binary) != specification["executable_sha256"]:
            raise ValueError("Prepared downloader fingerprint mismatch; refusing to execute it")
        if not os.access(binary, os.X_OK):
            raise ValueError("Prepared downloader is not executable")
        return binary

    archive = directory / "DepotDownloader-macos-arm64.zip"
    if not archive.exists():
        partial = directory / f"DepotDownloader-macos-arm64.zip.{uuid.uuid4().hex}.partial"
        started = time.monotonic()
        try:
            with (
                urllib.request.urlopen(specification["url"], timeout=20) as response,
                partial.open("xb") as output,
            ):
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > specification["archive_bytes"] or time.monotonic() - started > 90:
                        raise ValueError("Downloader tool preparation exceeded its size/time limit")
                    output.write(chunk)
            if _sha(partial) != specification["archive_sha256"]:
                raise ValueError("Downloaded tool archive fingerprint mismatch")
            os.link(partial, archive)
            partial.unlink()
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
    if archive.is_symlink() or _sha(archive) != specification["archive_sha256"]:
        raise ValueError("Downloader archive fingerprint mismatch")
    with zipfile.ZipFile(archive) as package:
        # Extract only the two named members, never arbitrary archive paths.
        executable = package.read("DepotDownloader")
        if hashlib.sha256(executable).hexdigest() != specification["executable_sha256"]:
            raise ValueError("Downloader executable fingerprint mismatch")
        with binary.open("xb") as output:
            output.write(executable)
        binary.chmod(0o755)
        license_path = directory / "LICENSE"
        if not license_path.exists():
            with license_path.open("xb") as output:
                output.write(package.read("LICENSE"))
    return binary


def downloader_arguments(
    config: EngineDownloadConfig, *, username: str | None = None, qr: bool = False
) -> list[str]:
    if qr == (username is not None):
        raise ValueError("Choose exactly one local login method")
    if username is not None and (not username.strip() or username.startswith("-")):
        raise ValueError("Enter a nonempty Steam account name")
    acquisition = config.qualification.document["acquisition"]
    return [
        str(config.tool_directory / "DepotDownloader"),
        "-app",
        str(config.qualification.target["app_id"]),
        "-depot",
        str(acquisition["depot_id"]),
        "-manifest",
        str(acquisition["manifest_id"]),
        "-branch",
        str(config.document["branch"]),
        "-os",
        "macos",
        "-dir",
        str(config.game_directory),
        "-validate",
        "-loginid",
        str(config.document["login_id"]),
        "-max-downloads",
        str(config.document["max_downloads"]),
        *(["-qr"] if qr else ["-username", str(username)]),
    ]


def download_plan(config: EngineDownloadConfig) -> dict[str, Any]:
    return {
        "schema_version": "engine-download-plan-v1",
        "config_id": config.config_id,
        "qualification_config_id": config.qualification.config_id,
        "arguments_without_account_credentials": downloader_arguments(config, qr=True),
        "game_directory": str(config.game_directory),
        "max_wall_seconds": config.document["max_wall_seconds"],
        "owner_interactive_login_required": True,
        "manifest_availability_verified": False,
        "downloads_started": 0,
        "games_launched": 0,
        "training_allowed": False,
    }


def download_exact_game(config: EngineDownloadConfig, *, qr: bool = False) -> dict[str, Any]:
    if not sys.stdin.isatty():
        raise ValueError(
            "Start the download yourself in Terminal; interactive Steam login is required"
        )
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ValueError("This acquisition recipe requires macOS arm64")
    _ensure_private_path(config.game_directory, config.qualification.root)
    if config.game_directory.exists():
        for item in config.game_directory.rglob("*"):
            if item.is_symlink():
                raise ValueError(f"Refusing a symlink in existing download content: {item}")
    binary = prepare_downloader(config)
    _ensure_private_path(binary, config.qualification.root)
    config.work_directory.mkdir(parents=True, exist_ok=True)
    username = None if qr else input("Steam account name (login name, not display name): ").strip()
    arguments = downloader_arguments(config, username=username, qr=qr)
    print(
        "Downloading only the exact v0.111.0 beta manifest to a separate private directory.\n"
        "Sign in to DepotDownloader locally and approve Steam Guard if prompted.\n"
        f"There is a {config.document['max_wall_seconds'] // 60}-minute cap. Ctrl+C stops it; "
        "re-running validates and resumes this manifest.\n"
        "No game launch, archive freezing or training follows.",
        flush=True,
    )
    completed = subprocess.run(
        arguments,
        cwd=config.work_directory,
        timeout=config.document["max_wall_seconds"],
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(
            f"DepotDownloader exited with code {completed.returncode}; preserve the error above. "
            "Do not substitute another manifest or change Steam branches."
        )
    result = inspect_candidate(
        config.qualification, GameCandidate(config.game_directory, "licensed_depotdownloader", None)
    )
    return {
        "schema_version": "engine-download-result-v1",
        "config_id": config.config_id,
        "qualification_config_id": config.qualification.config_id,
        "status": "downloaded_identity_matches"
        if result["matches_target"]
        else "identity_mismatch",
        "game_directory": str(config.game_directory),
        "identity_check": result,
        "games_launched": 0,
        "training_allowed": False,
        "archive_created": False,
    }
