"""Reuse six collected games and four copy updates; finish two unstarted reload games."""

from __future__ import annotations

import fcntl
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_qualified_learning_session_v1 as previous
from spireshift.native_a8_head_policy import HeadState
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_qualified_learning_inputs_v2 import (
    IMPORTS,
    MODULE,
    PARENT,
    SCHEMA,
    context,
    load,
)


def canonical_partition(partition: str) -> str:
    return "reload-control" if partition == "reload_control" else partition


class AdoptedJournal(ChunkJournal):
    def __init__(self, root: Path, recipe: dict[str, Any], parent: dict[str, Any]):
        super().__init__(root, recipe)
        self.original = ChunkJournal(root, {**parent, "workspace": parent["control_workspace"]})

    def path(self, key: str) -> Path:
        return self.original.path(key) if key in IMPORTS else super().path(key)

    def completed(self, key: str, request: dict[str, Any]) -> dict[str, Any] | None:
        if key in IMPORTS:
            result = self.original.completed(key, request)
            if result is None:
                raise ValueError("Never replay a missing imported control unit")
            return result
        return super().completed(key, request)


class Session(previous.Session):
    def __init__(self, root: Path, cfg: dict[str, Any], control: bool, deadline: float):
        super().__init__(root, cfg, control, deadline)
        if control:
            parent = json.loads((root / PARENT).read_text())
            self.store = AdoptedJournal(root, self.store.recipe, parent)

    def game(
        self,
        seed: str,
        index: int,
        p: int,
        round_index: int,
        partition: str,
        arm: str,
        state: tuple[HeadState, str],
    ) -> dict[str, Any]:
        return super().game(seed, index, p, round_index, canonical_partition(partition), arm, state)

    def run(self) -> dict[str, Any]:
        result = super().run()
        return {
            **result,
            "imported_control_units": 8 if self.control else 0,
            "imported_control_optimizer_updates": 4 if self.control else 0,
            "new_control_optimizer_updates": 0 if self.control else None,
        }


def main() -> int:
    root = Path.cwd()
    parent = json.loads((root / PARENT).read_text())
    with (root / parent["control_workspace"] / "session.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        with patch.multiple(
            previous, MODULE=MODULE, SCHEMA=SCHEMA, load=load, context=context, Session=Session
        ):
            return previous.main()


if __name__ == "__main__":
    raise SystemExit(main())
