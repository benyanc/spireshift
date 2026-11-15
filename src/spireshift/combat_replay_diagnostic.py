"""Public, owner-run diagnosis of an already inspected combat confirmation."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import tempfile
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Self

from spireshift.agents.learned import ProductionCheckpointPolicy, ProductionPolicyDecision
from spireshift.combat_confirmation import (
    CombatConfirmationConfig,
    load_combat_confirmation_config,
    load_confirmation_policies,
)
from spireshift.combat_features import CombatLayout, bind_public_combat
from spireshift.combat_foundation import _relative_path, load_combat_foundation_report
from spireshift.combat_policy import load_combat_policy_config
from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.core.protocols import EnvironmentAdapter
from spireshift.core.types import DecisionType, LegalAction, Observation, Transition
from spireshift.models import _exact_keys, _integer, _mapping
from spireshift.production_evaluation import (
    FRESH_PRODUCTION_POLICY_CASE_SCHEMA_VERSION,
    LEARNED_POLICY_KIND,
    REFERENCE_POLICY_KIND,
    _evaluate_case,
    _validate_fresh_case,
    load_production_policy_evaluation,
)
from spireshift.production_models import _safe_child
from spireshift.representations import build_model_input
from spireshift.resource_tracking import load_resource_report
from spireshift.splits import SplitManifest, SplitName
from spireshift.starting_evidence import _publish_json
from spireshift.trajectory_policy import _id, _identified

CONFIG_SCHEMA = "combat-policy-replay-diagnostic-config-v1"
REPORT_SCHEMA = "combat-policy-replay-diagnostic-v1"
CASE_SCHEMA = "combat-policy-replay-diagnostic-case-v1"
CLAIM = "inspected_train_confirmation_public_replay_diagnosis_no_new_strength_claim"
PROTOCOL = {
    "population": "all_saved_train_seed_policy_pairs_no_replacement",
    "replay_rule": "saved_outcomes_action_digest_final_hash_and_guard_diagnostics_must_match",
    "shadow_rule": "same_public_state_ordered_menu_no_shadow_actions_executed",
    "unsupported_shadow": "record_error_keep_original_driver_choice",
    "information_policy": "public_observation_only_no_clone_no_hidden_resampling",
    "compute": "serial_original_cpu_cap_includes_diagnostic_overhead_not_new_benchmark",
    "interpretation": "descriptive_choices_and_realized_damage_not_causal_action_values",
    "stop_rule": "owner_review_before_any_new_collection_or_training",
}
SEMANTIC_FIELDS = (
    "status",
    "error",
    "decisions",
    "terminal",
    "victory",
    "truncated",
    "termination_reason",
    "liveness",
    "fallback",
    "maximum_floor",
    "maximum_act",
    "final_state_hash",
    "action_trace_sha256",
    "public_progress",
    "failure_kind",
)
KINDS = (LEARNED_POLICY_KIND, REFERENCE_POLICY_KIND)


@dataclass(frozen=True)
class CombatReplayConfig:
    document: dict[str, Any]

    @classmethod
    def from_mapping(cls, value: object) -> CombatReplayConfig:
        d = copy.deepcopy(_mapping(value, "combat replay config"))
        _exact_keys(
            d,
            {
                "schema_version",
                "config_id",
                "confirmation_config_path",
                "confirmation_config_id",
                "comparison_path",
                "comparison_report_id",
                "comparison_resource_path",
                "comparison_resource_report_id",
                "objective",
                "protocol",
                "claim_scope",
            },
            "combat replay config",
        )
        _identified(d, "config_id")
        for key, item in d.items():
            if key.endswith("_path"):
                _relative_path(item)
            elif key.endswith("_id"):
                _id(item, key)
        objective = ObjectiveSpec.from_mapping(_mapping(d["objective"], "objective"))
        if (
            d["schema_version"] != CONFIG_SCHEMA
            or d["protocol"] != PROTOCOL
            or d["claim_scope"] != CLAIM
            or objective.objective_id != "terminal-victory-v1"
        ):
            raise ValueError("Combat replay protocol differs")
        return cls(d)


def load_combat_replay_config(path: Path) -> CombatReplayConfig:
    return CombatReplayConfig.from_mapping(json.loads(path.read_text()))


@dataclass(frozen=True)
class CombatReplayInputs:
    config: CombatReplayConfig
    confirmation: CombatConfirmationConfig
    ruleset: RulesetIdentity
    candidate: ProductionCheckpointPolicy
    reference: ProductionCheckpointPolicy
    comparison: dict[str, Any]
    cases: dict[tuple[int, str], dict[str, Any]]
    coverage: dict[str, Any]
    layout: CombatLayout


def prepare_combat_replay(
    *,
    config: CombatReplayConfig,
    project_root: Path,
    split: SplitManifest,
    ruleset: RulesetIdentity,
    objective: ObjectiveSpec,
) -> CombatReplayInputs:
    """Read compact saved evidence only. No engine, source teacher corpus or optimizer."""
    config = CombatReplayConfig.from_mapping(config.document)
    d, root = config.document, project_root.resolve()
    confirmation = load_combat_confirmation_config(_safe_child(root, d["confirmation_config_path"]))
    if (
        confirmation.document["config_id"] != d["confirmation_config_id"]
        or d["objective"] != objective.as_dict()
        or d["objective"] != confirmation.document["objective"]
    ):
        raise ValueError("Combat replay objective or confirmation differs")
    candidate, reference = load_confirmation_policies(
        config=confirmation,
        project_root=root,
        split=split,
        ruleset=ruleset,
        objective=objective,
    )
    source = _safe_child(root, d["comparison_path"])
    comparison = load_production_policy_evaluation(
        source,
        model_id=candidate.model_id,
        training_report_id=confirmation.document["candidate"]["report_id"],
        reference_model_id=reference.model_id,
        reference_training_report_id=confirmation.document["reference"]["report_id"],
        split_manifest=split,
    )
    resource = load_resource_report(_safe_child(root, d["comparison_resource_path"]))
    if (
        comparison["report_id"] != d["comparison_report_id"]
        or comparison["confirmation_config"] != confirmation.document
        or resource["report_id"] != d["comparison_resource_report_id"]
        or resource["status"] != "completed"
        or resource["exit_code"] != 0
        or resource["cap"] is not None
        or resource["experiment_kind"] != "rollout"
        or resource["usage"]["trajectories"] != len(comparison["cases"])
        or resource["usage"]["simulations"] != 0
        or resource["usage"]["transitions"]
        != sum(
            comparison["summary"][arm]["completed_transitions"]
            for arm in ("candidate", "reference")
        )
    ):
        raise ValueError("Combat replay needs its exact completed comparison and resource report")
    cases = {}
    for entry in comparison["cases"]:
        case = json.loads(_safe_child(source.parent, entry["path"]).read_text())
        if (
            case["status"] != "completed"
            or not case["terminal"]
            or case["truncated"]
            or case["compute"]["budget_exhausted"]
        ):
            raise ValueError("This bounded replay requires completed uncapped source cases")
        cases[case["seed"], case["policy_kind"]] = case
    recipe = load_combat_policy_config(
        _safe_child(root, confirmation.document["training_config_path"])
    )
    audit = load_combat_foundation_report(
        _safe_child(root, recipe.document["foundation_report_path"]), recipe.foundation
    )
    if audit["report_id"] != recipe.document["foundation_report_id"]:
        raise ValueError("Combat replay fitting coverage audit differs")
    fit = audit["summary"]["by_subfold"]["fit"]
    coverage = {
        "foundation_report_id": audit["report_id"],
        "fitting_card_ids": fit["card_ids"],
        "signal_card_ids": fit["signal_card_ids"],
    }
    inputs = CombatReplayInputs(
        config,
        confirmation,
        ruleset,
        candidate,
        reference,
        comparison,
        cases,
        coverage,
        CombatLayout.from_mapping(recipe.document["residual_layout"]),
    )
    _validate_inputs(inputs)
    return inputs


def _validate_inputs(inputs: CombatReplayInputs) -> None:
    """Recheck mutable snapshots before any new environment can be created."""
    config = CombatReplayConfig.from_mapping(inputs.config.document).document
    confirmation = CombatConfirmationConfig.from_mapping(inputs.confirmation.document).document
    _identified(inputs.comparison, "report_id")
    coordinates = {(s, k) for s in confirmation["seeds"] for k in KINDS}
    references = {(r["seed"], r["policy_kind"]): r for r in inputs.comparison["cases"]}
    if (
        confirmation["config_id"] != config["confirmation_config_id"]
        or config["objective"] != confirmation["objective"]
        or inputs.comparison["report_id"] != config["comparison_report_id"]
        or inputs.comparison["confirmation_config"] != confirmation
        or set(inputs.cases) != coordinates
        or set(references) != coordinates
        or len(references) != len(inputs.comparison["cases"])
        or inputs.ruleset.manifest_id != confirmation["ruleset_manifest_id"]
        or inputs.ruleset.patch_id != confirmation["patch_id"]
        or inputs.layout.ruleset_manifest_id != inputs.ruleset.manifest_id
        or inputs.layout.patch_id != inputs.ruleset.patch_id
    ):
        raise ValueError("Diagnostic frozen input identities or complete seed coverage differ")
    _exact_keys(
        inputs.coverage,
        {"foundation_report_id", "fitting_card_ids", "signal_card_ids"},
        "diagnostic fitting coverage",
    )
    _id(inputs.coverage["foundation_report_id"], "foundation report")
    for key in ("fitting_card_ids", "signal_card_ids"):
        values = inputs.coverage[key]
        if (
            not isinstance(values, list)
            or any(type(i) is not int or i < 0 for i in values)
            or values != sorted(set(values))
        ):
            raise ValueError("Diagnostic coverage must contain sorted public card identities")
    for (seed, kind), expected in inputs.cases.items():
        role = "candidate" if kind == LEARNED_POLICY_KIND else "reference"
        driver = inputs.candidate if kind == LEARNED_POLICY_KIND else inputs.reference
        _identified(expected, "case_id")
        _validate_fresh_case(expected, inputs.confirmation)
        if (
            expected["schema_version"] != FRESH_PRODUCTION_POLICY_CASE_SCHEMA_VERSION
            or (expected["seed"], expected["policy_kind"]) != (seed, kind)
            or expected["case_id"] != references[seed, kind]["case_id"]
            or expected["status"] != "completed"
            or not expected["terminal"]
            or expected["truncated"]
            or expected["compute"]["budget_exhausted"]
            or expected["model_id"] != confirmation[role]["model_id"]
            or expected["ruleset_manifest_id"] != inputs.ruleset.manifest_id
            or driver.model_id != expected["model_id"]
            or driver.policy_id != expected["policy_id"]
            or driver.ruleset != inputs.ruleset
            or driver.split_manifest_id != confirmation["split_manifest_id"]
        ):
            raise ValueError("Diagnostic source case or frozen driver identity differs")


def _observation(value: object) -> Observation:
    d = _mapping(value, "public replay observation")
    _exact_keys(
        d,
        {"schema_version", "patch_id", "decision_type", "public_state", "state_hash"},
        "public replay observation",
    )
    return Observation(
        d["schema_version"],
        d["patch_id"],
        DecisionType(d["decision_type"]),
        _mapping(d["public_state"], "public state"),
        d["state_hash"],
    )


def _actions(value: object) -> tuple[LegalAction, ...]:
    if not isinstance(value, list):
        raise ValueError("Replay legal menu is missing")
    result = []
    for item in value:
        d = _mapping(item, "replay action")
        _exact_keys(d, {"action_id", "kind", "payload"}, "replay action")
        result.append(LegalAction(d["action_id"], d["kind"], _mapping(d["payload"], "payload")))
    return tuple(result)


def _public_combat(
    observation: Observation,
    actions: Sequence[LegalAction],
    inputs: CombatReplayInputs,
) -> tuple[dict[str, Any] | None, str | None]:
    # This validates the public hash and rejects privileged keys for every decision type.
    representation = build_model_input(inputs.ruleset, observation, actions)
    try:
        combat = bind_public_combat(representation, inputs.layout)
    except ValueError as error:
        return None, str(error)
    if combat is None:
        return None, None
    cards = sorted({b["card"]["card_id"] for b in combat.bindings if b["card"] is not None})
    return {
        "context": combat.context,
        "bindings": list(combat.bindings),
        "available_card_ids": cards,
        "card_ids_absent_from_fit": sorted(set(cards) - set(inputs.coverage["fitting_card_ids"])),
        "card_ids_absent_from_signal": sorted(set(cards) - set(inputs.coverage["signal_card_ids"])),
    }, None


def _prediction(
    decision: ProductionPolicyDecision, actions: Sequence[LegalAction]
) -> dict[str, Any]:
    values = list(decision.policy)
    index = decision.selected_candidate_index
    if (
        decision.source_action_ids != tuple(a.action_id for a in actions)
        or len(values) != len(actions)
        or not 0 <= index < len(actions)
        or decision.selected_action != actions[index]
        or index != max(range(len(values)), key=lambda i: (values[i], -i))
        or any(
            type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in values
        )
        or not math.isclose(sum(values), 1, abs_tol=1e-9)
    ):
        raise ValueError("Diagnostic policy prediction is not candidate aligned")
    ordered = sorted(values, reverse=True)
    return {
        "selected_index": index,
        "action_id": actions[index].action_id,
        "policy": values,
        "top_probability_gap": ordered[0] - ordered[1] if len(values) > 1 else 0,
    }


class _ReplayPolicy:
    def __init__(self, inputs: CombatReplayInputs, kind: str) -> None:
        self.inputs, self.kind = inputs, kind
        self.driver = inputs.candidate if kind == LEARNED_POLICY_KIND else inputs.reference
        self.other = inputs.reference if kind == LEARNED_POLICY_KIND else inputs.candidate
        self.policy_id = self.driver.policy_id
        self.rows: list[dict[str, Any]] = []

    def choose_action(
        self, observation: Observation, actions: Sequence[LegalAction]
    ) -> LegalAction:
        combat, binding_error = _public_combat(observation, actions, self.inputs)
        driver = self.driver.predict(observation, actions)
        predictions: dict[str, dict[str, Any] | None] = {self.kind: _prediction(driver, actions)}
        other_kind = (
            REFERENCE_POLICY_KIND if self.kind == LEARNED_POLICY_KIND else LEARNED_POLICY_KIND
        )
        shadow_error = None
        try:
            predictions[other_kind] = _prediction(self.other.predict(observation, actions), actions)
        except Exception as error:
            shadow_error = f"{type(error).__name__}: {error}"
            predictions[other_kind] = None
        self.rows.append(
            {
                "decision_index": len(self.rows),
                "observation": observation.as_dict(),
                "legal_actions": [a.as_dict() for a in actions],
                "executed_action_id": driver.selected_action.action_id,
                "predictions": predictions,
                "shadow_error": shadow_error,
                "combat": combat,
                "binding_error": binding_error,
                "transition": None,
            }
        )
        return driver.selected_action


class _ReplayEnvironment:
    def __init__(self, environment: EnvironmentAdapter, recorder: _ReplayPolicy) -> None:
        self.environment, self.recorder = environment, recorder
        self.ruleset, self.patch_id = environment.ruleset, environment.patch_id

    def reset(self, seed: int) -> Observation:
        return self.environment.reset(seed)

    def legal_actions(self) -> Sequence[LegalAction]:
        return self.environment.legal_actions()

    def step(self, action: LegalAction) -> Transition:
        transition = self.environment.step(action)
        self.recorder.rows[-1]["transition"] = transition.as_dict()
        return transition

    def clone(self, *, resample_hidden: bool, seed: int | None = None) -> Self:
        raise RuntimeError("Combat diagnosis must not clone or resample hidden state")

    def close(self) -> None:
        close = getattr(self.environment, "close", None)
        if callable(close):
            close()


def _recording_environment(
    factory: Callable[[], EnvironmentAdapter], recorder: _ReplayPolicy
) -> _ReplayEnvironment:
    return _ReplayEnvironment(factory(), recorder)


def _validate_rows(case: dict[str, Any], inputs: CombatReplayInputs) -> None:
    previous_next = None
    completed_actions = []
    terminal = victory = False
    for index, row in enumerate(case["rows"]):
        _exact_keys(
            row,
            {
                "decision_index",
                "observation",
                "legal_actions",
                "executed_action_id",
                "predictions",
                "shadow_error",
                "combat",
                "binding_error",
                "transition",
            },
            "replay row",
        )
        obs, actions = _observation(row["observation"]), _actions(row["legal_actions"])
        if (
            terminal
            or _integer(row["decision_index"], "decision index") != index
            or (previous_next is not None and previous_next != obs.as_dict())
        ):
            raise ValueError("Diagnostic public trajectory continuity differs")
        combat, binding_error = _public_combat(obs, actions, inputs)
        if (row["combat"], row["binding_error"]) != (combat, binding_error):
            raise ValueError("Saved diagnostic public combat binding differs")
        predictions = row["predictions"]
        if set(predictions) != set(KINDS) or predictions[case["policy_kind"]] is None:
            raise ValueError("Replay driver prediction is missing")
        if (
            all(value is not None for value in predictions.values())
            and row["shadow_error"] is not None
        ):
            raise ValueError("A successful shadow prediction carries a spurious error")
        for value in predictions.values():
            if value is None:
                if not isinstance(row["shadow_error"], str) or not row["shadow_error"]:
                    raise ValueError("Missing shadow prediction has no explicit error")
                continue
            _exact_keys(
                value,
                {"selected_index", "action_id", "policy", "top_probability_gap"},
                "diagnostic prediction",
            )
            selected = _integer(value["selected_index"], "selected index")
            if not 0 <= selected < len(actions):
                raise ValueError("Saved prediction index differs")
            packet = ProductionPolicyDecision(
                "",
                tuple(a.action_id for a in actions),
                selected,
                actions[selected],
                tuple(value["policy"]),
                None,
                (),
                {},
                0,
            )
            if _prediction(packet, actions) != value:
                raise ValueError("Saved policy scores or selection differ")
        driver = predictions[case["policy_kind"]]
        if driver["action_id"] != row["executed_action_id"]:
            raise ValueError("A shadow choice was executed instead of the original driver")
        transition = row["transition"]
        if transition is None:
            result = case["replay_result"]
            if index != len(case["rows"]) - 1 or not (
                result["status"] == "failed" or result["compute"]["budget_exhausted"]
            ):
                raise ValueError("Only a failed or CPU-capped final step may have no transition")
            continue
        _exact_keys(
            transition,
            {"observation", "action", "next_observation", "reward", "terminal", "victory"},
            "public replay transition",
        )
        if (
            transition["observation"] != obs.as_dict()
            or transition["action"] != actions[driver["selected_index"]].as_dict()
            or type(transition["terminal"]) is not bool
            or type(transition["victory"]) is not bool
        ):
            raise ValueError("Diagnostic transition does not execute its recorded public choice")
        next_obs = _observation(transition["next_observation"])
        build_model_input(inputs.ruleset, next_obs, ())
        Transition(
            obs,
            actions[driver["selected_index"]],
            next_obs,
            transition["reward"],
            transition["terminal"],
            transition["victory"],
        )
        previous_next = next_obs.as_dict()
        completed_actions.append(row["executed_action_id"])
        terminal, victory = transition["terminal"], transition["victory"]
    result = case["replay_result"]
    if (
        len(completed_actions) != result["activity"]["completed_transitions"]
        or len(case["rows"]) > result["activity"]["attempted_decisions"]
    ):
        raise ValueError("Replay rows do not reconcile with partial work counters")
    if result["status"] == "completed":
        digest = "sha256:" + hashlib.sha256("\n".join(completed_actions).encode()).hexdigest()
        if (
            len(completed_actions) != result["decisions"]
            or digest != result["action_trace_sha256"]
            or (
                previous_next is not None
                and previous_next["state_hash"] != result["final_state_hash"]
            )
            or (
                completed_actions
                and (
                    terminal != result["compute"]["observed_terminal"]
                    or victory != result["compute"]["observed_victory"]
                )
            )
        ):
            raise ValueError("Replay rows do not reconcile with their final action digest/state")


def _validate_case(
    case: dict[str, Any], inputs: CombatReplayInputs, expected: dict[str, Any]
) -> None:
    _exact_keys(
        case,
        {
            "schema_version",
            "case_id",
            "config_id",
            "seed",
            "policy_kind",
            "source_case_id",
            "replay_result",
            "rows",
            "semantic_matches",
            "mismatched_fields",
        },
        "combat replay case",
    )
    _identified(case, "case_id")
    if (
        case["schema_version"] != CASE_SCHEMA
        or case["config_id"] != inputs.config.document["config_id"]
        or case["source_case_id"] != expected["case_id"]
        or (case["seed"], case["policy_kind"]) != (expected["seed"], expected["policy_kind"])
    ):
        raise ValueError("Diagnostic case source binding differs")
    result = case["replay_result"]
    _identified(result, "case_id")
    _validate_fresh_case(result, inputs.confirmation)
    if result["schema_version"] != FRESH_PRODUCTION_POLICY_CASE_SCHEMA_VERSION:
        raise ValueError("Diagnostic replay needs the current outcome accounting schema")
    for field in ("seed", "policy_kind", "policy_id", "model_id", "ruleset_manifest_id"):
        if result[field] != expected[field]:
            raise ValueError("Diagnostic replay result belongs to another source")
    different = [key for key in SEMANTIC_FIELDS if result[key] != expected[key]]
    matches = not different
    if case["semantic_matches"] is not matches or case["mismatched_fields"] != different:
        raise ValueError("Diagnostic source reconciliation differs")
    if not isinstance(case["rows"], list):
        raise ValueError("Diagnostic decision rows are missing")
    _validate_rows(case, inputs)


def _first_difference(candidate: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    for c, r in zip(candidate["rows"], reference["rows"], strict=False):
        index = c["decision_index"]
        if c["observation"] != r["observation"] or c["legal_actions"] != r["legal_actions"]:
            return {
                "kind": "environment_or_menu_divergence_before_action_difference",
                "decision_index": index,
            }
        if c["predictions"] != r["predictions"]:
            return {
                "kind": "inconsistent_shadow_scores_on_identical_input",
                "decision_index": index,
            }
        if c["executed_action_id"] != r["executed_action_id"]:
            return {
                "kind": "aligned_policy_action_difference",
                "decision_index": index,
                "state_hash": c["observation"]["state_hash"],
                "decision_type": c["observation"]["decision_type"],
                "candidate_action_id": c["executed_action_id"],
                "reference_action_id": r["executed_action_id"],
            }
        if c["transition"] != r["transition"]:
            return {
                "kind": "environment_or_menu_divergence_before_action_difference",
                "decision_index": index,
            }
    if len(candidate["rows"]) != len(reference["rows"]):
        return {"kind": "length_divergence_without_prior_action_difference", "decision_index": None}
    return {"kind": "identical_public_action_trajectory", "decision_index": None}


def _death_evidence(case: dict[str, Any]) -> dict[str, Any]:
    combat_rows = [r for r in case["rows"] if r["combat"] is not None]
    fatal = next((r for r in reversed(case["rows"]) if r["transition"] is not None), None)
    before_hp = after_hp = None
    if fatal is not None and fatal["combat"] is not None:
        before_hp = fatal["combat"]["context"]["player"]["hp"]
        vector = fatal["transition"]["next_observation"]["public_state"].get("observation_vector")
        if isinstance(vector, list) and vector and type(vector[0]) is int:
            after_hp = vector[0]
    return {
        "last_combat_decision_indices": [r["decision_index"] for r in combat_rows[-8:]],
        "last_completed_decision_index": fatal["decision_index"] if fatal else None,
        "last_completed_decision_type": fatal["observation"]["decision_type"] if fatal else None,
        "last_completed_action_id": fatal["executed_action_id"] if fatal else None,
        "terminal_defeat": bool(
            fatal and fatal["transition"]["terminal"] and not fatal["transition"]["victory"]
        ),
        "player_hp_before_last_transition": before_hp,
        "player_hp_after_last_transition": after_hp,
        "last_transition_hp_change": after_hp - before_hp
        if before_hp is not None and after_hp is not None
        else None,
    }


def _summarize(cases: Sequence[dict[str, Any]], inputs: CombatReplayInputs) -> dict[str, Any]:
    result: dict[str, Any] = {
        "case_denominator": len(inputs.cases),
        "verified_replays": sum(c["semantic_matches"] for c in cases),
        "mismatched_replays": sum(not c["semantic_matches"] for c in cases),
        "failed_replays": sum(c["replay_result"]["status"] == "failed" for c in cases),
        "arms": {},
        "pairs": [],
    }
    for kind in KINDS:
        verified = [c for c in cases if c["policy_kind"] == kind and c["semantic_matches"]]
        rows = [row for c in verified for row in c["rows"]]
        disagreements: Counter[str] = Counter()
        swaps: Counter[str] = Counter()
        noncombat_drift = shadow_failures = binding_failures = end_with_options = 0
        combat_states = uncovered_fit_states = uncovered_signal_states = fatal_end_turns = 0
        for row in rows:
            p, r = (row["predictions"][k] for k in KINDS)
            binding_failures += row["binding_error"] is not None
            if p is None or r is None:
                shadow_failures += 1
            else:
                phase = row["observation"]["decision_type"]
                if phase != "combat" and p["policy"] != r["policy"]:
                    noncombat_drift += 1
                if p["action_id"] != r["action_id"]:
                    disagreements[phase] += 1
                    if row["combat"] is not None:
                        b = row["combat"]["bindings"]
                        swaps[
                            f"{b[r['selected_index']]['kind']} -> {b[p['selected_index']]['kind']}"
                        ] += 1
            combat = row["combat"]
            if combat is None:
                continue
            combat_states += 1
            uncovered_fit_states += bool(combat["card_ids_absent_from_fit"])
            uncovered_signal_states += bool(combat["card_ids_absent_from_signal"])
            chosen = combat["bindings"][row["predictions"][kind]["selected_index"]]
            if chosen["kind"] == "end_turn":
                end_with_options += any(
                    b["kind"] in ("play_card", "use_potion") for b in combat["bindings"]
                )
                fatal_end_turns += bool(
                    row["transition"]
                    and row["transition"]["terminal"]
                    and not row["transition"]["victory"]
                )
        result["arms"][kind] = {
            "verified_replays": len(verified),
            "decisions": len(rows),
            "combat_states": combat_states,
            "shadow_failures": shadow_failures,
            "binding_failures": binding_failures,
            "noncombat_score_drift_states": noncombat_drift,
            "choice_disagreements_by_phase": dict(sorted(disagreements.items())),
            "reference_to_candidate_combat_kind_changes": dict(sorted(swaps.items())),
            "end_turn_with_legal_card_or_potion_states": end_with_options,
            "terminal_defeats_after_end_turn": fatal_end_turns,
            "states_with_cards_absent_from_fit": uncovered_fit_states,
            "states_with_cards_absent_from_reliable_signal": uncovered_signal_states,
        }
    by_coordinate = {(c["seed"], c["policy_kind"]): c for c in cases}
    for seed in inputs.confirmation.document["seeds"]:
        c, r = (by_coordinate[seed, kind] for kind in KINDS)
        first = (
            _first_difference(c, r)
            if c["semantic_matches"] and r["semantic_matches"]
            else {"kind": "unverified_replay_pair", "decision_index": None}
        )
        result["pairs"].append(
            {
                "seed": seed,
                "first_difference": first,
                "saved_maximum_floor_difference": inputs.cases[seed, LEARNED_POLICY_KIND][
                    "maximum_floor"
                ]
                - inputs.cases[seed, REFERENCE_POLICY_KIND]["maximum_floor"],
                "candidate_death_evidence": _death_evidence(c) if c["semantic_matches"] else None,
                "reference_death_evidence": _death_evidence(r) if r["semantic_matches"] else None,
            }
        )
    result["analysis_integrity_pass"] = (
        result["verified_replays"] == len(inputs.cases)
        and all(
            arm["noncombat_score_drift_states"] == 0
            and arm["shadow_failures"] == 0
            and arm["binding_failures"] == 0
            for arm in result["arms"].values()
        )
        and all(
            p["first_difference"]["kind"]
            in ("aligned_policy_action_difference", "identical_public_action_trajectory")
            for p in result["pairs"]
        )
    )
    return result


def _publish_case(path: Path, case: dict[str, Any]) -> None:
    """Keep full public traces compact; preserve atomic, immutable publication."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".combat-diagnostic-", dir=path.parent) as staging:
        temporary = Path(staging) / "complete.json"
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(case, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)


