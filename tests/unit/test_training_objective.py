from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from spireshift import cli
from spireshift.core.objective import load_objective
from spireshift.training_objective import (
    PANEL_SCHEMA,
    TERMINAL_OBJECTIVE_ID,
    RunStatus,
    TrainingOutcome,
    TrainingPanel,
    TrainingScoreSpec,
    TrainingStage,
    assess_training_graduation,
    load_training_score_spec,
    score_training_outcome,
    score_training_panel,
)

CONFIG = Path("configs/training-objective/sts2-v0.107.1-full-run-bootstrap-v1.json")


def _spec() -> TrainingScoreSpec:
    return load_training_score_spec(CONFIG)


def _outcome(
    seed: int = 0, status: RunStatus = RunStatus.LOSS, acts: int = 0, floor: int = 7
) -> TrainingOutcome:
    return TrainingOutcome(seed, status, acts, floor, 100, 0.5)


def _panel_document(spec: TrainingScoreSpec) -> dict[str, Any]:
    return {
        "schema_version": PANEL_SCHEMA,
        "training_spec_id": spec.spec_id,
        "training_objective_id": spec.training_objective_id,
        "scope": spec.scope.as_dict(),
        "partition": "train",
        "planned_seeds": [0, 1],
        "outcomes": [
            {
                "seed": 0,
                "status": "terminal_loss",
                "completed_acts": 0,
                "maximum_floor": 7,
                "decisions": 100,
                "cpu_seconds": 0.5,
            },
        ],
    }


def test_training_spec_preserves_the_real_evaluation_contract() -> None:
    spec = _spec()
    assert spec.evaluation_objective == load_objective(Path("configs/default.toml"))
    assert spec.training_objective_id != spec.evaluation_objective.objective_id
    assert spec.spec_id == TrainingScoreSpec.from_mapping(spec.as_dict()).spec_id


def test_losses_have_a_monotone_bounded_progress_signal_and_victory_wins() -> None:
    spec = _spec()
    returns = [
        score_training_outcome(spec, _outcome(acts=acts, floor=floor))["training_return"]
        for acts, floor in [(0, 0), (0, 3), (0, 17), (1, 17), (2, 40), (3, 2**31 - 1)]
    ]
    assert returns[0] == 0
    assert all(left < right for left, right in zip(returns, returns[1:], strict=False))
    assert returns[-1] < spec.loss_progress_weight < 1
    win = score_training_outcome(spec, _outcome(status=RunStatus.VICTORY, acts=3, floor=51))
    assert win["training_return"] == win["evaluation_terminal_reward"] == 1
    assert all(
        score_training_outcome(spec, _outcome(floor=floor))["evaluation_terminal_reward"] == 0
        for floor in (0, 7, 17, 50)
    )


def test_act_completion_outranks_floor_only_progress_without_a_hardcoded_floor_limit() -> None:
    spec = _spec()
    before = score_training_outcome(spec, _outcome(floor=2**31 - 1))
    after = score_training_outcome(spec, _outcome(acts=1, floor=0))
    assert after["training_return"] > before["training_return"]


@pytest.mark.parametrize(
    "status",
    [
        status
        for status in RunStatus
        if status != RunStatus.VICTORY and status != RunStatus.LOSS and status != RunStatus.MISSING
    ],
)
def test_failures_never_keep_progress_credit(status: RunStatus) -> None:
    result = score_training_outcome(_spec(), _outcome(status=status, acts=2, floor=40))
    assert result["training_return"] == result["evaluation_terminal_reward"] == 0
    assert not result["completed"]


def test_stalling_and_more_decisions_never_improve_the_score() -> None:
    spec = _spec()
    original = _outcome()
    longer = replace(original, decisions=100000, cpu_seconds=127)
    assert (
        score_training_outcome(spec, original)["training_return"]
        == (score_training_outcome(spec, longer)["training_return"])
    )
    stalled = replace(longer, status=RunStatus.LIVENESS)
    assert score_training_outcome(spec, stalled)["training_return"] == 0


def test_a_reported_victory_over_the_compute_cap_is_a_failed_attempt() -> None:
    outcome = replace(_outcome(status=RunStatus.VICTORY), cpu_seconds=128.001)
    score = score_training_outcome(_spec(), outcome)
    assert score["recorded_status"] == "terminal_victory"
    assert score["status"] == "budget_exhausted"
    assert score["training_return"] == score["evaluation_terminal_reward"] == 0


