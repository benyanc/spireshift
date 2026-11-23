"""Keep a merchant target alive under its map without changing host60."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_mixed_handoff_worker_v1
from spireshift.native_mixed_handoff_worker_v1 import MixedWorker as PreviousWorker

SCRIPT = "engine-mixed-handoffs-worker-v2.mjs"


class MixedWorker(PreviousWorker):
    def __init__(self, ctx: dict[str, Any], target: Path) -> None:
        with patch.object(native_mixed_handoff_worker_v1, "SCRIPT", SCRIPT):
            super().__init__(ctx, target)
