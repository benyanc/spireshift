from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from spireshift.agents.learned import ProductionCheckpointPolicy
from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.protocols import EnvironmentAdapter
from spireshift.core.types import DecisionType, Observation
from spireshift.liveness import PublicNoOpActionGuard
from spireshift.models import write_model_artifact
from spireshift.splits import SplitManifest, SplitName

LEGACY_CONFIG_SCHEMA_VERSION = "run-level-trajectory-search-config-v2"
FRONTIER_CONFIG_SCHEMA_VERSION = "run-level-trajectory-search-config-v3"
CORRECTED_FRONTIER_CONFIG_SCHEMA_VERSION = "run-level-trajectory-search-config-v4"
LEGACY_CASE_SCHEMA_VERSION = "run-level-trajectory-search-case-v1"
FRONTIER_CASE_SCHEMA_VERSION = "run-level-trajectory-search-case-v2"
CORRECTED_FRONTIER_CASE_SCHEMA_VERSION = "run-level-trajectory-search-case-v3"
LEGACY_REPORT_SCHEMA_VERSION = "run-level-trajectory-search-v1"
FRONTIER_REPORT_SCHEMA_VERSION = "run-level-trajectory-search-v2"
CORRECTED_FRONTIER_REPORT_SCHEMA_VERSION = "run-level-trajectory-search-v3"
LEGACY_VERIFICATION_SCHEMA_VERSION = "run-level-trajectory-search-verification-v1"
FRONTIER_VERIFICATION_SCHEMA_VERSION = "run-level-trajectory-search-verification-v2"
CORRECTED_FRONTIER_VERIFICATION_SCHEMA_VERSION = "run-level-trajectory-search-verification-v3"
MILESTONE_SCHEMA_VERSION = "act1-milestone-semantics-v2"
FRONTIER_RANKING_SCHEMA_VERSION = "public-frontier-ranking-v1"
CORRECTED_FRONTIER_RANKING_SCHEMA_VERSION = "public-frontier-ranking-v2"
FRONTIER_SUMMARY_SCHEMA_VERSION = "public-trajectory-frontier-v1"
CORRECTED_FRONTIER_SUMMARY_SCHEMA_VERSION = "public-trajectory-frontier-v2"
TRAJECTORY_SEARCH_ABLATION_SCHEMA_VERSION = "run-level-trajectory-search-ablation-v2"
LEGACY_SEARCH_CONTROLLER_ID = "policy-guided-trajectory-beam-v1"
FRONTIER_SEARCH_CONTROLLER_ID = "public-frontier-trajectory-beam-v2"
CORRECTED_FRONTIER_SEARCH_CONTROLLER_ID = "public-frontier-trajectory-beam-v3"
LEGACY_CLAIM_SCOPE = "train_only_act1_milestone_trajectory_search"
FRONTIER_CLAIM_SCOPE = "train_only_act1_public_frontier_ablation"
CORRECTED_FRONTIER_CLAIM_SCOPE = "train_only_act1_public_frontier_ablation_v2"

LEGACY_ENEMY_SNAPSHOT_RULE = "terminal_then_last_actionable_v1"
LAST_ACTIONABLE_ENEMY_SNAPSHOT_RULE = "last_actionable_on_deepest_floor_v2"

HASH_TIEBREAK_STRATEGY = "hash_tiebreak_v1"
PUBLIC_FRONTIER_STRATEGY = "public_frontier_v1"
PUBLIC_FRONTIER_DIVERSE_STRATEGY = "public_frontier_diverse_v1"
_FRONTIER_STRATEGIES = {
    HASH_TIEBREAK_STRATEGY,
    PUBLIC_FRONTIER_STRATEGY,
    PUBLIC_FRONTIER_DIVERSE_STRATEGY,
}
_STRATEGIC_DECISION_TYPES = (
    DecisionType.PATH.value,
    DecisionType.REWARD.value,
    DecisionType.EVENT.value,
    DecisionType.REST_SITE.value,
    DecisionType.SHOP.value,
    DecisionType.TREASURE.value,
    DecisionType.CARD_SELECTION.value,
    DecisionType.RELIC_SELECTION.value,
)
_AUXILIARY_RANK_ORDER = (
    "encounter_cleared",
    "enemy_hp_defeated_fraction_ppm",
    "player_hp_fraction_ppm",
    "last_actionable_player_hp_fraction_ppm",
    "distinct_public_states_on_floor",
)


@dataclass(frozen=True, slots=True)
class PublicFrontierRanking:
    strategy: str
    enemy_hp_offset: int
    enemy_slot_size: int
    maximum_enemy_slots: int
    enemy_snapshot_rule: str = LAST_ACTIONABLE_ENEMY_SNAPSHOT_RULE

    def __post_init__(self) -> None:
        if self.strategy not in _FRONTIER_STRATEGIES:
            raise ValueError("Unknown public-frontier ranking strategy")
        if self.enemy_snapshot_rule not in {
            LEGACY_ENEMY_SNAPSHOT_RULE,
            LAST_ACTIONABLE_ENEMY_SNAPSHOT_RULE,
        }:
            raise ValueError("Unknown public-frontier enemy snapshot rule")
        for name, value, minimum in (
            ("enemy_hp_offset", self.enemy_hp_offset, 0),
            ("enemy_slot_size", self.enemy_slot_size, 1),
            ("maximum_enemy_slots", self.maximum_enemy_slots, 1),
        ):
            if isinstance(value, bool) or value < minimum:
                raise ValueError(f"{name} must be at least {minimum}")

    @property
    def diversity_rule(self) -> str:
        return (
            "one_per_strategic_trace_then_fill_within_primary_rank"
            if self.strategy == PUBLIC_FRONTIER_DIVERSE_STRATEGY
            else "none"
        )

    def body(self) -> dict[str, object]:
        body: dict[str, object] = {
            "schema_version": self.schema_version,
            "strategy": self.strategy,
            "information_policy_id": "public-state-v1",
            "enemy_hp_layout": {
                "source": "observation_vector",
                "offset": self.enemy_hp_offset,
                "slot_size": self.enemy_slot_size,
                "maximum_slots": self.maximum_enemy_slots,
            },
            "auxiliary_rank_order": list(_AUXILIARY_RANK_ORDER),
            "strategic_decision_types": list(_STRATEGIC_DECISION_TYPES),
            "diversity_rule": self.diversity_rule,
            "primary_rank_rule": "victory_act1_clear_boss_reach_maximum_floor",
        }
        if self.schema_version == CORRECTED_FRONTIER_RANKING_SCHEMA_VERSION:
            body["enemy_snapshot_rule"] = self.enemy_snapshot_rule
        return body

    @property
    def schema_version(self) -> str:
        return (
            FRONTIER_RANKING_SCHEMA_VERSION
            if self.enemy_snapshot_rule == LEGACY_ENEMY_SNAPSHOT_RULE
            else CORRECTED_FRONTIER_RANKING_SCHEMA_VERSION
        )

    @property
    def frontier_summary_schema_version(self) -> str:
        return (
            FRONTIER_SUMMARY_SCHEMA_VERSION
            if self.enemy_snapshot_rule == LEGACY_ENEMY_SNAPSHOT_RULE
            else CORRECTED_FRONTIER_SUMMARY_SCHEMA_VERSION
        )

    @property
    def ranking_id(self) -> str:
        return manifest_identifier(self.body())

    def as_dict(self) -> dict[str, object]:
        return {**self.body(), "ranking_id": self.ranking_id}

    @classmethod
    def from_mapping(cls, value: object) -> PublicFrontierRanking:
        document = _mapping(value, "public-frontier ranking")
        schema_version = document.get("schema_version")
        if schema_version not in {
            FRONTIER_RANKING_SCHEMA_VERSION,
            CORRECTED_FRONTIER_RANKING_SCHEMA_VERSION,
        }:
            raise ValueError("Public-frontier ranking schema differs")
        expected = {
            "schema_version",
            "ranking_id",
            "strategy",
            "information_policy_id",
            "enemy_hp_layout",
            "auxiliary_rank_order",
            "strategic_decision_types",
            "diversity_rule",
            "primary_rank_rule",
        }
        if schema_version == CORRECTED_FRONTIER_RANKING_SCHEMA_VERSION:
            expected.add("enemy_snapshot_rule")
        if set(document) != expected:
            raise ValueError("Public-frontier ranking fields differ")
        layout = _mapping(document.get("enemy_hp_layout"), "enemy HP layout")
        if set(layout) != {"source", "offset", "slot_size", "maximum_slots"}:
            raise ValueError("Public-frontier enemy HP layout fields differ")
        ranking = cls(
            strategy=_string(document.get("strategy"), "frontier strategy"),
            enemy_hp_offset=_integer(layout.get("offset"), "enemy HP offset"),
            enemy_slot_size=_integer(layout.get("slot_size"), "enemy slot size"),
            maximum_enemy_slots=_integer(layout.get("maximum_slots"), "maximum enemy slots"),
            enemy_snapshot_rule=(
                _string(document.get("enemy_snapshot_rule"), "enemy snapshot rule")
                if schema_version == CORRECTED_FRONTIER_RANKING_SCHEMA_VERSION
                else LEGACY_ENEMY_SNAPSHOT_RULE
            ),
        )
        if document != ranking.as_dict():
            raise ValueError("Public-frontier ranking contract or identity differs")
        return ranking


