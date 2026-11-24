"""Bind the optional-ledger-aware verifier without changing native execution."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_qualified_learning_worker_v2 as original
from spireshift.native_a8_head_policy import HeadState
from spireshift.native_qualified_learning_verification_v3 import verify_episode


def play(
    ctx: dict[str, Any],
    task: dict[str, Any],
    directory: Path,
    state: HeadState,
    deadline: float,
) -> dict[str, Any]:
    with patch.object(original, "verify_episode", verify_episode):
        return original.play(ctx, task, directory, state, deadline)
