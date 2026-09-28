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
from spireshift.core.types import Observation
from spireshift.liveness import PublicNoOpActionGuard
from spireshift.models import write_model_artifact
from spireshift.splits import SplitManifest, SplitName

TRAJECTORY_SEARCH_CONFIG_SCHEMA_VERSION = "run-level-trajectory-search-config-v2"
TRAJECTORY_SEARCH_CASE_SCHEMA_VERSION = "run-level-trajectory-search-case-v1"
TRAJECTORY_SEARCH_REPORT_SCHEMA_VERSION = "run-level-trajectory-search-v1"
TRAJECTORY_SEARCH_VERIFICATION_SCHEMA_VERSION = "run-level-trajectory-search-verification-v1"
MILESTONE_SCHEMA_VERSION = "act1-milestone-semantics-v2"
SEARCH_CONTROLLER_ID = "policy-guided-trajectory-beam-v1"
CLAIM_SCOPE = "train_only_act1_milestone_trajectory_search"


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
        return {
            "schema_version": TRAJECTORY_SEARCH_CONFIG_SCHEMA_VERSION,
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
            "search_controller_id": SEARCH_CONTROLLER_ID,
            "mutation_salt": self.mutation_salt,
            "exact_replay_only": self.exact_replay_only,
            "milestones": self.milestones.as_dict(),
        }

    @property
    def config_id(self) -> str:
        return manifest_identifier(self.body())

    def as_dict(self) -> dict[str, object]:
        return {**self.body(), "config_id": self.config_id}

    @classmethod
    def from_mapping(cls, value: object) -> TrajectorySearchConfig:
        document = _mapping(value, "trajectory search config")
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
        if set(document) != expected:
            raise ValueError("Trajectory search config fields differ")
        if document.get("schema_version") != TRAJECTORY_SEARCH_CONFIG_SCHEMA_VERSION:
            raise ValueError("Trajectory search config schema differs")
        if document.get("search_controller_id") != SEARCH_CONTROLLER_ID:
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
        )
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
        "schema_version": TRAJECTORY_SEARCH_REPORT_SCHEMA_VERSION,
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
        "search_controller_id": SEARCH_CONTROLLER_ID,
        "hidden_state_resampling": False,
        "configuration": config.as_dict(),
        "milestone_preflight": milestone_preflight,
        "cases": references,
        "milestone_cases": milestone_references,
        "summary": summary,
        "readiness": _readiness(summary),
        "claim_scope": CLAIM_SCOPE,
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
            "schema_version": TRAJECTORY_SEARCH_REPORT_SCHEMA_VERSION,
            "config_id": config.config_id,
            "model_id": config.model_id,
            "training_report_id": config.training_report_id,
            "split_manifest_id": split_manifest.manifest_id,
            "partition": SplitName.TRAIN.value,
            "ruleset_manifest_id": split_manifest.ruleset_manifest_id,
            "objective_id": split_manifest.objective_id,
            "search_controller_id": SEARCH_CONTROLLER_ID,
            "hidden_state_resampling": False,
            "configuration": config.as_dict(),
            "claim_scope": CLAIM_SCOPE,
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
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(str(error))
    body = {
        "schema_version": TRAJECTORY_SEARCH_VERIFICATION_SCHEMA_VERSION,
        "valid": not errors,
        "report_id": report_id,
        "config_id": config.config_id,
        "verified_cases": verified_cases,
        "errors": errors,
    }
    return {**body, "verification_id": manifest_identifier(body)}


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
        generations = [_generation_record(0, [baseline], baseline)]
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
            beam = _select_beam([*beam, *children], width=config.beam_width)
            next_incumbent = beam[0]
            if _trajectory_rank(next_incumbent) < _trajectory_rank(incumbent):
                raise RuntimeError("Trajectory search incumbent regressed")
            incumbent = next_incumbent
            generations.append(_generation_record(generation, children, incumbent))
        body: dict[str, Any] = {
            "schema_version": TRAJECTORY_SEARCH_CASE_SCHEMA_VERSION,
            "config_id": config.config_id,
            "seed": seed,
            "partition": SplitName.TRAIN.value,
            "model_id": policy.model_id,
            "policy_id": policy.policy_id,
            "ruleset_manifest_id": ruleset.manifest_id,
            "milestone_id": config.milestones.milestone_id,
            "search_controller_id": SEARCH_CONTROLLER_ID,
            "hidden_state_resampling": False,
            "status": "completed",
            "error": None,
            "baseline_trajectory_id": baseline["trajectory_id"],
            "best_trajectory_id": incumbent["trajectory_id"],
            "best_trajectory": _trajectory_outcome(incumbent),
            "generations": generations,
            "trajectories": trajectories,
        }
    except Exception as error:
        body = {
            "schema_version": TRAJECTORY_SEARCH_CASE_SCHEMA_VERSION,
            "config_id": config.config_id,
            "seed": seed,
            "partition": SplitName.TRAIN.value,
            "model_id": policy.model_id,
            "policy_id": policy.policy_id,
            "ruleset_manifest_id": ruleset.manifest_id,
            "milestone_id": config.milestones.milestone_id,
            "search_controller_id": SEARCH_CONTROLLER_ID,
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
        return {**body, "trajectory_id": manifest_identifier(body)}
    finally:
        if environment is not None:
            close = getattr(environment, "close", None)
            if callable(close):
                close()


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


def _select_beam(trajectories: Sequence[dict[str, Any]], *, width: int) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for trajectory in trajectories:
        trace = str(trajectory["action_trace_sha256"])
        current = unique.get(trace)
        if current is None or _trajectory_rank(trajectory) > _trajectory_rank(current):
            unique[trace] = trajectory
    return sorted(unique.values(), key=_trajectory_sort_key)[:width]


def _trajectory_rank(trajectory: dict[str, Any]) -> tuple[int, int, int, int]:
    return (
        int(trajectory["victory"] is True),
        int(trajectory["act1_cleared"] is True),
        int(trajectory["boss_reached"] is True),
        int(trajectory["maximum_floor"]),
    )


def _trajectory_sort_key(trajectory: dict[str, Any]) -> tuple[int, int, int, int, str]:
    rank = _trajectory_rank(trajectory)
    return (-rank[0], -rank[1], -rank[2], -rank[3], str(trajectory["action_trace_sha256"]))


def _generation_record(
    generation: int,
    evaluated: Sequence[dict[str, Any]],
    incumbent: dict[str, Any],
) -> dict[str, Any]:
    return {
        "generation": generation,
        "evaluated_trajectory_ids": [item["trajectory_id"] for item in evaluated],
        "incumbent_trajectory_id": incumbent["trajectory_id"],
        "incumbent_rank": list(_trajectory_rank(incumbent)),
    }


def _trajectory_outcome(trajectory: dict[str, Any]) -> dict[str, Any]:
    return {
        "trajectory_id": trajectory["trajectory_id"],
        "terminal": trajectory["terminal"],
        "victory": trajectory["victory"],
        "boss_reached": trajectory["boss_reached"],
        "act1_cleared": trajectory["act1_cleared"],
        "maximum_floor": trajectory["maximum_floor"],
        "action_trace_sha256": trajectory["action_trace_sha256"],
    }


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
    incumbent_rank: tuple[int, int, int, int] | None = None
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
        rank = _trajectory_rank(incumbent)
        if generation.get("incumbent_rank") != list(rank):
            raise ValueError("Trajectory search incumbent rank differs")
        if incumbent_rank is not None and rank < incumbent_rank:
            raise ValueError("Trajectory search incumbent regressed")
        incumbent_rank = rank
    expected_best = max(
        by_id.values(), key=lambda item: (_trajectory_rank(item), _trace_tiebreak(item))
    )
    actual_best = by_id[str(best_id)]
    if actual_best["trajectory_id"] != expected_best["trajectory_id"]:
        raise ValueError("Trajectory search best outcome is not maximal")
    if generations[-1]["incumbent_trajectory_id"] != best_id:
        raise ValueError("Trajectory search final incumbent differs from the best trajectory")
    if case.get("best_trajectory") != _trajectory_outcome(actual_best):
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
        "schema_version": TRAJECTORY_SEARCH_CASE_SCHEMA_VERSION,
        "config_id": config.config_id,
        "seed": seed,
        "partition": SplitName.TRAIN.value,
        "model_id": config.model_id,
        "policy_id": f"production-checkpoint-policy-v1:{config.model_id}",
        "ruleset_manifest_id": config.ruleset_manifest_id,
        "milestone_id": config.milestones.milestone_id,
        "search_controller_id": SEARCH_CONTROLLER_ID,
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


def _trace_tiebreak(trajectory: dict[str, Any]) -> int:
    return -int(str(trajectory["action_trace_sha256"]).split(":", 1)[-1], 16)


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