def run_combat_replay(
    *,
    inputs: CombatReplayInputs,
    environment_factory: Callable[[], EnvironmentAdapter],
    output_directory: Path,
    resume: bool = False,
    progress: Callable[[int, int], None] | None = None,
    activity: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    _validate_inputs(inputs)
    if output_directory.exists() and not resume:
        raise FileExistsError(
            "Diagnostic output exists; use resume or display its completed result"
        )
    report_path = output_directory / "diagnostic.json"
    if report_path.exists():
        raise FileExistsError("Diagnostic is complete; display its saved result")
    plan = output_directory / "diagnostic-plan.json"
    if plan.exists():
        if json.loads(plan.read_text()) != inputs.config.document:
            raise ValueError("Resumed diagnostic plan differs")
    elif any((output_directory / "cases").glob("*.json")):
        raise ValueError("Existing diagnostic cases have no frozen plan")
    else:
        _publish_json(plan, inputs.config.document)
    cases, new_runs, new_transitions = [], 0, 0
    for seed in inputs.confirmation.document["seeds"]:
        for kind in KINDS:
            expected = inputs.cases[seed, kind]
            _identified(expected, "case_id")
            path = output_directory / "cases" / f"seed-{seed:06d}-{kind}.json"
            if path.exists():
                case = json.loads(path.read_text())
                _validate_case(case, inputs, expected)
            else:
                recorder = _ReplayPolicy(inputs, kind)
                replay = _evaluate_case(
                    environment_factory=partial(
                        _recording_environment, environment_factory, recorder
                    ),
                    ruleset=inputs.ruleset,
                    seed=seed,
                    policy_kind=kind,
                    policy=recorder,
                    model_id=expected["model_id"],
                    maximum_decisions=inputs.confirmation.document["maximum_decisions_per_run"],
                    partition=SplitName.TRAIN,
                    cycle_repetition_threshold=inputs.confirmation.document[
                        "cycle_repetition_threshold"
                    ],
                    liveness_tail_length=inputs.confirmation.document["liveness_tail_length"],
                    no_op_fallback_threshold=inputs.confirmation.document[
                        "no_op_fallback_threshold"
                    ],
                    schema_version=FRESH_PRODUCTION_POLICY_CASE_SCHEMA_VERSION,
                    confirmation=inputs.confirmation,
                )
                differing = [key for key in SEMANTIC_FIELDS if replay[key] != expected[key]]
                body = {
                    "schema_version": CASE_SCHEMA,
                    "config_id": inputs.config.document["config_id"],
                    "seed": seed,
                    "policy_kind": kind,
                    "source_case_id": expected["case_id"],
                    "replay_result": replay,
                    "rows": recorder.rows,
                    "semantic_matches": not differing,
                    "mismatched_fields": differing,
                }
                case = {**body, "case_id": manifest_identifier(body)}
                new_runs += 1
                new_transitions += replay["activity"]["completed_transitions"]
                if activity:
                    activity(new_runs, new_transitions)
                _validate_case(case, inputs, expected)
                _publish_case(path, case)
            cases.append(case)
            if progress:
                progress(len(cases), len(inputs.cases))
    body = {
        "schema_version": REPORT_SCHEMA,
        "config": inputs.config.document,
        "confirmation_config_id": inputs.confirmation.document["config_id"],
        "comparison_report_id": inputs.comparison["report_id"],
        "coverage": inputs.coverage,
        "cases": [
            {
                "seed": c["seed"],
                "policy_kind": c["policy_kind"],
                "path": f"cases/seed-{c['seed']:06d}-{c['policy_kind']}.json",
                "case_id": c["case_id"],
            }
            for c in cases
        ],
        "summary": _summarize(cases, inputs),
        "claim_scope": CLAIM,
        "decision": {
            "checkpoint_promoted": False,
            "foundation_ready": False,
            "adaptive_controller_allowed": False,
            "next_step": "review_public_choice_evidence_before_any_new_experiment",
        },
    }
    report = {**body, "report_id": manifest_identifier(body)}
    _publish_json(report_path, report)
    return report


def load_combat_replay_report(path: Path, inputs: CombatReplayInputs) -> dict[str, Any]:
    _validate_inputs(inputs)
    report = _mapping(json.loads(path.read_text()), "combat replay report")
    _identified(report, "report_id")
    _exact_keys(
        report,
        {
            "schema_version",
            "report_id",
            "config",
            "confirmation_config_id",
            "comparison_report_id",
            "coverage",
            "cases",
            "summary",
            "claim_scope",
            "decision",
        },
        "combat replay report",
    )
    if (
        report["schema_version"] != REPORT_SCHEMA
        or report["config"] != inputs.config.document
        or report["confirmation_config_id"] != inputs.confirmation.document["config_id"]
        or report["comparison_report_id"] != inputs.comparison["report_id"]
        or report["coverage"] != inputs.coverage
        or report["claim_scope"] != CLAIM
        or json.loads((path.parent / "diagnostic-plan.json").read_text()) != inputs.config.document
        or report["decision"]
        != {
            "checkpoint_promoted": False,
            "foundation_ready": False,
            "adaptive_controller_allowed": False,
            "next_step": "review_public_choice_evidence_before_any_new_experiment",
        }
    ):
        raise ValueError("Saved combat diagnostic source/protocol/decision differs")
    cases, coordinates = [], set()
    for ref in report["cases"]:
        _exact_keys(ref, {"seed", "policy_kind", "path", "case_id"}, "diagnostic case reference")
        key = (ref["seed"], ref["policy_kind"])
        if key in coordinates or key not in inputs.cases:
            raise ValueError("Diagnostic case coverage differs")
        coordinates.add(key)
        case = json.loads(_safe_child(path.parent.resolve(), ref["path"]).read_text())
        _validate_case(case, inputs, inputs.cases[key])
        if ref["case_id"] != case["case_id"]:
            raise ValueError("Diagnostic case reference differs")
        cases.append(case)
    if coordinates != set(inputs.cases) or report["summary"] != _summarize(cases, inputs):
        raise ValueError("Diagnostic denominator or recomputed summary differs")
    return report
