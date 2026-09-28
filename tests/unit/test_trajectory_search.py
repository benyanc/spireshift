from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Self, cast

from jsonschema import Draft202012Validator

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.agents.learned import ProductionCheckpointPolicy, ProductionPolicyDecision
from spireshift.cli import build_parser
from spireshift.core.manifest import manifest_identifier
from spireshift.core.types import DecisionType, LegalAction, Observation, Transition
from spireshift.splits import SplitName, load_split_manifest
from spireshift.trajectory_search import (
    Act1Milestones,
    TrajectorySearchConfig,
    load_trajectory_search_config,
    run_trajectory_search,
    verify_trajectory_search,
)

MOCK_SPLIT_PATH = Path("manifests/splits/mock-v1-seeds-000000-000999-v1.json")


class _MilestoneEnvironment:
    patch_id = MockSpireEnvironment.patch_id
    ruleset = MockSpireEnvironment.ruleset

    def __init__(self) -> None:
        self._stage = 0
        self._terminal = False

    def reset(self, seed: int) -> Observation:
        del seed
        self._stage = 0
        self._terminal = False
        return self._observation()

    def legal_actions(self) -> tuple[LegalAction, ...]:
        if self._terminal:
            return ()
        if self._stage == 0:
            return (
                LegalAction("early-defeat", "choose", {}),
                LegalAction("coherent-route", "choose", {}),
            )
        return (LegalAction("enter-next-act", "choose", {}),)

    def step(self, action: LegalAction) -> Transition:
        source = self._observation()
        legal = {candidate.action_id: candidate for candidate in self.legal_actions()}
        selected = legal[action.action_id]
        if action.action_id == "early-defeat":
            self._terminal = True
        elif action.action_id == "coherent-route":
            self._stage = 1
        else:
            self._stage = 2
            self._terminal = True
        return Transition(
            observation=source,
            action=selected,
            next_observation=self._observation(),
            reward=0.0,
            terminal=self._terminal,
            victory=False,
        )

    def close(self) -> None:
        return None

    def clone(self, *, resample_hidden: bool, seed: int | None = None) -> Self:
        del resample_hidden, seed
        cloned = type(self)()
        cloned._stage = self._stage
        cloned._terminal = self._terminal
        return cloned

    def _observation(self) -> Observation:
        public_state = {
            "floor": 0 if self._stage == 0 else 17,
            "act": "hive" if self._stage == 2 else "overgrowth",
            "terminal": self._terminal,
            "victory": False,
        }
        digest = hashlib.sha256(
            json.dumps(public_state, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return Observation(
            schema_version="observation-v1",
            patch_id=self.patch_id,
            decision_type=DecisionType.TERMINAL if self._terminal else DecisionType.PATH,
            public_state=public_state,
            state_hash=digest,
        )


class _EarlyDefeatPolicy:
    def __init__(self, *, split_manifest_id: str) -> None:
        self.model_id = manifest_identifier({"model": "early-defeat"})
        self.policy_id = f"production-checkpoint-policy-v1:{self.model_id}"
        self.split_manifest_id = split_manifest_id
        self.ruleset = MockSpireEnvironment.ruleset

    def predict(
        self, observation: Observation, legal_actions: Sequence[LegalAction]
    ) -> ProductionPolicyDecision:
        del observation
        actions = tuple(legal_actions)
        policy = (0.9, 0.1) if len(actions) == 2 else (1.0,)
        return ProductionPolicyDecision(
            representation_hash=manifest_identifier(
                {"actions": [action.action_id for action in actions]}
            ),
            source_action_ids=tuple(action.action_id for action in actions),
            selected_candidate_index=0,
            selected_action=actions[0],
            policy=policy,
            terminal_value=None,
            tactical_death_risk=tuple(0.0 for _ in actions),
            maximum_floor_reach={},
            inference_seconds=0.0,
        )


def _config(policy: _EarlyDefeatPolicy, training_report_id: str) -> TrajectorySearchConfig:
    return TrajectorySearchConfig(
        split_manifest_id=policy.split_manifest_id,
        ruleset_manifest_id=policy.ruleset.manifest_id,
        model_id=policy.model_id,
        training_report_id=training_report_id,
        run_offset=0,
        run_count=2,
        generations=2,
        beam_width=2,
        mutations_per_parent=2,
        workers=2,
        maximum_decisions_per_run=8,
        cycle_repetition_threshold=3,
        liveness_tail_length=4,
        no_op_fallback_threshold=2,
        mutation_salt="trajectory-search-test",
        milestones=Act1Milestones(
            first_act_ids=("overgrowth", "underdocks"),
            next_act_id="hive",
            boss_floor=17,
        ),
    )


def test_trajectory_search_retains_act1_clear_and_verifies(tmp_path: Path) -> None:
    split = load_split_manifest(MOCK_SPLIT_PATH)
    policy = _EarlyDefeatPolicy(split_manifest_id=split.manifest_id)
    training_report_id = manifest_identifier({"report": "early-defeat"})
    config = _config(policy, training_report_id)
    output = tmp_path / "search"
    timestamps = iter(("2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z"))

    result = run_trajectory_search(
        environment_factory=_MilestoneEnvironment,
        ruleset=policy.ruleset,
        policy=cast(ProductionCheckpointPolicy, policy),
        split_manifest=split,
        training_report_id=training_report_id,
        config=config,
        output_directory=output,
        now=lambda: next(timestamps),
    )

    assert result.successful is True
    assert result.report["hidden_state_resampling"] is False
    assert result.report["summary"]["baseline"]["act1_clears"] == 0
    assert result.report["summary"]["best"]["boss_reaches"] == 2
    assert result.report["summary"]["best"]["act1_clears"] == 2
    assert result.report["summary"]["paired"]["seeds_regressed"] == 0
    assert result.report["readiness"]["recommended_next_step"] == (
        "replay_and_label_act1_milestones"
    )
    report_schema = json.loads(Path("schemas/run-level-trajectory-search-v1.json").read_text())
    Draft202012Validator(report_schema).validate(result.report)
    case_schema = json.loads(Path("schemas/run-level-trajectory-search-case-v1.json").read_text())
    case_ids = []
    for reference in result.report["cases"]:
        case = json.loads((output / reference["path"]).read_text())
        Draft202012Validator(case_schema).validate(case)
        baseline = case["trajectories"][0]
        assert all(
            decision["selection_source"] == "base_policy" for decision in baseline["decisions"]
        )
        ranks = [tuple(generation["incumbent_rank"]) for generation in case["generations"]]
        assert ranks == sorted(ranks)
        case_ids.append(case["case_id"])

    verification = verify_trajectory_search(
        result.report_path,
        config=config,
        split_manifest=split,
    )
    assert verification["valid"] is True
    assert verification["verified_cases"] == 2
    verification_schema = json.loads(
        Path("schemas/run-level-trajectory-search-verification-v1.json").read_text()
    )
    Draft202012Validator(verification_schema).validate(verification)

    result.report_path.unlink()
    resumed_times = iter(("2026-01-02T00:00:00Z", "2026-01-02T00:00:01Z"))
    resumed = run_trajectory_search(
        environment_factory=_MilestoneEnvironment,
        ruleset=policy.ruleset,
        policy=cast(ProductionCheckpointPolicy, policy),
        split_manifest=split,
        training_report_id=training_report_id,
        config=config,
        output_directory=output,
        resume=True,
        now=lambda: next(resumed_times),
    )
    assert [reference["case_id"] for reference in resumed.report["cases"]] == case_ids


def test_trajectory_search_config_and_cli_are_frozen(tmp_path: Path) -> None:
    split = load_split_manifest(MOCK_SPLIT_PATH)
    policy = _EarlyDefeatPolicy(split_manifest_id=split.manifest_id)
    config = _config(policy, manifest_identifier({"report": "frozen"}))
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config.as_dict()), encoding="utf-8")

    assert load_trajectory_search_config(config_path) == config
    config_schema = json.loads(
        Path("schemas/run-level-trajectory-search-config-v2.json").read_text()
    )
    Draft202012Validator(config_schema).validate(config.as_dict())
    parsed = build_parser().parse_args(
        [
            "model",
            "search-run-trajectories",
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
    assert parsed.model_command == "search-run-trajectories"
    assert split.split_for_seed(split.seeds(SplitName.TRAIN)[0]) is SplitName.TRAIN
