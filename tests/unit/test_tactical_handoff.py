from __future__ import annotations

import copy
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.adapters.tactical_mock import TacticalHandoffMockEnvironment
from spireshift.cli import main
from spireshift.conformance import run_environment_conformance
from spireshift.core.types import LegalAction, Observation
from spireshift.models import load_model_checkpoint
from spireshift.representations import CompositionalModelInput
from spireshift.tactical_handoff import (
    TacticalMockRunValueModel,
    benchmark_mock_tactical_handoff,
    load_tactical_handoff_report,
    verify_mock_tactical_handoff_report,
    write_tactical_handoff_report,
)
from spireshift.tactical_values import (
    ModelRunValueEstimator,
    TacticalValueConfig,
    evaluate_tactical_leaf,
    model_run_value_estimator_from_checkpoint,
    rank_tactical_actions,
)

REPORT_FIXTURE_PATH = Path("tests/fixtures/tactical-handoff-report-v1.json")
MODEL_CHECKPOINT_PATH = Path("tests/fixtures/model-checkpoint-v1.json")
MODEL_CALIBRATION_PATH = Path("tests/fixtures/model-calibration-v1.json")


class _FirstActionPolicy:
    policy_id = "first-action-test-policy"

    def choose_action(
        self, observation: Observation, legal_actions: Sequence[LegalAction]
    ) -> LegalAction:
        del observation
        return legal_actions[0]


class _LastActionPolicy:
    policy_id = "last-action-test-policy"

    def choose_action(
        self, observation: Observation, legal_actions: Sequence[LegalAction]
    ) -> LegalAction:
        del observation
        return legal_actions[-1]


@dataclass(frozen=True, slots=True)
class _Prediction:
    run_value: float


class _ConstantModel:
    def __init__(self, value: float) -> None:
        self.value = value

    def predict(self, representation: CompositionalModelInput) -> _Prediction:
        del representation
        return _Prediction(self.value)


def test_terminal_value_ranking_reverses_hp_greedy_tradeoffs_within_budget() -> None:
    environment = TacticalHandoffMockEnvironment()
    observation = environment.reset(7)
    config = TacticalValueConfig()

    ranking = rank_tactical_actions(
        environment=environment,
        observation=observation,
        legal_actions=environment.legal_actions(),
        continuation_policy=_FirstActionPolicy(),
        run_value_estimator=ModelRunValueEstimator(
            environment.ruleset,
            TacticalMockRunValueModel(),
            "tactical-handoff-public-state-oracle-v1",
        ),
        config=config,
        seed=7,
    )
    by_action = {
        candidate.source_action_id: candidate.estimated_terminal_victory_probability
        for candidate in ranking.candidates
    }

    assert ranking.objective_id == "terminal-victory-v1"
    assert ranking.selected_action_id == "spend_potion_for_relic"
    assert by_action["take_damage_for_power"] > by_action["preserve_hp"]
    assert by_action["spend_potion_for_relic"] > by_action["preserve_hp"]
    assert ranking.usage.compute_units == 60
    assert ranking.usage.compute_units <= config.maximum_compute_units


def test_tactical_mock_obeys_environment_contract() -> None:
    report = run_environment_conformance(
        TacticalHandoffMockEnvironment,
        seeds=(1, 7),
    )

    assert report.verdict != "fail"
    assert all(check.status != "fail" for check in report.checks)


def test_leaf_representation_preserves_public_resources_and_persistent_mechanics() -> None:
    environment = TacticalHandoffMockEnvironment()
    environment.reset(7)
    action = next(
        action
        for action in environment.legal_actions()
        if action.action_id == "spend_potion_for_relic"
    )
    successor = environment.step(action).next_observation
    estimator = ModelRunValueEstimator(
        environment.ruleset,
        TacticalMockRunValueModel(),
        "tactical-handoff-public-state-oracle-v1",
    )

    estimate = estimator.estimate(successor, environment.legal_actions())

    assert estimate.source_state_hash == successor.state_hash
    assert estimate.terminal_victory_probability == 0.82
    assert {
        "player.hp",
        "player.max_hp",
        "player.gold",
        "player.deck.id[0]",
        "player.relics.id[0]",
        "player.relics.counter[0]",
        "run.permanent_power",
        "run.relic_counter",
        "run.next_options.id[0]",
    } <= set(estimate.represented_state_paths)


