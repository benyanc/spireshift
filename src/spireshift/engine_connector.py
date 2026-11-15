"""Pinned, disposable Connector menu check against the shipped game.

This is transport/control qualification, never gameplay or training admission.
The released Host owns all public projection, legality and action execution.
"""

from __future__ import annotations

import ctypes
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
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
from contextlib import ExitStack, suppress
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
from spireshift.engine_working_app import WorkingAppPolicy, lease_working_app
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
    if not isinstance(value, dict) or value.get("schema_version") not in {
        "engine-connector-config-v1",
        "engine-connector-config-v2",
    }:
        raise ValueError("Expected a versioned pinned Connector configuration")
    if value.get("qualification_config_id") != qualification.config_id:
        raise ValueError("Connector check belongs to another frozen game")
    if (
        value.get("stage")
        != (
            "local_shipped_menu_control_only"
            if value["schema_version"] == "engine-connector-config-v2"
            else "shipped_menu_control_only"
        )
        or value.get("training_allowed") is not False
    ):
        raise ValueError("Connector menu checks do not admit gameplay or training")
    native_path = qualification.root / str(value.get("native_config", ""))
    if native_path.resolve() != path.parent.resolve() / native_path.name:
        raise ValueError("Native prerequisite configuration must be beside this configuration")
    native = load_native_qualification_config(native_path, qualification)
    config = ConnectorQualificationConfig(value, native)
    if value["schema_version"] == "engine-connector-config-v2":
        local = value.get("local_build", {})
        if (
            not isinstance(local, dict)
            or set(local) != {"build_config", "build_config_id", "build_report"}
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(local.get("build_config_id", "")))
        ):
            raise ValueError("Local Connector requires its separate pinned build recipe")
        recipe_path = qualification.root / local["build_config"]
        if recipe_path.resolve().parent != path.resolve().parent:
            raise ValueError("The local Host recipe must stay beside its Connector configuration")
        _private_path(qualification.root, local["build_report"])
    elif "local_build" in value:
        raise ValueError("A local Host cannot inherit an upstream release identity")
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
    if "local_build" in config.document:
        raise ValueError(
            "Run the pinned local Host build recipe; do not install the original release"
        )
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
    if "local_build" in config.document:
        local = config.document["local_build"]
        recipe = json.loads((config.qualification.root / local["build_config"]).read_text())
        built = json.loads(
            _private_path(config.qualification.root, local["build_report"]).read_text()
        )
        identity = config.document["connector"]
        if (
            manifest_identifier(recipe) != local["build_config_id"]
            or manifest_identifier(
                {k: v for k, v in built.items() if k not in {"report_id", "report_path"}}
            )
            != built.get("report_id")
            or report.get("local_build_report_id") != built.get("report_id")
            or report.get("local_build_report") != local["build_report"]
            or built.get("config_id") != local["build_config_id"]
            or built.get("qualification_config_id") != config.qualification.config_id
            or built.get("status") != "local_connector_built_unqualified"
            or built.get("source_revision") != identity["source_revision"]
            or built.get("patch_sha256") != _sha_file(config.qualification.root / recipe["patch"])
            or len(built.get("fresh_builds", [])) != 2
            or any(
                row.get("sha256") != identity["artifact_sha256"]
                or row.get("module_version_id") != identity["artifact_mvid"]
                for row in built["fresh_builds"]
            )
            or _sha_file(root / "release/payload/STS2_MCP.dll") != identity["artifact_sha256"]
            or (root / "seal.download").exists()
        ):
            raise ValueError("Local Host is not bound to its reproducible, unsealed build identity")
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


def _run_natural_client(
    command: list[str], spec: dict[str, Any], attempt: Path, timeout: int
) -> None:
    """Show bounded numeric progress; keep all other client output private."""
    with (
        (attempt / "client-stdout.log").open("wb") as log,
        (attempt / "client-stderr.log").open("wb") as errors,
    ):
        client = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=errors,
            start_new_session=True,
        )
        assert client.stdin is not None and client.stdout is not None
        output = client.stdout

        def relay() -> None:
            for line in output:
                log.write(line)
                log.flush()
                if re.fullmatch(
                    rb"Natural A8 run: [0-9]{1,4} actions, floor [0-9]{1,3}, act [1-3]\.\n", line
                ):
                    print(line.decode(), end="", flush=True)

        reader = threading.Thread(target=relay, daemon=True)
        reader.start()
        try:
            client.stdin.write(json.dumps(spec).encode())
            client.stdin.close()
            client.wait(timeout=timeout)
        finally:
            _stop_child(client)
            reader.join(timeout=5)
            output.close()


