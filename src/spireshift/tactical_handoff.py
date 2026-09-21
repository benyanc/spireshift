from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spireshift.adapters.tactical_mock import (
    TACTICAL_MOCK_RULES,
    TacticalHandoffMockEnvironment,
)
from spireshift.core.manifest import manifest_identifier
from spireshift.core.types import LegalAction, Observation
from spireshift.representations import CompositionalModelInput, ScalarFeature
from spireshift.tactical_values import (
    COMPUTE_UNIT_DEFINITION,
    TERMINAL_VICTORY_OBJECTIVE_ID,
    ModelRunValueEstimator,
    RunValuePrediction,
    TacticalValueConfig,
    rank_tactical_actions,
)

TACTICAL_HANDOFF_REPORT_SCHEMA_VERSION = "tactical-handoff-report-v1"
TACTICAL_MOCK_MODEL_ID = "tactical-handoff-public-state-oracle-v1"
LOCAL_ABLATION_ID = "post-combat-hp-greedy-v1"
ARTIFACT_FLOAT_DECIMALS = 12
DEFAULT_WHOLE_RUN_BUDGET = 128


@dataclass(frozen=True, slots=True)
class _Prediction:
    run_value: float


class TacticalMockRunValueModel:
    """A transparent fixture model over the public compositional representation."""

    def predict(self, representation: CompositionalModelInput) -> RunValuePrediction:
        features = [*representation.global_features, *representation.persistent_resources]
        for entity in representation.entities:
            features.extend(entity.features)
        relic_ids = {
            feature.categorical_value
            for feature in features
            if feature.path[-1:] == ("id",) and feature.categorical_value is not None
        }
        permanent_power = _numeric_feature(features, ("run", "permanent_power"))
        probabilities = TACTICAL_MOCK_RULES["continuation_win_probabilities"]
        if not isinstance(probabilities, dict):
            raise RuntimeError("Tactical mock probabilities are malformed")
        if "ember_core" in relic_ids:
            value = probabilities["spend_potion_for_relic"]
        elif permanent_power > 0.0:
            value = probabilities["take_damage_for_power"]
        else:
            value = probabilities["preserve_hp"]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise RuntimeError("Tactical mock run value is malformed")
        return _Prediction(float(value))


class _OnlyActionPolicy:
    policy_id = "only-legal-continuation-v1"

    def choose_action(
        self, observation: Observation, legal_actions: Sequence[LegalAction]
    ) -> LegalAction:
        del observation
        if len(legal_actions) != 1:
            raise ValueError("Tactical fixture continuation requires exactly one action")
        return legal_actions[0]


@dataclass(frozen=True, slots=True)
class TacticalHandoffVerification:
    valid: bool
    report_id: str | None
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "report_id": self.report_id,
            "errors": list(self.errors),
        }