def test_missing_failed_and_capped_outcomes_remain_in_the_denominator() -> None:
    outcomes = (
        _outcome(0, RunStatus.VICTORY),
        _outcome(1),
        _outcome(2, RunStatus.ERROR),
        replace(_outcome(3, RunStatus.VICTORY), cpu_seconds=129),
    )
    result = score_training_panel(_spec(), TrainingPanel("train", tuple(range(5)), outcomes))
    summary = result["summary"]
    assert summary["benchmark_denominator"] == 5
    assert summary["recorded_runs"] == 4
    assert summary["completed_runs"] == 2
    assert summary["failed_runs"] == 3
    assert summary["missing_runs"] == 1
    assert summary["victory_rate"] == 0.2
    assert len(result["outcomes"]) == 5
    assert summary["recorded_cpu_seconds"] == 130.5
    assert not result["foundation_readiness_established"]


def test_population_ranking_never_trades_a_higher_win_rate_for_floor_points() -> None:
    spec = _spec()
    seeds = tuple(range(128))
    floor_player = TrainingPanel(
        "train", seeds, tuple(_outcome(seed, acts=3, floor=1000) for seed in seeds)
    )
    winning_player = TrainingPanel(
        "train",
        seeds,
        tuple(
            _outcome(seed, RunStatus.VICTORY if seed == 0 else RunStatus.LOSS, floor=0)
            for seed in seeds
        ),
    )
    losing = score_training_panel(spec, floor_player)["summary"]
    winning = score_training_panel(spec, winning_player)["summary"]
    assert losing["mean_training_return"] > winning["mean_training_return"]
    assert winning["fitness_rank"] > losing["fitness_rank"]


def test_terminal_only_stage_removes_all_progress_preferences() -> None:
    spec = replace(
        _spec(),
        training_objective_id=TERMINAL_OBJECTIVE_ID,
        stage=TrainingStage.TERMINAL,
        loss_progress_weight=0.0,
    )
    early = score_training_panel(spec, TrainingPanel("train", (0,), (_outcome(floor=1),)))
    late = score_training_panel(spec, TrainingPanel("train", (0,), (_outcome(acts=2, floor=40),)))
    assert early["summary"]["fitness_rank"] == late["summary"]["fitness_rank"]
    assert early["summary"]["mean_training_return"] == 0
    assert TrainingScoreSpec.from_mapping(spec.as_dict()) == spec


@pytest.mark.parametrize(
    "field,value",
    [
        ("stage", "terminal_only"),
        ("training_objective_id", "terminal-victory-v1"),
        ("discount_factor", 0.99),
        ("discount_factor", True),
        ("population_ranking", "mean_training_return"),
        ("hidden_state", {}),
    ],
)
def test_unversioned_or_unsafe_contract_changes_are_rejected(field: str, value: Any) -> None:
    document = _spec().as_dict()
    document[field] = value
    with pytest.raises(ValueError):
        TrainingScoreSpec.from_mapping(document)


@pytest.mark.parametrize(
    "field,value",
    [
        ("total_acts", True),
        ("floor_scale", 0),
        ("loss_progress_weight", 1),
        ("loss_progress_weight", float("nan")),
        ("loss_progress_weight", float("inf")),
    ],
)
def test_invalid_normalization_is_rejected(field: str, value: Any) -> None:
    document = _spec().as_dict()
    document["progress"][field] = value
    with pytest.raises(ValueError):
        TrainingScoreSpec.from_mapping(document)


def test_progress_configuration_changes_have_different_identities() -> None:
    first = _spec()
    assert replace(first, floor_scale=32).spec_id != first.spec_id
    assert replace(first, loss_progress_weight=0.1).spec_id != first.spec_id


@pytest.mark.parametrize(
    "field,value",
    [
        ("maximum_floor", -1),
        ("maximum_floor", 2**31),
        ("completed_acts", True),
        ("cpu_seconds", float("nan")),
        ("cpu_seconds", float("inf")),
        ("cpu_seconds", -1),
        ("status", "won_act_one"),
        ("hidden_rng", 5),
    ],
)
def test_malformed_or_privileged_outcome_fields_are_rejected(field: str, value: Any) -> None:
    document = _panel_document(_spec())["outcomes"][0]
    document[field] = value
    with pytest.raises(ValueError):
        TrainingOutcome.from_mapping(document)