@dataclass(frozen=True, slots=True)
class Act1Milestones:
    first_act_ids: tuple[str, ...]
    next_act_id: str
    boss_floor: int

    def __post_init__(self) -> None:
        if not self.first_act_ids or any(not act_id for act_id in self.first_act_ids):
            raise ValueError("Milestone act IDs must be non-empty")
        if len(self.first_act_ids) != len(set(self.first_act_ids)):
            raise ValueError("Milestone first-act IDs must be unique")
        if not self.next_act_id or self.next_act_id in self.first_act_ids:
            raise ValueError("Milestone next-act ID must differ from every first-act ID")
        if isinstance(self.boss_floor, bool) or self.boss_floor < 1:
            raise ValueError("Milestone boss floor must be positive")

    def body(self) -> dict[str, object]:
        return {
            "schema_version": MILESTONE_SCHEMA_VERSION,
            "first_act_ids": list(self.first_act_ids),
            "next_act_id": self.next_act_id,
            "boss_floor": self.boss_floor,
            "boss_reach_rule": "observed_first_act_floor_at_least_boss_floor",
            "act1_clear_rule": "observed_next_act_id",
            "terminal_victory_rule": "environment_terminal_victory_only",
        }

    @property
    def milestone_id(self) -> str:
        return manifest_identifier(self.body())

    def as_dict(self) -> dict[str, object]:
        return {**self.body(), "milestone_id": self.milestone_id}

    @classmethod
    def from_mapping(cls, value: object) -> Act1Milestones:
        document = _mapping(value, "milestone semantics")
        expected = {
            "schema_version",
            "milestone_id",
            "first_act_ids",
            "next_act_id",
            "boss_floor",
            "boss_reach_rule",
            "act1_clear_rule",
            "terminal_victory_rule",
        }
        if set(document) != expected:
            raise ValueError("Milestone semantics fields differ")
        if document.get("schema_version") != MILESTONE_SCHEMA_VERSION:
            raise ValueError("Milestone semantics schema differs")
        rules = {
            "boss_reach_rule": "observed_first_act_floor_at_least_boss_floor",
            "act1_clear_rule": "observed_next_act_id",
            "terminal_victory_rule": "environment_terminal_victory_only",
        }
        if any(document.get(key) != rule for key, rule in rules.items()):
            raise ValueError("Milestone semantics rules differ")
        milestones = cls(
            first_act_ids=_string_tuple(document.get("first_act_ids"), "first act IDs"),
            next_act_id=_string(document.get("next_act_id"), "next act ID"),
            boss_floor=_integer(document.get("boss_floor"), "boss floor"),
        )
        if document.get("milestone_id") != milestones.milestone_id:
            raise ValueError("Milestone semantics identity mismatch")
        return milestones


@dataclass(frozen=True, slots=True)
class TrajectorySearchConfig:
    split_manifest_id: str
    ruleset_manifest_id: str
    model_id: str
    training_report_id: str
    run_offset: int
    run_count: int
    generations: int
    beam_width: int
    mutations_per_parent: int
    workers: int
    maximum_decisions_per_run: int
    cycle_repetition_threshold: int
    liveness_tail_length: int
    no_op_fallback_threshold: int
    mutation_salt: str
    milestones: Act1Milestones
    frontier_ranking: PublicFrontierRanking | None = None
    objective_id: str = "terminal-victory-v1"
    partition: str = SplitName.TRAIN.value
    exact_replay_only: bool = True

    def __post_init__(self) -> None:
        if self.partition != SplitName.TRAIN.value:
            raise ValueError("Trajectory search may use only train runs")
        if self.objective_id != "terminal-victory-v1":
            raise ValueError("Trajectory search must preserve terminal victory")
        if self.exact_replay_only is not True:
            raise ValueError("Initial trajectory search must use exact replay only")
        for name, value, minimum in (
            ("run_offset", self.run_offset, 0),
            ("run_count", self.run_count, 1),
            ("generations", self.generations, 1),
            ("beam_width", self.beam_width, 1),
            ("mutations_per_parent", self.mutations_per_parent, 1),
            ("workers", self.workers, 1),
            ("maximum_decisions_per_run", self.maximum_decisions_per_run, 1),
            ("cycle_repetition_threshold", self.cycle_repetition_threshold, 2),
            ("liveness_tail_length", self.liveness_tail_length, 1),
            ("no_op_fallback_threshold", self.no_op_fallback_threshold, 1),
        ):
            if isinstance(value, bool) or value < minimum:
                raise ValueError(f"{name} must be at least {minimum}")
        if not self.mutation_salt:
            raise ValueError("Trajectory search mutation salt must be non-empty")

    def body(self) -> dict[str, object]:
        body: dict[str, object] = {
            "schema_version": self.schema_version,
            "split_manifest_id": self.split_manifest_id,
            "ruleset_manifest_id": self.ruleset_manifest_id,
            "objective_id": self.objective_id,
            "model_id": self.model_id,
            "training_report_id": self.training_report_id,
            "partition": self.partition,
            "run_offset": self.run_offset,
            "run_count": self.run_count,
            "generations": self.generations,
            "beam_width": self.beam_width,
            "mutations_per_parent": self.mutations_per_parent,
            "workers": self.workers,
            "maximum_decisions_per_run": self.maximum_decisions_per_run,
            "cycle_repetition_threshold": self.cycle_repetition_threshold,
            "liveness_tail_length": self.liveness_tail_length,
            "no_op_fallback_threshold": self.no_op_fallback_threshold,
            "search_controller_id": self.search_controller_id,
            "mutation_salt": self.mutation_salt,
            "exact_replay_only": self.exact_replay_only,
            "milestones": self.milestones.as_dict(),
        }
        if self.frontier_ranking is not None:
            body["frontier_ranking"] = self.frontier_ranking.as_dict()
        return body

    @property
    def schema_version(self) -> str:
        if self.frontier_ranking is None:
            return LEGACY_CONFIG_SCHEMA_VERSION
        if self.frontier_ranking.schema_version == FRONTIER_RANKING_SCHEMA_VERSION:
            return FRONTIER_CONFIG_SCHEMA_VERSION
        return CORRECTED_FRONTIER_CONFIG_SCHEMA_VERSION

    @property
    def search_controller_id(self) -> str:
        if self.frontier_ranking is None:
            return LEGACY_SEARCH_CONTROLLER_ID
        if self.frontier_ranking.schema_version == FRONTIER_RANKING_SCHEMA_VERSION:
            return FRONTIER_SEARCH_CONTROLLER_ID
        return CORRECTED_FRONTIER_SEARCH_CONTROLLER_ID

    @property
    def case_schema_version(self) -> str:
        if self.frontier_ranking is None:
            return LEGACY_CASE_SCHEMA_VERSION
        if self.frontier_ranking.schema_version == FRONTIER_RANKING_SCHEMA_VERSION:
            return FRONTIER_CASE_SCHEMA_VERSION
        return CORRECTED_FRONTIER_CASE_SCHEMA_VERSION

    @property
    def report_schema_version(self) -> str:
        if self.frontier_ranking is None:
            return LEGACY_REPORT_SCHEMA_VERSION
        if self.frontier_ranking.schema_version == FRONTIER_RANKING_SCHEMA_VERSION:
            return FRONTIER_REPORT_SCHEMA_VERSION
        return CORRECTED_FRONTIER_REPORT_SCHEMA_VERSION

    @property
    def verification_schema_version(self) -> str:
        if self.frontier_ranking is None:
            return LEGACY_VERIFICATION_SCHEMA_VERSION
        if self.frontier_ranking.schema_version == FRONTIER_RANKING_SCHEMA_VERSION:
            return FRONTIER_VERIFICATION_SCHEMA_VERSION
        return CORRECTED_FRONTIER_VERIFICATION_SCHEMA_VERSION

    @property
    def claim_scope(self) -> str:
        if self.frontier_ranking is None:
            return LEGACY_CLAIM_SCOPE
        if self.frontier_ranking.schema_version == FRONTIER_RANKING_SCHEMA_VERSION:
            return FRONTIER_CLAIM_SCOPE
        return CORRECTED_FRONTIER_CLAIM_SCOPE

    @property
    def config_id(self) -> str:
        return manifest_identifier(self.body())

    def as_dict(self) -> dict[str, object]:
        return {**self.body(), "config_id": self.config_id}

    @classmethod
    def from_mapping(cls, value: object) -> TrajectorySearchConfig:
        document = _mapping(value, "trajectory search config")
        schema_version = document.get("schema_version")
        if schema_version not in {
            LEGACY_CONFIG_SCHEMA_VERSION,
            FRONTIER_CONFIG_SCHEMA_VERSION,
            CORRECTED_FRONTIER_CONFIG_SCHEMA_VERSION,
        }:
            raise ValueError("Trajectory search config schema differs")
        expected = {
            "schema_version",
            "config_id",
            "split_manifest_id",
            "ruleset_manifest_id",
            "objective_id",
            "model_id",
            "training_report_id",
            "partition",
            "run_offset",
            "run_count",
            "generations",
            "beam_width",
            "mutations_per_parent",
            "workers",
            "maximum_decisions_per_run",
            "cycle_repetition_threshold",
            "liveness_tail_length",
            "no_op_fallback_threshold",
            "search_controller_id",
            "mutation_salt",
            "exact_replay_only",
            "milestones",
        }
        if schema_version in {
            FRONTIER_CONFIG_SCHEMA_VERSION,
            CORRECTED_FRONTIER_CONFIG_SCHEMA_VERSION,
        }:
            expected.add("frontier_ranking")
        if set(document) != expected:
            raise ValueError("Trajectory search config fields differ")
        expected_controller = {
            LEGACY_CONFIG_SCHEMA_VERSION: LEGACY_SEARCH_CONTROLLER_ID,
            FRONTIER_CONFIG_SCHEMA_VERSION: FRONTIER_SEARCH_CONTROLLER_ID,
            CORRECTED_FRONTIER_CONFIG_SCHEMA_VERSION: CORRECTED_FRONTIER_SEARCH_CONTROLLER_ID,
        }[schema_version]
        if document.get("search_controller_id") != expected_controller:
            raise ValueError("Trajectory search controller differs")
        config = cls(
            split_manifest_id=_string(document.get("split_manifest_id"), "split manifest ID"),
            ruleset_manifest_id=_string(document.get("ruleset_manifest_id"), "ruleset ID"),
            objective_id=_string(document.get("objective_id"), "objective ID"),
            model_id=_string(document.get("model_id"), "model ID"),
            training_report_id=_string(document.get("training_report_id"), "training report ID"),
            partition=_string(document.get("partition"), "partition"),
            run_offset=_integer(document.get("run_offset"), "run offset"),
            run_count=_integer(document.get("run_count"), "run count"),
            generations=_integer(document.get("generations"), "generations"),
            beam_width=_integer(document.get("beam_width"), "beam width"),
            mutations_per_parent=_integer(
                document.get("mutations_per_parent"), "mutations per parent"
            ),
            workers=_integer(document.get("workers"), "workers"),
            maximum_decisions_per_run=_integer(
                document.get("maximum_decisions_per_run"), "maximum decisions"
            ),
            cycle_repetition_threshold=_integer(
                document.get("cycle_repetition_threshold"), "cycle threshold"
            ),
            liveness_tail_length=_integer(
                document.get("liveness_tail_length"), "liveness tail length"
            ),
            no_op_fallback_threshold=_integer(
                document.get("no_op_fallback_threshold"), "fallback threshold"
            ),
            mutation_salt=_string(document.get("mutation_salt"), "mutation salt"),
            exact_replay_only=_boolean(document.get("exact_replay_only"), "exact replay flag"),
            milestones=Act1Milestones.from_mapping(document.get("milestones")),
            frontier_ranking=(
                PublicFrontierRanking.from_mapping(document.get("frontier_ranking"))
                if schema_version
                in {FRONTIER_CONFIG_SCHEMA_VERSION, CORRECTED_FRONTIER_CONFIG_SCHEMA_VERSION}
                else None
            ),
        )
        if config.schema_version != schema_version:
            raise ValueError("Trajectory search config and frontier-ranking schemas differ")
        if document.get("config_id") != config.config_id:
            raise ValueError("Trajectory search config identity mismatch")
        return config


