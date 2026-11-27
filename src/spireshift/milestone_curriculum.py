from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.bootstrap_teacher import (
    MILESTONE_TRAJECTORY_SELECTION_POLICY_PREFIX,
    BootstrapPolicyArtifacts,
    CurriculumSignalSpec,
    CurriculumStateCase,
    CurriculumStateSet,
    load_bootstrap_state_set_document,
    verify_bootstrap_teacher_dataset,
    verify_milestone_trajectory_replay,
)
from spireshift.core.manifest import manifest_identifier
from spireshift.core.types import DecisionType
from spireshift.rollouts import write_exclusive_json
from spireshift.search_workers import SearchBackendSpec
from spireshift.splits import SplitManifest, SplitName
from spireshift.trajectory_search import TrajectorySearchConfig, verify_trajectory_search

MILESTONE_REPLAY_SCHEMA_VERSION = "milestone-trajectory-replay-v1"
MILESTONE_DISCOVERY_SCHEMA_VERSION = "milestone-trajectory-discovery-v1"


def freeze_milestone_trajectory_state_set(
    *,
    search_report_path: Path,
    search_config: TrajectorySearchConfig,
    output_path: Path,
    split_manifest: SplitManifest,
    backend: SearchBackendSpec,
    policy_artifacts: BootstrapPolicyArtifacts,
    run_seed: int,
    trajectory_id: str,
    excluded_dataset_paths: tuple[Path, ...] = (),
    predecessor_count: int = 1,
    frontier_minimum_floor: int = 17,
    frontier_minimum_actions: int = 2,
    expected_mutations: int = 7,
) -> dict[str, Any]:
    """Freeze exact searched states for later teacher generation."""
    if predecessor_count < 0:
        raise ValueError("predecessor_count must be non-negative")
    if frontier_minimum_floor < 0 or frontier_minimum_actions < 2:
        raise ValueError("Milestone frontier thresholds are outside their allowed range")
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
    report = _load_object(search_report_path)
    if report.get("hidden_state_resampling") is not False:
        raise ValueError("Trajectory search permits hidden-state resampling")
    if split_manifest.split_for_seed(run_seed) is not SplitName.TRAIN:
        raise ValueError("Milestone trajectory seed is outside the train partition")
    policy_artifacts.validate_for(
        split_manifest_id=split_manifest.manifest_id,
        ruleset_manifest_id=split_manifest.ruleset_manifest_id,
    )
    expected_policy = {
        "model_id": search_config.model_id,
        "training_report_id": search_config.training_report_id,
        "split_manifest_id": search_config.split_manifest_id,
        "ruleset_manifest_id": search_config.ruleset_manifest_id,
    }
    provenance = policy_artifacts.provenance()
    if any(provenance.get(key) != value for key, value in expected_policy.items()):
        raise ValueError("Milestone continuation policy differs from trajectory-search policy")

    case_path, case_reference = _search_case_path(search_report_path, report, run_seed)
    case = _load_object(case_path)
    if case.get("case_id") != case_reference.get("case_id"):
        raise ValueError("Milestone search case identity differs from its report reference")
    if case.get("status") != "completed" or case.get("hidden_state_resampling") is not False:
        raise ValueError("Milestone search case is not a completed exact-replay case")
    if case.get("best_trajectory_id") != trajectory_id:
        raise ValueError("Requested trajectory is not the accepted best trajectory")
    trajectories = {
        str(item["trajectory_id"]): item
        for item in _list(case.get("trajectories"), "search trajectories")
        if isinstance(item, dict) and isinstance(item.get("trajectory_id"), str)
    }
    trajectory = trajectories.get(trajectory_id)
    if trajectory is None:
        raise ValueError("Accepted trajectory is absent from its verified search case")
    if (
        trajectory.get("boss_reached") is not True
        or trajectory.get("act1_cleared") is not False
        or trajectory.get("terminal") is not True
        or trajectory.get("victory") is not False
    ):
        raise ValueError("Accepted trajectory no longer represents the non-victory boss reach")

    lineage, mutations = _trajectory_lineage(trajectory, trajectories)
    if len(mutations) != expected_mutations:
        raise ValueError(
            f"Accepted trajectory has {len(mutations)} mutations; expected {expected_mutations}"
        )
    decisions = [
        _capture_decision(raw_record)
        for raw_record in _list(trajectory.get("decisions"), "trajectory decisions")
    ]
    capture_body: dict[str, Any] = {
        "schema_version": MILESTONE_REPLAY_SCHEMA_VERSION,
        "search_report_id": report["report_id"],
        "search_verification_id": verification["verification_id"],
        "search_config_id": search_config.config_id,
        "search_case_id": case["case_id"],
        "trajectory_id": trajectory_id,
        "lineage_trajectory_ids": lineage,
        "mutation_lineage": mutations,
        "run_seed": run_seed,
        "ruleset_manifest_id": split_manifest.ruleset_manifest_id,
        "hidden_state_resampling": False,
        "action_trace_sha256": trajectory["action_trace_sha256"],
        "maximum_floor": trajectory["maximum_floor"],
        "boss_reached": True,
        "act1_cleared": False,
        "terminal": True,
        "victory": False,
        "final_state_hash": trajectory["final_state_hash"],
        "no_op_fallback_threshold": search_config.no_op_fallback_threshold,
        "liveness_tail_length": search_config.liveness_tail_length,
        "decisions": decisions,
    }
    capture_trajectory = {
        **capture_body,
        "capture_trajectory_id": manifest_identifier(capture_body),
    }
    eligible_action_counts = verify_milestone_trajectory_replay(
        backend=backend,
        capture_trajectory=capture_trajectory,
    )
    if len(eligible_action_counts) != len(decisions):
        raise AssertionError("Exact milestone replay returned incomplete action evidence")

    mutation_indices = {int(item["decision_index"]) for item in mutations}
    selected_indices = set(mutation_indices)
    for mutation_index in mutation_indices:
        selected_indices.update(range(max(0, mutation_index - predecessor_count), mutation_index))
    selected_indices.update(
        index
        for index, (record, action_count) in enumerate(
            zip(decisions, eligible_action_counts, strict=True)
        )
        if int(record["source_floor"] or 0) >= frontier_minimum_floor
        and action_count >= frontier_minimum_actions
    )
    excluded_hashes, excluded_dataset_ids = _excluded_state_hashes(
        excluded_dataset_paths,
        split_manifest=split_manifest,
    )
    occurrences: Counter[str] = Counter()
    occurrence_by_index: dict[int, int] = {}
    for index, record in enumerate(decisions):
        decision_type = str(record["decision_type"])
        occurrence_by_index[index] = occurrences[decision_type]
        occurrences[decision_type] += 1

    cases: list[CurriculumStateCase] = []
    seen_hashes = set(excluded_hashes)
    excluded_duplicates = 0
    for index in sorted(selected_indices):
        record = decisions[index]
        state_hash = str(record["source_state_hash"])
        if state_hash in seen_hashes:
            excluded_duplicates += 1
            continue
        seen_hashes.add(state_hash)
        cases.append(
            CurriculumStateCase(
                state_id=f"train-seed-{run_seed:06d}-trajectory-{index:03d}",
                run_seed=run_seed,
                decision_type=DecisionType(str(record["decision_type"])),
                decision_index=occurrence_by_index[index],
                expected_state_hash=state_hash,
                expected_legal_actions=eligible_action_counts[index],
                expected_source_floor=_optional_integer(record.get("source_floor")),
                expected_source_act=_optional_act(record.get("source_act")),
                trajectory_decision_index=index,
                expected_selected_action_id=str(record["selected_action_id"]),
                expected_next_state_hash=str(record["next_state_hash"]),
            )
        )
    if not cases:
        raise ValueError("Milestone selection produced no new curriculum states")

    selection_body = {
        "schema_version": "milestone-trajectory-selection-v1",
        "mutation_decisions": sorted(mutation_indices),
        "predecessor_count": predecessor_count,
        "frontier_minimum_floor": frontier_minimum_floor,
        "frontier_minimum_actions": frontier_minimum_actions,
        "deduplication_rule": "source_state_hash_against_existing_verified_curricula_v1",
    }
    selection_policy = MILESTONE_TRAJECTORY_SELECTION_POLICY_PREFIX + manifest_identifier(
        selection_body
    )
    discovery = {
        "schema_version": MILESTONE_DISCOVERY_SCHEMA_VERSION,
        "exact_replay": True,
        "search_report_id": report["report_id"],
        "search_verification_id": verification["verification_id"],
        "search_case_id": case["case_id"],
        "trajectory_id": trajectory_id,
        "capture_trajectory_id": capture_trajectory["capture_trajectory_id"],
        "replayed_decisions": len(decisions),
        "maximum_steps_per_run": search_config.maximum_decisions_per_run,
        "mutation_lineage_count": len(mutations),
        "selection": selection_body,
        "requested_coordinates": len(selected_indices),
        "captured_coordinates": len(cases),
        "excluded_duplicate_states": excluded_duplicates,
        "excluded_dataset_ids": excluded_dataset_ids,
        "source_maximum_floor": trajectory["maximum_floor"],
        "boss_reached": True,
        "act1_cleared": False,
        "terminal": True,
        "victory": False,
    }
    floors = {
        case.expected_source_floor for case in cases if case.expected_source_floor is not None
    }
    decision_types = {case.decision_type for case in cases}
    signal_spec = CurriculumSignalSpec(
        minimum_states=len(cases),
        minimum_source_floors=len(floors),
        minimum_decision_types=len(decision_types),
        minimum_effective_labeled_states=1.0,
        minimum_half_split_agreement=0.5,
        minimum_occupied_maximum_floor_bins=1,
    )
    state_body: dict[str, Any] = {
        "schema_version": "bootstrap-state-set-v6",
        "split_manifest_id": split_manifest.manifest_id,
        "ruleset_manifest_id": split_manifest.ruleset_manifest_id,
        "objective_id": split_manifest.objective_id,
        "capture_policy_id": policy_artifacts.policy_id,
        "partition": SplitName.TRAIN.value,
        "selection_policy": selection_policy,
        "discovery": discovery,
        "signal_spec": signal_spec.as_dict(),
        "cases": [case.as_dict() for case in cases],
        "capture_policy": provenance,
        "capture_trajectory": capture_trajectory,
    }
    document = {**state_body, "state_set_id": manifest_identifier(state_body)}
    loaded = load_bootstrap_state_set_document(document)
    if not isinstance(loaded, CurriculumStateSet) or loaded.as_dict() != document:
        raise AssertionError("Milestone state set failed its canonical round trip")
    write_exclusive_json(output_path, document)
    return document


