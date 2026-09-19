from pathlib import Path

import pytest

from spireshift.core.objective import ObjectiveSpec, load_objective


def test_default_objective_is_terminal_victory() -> None:
    objective = load_objective(Path("configs/default.toml"))
    assert objective.primary == "terminal_victory"
    assert objective.constraint == "cpu_time_per_run"
    assert objective.auxiliary_reward_allowed is False


def test_auxiliary_reward_is_rejected() -> None:
    with pytest.raises(ValueError, match="Auxiliary metrics"):
        ObjectiveSpec(
            objective_id="invalid",
            primary="terminal_victory",
            constraint="cpu_time_per_run",
            whole_run_budget=10,
            auxiliary=("act_completion",),
            auxiliary_reward_allowed=True,
        )


def test_act_completion_cannot_be_primary() -> None:
    with pytest.raises(ValueError, match="terminal_victory"):
        ObjectiveSpec(
            objective_id="invalid",
            primary="act_completion",
            constraint="cpu_time_per_run",
            whole_run_budget=10,
            auxiliary=(),
            auxiliary_reward_allowed=False,
        )