def benchmark_mock_tactical_handoff(
    *,
    seeds: tuple[int, ...] = (7, 19, 41),
    config: TacticalValueConfig | None = None,
    whole_run_budget: int = DEFAULT_WHOLE_RUN_BUDGET,
) -> dict[str, Any]:
    if not seeds:
        raise ValueError("Tactical handoff benchmark requires at least one seed")
    if any(isinstance(seed, bool) or not isinstance(seed, int) or seed < 0 for seed in seeds):
        raise ValueError("Tactical handoff benchmark seeds must be non-negative integers")
    if len(seeds) != len(set(seeds)):
        raise ValueError("Tactical handoff benchmark seeds must be unique")
    if isinstance(whole_run_budget, bool) or not isinstance(whole_run_budget, int):
        raise ValueError("whole_run_budget must be an integer")
    if whole_run_budget <= 0:
        raise ValueError("whole_run_budget must be positive")
    config = config or TacticalValueConfig()
    if config.maximum_compute_units > whole_run_budget:
        raise ValueError("Tactical decision limit exceeds the declared whole-run budget")
    cases: list[dict[str, Any]] = []
    all_paths: set[str] = set()
    total_compute = 0
    terminal_selections: list[str] = []
    local_selections: list[str] = []
    for seed in seeds:
        environment = TacticalHandoffMockEnvironment()
        observation = environment.reset(seed)
        actions = tuple(environment.legal_actions())
        estimator = ModelRunValueEstimator(
            ruleset=environment.ruleset,
            model=TacticalMockRunValueModel(),
            estimator_id=TACTICAL_MOCK_MODEL_ID,
        )
        ranking = rank_tactical_actions(
            environment=environment,
            observation=observation,
            legal_actions=actions,
            continuation_policy=_OnlyActionPolicy(),
            run_value_estimator=estimator,
            config=config,
            seed=seed,
        )
        candidate_documents: list[dict[str, Any]] = []
        local_scores: list[float] = []
        for candidate, action in zip(ranking.candidates, actions, strict=True):
            successor_environment = environment.clone(resample_hidden=False)
            successor = successor_environment.step(action).next_observation
            resources = _resource_summary(successor)
            local_score = resources["hp"] / resources["max_hp"]
            local_scores.append(local_score)
            all_paths.update(candidate.represented_state_paths)
            candidate_documents.append(
                {
                    "candidate_index": candidate.candidate_index,
                    "source_action_id": candidate.source_action_id,
                    "action_kind": candidate.action_kind,
                    "estimated_terminal_victory_probability": _artifact_float(
                        candidate.estimated_terminal_victory_probability
                    ),
                    "local_hp_score": _artifact_float(local_score),
                    "successor_resources": resources,
                    "sampled_leaf_values": [
                        _artifact_float(value) for value in candidate.sampled_leaf_values
                    ],
                    "rollout_terminal_samples": candidate.rollout_terminal_samples,
                    "rollout_bootstrap_samples": candidate.rollout_bootstrap_samples,
                    "successor_state_hashes": list(candidate.successor_state_hashes),
                    "representation_hashes": list(candidate.representation_hashes),
                    "represented_state_paths": list(candidate.represented_state_paths),
                }
            )
        local_index = max(range(len(local_scores)), key=local_scores.__getitem__)
        terminal_action = ranking.selected_action_id
        local_action = actions[local_index].action_id
        terminal_selections.append(terminal_action)
        local_selections.append(local_action)
        total_compute += ranking.usage.compute_units
        by_action = {
            candidate.source_action_id: candidate.estimated_terminal_victory_probability
            for candidate in ranking.candidates
        }
        cases.append(
            {
                "seed": seed,
                "root_state_hash": observation.state_hash,
                "terminal_value_selected_action_id": terminal_action,
                "local_hp_selected_action_id": local_action,
                "selection_disagrees": terminal_action != local_action,
                "damage_tradeoff_beats_hp_greedy": (
                    by_action["take_damage_for_power"] > by_action["preserve_hp"]
                ),
                "potion_tradeoff_beats_hp_greedy": (
                    by_action["spend_potion_for_relic"] > by_action["preserve_hp"]
                ),
                "usage": ranking.usage.as_dict(),
                "candidates": candidate_documents,
            }
        )
    report_body: dict[str, Any] = {
        "schema_version": TACTICAL_HANDOFF_REPORT_SCHEMA_VERSION,
        "backend": "tactical-handoff-mock-v1",
        "ruleset_manifest_id": TacticalHandoffMockEnvironment.ruleset.manifest_id,
        "objective": {
            "id": TERMINAL_VICTORY_OBJECTIVE_ID,
            "primary": "terminal_victory",
            "constraint": "cpu_time_per_run",
            "whole_run_budget": whole_run_budget,
            "portable_compute_proxy": COMPUTE_UNIT_DEFINITION,
            "local_hp_role": "diagnostic_ablation_only",
        },
        "run_value_estimator_id": TACTICAL_MOCK_MODEL_ID,
        "local_ablation_id": LOCAL_ABLATION_ID,
        "method": "terminal-victory-leaf-mixture-v1",
        "compute_unit_definition": COMPUTE_UNIT_DEFINITION,
        "configuration": config.as_dict(),
        "seeds": list(seeds),
        "cases": cases,
        "represented_state_paths": sorted(all_paths),
        "summary": {
            "cases": len(cases),
            "selection_disagreements": sum(int(case["selection_disagrees"]) for case in cases),
            "damage_tradeoff_cases": sum(
                int(case["damage_tradeoff_beats_hp_greedy"]) for case in cases
            ),
            "potion_tradeoff_cases": sum(
                int(case["potion_tradeoff_beats_hp_greedy"]) for case in cases
            ),
            "terminal_value_selected_actions": terminal_selections,
            "local_hp_selected_actions": local_selections,
            "total_compute_units": total_compute,
        },
        "claim_scope": "mock_pipeline_validation",
    }
    return {**report_body, "report_id": manifest_identifier(report_body)}