def _run_menu_probe(
    config: ConnectorQualificationConfig,
    node: Path,
    attempt: Path,
    executable: Path,
    port: int,
    *,
    fixture: dict[str, Any] | None = None,
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
    if fixture is not None and fixture.get("comparison_mode") == "new_run_v1":
        environment["STS2_CONNECTOR_RUN_SEED"] = fixture["seed"]
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
    cap = (
        fixture["natural_run_limits"]["max_wall_seconds"]
        if fixture is not None and "natural_run_limits" in fixture
        else config.document["max_wall_seconds"]
    )
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
            if fixture is not None:
                spec["fixture"] = fixture
            helper = (
                "engine-natural-shipped-run-v4.mjs"
                if fixture is not None
                and fixture.get("natural_run") is True
                and fixture.get("shipped_ui_revision") == "natural_v4"
                else "engine-natural-shipped-run-v3.mjs"
                if fixture is not None
                and fixture.get("natural_run") is True
                and fixture.get("shipped_ui_revision") == "natural_v3"
                else "engine-natural-shipped-run-v2.mjs"
                if fixture is not None
                and fixture.get("natural_run") is True
                and fixture.get("shipped_ui_revision") == "natural_v2"
                else "engine-natural-shipped-run-v1.mjs"
                if fixture is not None and fixture.get("natural_run") is True
                else "engine-new-run-shipped-probe-v1.mjs"
                if fixture is not None and fixture.get("comparison_mode") == "new_run_v1"
                else "engine-progression-shipped-probe-v1.mjs"
                if fixture is not None and fixture.get("comparison_mode") == "progression_v1"
                else "engine-progression-shipped-probe-v2.mjs"
                if fixture is not None and fixture.get("comparison_mode") == "progression_v2"
                else "engine-progression-shipped-probe-v3.mjs"
                if fixture is not None and fixture.get("comparison_mode") == "progression_v3"
                else "engine-progression-shipped-probe-v4.mjs"
                if fixture is not None and fixture.get("comparison_mode") == "progression_v4"
                else "engine-progression-shipped-probe-v5.mjs"
                if fixture is not None and fixture.get("comparison_mode") == "progression_v5"
                else "engine-combat-shipped-probe-v5.mjs"
                if fixture is not None and fixture.get("comparison_mode") == "combat_bridge_v5"
                else "engine-combat-shipped-probe-v4.mjs"
                if fixture is not None and fixture.get("comparison_mode") == "combat_bridge_v4"
                else "engine-profile-shipped-probe-v1.mjs"
                if fixture is not None and fixture.get("comparison_mode") == "profile_text_v1"
                else "engine-reward-shipped-probe-v3.mjs"
                if fixture is not None and fixture.get("comparison_mode") == "reward_bridge_v3"
                else "engine-reward-shipped-probe-v2.mjs"
                if fixture is not None and fixture.get("comparison_mode") == "reward_bridge_v2"
                else "engine-reward-shipped-probe-v1.mjs"
                if fixture is not None
                and fixture.get("comparison_mode")
                in {"reward_bridge_v1", "reward_bridge_v2", "reward_bridge_v3"}
                else "engine-bundle-shipped-probe-v3.mjs"
                if fixture is not None and fixture.get("comparison_mode") == "bundle_bridge_v3"
                else "engine-bundle-shipped-probe-v2.mjs"
                if fixture is not None and fixture.get("comparison_mode") == "bundle_bridge_v2"
                else "engine-bundle-shipped-probe-v1.mjs"
                if fixture is not None and fixture.get("comparison_mode") == "bundle_bridge_v1"
                else "engine-shop-shipped-probe-v1.mjs"
                if fixture is not None and fixture.get("comparison_mode") == "shop_bridge_v1"
                else "engine-rest-shipped-probe-v2.mjs"
                if fixture is not None and fixture.get("comparison_mode") == "rest_bridge_v2"
                else "engine-rest-shipped-probe.mjs"
                if fixture is not None and fixture.get("comparison_mode") == "rest_bridge_v1"
                else "engine-journey-shipped-probe-v4.mjs"
                if fixture is not None and fixture.get("shipped_ui_revision") == "tutorial_v4"
                else "engine-journey-shipped-probe-v3.mjs"
                if fixture is not None and fixture.get("shipped_ui_revision") == "tutorial_v3"
                else "engine-journey-shipped-probe-v2.mjs"
                if fixture is not None and fixture.get("comparison_mode") == "journey_v2"
                else "engine-journey-shipped-probe.mjs"
                if fixture is not None and fixture.get("comparison_mode") == "journey_v1"
                else "engine-checkpoint-shipped-probe.mjs"
                if fixture is not None
                else "engine-menu-probe.mjs"
            )
            client_command = [str(node), str(config.qualification.root / "scripts" / helper)]
            if fixture is not None and fixture.get("shipped_ui_revision") in {
                "natural_v3",
                "natural_v4",
            }:
                _run_natural_client(client_command, spec, attempt, cap - 10)
            else:
                client_result = subprocess.run(
                    client_command,
                    input=json.dumps(spec),
                    text=True,
                    capture_output=True,
                    timeout=cap - 10,
                    check=False,
                )
                (attempt / "client-stdout.log").write_text(client_result.stdout)
                (attempt / "client-stderr.log").write_text(client_result.stderr)
            child.wait(timeout=max(0.1, cap - (time.monotonic() - started)))
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            forced = child.poll() is None
            _stop_child(child)
    result_path = attempt / (
        "checkpoint-control.json" if fixture is not None else "menu-control.json"
    )
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


def probe_connector_menu(
    config: ConnectorQualificationConfig, *, node: Path, working_app: WorkingAppPolicy | None = None
) -> dict[str, Any]:
    return _probe_connector_private(config, node=node, working_app=working_app)


def _copy_disposable_game_file(source: str | Path, destination: str | Path) -> str:
    """Independent APFS clones for large assets; copies otherwise, never hard links."""
    src, dst = Path(source), Path(destination)
    if sys.platform == "darwin" and src.stat().st_size >= 100_000_000:
        library = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        clone = library.clonefile
        clone.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
        clone.restype = ctypes.c_int
        if clone(os.fsencode(src), os.fsencode(dst), 0) == 0:
            shutil.copystat(src, dst)
            if src.stat().st_ino == dst.stat().st_ino:
                raise ValueError("Disposable game asset must have an independent inode")
            return str(dst)
    return str(shutil.copy2(src, dst))


def _fresh_reward_profile_required(mode: object) -> bool:
    return isinstance(mode, str) and mode in {
        "shop_bridge_v1",
        "reward_bridge_v1",
        "reward_bridge_v2",
        "reward_bridge_v3",
    }


BENCHMARK_PROFILE_MODES = {
    "progression_v1",
    "progression_v2",
    "progression_v3",
    "progression_v4",
    "progression_v5",
    "profile_text_v1",
    "combat_bridge_v4",
    "combat_bridge_v5",
    "new_run_v1",
}


def _validate_benchmark_fixture_scope(fixture: dict[str, Any] | None) -> None:
    if (
        fixture is not None
        and fixture.get("comparison_mode")
        in {
            "progression_v1",
            "progression_v2",
            "progression_v3",
            "progression_v4",
            "progression_v5",
        }
        and (
            fixture.get("privileged_fixture") is not True
            or fixture.get("natural_run") is True
            or fixture.get("act") not in {1, 2, 3}
            or "benchmark_progress" not in fixture
            or "profile_policy" not in fixture
            or "checkpoint_path" not in fixture
        )
    ):
        raise ValueError("Progression checks require explicitly privileged benchmark checkpoints")
    if fixture is not None and "natural_run_limits" in fixture:
        limits = fixture["natural_run_limits"]
        if (
            fixture.get("comparison_mode") != "new_run_v1"
            or fixture.get("natural_run") is not True
            or fixture.get("shipped_ui_revision") not in {"natural_v3", "natural_v4"}
            or not isinstance(limits, dict)
            or set(limits) != {"schema_version", "max_wall_seconds", "max_decisions"}
            or limits.get("schema_version") != "engine-natural-run-limits-v1"
            or type(limits.get("max_wall_seconds")) is not int
            or not 120 <= limits["max_wall_seconds"] <= 900
            or type(limits.get("max_decisions")) is not int
            or not 1 <= limits["max_decisions"] <= 4096
        ):
            raise ValueError("Longer caps require the explicit bounded natural new-run scope")
    if fixture is not None and fixture.get("shipped_ui_revision") == "natural_v4":
        limits = fixture.get("diagnostic_limits", {})
        if (
            fixture.get("natural_run") is not True
            or "natural_run_limits" not in fixture
            or set(limits)
            != {
                "schema_version",
                "mode",
                "max_unique_issues",
                "max_issue_observations",
                "max_recoveries",
                "unsupported_grace_ms",
            }
            or limits.get("schema_version") != "engine-run-diagnostic-limits-v1"
            or limits.get("mode") not in {"validation", "discovery"}
            or any(
                type(limits.get(key)) is not int or not lower <= limits[key] <= upper
                for key, lower, upper in (
                    ("max_unique_issues", 1, 128),
                    ("max_issue_observations", 1, 256),
                    ("max_recoveries", 0, 32),
                    ("unsupported_grace_ms", 3000, 5000),
                )
            )
            or (limits.get("mode") == "validation" and limits.get("max_recoveries") != 0)
        ):
            raise ValueError("Expected bounded explicit diagnostic recovery limits")
    if (
        fixture is not None
        and fixture.get("comparison_mode") == "new_run_v1"
        and (
            "checkpoint_path" in fixture
            or "checkpoint_sha256" in fixture
            or not re.fullmatch(r"SP1RESH1FTA8D1AG[0-9]{3}", str(fixture.get("seed", "")))
            or "benchmark_progress" not in fixture
            or "profile_policy" not in fixture
        )
    ):
        raise ValueError(
            "A new-run comparison requires a fresh benchmark profile and no imported run"
        )
    if (
        fixture is not None
        and ("benchmark_progress" in fixture or "profile_policy" in fixture)
        and (
            not isinstance(fixture.get("comparison_mode"), str)
            or fixture["comparison_mode"] not in BENCHMARK_PROFILE_MODES
        )
    ):
        raise ValueError("Benchmark progress is restricted to its explicit comparison scope")


def _probe_connector_private(
    config: ConnectorQualificationConfig,
    *,
    node: Path,
    fixture: dict[str, Any] | None = None,
    retain_working_game: bool = True,
    working_app: WorkingAppPolicy | None = None,
) -> dict[str, Any]:
    """One copied shipped host; optional fixture is already bound by the checkpoint verifier."""
    # Reject an invalid scope before acquiring a worker or altering its executable/profile.
    _validate_benchmark_fixture_scope(fixture)
    if (
        fixture is not None
        and fixture.get("comparison_mode")
        in {
            "new_run_v1",
            "progression_v1",
            "progression_v2",
            "progression_v3",
            "progression_v4",
            "progression_v5",
        }
        and working_app is None
    ):
        raise ValueError(
            "New-run and progression comparisons require the explicit fixed-app reuse policy"
        )
    if type(retain_working_game) is not bool or (
        not retain_working_game and fixture is None and working_app is None
    ):
        raise ValueError("Disposable payload removal requires an explicit checkpoint fixture")
    _require_native_launch_support()
    if _running_games():
        raise ValueError("Close the existing STS2 game before the short Connector check")
    if not node.is_file():
        raise ValueError("Pass the local Node runtime explicitly with --node")
    if working_app is None and shutil.disk_usage(config.qualification.root).free < 3_500_000_000:
        raise ValueError("Allow 3.5 GB free before copying one disposable shipped game")
    archive, verified = _verified_archive(config.native)
    toolchain = _verify_toolchain(config)
    template, template_report = _settings_template(config)
    user_data = Path.home() / "Library/Application Support"
    shared = user_data / "SlayTheSpire2"
    before = _shared_snapshot(shared)
    workspace = (
        _private_path(config.qualification.root, fixture["workspace"])
        if fixture is not None and "workspace" in fixture
        else config.private("workspace")
    )
    workspace.mkdir(parents=True, exist_ok=True)
    attempt = Path(
        tempfile.mkdtemp(prefix="checkpoint-" if fixture is not None else "menu-", dir=workspace)
    )
    atomic_json(
        attempt / "in-progress.json", {"config_id": config.config_id, "training_allowed": False}
    )
    app_stack = ExitStack()
    try:
        record = json.loads((archive / ARCHIVE_RECORD).read_text())
        lease = (
            app_stack.enter_context(
                lease_working_app(
                    working_app, archive, attempt, copy_file=_copy_disposable_game_file
                )
            )
            if working_app is not None
            else None
        )
        game = lease.game if lease is not None else attempt / "game"
        if lease is None:
            shutil.copytree(
                archive / GAME_RELATIVE,
                game,
                copy_function=_copy_disposable_game_file,
                symlinks=True,
            )
        if _inventory(game) != record["inventory"]:
            raise ValueError("Connector working copy differs from the frozen game")
        executable = game / EXE_RELATIVE
        mode = stat.S_IMODE(executable.stat().st_mode)
        executable.chmod(mode | 0o111)
        archive_name = config.qualification.document["archive_name"]
        profile_name = f"SpireShift/engine-profiles/{archive_name}-{attempt.name}"
        profile = user_data / profile_name
        _no_symlinks(profile)
        # Fresh settings-only profile; explicitly scoped fixture inputs are copied below.
        profile.mkdir(parents=True)
        settings = profile / "default/1/settings.save"
        settings.parent.mkdir(parents=True)
        shutil.copy2(template, settings)
        consent_fresh_rest = False
        consent_fresh_shop = False
        benchmark_consent = None
        if fixture is not None:
            # The exact game's RunSaveManager/UserDataPathProvider use this modded namespace.
            destination = profile / "default/1/modded/profile1/saves/current_run.save"
            destination.parent.mkdir(parents=True)
            if fixture.get("comparison_mode") == "new_run_v1":
                if destination.exists():
                    raise ValueError("Fresh new-run profile unexpectedly has a current save")
            else:
                checkpoint = Path(fixture["checkpoint_path"])
                if _sha_file(checkpoint) != fixture["checkpoint_sha256"]:
                    raise ValueError("Native checkpoint changed before the disposable host copy")
                shutil.copy2(checkpoint, destination)
            if fixture.get("comparison_mode") in BENCHMARK_PROFILE_MODES:
                from spireshift.engine_profile import load_profile_policy, verify_benchmark_progress

                policy = load_profile_policy(
                    config.qualification.root / fixture["profile_policy"], config.qualification
                )
                if manifest_identifier(policy) != fixture["profile_policy_id"]:
                    raise ValueError("Benchmark profile policy changed before launch")
                source = _private_path(config.qualification.root, fixture["benchmark_progress"])
                verify_benchmark_progress(source, policy)
                if "rest_tutorial_baseline" in fixture:
                    raise ValueError("Benchmark profile cannot import a seen-tutorial baseline")
                shutil.copy2(source, destination.with_name("progress.save"))
                benchmark_consent = {
                    "profile_policy_id": manifest_identifier(policy),
                    "progress_sha256": _sha_file(destination.with_name("progress.save")),
                    "fresh_tutorials": True,
                }
            elif "benchmark_progress" in fixture or "profile_policy" in fixture:
                raise ValueError(
                    "Benchmark progress is restricted to its explicit comparison scope"
                )
            if _fresh_reward_profile_required(fixture.get("comparison_mode")):
                if (
                    "rest_tutorial_baseline" in fixture
                    or (destination.parent / "progress.save").exists()
                ):
                    raise ValueError(
                        "Shop/reward qualification requires a fresh tutorial-enabled profile"
                    )
                consent_fresh_shop = True
            if fixture.get("comparison_mode") == "rest_bridge_v2":
                if "rest_tutorial_baseline" in fixture:
                    raise ValueError(
                        "Fresh rest tutorial qualification cannot copy already-seen progress"
                    )
                if (destination.parent / "progress.save").exists():
                    raise ValueError(
                        "Fresh rest fixture unexpectedly has existing tutorial progress"
                    )
                consent_fresh_rest = True
            else:
                consent_fresh_rest = False
            if "rest_tutorial_baseline" in fixture:
                if fixture.get("comparison_mode") != "rest_bridge_v1":
                    raise ValueError(
                        "The rest tutorial baseline is scoped to the privileged rest fixture"
                    )
                baseline = fixture["rest_tutorial_baseline"]
                progress = _private_path(config.qualification.root, baseline["path"])
                progress_body = json.loads(progress.read_text())
                if (
                    _sha_file(progress) != baseline["sha256"]
                    or progress_body.get("ftue_completed") != ["rest_site_ftue"]
                    or progress_body.get("enable_ftues") is not True
                ):
                    raise ValueError(
                        "Expected the unchanged native-generated rest-tutorial-seen profile"
                    )
                shutil.copy2(progress, destination.with_name("progress.save"))
        consent = _enable_mod_settings(settings, config.native.document["settings_schema"])
        if benchmark_consent is not None:
            consent["benchmark_profile"] = benchmark_consent
        if fixture is not None and "rest_tutorial_baseline" in fixture:
            consent["rest_tutorial_baseline"] = fixture["rest_tutorial_baseline"]
        if fixture is not None and consent_fresh_rest:
            consent["fresh_rest_progress_absent_before_launch"] = True
        if consent_fresh_shop:
            consent["fresh_shop_progress_absent_before_launch"] = True
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
        process = (
            _run_menu_probe(config, node, attempt, executable, port, fixture=fixture)
            if fixture is not None
            else _run_menu_probe(config, node, attempt, executable, port)
        )
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
        if fixture is not None and fixture.get("comparison_mode") in BENCHMARK_PROFILE_MODES:
            checks["benchmark_profile_bound_before_launch"] = benchmark_consent is not None
        reuse_result = None
        if lease is not None:
            if not all(
                checks[key]
                for key in ("working_game_unchanged", "archive_still_valid", "natural_shutdown")
            ):
                raise ValueError(
                    "Reusable app did not exit intact; worker blocked and evidence preserved"
                )
            reuse_result = lease.restore(expected_working)
            checks["reusable_working_app_restored"] = True
        fresh_rest_tutorial = (
            fixture is not None and fixture.get("comparison_mode") == "rest_bridge_v2"
        )
        if fresh_rest_tutorial:
            checks["fresh_rest_progress_absent_before_launch"] = (
                consent.get("fresh_rest_progress_absent_before_launch") is True
            )
        shop_bridge = fixture is not None and fixture.get("comparison_mode") == "shop_bridge_v1"
        if shop_bridge or (
            fixture is not None
            and fixture.get("comparison_mode")
            in {"reward_bridge_v1", "reward_bridge_v2", "reward_bridge_v3"}
        ):
            checks["fresh_shop_progress_absent_before_launch"] = (
                consent.get("fresh_shop_progress_absent_before_launch") is True
            )
        verdict = (
            _evaluate_connector_checkpoint(
                checks,
                journey=fixture.get("comparison_mode") in {"journey_v1", "journey_v2"},
                rest_bridge=fixture.get("comparison_mode") in {"rest_bridge_v1", "rest_bridge_v2"},
                fresh_rest_tutorial=fresh_rest_tutorial,
                shop_bridge=shop_bridge,
                bundle_bridge=fixture.get("comparison_mode")
                in {"bundle_bridge_v1", "bundle_bridge_v2", "bundle_bridge_v3"},
                reward_bridge=fixture.get("comparison_mode")
                in {"reward_bridge_v1", "reward_bridge_v2", "reward_bridge_v3"},
                profile_text=fixture.get("comparison_mode") == "profile_text_v1",
                combat_bridge=fixture.get("comparison_mode") == "combat_bridge_v4",
                combat_discard=fixture.get("comparison_mode") == "combat_bridge_v5",
                new_run=fixture.get("comparison_mode") == "new_run_v1",
                natural_run=fixture.get("natural_run") is True,
                progression=fixture.get("comparison_mode")
                in {
                    "progression_v1",
                    "progression_v2",
                    "progression_v3",
                    "progression_v4",
                    "progression_v5",
                },
            )
            if fixture is not None
            else evaluate_connector_menu(checks)
        )
        removed_payload = False
        if (
            lease is None
            and not retain_working_game
            and verdict["status"] == "shipped_checkpoint_input_pass"
        ):
            # Only this attempt's generated payload; reports, logs, profile and source stay.
            # All integrity checks and natural child shutdown already passed above.
            shutil.rmtree(game)
            removed_payload = True
        return _finish(
            attempt,
            {
                "schema_version": "engine-connector-checkpoint-v1"
                if fixture is not None
                else "engine-connector-menu-v1",
                "config_id": config.config_id,
                "qualification_config_id": config.qualification.config_id,
                "archive_id": record["archive_id"],
                "archive_verification_before": verified["report_id"],
                "archive_verification_after": archive_after["report_id"],
                "toolchain_report_id": toolchain["report_id"],
                "bootstrap_report_id": template_report["report_id"],
                "verdict": verdict,
                "checks": checks,
                "process": process,
                "probe": probe,
                "profile": str(profile),
                "profile_settings_consent": consent,
                "shared_profile_sentinel": {"before": before, "after": after},
                "working_inventory_id": manifest_identifier(expected_working),
                **({"working_app": reuse_result} if lease is not None else {}),
                "working_payload_retained": not removed_payload,
                "disposable_payload_removed_after_verified_success": removed_payload,
                "diagnostics": {
                    "error_lines": len(re.findall(r"^ERROR:", stderr, re.MULTILINE)),
                    "warning_lines": len(re.findall(r"^WARNING:", stderr, re.MULTILINE)),
                    "logs_preserved": True,
                },
                "authority": "exact_process_local_source_canary",
                "launcher_invocations": 1,
                "games_launched": int("MegaDot" in stdout),
                "menu_actions_requested": probe.get("menu_actions_requested", 0),
                "full_run_attempts": int(
                    fixture is not None
                    and fixture.get("natural_run") is True
                    and probe.get("checks", {}).get("normal_new_run_embarked") is True
                ),
                "optimizer_steps": 0,
                "mechanics_qualified": False,
                "training_allowed": False,
                "claim_scope": "natural_shipped_Ironclad_A8_diagnostic_only"
                if fixture is not None and fixture.get("natural_run") is True
                else "single_native_checkpoint_shipped_public_input_only"
                if fixture is not None
                else "shipped_public_menu_transition_and_control_only",
            },
        )
    except BaseException as error:
        _failure(attempt, error)
        raise
    finally:
        app_stack.close()


def _evaluate_connector_checkpoint(
    checks: dict[str, Any],
    *,
    journey: bool = False,
    rest_bridge: bool = False,
    fresh_rest_tutorial: bool = False,
    shop_bridge: bool = False,
    bundle_bridge: bool = False,
    reward_bridge: bool = False,
    profile_text: bool = False,
    combat_bridge: bool = False,
    combat_discard: bool = False,
    new_run: bool = False,
    natural_run: bool = False,
    progression: bool = False,
) -> dict[str, Any]:
    if (
        sum(
            (
                journey,
                rest_bridge,
                shop_bridge,
                bundle_bridge,
                reward_bridge,
                profile_text,
                combat_bridge,
                combat_discard,
                new_run,
                progression,
            )
        )
        > 1
    ):
        raise ValueError("Do not merge separately scoped combat, rest and shop comparisons")
    if fresh_rest_tutorial and not rest_bridge:
        raise ValueError("Fresh rest tutorial evidence requires the scoped rest fixture")
    required: tuple[str, ...] = (
        "loaded_identity",
        "endpoint_owned_by_child",
        "native_continue_offered",
        "native_checkpoint_loaded",
        "complete_public_starting_event",
        "native_A8_seed_preserved",
        "same_starting_public_option_titles_and_availability",
        "profile_path_logged",
        "steam_disabled_observed",
        "shared_profile_unchanged",
        "working_game_unchanged",
        "archive_still_valid",
        "template_unchanged",
        "natural_shutdown",
    )
    if new_run:
        required = tuple(
            name
            for name in required
            if name not in {"native_continue_offered", "native_checkpoint_loaded"}
        ) + (
            "no_continue_used",
            "normal_new_run_embarked",
            "Ironclad_A8_selected",
            "same_public_initial_run_facts",
            "benchmark_profile_bound_before_launch",
        )
    if progression:
        required = tuple(
            name
            for name in required
            if name
            not in {
                "complete_public_starting_event",
                "same_starting_public_option_titles_and_availability",
            }
        ) + (
            "benchmark_profile_bound_before_launch",
            "progression_source_not_terminal",
            "progression_target_observed",
            "progression_all_actions_delivered",
        )
    if natural_run:
        if not new_run:
            raise ValueError("Natural shipped runs require normal fresh startup")
        required += ("natural_full_run_observed",)
        if "natural_run_compute_within_budget" in checks:
            required += ("natural_run_compute_within_budget", "all_natural_run_actions_delivered")
        if "natural_run_clean" in checks:
            required += ("natural_run_clean",)
    if rest_bridge:
        required = tuple(
            name
            for name in required
            if name
            not in {
                "complete_public_starting_event",
                "same_starting_public_option_titles_and_availability",
            }
        ) + (
            "complete_public_rest_fixture",
            "rest_all_snapshots_match",
            "rest_all_actions_delivered",
            "rest_final_map_observed",
            "rest_heal_and_upgrade_observed",
        )
    if journey:
        required += (
            "journey_all_snapshots_match",
            "journey_all_actions_delivered",
            "journey_second_turn_observed",
        )
    if bundle_bridge:
        required += (
            "bundle_all_snapshots_match",
            "bundle_all_actions_delivered",
            "bundle_preview_cancel_confirm_verified",
            "bundle_selected_cards_obtained",
        )
    if shop_bridge:
        required = tuple(
            name
            for name in required
            if name
            not in {
                "complete_public_starting_event",
                "same_starting_public_option_titles_and_availability",
            }
        ) + (
            "fresh_shop_progress_absent_before_launch",
            "complete_public_shop_fixture",
            "shop_all_snapshots_match",
            "shop_all_actions_delivered",
            "shop_final_map_observed",
            "shop_purchase_removal_and_exit_effects",
            "shop_fresh_potion_tutorial_delivered",
        )
    if reward_bridge:
        required = tuple(
            name
            for name in required
            if name
            not in {
                "complete_public_starting_event",
                "same_starting_public_option_titles_and_availability",
            }
        ) + (
            "fresh_shop_progress_absent_before_launch",
            "complete_public_reward_fixture",
            "reward_all_snapshots_match",
            "reward_all_actions_delivered",
            "reward_pickup_capacity_and_skip_effects",
            "reward_fresh_tutorials_preserve_facts",
        )
    if profile_text:
        required += (
            "benchmark_profile_bound_before_launch",
            "same_public_profile_descriptions",
            "native_current_act_preserved",
        )
    if combat_bridge or combat_discard:
        required += (
            "benchmark_profile_bound_before_launch",
            "native_current_act_preserved",
            "combat_all_snapshots_match",
            "combat_all_actions_delivered",
            "combat_effect_signals_verified",
            "combat_fresh_tutorials_preserve_facts",
        )
    if combat_discard:
        required += (
            "combat_full_potion_action_menu_compared",
            "combat_exact_slot_discard_effects",
        )
    if fresh_rest_tutorial:
        required += ("fresh_rest_tutorial_dismissed", "fresh_rest_progress_absent_before_launch")
    errors = [key for key in required if checks.get(key) is not True]
    return {
        "status": "shipped_checkpoint_input_pass"
        if not errors
        else "shipped_checkpoint_input_incomplete",
        "errors": errors,
    }