@dataclass(frozen=True, slots=True)
class TrajectorySearchResult:
    successful: bool
    report_path: Path
    report: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _MutationPlan:
    parent: dict[str, Any]
    decision_index: int
    action_id: str
    offspring_index: int


def load_trajectory_search_config(path: Path) -> TrajectorySearchConfig:
    return TrajectorySearchConfig.from_mapping(_load_object(path, "trajectory search config"))


def run_trajectory_search(
    *,
    environment_factory: Callable[[], EnvironmentAdapter],
    ruleset: RulesetIdentity,
    policy: ProductionCheckpointPolicy,
    split_manifest: SplitManifest,
    training_report_id: str,
    config: TrajectorySearchConfig,
    output_directory: Path,
    resume: bool = False,
    now: Callable[[], str] | None = None,
) -> TrajectorySearchResult:
    _validate_inputs(
        ruleset=ruleset,
        policy=policy,
        split_manifest=split_manifest,
        training_report_id=training_report_id,
        config=config,
    )
    seeds = split_manifest.seeds(SplitName.TRAIN)[
        config.run_offset : config.run_offset + config.run_count
    ]
    if len(seeds) != config.run_count:
        raise ValueError("Trajectory search seed window exceeds the train partition")
    milestone_preflight = _milestone_preflight(
        environment_factory=environment_factory,
        ruleset=ruleset,
        seed=seeds[0],
        milestones=config.milestones,
    )
    output_directory = output_directory.expanduser().resolve()
    if output_directory.exists() and not resume:
        raise FileExistsError(f"Trajectory search output already exists: {output_directory}")
    output_directory.mkdir(parents=True, exist_ok=True)
    report_path = output_directory / "run-level-trajectory-search.json"
    if report_path.exists():
        raise FileExistsError(f"Trajectory search report already exists: {report_path}")

    started_at = (now or _utc_now)()
    cases: list[dict[str, Any]] = []
    pending: list[tuple[int, Path]] = []
    for seed in seeds:
        path = _case_path(output_directory, seed)
        if path.exists():
            cases.append(_load_case(path, seed=seed, config=config, policy=policy))
        else:
            pending.append((seed, path))

    maximum_workers = min(config.workers, max(1, len(pending)))
    with ThreadPoolExecutor(max_workers=maximum_workers) as executor:
        futures: dict[Future[dict[str, Any]], tuple[int, Path]] = {}
        for seed, path in pending:
            future = executor.submit(
                _run_seed_search,
                environment_factory=environment_factory,
                ruleset=ruleset,
                policy=policy,
                config=config,
                seed=seed,
            )
            futures[future] = (seed, path)
        for future in as_completed(futures):
            path = futures[future][1]
            case = future.result()
            write_model_artifact(case, path, label="trajectory search case")
            cases.append(case)

    ordered = sorted(cases, key=lambda case: int(case["seed"]))
    if len(ordered) != config.run_count:
        raise RuntimeError("Trajectory search did not produce every configured seed case")
    summary = _summary(ordered)
    references = [_case_reference(output_directory, case) for case in ordered]
    milestone_references = [
        reference
        for reference, case in zip(references, ordered, strict=True)
        if case["status"] == "completed"
        and (case["best_trajectory"]["boss_reached"] or case["best_trajectory"]["act1_cleared"])
    ]
    body: dict[str, Any] = {
        "schema_version": config.report_schema_version,
        "started_at": started_at,
        "completed_at": (now or _utc_now)(),
        "config_id": config.config_id,
        "model_id": policy.model_id,
        "training_report_id": training_report_id,
        "split_manifest_id": split_manifest.manifest_id,
        "partition": SplitName.TRAIN.value,
        "ruleset_manifest_id": ruleset.manifest_id,
        "patch_id": ruleset.patch_id,
        "objective_id": "terminal-victory-v1",
        "search_controller_id": config.search_controller_id,
        "hidden_state_resampling": False,
        "configuration": config.as_dict(),
        "milestone_preflight": milestone_preflight,
        "cases": references,
        "milestone_cases": milestone_references,
        "summary": summary,
        "readiness": _readiness(summary),
        "claim_scope": config.claim_scope,
    }
    report = {**body, "report_id": manifest_identifier(body)}
    write_model_artifact(report, report_path, label="trajectory search report")
    return TrajectorySearchResult(
        successful=int(summary["failed_seed_cases"]) == 0,
        report_path=report_path,
        report=report,
    )


def verify_trajectory_search(
    report_path: Path,
    *,
    config: TrajectorySearchConfig,
    split_manifest: SplitManifest,
) -> dict[str, Any]:
    errors: list[str] = []
    report_id: str | None = None
    verified_cases = 0
    try:
        report = _load_object(report_path, "trajectory search report")
        report_id = report.get("report_id") if isinstance(report.get("report_id"), str) else None
        body = {key: value for key, value in report.items() if key != "report_id"}
        if report_id != manifest_identifier(body):
            raise ValueError("Trajectory search report identity mismatch")
        expected = {
            "schema_version": config.report_schema_version,
            "config_id": config.config_id,
            "model_id": config.model_id,
            "training_report_id": config.training_report_id,
            "split_manifest_id": split_manifest.manifest_id,
            "partition": SplitName.TRAIN.value,
            "ruleset_manifest_id": split_manifest.ruleset_manifest_id,
            "objective_id": split_manifest.objective_id,
            "search_controller_id": config.search_controller_id,
            "hidden_state_resampling": False,
            "configuration": config.as_dict(),
            "claim_scope": config.claim_scope,
        }
        if any(report.get(key) != value for key, value in expected.items()):
            raise ValueError("Trajectory search report provenance differs")
        _validate_milestone_preflight(report.get("milestone_preflight"), config=config)
        seeds = split_manifest.seeds(SplitName.TRAIN)[
            config.run_offset : config.run_offset + config.run_count
        ]
        references = report.get("cases")
        if not isinstance(references, list):
            raise ValueError("Trajectory search case references are missing")
        root = report_path.expanduser().resolve().parent
        cases: list[dict[str, Any]] = []
        seen: set[int] = set()
        for raw_reference in references:
            reference = _mapping(raw_reference, "trajectory search case reference")
            seed = _integer(reference.get("seed"), "case seed")
            if seed in seen:
                raise ValueError("Trajectory search repeats a seed case")
            seen.add(seed)
            relative_path = Path(_string(reference.get("path"), "case path"))
            case_path = (root / relative_path).resolve()
            if root not in case_path.parents:
                raise ValueError("Trajectory search case escapes its report root")
            case = _load_case_document(case_path, seed=seed, config=config)
            if reference.get("case_id") != case["case_id"]:
                raise ValueError("Trajectory search case reference identity mismatch")
            cases.append(case)
            verified_cases += 1
        if seen != set(seeds):
            raise ValueError("Trajectory search seed coverage differs")
        ordered = sorted(cases, key=lambda case: int(case["seed"]))
        expected_summary = _summary(ordered)
        if report.get("summary") != expected_summary:
            raise ValueError("Trajectory search summary differs from its cases")
        expected_milestones = [
            _case_reference(root, case)
            for case in ordered
            if case["status"] == "completed"
            and (case["best_trajectory"]["boss_reached"] or case["best_trajectory"]["act1_cleared"])
        ]
        if report.get("milestone_cases") != expected_milestones:
            raise ValueError("Trajectory search milestone references differ")
        if report.get("readiness") != _readiness(expected_summary):
            raise ValueError("Trajectory search readiness differs from its cases")
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        errors.append(str(error))
    body = {
        "schema_version": config.verification_schema_version,
        "valid": not errors,
        "report_id": report_id,
        "config_id": config.config_id,
        "verified_cases": verified_cases,
        "errors": errors,
    }
    return {**body, "verification_id": manifest_identifier(body)}


