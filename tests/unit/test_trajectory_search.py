from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, Self, cast

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.agents.learned import ProductionCheckpointPolicy, ProductionPolicyDecision
from spireshift.cli import build_parser
from spireshift.core.manifest import manifest_identifier
from spireshift.core.types import DecisionType, LegalAction, Observation, Transition
from spireshift.splits import SplitName, load_split_manifest
from spireshift.trajectory_preferences import (
    TRAJECTORY_PREFERENCE_COLLECTION_FILENAME,
    freeze_trajectory_mutation_preference_collection,
    freeze_trajectory_mutation_preferences,
    verify_trajectory_mutation_preference_collection,
    verify_trajectory_mutation_preferences,
)
from spireshift.trajectory_search import (
    LEGACY_ENEMY_SNAPSHOT_RULE,
    PUBLIC_FRONTIER_DIVERSE_STRATEGY,
    PUBLIC_FRONTIER_STRATEGY,
    Act1Milestones,
    PublicFrontierRanking,
    TrajectorySearchConfig,
    _public_frontier_summary,
    _select_beam,
    compare_trajectory_search_ablation,
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


def _frontier_config(
    policy: _EarlyDefeatPolicy,
    training_report_id: str,
    *,
    strategy: str = PUBLIC_FRONTIER_STRATEGY,
) -> TrajectorySearchConfig:
    return replace(
        _config(policy, training_report_id),
        frontier_ranking=PublicFrontierRanking(
            strategy=strategy,
            enemy_hp_offset=80,
            enemy_slot_size=15,
            maximum_enemy_slots=6,
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

    parsed_comparison = build_parser().parse_args(
        [
            "model",
            "compare-run-trajectory-search",
            "legacy.json",
            "frontier.json",
            "diverse.json",
            "--legacy-config",
            "legacy-config.json",
            "--frontier-config",
            "frontier-config.json",
            "--diverse-config",
            "diverse-config.json",
            "--split-manifest",
            str(MOCK_SPLIT_PATH),
        ]
    )
    assert parsed_comparison.model_command == "compare-run-trajectory-search"

    retired_frontier = load_trajectory_search_config(
        Path("configs/trajectory-search/sts2-v0.107.1-base-v2-act1-frontier-score-train-v3.json")
    )
    retired_diverse = load_trajectory_search_config(
        Path("configs/trajectory-search/sts2-v0.107.1-base-v2-act1-frontier-diverse-train-v3.json")
    )
    production_frontier = load_trajectory_search_config(
        Path("configs/trajectory-search/sts2-v0.107.1-base-v2-act1-frontier-score-train-v4.json")
    )
    production_diverse = load_trajectory_search_config(
        Path("configs/trajectory-search/sts2-v0.107.1-base-v2-act1-frontier-diverse-train-v4.json")
    )
    assert retired_frontier.frontier_ranking is not None
    assert retired_frontier.frontier_ranking.enemy_snapshot_rule == LEGACY_ENEMY_SNAPSHOT_RULE
    assert retired_diverse.frontier_ranking is not None
    assert retired_frontier.config_id == (
        "sha256:d85daa391dd41d81f6a4c183b7ac4f08768d7b89fb7511f640000adecbddc1ef"
    )
    assert retired_diverse.config_id == (
        "sha256:922617859a45e832329683bc19bb316d706d517037f88ae344abb69d27277db3"
    )
    assert production_frontier.frontier_ranking is not None
    assert production_frontier.frontier_ranking.strategy == PUBLIC_FRONTIER_STRATEGY
    assert production_diverse.frontier_ranking is not None
    assert production_diverse.frontier_ranking.strategy == PUBLIC_FRONTIER_DIVERSE_STRATEGY
    assert production_frontier.config_id == (
        "sha256:f4686a81461f368731cdd64da4652242ffb2c4d8ac848c471d1fcf10e4ec527d"
    )
    assert production_diverse.config_id == (
        "sha256:1c2033da21d6abb694523f6d61f229e66b2d2ea32877b28e72afe101adb935c0"
    )


def test_public_frontier_records_health_enemy_progress_and_strategic_trace() -> None:
    ranking = PublicFrontierRanking(
        strategy=PUBLIC_FRONTIER_STRATEGY,
        enemy_hp_offset=80,
        enemy_slot_size=15,
        maximum_enemy_slots=6,
    )

    def observation(*, hp: int, enemy_hp: int, terminal: bool, suffix: str) -> Observation:
        vector = [0] * 96
        vector[80] = enemy_hp
        public_state = {
            "floor": 5,
            "act": "overgrowth",
            "phase": "combat" if not terminal else "complete",
            "terminal": terminal,
            "victory": False,
            "player_hp": hp,
            "player_max_hp": 80,
            "enemy_def_ids": [101],
            "encounter_id": 7,
            "encounter": "synthetic",
            "observation_vector": vector,
            "suffix": suffix,
        }
        state_hash = hashlib.sha256(
            json.dumps(public_state, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return Observation(
            schema_version="observation-v1",
            patch_id=MockSpireEnvironment.patch_id,
            decision_type=DecisionType.TERMINAL if terminal else DecisionType.COMBAT,
            public_state=public_state,
            state_hash=state_hash,
        )

    initial = observation(hp=60, enemy_hp=100, terminal=False, suffix="initial")
    progressed = observation(hp=50, enemy_hp=20, terminal=False, suffix="progressed")
    final = observation(hp=0, enemy_hp=0, terminal=True, suffix="terminal-cleanup")
    records = [
        {
            "decision_index": 0,
            "decision_type": DecisionType.PATH.value,
            "selected_action_id": "choose-risky-route",
            "source_floor": 5,
        }
    ]

    frontier = _public_frontier_summary(
        observations=[initial, progressed, final],
        records=records,
        maximum_floor=5,
        ranking=ranking,
    )

    assert frontier["information_policy_id"] == "public-state-v1"
    assert frontier["player_hp_fraction"] == 0.0
    assert frontier["last_actionable_player_hp_fraction"] == 0.625
    assert frontier["enemy_hp_current"] == 20
    assert frontier["enemy_hp_reference"] == 100
    assert frontier["enemy_hp_defeated_fraction"] == 0.8
    assert frontier["living_enemy_count"] == 1
    assert frontier["enemy_snapshot_state_hash"] == progressed.state_hash
    assert frontier["enemy_snapshot_state_hash"] == frontier["last_actionable_state_hash"]
    assert frontier["strategic_trace_sha256"].startswith("sha256:")

    retired = _public_frontier_summary(
        observations=[initial, progressed, final],
        records=records,
        maximum_floor=5,
        ranking=replace(ranking, enemy_snapshot_rule=LEGACY_ENEMY_SNAPSHOT_RULE),
    )
    assert retired["enemy_hp_current"] == 0
    assert retired["enemy_hp_defeated_fraction"] == 1.0
    assert retired["enemy_snapshot_state_hash"] == final.state_hash


def test_public_frontier_ranking_prefers_progress_and_diversifies_strategic_traces() -> None:
    split = load_split_manifest(MOCK_SPLIT_PATH)
    policy = _EarlyDefeatPolicy(split_manifest_id=split.manifest_id)
    report_id = manifest_identifier({"report": "frontier-ranking"})
    score_config = _frontier_config(policy, report_id)
    diverse_config = _frontier_config(
        policy,
        report_id,
        strategy=PUBLIC_FRONTIER_DIVERSE_STRATEGY,
    )

    def trajectory(
        name: str, *, enemy_progress: float, hp: float, strategic_trace: str
    ) -> dict[str, Any]:
        digest = manifest_identifier({"trace": name})
        return {
            "trajectory_id": manifest_identifier({"trajectory": name}),
            "victory": False,
            "act1_cleared": False,
            "boss_reached": False,
            "maximum_floor": 10,
            "action_trace_sha256": digest,
            "public_frontier": {
                "encounter_cleared": False,
                "enemy_hp_defeated_fraction": enemy_progress,
                "player_hp_fraction": hp,
                "last_actionable_player_hp_fraction": hp,
                "distinct_public_states_on_floor": 5,
                "strategic_trace_sha256": strategic_trace,
            },
        }

    shared = manifest_identifier({"strategic": "shared"})
    distinct = manifest_identifier({"strategic": "distinct"})
    best = trajectory("best", enemy_progress=0.9, hp=0.4, strategic_trace=shared)
    healthier = trajectory("healthier", enemy_progress=0.8, hp=0.8, strategic_trace=shared)
    diverse = trajectory("diverse", enemy_progress=0.7, hp=0.5, strategic_trace=distinct)

    assert _select_beam([best, healthier, diverse], config=score_config) == [best, healthier]
    assert _select_beam([best, healthier, diverse], config=diverse_config) == [best, diverse]


def test_frontier_search_artifacts_validate_and_tampering_is_rejected(tmp_path: Path) -> None:
    split = load_split_manifest(MOCK_SPLIT_PATH)
    policy = _EarlyDefeatPolicy(split_manifest_id=split.manifest_id)
    training_report_id = manifest_identifier({"report": "frontier-artifact"})
    config = _frontier_config(policy, training_report_id)
    output = tmp_path / "frontier-search"
    timestamps = iter(("2026-01-03T00:00:00Z", "2026-01-03T00:00:01Z"))

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

    Draft202012Validator(
        json.loads(Path("schemas/run-level-trajectory-search-v3.json").read_text())
    ).validate(result.report)
    case_path = output / result.report["cases"][0]["path"]
    case = json.loads(case_path.read_text())
    Draft202012Validator(
        json.loads(Path("schemas/run-level-trajectory-search-case-v3.json").read_text())
    ).validate(case)
    verification = verify_trajectory_search(
        result.report_path,
        config=config,
        split_manifest=split,
    )
    assert verification["valid"] is True
    Draft202012Validator(
        json.loads(Path("schemas/run-level-trajectory-search-verification-v3.json").read_text())
    ).validate(verification)

    original_case_ids = [reference["case_id"] for reference in result.report["cases"]]
    result.report_path.unlink()
    resumed_timestamps = iter(("2026-01-03T00:01:00Z", "2026-01-03T00:01:01Z"))
    resumed = run_trajectory_search(
        environment_factory=_MilestoneEnvironment,
        ruleset=policy.ruleset,
        policy=cast(ProductionCheckpointPolicy, policy),
        split_manifest=split,
        training_report_id=training_report_id,
        config=config,
        output_directory=output,
        resume=True,
        now=resumed_timestamps.__next__,
    )
    assert [reference["case_id"] for reference in resumed.report["cases"]] == original_case_ids

    case["trajectories"][0]["public_frontier"]["hidden_rng"] = 0.5
    case_path.write_text(json.dumps(case), encoding="utf-8")
    rejected = verify_trajectory_search(
        result.report_path,
        config=config,
        split_manifest=split,
    )
    assert rejected["valid"] is False


def test_strict_trajectory_preferences_replay_lineage_and_reject_tampering(
    tmp_path: Path,
) -> None:
    split = load_split_manifest(MOCK_SPLIT_PATH)
    policy = _EarlyDefeatPolicy(split_manifest_id=split.manifest_id)
    training_report_id = manifest_identifier({"report": "trajectory-preferences"})
    config = _frontier_config(policy, training_report_id)
    search_output = tmp_path / "preference-search"
    timestamps = iter(("2026-01-04T00:00:00Z", "2026-01-04T00:00:01Z"))
    result = run_trajectory_search(
        environment_factory=_MilestoneEnvironment,
        ruleset=policy.ruleset,
        policy=cast(ProductionCheckpointPolicy, policy),
        split_manifest=split,
        training_report_id=training_report_id,
        config=config,
        output_directory=search_output,
        now=lambda: next(timestamps),
    )
    reference = result.report["cases"][0]
    case = json.loads((search_output / reference["path"]).read_text(encoding="utf-8"))
    preference_path = tmp_path / "trajectory-preferences.json"
    document = freeze_trajectory_mutation_preferences(
        search_report_path=result.report_path,
        search_config=config,
        output_path=preference_path,
        split_manifest=split,
        environment_factory=_MilestoneEnvironment,
        ruleset=policy.ruleset,
        policy=cast(ProductionCheckpointPolicy, policy),
        run_seed=reference["seed"],
        trajectory_id=case["best_trajectory_id"],
    )

    assert document["summary"] == {
        "mutations": 1,
        "strict_improvements": 1,
        "tied": 0,
        "regressed": 0,
        "unique_runs": 1,
        "minimum_training_runs": 2,
        "training_ready": False,
        "terminal_victory_positive_labels": 0,
    }
    assert document["preferences"][0]["preferred_action_id"] == "coherent-route"
    assert document["preferences"][0]["terminal_victory_label"] is False
    preference_schema = json.loads(
        Path("schemas/trajectory-mutation-preference-set-v1.json").read_text(encoding="utf-8")
    )
    observation_schema = json.loads(Path("schemas/observation-v1.json").read_text(encoding="utf-8"))
    schema_registry: Registry[Any] = Registry().with_resource(
        str(observation_schema["$id"]), Resource.from_contents(observation_schema)
    )
    Draft202012Validator(preference_schema, registry=schema_registry).validate(document)
    verification = verify_trajectory_mutation_preferences(
        preference_path,
        search_report_path=result.report_path,
        search_config=config,
        split_manifest=split,
        environment_factory=_MilestoneEnvironment,
        ruleset=policy.ruleset,
        policy=cast(ProductionCheckpointPolicy, policy),
        run_seed=reference["seed"],
        trajectory_id=case["best_trajectory_id"],
    )
    assert verification["valid"] is True
    assert verification["verified_mutations"] == 1

    document["preferences"][0]["child_rank"][-1] += 1
    preference_path.write_text(json.dumps(document), encoding="utf-8")
    rejected = verify_trajectory_mutation_preferences(
        preference_path,
        search_report_path=result.report_path,
        search_config=config,
        split_manifest=split,
        environment_factory=_MilestoneEnvironment,
        ruleset=policy.ruleset,
        policy=cast(ProductionCheckpointPolicy, policy),
        run_seed=reference["seed"],
        trajectory_id=case["best_trajectory_id"],
    )
    assert rejected["valid"] is False


def test_trajectory_preference_collection_preserves_complete_run_ownership(
    tmp_path: Path,
) -> None:
    split = load_split_manifest(MOCK_SPLIT_PATH)
    policy = _EarlyDefeatPolicy(split_manifest_id=split.manifest_id)
    training_report_id = manifest_identifier({"report": "trajectory-preference-collection"})
    config = _frontier_config(policy, training_report_id)
    search_output = tmp_path / "collection-search"
    timestamps = iter(("2026-01-05T00:00:00Z", "2026-01-05T00:00:01Z"))
    result = run_trajectory_search(
        environment_factory=_MilestoneEnvironment,
        ruleset=policy.ruleset,
        policy=cast(ProductionCheckpointPolicy, policy),
        split_manifest=split,
        training_report_id=training_report_id,
        config=config,
        output_directory=search_output,
        now=lambda: next(timestamps),
    )
    collection_root = tmp_path / "preference-collection"
    collection = freeze_trajectory_mutation_preference_collection(
        search_report_path=result.report_path,
        search_config=config,
        output_directory=collection_root,
        split_manifest=split,
        environment_factory=_MilestoneEnvironment,
        ruleset=policy.ruleset,
        policy=cast(ProductionCheckpointPolicy, policy),
    )

    assert collection["summary"] == {
        "cases": 2,
        "mutations": 2,
        "strict_improvements": 2,
        "tied": 0,
        "regressed": 0,
        "unique_runs": 2,
        "minimum_training_runs": 2,
        "training_ready": True,
        "terminal_victory_positive_labels": 0,
    }
    assert len({case["run_seed"] for case in collection["cases"]}) == 2
    collection_schema = json.loads(
        Path("schemas/trajectory-mutation-preference-collection-v1.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(collection_schema).validate(collection)
    collection_path = collection_root / TRAJECTORY_PREFERENCE_COLLECTION_FILENAME
    verification = verify_trajectory_mutation_preference_collection(
        collection_path,
        search_report_path=result.report_path,
        search_config=config,
        split_manifest=split,
        environment_factory=_MilestoneEnvironment,
        ruleset=policy.ruleset,
        policy=cast(ProductionCheckpointPolicy, policy),
    )
    assert verification["valid"] is True
    assert verification["verified_cases"] == 2
    assert verification["verified_mutations"] == 2

    first_component_path = collection_root / collection["cases"][0]["path"]
    first_component = json.loads(first_component_path.read_text(encoding="utf-8"))
    first_component["preferences"][0]["preferred_action_id"] = "tampered-action"
    first_component_path.write_text(json.dumps(first_component), encoding="utf-8")
    rejected = verify_trajectory_mutation_preference_collection(
        collection_path,
        search_report_path=result.report_path,
        search_config=config,
        split_manifest=split,
        environment_factory=_MilestoneEnvironment,
        ruleset=policy.ruleset,
        policy=cast(ProductionCheckpointPolicy, policy),
    )
    assert rejected["valid"] is False
    assert rejected["verified_cases"] == 0


def test_same_budget_ablation_compares_three_verified_arms(tmp_path: Path) -> None:
    split = load_split_manifest(MOCK_SPLIT_PATH)
    policy = _EarlyDefeatPolicy(split_manifest_id=split.manifest_id)
    training_report_id = manifest_identifier({"report": "frontier-ablation"})
    legacy_config = _config(policy, training_report_id)
    frontier_config = _frontier_config(policy, training_report_id)
    diverse_config = _frontier_config(
        policy,
        training_report_id,
        strategy=PUBLIC_FRONTIER_DIVERSE_STRATEGY,
    )

    reports = []
    for name, config in (
        ("legacy", legacy_config),
        ("frontier", frontier_config),
        ("diverse", diverse_config),
    ):
        timestamps = iter(("2026-01-04T00:00:00Z", "2026-01-04T00:00:01Z"))
        reports.append(
            run_trajectory_search(
                environment_factory=_MilestoneEnvironment,
                ruleset=policy.ruleset,
                policy=cast(ProductionCheckpointPolicy, policy),
                split_manifest=split,
                training_report_id=training_report_id,
                config=config,
                output_directory=tmp_path / name,
                now=timestamps.__next__,
            )
        )

    comparison = compare_trajectory_search_ablation(
        legacy_report_path=reports[0].report_path,
        frontier_report_path=reports[1].report_path,
        diverse_report_path=reports[2].report_path,
        legacy_config=legacy_config,
        frontier_config=frontier_config,
        diverse_config=diverse_config,
        split_manifest=split,
    )

    assert [arm["strategy"] for arm in comparison["arms"]] == [
        "hash_tiebreak_v1",
        "public_frontier_v1",
        "public_frontier_diverse_v1",
    ]
    assert comparison["comparison"]["boss_reach_or_act1_clear_found"] is True
    Draft202012Validator(
        json.loads(Path("schemas/run-level-trajectory-search-ablation-v2.json").read_text())
    ).validate(comparison)

    assert frontier_config.frontier_ranking is not None
    with pytest.raises(ValueError, match="retired enemy-progress semantics"):
        compare_trajectory_search_ablation(
            legacy_report_path=reports[0].report_path,
            frontier_report_path=reports[1].report_path,
            diverse_report_path=reports[2].report_path,
            legacy_config=legacy_config,
            frontier_config=replace(
                frontier_config,
                frontier_ranking=replace(
                    frontier_config.frontier_ranking,
                    enemy_snapshot_rule=LEGACY_ENEMY_SNAPSHOT_RULE,
                ),
            ),
            diverse_config=diverse_config,
            split_manifest=split,
        )

    with pytest.raises(ValueError, match="equal frozen budgets"):
        compare_trajectory_search_ablation(
            legacy_report_path=reports[0].report_path,
            frontier_report_path=reports[1].report_path,
            diverse_report_path=reports[2].report_path,
            legacy_config=legacy_config,
            frontier_config=replace(frontier_config, generations=3),
            diverse_config=diverse_config,
            split_manifest=split,
        )