def validate_tactical_handoff_report(document: object) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ValueError("Tactical handoff report must be an object")
    report = document
    if report.get("schema_version") != TACTICAL_HANDOFF_REPORT_SCHEMA_VERSION:
        raise ValueError("Unsupported tactical-handoff-report schema")
    report_id = report.get("report_id")
    if not isinstance(report_id, str) or not report_id:
        raise ValueError("Tactical handoff report_id must be non-empty")
    body = {key: value for key, value in report.items() if key != "report_id"}
    if report_id != manifest_identifier(body):
        raise ValueError("Tactical handoff report identity mismatch")
    if report.get("ruleset_manifest_id") != TacticalHandoffMockEnvironment.ruleset.manifest_id:
        raise ValueError("Tactical handoff report ruleset mismatch")
    if report.get("run_value_estimator_id") != TACTICAL_MOCK_MODEL_ID:
        raise ValueError("Tactical handoff report estimator mismatch")
    TacticalValueConfig.from_mapping(report.get("configuration"))
    return report


def verify_mock_tactical_handoff_report(document: object) -> TacticalHandoffVerification:
    report_id: str | None = None
    errors: list[str] = []
    try:
        report = validate_tactical_handoff_report(document)
        report_id = str(report["report_id"])
        raw_seeds = report.get("seeds")
        if not isinstance(raw_seeds, list):
            raise ValueError("Tactical handoff report seeds must be an array")
        seeds = tuple(_integer(seed, "seed") for seed in raw_seeds)
        regenerated = benchmark_mock_tactical_handoff(
            seeds=seeds,
            config=TacticalValueConfig.from_mapping(report.get("configuration")),
            whole_run_budget=_integer(
                _mapping(report.get("objective"), "objective").get("whole_run_budget"),
                "whole_run_budget",
            ),
        )
        if regenerated != report:
            errors.append("report differs from deterministic regeneration")
    except (TypeError, ValueError) as error:
        errors.append(str(error))
    return TacticalHandoffVerification(not errors, report_id, tuple(errors))


def load_tactical_handoff_report(path: Path) -> dict[str, Any]:
    try:
        document: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load tactical handoff report {path}: {error}") from error
    return validate_tactical_handoff_report(document)


def write_tactical_handoff_report(document: dict[str, Any], path: Path) -> None:
    encoded = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise FileExistsError(f"Refusing to replace immutable tactical handoff report: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded, encoding="utf-8", newline="\n")


def _resource_summary(observation: Observation) -> dict[str, Any]:
    player = observation.public_state.get("player")
    run = observation.public_state.get("run")
    if not isinstance(player, dict) or not isinstance(run, dict):
        raise ValueError("Tactical successor lacks player or run state")
    potions = player.get("potions")
    relics = player.get("relics")
    deck = player.get("deck")
    if not isinstance(potions, list) or not isinstance(relics, list) or not isinstance(deck, list):
        raise ValueError("Tactical successor resources are malformed")
    return {
        "hp": _integer(player.get("hp"), "player.hp"),
        "max_hp": _integer(player.get("max_hp"), "player.max_hp"),
        "gold": _integer(player.get("gold"), "player.gold"),
        "potion_charges": sum(
            _integer(potion.get("charges"), "potion.charges")
            for potion in potions
            if isinstance(potion, dict)
        ),
        "deck_size": len(deck),
        "relic_ids": [
            relic["id"]
            for relic in relics
            if isinstance(relic, dict) and isinstance(relic.get("id"), str)
        ],
        "relic_counter": _integer(run.get("relic_counter"), "run.relic_counter"),
        "permanent_power": _integer(run.get("permanent_power"), "run.permanent_power"),
        "future_path_options": len(
            run["next_options"] if isinstance(run.get("next_options"), list) else []
        ),
    }


def _numeric_feature(features: list[ScalarFeature], path: tuple[str, ...]) -> float:
    matches = [
        feature.numeric_value
        for feature in features
        if feature.path == path and feature.numeric_value is not None
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one numeric feature at {'.'.join(path)}")
    return matches[0]


def _artifact_float(value: float) -> float:
    return round(float(value), ARTIFACT_FLOAT_DECIMALS)


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value