def compare_trajectory_search_ablation(
    *,
    legacy_report_path: Path,
    frontier_report_path: Path,
    diverse_report_path: Path,
    legacy_config: TrajectorySearchConfig,
    frontier_config: TrajectorySearchConfig,
    diverse_config: TrajectorySearchConfig,
    split_manifest: SplitManifest,
) -> dict[str, Any]:
    arms = (
        (HASH_TIEBREAK_STRATEGY, legacy_report_path, legacy_config),
        (PUBLIC_FRONTIER_STRATEGY, frontier_report_path, frontier_config),
        (PUBLIC_FRONTIER_DIVERSE_STRATEGY, diverse_report_path, diverse_config),
    )
    signatures = [_ablation_config_signature(config) for _, _, config in arms]
    if any(signature != signatures[0] for signature in signatures[1:]):
        raise ValueError("Trajectory-search ablation arms do not have equal frozen budgets")
    if legacy_config.frontier_ranking is not None:
        raise ValueError("Trajectory-search hash baseline must use the frozen v2 config")
    if (
        frontier_config.frontier_ranking is None
        or frontier_config.frontier_ranking.strategy != PUBLIC_FRONTIER_STRATEGY
    ):
        raise ValueError("Trajectory-search frontier arm has the wrong strategy")
    if (
        diverse_config.frontier_ranking is None
        or diverse_config.frontier_ranking.strategy != PUBLIC_FRONTIER_DIVERSE_STRATEGY
    ):
        raise ValueError("Trajectory-search diverse arm has the wrong strategy")
    for config in (frontier_config, diverse_config):
        assert config.frontier_ranking is not None
        if config.frontier_ranking.schema_version != CORRECTED_FRONTIER_RANKING_SCHEMA_VERSION:
            raise ValueError("Trajectory-search frontier arm uses retired enemy-progress semantics")

    arm_reports: list[dict[str, Any]] = []
    expected_seeds: set[int] | None = None
    for strategy, path, config in arms:
        verification = verify_trajectory_search(
            path,
            config=config,
            split_manifest=split_manifest,
        )
        if verification["valid"] is not True:
            raise ValueError(
                f"Trajectory-search ablation arm {strategy} is invalid: {verification['errors']}"
            )
        report = _load_object(path, f"trajectory-search {strategy} report")
        references = report.get("cases")
        if not isinstance(references, list):
            raise ValueError("Trajectory-search ablation arm has no cases")
        seeds = {
            _integer(_mapping(reference, "ablation case reference").get("seed"), "case seed")
            for reference in references
        }
        if expected_seeds is None:
            expected_seeds = seeds
        elif seeds != expected_seeds:
            raise ValueError("Trajectory-search ablation seed coverage differs")
        summary = _mapping(report.get("summary"), "trajectory-search summary")
        best = _mapping(summary.get("best"), "trajectory-search best summary")
        arm_reports.append(
            {
                "strategy": strategy,
                "config_id": config.config_id,
                "report_id": report["report_id"],
                "verification_id": verification["verification_id"],
                "evaluated_trajectories": summary["evaluated_trajectories"],
                "failed_seed_cases": summary["failed_seed_cases"],
                "best": best,
                "paired": summary["paired"],
            }
        )

    hash_floor = float(arm_reports[0]["best"]["mean_maximum_floor"])
    frontier_gain = _artifact_float(
        float(arm_reports[1]["best"]["mean_maximum_floor"]) - hash_floor
    )
    diverse_gain = _artifact_float(float(arm_reports[2]["best"]["mean_maximum_floor"]) - hash_floor)
    milestone_found = any(
        int(arm["best"]["boss_reaches"]) > 0 or int(arm["best"]["act1_clears"]) > 0
        for arm in arm_reports[1:]
    )
    material_threshold = 0.5
    material_improvement = max(frontier_gain, diverse_gain) >= material_threshold
    body: dict[str, Any] = {
        "schema_version": TRAJECTORY_SEARCH_ABLATION_SCHEMA_VERSION,
        "split_manifest_id": split_manifest.manifest_id,
        "partition": SplitName.TRAIN.value,
        "objective_id": split_manifest.objective_id,
        "ruleset_manifest_id": split_manifest.ruleset_manifest_id,
        "seed_count": len(expected_seeds or ()),
        "equal_budget": signatures[0],
        "arms": arm_reports,
        "comparison": {
            "frontier_mean_maximum_floor_gain_over_hash": frontier_gain,
            "diverse_mean_maximum_floor_gain_over_hash": diverse_gain,
            "material_mean_maximum_floor_gain_threshold": material_threshold,
            "boss_reach_or_act1_clear_found": milestone_found,
            "material_fixed_budget_improvement_found": material_improvement,
        },
        "readiness": {
            "advance_search_foundation": milestone_found or material_improvement,
            "recommended_next_step": (
                "advance_best_frontier_strategy"
                if milestone_found or material_improvement
                else "reassess_policy_representation_or_environment"
            ),
        },
        "claim_scope": CORRECTED_FRONTIER_CLAIM_SCOPE,
    }
    return {**body, "ablation_id": manifest_identifier(body)}


def _ablation_config_signature(config: TrajectorySearchConfig) -> dict[str, Any]:
    return {
        "split_manifest_id": config.split_manifest_id,
        "ruleset_manifest_id": config.ruleset_manifest_id,
        "objective_id": config.objective_id,
        "model_id": config.model_id,
        "training_report_id": config.training_report_id,
        "partition": config.partition,
        "run_offset": config.run_offset,
        "run_count": config.run_count,
        "generations": config.generations,
        "beam_width": config.beam_width,
        "mutations_per_parent": config.mutations_per_parent,
        "workers": config.workers,
        "maximum_decisions_per_run": config.maximum_decisions_per_run,
        "cycle_repetition_threshold": config.cycle_repetition_threshold,
        "liveness_tail_length": config.liveness_tail_length,
        "no_op_fallback_threshold": config.no_op_fallback_threshold,
        "mutation_salt": config.mutation_salt,
        "exact_replay_only": config.exact_replay_only,
        "milestone_id": config.milestones.milestone_id,
    }


def _run_seed_search(
    *,
    environment_factory: Callable[[], EnvironmentAdapter],
    ruleset: RulesetIdentity,
    policy: ProductionCheckpointPolicy,
    config: TrajectorySearchConfig,
    seed: int,
) -> dict[str, Any]:
    try:
        baseline = _run_trajectory(
            environment_factory=environment_factory,
            ruleset=ruleset,
            policy=policy,
            config=config,
            seed=seed,
            generation=0,
            parent=None,
            mutation=None,
        )
        trajectories = [baseline]
        beam = [baseline]
        generations = [_generation_record(0, [baseline], [baseline], baseline, config=config)]
        incumbent = baseline
        seen_plans: set[tuple[str, int, str]] = set()
        for generation in range(1, config.generations + 1):
            if incumbent["victory"] is True:
                break
            plans: list[_MutationPlan] = []
            for parent in beam:
                plans.extend(
                    _mutation_plans(
                        parent,
                        generation=generation,
                        config=config,
                        seen=seen_plans,
                    )
                )
            children = [
                _run_trajectory(
                    environment_factory=environment_factory,
                    ruleset=ruleset,
                    policy=policy,
                    config=config,
                    seed=seed,
                    generation=generation,
                    parent=plan.parent,
                    mutation=plan,
                )
                for plan in plans
            ]
            if not children:
                break
            trajectories.extend(children)
            beam = _select_beam([*beam, *children], config=config)
            next_incumbent = beam[0]
            if _selection_rank(next_incumbent, config=config) < _selection_rank(
                incumbent, config=config
            ):
                raise RuntimeError("Trajectory search incumbent regressed")
            incumbent = next_incumbent
            generations.append(
                _generation_record(generation, children, beam, incumbent, config=config)
            )
        body: dict[str, Any] = {
            "schema_version": config.case_schema_version,
            "config_id": config.config_id,
            "seed": seed,
            "partition": SplitName.TRAIN.value,
            "model_id": policy.model_id,
            "policy_id": policy.policy_id,
            "ruleset_manifest_id": ruleset.manifest_id,
            "milestone_id": config.milestones.milestone_id,
            "search_controller_id": config.search_controller_id,
            "hidden_state_resampling": False,
            "status": "completed",
            "error": None,
            "baseline_trajectory_id": baseline["trajectory_id"],
            "best_trajectory_id": incumbent["trajectory_id"],
            "best_trajectory": _trajectory_outcome(incumbent, config=config),
            "generations": generations,
            "trajectories": trajectories,
        }
    except Exception as error:
        body = {
            "schema_version": config.case_schema_version,
            "config_id": config.config_id,
            "seed": seed,
            "partition": SplitName.TRAIN.value,
            "model_id": policy.model_id,
            "policy_id": policy.policy_id,
            "ruleset_manifest_id": ruleset.manifest_id,
            "milestone_id": config.milestones.milestone_id,
            "search_controller_id": config.search_controller_id,
            "hidden_state_resampling": False,
            "status": "failed",
            "error": f"{type(error).__name__}: {error}",
            "baseline_trajectory_id": None,
            "best_trajectory_id": None,
            "best_trajectory": None,
            "generations": [],
            "trajectories": [],
        }
    return {**body, "case_id": manifest_identifier(body)}


