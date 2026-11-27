"""Run shop and reward fixtures through the versioned shared lifecycle worker."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_lifecycle_worker
from spireshift.native_lifecycle_worker import LifecycleWorker

SCRIPT = "engine-selector-lifecycle-worker-v1.mjs"


class OwnerWorker(LifecycleWorker):
    def __init__(self, ctx: dict[str, Any], target: Path) -> None:
        with patch.object(native_lifecycle_worker, "SCRIPT", SCRIPT):
            super().__init__(ctx, target, fixture=True)

    def request(self, command: str, *, timeout: float = 20, **values: Any) -> dict[str, Any]:
        if command == "initialize":
            values["spec"] = {**values["spec"], "selector_fixture": True}
        return super().request(command, timeout=timeout, **values)
