from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.agents.learned import ProductionPolicyDecision
from spireshift.bootstrap_teacher import (
    BootstrapPolicyArtifacts,
    CurriculumStateSet,
    load_bootstrap_state_set_document,
)
from spireshift.core.manifest import manifest_identifier
from spireshift.core.types import LegalAction, Observation, Transition
from spireshift.production_dagger import (
    ProductionDaggerConfig,
    ProductionDaggerReference,
    load_production_dagger_config,
    run_production_dagger_collection,
    verify_production_dagger_collection,
)
from spireshift.representations import build_model_input
from spireshift.splits import SplitName, load_split_manifest

MOCK_SPLIT = Path("manifests/splits/mock-v1-seeds-000000-000999-v1.json")


class _AlwaysLastProductionPolicy:
    def __init__(self, *, model_id: str, split_manifest_id: str) -> None:
        self.model_id = model_id
        self.policy_id = f"production-checkpoint-policy-v1:{model_id}"
        self.split_manifest_id = split_manifest_id
        self.ruleset = MockSpireEnvironment.ruleset

    def predict(
        self, observation: Observation, legal_actions: Sequence[LegalAction]
    ) -> ProductionPolicyDecision:
        representation = build_model_input(self.ruleset, observation, legal_actions)
        policy = tuple(
            1.0 if index == len(legal_actions) - 1 else 0.0 for index in range(len(legal_actions))
        )
        return ProductionPolicyDecision(
            representation_hash=representation.representation_hash,
            source_action_ids=tuple(action.action_id for action in legal_actions),
            selected_candidate_index=len(legal_actions) - 1,
            selected_action=legal_actions[-1],
            policy=policy,
            terminal_value=None,
            tactical_death_risk=tuple(0.0 for _ in legal_actions),
            maximum_floor_reach={},
            inference_seconds=0.0,
        )


class _RecoverableNoOpEnvironment(MockSpireEnvironment):
    def legal_actions(self) -> tuple[LegalAction, ...]:
        if self._state.terminal:
            return ()
        return (
            LegalAction("finish", "choose", {}),
            LegalAction("stuck", "choose", {}),
        )

    def step(self, action: LegalAction) -> Transition:
        observation = self._observation()
        legal = {candidate.action_id: candidate for candidate in self.legal_actions()}
        if action.action_id not in legal:
            raise ValueError(f"Illegal action: {action.action_id}")
        if action.action_id == "finish":
            self._state.terminal = True
        return Transition(
            observation=observation,
            action=legal[action.action_id],
            next_observation=self._observation(),
            reward=0.0,
            terminal=self._state.terminal,
            victory=False,
        )


def _id(label: str) -> str:
    return manifest_identifier({"test": label})


def _causal_preferences(config: ProductionDaggerConfig) -> dict[str, object]:
    preference_body = {
        "seed": 900,
        "intervention_ordinal": 0,
        "source_case_id": _id("case"),
        "decision_index": 2,
        "source_state_hash": "a" * 64,
        "source_floor": 1,
        "paired_label": "beneficial",
        "base_action_id": "base",
        "search_action_id": "search",
        "preferred_action_id": "search",
        "disfavored_action_id": "base",
        "search_over_base_probability": 1.0,
        "training_weight": 1.0,
        "search_advantage": 0.2,
        "maximum_floor_difference": 1,
        "victory_difference": 0,
    }
    preference = {**preference_body, "preference_id": manifest_identifier(preference_body)}
    body = {
        "schema_version": "production-causal-preference-set-v1",
        "intervention_spec_id": config.intervention_spec_id,
        "intervention_report_id": config.intervention_report_id,
        "source_model_id": _id("intervention-model"),
        "source_training_report_id": _id("intervention-training-report"),
        "split_manifest_id": config.split_manifest_id,
        "ruleset_manifest_id": config.ruleset_manifest_id,
        "objective_id": config.objective_id,
        "partition": "train",
        "preferences": [preference],
        "summary": {
            "preferences": 1,
            "unique_runs": 1,
            "beneficial": 1,
            "harmful": 0,
            "tied": 0,
            "effective_training_weight": 1.0,
        },
        "claim_scope": "verified_train_only_single_intervention_preferences",
    }
    return {**body, "preference_set_id": manifest_identifier(body)}


def _setup(
    run_count: int = 3,
) -> tuple[
    ProductionDaggerConfig,
    _AlwaysLastProductionPolicy,
    BootstrapPolicyArtifacts,
    ProductionDaggerReference,
]:
    split = load_split_manifest(MOCK_SPLIT)
    model_id = _id("model")
    training_report_id = _id("training-report")
    reference_dataset_id = _id("reference")
    policy = _AlwaysLastProductionPolicy(
        model_id=model_id,
        split_manifest_id=split.manifest_id,
    )
    config = ProductionDaggerConfig(
        split_manifest_id=split.manifest_id,
        ruleset_manifest_id=split.ruleset_manifest_id,
        model_id=model_id,
        training_report_id=training_report_id,
        reference_dataset_id=reference_dataset_id,
        intervention_spec_id=_id("intervention-spec"),
        intervention_report_id=_id("intervention-report"),
        run_offset=0,
        run_count=run_count,
        workers=2,
        maximum_decisions_per_run=8,
        cycle_repetition_threshold=5,
        liveness_tail_length=4,
        no_op_fallback_threshold=2,
        rare_state_max_fraction=0.05,
        high_entropy_threshold=0.8,
        terminal_frontier_states_per_run=1,
        maximum_selected_states_per_run=2,
        minimum_selected_states=run_count,
        minimum_source_floors=1,
        minimum_decision_types=1,
        selection_salt="production-dagger-unit-test",
    )
    artifacts = BootstrapPolicyArtifacts(
        checkpoint_path=Path("unused-checkpoint.json"),
        training_report_path=Path("unused-report.json"),
        policy_id=policy.policy_id,
        model_id=model_id,
        training_report_id=training_report_id,
        split_manifest_id=split.manifest_id,
        ruleset_manifest_id=split.ruleset_manifest_id,
    )
    reference = ProductionDaggerReference(
        dataset_id=reference_dataset_id,
        capture_policy_id=policy.policy_id,
        run_seeds=frozenset(),
        feature_counts=Counter(),
        examples=1,
    )
    return config, policy, artifacts, reference


