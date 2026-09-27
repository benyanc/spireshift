from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Self, cast

import pytest
from jsonschema import Draft202012Validator

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.agents.combat_advancement import CombatAdvancementConfig
from spireshift.agents.learned import ProductionCheckpointPolicy, ProductionPolicyDecision
from spireshift.combat_search_intervention import (
    CombatSearchInterventionSpec,
    MarginStratum,
    load_combat_search_interventions,
    run_combat_search_interventions,
)
from spireshift.core.manifest import manifest_identifier
from spireshift.core.types import DecisionType, LegalAction, Observation, Transition
from spireshift.splits import load_split_manifest

MOCK_SPLIT_PATH = Path("manifests/splits/mock-v1-seeds-000000-000999-v1.json")


class _InterventionEnvironment:
    patch_id = "mock-v1"
    ruleset = MockSpireEnvironment.ruleset

    def __init__(
        self,
        *,
        seed: int = 0,
        stage: str = "root",
        floor: int = 1,
        victory: bool = False,
    ) -> None:
        self.seed = seed
        self.stage = stage
        self.floor = floor
        self.victory = victory

    def reset(self, seed: int) -> Observation:
        self.seed = seed
        self.stage = "root"
        self.floor = 1
        self.victory = False
        return self._observation()

    def legal_actions(self) -> Sequence[LegalAction]:
        if self.stage == "terminal":
            return ()
        if self.stage == "root":
            return (LegalAction("base", "card", {}), LegalAction("search", "card", {}))
        return (LegalAction("continue", "card", {}),)

    def step(self, action: LegalAction) -> Transition:
        source = self._observation()
        if action not in self.legal_actions():
            raise ValueError("illegal action")
        if self.stage == "root":
            self.stage = f"{action.action_id}_mid"
            terminal = False
            victory = False
        else:
            chose_search = self.stage == "search_mid"
            self.victory = chose_search if self.seed == 0 else not chose_search
            self.floor = 3 if self.victory else 1
            self.stage = "terminal"
            terminal = True
            victory = self.victory
        return Transition(source, action, self._observation(), float(victory), terminal, victory)

    def clone(self, *, resample_hidden: bool, seed: int | None = None) -> Self:
        del resample_hidden, seed
        return type(self)(
            seed=self.seed,
            stage=self.stage,
            floor=self.floor,
            victory=self.victory,
        )

    def _observation(self) -> Observation:
        public = {
            "seed": self.seed,
            "stage": self.stage,
            "floor": self.floor,
            "terminal": self.stage == "terminal",
            "victory": self.victory,
        }
        state_hash = hashlib.sha256(
            json.dumps(public, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return Observation(
            "observation-v1",
            self.patch_id,
            DecisionType.TERMINAL if self.stage == "terminal" else DecisionType.COMBAT,
            public,
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
        policy: tuple[float, ...]
        risks: tuple[float, ...]
        floors: tuple[float, ...]
        if observation.public_state["stage"] == "root":
            policy = (0.9, 0.1)
            risks = (0.5, 0.5)
            floors = (0.5, 0.5)
            selected = 0
        else:
            search_branch = observation.public_state["stage"] == "search_mid"
            policy = (1.0,)
            risks = (0.1 if search_branch else 0.9,)
            floors = (0.9 if search_branch else 0.1,)
            selected = 0
        return ProductionPolicyDecision(
            representation_hash=observation.state_hash,
            source_action_ids=tuple(action.action_id for action in actions),
            selected_candidate_index=selected,
            selected_action=actions[selected],
            policy=policy,
            terminal_value=None,
            tactical_death_risk=risks,
            maximum_floor_reach={2: floors},
            inference_seconds=0.0,
        )

    def choose_action(
        self, observation: Observation, legal_actions: Sequence[LegalAction]
    ) -> LegalAction:
        return self.predict(observation, legal_actions).selected_action


def _spec(split_id: str, ruleset_id: str) -> CombatSearchInterventionSpec:
    config = CombatAdvancementConfig(
        schema_version="combat-advancement-config-v2",
        candidate_worlds=2,
        maximum_rollout_steps=1,
        maximum_simulated_transitions_per_decision=8,
        maximum_public_resample_attempts=2,
        public_resample_exhaustion="policy_only_fallback",
        progress_weight=0.25,
        tactical_survival_weight=0.75,
        sampling_salt="intervention-unit-test",
        selection_mode="shadow",
        minimum_search_advantage=0.0,
    )
    return CombatSearchInterventionSpec(
        split_manifest_id=split_id,
        ruleset_manifest_id=ruleset_id,
        model_id=_BasePolicy.model_id,
        training_report_id="sha256:" + "4" * 64,
        run_offset=0,
        run_count=2,
        workers=2,
        maximum_decisions_per_run=8,
        cycle_repetition_threshold=4,
        shadow_config=config,
        margin_strata=(MarginStratum("all", 0.0, None, 1),),
        selection_salt="intervention-selection-unit-test",
    )


def test_single_interventions_label_beneficial_and_harmful_without_changing_base(
    tmp_path: Path,
) -> None:
    split = load_split_manifest(MOCK_SPLIT_PATH)
    spec = _spec(split.manifest_id, split.ruleset_manifest_id)
    assert CombatSearchInterventionSpec.from_mapping(spec.as_dict()) == spec
    policy = cast(ProductionCheckpointPolicy, _BasePolicy(split.manifest_id))
    timestamps = iter(("2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z"))

    result = run_combat_search_interventions(
        environment_factory=_InterventionEnvironment,
        ruleset=MockSpireEnvironment.ruleset,
        base_policy=policy,
        split_manifest=split,
        spec=spec,
        output_directory=tmp_path / "interventions",
        now=lambda: next(timestamps),
    )

    assert result.successful is True
    summary = result.report["summary"]
    assert summary["base_runs"]["victories"] == 1
    assert summary["interventions"]["overall"]["beneficial_interventions"] == 1
    assert summary["interventions"]["overall"]["harmful_interventions"] == 1
    assert summary["interventions"]["selected_interventions"] == 2
    cases = [
        json.loads((result.report_path.parent / reference["path"]).read_text())
        for reference in result.report["cases"]
    ]
    assert [case["base_run"]["victory"] for case in cases] == [False, True]
    assert [case["interventions"][0]["paired_label"] for case in cases] == [
        "beneficial",
        "harmful",
    ]
    assert all(
        case["source_search"]["selected_interventions_by_stratum"] == {"all": 1} for case in cases
    )
    assert (
        load_combat_search_interventions(
            result.report_path,
            spec=spec,
            split_manifest=split,
        )
        == result.report
    )
    Draft202012Validator(
        json.loads(Path("schemas/combat-search-intervention-report-v1.json").read_text())
    ).validate(result.report)
    Draft202012Validator(
        json.loads(Path("schemas/combat-search-intervention-case-v1.json").read_text())
    ).validate(cases[0])


def test_single_intervention_resume_and_semantic_tamper_rejection(tmp_path: Path) -> None:
    split = load_split_manifest(MOCK_SPLIT_PATH)
    spec = _spec(split.manifest_id, split.ruleset_manifest_id)
    policy = cast(ProductionCheckpointPolicy, _BasePolicy(split.manifest_id))
    output = tmp_path / "interventions"
    timestamps = iter(("2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z"))
    first = run_combat_search_interventions(
        environment_factory=_InterventionEnvironment,
        ruleset=MockSpireEnvironment.ruleset,
        base_policy=policy,
        split_manifest=split,
        spec=spec,
        output_directory=output,
        now=lambda: next(timestamps),
    )
    preserved_path = output / first.report["cases"][0]["path"]
    preserved = preserved_path.read_text()
    missing_path = output / first.report["cases"][1]["path"]
    first.report_path.unlink()
    missing_path.unlink()
    resumed_times = iter(("2026-01-01T00:00:02Z", "2026-01-01T00:00:03Z"))
    resumed = run_combat_search_interventions(
        environment_factory=_InterventionEnvironment,
        ruleset=MockSpireEnvironment.ruleset,
        base_policy=policy,
        split_manifest=split,
        spec=spec,
        output_directory=output,
        resume=True,
        now=lambda: next(resumed_times),
    )
    assert resumed.successful is True
    assert preserved_path.read_text() == preserved
    case = json.loads(preserved_path.read_text())
    case["interventions"][0]["paired_label"] = "tied"
    body = {key: value for key, value in case.items() if key != "case_id"}
    case["case_id"] = manifest_identifier(body)
    preserved_path.write_text(json.dumps(case))
    with pytest.raises(ValueError, match="paired label differs"):
        load_combat_search_interventions(
            resumed.report_path,
            spec=spec,
            split_manifest=split,
        )
