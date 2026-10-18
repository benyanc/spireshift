"""Exclusive, sealed chunk commits with model and complete Adam-state restoration.

No game/optimizer starts here. Existing uncommitted collection directories are
preserved for explicit recovery; their seeds and worker profiles are never reset.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Adam
from spireshift.native_context_cache import CachedContextModel


def save_state(path: Path, model: CachedContextModel, optimizer: Adam) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError("Preserve an existing model/optimizer checkpoint")
    body = {
        "schema_version": "native-context-model-optimizer-v1",
        "model": model.as_dict(),
        "optimizer": optimizer.as_dict(),
    }
    atomic_json(path, {**body, "state_id": manifest_identifier(body)})


def load_state(path: Path) -> tuple[CachedContextModel, Adam, str]:
    d = identified(path, "state_id")
    if d["schema_version"] != "native-context-model-optimizer-v1":
        raise ValueError("Context chunk state schema differs")
    model = CachedContextModel.from_mapping(d["model"])
    optimizer = Adam.from_mapping(d["optimizer"], model.parameter_count)
    return model, optimizer, d["state_id"]


class ChunkJournal:
    def __init__(self, root: Path, recipe: dict[str, Any]) -> None:
        self.root = root
        self.recipe = recipe
        self.workspace = _private_path(root, recipe["workspace"])
        self.config_id = manifest_identifier(recipe)
        self.locked = False

    @contextmanager
    def lock(self) -> Iterator[None]:
        self.workspace.mkdir(parents=True, exist_ok=True)
        with (self.workspace / "session.lock").open("a+") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError("Another process owns this chunked comparison") from exc
            self.locked = True
            try:
                path = self.workspace / "config-at-launch.json"
                if path.exists():
                    if json.loads(path.read_text()) != self.recipe:
                        raise ValueError("Saved chunked comparison recipe changed")
                else:
                    atomic_json(path, self.recipe)
                yield
            finally:
                self.locked = False
                fcntl.flock(handle, fcntl.LOCK_UN)

    def path(self, key: str) -> Path:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,120}", key):
            raise ValueError("Invalid chunk key")
        target = self.workspace / "chunks" / key
        if target.is_symlink() or target.resolve() != self.workspace.resolve() / "chunks" / key:
            raise ValueError("Chunk path aliases another location")
        return target

    def begin(self, key: str, request: dict[str, Any]) -> Path:
        if not self.locked:
            raise ValueError("Acquire the comparison lock before starting a chunk")
        target = self.path(key)
        if target.exists():
            raise FileExistsError(f"Preserve uncommitted chunk {key}; no automatic game/fit replay")
        target.mkdir(parents=True)
        atomic_json(
            target / "active.json",
            {
                "config_id": self.config_id,
                "key": key,
                "request": request,
                "request_id": manifest_identifier(request),
                "owner_process": os.getpid(),
            },
        )
        return target

    def completed(self, key: str, request: dict[str, Any]) -> dict[str, Any] | None:
        target = self.path(key)
        if not target.exists():
            return None
        receipt = target / "done.json"
        if not receipt.is_file():
            raise FileExistsError(f"Preserve uncommitted chunk {key}; inspect before resuming")
        result = identified(receipt)
        if (
            result["schema_version"] != "native-context-chunk-commit-v1"
            or result["config_id"] != self.config_id
            or result["key"] != key
            or result["request_id"] != manifest_identifier(request)
        ):
            raise ValueError("Completed chunk predecessor, seeds or settings differ")
        present = {
            str(p.relative_to(self.root))
            for p in target.rglob("*")
            if p.is_file() and not p.is_symlink() and p != receipt
        }
        sealed = {n for n in result["sources"] if (self.root / n).is_relative_to(target)}
        if present != sealed:
            raise ValueError("Completed chunk contains missing or unexpected evidence")
        for name, sha in result["sources"].items():
            path = self.root / name
            if (
                Path(name).is_absolute()
                or ".." in Path(name).parts
                or path.is_symlink()
                or path.resolve() != self.root.resolve() / name
                or _sha_file(path) != sha
            ):
                raise ValueError("Completed chunk evidence changed")
        return result

    def commit(
        self,
        key: str,
        request: dict[str, Any],
        result: dict[str, Any],
        extra_sources: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if not self.locked:
            raise ValueError("Acquire the comparison lock before committing a chunk")
        target = self.path(key)
        active = json.loads((target / "active.json").read_text())
        if active["config_id"] != self.config_id or active["request_id"] != manifest_identifier(
            request
        ):
            raise ValueError("Chunk request changed while executing")
        if (target / "done.json").exists():
            raise FileExistsError("Never overwrite a completed chunk")
        sources = dict(extra_sources or {})
        sources.update(
            {
                str(p.relative_to(self.root)): _sha_file(p)
                for p in target.rglob("*")
                if p.is_file() and not p.is_symlink()
            }
        )
        body = {
            "schema_version": "native-context-chunk-commit-v1",
            "config_id": self.config_id,
            "key": key,
            "request_id": manifest_identifier(request),
            "sources": sources,
            "result": result,
        }
        receipt = {**body, "report_id": manifest_identifier(body)}
        atomic_json(target / "done.json", receipt)
        return receipt