def _run_trajectory(
    *,
    environment_factory: Callable[[], EnvironmentAdapter],
    ruleset: RulesetIdentity,
    policy: ProductionCheckpointPolicy,
    config: TrajectorySearchConfig,
    seed: int,
    generation: int,
    parent: dict[str, Any] | None,
    mutation: _MutationPlan | None,
) -> dict[str, Any]:
    environment: EnvironmentAdapter | None = None
    try:
        environment = environment_factory()
        if environment.ruleset != ruleset:
            raise ValueError("Trajectory search environment ruleset changed")
        observation = environment.reset(seed)
        public_observations = [observation]
        guard = PublicNoOpActionGuard(
            repetition_threshold=config.no_op_fallback_threshold,
            event_limit=config.liveness_tail_length,
        )
        parent_decisions = [] if parent is None else list(parent["decisions"])
        records: list[dict[str, Any]] = []
        action_ids: list[str] = []
        observed_acts: list[str] = []
        maximum_floor = _public_integer(observation.public_state.get("floor")) or 0
        _record_act(observed_acts, observation)
        terminal = bool(observation.public_state.get("terminal"))
        victory = bool(observation.public_state.get("victory")) if terminal else False
        termination_reason = "terminal" if terminal else "decision_limit"
        replay_aligned = True
        replay_divergence: dict[str, Any] | None = None
        mutation_applied = False
        transition_counts: dict[tuple[str, str, str], int] = {}
        maximum_transition_repetitions = 0
        cycle_transition: tuple[str, str, str] | None = None

        for decision_index in range(config.maximum_decisions_per_run):
            if terminal:
                break
            legal_actions = tuple(environment.legal_actions())
            if not legal_actions:
                raise RuntimeError("Nonterminal trajectory-search state has no legal actions")
            eligible_actions = guard.eligible_actions(observation, legal_actions)
            decision = policy.predict(observation, eligible_actions)
            selected = decision.selected_action
            selection_source = "base_policy"
            expected_parent_state: str | None = None
            if (
                mutation is not None
                and decision_index <= mutation.decision_index
                and replay_aligned
            ):
                if decision_index >= len(parent_decisions):
                    replay_aligned = False
                    replay_divergence = _divergence(
                        decision_index, "parent_trace_ended", None, observation.state_hash
                    )
                else:
                    parent_record = _mapping(parent_decisions[decision_index], "parent decision")
                    expected_parent_state = _string(
                        parent_record.get("source_state_hash"), "parent source state hash"
                    )
                    if expected_parent_state != observation.state_hash:
                        replay_aligned = False
                        replay_divergence = _divergence(
                            decision_index,
                            "public_state_mismatch",
                            expected_parent_state,
                            observation.state_hash,
                        )
                    else:
                        desired_id = (
                            mutation.action_id
                            if decision_index == mutation.decision_index
                            else _string(
                                parent_record.get("selected_action_id"),
                                "parent selected action",
                            )
                        )
                        by_id = {action.action_id: action for action in eligible_actions}
                        desired = by_id.get(desired_id)
                        if desired is None:
                            replay_aligned = False
                            replay_divergence = _divergence(
                                decision_index,
                                "action_not_eligible",
                                expected_parent_state,
                                observation.state_hash,
                            )
                        else:
                            selected = desired
                            if decision_index == mutation.decision_index:
                                selection_source = "mutation"
                                mutation_applied = True
                            else:
                                selection_source = "parent_replay"
            if selected not in legal_actions:
                raise RuntimeError("Trajectory search selected an illegal action")
            source = observation
            transition = environment.step(selected)
            observation = transition.next_observation
            public_observations.append(observation)
            guard.observe_transition(
                observation=source,
                action=selected,
                next_observation=observation,
                decision_index=decision_index,
            )
            action_ids.append(selected.action_id)
            records.append(
                {
                    "decision_index": decision_index,
                    "decision_type": source.decision_type.value,
                    "source_state_hash": source.state_hash,
                    "source_floor": _public_integer(source.public_state.get("floor")),
                    "source_act": source.public_state.get("act"),
                    "candidate_action_ids": list(decision.source_action_ids),
                    "policy": [_artifact_float(value) for value in decision.policy],
                    "argmax_action_id": decision.selected_action.action_id,
                    "selected_action_id": selected.action_id,
                    "selection_source": selection_source,
                    "next_state_hash": observation.state_hash,
                    "terminal_after_action": transition.terminal,
                    "victory_after_action": transition.victory,
                }
            )
            maximum_floor = max(
                maximum_floor,
                _public_integer(observation.public_state.get("floor")) or 0,
            )
            _record_act(observed_acts, observation)
            terminal = transition.terminal
            victory = transition.victory if terminal else False
            key = (source.state_hash, selected.action_id, observation.state_hash)
            transition_counts[key] = transition_counts.get(key, 0) + 1
            maximum_transition_repetitions = max(
                maximum_transition_repetitions, transition_counts[key]
            )
            if terminal:
                termination_reason = "terminal"
                break
            if transition_counts[key] >= config.cycle_repetition_threshold:
                termination_reason = "policy_cycle"
                cycle_transition = key
                break

        boss_reached = _boss_reached(
            records=records,
            maximum_floor=maximum_floor,
            milestones=config.milestones,
        )
        act1_cleared = config.milestones.next_act_id in observed_acts
        action_trace_sha256 = "sha256:" + hashlib.sha256("\n".join(action_ids).encode()).hexdigest()
        mutation_evidence = None
        if mutation is not None:
            mutation_evidence = {
                "parent_trajectory_id": mutation.parent["trajectory_id"],
                "requested_decision_index": mutation.decision_index,
                "requested_action_id": mutation.action_id,
                "offspring_index": mutation.offspring_index,
                "applied": mutation_applied,
                "replay_aligned_through_mutation": mutation_applied,
                "divergence": replay_divergence,
            }
        body: dict[str, Any] = {
            "generation": generation,
            "parent_trajectory_id": None if parent is None else parent["trajectory_id"],
            "mutation": mutation_evidence,
            "decisions": records,
            "terminal": terminal,
            "victory": victory if terminal else False,
            "truncated": not terminal,
            "termination_reason": termination_reason,
            "maximum_floor": maximum_floor,
            "observed_acts": observed_acts,
            "boss_reached": boss_reached,
            "act1_cleared": act1_cleared,
            "final_state_hash": observation.state_hash,
            "action_trace_sha256": action_trace_sha256,
            "liveness": {
                "schema_version": "trajectory-search-liveness-v1",
                "cycle_detected": cycle_transition is not None,
                "repetition_threshold": config.cycle_repetition_threshold,
                "maximum_public_transition_repetitions": maximum_transition_repetitions,
                "repeated_source_state_hash": (
                    None if cycle_transition is None else cycle_transition[0]
                ),
                "repeated_action_id": None if cycle_transition is None else cycle_transition[1],
                "repeated_next_state_hash": (
                    None if cycle_transition is None else cycle_transition[2]
                ),
            },
            "fallback": guard.as_dict(),
        }
        if config.frontier_ranking is not None:
            body["public_frontier"] = _public_frontier_summary(
                observations=public_observations,
                records=records,
                maximum_floor=maximum_floor,
                ranking=config.frontier_ranking,
            )
        return {**body, "trajectory_id": manifest_identifier(body)}
    finally:
        if environment is not None:
            close = getattr(environment, "close", None)
            if callable(close):
                close()


def _public_frontier_summary(
    *,
    observations: Sequence[Observation],
    records: Sequence[dict[str, Any]],
    maximum_floor: int,
    ranking: PublicFrontierRanking,
) -> dict[str, Any]:
    deepest_observations = [
        observation
        for observation in observations
        if (_public_integer(observation.public_state.get("floor")) or 0) == maximum_floor
    ]
    if not deepest_observations:
        raise ValueError("Trajectory has no public observation at its maximum floor")
    deepest = deepest_observations[-1]
    actionable = next(
        (
            observation
            for observation in reversed(deepest_observations)
            if observation.decision_type is not DecisionType.TERMINAL
            and observation.public_state.get("terminal") is not True
        ),
        None,
    )
    if (
        ranking.enemy_snapshot_rule == LAST_ACTIONABLE_ENEMY_SNAPSHOT_RULE
        and actionable is not None
    ):
        enemy_source = actionable
        enemy_snapshot = _enemy_hp_snapshot(enemy_source, ranking=ranking)
    else:
        enemy_source = deepest
        enemy_snapshot = _enemy_hp_snapshot(enemy_source, ranking=ranking)
        if enemy_snapshot is None and actionable is not None:
            enemy_source = actionable
            enemy_snapshot = _enemy_hp_snapshot(enemy_source, ranking=ranking)
    encounter_identity = _encounter_identity(enemy_source)
    enemy_references = [
        snapshot[0]
        for observation in deepest_observations
        if _encounter_identity(observation) == encounter_identity
        and (snapshot := _enemy_hp_snapshot(observation, ranking=ranking)) is not None
    ]
    enemy_current = None if enemy_snapshot is None else enemy_snapshot[0]
    living_enemies = None if enemy_snapshot is None else enemy_snapshot[1]
    enemy_reference = max(enemy_references) if enemy_references else None
    enemy_defeated_fraction = (
        _artifact_float(1.0 - (enemy_current / enemy_reference))
        if enemy_current is not None and enemy_reference is not None and enemy_reference > 0
        else None
    )
    deepest_hp = _hp_values(deepest)
    actionable_hp = None if actionable is None else _hp_values(actionable)
    strategic_trace = manifest_identifier(
        {
            "schema_version": "strategic-action-trace-v1",
            "decisions": [
                {
                    "decision_index": record["decision_index"],
                    "decision_type": record["decision_type"],
                    "selected_action_id": record["selected_action_id"],
                }
                for record in records
                if record.get("decision_type") in _STRATEGIC_DECISION_TYPES
            ],
        }
    )
    state = deepest.public_state
    enemy_state_hash = None if enemy_snapshot is None else enemy_source.state_hash
    body: dict[str, Any] = {
        "schema_version": ranking.frontier_summary_schema_version,
        "ranking_id": ranking.ranking_id,
        "information_policy_id": "public-state-v1",
        "state_hash": deepest.state_hash,
        "last_actionable_state_hash": None if actionable is None else actionable.state_hash,
        "enemy_snapshot_state_hash": enemy_state_hash,
        "floor": maximum_floor,
        "act": _public_scalar(state.get("act")),
        "decision_type": deepest.decision_type.value,
        "last_actionable_decision_type": (
            None if actionable is None else actionable.decision_type.value
        ),
        "phase": _public_scalar(state.get("phase")),
        "terminal": state.get("terminal") is True,
        "player_hp": None if deepest_hp is None else deepest_hp[0],
        "player_max_hp": None if deepest_hp is None else deepest_hp[1],
        "player_hp_fraction": None if deepest_hp is None else deepest_hp[2],
        "last_actionable_player_hp_fraction": (None if actionable_hp is None else actionable_hp[2]),
        "encounter_id": _public_scalar(enemy_source.public_state.get("encounter_id")),
        "encounter": (
            enemy_source.public_state.get("encounter")
            if isinstance(enemy_source.public_state.get("encounter"), str)
            else None
        ),
        "decisions_on_floor": sum(
            (_public_integer(record.get("source_floor")) or 0) == maximum_floor
            for record in records
        ),
        "distinct_public_states_on_floor": len(
            {observation.state_hash for observation in deepest_observations}
        ),
        "enemy_hp_available": enemy_snapshot is not None,
        "enemy_hp_current": enemy_current,
        "enemy_hp_reference": enemy_reference,
        "enemy_hp_defeated_fraction": enemy_defeated_fraction,
        "living_enemy_count": living_enemies,
        "encounter_cleared": (
            enemy_current == 0 and enemy_reference is not None and enemy_reference > 0
        ),
        "strategic_trace_sha256": strategic_trace,
    }
    return {**body, "frontier_id": manifest_identifier(body)}


