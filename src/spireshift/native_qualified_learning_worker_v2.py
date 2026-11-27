"""Keep gameplay unchanged and bind the current saved-answer verifier explicitly."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_win4_game
from spireshift.native_a8_head_policy import HeadState
from spireshift.native_qualified_learning_verification_v2 import verify_episode
from spireshift.native_qualified_learning_worker_v1 import play as original_play


def play(
    ctx: dict[str, Any],
    task: dict[str, Any],
    directory: Path,
    state: HeadState,
    deadline: float,
) -> dict[str, Any]:
    try:
        with patch.object(native_win4_game, "verify_episode", verify_episode):
            return original_play(ctx, task, directory, state, deadline)
    except (subprocess.SubprocessError, StopIteration) as exc:
        # The session writes a durable stop instead of losing its summary to a traceback.
        raise ValueError(f"Saved subprocess verification did not complete: {exc}") from exc
