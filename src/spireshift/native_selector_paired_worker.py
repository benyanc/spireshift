"""Use shared serialized fixtures with the qualified native lifecycle checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_lifecycle_worker
from spireshift.native_lifecycle_worker import LifecycleWorker

SCRIPT = "engine-selector-paired-worker-v1.mjs"


class PairedWorker(LifecycleWorker):
    def __init__(self, ctx: dict[str, Any], target: Path) -> None:
        self.shared_fixture = ctx.get("selector_fixture_save")
        with patch.object(native_lifecycle_worker, "SCRIPT", SCRIPT):
            super().__init__(ctx, target, fixture=True)

    def request(self, command: str, *, timeout: float = 20, **values: Any) -> dict[str, Any]:
        if command == "initialize":
            values["spec"] = {**values["spec"], "selector_fixture": True}
        if self.shared_fixture is not None:
            save = json.loads(self.shared_fixture.read_text())
            if command in {"prepare", "reward_fixture"} and save["rng"]["seed"] != values["seed"]:
                raise ValueError("Wrong shared fixture seed")
            if command == "prepare":
                return {"save": save, "privileged_fixture": True, "training_allowed": False}
            if command == "reward_fixture":
                command = "load"
                values["save_json"] = self.shared_fixture.read_text()
        return super().request(command, timeout=timeout, **values)
