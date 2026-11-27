from __future__ import annotations

import copy
import json
import os
import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

from spireshift.agents.learned import ProductionCheckpointPolicy
from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.core.protocols import EnvironmentAdapter
from spireshift.core.types import DecisionType, LegalAction, Observation
from spireshift.models import _exact_keys, _integer, _list, _mapping
from spireshift.representations import build_model_input, model_input_from_mapping
from spireshift.rollouts import sha256_file, write_exclusive_json
from spireshift.splits import SplitManifest, SplitName
from spireshift.starting_options import ENCODER_ID, StartingOptionHead, starting_option_ids
from spireshift.trajectory_policy import _folds
from spireshift.trajectory_search import (
    CORRECTED_FRONTIER_CONFIG_SCHEMA_VERSION,
    PUBLIC_FRONTIER_STRATEGY,
    TRAJECTORY_SELECTION_RANK_ORDER,
    TrajectorySearchConfig,
    _generation_record,
    _MutationPlan,
    _run_trajectory,
    _select_beam,
    _trajectory_outcome,
    _utc_now,
    _validate_case,
    _validate_inputs,
    trajectory_selection_rank,
)

CONFIG_SCHEMA = "starting-option-evidence-config-v1"
CASE_SCHEMA = "starting-option-evidence-case-v1"
REPORT_SCHEMA = "starting-option-evidence-report-v1"
FILENAME = "starting-option-evidence.json"
CLAIM = "train_only_exact_seed_fixed_policy_starting_option_evidence"
STRONG_COMPONENTS = {"victory", "act1_cleared", "boss_reached", "maximum_floor"}


@dataclass(frozen=True, slots=True)
class StartingEvidenceConfig:
    document: dict[str, Any]

    @classmethod
    def from_mapping(cls, value: object) -> StartingEvidenceConfig:
        doc = copy.deepcopy(_mapping(value, "starting evidence config"))
        _exact_keys(
            doc,
            {
                "schema_version",
                "config_id",
                "encoder_id",
                "trajectory_config",
                "selection_fraction",
                "selection_salt",
                "complete_run_subfolds",
                "minimum_runs",
            },
            "starting evidence config",
        )
        _identity(doc, "config_id")
        if doc["schema_version"] != CONFIG_SCHEMA or doc["encoder_id"] != ENCODER_ID:
            raise ValueError("Unsupported starting evidence config")
        runner = TrajectorySearchConfig.from_mapping(doc["trajectory_config"])
        if (
            runner.schema_version != CORRECTED_FRONTIER_CONFIG_SCHEMA_VERSION
            or runner.frontier_ranking is None
            or runner.frontier_ranking.strategy != PUBLIC_FRONTIER_STRATEGY
            or (runner.generations, runner.beam_width, runner.mutations_per_parent) != (1, 3, 2)
        ):
            raise ValueError("Starting evidence requires the corrected three-branch runner")
        if (
            doc["selection_fraction"] != 0.25
            or not isinstance(doc["selection_salt"], str)
            or not doc["selection_salt"]
        ):
            raise ValueError("Starting evidence subfold recipe differs")
        folds = _mapping(doc["complete_run_subfolds"], "starting evidence subfolds")
        _exact_keys(folds, {"fit", "selection"}, "starting evidence subfolds")
        seeds = []
        for name in ("fit", "selection"):
            group = [_integer(s, "starting run seed") for s in _list(folds[name], name)]
            if not group or group != sorted(set(group)) or min(group) < 0:
                raise ValueError("Starting evidence subfold seeds must be sorted and unique")
            seeds.extend(group)
        if len(seeds) != runner.run_count or len(set(seeds)) != len(seeds):
            raise ValueError("Starting evidence has overlapping or missing complete runs")
        if folds != _folds(set(seeds), doc):
            raise ValueError("Starting evidence ownership differs from its frozen recipe")
        minimum = _mapping(doc["minimum_runs"], "starting evidence minimum runs")
        _exact_keys(minimum, {"fit", "selection", "strong_selection"}, "minimum runs")
        for name, count in minimum.items():
            limit = len(folds["fit" if name == "fit" else "selection"])
            if not 1 <= _integer(count, "minimum informative runs") <= limit:
                raise ValueError("Starting evidence minimum coverage is invalid")
        return cls(doc)

    @property
    def runner(self) -> TrajectorySearchConfig:
        return TrajectorySearchConfig.from_mapping(self.document["trajectory_config"])

    @property
    def config_id(self) -> str:
        return str(self.document["config_id"])

    @property
    def seeds(self) -> tuple[int, ...]:
        folds = self.document["complete_run_subfolds"]
        return tuple(sorted(folds["fit"] + folds["selection"]))


