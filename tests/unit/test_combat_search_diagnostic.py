from __future__ import annotations

import hashlib
import itertools
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Self, cast

import pytest
from jsonschema import Draft202012Validator

from spireshift.adapters.mock import MOCK_PATCH_MANIFEST, MockSpireEnvironment
from spireshift.agents.combat_advancement import CombatAdvancementConfig
from spireshift.agents.learned import ProductionCheckpointPolicy, ProductionPolicyDecision
from spireshift.combat_search_diagnostic import (
    CombatSearchDiagnosticSpec,
    CombatSearchDiagnosticVariant,
    load_combat_search_diagnostic,
    run_combat_search_diagnostic,
)
from spireshift.core.manifest import manifest_identifier
from spireshift.core.types import DecisionType, LegalAction, Observation, Transition
from spireshift.splits import SplitName, load_split_manifest

MOCK_SPLIT_PATH = Path("manifests/splits/mock-v1-seeds-000000-000999-v1.json")


class _DiagnosticEnvironment:
    patch_id = "mock-v1"
    ruleset = MOCK_PATCH_MANIFEST.ruleset_identity()

    def __init__(self, *, stage: str = "root", floor: int = 1, victory: bool = False) -> None:
        self.stage = stage
        self.floor = floor
        self.victory = victory

    def reset(self, seed: int) -> Observation:
        del seed
        self.stage = "root"
        self.floor = 1
        self.victory = False
        return self._observation()

    def legal_actions(self) -> Sequence[LegalAction]:
        if self.stage == "terminal":
            return ()
        return (LegalAction("bad", "card", {}), LegalAction("good", "card", {}))

    def step(self, action: LegalAction) -> Transition:
        source = self._observation()
        if action not in self.legal_actions():
            raise ValueError("illegal action")
        self.stage = "terminal"
        self.victory = action.action_id == "good"
        self.floor = 2 if self.victory else 1
        return Transition(
            source, action, self._observation(), float(self.victory), True, self.victory
        )

    def clone(self, *, resample_hidden: bool, seed: int | None = None) -> Self:
        del resample_hidden, seed
        return type(self)(stage=self.stage, floor=self.floor, victory=self.victory)

    def _observation(self) -> Observation:
        public_state = {
            "stage": self.stage,
            "floor": self.floor,
            "terminal": self.stage == "terminal",
            "victory": self.victory,
        }
        state_hash = hashlib.sha256(
            json.dumps(public_state, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return Observation(
            "observation-v1",
            self.patch_id,
            DecisionType.TERMINAL if self.stage == "terminal" else DecisionType.COMBAT,
            public_state,
            state_hash,
        )


class _BasePolicy:
    model_id = "sha256:" + "3" * 64
    policy_id = f"production-checkpoint-policy-v1:{model_id}"
    ruleset = MockSpireEnvironment.ruleset

    def __init__(self, split_manifest_id: str) -> None:
        self.split_manifest_id = split_manifest_id

    def predict(
        self, observation: Observation, legal_actions: Sequence[LegalAction]
    ) -> ProductionPolicyDecision:
        actions = tuple(legal_actions)
        return ProductionPolicyDecision(
            representation_hash=observation.state_hash,
            source_action_ids=tuple(action.action_id for action in actions),
            selected_candidate_index=0,
            selected_action=actions[0],
            policy=(0.9, 0.1),
            terminal_value=None,
            tactical_death_risk=(0.5, 0.5),
            maximum_floor_reach={2: (0.5, 0.5)},
            inference_seconds=0.0,
        )

    def choose_action(
        self, observation: Observation, legal_actions: Sequence[LegalAction]
    ) -> LegalAction:
        return self.predict(observation, legal_actions).selected_action


def _search_config(*, mode: str, advantage: float) -> CombatAdvancementConfig:
    return CombatAdvancementConfig(
        schema_version="combat-advancement-config-v2",
        candidate_worlds=2,
        maximum_rollout_steps=2,
        maximum_simulated_transitions_per_decision=16,
        maximum_public_resample_attempts=2,
        public_resample_exhaustion="policy_only_fallback",
        progress_weight=0.25,
        tactical_survival_weight=0.75,
        sampling_salt="diagnostic-unit-test",
        selection_mode=mode,
        minimum_search_advantage=advantage,
    )


def _spec(split_id: str, ruleset_id: str) -> CombatSearchDiagnosticSpec:
    return CombatSearchDiagnosticSpec(
        split_manifest_id=split_id,
        ruleset_manifest_id=ruleset_id,
        model_id=_BasePolicy.model_id,
        training_report_id="sha256:" + "4" * 64,
        run_offset=0,
        run_count=2,
        workers=2,
        maximum_decisions_per_run=8,
        cycle_repetition_threshold=4,
        variants=(
            CombatSearchDiagnosticVariant(
                name="shadow", config=_search_config(mode="shadow", advantage=0.0)
            ),
            CombatSearchDiagnosticVariant(
                name="margin-050", config=_search_config(mode="apply", advantage=0.5)
            ),
        ),
    )


def _terminal_rescue_spec(split_id: str, ruleset_id: str) -> CombatSearchDiagnosticSpec:
    def config(mode: str) -> CombatAdvancementConfig:
        return CombatAdvancementConfig(
            schema_version="combat-advancement-config-v3",
            candidate_worlds=2,
            maximum_rollout_steps=2,
            maximum_simulated_transitions_per_decision=16,
            maximum_public_resample_attempts=2,
            public_resample_exhaustion="policy_only_fallback",
            progress_weight=0.25,
            tactical_survival_weight=0.75,
            sampling_salt="terminal-rescue-diagnostic-unit-test",
            selection_mode=mode,
            minimum_search_advantage=0.2,
            override_rule="terminal_rescue",
        )

    return CombatSearchDiagnosticSpec(
        split_manifest_id=split_id,
        ruleset_manifest_id=ruleset_id,
        model_id=_BasePolicy.model_id,
        training_report_id="sha256:" + "4" * 64,
        run_offset=0,
        run_count=2,
        workers=2,
        maximum_decisions_per_run=8,
        cycle_repetition_threshold=4,
        variants=(
            CombatSearchDiagnosticVariant(name="shadow", config=config("shadow")),
            CombatSearchDiagnosticVariant(name="terminal-rescue", config=config("apply")),
        ),
    )


def _combat_resolution_spec(split_id: str, ruleset_id: str) -> CombatSearchDiagnosticSpec:
    def config(mode: str) -> CombatAdvancementConfig:
        return CombatAdvancementConfig(
            schema_version="combat-advancement-config-v4",
            candidate_worlds=2,
            maximum_rollout_steps=2,
            maximum_simulated_transitions_per_decision=16,
            maximum_public_resample_attempts=2,
            public_resample_exhaustion="policy_only_fallback",
            progress_weight=0.25,
            tactical_survival_weight=0.75,
            sampling_salt="combat-resolution-diagnostic-unit-test",
            selection_mode=mode,
            minimum_search_advantage=0.2,
            override_rule="combat_clear_rescue",
        )

    return CombatSearchDiagnosticSpec(
        split_manifest_id=split_id,
        ruleset_manifest_id=ruleset_id,
        model_id=_BasePolicy.model_id,
        training_report_id="sha256:" + "4" * 64,
        run_offset=0,
        run_count=2,
        workers=2,
        maximum_decisions_per_run=8,
        cycle_repetition_threshold=4,
        variants=(
            CombatSearchDiagnosticVariant(name="shadow", config=config("shadow")),
            CombatSearchDiagnosticVariant(name="combat-clear", config=config("apply")),
        ),
    )


def test_paired_combat_search_diagnostic_records_and_verifies_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cpu_ticks = itertools.count()
    monkeypatch.setattr(
        "spireshift.combat_search_diagnostic.time.thread_time",
        lambda: next(cpu_ticks) * 0.001,
    )
    split = load_split_manifest(MOCK_SPLIT_PATH)
    spec = _spec(split.manifest_id, split.ruleset_manifest_id)
    assert CombatSearchDiagnosticSpec.from_mapping(spec.as_dict()) == spec
    policy = cast(ProductionCheckpointPolicy, _BasePolicy(split.manifest_id))
    timestamps = iter(("2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z"))
    result = run_combat_search_diagnostic(
        environment_factory=_DiagnosticEnvironment,
        ruleset=MockSpireEnvironment.ruleset,
        base_policy=policy,
        split_manifest=split,
        spec=spec,
        output_directory=tmp_path / "diagnostic",
        now=lambda: next(timestamps),
    )

    assert result.successful is True
    assert result.report["partition"] == SplitName.TRAIN.value
    summary = result.report["summary"]
    assert summary["base"]["mean_maximum_floor"] == 1.0
    shadow, margin = summary["variants"]
    assert shadow["paired_vs_base"]["identical_outcome_runs"] == 2
    assert shadow["search"]["recommended_overrides"] == 2
    assert shadow["search"]["executed_overrides"] == 0
    assert margin["runs"]["mean_maximum_floor"] == 2.0
    assert margin["paired_vs_base"]["floor_improved_runs"] == 2
    assert margin["search"]["executed_overrides"] == 2
    assert summary["recommendation"] == {
        "shadow_consistency_pass": True,
        "eligible_variant_names": ["margin-050"],
        "selected_variant_name": "margin-050",
        "selected_config_id": spec.variants[1].config.config_id,
        "validation_allowed": True,
    }
    assert (
        load_combat_search_diagnostic(
            result.report_path,
            spec=spec,
            split_manifest=split,
        )
        == result.report
    )
    Draft202012Validator(
        json.loads(Path("schemas/combat-search-diagnostic-report-v1.json").read_text())
    ).validate(result.report)
    first_case = json.loads(
        (result.report_path.parent / result.report["cases"][0]["path"]).read_text()
    )
    Draft202012Validator(
        json.loads(Path("schemas/combat-search-diagnostic-case-v1.json").read_text())
    ).validate(first_case)


def test_combat_search_diagnostic_resumes_only_missing_cases(tmp_path: Path) -> None:
    split = load_split_manifest(MOCK_SPLIT_PATH)
    spec = _spec(split.manifest_id, split.ruleset_manifest_id)
    policy = cast(ProductionCheckpointPolicy, _BasePolicy(split.manifest_id))
    output = tmp_path / "diagnostic"
    timestamps = iter(("2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z"))
    first = run_combat_search_diagnostic(
        environment_factory=_DiagnosticEnvironment,
        ruleset=MockSpireEnvironment.ruleset,
        base_policy=policy,
        split_manifest=split,
        spec=spec,
        output_directory=output,
        now=lambda: next(timestamps),
    )
    preserved_path = output / first.report["cases"][0]["path"]
    preserved = preserved_path.read_text()
    missing_path = output / first.report["cases"][-1]["path"]
    first.report_path.unlink()
    missing_path.unlink()
    resumed_timestamps = iter(("2026-01-01T00:00:02Z", "2026-01-01T00:00:03Z"))

    resumed = run_combat_search_diagnostic(
        environment_factory=_DiagnosticEnvironment,
        ruleset=MockSpireEnvironment.ruleset,
        base_policy=policy,
        split_manifest=split,
        spec=spec,
        output_directory=output,
        resume=True,
        now=lambda: next(resumed_timestamps),
    )

    assert resumed.successful is True
    assert preserved_path.read_text() == preserved
    assert missing_path.exists()


def test_combat_search_diagnostic_rejects_non_train_spec() -> None:
    split = load_split_manifest(MOCK_SPLIT_PATH)
    document = _spec(split.manifest_id, split.ruleset_manifest_id).as_dict()
    document["partition"] = "validation"
    body = {key: value for key, value in document.items() if key != "spec_id"}
    document["spec_id"] = manifest_identifier(body)
    with pytest.raises(ValueError, match="only train seeds"):
        CombatSearchDiagnosticSpec.from_mapping(document)


def test_terminal_rescue_diagnostic_audits_and_verifies_paired_outcomes(
    tmp_path: Path,
) -> None:
    split = load_split_manifest(MOCK_SPLIT_PATH)
    spec = _terminal_rescue_spec(split.manifest_id, split.ruleset_manifest_id)
    policy = cast(ProductionCheckpointPolicy, _BasePolicy(split.manifest_id))
    timestamps = iter(("2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z"))
    result = run_combat_search_diagnostic(
        environment_factory=_DiagnosticEnvironment,
        ruleset=MockSpireEnvironment.ruleset,
        base_policy=policy,
        split_manifest=split,
        spec=spec,
        output_directory=tmp_path / "rescue",
        now=lambda: next(timestamps),
    )

    rescue_summary = result.report["summary"]["variants"][1]
    assert rescue_summary["search"]["executed_overrides"] == 2
    assert rescue_summary["paired_vs_base"]["floor_improved_runs"] == 2
    rescue_reference = next(
        reference
        for reference in result.report["cases"]
        if reference["variant_name"] == "terminal-rescue"
    )
    rescue_path = result.report_path.parent / rescue_reference["path"]
    rescue_case = json.loads(rescue_path.read_text())
    trace = rescue_case["search_diagnostics"]["decisions"][0]
    assert trace["override_rule"] == "terminal_rescue"
    assert trace["override_rule_eligible"] is True
    assert trace["base_terminal_defeats"] == 2
    assert trace["search_terminal_defeats"] == 0
    assert (
        load_combat_search_diagnostic(
            result.report_path,
            spec=spec,
            split_manifest=split,
        )
        == result.report
    )

    trace["override_rule_eligible"] = False
    body = {key: value for key, value in rescue_case.items() if key != "case_id"}
    rescue_case["case_id"] = manifest_identifier(body)
    rescue_path.write_text(json.dumps(rescue_case))
    report = json.loads(result.report_path.read_text())
    for reference in report["cases"]:
        if reference["path"] == rescue_reference["path"]:
            reference["case_id"] = rescue_case["case_id"]
    report_body = {key: value for key, value in report.items() if key != "report_id"}
    report["report_id"] = manifest_identifier(report_body)
    result.report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="eligibility is inconsistent"):
        load_combat_search_diagnostic(
            result.report_path,
            spec=spec,
            split_manifest=split,
        )


def test_combat_resolution_diagnostic_verifies_resolution_boundaries(tmp_path: Path) -> None:
    split = load_split_manifest(MOCK_SPLIT_PATH)
    spec = _combat_resolution_spec(split.manifest_id, split.ruleset_manifest_id)
    policy = cast(ProductionCheckpointPolicy, _BasePolicy(split.manifest_id))
    timestamps = iter(("2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z"))
    result = run_combat_search_diagnostic(
        environment_factory=_DiagnosticEnvironment,
        ruleset=MockSpireEnvironment.ruleset,
        base_policy=policy,
        split_manifest=split,
        spec=spec,
        output_directory=tmp_path / "combat-resolution",
        now=lambda: next(timestamps),
    )

    resolution_reference = next(
        reference
        for reference in result.report["cases"]
        if reference["variant_name"] == "combat-clear"
    )
    resolution_path = result.report_path.parent / resolution_reference["path"]
    resolution_case = json.loads(resolution_path.read_text())
    trace = resolution_case["search_diagnostics"]["decisions"][0]
    assert trace["override_rule"] == "combat_clear_rescue"
    assert trace["override_rule_eligible"] is True
    assert trace["base_terminal_defeats"] == 2
    assert trace["search_terminal_victories"] == 2
    assert trace["search_combat_clears"] == 0
    assert {item["outcome"] for item in trace["search_branch_outcomes"]} == {"run_victory"}
    assert trace["source_observation"]["state_hash"] == trace["source_state_hash"]
    assert all(
        item["resolved_observation"]["state_hash"] == item["resolved_state_hash"]
        for item in trace["search_branch_outcomes"]
    )
    assert (
        load_combat_search_diagnostic(
            result.report_path,
            spec=spec,
            split_manifest=split,
        )
        == result.report
    )

    trace["search_branch_outcomes"][0]["outcome"] = "censored"
    body = {key: value for key, value in resolution_case.items() if key != "case_id"}
    resolution_case["case_id"] = manifest_identifier(body)
    resolution_path.write_text(json.dumps(resolution_case))
    report = json.loads(result.report_path.read_text())
    for reference in report["cases"]:
        if reference["path"] == resolution_reference["path"]:
            reference["case_id"] = resolution_case["case_id"]
    report_body = {key: value for key, value in report.items() if key != "report_id"}
    report["report_id"] = manifest_identifier(report_body)
    result.report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="censored boundary differs"):
        load_combat_search_diagnostic(
            result.report_path,
            spec=spec,
            split_manifest=split,
        )
