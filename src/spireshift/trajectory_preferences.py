from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from spireshift.agents.learned import ProductionCheckpointPolicy
from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.protocols import EnvironmentAdapter
from spireshift.core.types import LegalAction, Observation
from spireshift.rollouts import write_exclusive_json
from spireshift.splits import SplitManifest, SplitName
from spireshift.trajectory_search import (
    TRAJECTORY_SELECTION_RANK_ORDER,
    TrajectorySearchConfig,
    _MutationPlan,
    _run_trajectory,
    trajectory_selection_rank,
    verify_trajectory_search,
)

TRAJECTORY_PREFERENCE_SCHEMA_VERSION = "trajectory-mutation-preference-set-v1"
TRAJECTORY_PREFERENCE_VERIFICATION_SCHEMA_VERSION = "trajectory-mutation-preference-verification-v1"
TRAJECTORY_PREFERENCE_CLAIM_SCOPE = "verified_train_only_single_run_auxiliary_policy_preferences"


def freeze_trajectory_mutation_preferences(
    *,
    search_report_path: Path,
    search_config: TrajectorySearchConfig,
    output_path: Path,
    split_manifest: SplitManifest,
    environment_factory: Callable[[], EnvironmentAdapter],
    ruleset: RulesetIdentity,
    policy: ProductionCheckpointPolicy,
    run_seed: int,
    trajectory_id: str,
    minimum_training_runs: int = 2,
) -> dict[str, Any]:
    document = build_trajectory_mutation_preferences(
        search_report_path=search_report_path,
        search_config=search_config,
        split_manifest=split_manifest,
        environment_factory=environment_factory,
        ruleset=ruleset,
        policy=policy,
        run_seed=run_seed,
        trajectory_id=trajectory_id,
        minimum_training_runs=minimum_training_runs,
    )
    write_exclusive_json(output_path, document)
    return document


