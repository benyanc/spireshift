"""Select qualified normal-start delivery without diagnostic fixture capabilities."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import (
    native_a8_head_policy,
    native_a8_own_experience,
    native_lifecycle_worker,
    native_win4_game,
)
from spireshift.native_combat_intent_model import using_intent_encoder
from spireshift.native_lifecycle_worker import LifecycleWorker
from spireshift.native_systematic_selectors_v2 import SelectorBridge

SCRIPT = "engine-qualified-learning-worker-v1.mjs"
CONTRACT = "qualified_full_menu_model_owned_normal_start_v1"


class LearningWorker(LifecycleWorker):
    def __init__(self, ctx: dict[str, Any], target: Path) -> None:
        with patch.object(native_lifecycle_worker, "SCRIPT", SCRIPT):
            super().__init__(ctx, target, fixture=False)

    def request(self, command: str, *, timeout: float = 20, **values: Any) -> dict[str, Any]:
        if command == "initialize":
            values["spec"] = {
                **values["spec"],
                "selector_fixture": False,
                "qualified_learning_contract": CONTRACT,
            }
        return super().request(command, timeout=timeout, **values)


def play(
    ctx: dict[str, Any],
    task: dict[str, Any],
    directory: Path,
    state: native_a8_head_policy.HeadState,
    deadline: float,
) -> dict[str, Any]:
    with (
        using_intent_encoder(),
        patch.multiple(
            native_a8_own_experience, worker=LearningWorker, policy=native_a8_head_policy.policy
        ),
        patch.object(native_win4_game, "JsonLines", SelectorBridge),
    ):
        return native_a8_own_experience.play(ctx, task, directory, state.model, deadline)