def _enemy_hp_snapshot(
    observation: Observation, *, ranking: PublicFrontierRanking
) -> tuple[int, int] | None:
    state = observation.public_state
    vector = state.get("observation_vector")
    enemy_ids = state.get("enemy_def_ids")
    if not isinstance(vector, list) or not isinstance(enemy_ids, list) or not enemy_ids:
        return None
    slots = min(len(enemy_ids), ranking.maximum_enemy_slots)
    hit_points: list[int] = []
    for slot in range(slots):
        index = ranking.enemy_hp_offset + slot * ranking.enemy_slot_size
        if index >= len(vector):
            return None
        value = vector[index]
        if not isinstance(value, int) or isinstance(value, bool):
            return None
        hit_points.append(max(0, value))
    return sum(hit_points), sum(value > 0 for value in hit_points)


def _encounter_identity(observation: Observation) -> tuple[object, object]:
    state = observation.public_state
    return (_public_scalar(state.get("encounter_id")), _public_scalar(state.get("encounter")))


def _hp_values(observation: Observation) -> tuple[int, int, float] | None:
    hp = _public_integer(observation.public_state.get("player_hp"))
    maximum = _public_integer(observation.public_state.get("player_max_hp"))
    if hp is None or maximum is None or maximum <= 0:
        return None
    return hp, maximum, _artifact_float(min(1.0, max(0.0, hp / maximum)))


def _public_scalar(value: object) -> int | str | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, (int, str)) else None


def _mutation_plans(
    parent: dict[str, Any],
    *,
    generation: int,
    config: TrajectorySearchConfig,
    seen: set[tuple[str, int, str]],
) -> list[_MutationPlan]:
    choices: list[tuple[int, str]] = []
    for record in parent["decisions"]:
        candidate_ids = record.get("candidate_action_ids")
        policy = record.get("policy")
        selected_id = record.get("selected_action_id")
        if not isinstance(candidate_ids, list) or not isinstance(policy, list):
            continue
        alternatives = [
            (float(policy[index]), str(action_id))
            for index, action_id in enumerate(candidate_ids)
            if action_id != selected_id
        ]
        alternatives.sort(key=lambda item: (-item[0], item[1]))
        choices.extend((int(record["decision_index"]), action_id) for _, action_id in alternatives)
    choices.sort(
        key=lambda choice: _digest_integer(
            config.mutation_salt,
            parent["trajectory_id"],
            generation,
            choice[0],
            choice[1],
        )
    )
    plans: list[_MutationPlan] = []
    for decision_index, action_id in choices:
        key = (str(parent["trajectory_id"]), decision_index, action_id)
        if key in seen:
            continue
        seen.add(key)
        plans.append(
            _MutationPlan(
                parent=parent,
                decision_index=decision_index,
                action_id=action_id,
                offspring_index=len(plans),
            )
        )
        if len(plans) == config.mutations_per_parent:
            break
    return plans


def _select_beam(
    trajectories: Sequence[dict[str, Any]], *, config: TrajectorySearchConfig
) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for trajectory in trajectories:
        trace = str(trajectory["action_trace_sha256"])
        current = unique.get(trace)
        if current is None or _trajectory_sort_key(
            trajectory, config=config
        ) < _trajectory_sort_key(current, config=config):
            unique[trace] = trajectory
    ordered = sorted(
        unique.values(), key=lambda trajectory: _trajectory_sort_key(trajectory, config=config)
    )
    if (
        config.frontier_ranking is None
        or config.frontier_ranking.strategy != PUBLIC_FRONTIER_DIVERSE_STRATEGY
    ):
        return ordered[: config.beam_width]

    selected: list[dict[str, Any]] = []
    primary_ranks: list[tuple[int, int, int, int]] = []
    for trajectory in ordered:
        rank = _trajectory_rank(trajectory)
        if rank not in primary_ranks:
            primary_ranks.append(rank)
    for rank in primary_ranks:
        remaining = config.beam_width - len(selected)
        if remaining <= 0:
            break
        group = [trajectory for trajectory in ordered if _trajectory_rank(trajectory) == rank]
        diverse: list[dict[str, Any]] = []
        duplicates: list[dict[str, Any]] = []
        seen_strategic_traces: set[str] = set()
        for trajectory in group:
            strategic_trace = _frontier_strategic_trace(trajectory)
            if strategic_trace in seen_strategic_traces:
                duplicates.append(trajectory)
            else:
                seen_strategic_traces.add(strategic_trace)
                diverse.append(trajectory)
        selected.extend([*diverse, *duplicates][:remaining])
    return sorted(selected, key=lambda trajectory: _trajectory_sort_key(trajectory, config=config))


def _trajectory_rank(trajectory: dict[str, Any]) -> tuple[int, int, int, int]:
    return (
        int(trajectory["victory"] is True),
        int(trajectory["act1_cleared"] is True),
        int(trajectory["boss_reached"] is True),
        int(trajectory["maximum_floor"]),
    )


def _auxiliary_rank(trajectory: dict[str, Any]) -> tuple[int, int, int, int, int]:
    frontier = _mapping(trajectory.get("public_frontier"), "trajectory public frontier")
    defeated_fraction = frontier.get("enemy_hp_defeated_fraction")
    player_fraction = frontier.get("player_hp_fraction")
    actionable_fraction = frontier.get("last_actionable_player_hp_fraction")
    return (
        int(frontier.get("encounter_cleared") is True),
        _fraction_parts_per_million(defeated_fraction),
        _fraction_parts_per_million(player_fraction),
        _fraction_parts_per_million(actionable_fraction),
        min(
            1_000_000,
            _integer(
                frontier.get("distinct_public_states_on_floor"),
                "frontier distinct public states",
            ),
        ),
    )


def _selection_rank(
    trajectory: dict[str, Any], *, config: TrajectorySearchConfig
) -> tuple[int, ...]:
    primary = _trajectory_rank(trajectory)
    if (
        config.frontier_ranking is None
        or config.frontier_ranking.strategy == HASH_TIEBREAK_STRATEGY
    ):
        return primary
    return (*primary, *_auxiliary_rank(trajectory))


def _trajectory_sort_key(
    trajectory: dict[str, Any], *, config: TrajectorySearchConfig
) -> tuple[object, ...]:
    rank = _selection_rank(trajectory, config=config)
    return (*(-value for value in rank), str(trajectory["action_trace_sha256"]))


def _frontier_strategic_trace(trajectory: dict[str, Any]) -> str:
    frontier = _mapping(trajectory.get("public_frontier"), "trajectory public frontier")
    return _string(frontier.get("strategic_trace_sha256"), "strategic trace SHA-256")


def _generation_record(
    generation: int,
    evaluated: Sequence[dict[str, Any]],
    beam: Sequence[dict[str, Any]],
    incumbent: dict[str, Any],
    *,
    config: TrajectorySearchConfig,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "generation": generation,
        "evaluated_trajectory_ids": [item["trajectory_id"] for item in evaluated],
        "incumbent_trajectory_id": incumbent["trajectory_id"],
        "incumbent_rank": list(_trajectory_rank(incumbent)),
    }
    if config.frontier_ranking is not None:
        record.update(
            {
                "incumbent_auxiliary_rank": list(_auxiliary_rank(incumbent)),
                "beam_trajectory_ids": [item["trajectory_id"] for item in beam],
                "beam_distinct_strategic_traces": len(
                    {_frontier_strategic_trace(item) for item in beam}
                ),
            }
        )
    return record


def _trajectory_outcome(
    trajectory: dict[str, Any], *, config: TrajectorySearchConfig
) -> dict[str, Any]:
    outcome: dict[str, Any] = {
        "trajectory_id": trajectory["trajectory_id"],
        "terminal": trajectory["terminal"],
        "victory": trajectory["victory"],
        "boss_reached": trajectory["boss_reached"],
        "act1_cleared": trajectory["act1_cleared"],
        "maximum_floor": trajectory["maximum_floor"],
        "action_trace_sha256": trajectory["action_trace_sha256"],
    }
    if config.frontier_ranking is not None:
        outcome.update(
            {
                "auxiliary_rank": list(_auxiliary_rank(trajectory)),
                "public_frontier_id": trajectory["public_frontier"]["frontier_id"],
            }
        )
    return outcome


def _summary(cases: Sequence[dict[str, Any]]) -> dict[str, Any]:
    completed = [case for case in cases if case["status"] == "completed"]
    all_trajectories = [trajectory for case in completed for trajectory in case["trajectories"]]
    baseline = [
        next(
            trajectory
            for trajectory in case["trajectories"]
            if trajectory["trajectory_id"] == case["baseline_trajectory_id"]
        )
        for case in completed
    ]
    best = [
        next(
            trajectory
            for trajectory in case["trajectories"]
            if trajectory["trajectory_id"] == case["best_trajectory_id"]
        )
        for case in completed
    ]
    applied = sum(
        trajectory["mutation"] is not None and trajectory["mutation"]["applied"] is True
        for trajectory in all_trajectories
    )
    requested = sum(trajectory["mutation"] is not None for trajectory in all_trajectories)
    return {
        "benchmark_denominator": len(cases),
        "completed_seed_cases": len(completed),
        "failed_seed_cases": len(cases) - len(completed),
        "evaluated_trajectories": len(all_trajectories),
        "terminal_trajectories": sum(item["terminal"] is True for item in all_trajectories),
        "victorious_trajectories": sum(item["victory"] is True for item in all_trajectories),
        "mutation_requests": requested,
        "mutations_applied": applied,
        "replay_divergences": requested - applied,
        "decisions": sum(len(item["decisions"]) for item in all_trajectories),
        "baseline": _outcome_summary(baseline),
        "best": _outcome_summary(best),
        "paired": {
            "mean_maximum_floor_difference": _artifact_float(
                sum(
                    int(best_item["maximum_floor"]) - int(base_item["maximum_floor"])
                    for best_item, base_item in zip(best, baseline, strict=True)
                )
                / max(1, len(best))
            ),
            "seeds_improved": sum(
                _trajectory_rank(best_item) > _trajectory_rank(base_item)
                for best_item, base_item in zip(best, baseline, strict=True)
            ),
            "seeds_regressed": sum(
                _trajectory_rank(best_item) < _trajectory_rank(base_item)
                for best_item, base_item in zip(best, baseline, strict=True)
            ),
        },
    }


