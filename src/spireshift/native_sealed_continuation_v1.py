"""Restore exact committed units while permanently excluding uncertain attempts."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from spireshift.native_context_journal import ChunkJournal


class SealedPrefixJournal(ChunkJournal):
    def __init__(
        self,
        root: Path,
        cfg: dict[str, Any],
        parent: dict[str, Any],
        imports: dict[str, str],
        excluded: frozenset[str],
    ):
        super().__init__(root, cfg)
        self.original = ChunkJournal(root, parent)
        self.imports = imports
        self.excluded = excluded
        if set(imports) & excluded:
            raise ValueError("An excluded uncertain attempt cannot also be a clean import")

    @contextmanager
    def lock(self) -> Iterator[None]:
        with self.original.lock(), super().lock():
            yield

    def path(self, key: str) -> Path:
        if key in self.excluded:
            raise ValueError("Never reopen an excluded uncertain attempt")
        return self.original.path(key) if key in self.imports else super().path(key)

    def completed(self, key: str, request: dict[str, Any]) -> dict[str, Any] | None:
        if key in self.excluded:
            raise ValueError("Never replay an excluded uncertain attempt")
        if key in self.imports:
            result = self.original.completed(key, request)
            if result is None or result["report_id"] != self.imports[key]:
                raise ValueError("A complete historical unit changed; do not repeat it")
            return result
        return super().completed(key, request)

    def begin(self, key: str, request: dict[str, Any]) -> Path:
        if key in self.excluded or key in self.imports:
            raise ValueError("Never collect or update an imported/excluded unit again")
        return super().begin(key, request)
