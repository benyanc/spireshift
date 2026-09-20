from __future__ import annotations

import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any


class JsonlRecorder:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")

    def record_header(self, payload: dict[str, object]) -> None:
        self._append({"record_type": "header", **payload})

    def record_step(self, payload: dict[str, object]) -> None:
        self._append({"record_type": "step", **payload})

    def record_summary(self, payload: dict[str, object]) -> None:
        self._append({"record_type": "summary", **payload})

    def _append(self, payload: dict[str, object]) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
            handle.write("\n")


class ImmutableJsonlRecorder:
    """Append-only recorder that refuses to replace an existing artifact."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("x", encoding="utf-8")

    def record_header(self, payload: dict[str, object]) -> None:
        self._append({"record_type": "header", **payload})

    def record_step(self, payload: dict[str, object]) -> None:
        self._append({"record_type": "step", **payload})

    def record_summary(self, payload: dict[str, object]) -> None:
        self._append({"record_type": "summary", **payload})

    def close(self) -> None:
        if not self._handle.closed:
            self._handle.close()

    def _append(self, payload: dict[str, object]) -> None:
        self._handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        self._handle.write("\n")
        self._handle.flush()
        os.fsync(self._handle.fileno())


def load_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Non-object record in {path}")
            records.append(value)
    return records


def records_of_type(records: Iterable[dict[str, Any]], record_type: str) -> list[dict[str, Any]]:
    return [record for record in records if record.get("record_type") == record_type]