def _outcome_summary(trajectories: Sequence[dict[str, Any]]) -> dict[str, Any]:
    count = len(trajectories)
    victories = sum(item["victory"] is True for item in trajectories)
    clears = sum(item["act1_cleared"] is True for item in trajectories)
    reaches = sum(item["boss_reached"] is True for item in trajectories)
    return {
        "trajectories": count,
        "victories": victories,
        "victory_rate": _artifact_float(victories / max(1, count)),
        "act1_clears": clears,
        "act1_clear_rate": _artifact_float(clears / max(1, count)),
        "boss_reaches": reaches,
        "boss_reach_rate": _artifact_float(reaches / max(1, count)),
        "mean_maximum_floor": _artifact_float(
            sum(int(item["maximum_floor"]) for item in trajectories) / max(1, count)
        ),
        "maximum_floor": max((int(item["maximum_floor"]) for item in trajectories), default=0),
    }


def _readiness(summary: dict[str, Any]) -> dict[str, Any]:
    best = _mapping(summary.get("best"), "best summary")
    victories = _integer(best.get("victories"), "best victories")
    clears = _integer(best.get("act1_clears"), "best Act 1 clears")
    reaches = _integer(best.get("boss_reaches"), "best boss reaches")
    terminal_trajectories = _integer(summary.get("terminal_trajectories"), "terminal trajectories")
    return {
        "boss_reach_signal_found": reaches > 0,
        "act1_clear_signal_found": clears > 0,
        "terminal_positive_trajectories_found": victories > 0,
        "terminal_value_head_unblocked": 0 < victories < terminal_trajectories,
        "recommended_next_step": (
            "replay_and_label_terminal_trajectories"
            if victories > 0
            else "replay_and_label_act1_milestones"
            if clears > 0 or reaches > 0
            else "audit_policy_or_environment_before_scaling"
        ),
    }


def _validate_public_frontier(
    value: object,
    *,
    trajectory: dict[str, Any],
    ranking: PublicFrontierRanking,
) -> None:
    frontier = _mapping(value, "trajectory public frontier")
    expected_fields = {
        "schema_version",
        "frontier_id",
        "ranking_id",
        "information_policy_id",
        "state_hash",
        "last_actionable_state_hash",
        "enemy_snapshot_state_hash",
        "floor",
        "act",
        "decision_type",
        "last_actionable_decision_type",
        "phase",
        "terminal",
        "player_hp",
        "player_max_hp",
        "player_hp_fraction",
        "last_actionable_player_hp_fraction",
        "encounter_id",
        "encounter",
        "decisions_on_floor",
        "distinct_public_states_on_floor",
        "enemy_hp_available",
        "enemy_hp_current",
        "enemy_hp_reference",
        "enemy_hp_defeated_fraction",
        "living_enemy_count",
        "encounter_cleared",
        "strategic_trace_sha256",
    }
    if set(frontier) != expected_fields:
        raise ValueError("Public-frontier fields differ")
    frontier_id = _string(frontier.get("frontier_id"), "public-frontier ID")
    body = {key: item for key, item in frontier.items() if key != "frontier_id"}
    if frontier_id != manifest_identifier(body):
        raise ValueError("Public-frontier identity mismatch")
    expected = {
        "schema_version": ranking.frontier_summary_schema_version,
        "ranking_id": ranking.ranking_id,
        "information_policy_id": "public-state-v1",
        "floor": trajectory.get("maximum_floor"),
        "state_hash": trajectory.get("final_state_hash"),
    }
    if any(frontier.get(key) != item for key, item in expected.items()):
        raise ValueError("Public-frontier provenance or maximum-floor state differs")
    if frontier.get("terminal") is not trajectory.get("terminal"):
        raise ValueError("Public-frontier terminal evidence differs")
    if (
        ranking.enemy_snapshot_rule == LAST_ACTIONABLE_ENEMY_SNAPSHOT_RULE
        and frontier.get("enemy_hp_available") is True
        and frontier.get("enemy_snapshot_state_hash") != frontier.get("last_actionable_state_hash")
    ):
        raise ValueError("Corrected public enemy HP evidence is not from the last actionable state")
    for key in ("decisions_on_floor", "distinct_public_states_on_floor"):
        if _integer(frontier.get(key), key) < 0:
            raise ValueError(f"{key} must be nonnegative")
    if _integer(frontier.get("distinct_public_states_on_floor"), "frontier states") < 1:
        raise ValueError("Public frontier must contain at least one state")
    for key in ("player_hp_fraction", "last_actionable_player_hp_fraction"):
        _fraction_parts_per_million(frontier.get(key))
    enemy_available = _boolean(frontier.get("enemy_hp_available"), "enemy HP availability")
    enemy_fields = (
        frontier.get("enemy_hp_current"),
        frontier.get("enemy_hp_reference"),
        frontier.get("living_enemy_count"),
    )
    if enemy_available:
        if any(value is None for value in enemy_fields):
            raise ValueError("Available public enemy HP evidence is incomplete")
        current = _integer(enemy_fields[0], "enemy HP current")
        reference = _integer(enemy_fields[1], "enemy HP reference")
        living = _integer(enemy_fields[2], "living enemy count")
        if min(current, reference, living) < 0 or current > reference:
            raise ValueError("Public enemy HP evidence is invalid")
        expected_fraction = _artifact_float(1.0 - current / reference) if reference > 0 else None
        if frontier.get("enemy_hp_defeated_fraction") != expected_fraction:
            raise ValueError("Public enemy HP progress differs")
        if frontier.get("encounter_cleared") is not (current == 0 and reference > 0):
            raise ValueError("Public encounter-clear evidence differs")
    elif (
        any(value is not None for value in enemy_fields)
        or frontier.get("enemy_hp_defeated_fraction") is not None
    ):
        raise ValueError("Unavailable public enemy HP evidence is populated")
    elif frontier.get("encounter_cleared") is not False:
        raise ValueError("Unavailable enemy evidence cannot mark an encounter clear")
    strategic_trace = manifest_identifier(
        {
            "schema_version": "strategic-action-trace-v1",
            "decisions": [
                {
                    "decision_index": record["decision_index"],
                    "decision_type": record["decision_type"],
                    "selected_action_id": record["selected_action_id"],
                }
                for record in trajectory["decisions"]
                if record.get("decision_type") in _STRATEGIC_DECISION_TYPES
            ],
        }
    )
    if frontier.get("strategic_trace_sha256") != strategic_trace:
        raise ValueError("Public-frontier strategic trace differs")


def _validate_case(case: dict[str, Any], *, config: TrajectorySearchConfig) -> None:
    if case.get("status") not in ("completed", "failed"):
        raise ValueError("Trajectory search case status differs")
    if case["status"] == "failed":
        if not isinstance(case.get("error"), str):
            raise ValueError("Failed trajectory search case has no error")
        return
    trajectories = case.get("trajectories")
    generations = case.get("generations")
    if not isinstance(trajectories, list) or not trajectories:
        raise ValueError("Trajectory search case has no trajectories")
    if not isinstance(generations, list) or not generations:
        raise ValueError("Trajectory search case has no generations")
    by_id: dict[str, dict[str, Any]] = {}
    for trajectory in trajectories:
        item = _mapping(trajectory, "trajectory")
        trajectory_id = _string(item.get("trajectory_id"), "trajectory ID")
        body = {key: value for key, value in item.items() if key != "trajectory_id"}
        if trajectory_id != manifest_identifier(body):
            raise ValueError("Trajectory identity mismatch")
        if trajectory_id in by_id:
            raise ValueError("Trajectory search repeats a trajectory ID")
        by_id[trajectory_id] = item
        decisions = item.get("decisions")
        if not isinstance(decisions, list) or len(decisions) > config.maximum_decisions_per_run:
            raise ValueError("Trajectory decision trace is invalid")
        if any(
            not isinstance(record, dict) or record.get("decision_index") != index
            for index, record in enumerate(decisions)
        ):
            raise ValueError("Trajectory decision indexes differ")
        if item.get("victory") is True and item.get("terminal") is not True:
            raise ValueError("Trajectory victory is not terminal")
        action_trace = (
            "sha256:"
            + hashlib.sha256(
                "\n".join(str(record["selected_action_id"]) for record in decisions).encode()
            ).hexdigest()
        )
        if item.get("action_trace_sha256") != action_trace:
            raise ValueError("Trajectory action trace identity differs")
        expected_clear = config.milestones.next_act_id in item.get("observed_acts", [])
        expected_reach = _boss_reached(
            records=decisions,
            maximum_floor=_integer(item.get("maximum_floor"), "trajectory maximum floor"),
            milestones=config.milestones,
        )
        if item.get("act1_cleared") is not expected_clear:
            raise ValueError("Trajectory Act 1 clear evidence differs")
        if item.get("boss_reached") is not expected_reach:
            raise ValueError("Trajectory boss-reach evidence differs")
        if config.frontier_ranking is not None:
            _validate_public_frontier(
                item.get("public_frontier"),
                trajectory=item,
                ranking=config.frontier_ranking,
            )
        elif "public_frontier" in item:
            raise ValueError("Legacy trajectory unexpectedly contains a public frontier")
        liveness = _mapping(item.get("liveness"), "trajectory liveness")
        if liveness.get("schema_version") != "trajectory-search-liveness-v1":
            raise ValueError("Trajectory liveness schema differs")
        if (item.get("termination_reason") == "policy_cycle") != (
            liveness.get("cycle_detected") is True
        ):
            raise ValueError("Trajectory cycle evidence differs")
        parent_id = item.get("parent_trajectory_id")
        if parent_id is not None and parent_id not in by_id:
            raise ValueError("Trajectory parent must precede its child")
        mutation = item.get("mutation")
        if parent_id is None and mutation is not None:
            raise ValueError("Baseline trajectory has mutation evidence")
        if parent_id is not None and (
            not isinstance(mutation, dict) or mutation.get("parent_trajectory_id") != parent_id
        ):
            raise ValueError("Child trajectory mutation parent differs")
        if parent_id is not None:
            parent = by_id[str(parent_id)]
            if _integer(item.get("generation"), "child generation") <= _integer(
                parent.get("generation"), "parent generation"
            ):
                raise ValueError("Trajectory parent generation is not earlier")
            assert isinstance(mutation, dict)
            if mutation.get("applied") is True:
                index = _integer(
                    mutation.get("requested_decision_index"), "mutation decision index"
                )
                if index >= len(decisions):
                    raise ValueError("Applied mutation is outside the child trace")
                record = decisions[index]
                if record.get("selection_source") != "mutation" or record.get(
                    "selected_action_id"
                ) != mutation.get("requested_action_id"):
                    raise ValueError("Applied mutation evidence differs from the child trace")
    baseline_id = case.get("baseline_trajectory_id")
    best_id = case.get("best_trajectory_id")
    if baseline_id not in by_id or best_id not in by_id:
        raise ValueError("Trajectory search baseline or best trajectory is missing")
    baseline = by_id[str(baseline_id)]
    if baseline.get("generation") != 0 or baseline.get("parent_trajectory_id") is not None:
        raise ValueError("Trajectory search baseline is not generation zero")
    if any(record.get("selection_source") != "base_policy" for record in baseline["decisions"]):
        raise ValueError("Trajectory search baseline does not exactly use the base policy")
    incumbent_rank: tuple[int, ...] | None = None
    previous_beam: list[dict[str, Any]] = []
    for expected_generation, raw_generation in enumerate(generations):
        generation = _mapping(raw_generation, "generation record")
        if generation.get("generation") != expected_generation:
            raise ValueError("Trajectory search generation sequence differs")
        incumbent_id = generation.get("incumbent_trajectory_id")
        if incumbent_id not in by_id:
            raise ValueError("Trajectory search incumbent is missing")
        evaluated_ids = generation.get("evaluated_trajectory_ids")
        if not isinstance(evaluated_ids, list) or not evaluated_ids:
            raise ValueError("Trajectory search generation has no evaluated trajectories")
        if any(
            trajectory_id not in by_id
            or by_id[str(trajectory_id)].get("generation") != expected_generation
            for trajectory_id in evaluated_ids
        ):
            raise ValueError("Trajectory search generation membership differs")
        incumbent = by_id[str(incumbent_id)]
        primary_rank = _trajectory_rank(incumbent)
        rank = _selection_rank(incumbent, config=config)
        if generation.get("incumbent_rank") != list(primary_rank):
            raise ValueError("Trajectory search incumbent rank differs")
        evaluated = [by_id[str(trajectory_id)] for trajectory_id in evaluated_ids]
        if config.frontier_ranking is not None:
            if generation.get("incumbent_auxiliary_rank") != list(_auxiliary_rank(incumbent)):
                raise ValueError("Trajectory search incumbent auxiliary rank differs")
            expected_beam = _select_beam(
                [*previous_beam, *evaluated] if expected_generation else evaluated,
                config=config,
            )
            expected_beam_ids = [item["trajectory_id"] for item in expected_beam]
            if generation.get("beam_trajectory_ids") != expected_beam_ids:
                raise ValueError("Trajectory search beam selection differs")
            expected_diversity = len({_frontier_strategic_trace(item) for item in expected_beam})
            if generation.get("beam_distinct_strategic_traces") != expected_diversity:
                raise ValueError("Trajectory search beam diversity evidence differs")
            previous_beam = expected_beam
        if incumbent_rank is not None and rank < incumbent_rank:
            raise ValueError("Trajectory search incumbent regressed")
        incumbent_rank = rank
    expected_best = min(by_id.values(), key=lambda item: _trajectory_sort_key(item, config=config))
    actual_best = by_id[str(best_id)]
    if actual_best["trajectory_id"] != expected_best["trajectory_id"]:
        raise ValueError("Trajectory search best outcome is not maximal")
    if generations[-1]["incumbent_trajectory_id"] != best_id:
        raise ValueError("Trajectory search final incumbent differs from the best trajectory")
    if case.get("best_trajectory") != _trajectory_outcome(actual_best, config=config):
        raise ValueError("Trajectory search best outcome differs")


