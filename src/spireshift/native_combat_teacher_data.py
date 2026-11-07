"""Fixed-world native counterfactual lessons, explicitly separate from on-policy PPO.

Student inputs are public. The teacher replays one original native hidden world;
replicates sample continuation-policy actions, not independent hidden draw orders.
"""

from __future__ import annotations

import hashlib
import math
import random
import statistics
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import validate_public_input
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_rest_exploration import choose
from spireshift.native_shop_policy import ShopNavigation
from spireshift.training_objective import TrainingScoreSpec

CONTRACT = "native_fixed_world_combat_comparison_v1"
INFORMATION = "public_student_inputs_original_fixed_hidden_world_teacher"


def prefix_root(case: dict[str, Any], binding: dict[str, Any], index: int) -> dict[str, Any]:
    if (
        binding.get("partition") != "train"
        or binding.get("panel_purpose") != "training"
        or case.get("status") != "terminal"
        or case.get("recovered") is not False
        or case.get("privileged_fixture") is not False
        or case.get("native_ending_evidence_agrees") is not True
        or case.get("seed") != binding.get("native_seed")
        or type(index) is not int
        or not 0 <= index < len(case["decisions"])
    ):
        raise ValueError("Native teacher roots require sealed natural terminal TRAIN records")
    row = case["decisions"][index]
    public = row["public_input"]
    validate_public_input(public)
    if row["choice"].get("public_input_id") != manifest_identifier(public):
        raise ValueError("Source root does not bind its public observation")
    if (
        public["context"]["interaction"]["kind"] != "combat_turn"
        or not 2 <= len(public["candidates"]) <= 12
    ):
        raise ValueError("Freeze a complete 2–12-action native combat root")
    prefix = []
    for previous in case["decisions"][:index]:
        identity = manifest_identifier(previous["public_input"])
        if previous["choice"].get("public_input_id") != identity:
            raise ValueError("Source prefix does not bind its public observations")
        prefix.append(
            {"public_input_id": identity, "action_index": previous["choice"]["action_index"]}
        )
    return {
        "public_input": public,
        "public_input_id": manifest_identifier(public),
        "prefix": prefix,
    }


def sampling_seed(root_id: str, repeat: int) -> int:
    if type(repeat) is not int or repeat < 0:
        raise ValueError("Use a declared nonnegative continuation replicate")
    return int.from_bytes(
        hashlib.sha256(f"native-combat-teacher-v1|{root_id}|{repeat}".encode()).digest()[:8], "big"
    )


class ReplayChooser:
    def __init__(
        self,
        root: dict[str, Any],
        action: int,
        repeat: int,
        model: CachedContextModel,
        score: TrainingScoreSpec,
        temperature: float,
    ) -> None:
        if type(action) is not int or not 0 <= action < len(root["public_input"]["candidates"]):
            raise ValueError("Teacher intervention is outside the complete public menu")
        self.root, self.action, self.model, self.score = root, action, model, score
        self.temperature = temperature
        self.rng = random.Random(sampling_seed(root["root_id"], repeat))
        self.navigation = ShopNavigation()
        self.index = 0
        self.root_reached = False
        self.root_successor_kind: str | None = None

    def __call__(self, public: dict[str, Any]) -> dict[str, Any]:
        identity = manifest_identifier(public)
        index = self.index
        self.index += 1
        if index < len(self.root["prefix"]):
            saved = self.root["prefix"][index]
            if saved["public_input_id"] != identity:
                raise ValueError(f"Teacher public prefix mismatch at decision {index}")
            action, phase = saved["action_index"], "verified_source_prefix"
        elif index == len(self.root["prefix"]):
            if identity != self.root["public_input_id"] or public != self.root["public_input"]:
                raise ValueError("Teacher public root mismatch")
            self.root_reached = True
            action, phase = self.action, "forced_counterfactual_root"
        else:
            if self.root_successor_kind is None:
                self.root_successor_kind = public["context"]["interaction"]["kind"]
            selected = choose(
                self.model, self.score, public, self.navigation, self.rng, self.temperature, 0.0
            )
            return {
                **selected,
                "policy_contract": CONTRACT,
                "teacher_phase": "public_policy_continuation",
                "ordinary_PPO_eligible": False,
            }
        if type(action) is not int or not 0 <= action < len(public["candidates"]):
            raise ValueError("Teacher prefix action is no longer advertised")
        self.navigation.advance(public, action)
        return {
            "action_index": action,
            "public_input_id": identity,
            "policy_contract": CONTRACT,
            "teacher_phase": phase,
            "ordinary_PPO_eligible": False,
        }