def load_starting_evidence_config(path: Path) -> StartingEvidenceConfig:
    return StartingEvidenceConfig.from_mapping(json.loads(path.read_text(encoding="utf-8")))


def _identity(doc: dict[str, Any], field: str) -> None:
    if doc.get(field) != manifest_identifier({k: v for k, v in doc.items() if k != field}):
        raise ValueError(f"Starting evidence {field} identity differs")


def _identified(body: dict[str, Any], field: str) -> dict[str, Any]:
    return {**body, field: manifest_identifier(body)}


def _path(directory: Path, seed: int) -> Path:
    return directory / "cases" / f"seed-{seed:06d}.json"


def _reference(directory: Path, case: dict[str, Any]) -> dict[str, Any]:
    path = _path(directory, int(case["run_seed"]))
    return {
        "run_seed": case["run_seed"],
        "path": str(path.relative_to(directory)),
        "sha256": sha256_file(path),
        "case_id": case["case_id"],
    }


def _publish_json(path: Path, value: object) -> None:
    """Publish a flushed complete file atomically, without replacing an existing result."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".starting-evidence-", dir=path.parent) as staging:
        temporary = Path(staging) / "complete.json"
        write_exclusive_json(temporary, value)
        os.link(temporary, path)


def _comparisons(
    branches: list[dict[str, Any]], runner: TrajectorySearchConfig
) -> list[dict[str, Any]]:
    rows = []
    for left, right in combinations(branches, 2):
        a = trajectory_selection_rank(left["trajectory"], config=runner)
        b = trajectory_selection_rank(right["trajectory"], config=runner)
        component = next(
            (
                name
                for name, x, y in zip(TRAJECTORY_SELECTION_RANK_ORDER, a, b, strict=True)
                if x != y
            ),
            None,
        )
        preferred, disfavored = (left, right) if a > b else (right, left)
        body = {
            "left_action_id": left["action_id"],
            "right_action_id": right["action_id"],
            "left_rank": list(a),
            "right_rank": list(b),
            "deciding_rank_component": component,
            "label": "tied" if a == b else "strict",
            "preferred_action_id": None if a == b else preferred["action_id"],
            "disfavored_action_id": None if a == b else disfavored["action_id"],
            "eligible_policy_preference": component is not None
            and component != "distinct_public_states_on_floor",
            "terminal_victory_difference": component == "victory",
        }
        rows.append(_identified(body, "comparison_id"))
    return rows


def _collect_case(
    *,
    factory: Callable[[], EnvironmentAdapter],
    ruleset: RulesetIdentity,
    policy: ProductionCheckpointPolicy,
    config: StartingEvidenceConfig,
    seed: int,
) -> dict[str, Any]:
    runner = config.runner
    body: dict[str, Any] = {
        "schema_version": CASE_SCHEMA,
        "config_id": config.config_id,
        "run_seed": seed,
        "source_observation": None,
        "source_legal_actions": None,
        "source_model_input": None,
        "option_ids": None,
        "baseline_action_id": None,
        "branches": [],
        "comparisons": [],
        "status": "failed",
        "error": None,
    }
    environment = None
    try:
        environment = factory()
        if environment.ruleset != ruleset:
            raise ValueError("Starting evidence environment ruleset changed")
        observation = environment.reset(seed)
        actions = tuple(environment.legal_actions())
        representation = build_model_input(ruleset, observation, actions)
        option_ids = starting_option_ids(representation)
        if option_ids is None or len(option_ids) != 3:
            raise ValueError("Expected all three legal starting Ancient options")
        # Require the same resource context the subsequent residual learner will consume.
        StartingOptionHead(128, tuple(sorted(set(option_ids)))).features(representation)
        if observation.public_state.get("act") not in runner.milestones.first_act_ids:
            raise ValueError("Starting evidence first-act semantics differ")
        predicted = policy.predict(observation, actions)
        baseline_action = predicted.selected_action.action_id
        if predicted.source_action_ids != tuple(
            a.action_id for a in actions
        ) or baseline_action not in (a.action_id for a in actions):
            raise ValueError("Starting evidence base-policy candidate alignment differs")
        body.update(
            source_observation=observation.as_dict(),
            source_legal_actions=[a.as_dict() for a in actions],
            source_model_input=representation.as_dict(),
            option_ids=list(option_ids),
            baseline_action_id=baseline_action,
        )
    except Exception as error:
        body["error"] = f"{type(error).__name__}: {error}"
    finally:
        if environment is not None:
            close = getattr(environment, "close", None)
            if callable(close):
                try:
                    close()
                except Exception as error:
                    body["error"] = (
                        f"Starting preflight cleanup failed: {type(error).__name__}: {error}"
                    )
    if body["error"] is not None:
        for key in (
            "source_observation",
            "source_legal_actions",
            "source_model_input",
            "option_ids",
            "baseline_action_id",
        ):
            body[key] = None
        return _identified(body, "case_id")

    def same_source(index: int, observed: Observation, legal: tuple[LegalAction, ...]) -> None:
        if index == 0 and (observed != observation or legal != actions):
            raise ValueError("Starting branch reset changed public observation or legal actions")

    def branch(action: LegalAction, index: int, parent: dict[str, Any] | None) -> dict[str, Any]:
        try:
            if parent is None and action.action_id != baseline_action:
                return {
                    "action_id": action.action_id,
                    "status": "blocked",
                    "error": "Baseline branch failed",
                    "trajectory": None,
                }
            plan = None if parent is None else _MutationPlan(parent, 0, action.action_id, index)
            trajectory = _run_trajectory(
                environment_factory=factory,
                ruleset=ruleset,
                policy=policy,
                config=runner,
                seed=seed,
                generation=0 if parent is None else 1,
                parent=parent,
                mutation=plan,
                source_observer=same_source,
            )
            complete = trajectory["terminal"] is True and trajectory["truncated"] is False
            return {
                "action_id": action.action_id,
                "status": "completed" if complete else "failed",
                "error": None if complete else trajectory["termination_reason"],
                "trajectory": trajectory,
            }
        except Exception as error:
            return {
                "action_id": action.action_id,
                "status": "failed",
                "error": f"{type(error).__name__}: {error}",
                "trajectory": None,
            }

    baseline_index = next(i for i, a in enumerate(actions) if a.action_id == baseline_action)
    baseline = branch(actions[baseline_index], baseline_index, None)
    branches = [
        baseline
        if action.action_id == baseline_action
        else branch(action, i, baseline["trajectory"])
        for i, action in enumerate(actions)
    ]
    body["branches"] = branches
    if all(b["status"] == "completed" for b in branches):
        body.update(status="completed", comparisons=_comparisons(branches, runner))
    else:
        body["error"] = "One or more starting branches failed or did not terminate"
    case = _identified(body, "case_id")
    _validate_evidence_case(case, config=config, ruleset=ruleset, seed=seed)
    return case


def _validate_evidence_case(
    case: dict[str, Any],
    *,
    config: StartingEvidenceConfig,
    ruleset: RulesetIdentity,
    seed: int,
) -> None:
    _exact_keys(
        case,
        {
            "schema_version",
            "case_id",
            "config_id",
            "run_seed",
            "source_observation",
            "source_legal_actions",
            "source_model_input",
            "option_ids",
            "baseline_action_id",
            "branches",
            "comparisons",
            "status",
            "error",
        },
        "starting evidence case",
    )
    _identity(case, "case_id")
    if (case["schema_version"], case["config_id"], case["run_seed"]) != (
        CASE_SCHEMA,
        config.config_id,
        seed,
    ):
        raise ValueError("Starting evidence case provenance differs")
    branches = _list(case["branches"], "starting branches")
    if case["source_model_input"] is None:
        if (
            case["status"] != "failed"
            or not isinstance(case["error"], str)
            or branches
            or case["comparisons"]
            or any(
                case[k] is not None
                for k in (
                    "source_observation",
                    "source_legal_actions",
                    "option_ids",
                    "baseline_action_id",
                )
            )
        ):
            raise ValueError("Unsupported starting case has inconsistent failure evidence")
        return
    raw = _mapping(case["source_observation"], "starting observation")
    _exact_keys(
        raw,
        {"schema_version", "patch_id", "decision_type", "public_state", "state_hash"},
        "starting observation",
    )
    observation = Observation(
        raw["schema_version"],
        raw["patch_id"],
        DecisionType(raw["decision_type"]),
        raw["public_state"],
        raw["state_hash"],
    )
    actions = []
    for a in _list(case["source_legal_actions"], "starting legal actions"):
        _exact_keys(a, {"action_id", "kind", "payload"}, "starting legal action")
        actions.append(LegalAction(a["action_id"], a["kind"], a["payload"]))
    representation = model_input_from_mapping(case["source_model_input"])
    if representation != build_model_input(ruleset, observation, tuple(actions)):
        raise ValueError("Starting evidence public representation differs")
    ids = starting_option_ids(representation)
    if ids is None or len(ids) != 3 or list(ids) != case["option_ids"]:
        raise ValueError("Starting evidence public option binding differs")
    StartingOptionHead(128, tuple(sorted(set(ids)))).features(representation)
    runner = config.runner
    if observation.public_state.get("act") not in runner.milestones.first_act_ids:
        raise ValueError("Starting evidence first-act semantics differ")
    if [b.get("action_id") for b in branches] != [a.action_id for a in actions]:
        raise ValueError("Starting evidence omits or reorders legal options")
    baseline = next((b for b in branches if b["action_id"] == case["baseline_action_id"]), None)
    if baseline is None:
        raise ValueError("Starting evidence baseline action is absent")
    for i, b in enumerate(branches):
        _exact_keys(b, {"action_id", "status", "error", "trajectory"}, "starting branch")
        trajectory = b["trajectory"]
        if trajectory is None:
            if b["status"] not in {"failed", "blocked"} or not isinstance(b["error"], str):
                raise ValueError("Starting branch failure evidence differs")
            if b["status"] == "blocked" and (b is baseline or baseline["trajectory"] is not None):
                raise ValueError("Starting branch was incorrectly blocked")
            continue
        _identity(trajectory, "trajectory_id")
        records = trajectory["decisions"]
        if not records or len(records) > runner.maximum_decisions_per_run:
            raise ValueError("Starting branch decision trace is invalid")
        for index, record in enumerate(records):
            if (
                record["decision_index"] != index
                or record["selected_action_id"] not in record["candidate_action_ids"]
                or (index and record["source_state_hash"] != records[index - 1]["next_state_hash"])
                or (
                    index
                    and (
                        record["selection_source"] != "base_policy"
                        or record["selected_action_id"] != record["argmax_action_id"]
                    )
                )
            ):
                raise ValueError("Starting branch changed a later decision or trace alignment")
        first = records[0]
        if (
            first["source_state_hash"] != observation.state_hash
            or first["candidate_action_ids"] != [a.action_id for a in actions]
            or first["selected_action_id"] != b["action_id"]
            or first["argmax_action_id"] != case["baseline_action_id"]
        ):
            raise ValueError("Starting branch source or action differs")
        if b is baseline:
            if trajectory["mutation"] is not None or trajectory["generation"] != 0:
                raise ValueError("Starting baseline contains a mutation")
            if first["selection_source"] != "base_policy":
                raise ValueError("Starting baseline changed its policy choice")
        else:
            if (
                trajectory["generation"] != 1
                or first["selection_source"] != "mutation"
                or trajectory["mutation"]
                != {
                    "parent_trajectory_id": baseline["trajectory"]["trajectory_id"],
                    "requested_decision_index": 0,
                    "requested_action_id": b["action_id"],
                    "offspring_index": i,
                    "applied": True,
                    "replay_aligned_through_mutation": True,
                    "divergence": None,
                }
                or first["policy"] != baseline["trajectory"]["decisions"][0]["policy"]
            ):
                raise ValueError("Starting branch exact intervention differs")
        complete = trajectory["terminal"] is True and trajectory["truncated"] is False
        if b["status"] != ("completed" if complete else "failed") or (
            (b["error"] is not None) if complete else not isinstance(b["error"], str)
        ):
            raise ValueError("Starting branch terminal status differs")
    complete = all(b["status"] == "completed" for b in branches)
    if case["status"] != ("completed" if complete else "failed") or (
        (case["error"] is not None) if complete else not isinstance(case["error"], str)
    ):
        raise ValueError("Starting evidence case status differs")
    if case["comparisons"] != (_comparisons(branches, runner) if complete else []):
        raise ValueError("Starting evidence comparisons differ from outcomes")
    if complete:
        root = baseline["trajectory"]
        children = [b["trajectory"] for b in branches if b is not baseline]
        beam = _select_beam([root, *children], config=runner)
        _validate_case(
            {
                "status": "completed",
                "trajectories": [root, *children],
                "baseline_trajectory_id": root["trajectory_id"],
                "best_trajectory_id": beam[0]["trajectory_id"],
                "best_trajectory": _trajectory_outcome(beam[0], config=runner),
                "generations": [
                    _generation_record(0, [root], [root], root, config=runner),
                    _generation_record(1, children, beam, beam[0], config=runner),
                ],
            },
            config=runner,
        )


def _summary(cases: list[dict[str, Any]], config: StartingEvidenceConfig) -> dict[str, Any]:
    folds = {}
    for name, seeds in config.document["complete_run_subfolds"].items():
        selected = [c for c in cases if c["run_seed"] in seeds]
        rows = [r for c in selected for r in c["comparisons"]]
        folds[name] = {
            "configured_runs": len(seeds),
            "completed_runs": sum(c["status"] == "completed" for c in selected),
            "informative_runs": sum(
                any(r["eligible_policy_preference"] for r in c["comparisons"]) for c in selected
            ),
            "strong_runs": sum(
                any(r["deciding_rank_component"] in STRONG_COMPONENTS for r in c["comparisons"])
                for c in selected
            ),
            "eligible_pairs": sum(r["eligible_policy_preference"] for r in rows),
            "tied_pairs": sum(r["label"] == "tied" for r in rows),
            "activity_only_pairs": sum(
                r["deciding_rank_component"] == "distinct_public_states_on_floor" for r in rows
            ),
            "unique_option_ids": sorted({i for c in selected for i in (c["option_ids"] or [])}),
        }
    branches = [b for c in cases for b in c["branches"]]
    trajectories = [b["trajectory"] for b in branches if b["trajectory"] is not None]
    completed = sum(c["status"] == "completed" for c in cases)
    minimum = config.document["minimum_runs"]
    checks = {
        "all_runs_complete_and_terminal": completed == len(config.seeds),
        "fit_coverage": folds["fit"]["informative_runs"] >= minimum["fit"],
        "selection_coverage": folds["selection"]["informative_runs"] >= minimum["selection"],
        "strong_selection_coverage": folds["selection"]["strong_runs"]
        >= minimum["strong_selection"],
    }
    fit_ids = set(folds["fit"]["unique_option_ids"])
    return {
        "benchmark_denominator": len(config.seeds),
        "completed_runs": completed,
        "failed_runs": len(config.seeds) - completed,
        "candidate_denominator": 3 * len(config.seeds),
        "completed_branches": sum(b["status"] == "completed" for b in branches),
        "failed_or_missing_branches": 3 * len(config.seeds)
        - sum(b["status"] == "completed" for b in branches),
        "recorded_trajectories": len(trajectories),
        "recorded_transitions": sum(len(t["decisions"]) for t in trajectories),
        "truncated_trajectories": sum(t["truncated"] is True for t in trajectories),
        "terminal_victories": sum(
            t["terminal"] is True and t["victory"] is True for t in trajectories
        ),
        "complete_run_subfolds": folds,
        "selection_option_ids_absent_from_fitting": sorted(
            set(folds["selection"]["unique_option_ids"]) - fit_ids
        ),
        "sufficiency_checks": checks,
        "evidence_sufficient": all(checks.values()),
        "independent_unit": "complete_run_seed",
        "futures_per_option": 1,
    }


def collect_starting_option_evidence(
    *,
    environment_factory: Callable[[], EnvironmentAdapter],
    ruleset: RulesetIdentity,
    policy: ProductionCheckpointPolicy,
    split_manifest: SplitManifest,
    training_report_id: str,
    config: StartingEvidenceConfig,
    objective: ObjectiveSpec,
    output_directory: Path,
    resume: bool = False,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    runner = config.runner
    _validate_inputs(
        ruleset=ruleset,
        policy=policy,
        split_manifest=split_manifest,
        training_report_id=training_report_id,
        config=runner,
    )
    if objective.objective_id != runner.objective_id:
        raise ValueError("Starting evidence objective differs")
    _validate_seed_window(config, split_manifest)
    directory = output_directory.expanduser().resolve()
    if (directory / FILENAME).exists() or (directory.exists() and not resume):
        raise FileExistsError(f"Starting evidence output already exists: {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    started_at = _utc_now()
    cases = []
    pending = []
    for seed in config.seeds:
        path = _path(directory, seed)
        if directory not in path.resolve().parents:
            raise ValueError("Starting evidence case path escapes its directory")
        if path.exists():
            case = json.loads(path.read_text(encoding="utf-8"))
            _validate_evidence_case(case, config=config, ruleset=ruleset, seed=seed)
            cases.append(case)
        else:
            pending.append(seed)
    if progress is not None and cases:
        progress(len(cases), len(config.seeds))
    with ThreadPoolExecutor(max_workers=runner.workers) as executor:
        futures = {
            executor.submit(
                _collect_case,
                factory=environment_factory,
                ruleset=ruleset,
                policy=policy,
                config=config,
                seed=seed,
            ): seed
            for seed in pending
        }
        for future in as_completed(futures):
            seed = futures[future]
            case = future.result()
            _publish_json(_path(directory, seed), case)
            cases.append(case)
            if progress is not None:
                progress(len(cases), len(config.seeds))
    cases.sort(key=lambda c: int(c["run_seed"]))
    body = {
        "schema_version": REPORT_SCHEMA,
        "configuration": config.document,
        "config_id": config.config_id,
        "ruleset_manifest_id": ruleset.manifest_id,
        "patch_id": ruleset.patch_id,
        "model_id": policy.model_id,
        "training_report_id": training_report_id,
        "split_manifest_id": split_manifest.manifest_id,
        "objective_id": objective.objective_id,
        "partition": "train",
        "started_at": started_at,
        "completed_at": _utc_now(),
        "cases": [_reference(directory, c) for c in cases],
        "summary": _summary(cases, config),
        "hidden_state_resampling": False,
        "training_started": False,
        "checkpoint_promoted": False,
        "claim_scope": CLAIM,
    }
    report = _identified(body, "report_id")
    _publish_json(directory / FILENAME, report)
    verify_starting_option_evidence(
        directory / FILENAME, config=config, split_manifest=split_manifest, ruleset=ruleset
    )
    return report


def _validate_seed_window(config: StartingEvidenceConfig, split: SplitManifest) -> None:
    runner = config.runner
    window = split.seeds(SplitName.TRAIN)[runner.run_offset : runner.run_offset + runner.run_count]
    if (
        config.seeds != window
        or split.manifest_id != runner.split_manifest_id
        or split.ruleset_manifest_id != runner.ruleset_manifest_id
        or split.objective_id != runner.objective_id
    ):
        raise ValueError("Starting evidence frozen seeds, split, ruleset or objective differ")


def verify_starting_option_evidence(
    path: Path,
    *,
    config: StartingEvidenceConfig,
    split_manifest: SplitManifest,
    ruleset: RulesetIdentity,
) -> dict[str, Any]:
    report, cases = load_verified_starting_option_evidence(
        path, config=config, split_manifest=split_manifest, ruleset=ruleset
    )
    return {
        "valid": True,
        "report_id": report["report_id"],
        "verified_cases": len(cases),
        "summary": report["summary"],
        "games_replayed": 0,
    }


def load_verified_starting_option_evidence(
    path: Path,
    *,
    config: StartingEvidenceConfig,
    split_manifest: SplitManifest,
    ruleset: RulesetIdentity,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load verified cases once for consumers; never reset or replay an environment."""
    _validate_seed_window(config, split_manifest)
    report = json.loads(path.read_text(encoding="utf-8"))
    _exact_keys(
        report,
        {
            "schema_version",
            "report_id",
            "configuration",
            "config_id",
            "ruleset_manifest_id",
            "patch_id",
            "model_id",
            "training_report_id",
            "split_manifest_id",
            "objective_id",
            "partition",
            "started_at",
            "completed_at",
            "cases",
            "summary",
            "hidden_state_resampling",
            "training_started",
            "checkpoint_promoted",
            "claim_scope",
        },
        "starting report",
    )
    _identity(report, "report_id")
    runner = config.runner
    expected = {
        "schema_version": REPORT_SCHEMA,
        "configuration": config.document,
        "config_id": config.config_id,
        "ruleset_manifest_id": ruleset.manifest_id,
        "patch_id": ruleset.patch_id,
        "model_id": runner.model_id,
        "training_report_id": runner.training_report_id,
        "split_manifest_id": split_manifest.manifest_id,
        "objective_id": runner.objective_id,
        "partition": "train",
        "hidden_state_resampling": False,
        "training_started": False,
        "checkpoint_promoted": False,
        "claim_scope": CLAIM,
    }
    if any(report[k] != v for k, v in expected.items()):
        raise ValueError("Starting evidence report provenance or scope differs")
    references = _list(report["cases"], "starting evidence cases")
    if [r.get("run_seed") for r in references] != list(config.seeds):
        raise ValueError("Starting evidence lost configured complete-run coverage")
    directory = path.expanduser().resolve().parent
    cases = []
    for reference, seed in zip(references, config.seeds, strict=True):
        case_path = _path(directory, seed)
        if directory not in case_path.resolve().parents:
            raise ValueError("Starting evidence case path escapes its directory")
        case = json.loads(case_path.read_text(encoding="utf-8"))
        _validate_evidence_case(case, config=config, ruleset=ruleset, seed=seed)
        if reference != _reference(directory, case):
            raise ValueError("Starting evidence case file reference differs")
        cases.append(case)
    if report["summary"] != _summary(cases, config):
        raise ValueError("Starting evidence summary or sufficiency gate differs")
    return report, cases
