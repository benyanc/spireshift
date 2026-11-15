from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from jsonschema import Draft202012Validator

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.agents.learned import ProductionCheckpointPolicy, ProductionPolicyDecision
from spireshift.cli import build_parser
from spireshift.core.manifest import manifest_identifier
from spireshift.core.types import LegalAction, Observation, Transition
from spireshift.splits import SplitName, load_split_manifest
from spireshift.terminal_discovery import (
    ExplorationProfile,
    TerminalDiscoveryConfig,
    load_terminal_discovery_config,
    run_terminal_trajectory_discovery,
    verify_terminal_trajectory_discovery,
)

MOCK_SPLIT_PATH = Path("manifests/splits/mock-v1-seeds-000000-000999-v1.json")


class _OneDecisionDiscoveryEnvironment(MockSpireEnvironment):
    def legal_actions(self) -> tuple[LegalAction, ...]:
        if self._state.terminal:
            return ()
        return (
            LegalAction("argmax-defeat", "choose", {}),
            LegalAction("explored-victory", "choose", {}),
        )

    def step(self, action: LegalAction) -> Transition:
        observation = self._observation()
        legal = {candidate.action_id: candidate for candidate in self.legal_actions()}
        if action.action_id not in legal:
            raise ValueError(f"Illegal action: {action.action_id}")
        self._state.terminal = True
        self._state.victory = action.action_id == "explored-victory"
        next_observation = self._observation()
        return Transition(
            observation=observation,
            action=legal[action.action_id],
            next_observation=next_observation,
            reward=1.0 if self._state.victory else 0.0,
            terminal=True,
            victory=self._state.victory,
        )


class _ArgmaxDefeatPolicy:
    def __init__(self, *, split_manifest_id: str) -> None:
        self.model_id = manifest_identifier({"model": "argmax-defeat"})
        self.policy_id = f"production-checkpoint-policy-v1:{self.model_id}"
        self.split_manifest_id = split_manifest_id
        self.ruleset = MockSpireEnvironment.ruleset

    def predict(
        self, observation: Observation, legal_actions: Sequence[LegalAction]
    ) -> ProductionPolicyDecision:
        del observation
        actions = tuple(legal_actions)
        return ProductionPolicyDecision(
            representation_hash=manifest_identifier(
                {"actions": [action.action_id for action in actions]}
            ),
            source_action_ids=tuple(action.action_id for action in actions),
            selected_candidate_index=0,
            selected_action=actions[0],
            policy=(0.9, 0.1),
            terminal_value=None,
            tactical_death_risk=(0.0, 0.0),
            maximum_floor_reach={},
            inference_seconds=0.0,
        )


def _config(policy: _ArgmaxDefeatPolicy, training_report_id: str) -> TerminalDiscoveryConfig:
    return TerminalDiscoveryConfig(
        split_manifest_id=policy.split_manifest_id,
        ruleset_manifest_id=policy.ruleset.manifest_id,
        model_id=policy.model_id,
        training_report_id=training_report_id,
        run_offset=0,
        run_count=2,
        attempts_per_profile=2,
        workers=2,
        maximum_decisions_per_run=8,
        cycle_repetition_threshold=3,
        liveness_tail_length=4,
        no_op_fallback_threshold=2,
        sampling_salt="terminal-discovery-test",
        profiles=(ExplorationProfile("always-explore", 1.0, 1.0),),
    )


def test_sparse_exploration_discovers_and_verifies_terminal_positive_runs(
    tmp_path: Path,
) -> None:
    split = load_split_manifest(MOCK_SPLIT_PATH)
    policy = _ArgmaxDefeatPolicy(split_manifest_id=split.manifest_id)
    training_report_id = manifest_identifier({"report": "argmax-defeat"})
    config = _config(policy, training_report_id)
    output = tmp_path / "discovery"
    timestamps = iter(("2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z"))

    result = run_terminal_trajectory_discovery(
        environment_factory=_OneDecisionDiscoveryEnvironment,
        ruleset=policy.ruleset,
        policy=cast(ProductionCheckpointPolicy, policy),
        split_manifest=split,
        training_report_id=training_report_id,
        config=config,
        output_directory=output,
        now=lambda: next(timestamps),
    )

    overall = result.report["summary"]["overall"]
    assert result.successful is True
    assert overall["benchmark_denominator"] == 4
    assert overall["victories"] == 4
    assert overall["exploration_invocations"] == 4
    assert overall["non_argmax_actions"] == 4
    assert len(result.report["winning_cases"]) == 4
    assert result.report["readiness"] == {
        "terminal_positive_trajectories_found": True,
        "terminal_value_head_unblocked": False,
        "recommended_next_step": "replay_and_label_winning_trajectories",
    }
    case_ids = []
    case_schema = json.loads(Path("schemas/terminal-trajectory-discovery-case-v1.json").read_text())
    for reference in result.report["cases"]:
        case = json.loads((output / reference["path"]).read_text())
        Draft202012Validator(case_schema).validate(case)
        assert case["decisions"][0]["argmax_action_id"] == "argmax-defeat"
        assert case["decisions"][0]["selected_action_id"] == "explored-victory"
        case_ids.append(case["case_id"])

    verification = verify_terminal_trajectory_discovery(
        result.report_path,
        config=config,
        split_manifest=split,
    )
    assert verification["valid"] is True
    assert verification["verified_cases"] == 4

    result.report_path.unlink()
    resumed_timestamps = iter(("2026-01-02T00:00:00Z", "2026-01-02T00:00:01Z"))
    resumed = run_terminal_trajectory_discovery(
        environment_factory=_OneDecisionDiscoveryEnvironment,
        ruleset=policy.ruleset,
        policy=cast(ProductionCheckpointPolicy, policy),
        split_manifest=split,
        training_report_id=training_report_id,
        config=config,
        output_directory=output,
        resume=True,
        now=lambda: next(resumed_timestamps),
    )
    assert [reference["case_id"] for reference in resumed.report["cases"]] == case_ids


def test_terminal_discovery_config_and_cli_are_frozen(tmp_path: Path) -> None:
    split = load_split_manifest(MOCK_SPLIT_PATH)
    policy = _ArgmaxDefeatPolicy(split_manifest_id=split.manifest_id)
    config = _config(policy, manifest_identifier({"report": "frozen"}))
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config.as_dict()), encoding="utf-8")

    assert load_terminal_discovery_config(config_path) == config
    config_schema = json.loads(
        Path("schemas/terminal-trajectory-discovery-config-v1.json").read_text()
    )
    Draft202012Validator(config_schema).validate(config.as_dict())
    parsed = build_parser().parse_args(
        [
            "model",
            "discover-terminal-trajectories",
            str(config_path),
            "checkpoint.json",
            "--report",
            "training-report.json",
            "--split-manifest",
            str(MOCK_SPLIT_PATH),
            "--upstream-root",
            "upstream",
            "--manifest",
            "manifest.json",
            "--output-dir",
            "output",
        ]
    )
    assert parsed.model_command == "discover-terminal-trajectories"
    assert split.split_for_seed(split.seeds(SplitName.TRAIN)[0]) is SplitName.TRAIN