def build_trajectory_mutation_preferences(
    *,
    search_report_path: Path,
    search_config: TrajectorySearchConfig,
    split_manifest: SplitManifest,
    environment_factory: Callable[[], EnvironmentAdapter],
    ruleset: RulesetIdentity,
    policy: ProductionCheckpointPolicy,
    run_seed: int,
    trajectory_id: str,
    minimum_training_runs: int = 2,
) -> dict[str, Any]:
    if minimum_training_runs < 2:
        raise ValueError("Trajectory preferences require at least two training runs")
    if search_config.frontier_ranking is None:
        raise ValueError("Trajectory preferences require a frozen public-frontier ranking")
    if split_manifest.split_for_seed(run_seed) is not SplitName.TRAIN:
        raise ValueError("Trajectory preference seed is outside the train partition")
    expected = {
        "split_manifest_id": split_manifest.manifest_id,
        "ruleset_manifest_id": ruleset.manifest_id,
        "model_id": policy.model_id,
        "policy_id": policy.policy_id,
    }
    actual = {
        "split_manifest_id": search_config.split_manifest_id,
        "ruleset_manifest_id": search_config.ruleset_manifest_id,
        "model_id": search_config.model_id,
        "policy_id": policy.policy_id,
    }
    if actual != expected or policy.split_manifest_id != split_manifest.manifest_id:
        raise ValueError("Trajectory preference runtime differs from the search configuration")

    verification = verify_trajectory_search(
        search_report_path,
        config=search_config,
        split_manifest=split_manifest,
    )
    if verification.get("valid") is not True:
        raise ValueError(
            "Trajectory search failed verification: "
            + "; ".join(str(value) for value in verification.get("errors", []))
        )
    report = _load_object(search_report_path, "trajectory search report")
    if report.get("hidden_state_resampling") is not False:
        raise ValueError("Trajectory search permits hidden-state resampling")
    case_path, case_reference = _search_case_path(search_report_path, report, run_seed)
    case = _load_object(case_path, "trajectory search case")
    if case.get("case_id") != case_reference.get("case_id"):
        raise ValueError("Trajectory preference search case identity differs")
    if case.get("status") != "completed" or case.get("hidden_state_resampling") is not False:
        raise ValueError("Trajectory preference search case is not completed exact evidence")
    if case.get("best_trajectory_id") != trajectory_id:
        raise ValueError("Trajectory preference source is not the accepted best trajectory")

    trajectories = {
        _string(item.get("trajectory_id"), "trajectory ID"): item
        for item in (
            _mapping(value, "trajectory")
            for value in _list(case.get("trajectories"), "search trajectories")
        )
    }
    accepted = trajectories.get(trajectory_id)
    if accepted is None:
        raise ValueError("Accepted trajectory is absent from its search case")
    lineage = _trajectory_lineage(accepted, trajectories)
    if len(lineage) < 2:
        raise ValueError("Accepted trajectory has no mutation lineage")

    replayed: dict[str, dict[str, Any]] = {}
    lineage_replay: list[dict[str, Any]] = []
    mutation_observations: dict[str, dict[str, Any]] = {}
    for stored in lineage:
        stored_id = _string(stored.get("trajectory_id"), "stored trajectory ID")
        parent_id = stored.get("parent_trajectory_id")
        plan: _MutationPlan | None = None
        source_observer = None
        if parent_id is not None:
            parent = replayed.get(_string(parent_id, "parent trajectory ID"))
            if parent is None:
                raise ValueError("Trajectory preference lineage parent was not replayed")
            mutation = _mapping(stored.get("mutation"), "trajectory mutation")
            if (
                mutation.get("applied") is not True
                or mutation.get("replay_aligned_through_mutation") is not True
                or mutation.get("divergence") is not None
            ):
                raise ValueError("Trajectory preference lineage mutation is not exact")
            mutation_index = _integer(
                mutation.get("requested_decision_index"), "mutation decision index"
            )
            plan = _MutationPlan(
                parent=parent,
                decision_index=mutation_index,
                action_id=_string(mutation.get("requested_action_id"), "mutation action ID"),
                offspring_index=_integer(
                    mutation.get("offspring_index"), "mutation offspring index"
                ),
            )

            def observe_source(
                decision_index: int,
                observation: Observation,
                _actions: tuple[LegalAction, ...],
                *,
                expected_index: int = mutation_index,
                child_id: str = stored_id,
            ) -> None:
                if decision_index == expected_index:
                    if child_id in mutation_observations:
                        raise ValueError("Mutation source was captured more than once")
                    mutation_observations[child_id] = observation.as_dict()

            source_observer = observe_source
        replay = _run_trajectory(
            environment_factory=environment_factory,
            ruleset=ruleset,
            policy=policy,
            config=search_config,
            seed=run_seed,
            generation=_integer(stored.get("generation"), "trajectory generation"),
            parent=None if plan is None else plan.parent,
            mutation=plan,
            source_observer=source_observer,
        )
        if replay != stored:
            raise ValueError(f"Exact trajectory replay differs for {stored_id}")
        replayed[stored_id] = replay
        lineage_replay.append(
            {
                "trajectory_id": stored_id,
                "action_trace_sha256": replay["action_trace_sha256"],
                "decisions": len(_list(replay.get("decisions"), "replayed decisions")),
                "exact": True,
            }
        )

    preferences: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for child in lineage[1:]:
        child_id = _string(child.get("trajectory_id"), "child trajectory ID")
        parent_id = _string(child.get("parent_trajectory_id"), "parent trajectory ID")
        parent = replayed[parent_id]
        replayed_child = replayed[child_id]
        mutation = _mapping(replayed_child.get("mutation"), "replayed mutation")
        decision_index = _integer(
            mutation.get("requested_decision_index"), "mutation decision index"
        )
        parent_decisions = _list(parent.get("decisions"), "parent decisions")
        child_decisions = _list(replayed_child.get("decisions"), "child decisions")
        if decision_index >= len(parent_decisions) or decision_index >= len(child_decisions):
            raise ValueError("Mutation decision is absent from its parent or child")
        parent_decision = _mapping(parent_decisions[decision_index], "parent decision")
        child_decision = _mapping(child_decisions[decision_index], "child decision")
        source_state_hash = _string(
            parent_decision.get("source_state_hash"), "mutation source state hash"
        )
        candidate_action_ids = [
            _string(value, "candidate action ID")
            for value in _list(parent_decision.get("candidate_action_ids"), "candidate actions")
        ]
        if (
            child_decision.get("source_state_hash") != source_state_hash
            or child_decision.get("candidate_action_ids") != candidate_action_ids
        ):
            raise ValueError("Mutation does not compare actions at the same public decision")
        parent_action = _string(parent_decision.get("selected_action_id"), "parent action ID")
        child_action = _string(child_decision.get("selected_action_id"), "child action ID")
        if child_action != mutation.get("requested_action_id") or child_action == parent_action:
            raise ValueError("Mutation action pair differs from its exact replay")
        if parent_action not in candidate_action_ids or child_action not in candidate_action_ids:
            raise ValueError("Mutation action pair is absent from the legal candidates")
        source_observation = mutation_observations.get(child_id)
        if source_observation is None:
            raise ValueError("Mutation source observation was not captured")
        if source_observation.get("state_hash") != source_state_hash:
            raise ValueError("Mutation source observation differs from exact replay")

        parent_rank = trajectory_selection_rank(parent, config=search_config)
        child_rank = trajectory_selection_rank(replayed_child, config=search_config)
        label = (
            "improved"
            if child_rank > parent_rank
            else "regressed"
            if child_rank < parent_rank
            else "tied"
        )
        deciding_component = _deciding_component(parent_rank, child_rank)
        evidence_body: dict[str, Any] = {
            "run_seed": run_seed,
            "generation": replayed_child["generation"],
            "parent_trajectory_id": parent_id,
            "child_trajectory_id": child_id,
            "decision_index": decision_index,
            "decision_type": parent_decision["decision_type"],
            "source_state_hash": source_state_hash,
            "source_floor": parent_decision["source_floor"],
            "source_act": parent_decision["source_act"],
            "candidate_action_ids": candidate_action_ids,
            "parent_action_id": parent_action,
            "child_action_id": child_action,
            "parent_rank": list(parent_rank),
            "child_rank": list(child_rank),
            "deciding_rank_component": deciding_component,
            "label": label,
            "terminal_victory_label": False,
            "source_observation": source_observation,
        }
        if label == "improved":
            preference_body = {
                **evidence_body,
                "preferred_action_id": child_action,
                "disfavored_action_id": parent_action,
            }
            preferences.append(
                {
                    **preference_body,
                    "preference_id": manifest_identifier(preference_body),
                }
            )
        else:
            exclusion_body = {
                **evidence_body,
                "exclusion_reason": (
                    "equal_frozen_public_frontier_rank"
                    if label == "tied"
                    else "child_regressed_on_frozen_public_frontier_rank"
                ),
            }
            excluded.append(
                {
                    **exclusion_body,
                    "mutation_evidence_id": manifest_identifier(exclusion_body),
                }
            )

    labels = [str(item["label"]) for item in preferences + excluded]
    unique_runs = 1
    body: dict[str, Any] = {
        "schema_version": TRAJECTORY_PREFERENCE_SCHEMA_VERSION,
        "search_report_id": report["report_id"],
        "search_verification_id": verification["verification_id"],
        "search_config_id": search_config.config_id,
        "search_case_id": case["case_id"],
        "accepted_trajectory_id": trajectory_id,
        "source_model_id": search_config.model_id,
        "source_training_report_id": search_config.training_report_id,
        "split_manifest_id": split_manifest.manifest_id,
        "ruleset_manifest_id": split_manifest.ruleset_manifest_id,
        "objective_id": split_manifest.objective_id,
        "partition": SplitName.TRAIN.value,
        "information_policy_id": "public-state-v1",
        "hidden_state_resampling": False,
        "rank_order": list(TRAJECTORY_SELECTION_RANK_ORDER),
        "lineage_replay": lineage_replay,
        "preferences": preferences,
        "excluded_mutations": excluded,
        "summary": {
            "mutations": len(lineage) - 1,
            "strict_improvements": labels.count("improved"),
            "tied": labels.count("tied"),
            "regressed": labels.count("regressed"),
            "unique_runs": unique_runs,
            "minimum_training_runs": minimum_training_runs,
            "training_ready": unique_runs >= minimum_training_runs and bool(preferences),
            "terminal_victory_positive_labels": 0,
        },
        "claim_scope": TRAJECTORY_PREFERENCE_CLAIM_SCOPE,
    }
    return {**body, "preference_set_id": manifest_identifier(body)}


