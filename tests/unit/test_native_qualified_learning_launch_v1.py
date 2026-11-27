from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from spireshift.native_qualified_learning_launch_v1 import run_phases


def test_failed_short_control_never_starts_training(tmp_path: Path) -> None:
    commands = []

    def runner(command: list[str], **_: Any) -> Any:
        commands.append(command)
        return SimpleNamespace(returncode=2)

    assert run_phases(tmp_path, False, runner) == 2
    assert [command[-1] for command in commands] == ["short"]


def test_clean_control_is_reverified_without_replaying_games_before_owner_training(
    tmp_path: Path,
) -> None:
    commands = []

    def runner(command: list[str], **_: Any) -> Any:
        commands.append(command)
        return SimpleNamespace(returncode=0)

    assert run_phases(tmp_path, True, runner) == 0
    assert [command[-1] for command in commands] == ["saved", "run"]