def test_impossible_act_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="completed_acts"):
        score_training_outcome(_spec(), _outcome(acts=4))


@pytest.mark.parametrize(
    "field,value",
    [
        ("training_spec_id", "sha256:" + "0" * 64),
        ("partition", "test"),
        ("planned_seeds", [0, 0]),
        ("planned_seeds", []),
        ("planned_seeds", [1]),
        ("planned_seeds", [{}]),
        ("training_objective_id", "terminal-victory-v1"),
    ],
)
def test_panel_identity_ownership_and_plan_validation(field: str, value: Any) -> None:
    spec = _spec()
    document = _panel_document(spec)
    document[field] = value
    with pytest.raises(ValueError):
        TrainingPanel.from_mapping(document, spec)


def test_duplicate_outcomes_and_changed_scope_are_rejected() -> None:
    spec = _spec()
    document = _panel_document(spec)
    document["outcomes"] *= 2
    with pytest.raises(ValueError, match="duplicate outcomes"):
        TrainingPanel.from_mapping(document, spec)
    document = _panel_document(spec)
    document["scope"]["ascension"] = 1
    with pytest.raises(ValueError, match="scope mismatch"):
        TrainingPanel.from_mapping(document, spec)


def test_graduation_needs_disjoint_confirmed_wins_and_never_starts_a_job() -> None:
    spec = _spec()
    train = TrainingPanel(
        "train", (0, 1, 2), tuple(_outcome(seed, RunStatus.VICTORY) for seed in range(3))
    )
    dev = TrainingPanel(
        "development",
        tuple(range(100, 164)),
        tuple(
            _outcome(seed, RunStatus.VICTORY if seed < 103 else RunStatus.LOSS)
            for seed in range(100, 164)
        ),
    )
    assessment = assess_training_graduation(spec, train, dev)
    assert assessment["terminal_only_stage_recommended"]
    assert not assessment["next_stage_started"]
    assert not assessment["foundation_readiness_established"]
    missing = replace(dev, outcomes=dev.outcomes[:-1])
    assert not assess_training_graduation(spec, train, missing)["terminal_only_stage_recommended"]
    no_wins = replace(train, outcomes=tuple(_outcome(seed) for seed in range(3)))
    assert not assess_training_graduation(spec, no_wins, dev)["terminal_only_stage_recommended"]
    overlapping = replace(dev, planned_seeds=(0, 1, 2), outcomes=())
    with pytest.raises(ValueError, match="disjoint"):
        assess_training_graduation(spec, train, overlapping)


def test_cli_only_scores_saved_inputs_and_does_not_create_an_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("score command must never create environments or run games")

    monkeypatch.setattr(cli, "load_evangambit_backend", forbidden)
    monkeypatch.setattr(cli, "MockSpireEnvironment", forbidden)
    monkeypatch.setattr(cli, "run_episode", forbidden)
    panel = tmp_path / "panel.json"
    panel.write_text(json.dumps(_panel_document(_spec())))
    assert cli.main(["objective", "inspect", str(CONFIG)]) == 0
    inspection = json.loads(capsys.readouterr().out)
    assert inspection["training_spec_id"] == _spec().spec_id
    assert cli.main(["objective", "score", str(CONFIG), str(panel)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["summary"]["benchmark_denominator"] == 2
    assert result["summary"]["missing_runs"] == 1
    document = _panel_document(_spec())
    document["scope"]["character"] = "different"
    panel.write_text(json.dumps(document))
    assert cli.main(["objective", "score", str(CONFIG), str(panel)]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "error"


def test_cli_never_overwrites_existing_scoring_results(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    panel = tmp_path / "panel.json"
    panel.write_text(json.dumps(_panel_document(_spec())))
    output = tmp_path / "score.json"
    args = ["objective", "score", str(CONFIG), str(panel), "--output", str(output)]
    assert cli.main(args) == 0
    before = output.read_bytes()
    capsys.readouterr()
    assert cli.main(args) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "error"
    assert output.read_bytes() == before
