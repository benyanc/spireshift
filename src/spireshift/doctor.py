from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import struct
import subprocess
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

STS2_APP_ID = "2868840"
STS2_DIRECTORY_NAME = "Slay the Spire 2"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    name: str
    status: str
    detail: str


@dataclass(frozen=True, slots=True)
class GameCandidate:
    path: Path
    source: str
    app_manifest_path: Path | None


@dataclass(frozen=True, slots=True)
class InstallationLayout:
    executable: Path
    mods_directory: Path
    data_directory: Path
    release_info_path: Path
    runtime_config_path: Path
    assembly_path: Path


@dataclass(frozen=True, slots=True)
class GameInstallation:
    root: Path
    source: str
    platform: str
    architecture: str
    executable: Path
    mods_directory: Path
    data_directory: Path
    release_info_path: Path
    runtime_config_path: Path
    assembly_path: Path
    version: str
    commit: str
    branch: str | None
    release_date: str | None
    steam_build_id: str | None
    runtime_tfm: str
    runtime_frameworks: tuple[str, ...]
    release_main_assembly_hash: int | str | None
    runtime_main_assembly_hash: int
    assembly_sha256: str
    assembly_size_bytes: int

    def manifest(self) -> dict[str, object]:
        return {
            "schema_version": "game-installation-v1",
            "app_id": STS2_APP_ID,
            "source": self.source,
            "platform": self.platform,
            "architecture": self.architecture,
            "game": {
                "directory": str(self.root),
                "executable": str(self.executable),
                "mods_directory": str(self.mods_directory),
                "mods_directory_exists": self.mods_directory.is_dir(),
            },
            "release": {
                "manifest_path": str(self.release_info_path),
                "version": self.version,
                "commit": self.commit,
                "branch": self.branch,
                "date": self.release_date,
                "steam_build_id": self.steam_build_id,
            },
            "runtime": {
                "data_directory": str(self.data_directory),
                "config_path": str(self.runtime_config_path),
                "tfm": self.runtime_tfm,
                "frameworks": list(self.runtime_frameworks),
            },
            "assembly": {
                "path": str(self.assembly_path),
                "size_bytes": self.assembly_size_bytes,
                "sha256": self.assembly_sha256,
                "sha1_int32_little_endian": self.runtime_main_assembly_hash,
                "release_declared_main_assembly_hash": self.release_main_assembly_hash,
            },
        }


@dataclass(frozen=True, slots=True)
class InstallationProbe:
    candidate: GameCandidate
    installation: GameInstallation | None
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return self.installation is not None


class GameInstallationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = tuple(errors)


def collect_diagnostics() -> list[Diagnostic]:
    return [
        Diagnostic("platform", "ok", platform.platform()),
        _command_diagnostic("git", ["git", "--version"]),
        _command_diagnostic("github", ["gh", "auth", "status"]),
        _command_diagnostic("uv", ["uv", "--version"]),
        _command_diagnostic("dotnet", ["dotnet", "--version"]),
        _game_diagnostic(),
    ]


def diagnostics_as_dict() -> list[dict[str, str]]:
    return [asdict(item) for item in collect_diagnostics()]