def _registry() -> tuple[list[dict[str, object]], Registry]:
    schemas = [
        cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
        for path in Path("schemas").glob("*.json")
    ]
    return schemas, Registry().with_resources(
        (cast(str, schema["$id"]), Resource.from_contents(schema)) for schema in schemas
    )


def test_production_dagger_collection_is_train_owned_resumable_and_versioned(
    tmp_path: Path,
) -> None:
    split = load_split_manifest(MOCK_SPLIT)
    config, policy, artifacts, reference = _setup()
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config.as_dict()), encoding="utf-8")
    assert load_production_dagger_config(config_path) == config
    output = tmp_path / "collection"
    timestamps = iter(("2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z"))

    result = run_production_dagger_collection(
        environment_factory=MockSpireEnvironment,
        ruleset=MockSpireEnvironment.ruleset,
        policy=policy,
        policy_artifacts=artifacts,
        split_manifest=split,
        reference=reference,
        causal_preferences=_causal_preferences(config),
        config=config,
        output_directory=output,
        now=lambda: next(timestamps),
    )

    assert result.successful is True
    assert result.state_set_path is not None
    assert result.report["summary"]["selected_states"] >= config.minimum_selected_states
    assert result.report["summary"]["victories"] >= 0
    state_set = cast(
        CurriculumStateSet,
        load_bootstrap_state_set_document(
            json.loads(result.state_set_path.read_text(encoding="utf-8"))
        ),
    )
    assert all(split.split_for_seed(case.run_seed) is SplitName.TRAIN for case in state_set.cases)
    assert len(state_set.cases) == result.report["summary"]["selected_states"]
    verification = verify_production_dagger_collection(
        result.report_path,
        config=config,
        split_manifest=split,
    )
    assert verification["valid"] is True

    schemas, registry = _registry()
    values = {
        "production-dagger-config-v1.json": config.as_dict(),
        "production-dagger-collection-v1.json": result.report,
        "production-causal-preference-set-v1.json": json.loads(
            result.causal_preferences_path.read_text(encoding="utf-8")
        ),
        "production-dagger-verification-v1.json": verification,
    }
    for reference_item in result.report["cases"]:
        case = json.loads((result.report_path.parent / reference_item["path"]).read_text())
        schema = next(
            item
            for item in schemas
            if cast(str, item["$id"]).endswith("/production-dagger-case-v1.json")
        )
        Draft202012Validator(schema, registry=registry).validate(case)
    for schema_name, value in values.items():
        schema = next(
            item for item in schemas if cast(str, item["$id"]).endswith(f"/{schema_name}")
        )
        Draft202012Validator(schema, registry=registry).validate(value)

    preserved_reference = result.report["cases"][0]
    preserved_path = result.report_path.parent / preserved_reference["path"]
    preserved = preserved_path.read_text(encoding="utf-8")
    result.report_path.unlink()
    result.state_set_path.unlink()
    resumed_timestamps = iter(("2026-01-01T00:00:02Z", "2026-01-01T00:00:03Z"))
    resumed = run_production_dagger_collection(
        environment_factory=MockSpireEnvironment,
        ruleset=MockSpireEnvironment.ruleset,
        policy=policy,
        policy_artifacts=artifacts,
        split_manifest=split,
        reference=reference,
        causal_preferences=_causal_preferences(config),
        config=config,
        output_directory=output,
        resume=True,
        now=lambda: next(resumed_timestamps),
    )
    assert resumed.successful is True
    assert preserved_path.read_text(encoding="utf-8") == preserved


def test_production_dagger_uses_shared_no_op_guard_before_cycle_detection(
    tmp_path: Path,
) -> None:
    split = load_split_manifest(MOCK_SPLIT)
    config, policy, artifacts, reference = _setup(run_count=1)
    timestamps = iter(("2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z"))
    result = run_production_dagger_collection(
        environment_factory=_RecoverableNoOpEnvironment,
        ruleset=MockSpireEnvironment.ruleset,
        policy=policy,
        policy_artifacts=artifacts,
        split_manifest=split,
        reference=reference,
        causal_preferences=_causal_preferences(config),
        config=config,
        output_directory=tmp_path / "liveness",
        now=lambda: next(timestamps),
    )

    case_reference = result.report["cases"][0]
    case = json.loads((result.report_path.parent / case_reference["path"]).read_text())
    assert case["terminal"] is True
    assert case["termination_reason"] == "terminal"
    assert case["fallback"]["controller_id"] == "public-no-op-action-guard-v1"
    assert case["fallback"]["invocations"] == 1
    assert case["fallback"]["suppressed_actions"] == 1
    assert result.report["summary"]["policy_cycle_runs"] == 0