def _search_case_path(
    report_path: Path,
    report: dict[str, Any],
    run_seed: int,
) -> tuple[Path, dict[str, Any]]:
    references = [
        item
        for item in _list(report.get("cases"), "search case references")
        if isinstance(item, dict) and item.get("seed") == run_seed
    ]
    if len(references) != 1:
        raise ValueError("Search report does not contain exactly one requested seed case")
    reference = references[0]
    relative = Path(str(reference.get("path")))
    root = report_path.expanduser().resolve().parent
    resolved = (root / relative).resolve()
    if root not in resolved.parents:
        raise ValueError("Search case path escapes its report root")
    return resolved, reference


def _trajectory_lineage(
    trajectory: dict[str, Any],
    trajectories: dict[str, dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    reverse_lineage: list[dict[str, Any]] = []
    seen: set[str] = set()
    current = trajectory
    while True:
        current_id = str(current["trajectory_id"])
        if current_id in seen:
            raise ValueError("Trajectory lineage contains a cycle")
        seen.add(current_id)
        reverse_lineage.append(current)
        parent_id = current.get("parent_trajectory_id")
        if parent_id is None:
            break
        parent = trajectories.get(str(parent_id))
        if parent is None:
            raise ValueError("Trajectory lineage parent is missing")
        current = parent
    lineage = list(reversed(reverse_lineage))
    mutations: list[dict[str, Any]] = []
    for child in lineage[1:]:
        mutation = child.get("mutation")
        if not isinstance(mutation, dict) or mutation.get("applied") is not True:
            raise ValueError("Milestone lineage contains an unapplied mutation")
        mutations.append(
            {
                "trajectory_id": child["trajectory_id"],
                "parent_trajectory_id": mutation["parent_trajectory_id"],
                "generation": child["generation"],
                "decision_index": mutation["requested_decision_index"],
                "action_id": mutation["requested_action_id"],
            }
        )
    return [str(item["trajectory_id"]) for item in lineage], mutations


def _capture_decision(value: object) -> dict[str, Any]:
    record = _mapping(value, "trajectory decision")
    return {
        "decision_index": record["decision_index"],
        "decision_type": record["decision_type"],
        "source_state_hash": record["source_state_hash"],
        "source_floor": record["source_floor"],
        "source_act": record["source_act"],
        "candidate_action_ids": record["candidate_action_ids"],
        "selected_action_id": record["selected_action_id"],
        "selection_source": record["selection_source"],
        "next_state_hash": record["next_state_hash"],
        "terminal_after_action": record["terminal_after_action"],
        "victory_after_action": record["victory_after_action"],
    }


def _excluded_state_hashes(
    paths: tuple[Path, ...],
    *,
    split_manifest: SplitManifest,
) -> tuple[set[str], list[str]]:
    hashes: set[str] = set()
    dataset_ids: list[str] = []
    for path in paths:
        resolved = path.expanduser().resolve()
        verification = verify_bootstrap_teacher_dataset(
            resolved,
            split_manifest=split_manifest,
        )
        if not verification.valid:
            raise ValueError(
                f"Excluded curriculum failed verification ({resolved}): "
                + "; ".join(verification.errors)
            )
        report = _load_object(resolved)
        state_set = load_bootstrap_state_set_document(report.get("state_set"))
        hashes.update(case.expected_state_hash for case in state_set.cases)
        dataset_ids.append(str(report["dataset_id"]))
    return hashes, dataset_ids


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected JSON object in {path}")
    return value


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    return value


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{label} must be an array")
    return value


def _optional_integer(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("source floor must be an integer or null")
    return value


def _optional_act(value: object) -> int | str | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise TypeError("source act must be an integer, string, or null")
    return value