def discover_game_candidates(
    *,
    home: Path | None = None,
    system: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> list[GameCandidate]:
    environment = os.environ if environ is None else environ
    configured = environment.get("SPIRESHIFT_GAME_DIR")
    if configured:
        path = Path(configured).expanduser()
        return [
            GameCandidate(
                path=path,
                source="environment:SPIRESHIFT_GAME_DIR",
                app_manifest_path=_infer_app_manifest(path),
            )
        ]

    current_home = Path.home() if home is None else home
    current_system = platform.system() if system is None else system
    candidates: list[GameCandidate] = []
    for steam_root in _steam_roots(current_home, current_system, environment):
        libraries = [steam_root]
        library_file = steam_root / "steamapps/libraryfolders.vdf"
        if library_file.is_file():
            with suppress(OSError):
                libraries.extend(
                    Path(item).expanduser()
                    for item in parse_steam_library_folders(library_file.read_text())
                )
        for library in libraries:
            app_manifest = library / f"steamapps/appmanifest_{STS2_APP_ID}.acf"
            candidates.append(
                GameCandidate(
                    path=library / f"steamapps/common/{STS2_DIRECTORY_NAME}",
                    source=f"steam:{steam_root}",
                    app_manifest_path=app_manifest,
                )
            )
    return _deduplicate_candidates(candidates)


def parse_steam_library_folders(content: str) -> list[str]:
    modern = re.findall(r'"path"\s+"([^"]+)"', content)
    legacy = re.findall(r'^\s*"\d+"\s+"([^"]+)"\s*$', content, flags=re.MULTILINE)
    return [item.replace(r"\\", "\\") for item in [*modern, *legacy]]


def probe_game_installations(
    *,
    home: Path | None = None,
    system: str | None = None,
    machine: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> list[InstallationProbe]:
    current_system = platform.system() if system is None else system
    current_machine = platform.machine() if machine is None else machine
    probes: list[InstallationProbe] = []
    for candidate in discover_game_candidates(
        home=home,
        system=current_system,
        environ=environ,
    ):
        try:
            installation = inspect_game_installation(
                candidate,
                system=current_system,
                machine=current_machine,
            )
        except GameInstallationError as error:
            probes.append(InstallationProbe(candidate, None, error.errors))
        else:
            probes.append(InstallationProbe(candidate, installation, ()))
    return probes


def find_game_installation(
    *,
    home: Path | None = None,
    system: str | None = None,
    machine: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> GameInstallation | None:
    for probe in probe_game_installations(
        home=home,
        system=system,
        machine=machine,
        environ=environ,
    ):
        if probe.installation is not None:
            return probe.installation
    return None


def find_game_path() -> Path | None:
    installation = find_game_installation()
    return installation.root if installation is not None else None


def inspect_game_installation(
    candidate: GameCandidate,
    *,
    system: str | None = None,
    machine: str | None = None,
) -> GameInstallation:
    current_system = platform.system() if system is None else system
    current_machine = platform.machine() if machine is None else machine
    platform_id = _platform_id(current_system)
    architecture = _architecture_id(current_machine)
    layout = _installation_layout(candidate.path, platform_id, architecture)

    errors: list[str] = []
    if not candidate.path.is_dir():
        errors.append("game directory is missing")
    _require_readable_file(layout.executable, "executable", errors)
    _require_readable_file(layout.release_info_path, "release_info.json", errors)
    _require_readable_file(layout.runtime_config_path, "sts2.runtimeconfig.json", errors)
    _require_readable_file(layout.assembly_path, "sts2.dll", errors)
    if errors:
        raise GameInstallationError(errors)

    release = _load_json_object(layout.release_info_path, "release_info.json", errors)
    runtime = _load_json_object(layout.runtime_config_path, "sts2.runtimeconfig.json", errors)
    version = _required_string(release, "version", "release_info.json", errors)
    commit = _required_string(release, "commit", "release_info.json", errors)
    runtime_options = _required_mapping(runtime, "runtimeOptions", "runtime config", errors)
    runtime_tfm = _required_string(runtime_options, "tfm", "runtime config", errors)
    if errors:
        raise GameInstallationError(errors)

    release_hash = release.get("main_assembly_hash")
    if not isinstance(release_hash, (int, str)):
        release_hash = None
    assembly_sha256, runtime_hash, assembly_size = _assembly_identity(layout.assembly_path)
    return GameInstallation(
        root=candidate.path.resolve(),
        source=candidate.source,
        platform=platform_id,
        architecture=architecture,
        executable=layout.executable.resolve(),
        mods_directory=layout.mods_directory.resolve(),
        data_directory=layout.data_directory.resolve(),
        release_info_path=layout.release_info_path.resolve(),
        runtime_config_path=layout.runtime_config_path.resolve(),
        assembly_path=layout.assembly_path.resolve(),
        version=version,
        commit=commit,
        branch=_optional_string(release.get("branch")),
        release_date=_optional_string(release.get("date")),
        steam_build_id=_read_steam_build_id(candidate.app_manifest_path),
        runtime_tfm=runtime_tfm,
        runtime_frameworks=_runtime_frameworks(runtime_options),
        release_main_assembly_hash=release_hash,
        runtime_main_assembly_hash=runtime_hash,
        assembly_sha256=assembly_sha256,
        assembly_size_bytes=assembly_size,
    )


def _game_diagnostic() -> Diagnostic:
    probes = probe_game_installations()
    installation = next((probe.installation for probe in probes if probe.valid), None)
    if installation is not None:
        build = (
            f", Steam build {installation.steam_build_id}"
            if installation.steam_build_id is not None
            else ""
        )
        return Diagnostic(
            "sts2",
            "ok",
            (
                f"{installation.version} ({installation.commit}){build}, "
                f"{installation.architecture}, {installation.root}"
            ),
        )

    relevant = [probe for probe in probes if probe.candidate.path.exists()]
    if not relevant:
        return Diagnostic(
            "sts2",
            "missing",
            "Set SPIRESHIFT_GAME_DIR or install app 2868840 through Steam",
        )
    detail = " | ".join(
        f"{probe.candidate.path}: {', '.join(probe.errors)}" for probe in relevant[:3]
    )
    return Diagnostic("sts2", "invalid", detail)


def _steam_roots(
    home: Path,
    system: str,
    environ: Mapping[str, str],
) -> list[Path]:
    system_id = _platform_id(system)
    if system_id == "macos":
        roots = [home / "Library/Application Support/Steam"]
    elif system_id == "linux":
        roots = [
            home / ".steam/steam",
            home / ".local/share/Steam",
            home / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
        ]
    else:
        roots = [
            Path(value)
            for value in (
                environ.get("STEAM_PATH"),
                _windows_steam_path(environ.get("PROGRAMFILES(X86)")),
                _windows_steam_path(environ.get("PROGRAMFILES")),
                r"C:\Program Files (x86)\Steam",
                r"C:\Program Files\Steam",
            )
            if value
        ]
    return list(dict.fromkeys(path.expanduser() for path in roots))


def _windows_steam_path(program_files: str | None) -> str | None:
    return str(Path(program_files) / "Steam") if program_files else None


def _infer_app_manifest(game_path: Path) -> Path | None:
    if game_path.parent.name != "common" or game_path.parent.parent.name != "steamapps":
        return None
    return game_path.parent.parent / f"appmanifest_{STS2_APP_ID}.acf"


def _deduplicate_candidates(candidates: list[GameCandidate]) -> list[GameCandidate]:
    unique: dict[str, GameCandidate] = {}
    for candidate in candidates:
        unique.setdefault(str(candidate.path.absolute()), candidate)
    return list(unique.values())


def _platform_id(system: str) -> str:
    normalized = system.casefold()
    if normalized in {"darwin", "macos"}:
        return "macos"
    if normalized in {"windows", "win32"}:
        return "windows"
    if normalized == "linux":
        return "linux"
    raise ValueError(f"Unsupported platform: {system}")


def _architecture_id(machine: str) -> str:
    normalized = machine.casefold()
    if normalized in {"arm64", "aarch64"}:
        return "arm64"
    if normalized in {"x86_64", "amd64", "x64"}:
        return "x86_64"
    raise ValueError(f"Unsupported architecture: {machine}")


def _installation_layout(root: Path, platform_id: str, architecture: str) -> InstallationLayout:
    if platform_id == "macos":
        contents = root / "SlayTheSpire2.app/Contents"
        data_directory = contents / f"Resources/data_sts2_macos_{architecture}"
        return InstallationLayout(
            executable=contents / "MacOS/Slay the Spire 2",
            mods_directory=contents / "MacOS/mods",
            data_directory=data_directory,
            release_info_path=contents / "Resources/release_info.json",
            runtime_config_path=data_directory / "sts2.runtimeconfig.json",
            assembly_path=data_directory / "sts2.dll",
        )
    if platform_id == "windows":
        data_directory = root / "data_sts2_windows_x86_64"
        return InstallationLayout(
            executable=root / "SlayTheSpire2.exe",
            mods_directory=root / "mods",
            data_directory=data_directory,
            release_info_path=root / "release_info.json",
            runtime_config_path=data_directory / "sts2.runtimeconfig.json",
            assembly_path=data_directory / "sts2.dll",
        )
    data_directory = root / "data_sts2_linuxbsd_x86_64"
    executable = next(
        (path for path in (root / "SlayTheSpire2", root / "Slay the Spire 2") if path.is_file()),
        root / "SlayTheSpire2",
    )
    return InstallationLayout(
        executable=executable,
        mods_directory=root / "mods",
        data_directory=data_directory,
        release_info_path=root / "release_info.json",
        runtime_config_path=data_directory / "sts2.runtimeconfig.json",
        assembly_path=data_directory / "sts2.dll",
    )


def _require_readable_file(path: Path, label: str, errors: list[str]) -> None:
    if not path.is_file():
        errors.append(f"{label} is missing at {path}")
        return
    try:
        with path.open("rb") as handle:
            handle.read(1)
    except OSError as error:
        errors.append(f"{label} is unreadable at {path}: {error}")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, object]:
    try:
        loaded: object = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"{label} is invalid: {error}")
        return {}
    if not isinstance(loaded, dict):
        errors.append(f"{label} must contain a JSON object")
        return {}
    return cast(dict[str, object], loaded)


def _required_mapping(
    value: Mapping[str, object],
    key: str,
    label: str,
    errors: list[str],
) -> dict[str, object]:
    result = value.get(key)
    if not isinstance(result, dict):
        errors.append(f"{label} is missing object field {key}")
        return {}
    return cast(dict[str, object], result)


def _required_string(
    value: Mapping[str, object],
    key: str,
    label: str,
    errors: list[str],
) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        errors.append(f"{label} is missing string field {key}")
        return ""
    return result


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _runtime_frameworks(runtime_options: Mapping[str, object]) -> tuple[str, ...]:
    raw_frameworks = runtime_options.get("includedFrameworks", [])
    if not isinstance(raw_frameworks, list):
        return ()
    frameworks: list[str] = []
    for raw in raw_frameworks:
        if not isinstance(raw, dict):
            continue
        name = raw.get("name")
        version = raw.get("version")
        if isinstance(name, str) and isinstance(version, str):
            frameworks.append(f"{name}/{version}")
    return tuple(frameworks)


def _assembly_identity(path: Path) -> tuple[str, int, int]:
    sha256 = hashlib.sha256()
    sha1 = hashlib.sha1()  # noqa: S324 - used only as a non-cryptographic game build identifier.
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha256.update(chunk)
            sha1.update(chunk)
            size += len(chunk)
    runtime_hash = struct.unpack("<i", sha1.digest()[:4])[0]
    return sha256.hexdigest(), runtime_hash, size


def _read_steam_build_id(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    try:
        content = path.read_text()
    except OSError:
        return None
    match = re.search(r'"buildid"\s+"([^"]+)"', content)
    return match.group(1) if match else None


def _command_diagnostic(name: str, command: list[str]) -> Diagnostic:
    if shutil.which(command[0]) is None:
        return Diagnostic(name, "missing", f"{command[0]} not found")
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    output = (completed.stdout or completed.stderr).strip().splitlines()
    detail = output[0] if output else f"exit {completed.returncode}"
    return Diagnostic(name, "ok" if completed.returncode == 0 else "error", detail)