def verify_trajectory_mutation_preferences(
    preference_path: Path,
    *,
    search_report_path: Path,
    search_config: TrajectorySearchConfig,
    split_manifest: SplitManifest,
    environment_factory: Callable[[], EnvironmentAdapter],
    ruleset: RulesetIdentity,
    policy: ProductionCheckpointPolicy,
    run_seed: int,
    trajectory_id: str,
    minimum_training_runs: int = 2,
) -> dict[str, Any]:
    errors: list[str] = []
    document: dict[str, Any] = {}
    try:
        document = _load_object(preference_path, "trajectory preference set")
        expected = build_trajectory_mutation_preferences(
            search_report_path=search_report_path,
            search_config=search_config,
            split_manifest=split_manifest,
            environment_factory=environment_factory,
            ruleset=ruleset,
            policy=policy,
            run_seed=run_seed,
            trajectory_id=trajectory_id,
            minimum_training_runs=minimum_training_runs,
        )
        if document != expected:
            errors.append("Trajectory preference set differs from exact lineage replay")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    body: dict[str, Any] = {
        "schema_version": TRAJECTORY_PREFERENCE_VERIFICATION_SCHEMA_VERSION,
        "preference_set_id": document.get("preference_set_id"),
        "valid": not errors,
        "verified_lineage_trajectories": (
            len(_list(document.get("lineage_replay"), "lineage replay")) if not errors else 0
        ),
        "verified_mutations": (
            _integer(
                _mapping(document.get("summary"), "preference summary").get("mutations"),
                "verified mutations",
            )
            if not errors
            else 0
        ),
        "errors": errors,
    }
    return {**body, "verification_id": manifest_identifier(body)}