def test_exact_terminal_return_overrides_bootstrap_and_local_state() -> None:
    environment = TacticalHandoffMockEnvironment()
    environment.reset(3)
    environment.step(environment.legal_actions()[0])
    terminal = environment.step(environment.legal_actions()[0]).next_observation
    estimator = ModelRunValueEstimator(
        environment.ruleset,
        _ConstantModel(0.99),
        "unused-terminal-estimator",
    )

    breakdown = evaluate_tactical_leaf(
        environment=environment,
        observation=terminal,
        continuation_policy=_FirstActionPolicy(),
        run_value_estimator=estimator,
        config=TacticalValueConfig(),
        seed=3,
    )

    expected = 1.0 if terminal.public_state["victory"] else 0.0
    assert breakdown.estimated_terminal_victory_probability == expected
    assert breakdown.exact_terminal_return == expected
    assert breakdown.bootstrapped_run_value is None
    assert breakdown.truncated_rollout_value is None


def test_truncated_nonterminal_rollout_bootstraps_terminal_run_value() -> None:
    environment = MockSpireEnvironment()
    observation = environment.reset(7)
    estimator = ModelRunValueEstimator(
        environment.ruleset,
        _ConstantModel(0.6),
        "constant-terminal-value-v1",
    )
    config = TacticalValueConfig(
        candidate_worlds=1,
        rollout_samples=2,
        rollout_horizon=1,
        truncated_rollout_weight=1.0,
        bootstrap_weight=1.0,
        maximum_compute_units=16,
    )

    breakdown = evaluate_tactical_leaf(
        environment=environment,
        observation=observation,
        continuation_policy=_FirstActionPolicy(),
        run_value_estimator=estimator,
        config=config,
        seed=7,
    )

    assert breakdown.bootstrapped_run_value == 0.6
    assert breakdown.truncated_rollout_value == 0.6
    assert breakdown.estimated_terminal_victory_probability == pytest.approx(0.6)
    assert breakdown.rollout_terminal_samples == 0
    assert breakdown.rollout_bootstrap_samples == 2


def test_leaf_mixture_keeps_exact_truncated_and_direct_sources_separate() -> None:
    environment = MockSpireEnvironment()
    observation = environment.reset(7)
    estimator = ModelRunValueEstimator(
        environment.ruleset,
        _ConstantModel(0.6),
        "constant-terminal-value-v1",
    )
    config = TacticalValueConfig(
        candidate_worlds=1,
        rollout_samples=16,
        rollout_horizon=1,
        exact_terminal_weight=1.0,
        truncated_rollout_weight=0.5,
        bootstrap_weight=0.5,
        maximum_compute_units=64,
    )

    breakdown = evaluate_tactical_leaf(
        environment=environment,
        observation=observation,
        continuation_policy=_LastActionPolicy(),
        run_value_estimator=estimator,
        config=config,
        seed=7,
    )

    assert breakdown.rollout_terminal_samples == 4
    assert breakdown.rollout_bootstrap_samples == 12
    assert breakdown.rollout_terminal_value == 0.0
    assert breakdown.truncated_rollout_value == pytest.approx(0.6)
    assert breakdown.bootstrapped_run_value == 0.6
    assert breakdown.estimated_terminal_victory_probability == pytest.approx(0.3)


