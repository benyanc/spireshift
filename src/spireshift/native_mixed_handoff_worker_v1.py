"""Select the qualified lifecycle adapters without changing historical workers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_selector_lifecycle_worker
from spireshift.native_mixed_handoff_inputs_v1 import SCRIPT
from spireshift.native_selector_lifecycle_worker import OwnerWorker


class MixedWorker(OwnerWorker):
    def __init__(self, ctx: dict[str, Any], target: Path) -> None:
        with patch.object(native_selector_lifecycle_worker, "SCRIPT", SCRIPT):
            super().__init__(ctx, target)

    def request(self, command: str, *, timeout: float = 20, **values: Any) -> dict[str, Any]:
        if command == "initialize":
            values["spec"] = {
                **values["spec"],
                "selector_fixture": True,
                "mixed_handoff_fixture": True,
            }
        return super().request(command, timeout=timeout, **values)