def _trajectory_lineage(
    trajectory: dict[str, Any], trajectories: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    reverse_lineage: list[dict[str, Any]] = []
    seen: set[str] = set()
    current = trajectory
    while True:
        current_id = _string(current.get("trajectory_id"), "trajectory ID")
        if current_id in seen:
            raise ValueError("Trajectory preference lineage contains a cycle")
        seen.add(current_id)
        reverse_lineage.append(current)
        parent_id = current.get("parent_trajectory_id")
        if parent_id is None:
            break
        parent = trajectories.get(_string(parent_id, "parent trajectory ID"))
        if parent is None:
            raise ValueError("Trajectory preference lineage parent is missing")
        current = parent
    return list(reversed(reverse_lineage))


def _deciding_component(parent_rank: tuple[int, ...], child_rank: tuple[int, ...]) -> str | None:
    for component, parent_value, child_value in zip(
        TRAJECTORY_SELECTION_RANK_ORDER, parent_rank, child_rank, strict=True
    ):
        if parent_value != child_value:
            return component
    return None


def _search_case_path(
    report_path: Path, report: dict[str, Any], run_seed: int
) -> tuple[Path, dict[str, Any]]:
    references = [
        _mapping(value, "search case reference")
        for value in _list(report.get("cases"), "search case references")
        if isinstance(value, dict) and value.get("seed") == run_seed
    ]
    if len(references) != 1:
        raise ValueError("Search report does not contain exactly one requested seed case")
    reference = references[0]
    root = report_path.expanduser().resolve().parent
    path = (root / _string(reference.get("path"), "search case path")).resolve()
    if root not in path.parents:
        raise ValueError("Trajectory preference search case path escapes its report root")
    return path, reference


def _load_object(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    return _mapping(value, label)


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise TypeError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{label} must be an array")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError(f"{label} must be a non-empty string")
    return value


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{label} must be an integer")
    return value
