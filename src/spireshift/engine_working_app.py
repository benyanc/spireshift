"""Locked reuse of a frozen game's working app; run evidence remains immutable."""

from __future__ import annotations

import fcntl
import json
import os
import shutil
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_native import EXE_RELATIVE, _no_symlinks, _private_path
from spireshift.engine_qualification import (
    ARCHIVE_RECORD,
    GAME_RELATIVE,
    EngineQualificationConfig,
    _inventory,
)
from spireshift.full_run_experience import atomic_json

POOL_RELATIVE = "artifacts/engine-working-apps"


@dataclass(frozen=True)
class WorkingAppPolicy:
    document: dict[str, Any]
    qualification: EngineQualificationConfig

    @property
    def config_id(self) -> str:
        return manifest_identifier(self.document)

    @property
    def pool(self) -> Path:
        return _private_path(self.qualification.root, POOL_RELATIVE)

    @property
    def slot(self) -> Path:
        return _private_path(self.qualification.root, self.document["workspace"])


def load_working_app_policy(
    path: Path, qualification: EngineQualificationConfig
) -> WorkingAppPolicy:
    document = json.loads(path.read_text())
    expected = f"{POOL_RELATIVE}/{qualification.document['archive_name']}/worker-00"
    if (
        document.get("schema_version") != "engine-working-app-config-v1"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("mode") != "serial_reuse"
        or document.get("workspace") != expected
        or document.get("max_pool_apps") != 2
        or document.get("max_pool_bytes") != 5_000_000_000
        or document.get("training_allowed") is not False
    ):
        raise ValueError("Expected the pinned serial worker and global two-app/5 GB pool cap")
    policy = WorkingAppPolicy(document, qualification)
    _ = policy.slot
    return policy


def working_app_inventory(
    qualification: EngineQualificationConfig, *, include_other_payloads: bool = True
) -> dict[str, Any]:
    """Preview only: include partial and blocked workers; never delete anything."""
    pool = _private_path(qualification.root, POOL_RELATIVE)
    workers = []
    if pool.exists():
        for slot in sorted(pool.glob("*/worker-*")):
            _no_symlinks(slot)
            game = slot / "game"
            inventory = _inventory(game) if game.exists() else []
            workers.append(
                {
                    "workspace": str(slot.relative_to(qualification.root)),
                    "app_present": game.exists(),
                    "logical_bytes": sum(row["bytes"] for row in inventory),
                    "blocked_or_active": (slot / "active.json").exists(),
                    "registered": (slot / "app.json").exists(),
                }
            )
    other_payloads = []
    errors = []
    for current, directories, _ in (
        os.walk(
            qualification.root / "artifacts",
            followlinks=False,
            onerror=lambda error: errors.append(str(error)),
        )
        if include_other_payloads
        else ()
    ):
        directories[:] = [
            name
            for name in directories
            if name not in {"engine-working-apps", ".git", ".venv", "node_modules"}
        ]
        game = Path(current)
        if game.name != "game":
            continue
        directories[:] = []
        _no_symlinks(game)
        bytes_used = sum(
            file.lstat().st_size
            for file in game.rglob("*")
            if file.is_file() and not file.is_symlink()
        )
        other_payloads.append(
            {
                "path": str(game),
                "logical_bytes": bytes_used,
                "classification": "download_staging"
                if game.is_relative_to(qualification.root / "artifacts/engine-downloads")
                else "legacy_or_unclassified_payload",
                "automatically_deletable": False,
            }
        )
    return {
        "schema_version": "engine-working-app-inventory-v1",
        "workers": workers,
        "apps": sum(row["app_present"] for row in workers),
        "logical_bytes": sum(row["logical_bytes"] for row in workers),
        "other_game_payloads": other_payloads,
        "scan_errors": errors,
        "files_deleted": 0,
        "games_launched": 0,
        "training_allowed": False,
    }


