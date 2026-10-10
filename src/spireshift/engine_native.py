"""Bounded shipped-game bootstrap and private, static model-registry inspection.

Neither command admits a gameplay backend. No game rules are reimplemented here.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import time
from collections import Counter
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import (
    ARCHIVE_RECORD,
    GAME_RELATIVE,
    EngineQualificationConfig,
    _inventory,
    _sha_file,
    default_archive_path,
    inspect_engine_sources,
    verify_game_archive,
)
from spireshift.full_run_experience import atomic_json

MODEL_ROOT = "MegaCrit.Sts2.Core.Models."
EXE_RELATIVE = "SlayTheSpire2.app/Contents/MacOS/Slay the Spire 2"
DATA_RELATIVE = "SlayTheSpire2.app/Contents/Resources/data_sts2_macos_arm64"


def _private_path(root: Path, relative: str) -> Path:
    pieces = Path(relative).parts
    if not pieces or pieces[0] != "artifacts" or ".." in pieces or Path(relative).is_absolute():
        raise ValueError("Native qualification outputs/tools must be under private artifacts")
    path = root / relative
    _no_symlinks(path)
    return path


def _no_symlinks(path: Path) -> None:
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise ValueError(f"Native qualification paths cannot traverse symlinks: {path}")


@dataclass(frozen=True)
class NativeQualificationConfig:
    document: dict[str, Any]
    qualification: EngineQualificationConfig

    @property
    def config_id(self) -> str:
        return manifest_identifier(self.document)

    @property
    def workspace(self) -> Path:
        return _private_path(self.qualification.root, self.document["workspace"])


def load_native_qualification_config(
    path: Path, qualification: EngineQualificationConfig
) -> NativeQualificationConfig:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != "engine-native-config-v1":
        raise ValueError("Expected engine-native-config-v1")
    if value.get("qualification_config_id") != qualification.config_id:
        raise ValueError("Native checks belong to another exact-build configuration")
    if value.get("stage") != "bootstrap_and_static_registry_only":
        raise ValueError("Native checks do not implement gameplay or training")
    if (
        qualification.target["platform"] != "macos"
        or qualification.target["architecture"] != "arm64"
    ):
        raise ValueError("This native profile route is scoped to macOS arm64")
    _private_path(qualification.root, str(value.get("workspace", "")))
    if value.get("settings_schema") != 8:
        raise ValueError("The frozen bootstrap requires native settings schema 8")
    if type(value.get("max_wall_seconds")) is not int or not 1 <= value["max_wall_seconds"] <= 60:
        raise ValueError("Native boot needs a short wall-time cap, at most 60 seconds")
    if (
        type(value.get("quit_after_frames")) is not int
        or not 60 <= value["quit_after_frames"] <= 1200
    ):
        raise ValueError("Native boot needs a bounded engine-owned quit frame")
    tool = value.get("decompiler")
    if not isinstance(tool, dict) or tool.get("version") != "9.1.0.7988":
        raise ValueError("Expected the pinned local ILSpy decompiler")
    files = tool.get("files")
    if not isinstance(files, list) or len(files) != 3:
        raise ValueError("Decompiler launcher, command and implementation identities are required")
    if len({item.get("path") for item in files if isinstance(item, dict)}) != 3:
        raise ValueError("Decompiler identities must name three distinct files")
    for item in files:
        if not isinstance(item, dict) or not re.fullmatch(
            r"[0-9a-f]{64}", str(item.get("sha256", ""))
        ):
            raise ValueError("Invalid decompiler file fingerprint")
        _private_path(qualification.root, str(item.get("path", "")))
    executable = _private_path(qualification.root, str(tool.get("executable", "")))
    if str(executable.relative_to(qualification.root)) not in {item["path"] for item in files}:
        raise ValueError("Decompiler executable must have a pinned fingerprint")
    return NativeQualificationConfig(value, qualification)


def _verified_archive(config: NativeQualificationConfig) -> tuple[Path, dict[str, Any]]:
    archive = default_archive_path(config.qualification)
    _no_symlinks(archive)
    verified = verify_game_archive(config.qualification, archive)
    if not verified["valid"]:
        raise ValueError(
            "Exact frozen archive verification failed: " + "; ".join(verified["errors"])
        )
    sources = inspect_engine_sources(config.qualification)
    if not all(source["matches_target"] for source in sources):
        raise ValueError(
            "Pinned headless/CLI sources changed; preserve the drift before proceeding"
        )
    return archive, verified


def _attempt(config: NativeQualificationConfig, prefix: str) -> Path:
    config.workspace.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix=prefix, dir=config.workspace))
    atomic_json(
        attempt / "in-progress.json", {"config_id": config.config_id, "training_allowed": False}
    )
    return attempt


def _finish(attempt: Path, body: dict[str, Any]) -> dict[str, Any]:
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(attempt / "report.json", result)
    (attempt / "in-progress.json").unlink()
    return {**result, "report_path": str(attempt / "report.json")}


def _failure(attempt: Path, error: BaseException) -> None:
    atomic_json(
        attempt / "failure.json",
        {"error": f"{type(error).__name__}: {error}", "training_allowed": False},
    )


def _shared_snapshot(root: Path) -> dict[str, Any]:
    """Read-only file/content/permission/mtime sentinel; do not follow linked directories."""
    rows: dict[str, Any] = {}

    def visit(path: Path) -> None:
        info = path.lstat()
        row: dict[str, Any] = {
            "mode": info.st_mode,
            "bytes": info.st_size,
            "mtime_ns": info.st_mtime_ns,
        }
        if stat.S_ISLNK(info.st_mode):
            row["link"] = os.readlink(path)
        elif stat.S_ISDIR(info.st_mode):
            for child in sorted(path.iterdir()):
                visit(child)
        elif stat.S_ISREG(info.st_mode):
            row["sha256"] = _sha_file(path)
        else:
            raise ValueError("Cannot verify an unsupported entry in the shared save tree")
        rows[path.relative_to(root).as_posix()] = row

    if root.exists() or root.is_symlink():
        visit(root)
    return {"present": bool(rows), "entries": len(rows), "tree_id": manifest_identifier(rows)}


def _running_games() -> list[int]:
    names = {
        "slay the spire 2",
        "slaythespire2",
        "slaythespire2.exe",
        "sts2headless",
        "sts2headless.dll",
    }
    found = []
    for process in psutil.process_iter(["name", "cmdline"]):
        try:
            info = process.info
            arguments = info.get("cmdline") or []
            if str(info.get("name", "")).lower() in names or any(
                Path(arg).name.lower() in names for arg in arguments[:2]
            ):
                found.append(process.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return found


def _profile_override(name: str) -> str:
    # Godot reads override.cfg beside an exported binary before initializing user://.
    return (
        "[application]\nconfig/use_custom_user_dir=true\nconfig/use_custom_user_dir.macos=true\n"
        f"config/custom_user_dir_name={json.dumps(name)}\n"
        f"config/custom_user_dir_name.macos={json.dumps(name)}\n"
    )


def _sandbox(protected: list[Path]) -> str:
    return (
        "(version 1)\n(allow default)\n"
        + "".join(f"(deny file-write* (subpath {json.dumps(str(path))}))\n" for path in protected)
        + "(deny network*)\n"
    )


def _run_boot(command: list[str], cwd: Path, attempt: Path, cap: int) -> dict[str, Any]:
    environment = dict(os.environ)
    # The game's native switch disables Steam before platform/save initialization.
    # Do not replace HOME, USERPROFILE or other operating-system directory settings.
    environment.pop("SteamAppId", None)
    environment.pop("SteamGameId", None)
    started = time.monotonic()
    timed_out = False
    with (
        (attempt / "stdout.log").open("wb") as stdout,
        (attempt / "stderr.log").open("wb") as stderr,
    ):
        child = subprocess.Popen(
            command, cwd=cwd, env=environment, stdout=stdout, stderr=stderr, start_new_session=True
        )
        try:
            child.wait(timeout=cap)
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            if child.poll() is None:
                timed_out = True
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=5)
    return {
        "returncode": child.returncode,
        "timed_out": timed_out,
        "wall_seconds": time.monotonic() - started,
    }


def evaluate_native_boot(checks: dict[str, Any]) -> dict[str, Any]:
    required = (
        "settings_created",
        "settings_schema_matches",
        "profile_path_logged",
        "steam_disabled_observed",
        "shared_profile_unchanged",
        "working_game_unchanged",
        "archive_still_valid",
        "natural_exit",
    )
    errors = [name for name in required if checks.get(name) is not True]
    return {
        "status": "native_profile_bootstrap_pass"
        if not errors
        else "native_profile_bootstrap_incomplete",
        "errors": errors,
    }


def _require_native_launch_support() -> None:
    if platform.system() != "Darwin" or platform.machine().lower() != "arm64":
        raise ValueError("Shipped bootstrap is scoped to the current macOS arm64 host")
    if not Path("/usr/bin/sandbox-exec").is_file():
        raise ValueError("macOS shared-save write protection is unavailable")


def bootstrap_native_profile(config: NativeQualificationConfig) -> dict[str, Any]:
    _require_native_launch_support()
    if _running_games():
        raise ValueError("Close the existing STS2 game before starting the short bootstrap")
    archive, verified = _verified_archive(config)
    user_data = Path.home() / "Library/Application Support"
    shared = user_data / "SlayTheSpire2"
    profile_parent = user_data / "SpireShift/engine-profiles"
    _no_symlinks(profile_parent)
    before = _shared_snapshot(shared)
    attempt = _attempt(config, "native-boot-")
    try:
        archive_name = config.qualification.document["archive_name"]
        profile_name = f"SpireShift/engine-profiles/{archive_name}-{attempt.name}"
        profile = user_data / profile_name
        if profile.exists() or profile.is_symlink():
            raise FileExistsError("A native boot requires a fresh private profile")
        game = attempt / "game"
        record = json.loads((archive / ARCHIVE_RECORD).read_text(encoding="utf-8"))
        shutil.copytree(archive / GAME_RELATIVE, game, copy_function=shutil.copy2, symlinks=True)
        if _inventory(game) != record["inventory"]:
            raise ValueError("Working copy differs from the frozen game")
        executable = game / EXE_RELATIVE
        mode_before = stat.S_IMODE(executable.stat().st_mode)
        executable.chmod(mode_before | 0o111)
        override = executable.parent / "override.cfg"
        if override.exists():
            raise ValueError("Base game already contains an unqualified settings override")
        override.write_text(_profile_override(profile_name), encoding="utf-8")
        expected_working = _inventory(game)
        sandbox = attempt / "profile-isolation.sb"
        sandbox.write_text(
            _sandbox(
                [
                    shared,
                    user_data / "Godot/app_userdata/SlayTheSpire2",
                    archive.parent,
                    user_data / "Steam/steamapps",
                    user_data / "Steam/userdata",
                ]
            ),
            encoding="utf-8",
        )
        command = [
            "/usr/bin/sandbox-exec",
            "-f",
            str(sandbox),
            str(executable),
            "--headless",
            "--verbose",
            "--force-steam=off",
            "--clientId=1",
            "--max-fps",
            "60",
            "--quit-after",
            str(config.document["quit_after_frames"]),
            "--log-file",
            str(attempt / "godot.log"),
        ]
        process = _run_boot(
            command, executable.parent, attempt, config.document["max_wall_seconds"]
        )
        settings = profile / "default/1/settings.save"
        schema = None
        if settings.is_file():
            with suppress(ValueError, AttributeError):
                schema = json.loads(settings.read_text(encoding="utf-8")).get("schema_version")
        stdout = (attempt / "stdout.log").read_text(encoding="utf-8", errors="replace")
        stderr = (attempt / "stderr.log").read_text(encoding="utf-8", errors="replace")
        after = _shared_snapshot(shared)
        archive_after = verify_game_archive(config.qualification, archive)
        checks = {
            "settings_created": settings.is_file(),
            "settings_schema_matches": type(schema) is int
            and schema == config.document["settings_schema"],
            "profile_path_logged": f"User Data Directory: {profile}\n" in stdout,
            "steam_disabled_observed": "Steam initialization skipped" in stdout,
            "shared_profile_unchanged": before == after,
            "working_game_unchanged": _inventory(game) == expected_working,
            "archive_still_valid": archive_after["valid"],
            "natural_exit": process["returncode"] == 0 and not process["timed_out"],
        }
        return _finish(
            attempt,
            {
                "schema_version": "engine-native-bootstrap-v1",
                "config_id": config.config_id,
                "qualification_config_id": config.qualification.config_id,
                "archive_id": record["archive_id"],
                "archive_verification_before": verified["report_id"],
                "archive_verification_after": archive_after["report_id"],
                "verdict": evaluate_native_boot(checks),
                "checks": checks,
                "process": process,
                "command": command,
                "profile": str(profile),
                "settings_schema": schema,
                "shared_profile_sentinel": {"before": before, "after": after},
                "working_copy_changes": {
                    "executable_mode_before": mode_before,
                    "executable_mode_after": mode_before | 0o111,
                    "executable_content_sha256": _sha_file(executable),
                    "override_sha256": _sha_file(override),
                    "rules_or_asset_patches": 0,
                },
                "diagnostics": {
                    "error_lines": len(re.findall(r"^ERROR:", stderr, re.MULTILINE)),
                    "warning_lines": len(re.findall(r"^WARNING:", stderr, re.MULTILINE)),
                    "logs_preserved": True,
                },
                "games_launched": 1,
                "full_run_attempts": 0,
                "optimizer_steps": 0,
                "connector_control_verified": False,
                "mechanics_qualified": False,
                "training_allowed": False,
                "claim_scope": (
                    "shipped_native_boot_and_profile_isolation_only_"
                    "not_interactive_or_gameplay_parity"
                ),
            },
        )
    except BaseException as error:
        _failure(attempt, error)
        raise


def parse_model_registry(source: str, classes: str) -> list[dict[str, Any]]:
    """Fail closed on incomplete, duplicated or ambiguous generated subtype bindings."""
    fields = re.findall(r"private static readonly Type (_t[0-9]+) = typeof\(([\w.]+)\);", source)
    count = re.search(r"public static int Count => ([0-9]+);", source)
    array = re.search(r"Type\[\] _subtypes = new Type\[([0-9]+)\]\s*\{([^}]+)\};", source)
    if (
        count is None
        or array is None
        or "public static IReadOnlyList<Type> All => _subtypes;" not in source
    ):
        raise ValueError("Unsupported generated model registry shape")
    size = int(count[1])
    members = [item.strip() for item in array[2].split(",") if item.strip()]
    expected = [f"_t{index}" for index in range(size)]
    bindings = dict(fields)
    if (
        int(array[1]) != size
        or members != expected
        or len(fields) != size
        or list(bindings) != expected
    ):
        raise ValueError("Generated model registry count, order or coverage mismatch")
    definitions = {line[6:] for line in classes.splitlines() if line.startswith("Class ")}
    namespaces = re.findall(r"^using ([\w.]+);$", source, re.MULTILINE)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for member in members:
        name = bindings[member]
        possible = (
            {name} if "." in name else {f"{namespace}.{name}" for namespace in namespaces}
        ) & definitions
        if len(possible) != 1:
            raise ValueError(f"Unknown or ambiguous model registry binding: {name}")
        qualified = next(iter(possible))
        if qualified in seen or not qualified.startswith(MODEL_ROOT):
            raise ValueError("Duplicate or non-game model registry type")
        seen.add(qualified)
        suffix = qualified.removeprefix(MODEL_ROOT)
        rows.append(
            {
                "index": len(rows),
                "type": qualified,
                "family": suffix.split(".")[0],
                "nonplayable_name_hint": any(
                    part.startswith(("Mock", "Test", "Deprecated")) for part in suffix.split(".")
                ),
                "offered_in_normal_play": None,
            }
        )
    return rows


def inspect_model_registry(config: NativeQualificationConfig) -> dict[str, Any]:
    archive, verified = _verified_archive(config)
    tool = config.document["decompiler"]
    for item in tool["files"]:
        path = _private_path(config.qualification.root, item["path"])
        if _sha_file(path) != item["sha256"]:
            raise ValueError("Pinned decompiler changed; do not trust a stale source inventory")
    executable = _private_path(config.qualification.root, tool["executable"])
    assembly = archive / GAME_RELATIVE / DATA_RELATIVE / "sts2.dll"
    environment = {**os.environ, "DOTNET_ROLL_FORWARD": "Major"}
    attempt = _attempt(config, "model-registry-")
    try:

        def decompile(*arguments: str) -> str:
            result = subprocess.run(
                [str(executable), "--disable-updatecheck", *arguments],
                env=environment,
                text=True,
                capture_output=True,
                check=True,
                timeout=45,
            )
            return result.stdout

        version = decompile("--version")
        if (
            f"ilspycmd: {tool['version']}" not in version
            or f"ICSharpCode.Decompiler: {tool['version']}" not in version
        ):
            raise ValueError("Decompiler version does not match the pinned tool")
        classes = decompile("-l", "c", str(assembly))
        source = decompile("-t", MODEL_ROOT + "AbstractModelSubtypes", str(assembly))
        model_db = decompile("-t", MODEL_ROOT + "ModelDb", str(assembly))
        (attempt / "classes.txt").write_text(classes, encoding="utf-8")
        (attempt / "AbstractModelSubtypes.cs").write_text(source, encoding="utf-8")
        (attempt / "ModelDb.cs").write_text(model_db, encoding="utf-8")
        rows = parse_model_registry(source, classes)
        registry = {
            "schema_version": "engine-static-model-registry-v1",
            "config_id": config.config_id,
            "assembly_sha256": config.qualification.target["assembly_sha256"],
            "models": rows,
            "authority": (
                "shipped_AbstractModelSubtypes_All_generated_registry_not_live_ModelDb_All"
            ),
            "runtime_instantiation_verified": False,
            "offered_content_qualified": False,
            "training_input": False,
        }
        registry_id = manifest_identifier(registry)
        atomic_json(attempt / "model-registry.json", {**registry, "registry_id": registry_id})
        return _finish(
            attempt,
            {
                "schema_version": "engine-model-registry-inspection-v1",
                "config_id": config.config_id,
                "qualification_config_id": config.qualification.config_id,
                "archive_verification": verified["report_id"],
                "registry_id": registry_id,
                "models": len(rows),
                "family_counts": dict(sorted(Counter(row["family"] for row in rows).items())),
                "nonplayable_name_hints": sum(row["nonplayable_name_hint"] for row in rows),
                "unresolved_bindings": 0,
                "offered_in_normal_play": "unverified",
                "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                "model_db_source_sha256": hashlib.sha256(model_db.encode()).hexdigest(),
                "raw_inventory_path": str(attempt / "model-registry.json"),
                "raw_material_private": True,
                "games_launched": 0,
                "optimizer_steps": 0,
                "training_allowed": False,
                "claim_scope": (
                    "complete_generated_base_model_type_registry_only_"
                    "not_complete_mechanics_or_reachable_states"
                ),
            },
        )
    except BaseException as error:
        _failure(attempt, error)
        raise