def test_checkpoint_adapter_binds_ruleset_objective_and_optional_calibration() -> None:
    environment = MockSpireEnvironment()
    observation = environment.reset(7)
    checkpoint = load_model_checkpoint(MODEL_CHECKPOINT_PATH)
    calibration = json.loads(MODEL_CALIBRATION_PATH.read_text(encoding="utf-8"))

    raw = model_run_value_estimator_from_checkpoint(
        checkpoint=checkpoint,
        ruleset=environment.ruleset,
    )
    calibrated = model_run_value_estimator_from_checkpoint(
        checkpoint=checkpoint,
        ruleset=environment.ruleset,
        calibration=calibration,
    )

    raw_estimate = raw.estimate(observation, environment.legal_actions())
    calibrated_estimate = calibrated.estimate(observation, environment.legal_actions())
    assert 0.0 <= raw_estimate.terminal_victory_probability <= 1.0
    assert 0.0 <= calibrated_estimate.terminal_victory_probability <= 1.0
    assert raw.estimator_id == checkpoint["model_id"]
    assert calibrated.estimator_id == calibration["calibration_id"]
    with pytest.raises(ValueError, match="ruleset differ"):
        model_run_value_estimator_from_checkpoint(
            checkpoint=checkpoint,
            ruleset=TacticalHandoffMockEnvironment.ruleset,
        )


def test_tactical_ranking_rejects_nonterminal_objective_estimator() -> None:
    environment = TacticalHandoffMockEnvironment()
    observation = environment.reset(7)
    estimator = ModelRunValueEstimator(
        environment.ruleset,
        TacticalMockRunValueModel(),
        "wrong-objective-estimator",
        objective_id="combat-survival-v1",
    )

    with pytest.raises(ValueError, match="terminal-victory"):
        rank_tactical_actions(
            environment=environment,
            observation=observation,
            legal_actions=environment.legal_actions(),
            continuation_policy=_FirstActionPolicy(),
            run_value_estimator=estimator,
            config=TacticalValueConfig(),
            seed=7,
        )


def test_ranking_rejects_incomplete_equal_candidate_budget() -> None:
    environment = TacticalHandoffMockEnvironment()
    observation = environment.reset(7)

    with pytest.raises(ValueError, match="cannot complete equal candidate sampling"):
        rank_tactical_actions(
            environment=environment,
            observation=observation,
            legal_actions=environment.legal_actions(),
            continuation_policy=_FirstActionPolicy(),
            run_value_estimator=ModelRunValueEstimator(
                environment.ruleset,
                TacticalMockRunValueModel(),
                "tactical-handoff-public-state-oracle-v1",
            ),
            config=TacticalValueConfig(maximum_compute_units=32),
            seed=7,
        )


def test_checked_report_is_reproducible_and_tamper_evident(tmp_path: Path) -> None:
    report = benchmark_mock_tactical_handoff()
    checked = json.loads(REPORT_FIXTURE_PATH.read_text(encoding="utf-8"))

    assert report == checked
    assert report["summary"] == {
        "cases": 3,
        "selection_disagreements": 3,
        "damage_tradeoff_cases": 3,
        "potion_tradeoff_cases": 3,
        "terminal_value_selected_actions": [
            "spend_potion_for_relic",
            "take_damage_for_power",
            "spend_potion_for_relic",
        ],
        "local_hp_selected_actions": ["preserve_hp"] * 3,
        "total_compute_units": 180,
    }
    assert verify_mock_tactical_handoff_report(report).valid

    path = tmp_path / "report.json"
    write_tactical_handoff_report(report, path)
    assert load_tactical_handoff_report(path) == report
    tampered = copy.deepcopy(report)
    tampered["cases"][0]["terminal_value_selected_action_id"] = "preserve_hp"
    tampered_path = tmp_path / "tampered.json"
    tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="identity mismatch"):
        load_tactical_handoff_report(tampered_path)
    with pytest.raises(FileExistsError, match="Refusing to replace"):
        write_tactical_handoff_report(tampered, path)


def test_cli_generates_and_verifies_report(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    verification_path = tmp_path / "verification.json"

    generated = main(["tactical-handoff", "benchmark-mock", str(report_path)])
    verified = main(
        [
            "tactical-handoff",
            "verify",
            str(report_path),
            "--output",
            str(verification_path),
        ]
    )

    assert generated == 0
    assert verified == 0
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    assert verification["valid"] is True
    assert verification["errors"] == []