def verify_working_app_receipt(
    policy: WorkingAppPolicy, result: dict[str, Any], *, attempt: Path, archive_id: str
) -> None:
    """Verify immutable run/reset receipts without requiring a still-existing working app."""
    _private_path(policy.qualification.root, str(attempt.relative_to(policy.qualification.root)))
    begin = json.loads((attempt / "working-app-lease.json").read_text())
    saved = json.loads((attempt / "working-app-restored.json").read_text())
    original = {
        key: value
        for key, value in result.items()
        if key not in {"status", "restored", "app_copies_created", "app_inode", "report_id"}
    }
    if (
        result != saved
        or manifest_identifier({key: value for key, value in result.items() if key != "report_id"})
        != result.get("report_id")
        or original != begin
        or result.get("config_id") != policy.config_id
        or result.get("qualification_config_id") != policy.qualification.config_id
        or result.get("archive_id") != archive_id
        or result.get("worker") != str(policy.slot)
        or result.get("game") != str(policy.slot / "game")
        or result.get("attempt") != str(attempt)
        or result.get("status") != "restored_to_frozen_baseline"
        or result.get("restored") is not True
        or type(result.get("app_created")) is not bool
        or result.get("app_copies_created") != int(result["app_created"])
        or type(result.get("app_inode")) is not int
        or result["app_inode"] <= 0
        or result.get("training_allowed") is not False
    ):
        raise ValueError("Saved working app ownership or reset receipt changed")


def preflight_working_app(policy: WorkingAppPolicy) -> dict[str, Any]:
    inventory = working_app_inventory(policy.qualification, include_other_payloads=False)
    if (policy.slot / "active.json").exists():
        raise ValueError(
            "Working app is active or interrupted; preserve its evidence before repair"
        )
    if (policy.slot / "game").exists() and not (policy.slot / "app.json").is_file():
        raise ValueError("Unregistered working app; preserve the partial setup before repair")
    if (policy.slot / "app.json").exists() and not (policy.slot / "game").is_dir():
        raise ValueError("Registered working app was removed; explicit repair is required")
    if (policy.slot / "game").exists():
        _no_symlinks(policy.slot / "app.json")
        registered = json.loads((policy.slot / "app.json").read_text())
        if registered.get("config_id") != policy.config_id or registered.get(
            "baseline_inventory_id"
        ) != manifest_identifier(_inventory(policy.slot / "game")):
            raise ValueError("Registered working app changed; explicit repair is required")
    if (
        inventory["apps"] > policy.document["max_pool_apps"]
        or inventory["logical_bytes"] > policy.document["max_pool_bytes"]
    ):
        raise ValueError("Working app pool exceeds its global storage cap")
    return inventory