def trace_id(case: dict[str, Any]) -> str:
    return manifest_identifier(
        {
            "decisions": [
                (manifest_identifier(d["public_input"]), d["choice"]["action_index"])
                for d in case["decisions"]
            ],
            "terminal_public_key": case.get("terminal_public_key"),
            "status": case["status"],
            "victory": case["victory"],
        }
    )


def sign_probability(positive: int, negative: int) -> float:
    """Exact one-sided paired sign test; ties excluded, not a test of mean return."""
    if any(type(v) is not int or v < 0 for v in (positive, negative)):
        raise ValueError("Sign counts must be nonnegative integers")
    n = positive + negative
    if not n:
        return 1.0
    return float(sum(math.comb(n, k) for k in range(positive, n + 1)) / 2**n)


def lesson(root: dict[str, Any], results: list[dict[str, Any]], repeats: int) -> dict[str, Any]:
    if type(repeats) is not int or not 1 <= repeats <= 32:
        raise ValueError("Freeze a finite number of teacher policy streams")
    n = len(root["public_input"]["candidates"])
    expected = {(a, r) for a in range(n) for r in range(repeats)}
    cells = {(x["action"], x["repeat"]): x for x in results if not x.get("duplicate_control")}
    if len(cells) != len([x for x in results if not x.get("duplicate_control")]):
        raise ValueError("Teacher comparison repeats a planned action/stream cell")
    for (action, repeat), cell in cells.items():
        if type(action) is not int or type(repeat) is not int or (action, repeat) not in expected:
            raise ValueError("Teacher outcome belongs to an unplanned action/stream")
        if cell["status"] == "terminal" and (
            type(cell.get("training_return")) not in (float, int)
            or not math.isfinite(cell["training_return"])
            or not 0 <= cell["training_return"] <= 1
        ):
            raise ValueError("Teacher outcome has an invalid declared return")
    complete = set(cells) == expected and all(
        x["status"] == "terminal" and x["root_reached"] and x["native_audit_valid"]
        for x in cells.values()
    )
    summaries, preferences = [], []
    if complete:
        baseline = root["reference_action"]
        for action in range(n):
            own = [cells[action, r] for r in range(repeats)]
            values = [x["training_return"] for x in own]
            summaries.append(
                {
                    "action_index": action,
                    "samples": repeats,
                    "full_run_wins": sum(x["victory"] for x in own),
                    "mean_bootstrap_return": statistics.fmean(values),
                    "return_standard_error": statistics.stdev(values) / math.sqrt(repeats)
                    if repeats > 1
                    else None,
                    "mean_maximum_floor": statistics.fmean(x["maximum_floor"] for x in own),
                    "independent_hidden_worlds": 1,
                }
            )
            if action == baseline:
                continue
            differences = [
                cells[action, r]["training_return"] - cells[baseline, r]["training_return"]
                for r in range(repeats)
            ]
            positive, negative = (
                sum(v > 1e-12 for v in differences),
                sum(v < -1e-12 for v in differences),
            )
            p = sign_probability(positive, negative)
            wins = sum(x["victory"] for x in own)
            base_wins = sum(cells[baseline, r]["victory"] for r in range(repeats))
            admitted = (
                repeats >= 8
                and statistics.fmean(differences) > 0
                and p <= 0.05 / (n - 1)
                and wins >= base_wins
            )
            preferences.append(
                {
                    "preferred_action": action,
                    "reference_action": baseline,
                    "mean_bootstrap_return_difference": statistics.fmean(differences),
                    "positive_pairs": positive,
                    "negative_pairs": negative,
                    "tied_pairs": repeats - positive - negative,
                    "one_sided_sign_p": p,
                    "within_root_threshold": 0.05 / (n - 1),
                    "admitted_exploratory_preference": admitted,
                    "label_kind": "terminal_victory_evidence"
                    if wins > base_wins
                    else "auxiliary_bootstrap_only",
                }
            )
    return {
        "root_id": root["root_id"],
        "public_input": root["public_input"],
        "public_input_id": root["public_input_id"],
        "comparison_complete": complete,
        "actions": summaries,
        "preferences": preferences,
        "eligible_for_experimental_value_supervision": complete and repeats >= 8,
        "information_scope": INFORMATION,
        "privileged_fixed_world_teacher": True,
        "student_inputs_public_only": True,
        "ordinary_PPO_eligible": False,
        "public_belief_search_eligible": False,
        "optimal_native_action_established": False,
        "uncertainty_scope": (
            "continuation_policy_sampling_conditional_on_one_original_hidden_world"
        ),
        "preference_test": "paired_outperformance_sign_test_not_expected_return_test",
        "multiple_comparisons": "Bonferroni_alternatives_vs_frozen_reference_within_each_root_only",
        "zero_observed_variance_is_not_hidden_world_certainty": True,
    }
