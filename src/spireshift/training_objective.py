"""Versioned episode scores for full-run learning, separate from engine rewards.

This module never loads an environment or a policy. Its inputs are normalized,
public-progress outcomes from an episode recorder; the collector verifies their source.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import ObjectiveSpec

SPEC_SCHEMA = "full-run-training-objective-v1"
PANEL_SCHEMA = "full-run-training-panel-v1"
REPORT_SCHEMA = "full-run-training-score-v1"
BOOTSTRAP_OBJECTIVE_ID = "full-run-progress-bootstrap-v1"
TERMINAL_OBJECTIVE_ID = "full-run-terminal-training-v1"
RANKING_RULE = "victory_rate_then_auxiliary_progress_then_completion_rate"


class TrainingStage(StrEnum):
    BOOTSTRAP = "progress_bootstrap"
    TERMINAL = "terminal_only"


class RunStatus(StrEnum):
    VICTORY = "terminal_victory"
    LOSS = "terminal_loss"
    UNSUPPORTED = "unsupported"
    ERROR = "runtime_error"
    TIMEOUT = "timeout"
    BUDGET = "budget_exhausted"
    TRUNCATED = "truncated"
    LIVENESS = "liveness_failure"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class TrainingScope:
    ruleset_manifest_id: str
    character: str
    ascension: int

    def __post_init__(self) -> None:
        if not isinstance(self.ruleset_manifest_id, str) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", self.ruleset_manifest_id
        ):
            raise ValueError("scope requires a ruleset manifest SHA-256 identity")
        if not isinstance(self.character, str) or not self.character.strip():
            raise ValueError("scope character must be nonempty")
        _integer(self.ascension, "ascension")

    @classmethod
    def from_mapping(cls, value: object) -> TrainingScope:
        d = _fields(value, {"ruleset_manifest_id", "character", "ascension"}, "scope")
        return cls(d["ruleset_manifest_id"], d["character"], d["ascension"])

    def as_dict(self) -> dict[str, Any]:
        return {
            "ruleset_manifest_id": self.ruleset_manifest_id,
            "character": self.character,
            "ascension": self.ascension,
        }


@dataclass(frozen=True, slots=True)
class GraduationSpec:
    minimum_train_victory_seeds: int
    minimum_development_victory_seeds: int
    minimum_development_runs: int

    def __post_init__(self) -> None:
        for name, value in self.as_dict().items():
            _integer(value, name, minimum=1)
        if self.minimum_development_victory_seeds > self.minimum_development_runs:
            raise ValueError("graduation victory minimum exceeds development run minimum")

    @classmethod
    def from_mapping(cls, value: object) -> GraduationSpec:
        names = {
            "minimum_train_victory_seeds",
            "minimum_development_victory_seeds",
            "minimum_development_runs",
        }
        d = _fields(value, names, "graduation")
        return cls(**d)

    def as_dict(self) -> dict[str, int]:
        return {
            "minimum_train_victory_seeds": self.minimum_train_victory_seeds,
            "minimum_development_victory_seeds": self.minimum_development_victory_seeds,
            "minimum_development_runs": self.minimum_development_runs,
        }


@dataclass(frozen=True, slots=True)
class TrainingScoreSpec:
    training_objective_id: str
    stage: TrainingStage
    evaluation_objective: ObjectiveSpec
    scope: TrainingScope
    total_acts: int
    floor_scale: int
    loss_progress_weight: float
    graduation: GraduationSpec

    def __post_init__(self) -> None:
        expected_id = (
            BOOTSTRAP_OBJECTIVE_ID
            if self.stage == TrainingStage.BOOTSTRAP
            else TERMINAL_OBJECTIVE_ID
        )
        if not isinstance(self.stage, TrainingStage) or self.training_objective_id != expected_id:
            raise ValueError("training objective identity must match its declared stage")
        if self.evaluation_objective.objective_id != "terminal-victory-v1":
            raise ValueError("evaluation objective must remain terminal-victory-v1")
        _integer(self.total_acts, "total_acts", minimum=1)
        _integer(self.floor_scale, "floor_scale", minimum=1)
        weight = _number(self.loss_progress_weight, "loss_progress_weight")
        if self.stage == TrainingStage.BOOTSTRAP and not 0 < weight < 1:
            raise ValueError("bootstrap loss_progress_weight must be between zero and one")
        if self.stage == TrainingStage.TERMINAL and weight != 0:
            raise ValueError("terminal-only training cannot contain progress reward")

    @classmethod
    def from_mapping(cls, value: object) -> TrainingScoreSpec:
        names = {
            "schema_version",
            "training_objective_id",
            "stage",
            "evaluation_objective",
            "scope",
            "progress",
            "graduation",
            "discount_factor",
            "population_ranking",
        }
        d = _fields(value, names, "training objective")
        if d["schema_version"] != SPEC_SCHEMA:
            raise ValueError("unsupported training objective schema")
        if d["population_ranking"] != RANKING_RULE:
            raise ValueError("population ranking must prioritize full-run victory rate")
        if _number(d["discount_factor"], "discount_factor") != 1:
            raise ValueError("whole-episode score requires undiscounted returns")
        progress = _fields(
            d["progress"], {"total_acts", "floor_scale", "loss_progress_weight"}, "progress"
        )
        evaluation = _fields(
            d["evaluation_objective"],
            {
                "id",
                "primary",
                "constraint",
                "whole_run_budget",
                "auxiliary",
                "auxiliary_reward_allowed",
            },
            "evaluation objective",
        )
        _integer(evaluation["whole_run_budget"], "whole_run_budget", minimum=1)
        if evaluation["auxiliary_reward_allowed"] is not False:
            raise ValueError("evaluation environment rewards must stay binary")
        if not isinstance(evaluation["auxiliary"], list) or any(
            not isinstance(item, str) for item in evaluation["auxiliary"]
        ):
            raise ValueError("evaluation auxiliary metrics must be a string list")
        return cls(
            training_objective_id=d["training_objective_id"],
            stage=TrainingStage(d["stage"]),
            evaluation_objective=ObjectiveSpec.from_mapping(evaluation),
            scope=TrainingScope.from_mapping(d["scope"]),
            total_acts=progress["total_acts"],
            floor_scale=progress["floor_scale"],
            loss_progress_weight=_number(progress["loss_progress_weight"], "loss_progress_weight"),
            graduation=GraduationSpec.from_mapping(d["graduation"]),
        )

    @property
    def spec_id(self) -> str:
        return manifest_identifier(self.as_dict())

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SPEC_SCHEMA,
            "training_objective_id": self.training_objective_id,
            "stage": self.stage.value,
            "evaluation_objective": self.evaluation_objective.as_dict(),
            "scope": self.scope.as_dict(),
            "progress": {
                "total_acts": self.total_acts,
                "floor_scale": self.floor_scale,
                "loss_progress_weight": self.loss_progress_weight,
            },
            "discount_factor": 1.0,
            "population_ranking": RANKING_RULE,
            "graduation": self.graduation.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class TrainingOutcome:
    seed: int
    status: RunStatus
    completed_acts: int
    maximum_floor: int
    decisions: int
    cpu_seconds: float

    def __post_init__(self) -> None:
        for name in ("seed", "completed_acts", "maximum_floor", "decisions"):
            _integer(getattr(self, name), name)
        if self.maximum_floor > 2**31 - 1:
            raise ValueError("maximum_floor exceeds the public signed 32-bit floor range")
        if not isinstance(self.status, RunStatus):
            raise ValueError("outcome status must be a supported RunStatus")
        _number(self.cpu_seconds, "cpu_seconds")
        if self.cpu_seconds < 0:
            raise ValueError("cpu_seconds must be nonnegative")
        if self.status == RunStatus.MISSING and any(
            (self.completed_acts, self.maximum_floor, self.decisions, self.cpu_seconds)
        ):
            raise ValueError("a missing outcome cannot contain recorded work")

    @classmethod
    def from_mapping(cls, value: object) -> TrainingOutcome:
        d = _fields(
            value,
            {"seed", "status", "completed_acts", "maximum_floor", "decisions", "cpu_seconds"},
            "outcome",
        )
        return cls(
            seed=d["seed"],
            status=RunStatus(d["status"]),
            completed_acts=d["completed_acts"],
            maximum_floor=d["maximum_floor"],
            decisions=d["decisions"],
            cpu_seconds=_number(d["cpu_seconds"], "cpu_seconds"),
        )


@dataclass(frozen=True, slots=True)
class TrainingPanel:
    partition: str
    planned_seeds: tuple[int, ...]
    outcomes: tuple[TrainingOutcome, ...]

    def __post_init__(self) -> None:
        if self.partition not in {"train", "development"}:
            raise ValueError("training panels must be train or development, never final test")
        for seed in self.planned_seeds:
            _integer(seed, "planned seed")
        if not self.planned_seeds or len(set(self.planned_seeds)) != len(self.planned_seeds):
            raise ValueError("planned seeds must be nonempty and unique")
        seeds = [item.seed for item in self.outcomes]
        if len(seeds) != len(set(seeds)):
            raise ValueError("duplicate outcomes cannot count as independent runs")
        if not set(seeds).issubset(self.planned_seeds):
            raise ValueError("outcome seed is outside the planned panel")

    @classmethod
    def from_mapping(cls, value: object, spec: TrainingScoreSpec) -> TrainingPanel:
        d = _fields(
            value,
            {
                "schema_version",
                "training_spec_id",
                "training_objective_id",
                "scope",
                "partition",
                "planned_seeds",
                "outcomes",
            },
            "training panel",
        )
        if d["schema_version"] != PANEL_SCHEMA:
            raise ValueError("unsupported training panel schema")
        if d["training_spec_id"] != spec.spec_id:
            raise ValueError("training panel score configuration identity mismatch")
        if d["training_objective_id"] != spec.training_objective_id:
            raise ValueError("training panel objective mismatch")
        if TrainingScope.from_mapping(d["scope"]) != spec.scope:
            raise ValueError("training panel scope mismatch")
        if not isinstance(d["planned_seeds"], list) or not isinstance(d["outcomes"], list):
            raise ValueError("planned_seeds and outcomes must be lists")
        return cls(
            d["partition"],
            tuple(d["planned_seeds"]),
            tuple(TrainingOutcome.from_mapping(item) for item in d["outcomes"]),
        )


def load_training_score_spec(path: Path) -> TrainingScoreSpec:
    return TrainingScoreSpec.from_mapping(json.loads(path.read_text(encoding="utf-8")))


def load_training_panel(path: Path, spec: TrainingScoreSpec) -> TrainingPanel:
    return TrainingPanel.from_mapping(json.loads(path.read_text(encoding="utf-8")), spec)


def score_training_outcome(spec: TrainingScoreSpec, outcome: TrainingOutcome) -> dict[str, Any]:
    """Return one whole-episode score. Decisions, HP, gold and repeated actions earn nothing."""
    if outcome.completed_acts > spec.total_acts:
        raise ValueError("completed_acts exceeds the declared game scope")
    status = outcome.status
    if outcome.cpu_seconds > spec.evaluation_objective.whole_run_budget:
        status = RunStatus.BUDGET
    completed = status in {RunStatus.VICTORY, RunStatus.LOSS}
    # A saturating floor term avoids inventing a maximum floor or paying for repeated rooms.
    # One completed act outranks any floor-only progress within the preceding act.
    progress = (
        (
            outcome.completed_acts
            + outcome.maximum_floor / (outcome.maximum_floor + spec.floor_scale)
        )
        / (spec.total_acts + 1)
        if completed
        else 0.0
    )
    victory = status == RunStatus.VICTORY
    auxiliary = spec.loss_progress_weight * progress if status == RunStatus.LOSS else 0.0
    return {
        "seed": outcome.seed,
        "recorded_status": outcome.status.value,
        "status": status.value,
        "completed": completed,
        "victory": victory,
        "completed_acts": outcome.completed_acts,
        "maximum_floor": outcome.maximum_floor,
        "decisions": outcome.decisions,
        "cpu_seconds": outcome.cpu_seconds,
        "auxiliary_progress_return": auxiliary,
        "training_return": 1.0 if victory else auxiliary,
        "evaluation_terminal_reward": 1.0 if victory else 0.0,
    }


def score_training_panel(spec: TrainingScoreSpec, panel: TrainingPanel) -> dict[str, Any]:
    """Missing cases are zero-scored failures in the original planned denominator."""
    by_seed = {item.seed: item for item in panel.outcomes}
    records = [
        score_training_outcome(
            spec, by_seed.get(seed, TrainingOutcome(seed, RunStatus.MISSING, 0, 0, 0, 0.0))
        )
        for seed in panel.planned_seeds
    ]
    denominator = len(records)
    wins = sum(item["victory"] for item in records)
    completed = sum(item["completed"] for item in records)
    missing = sum(item["status"] == RunStatus.MISSING for item in records)
    mean_auxiliary = math.fsum(item["auxiliary_progress_return"] for item in records) / denominator
    summary = {
        "benchmark_denominator": denominator,
        "recorded_runs": denominator - missing,
        "completed_runs": completed,
        "failed_runs": denominator - completed,
        "missing_runs": missing,
        "victories": wins,
        "victory_rate": wins / denominator,
        "completion_rate": completed / denominator,
        "mean_auxiliary_progress_return": mean_auxiliary,
        "mean_training_return": math.fsum(item["training_return"] for item in records)
        / denominator,
        # Do not rank populations by the mixed return: that could sacrifice victory rate.
        "fitness_rank": [wins / denominator, mean_auxiliary, completed / denominator],
        "recorded_cpu_seconds": math.fsum(item["cpu_seconds"] for item in records),
        "recorded_decisions": sum(item["decisions"] for item in records),
    }
    body = {
        "schema_version": REPORT_SCHEMA,
        "training_spec_id": spec.spec_id,
        "training_objective_id": spec.training_objective_id,
        "stage": spec.stage.value,
        "evaluation_objective": spec.evaluation_objective.as_dict(),
        "scope": spec.scope.as_dict(),
        "partition": panel.partition,
        "planned_seeds": list(panel.planned_seeds),
        "population_ranking": RANKING_RULE,
        "summary": summary,
        "outcomes": records,
        "claim_scope": "saved_outcome_training_score_only",
        "foundation_readiness_established": False,
    }
    return {**body, "report_id": manifest_identifier(body)}


def assess_training_graduation(
    spec: TrainingScoreSpec, train: TrainingPanel, development: TrainingPanel
) -> dict[str, Any]:
    """A staging recommendation; never an automatic launch or foundation readiness pass."""
    if spec.stage != TrainingStage.BOOTSTRAP:
        raise ValueError("graduation assessment requires the bootstrap stage")
    if train.partition != "train" or development.partition != "development":
        raise ValueError("graduation requires train and development panels")
    if set(train.planned_seeds).intersection(development.planned_seeds):
        raise ValueError("training and development seeds must be disjoint")
    train_score = score_training_panel(spec, train)
    development_score = score_training_panel(spec, development)
    t, d = train_score["summary"], development_score["summary"]
    checks = {
        "independent_train_victories": t["victories"]
        >= spec.graduation.minimum_train_victory_seeds,
        "independent_development_victories": (
            d["victories"] >= spec.graduation.minimum_development_victory_seeds
        ),
        "development_panel_size": (
            d["benchmark_denominator"] >= spec.graduation.minimum_development_runs
        ),
        "development_panel_complete": d["failed_runs"] == 0,
        "training_panel_complete": t["failed_runs"] == 0,
    }
    body = {
        "schema_version": "full-run-training-graduation-v1",
        "training_spec_id": spec.spec_id,
        "train_score_id": train_score["report_id"],
        "development_score_id": development_score["report_id"],
        "checks": checks,
        "terminal_only_stage_recommended": all(checks.values()),
        "next_training_objective_id": TERMINAL_OBJECTIVE_ID,
        "next_stage_started": False,
        "foundation_readiness_established": False,
        "claim_scope": "training_stage_recommendation_only",
    }
    return {**body, "report_id": manifest_identifier(body)}


def _fields(value: object, expected: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ValueError(f"{name} must contain exactly the declared fields")
    return dict(value)


def _integer(value: object, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum or value > 2**63 - 1:
        raise ValueError(f"{name} must be an integer >= {minimum} within signed 64-bit range")
    return value


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(f"{name} must be a finite number") from error
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result