@contextmanager
def _lock(path: Path) -> Iterator[None]:
    _no_symlinks(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError(
                "Another run owns this working app or is preparing the pool"
            ) from error
        yield
    finally:
        os.close(descriptor)


@dataclass
class WorkingAppLease:
    policy: WorkingAppPolicy
    game: Path
    baseline: list[dict[str, Any]]
    attempt: Path
    receipt: dict[str, Any]
    restored: bool = False
    in_context: bool = True

    def restore(self, expected_working: list[dict[str, Any]]) -> dict[str, Any]:
        """After child exit, remove only owned additions; never repair changed official bytes."""
        if not self.in_context:
            raise ValueError("Working app reset requires the still-held worker lock")
        if self.restored:
            raise ValueError("Working app lease already restored")
        _no_symlinks(self.policy.slot / "active.json")
        if json.loads((self.policy.slot / "active.json").read_text()) != self.receipt:
            raise ValueError("Working app lease ownership changed; preserve this worker")
        current = _inventory(self.game)
        if current != expected_working:
            raise ValueError("Working app changed unexpectedly; worker is blocked for inspection")
        base = {row["path"]: row for row in self.baseline}
        present = {row["path"]: row for row in current}
        executable = Path(EXE_RELATIVE).as_posix()
        mods = (Path(EXE_RELATIVE).parent / "mods").as_posix()
        override = (Path(EXE_RELATIVE).parent / "override.cfg").as_posix()
        for name, row in base.items():
            expected = {**row, "mode": row["mode"] | 0o111} if name == executable else row
            if present.get(name) != expected:
                raise ValueError(
                    "Official working app file changed; worker is blocked for inspection"
                )
        if any(
            name != override and not name.startswith(mods + "/")
            for name in present.keys() - base.keys()
        ):
            raise ValueError(
                "Unknown working app addition; preserve it before repairing this worker"
            )
        if any(name == override or name.startswith(mods + "/") for name in base):
            raise ValueError("Frozen master contains worker-owned settings or mods")
        mods_path = self.game / mods
        if mods_path.exists():
            shutil.rmtree(mods_path)
        (self.game / override).unlink(missing_ok=True)
        (self.game / executable).chmod(base[executable]["mode"])
        if _inventory(self.game) != self.baseline:
            raise ValueError("Working app reset failed; no later run may reuse it")
        result = {
            **self.receipt,
            "status": "restored_to_frozen_baseline",
            "restored": True,
            "app_copies_created": int(self.receipt["app_created"]),
            "app_inode": self.game.stat().st_ino,
        }
        result["report_id"] = manifest_identifier(result)
        atomic_json(self.attempt / "working-app-restored.json", result)
        (self.policy.slot / "active.json").unlink()
        self.restored = True
        return result


@contextmanager
def lease_working_app(
    policy: WorkingAppPolicy,
    archive: Path,
    attempt: Path,
    *,
    copy_file: Callable[[str | Path, str | Path], str],
) -> Iterator[WorkingAppLease]:
    record = json.loads((archive / ARCHIVE_RECORD).read_text())
    baseline = record["inventory"]
    source = archive / GAME_RELATIVE
    if _inventory(source) != baseline:
        raise ValueError("Frozen app changed before working app preparation")
    policy.slot.mkdir(parents=True, exist_ok=True)
    with _lock(policy.slot / ".lock"):
        with _lock(policy.pool / ".pool.lock"):
            inventory = preflight_working_app(policy)
            game = policy.slot / "game"
            created = not game.exists()
            if created:
                required = sum(row["bytes"] for row in baseline)
                if (
                    inventory["apps"] >= policy.document["max_pool_apps"]
                    or inventory["logical_bytes"] + required > policy.document["max_pool_bytes"]
                ):
                    raise ValueError("A new working app would exceed the global two-app/5 GB cap")
                if shutil.disk_usage(policy.pool).free < 3_500_000_000:
                    raise ValueError("Allow 3.5 GB free before preparing one reusable app")
            receipt = {
                "schema_version": "engine-working-app-lease-v1",
                "config_id": policy.config_id,
                "qualification_config_id": policy.qualification.config_id,
                "archive_id": record["archive_id"],
                "baseline_inventory_id": manifest_identifier(baseline),
                "worker": str(policy.slot),
                "game": str(game),
                "attempt": str(attempt),
                "app_created": created,
                "training_allowed": False,
            }
            # A crashed preparation/launch retains this marker and the single fixed app.
            atomic_json(policy.slot / "active.json", receipt)
            atomic_json(attempt / "working-app-lease.json", receipt)
            if created:
                shutil.copytree(source, game, copy_function=copy_file, symlinks=True)
                if any((source / row["path"]).samefile(game / row["path"]) for row in baseline):
                    raise ValueError("Working app cannot hard-link the frozen master")
                atomic_json(
                    policy.slot / "app.json",
                    {
                        "archive_id": record["archive_id"],
                        "baseline_inventory_id": manifest_identifier(baseline),
                        "config_id": policy.config_id,
                    },
                )
            registered = json.loads((policy.slot / "app.json").read_text())
            if (
                registered
                != {
                    "archive_id": record["archive_id"],
                    "baseline_inventory_id": manifest_identifier(baseline),
                    "config_id": policy.config_id,
                }
                or _inventory(game) != baseline
            ):
                raise ValueError("Working app identity drifted; preserve this worker before repair")
        lease = WorkingAppLease(policy, game, baseline, attempt, receipt)
        try:
            yield lease
        finally:
            lease.in_context = False
            # Never delete or recopy a failed app. One blocked slot bounds retained payload.
            if not lease.restored and not (attempt / "working-app-blocked.json").exists():
                atomic_json(
                    attempt / "working-app-blocked.json",
                    {**receipt, "status": "blocked_pending_inspection"},
                )
