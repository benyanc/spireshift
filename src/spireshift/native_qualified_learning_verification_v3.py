"""Keep exact frame/choice reconstruction; accept an absent unused cursor ledger."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_qualified_learning_verification_v2 as original

SCRIPT = "scripts/engine-card-answer-verify-v3.mjs"


def verify_episode(
    context: dict[str, Any],
    start: dict[str, Any],
    variant: str,
    directory: Path,
    output: Path,
    deadline: float,
    *,
    model: Any | None = None,
) -> int:
    # The proof schema and all Python binding/probability checks stay identical.
    with patch.object(original, "SCRIPT", SCRIPT):
        return original.verify_episode(
            context, start, variant, directory, output, deadline, model=model
        )
