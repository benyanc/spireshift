"""Pinned, disposable Connector menu check against the shipped game.

This is transport/control qualification, never gameplay or training admission.
The released Host owns all public projection, legality and action execution.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import signal
import socket
import stat
import subprocess
import tarfile
import tempfile
import time
import urllib.request
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_native import (
    EXE_RELATIVE,
    NativeQualificationConfig,
    _failure,
    _finish,
    _no_symlinks,
    _private_path,
    _profile_override,
    _require_native_launch_support,
    _running_games,
    _shared_snapshot,
    _verified_archive,
    load_native_qualification_config,
)
from spireshift.engine_qualification import (
    ARCHIVE_RECORD,
    GAME_RELATIVE,
    EngineQualificationConfig,
    _inventory,
    _sha_file,
    verify_game_archive,
)
from spireshift.full_run_experience import atomic_json


@dataclass(frozen=True)
class ConnectorQualificationConfig:
    document: dict[str, Any]
    native: NativeQualificationConfig

    @property
    def qualification(self) -> EngineQualificationConfig:
        return self.native.qualification

    @property
    def config_id(self) -> str:
        return manifest_identifier(self.document)

    def private(self, field: str) -> Path:
        return _private_path(self.qualification.root, self.document[field])


def load_connector_qualification_config(
    path: Path, qualification: EngineQualificationConfig
) -> ConnectorQualificationConfig:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != "engine-connector-config-v1":
        raise ValueError("Expected engine-connector-config-v1")
    if value.get("qualification_config_id") != qualification.config_id:
        raise ValueError("Connector check belongs to another frozen game")
    if (
        value.get("stage") != "shipped_menu_control_only"
        or value.get("training_allowed") is not False
    ):
        raise ValueError("Connector menu checks do not admit gameplay or training")
    native_path = qualification.root / str(value.get("native_config", ""))
    if native_path.resolve() != path.parent.resolve() / native_path.name:
        raise ValueError("Native prerequisite configuration must be beside this configuration")
    native = load_native_qualification_config(native_path, qualification)
    config = ConnectorQualificationConfig(value, native)
    for field in ("workspace", "toolchain", "bootstrap_report"):
        config.private(field)
    for field in ("bootstrap_report_id", "bootstrap_settings_sha256"):
        prefix = "sha256:" if field == "bootstrap_report_id" else ""
        if not re.fullmatch(prefix + r"[0-9a-f]{64}", str(value.get(field, ""))):
            raise ValueError("Exact native bootstrap evidence is required")
    if type(value.get("max_wall_seconds")) is not int or not 30 <= value["max_wall_seconds"] <= 120:
        raise ValueError("Connector check requires a short native-process cap, at most 120 seconds")
    connector = value.get("connector", {})
    if not isinstance(connector, dict) or connector.get("protocol") != "1.0.0":
        raise ValueError("Expected the pinned Player Environment protocol")
    for field, size in (("source_revision", 40), ("artifact_sha256", 64)):
        if not re.fullmatch(r"[0-9a-f]{" + str(size) + "}", str(connector.get(field, ""))):
            raise ValueError("Exact Connector source/artifact identity is required")
    assets = value.get("assets")
    if not isinstance(assets, dict) or set(assets) != {"host", "sdk", "zod", "seal"}:
        raise ValueError("Pinned Host, SDK, validator dependency and runtime seal are required")
    for asset in assets.values():
        if not isinstance(asset, dict) or not re.fullmatch(
            r"[0-9a-f]{64}", str(asset.get("sha256", ""))
        ):
            raise ValueError("Invalid Connector asset fingerprint")
        if not str(asset.get("url", "")).startswith("https://"):
            raise ValueError("Connector release downloads require HTTPS")
    return config


def _extract(archive: Path, destination: Path, *, strip_package: bool = False) -> None:
    """No links, special entries, absolute paths or traversal; no lifecycle scripts."""
    with tarfile.open(archive) as bundle:
        entries = bundle.getmembers()
        if sum(item.size for item in entries) > 32_000_000:
            raise ValueError("Connector extraction exceeds the size cap")
        for item in entries:
            parts = Path(item.name).parts
            if (
                not (item.isfile() or item.isdir())
                or Path(item.name).is_absolute()
                or ".." in parts
                or (strip_package and (not parts or parts[0] != "package"))
            ):
                raise ValueError("Unsafe Connector archive entry")
        if destination.exists():
            raise FileExistsError("Refusing to reuse an unverified extracted tool tree")
        destination.mkdir(parents=True)
        for item in entries:
            parts = Path(item.name).parts
            if strip_package:
                parts = parts[1:]
            if not parts:
                continue
            target = destination.joinpath(*parts)
            if item.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            stream = bundle.extractfile(item)
            if stream is None:
                raise ValueError("Missing release archive entry")
            with stream, target.open("xb") as output:
                shutil.copyfileobj(stream, output)
            target.chmod(item.mode & 0o777)


def prepare_connector_toolchain(config: ConnectorQualificationConfig) -> dict[str, Any]:
    """A bounded pinned download/install, with no npm lifecycle execution or game launch."""
    _verified_archive(config.native)
    root = config.private("toolchain")
    if (root / "toolchain.json").is_file():
        return _verify_toolchain(config)
    if root.exists():
        raise FileExistsError("Partial toolchain preserved; use a new private toolchain directory")
    root.mkdir(parents=True)
    try:
        downloaded = {}
        for name, asset in config.document["assets"].items():
            with urllib.request.urlopen(asset["url"], timeout=15) as response:
                body = response.read(32_000_001)
            if len(body) > 32_000_000 or hashlib.sha256(body).hexdigest() != asset["sha256"]:
                raise ValueError(f"Connector {name} download fails size/identity verification")
            destination = root / f"{name}.download"
            destination.write_bytes(body)
            downloaded[name] = asset["sha256"]
        _extract(root / "host.download", root / "release")
        _extract(
            root / "sdk.download",
            root / "node_modules/@rsgcsg/sts2-connector-client",
            strip_package=True,
        )
        _extract(root / "zod.download", root / "node_modules/zod", strip_package=True)
        identity = json.loads((root / "release/payload/build-identity.json").read_text())
        seal = json.loads((root / "seal.download").read_text())
        expected = config.document["connector"]
        if (
            any(
                identity.get(field) != expected[field]
                for field in ("artifact_sha256", "source_revision", "artifact_mvid")
            )
            or _sha_file(root / "release/payload/STS2_MCP.dll") != expected["artifact_sha256"]
        ):
            raise ValueError("Released Connector payload identity mismatch")
        if (
            seal.get("host_artifact", {}).get("sha256") != expected["artifact_sha256"]
            or seal.get("source_revision") != expected["source_revision"]
            or seal.get("game", {}).get("main_assembly_sha256")
            != config.qualification.target["assembly_sha256"]
        ):
            raise ValueError("Runtime seal does not bind this artifact and actual game")
        result = {
            "schema_version": "engine-connector-toolchain-v1",
            "config_id": config.config_id,
            "assets": downloaded,
            "inventory": _inventory(root),
            "games_launched": 0,
            "lifecycle_scripts_executed": 0,
            "training_allowed": False,
        }
        result["report_id"] = manifest_identifier(result)
        atomic_json(root / "toolchain.json", result)
        return result
    except BaseException as error:
        _failure(root, error)
        raise


def _verify_toolchain(config: ConnectorQualificationConfig) -> dict[str, Any]:
    root = config.private("toolchain")
    report: dict[str, Any] = json.loads((root / "toolchain.json").read_text())
    body = {key: value for key, value in report.items() if key != "report_id"}
    current = [item for item in _inventory(root) if item["path"] != "toolchain.json"]
    if (
        report.get("config_id") != config.config_id
        or manifest_identifier(body) != report.get("report_id")
        or current != report.get("inventory")
    ):
        raise ValueError("Connector tools changed; preserve drift before any game launch")
    return report


def _settings_template(config: ConnectorQualificationConfig) -> tuple[Path, dict[str, Any]]:
    report = json.loads(config.private("bootstrap_report").read_text())
    body = {key: value for key, value in report.items() if key not in {"report_id", "report_path"}}
    if (
        manifest_identifier(body) != report.get("report_id")
        or report.get("report_id") != config.document["bootstrap_report_id"]
        or report.get("config_id") != config.native.config_id
        or report.get("verdict", {}).get("status") != "native_profile_bootstrap_pass"
        or not all(item is True for item in report.get("checks", {}).values())
    ):
        raise ValueError("Native settings template lacks the exact passed bootstrap evidence")
    parent = Path.home() / "Library/Application Support/SpireShift/engine-profiles"
    settings = Path(report["profile"]) / "default/1/settings.save"
    if not settings.is_relative_to(parent):
        raise ValueError("Settings template must belong to the verified private native profile")
    _no_symlinks(settings)
    if _sha_file(settings) != config.document["bootstrap_settings_sha256"]:
        raise ValueError("Native settings template changed")
    return settings, report


def _enable_mod_settings(settings: Path, schema: int) -> dict[str, Any]:
    original = json.loads(settings.read_text())
    if original.get("schema_version") != schema:
        raise ValueError("Native mod-consent settings schema changed")
    mod_settings = original.get("mod_settings")
    if mod_settings is not None and not isinstance(mod_settings, dict):
        raise ValueError("Native mod_settings shape changed")
    backup = settings.with_name("settings.save.before-connector-consent")
    shutil.copy2(settings, backup)
    updated = {
        **original,
        "mod_settings": {**(mod_settings or {}), "mods_enabled": True},
        "seen_ea_disclaimer": True,
    }
    settings.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
    return {"before_sha256": _sha_file(backup), "after_sha256": _sha_file(settings)}


def connector_sandbox(protected: list[Path], port: int) -> str:
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Connector requires an exact local port")
    return (
        "(version 1)\n(allow default)\n"
        + "".join(f"(deny file-write* (subpath {json.dumps(str(path))}))\n" for path in protected)
        + "(deny network*)\n"
        + f'(allow network-inbound network-bind (local tcp "localhost:{port}"))\n'
        + '(allow network-outbound (remote tcp "localhost:*"))\n'
    )


def _available_port() -> int:
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        return int(reservation.getsockname()[1])


def _stop_child(child: subprocess.Popen[bytes]) -> None:
    # These children own a new process group. A tool may exit while its compiler
    # workers remain, so clean the group even when its original leader has exited.
    with suppress(ProcessLookupError):
        os.killpg(child.pid, signal.SIGTERM)
    if child.poll() is None:
        with suppress(subprocess.TimeoutExpired):
            child.wait(timeout=5)
    with suppress(ProcessLookupError):
        os.killpg(child.pid, signal.SIGKILL)
    child.wait(timeout=5)


def _run_menu_probe(
    config: ConnectorQualificationConfig, node: Path, attempt: Path, executable: Path, port: int
) -> dict[str, Any]:
    """Native lifecycle in Python; strict official SDK in the short Node client.

    The control secret exists only in the child's environment and the client's stdin.
    Neither command lines, descriptor files, logs nor evidence contain it.
    """
    token = secrets.token_hex(32)
    environment = dict(os.environ)
    for key in list(environment):
        if key.startswith("STS2_CONNECTOR_"):
            environment.pop(key)
    for key in ("SteamAppId", "SteamGameId", "STS2_CONNECTOR_EXPERIMENTAL_GAME_ID"):
        environment.pop(key, None)
    environment.update(
        {
            "STS2_CONNECTOR_PORT": str(port),
            "STS2_CONNECTOR_HOST_CONTROL_TOKEN": token,
            "STS2_CONNECTOR_EXPERIMENTAL_SOURCE_REVISION": config.document["connector"][
                "source_revision"
            ],
        }
    )
    command = [
        "/usr/bin/sandbox-exec",
        "-f",
        str(attempt / "profile-isolation.sb"),
        str(executable),
        "--headless",
        "--verbose",
        "--force-steam=off",
        "--clientId=1",
        "--max-fps",
        "60",
        "--log-file",
        str(attempt / "godot.log"),
    ]
    cap = config.document["max_wall_seconds"]
    started = time.monotonic()
    timed_out = False
    with (
        (attempt / "stdout.log").open("wb") as stdout,
        (attempt / "stderr.log").open("wb") as stderr,
    ):
        child = subprocess.Popen(
            command,
            cwd=executable.parent,
            env=environment,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
        try:
            spec = {
                "toolchain": str(config.private("toolchain")),
                "attempt": str(attempt),
                "expected_pid": child.pid,
                "endpoint": f"http://127.0.0.1:{port}",
                "host_control_token": token,
                "target": config.qualification.target,
                "connector": config.document["connector"],
                "max_wall_seconds": cap - 15,
            }
            client = subprocess.run(
                [str(node), str(config.qualification.root / "scripts/engine-menu-probe.mjs")],
                input=json.dumps(spec),
                text=True,
                capture_output=True,
                timeout=cap - 10,
                check=False,
            )
            (attempt / "client-stdout.log").write_text(client.stdout)
            (attempt / "client-stderr.log").write_text(client.stderr)
            child.wait(timeout=max(0.1, cap - (time.monotonic() - started)))
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            forced = child.poll() is None
            _stop_child(child)
    result_path = attempt / "menu-control.json"
    probe = (
        json.loads(result_path.read_text())
        if result_path.is_file()
        else {"error": "no_probe_result"}
    )
    return {
        "command": command,
        "pid": child.pid,
        "returncode": child.returncode,
        "timed_out": timed_out,
        "forced_cleanup": forced,
        "wall_seconds": time.monotonic() - started,
        "probe": probe,
    }


def evaluate_connector_menu(checks: dict[str, Any]) -> dict[str, Any]:
    required = (
        "loaded_identity",
        "endpoint_owned_by_child",
        "complete_public_menu",
        "completed_menu_transition",
        "duplicate_idempotent",
        "stale_rejected",
        "profile_path_logged",
        "steam_disabled_observed",
        "shared_profile_unchanged",
        "working_game_unchanged",
        "archive_still_valid",
        "template_unchanged",
        "natural_shutdown",
    )
    errors = [name for name in required if checks.get(name) is not True]
    return {
        "status": "shipped_connector_menu_pass"
        if not errors
        else "shipped_connector_menu_incomplete",
        "errors": errors,
    }


def probe_connector_menu(config: ConnectorQualificationConfig, *, node: Path) -> dict[str, Any]:
    _require_native_launch_support()
    if _running_games():
        raise ValueError("Close the existing STS2 game before the short Connector check")
    if not node.is_file():
        raise ValueError("Pass the local Node runtime explicitly with --node")
    archive, verified = _verified_archive(config.native)
    toolchain = _verify_toolchain(config)
    template, template_report = _settings_template(config)
    user_data = Path.home() / "Library/Application Support"
    shared = user_data / "SlayTheSpire2"
    before = _shared_snapshot(shared)
    workspace = config.private("workspace")
    workspace.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix="menu-", dir=workspace))
    atomic_json(
        attempt / "in-progress.json", {"config_id": config.config_id, "training_allowed": False}
    )
    try:
        record = json.loads((archive / ARCHIVE_RECORD).read_text())
        game = attempt / "game"
        shutil.copytree(archive / GAME_RELATIVE, game, copy_function=shutil.copy2, symlinks=True)
        if _inventory(game) != record["inventory"]:
            raise ValueError("Connector working copy differs from the frozen game")
        executable = game / EXE_RELATIVE
        mode = stat.S_IMODE(executable.stat().st_mode)
        executable.chmod(mode | 0o111)
        archive_name = config.qualification.document["archive_name"]
        profile_name = f"SpireShift/engine-profiles/{archive_name}-{attempt.name}"
        profile = user_data / profile_name
        _no_symlinks(profile)
        # Fresh settings-only profile, no copied progress/unlocks/saves.
        profile.mkdir(parents=True)
        settings = profile / "default/1/settings.save"
        settings.parent.mkdir(parents=True)
        shutil.copy2(template, settings)
        consent = _enable_mod_settings(settings, config.native.document["settings_schema"])
        override = executable.parent / "override.cfg"
        override.write_text(_profile_override(profile_name), encoding="utf-8")
        installation = subprocess.run(
            [
                str(node),
                str(config.qualification.root / "scripts/engine-menu-probe.mjs"),
                "--install",
            ],
            input=json.dumps(
                {
                    "toolchain": str(config.private("toolchain")),
                    "game": str(game),
                    "attempt": str(attempt),
                }
            ),
            text=True,
            capture_output=True,
            timeout=15,
            check=True,
        )
        atomic_json(attempt / "installation.json", json.loads(installation.stdout))
        # The Host normally creates this exact settings file on its first boot.
        # Declare it before the integrity baseline; do not ignore arbitrary new files.
        host_settings = executable.parent / "mods/STS2_MCP.conf"
        if host_settings.exists():
            raise ValueError(
                "Disposable Connector copy unexpectedly contains existing Host settings"
            )
        host_settings.write_text(
            '{\n  "port": 15526,\n  "player_environment_native_page_evidence_enabled": false\n}',
            encoding="utf-8",
        )
        expected_working = _inventory(game)
        port = _available_port()
        (attempt / "profile-isolation.sb").write_text(
            connector_sandbox(
                [
                    shared,
                    user_data / "Godot/app_userdata/SlayTheSpire2",
                    archive.parent,
                    user_data / "Steam/steamapps",
                    user_data / "Steam/userdata",
                ],
                port,
            ),
            encoding="utf-8",
        )
        # Compile the local protection policy before starting an actual game process.
        subprocess.run(
            ["/usr/bin/sandbox-exec", "-f", str(attempt / "profile-isolation.sb"), "/usr/bin/true"],
            timeout=5,
            capture_output=True,
            check=True,
        )
        process = _run_menu_probe(config, node, attempt, executable, port)
        stdout = (attempt / "stdout.log").read_text(errors="replace")
        stderr = (attempt / "stderr.log").read_text(errors="replace")
        after = _shared_snapshot(shared)
        archive_after = verify_game_archive(config.qualification, archive)
        probe = process.pop("probe")
        checks = {
            **probe.get("checks", {}),
            "profile_path_logged": f"User Data Directory: {profile}\n" in stdout,
            "steam_disabled_observed": "Steam initialization skipped" in stdout,
            "shared_profile_unchanged": before == after,
            "working_game_unchanged": _inventory(game) == expected_working,
            "archive_still_valid": archive_after["valid"],
            "template_unchanged": _sha_file(template)
            == config.document["bootstrap_settings_sha256"],
            "natural_shutdown": process["returncode"] == 0
            and not process["forced_cleanup"]
            and not process["timed_out"]
            and probe.get("shutdown_requested") is True,
        }
        return _finish(
            attempt,
            {
                "schema_version": "engine-connector-menu-v1",
                "config_id": config.config_id,
                "qualification_config_id": config.qualification.config_id,
                "archive_id": record["archive_id"],
                "archive_verification_before": verified["report_id"],
                "archive_verification_after": archive_after["report_id"],
                "toolchain_report_id": toolchain["report_id"],
                "bootstrap_report_id": template_report["report_id"],
                "verdict": evaluate_connector_menu(checks),
                "checks": checks,
                "process": process,
                "probe": probe,
                "profile": str(profile),
                "profile_settings_consent": consent,
                "shared_profile_sentinel": {"before": before, "after": after},
                "working_inventory_id": manifest_identifier(expected_working),
                "diagnostics": {
                    "error_lines": len(re.findall(r"^ERROR:", stderr, re.MULTILINE)),
                    "warning_lines": len(re.findall(r"^WARNING:", stderr, re.MULTILINE)),
                    "logs_preserved": True,
                },
                "authority": "exact_process_local_source_canary",
                "launcher_invocations": 1,
                "games_launched": int("MegaDot" in stdout),
                "menu_actions_requested": probe.get("menu_actions_requested", 0),
                "full_run_attempts": 0,
                "optimizer_steps": 0,
                "mechanics_qualified": False,
                "training_allowed": False,
                "claim_scope": "shipped_public_menu_transition_and_control_only",
            },
        )
    except BaseException as error:
        _failure(attempt, error)
        raise
