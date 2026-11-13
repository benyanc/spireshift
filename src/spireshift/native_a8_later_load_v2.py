"""Use the frozen host's file load for prepared A8 starts."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_feedback_host, native_a8_later_start
from spireshift.native_a8_head_policy import HeadState

SCRIPT = "engine-a8-prepared-start-worker-v2.mjs"
PROJECTION = "native_a8_later_act_file_load_v2"


class FileWorker(native_a8_feedback_host.FeedbackWorker):
    def __init__(self, context: dict[str, Any], target: Path) -> None:
        self.prepared_adapter = context["prepared_start_adapter"]
        with patch.multiple(native_a8_feedback_host, SCRIPT=SCRIPT, PROJECTION=PROJECTION):
            super().__init__(context, target)

    def request(self, command: str, *, timeout: float = 20, **values: Any) -> dict[str, Any]:
        if command == "initialize":
            values["spec"] = {**values["spec"], "prepared_start_adapter": self.prepared_adapter}
        return super().request(command, timeout=timeout, **values)


def play(
    context: dict[str, Any],
    task: dict[str, Any],
    start: dict[str, Any],
    target: Path,
    state: HeadState,
    deadline: float,
) -> dict[str, Any]:
    with patch.object(native_a8_later_start, "PreparedWorker", FileWorker):
        return native_a8_later_start.play(context, task, start, target, state, deadline)