def _load_case(
    path: Path,
    *,
    seed: int,
    config: TrajectorySearchConfig,
    policy: ProductionCheckpointPolicy,
) -> dict[str, Any]:
    case = _load_case_document(path, seed=seed, config=config)
    if case.get("policy_id") != policy.policy_id:
        raise ValueError("Trajectory search resumed policy differs")
    return case


def _load_case_document(
    path: Path,
    *,
    seed: int,
    config: TrajectorySearchConfig,
) -> dict[str, Any]:
    case = _load_object(path, "trajectory search case")
    case_id = case.get("case_id")
    body = {key: value for key, value in case.items() if key != "case_id"}
    if case_id != manifest_identifier(body):
        raise ValueError("Trajectory search case identity mismatch")
    expected = {
        "schema_version": config.case_schema_version,
        "config_id": config.config_id,
        "seed": seed,
        "partition": SplitName.TRAIN.value,
        "model_id": config.model_id,
        "policy_id": f"production-checkpoint-policy-v1:{config.model_id}",
        "ruleset_manifest_id": config.ruleset_manifest_id,
        "milestone_id": config.milestones.milestone_id,
        "search_controller_id": config.search_controller_id,
        "hidden_state_resampling": False,
    }
    if any(case.get(key) != value for key, value in expected.items()):
        raise ValueError("Trajectory search resumed case configuration differs")
    _validate_case(case, config=config)
    return case


def _case_reference(output_directory: Path, case: dict[str, Any]) -> dict[str, Any]:
    path = _case_path(output_directory, int(case["seed"]))
    return {
        "seed": case["seed"],
        "path": str(path.relative_to(output_directory)),
        "case_id": case["case_id"],
    }


def _case_path(output_directory: Path, seed: int) -> Path:
    return output_directory / "cases" / f"seed-{seed:06d}.json"


def _milestone_preflight(
    *,
    environment_factory: Callable[[], EnvironmentAdapter],
    ruleset: RulesetIdentity,
    seed: int,
    milestones: Act1Milestones,
) -> dict[str, Any]:
    environment: EnvironmentAdapter | None = None
    try:
        environment = environment_factory()
        if environment.ruleset != ruleset:
            raise ValueError("Trajectory search preflight environment ruleset changed")
        observation = environment.reset(seed)
        act = observation.public_state.get("act")
        floor = observation.public_state.get("floor")
        if act not in milestones.first_act_ids:
            raise ValueError(
                "Trajectory search milestone preflight expected one of "
                f"{milestones.first_act_ids!r}, got {act!r}"
            )
        if _public_integer(floor) is None:
            raise ValueError("Trajectory search milestone preflight has no public integer floor")
        return {
            "milestone_id": milestones.milestone_id,
            "seed": seed,
            "initial_act": act,
            "initial_floor": floor,
            "public_state_fields": ["act", "floor", "terminal", "victory"],
            "valid": True,
        }
    finally:
        if environment is not None:
            close = getattr(environment, "close", None)
            if callable(close):
                close()


def _validate_milestone_preflight(value: object, *, config: TrajectorySearchConfig) -> None:
    preflight = _mapping(value, "milestone preflight")
    expected = {
        "milestone_id": config.milestones.milestone_id,
        "public_state_fields": ["act", "floor", "terminal", "victory"],
        "valid": True,
    }
    if any(preflight.get(key) != item for key, item in expected.items()):
        raise ValueError("Trajectory search milestone preflight differs")
    _integer(preflight.get("seed"), "milestone preflight seed")
    _integer(preflight.get("initial_floor"), "milestone preflight floor")
    initial_act = _string(preflight.get("initial_act"), "milestone preflight act")
    if initial_act not in config.milestones.first_act_ids:
        raise ValueError("Trajectory search milestone preflight act is not an Act 1 region")


def _boss_reached(
    *,
    records: Sequence[dict[str, Any]],
    maximum_floor: int,
    milestones: Act1Milestones,
) -> bool:
    return maximum_floor >= milestones.boss_floor and any(
        record.get("source_act") in milestones.first_act_ids
        and (_public_integer(record.get("source_floor")) or 0) >= milestones.boss_floor
        for record in records
    )


def _record_act(observed: list[str], observation: Observation) -> None:
    act = observation.public_state.get("act")
    if isinstance(act, str) and act and act not in observed:
        observed.append(act)


def _divergence(
    decision_index: int,
    reason: str,
    expected_state_hash: str | None,
    actual_state_hash: str,
) -> dict[str, Any]:
    return {
        "decision_index": decision_index,
        "reason": reason,
        "expected_state_hash": expected_state_hash,
        "actual_state_hash": actual_state_hash,
        "fallback": "base_policy",
    }


def _digest_integer(*parts: object) -> int:
    return int.from_bytes(hashlib.sha256("\n".join(map(str, parts)).encode()).digest(), "big")


def _validate_inputs(
    *,
    ruleset: RulesetIdentity,
    policy: ProductionCheckpointPolicy,
    split_manifest: SplitManifest,
    training_report_id: str,
    config: TrajectorySearchConfig,
) -> None:
    expected = {
        "split_manifest_id": split_manifest.manifest_id,
        "ruleset_manifest_id": ruleset.manifest_id,
        "model_id": policy.model_id,
        "training_report_id": training_report_id,
        "objective_id": split_manifest.objective_id,
        "partition": SplitName.TRAIN.value,
    }
    if any(getattr(config, key) != value for key, value in expected.items()):
        raise ValueError("Trajectory search config provenance differs")
    if split_manifest.ruleset_manifest_id != ruleset.manifest_id:
        raise ValueError("Trajectory search split and environment rulesets differ")
    if split_manifest.objective_id != "terminal-victory-v1":
        raise ValueError("Trajectory search split does not use terminal victory")
    if policy.ruleset != ruleset or policy.split_manifest_id != split_manifest.manifest_id:
        raise ValueError("Trajectory search policy provenance differs")


def _artifact_float(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("Artifact float must be finite")
    return float(f"{value:.12g}")


def _fraction_parts_per_million(value: object) -> int:
    if value is None:
        return 0
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("Public-frontier fraction must be numeric or null")
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ValueError("Public-frontier fraction must be between zero and one")
    return round(numeric * 1_000_000)


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value: object = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load {label} {path}: {error}") from error
    return _mapping(value, label)


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return dict(value)


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _string_tuple(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty array")
    return tuple(_string(item, label) for item in value)


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    return value


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be boolean")
    return value


def _public_integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
