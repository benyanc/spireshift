"""Fresh public root sampling and complete turns with matched greedy continuation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.native_combat_behavior_policy import CONTRACT as BEHAVIOR
from spireshift.native_combat_behavior_policy import Chooser
from spireshift.native_combat_teacher_data import INFORMATION
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_later_teacher_roots import SELECTION, eligibility
from spireshift.native_turn_teacher_policy import TurnChooser, boundary
from spireshift.training_objective import TrainingScoreSpec

CONTRACT = "native_fresh_train_complete_turn_greedy_continuation_v1"
ROOT_SELECTION = "first_eligible_public_later_combat_in_manifest_order_no_replacement_v1"


def continuation_seed(root_id: str, repeat: int) -> str:
    if type(repeat) is not int or not 0 <= repeat < 8:
        raise ValueError("Declare a finite matched noncombat continuation stream")
    return f"native-greedy-turn-v1|{root_id}|noncombat|{repeat}"


class SourceChooser:
    """Seal the first eligible public root before the source game's later outcomes."""

    def __init__(
        self,
        seed: dict[str, Any],
        model: CachedContextModel,
        score: TrainingScoreSpec,
        on_root: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.seed, self.model, self.on_root = seed, model, on_root
        self.behavior = Chooser(model, score, seed["seed"], "greedy")
        self.prefix: list[dict[str, Any]] = []
        self.index = 0
        self.root: dict[str, Any] | None = None

    def __call__(self, public: dict[str, Any]) -> dict[str, Any]:
        selected = self.behavior(public)
        evidence = eligibility(public) if self.root is None and self.index <= 512 else None
        if evidence is not None:
            body = {
                "schema_version": "native-greedy-turn-public-root-v1",
                "source_key": f"source-{self.seed['id']}",
                "source_seed_id": self.seed["id"],
                "native_seed": self.seed["seed"],
                "numerical_seed": self.seed["numerical_seed"],
                "model_id": self.model.model_id,
                "public_input": public,
                "public_input_id": manifest_identifier(public),
                "prefix": list(self.prefix),
                "decision_index": self.index,
                "reference_action": selected["action_index"],
                "root_selection": ROOT_SELECTION,
                "eligibility_contract": SELECTION,
                "selection_evidence": evidence,
                "selection_uses_final_outcomes": False,
                "information_scope": INFORMATION,
                "ordinary_PPO_eligible": False,
            }
            self.root = {**body, "root_id": manifest_identifier(body)}
            if self.on_root is not None:
                self.on_root(self.root)
        if self.root is None and self.index < 512:
            self.prefix.append(
                {
                    "public_input_id": selected["public_input_id"],
                    "action_index": selected["action_index"],
                }
            )
        self.index += 1
        return {
            **selected,
            "policy_contract": CONTRACT,
            "continuation_policy_contract": BEHAVIOR,
            "teacher_phase": "fresh_natural_source",
        }


class GreedyTurnChooser(TurnChooser):
    """Reuse frozen turn generation/replay, replacing only its continuation policy.

    Prefix and proposed-turn actions update public ownership/navigation but consume
    no continuation draws. Room/family slots isolate later noncombat choices from
    different combat lengths, while repeat changes only the noncombat random seed.
    """

    def __init__(
        self,
        root: dict[str, Any],
        model: CachedContextModel,
        score: TrainingScoreSpec,
        *,
        first_action: int | None,
        repeat: int,
        plan: dict[str, Any] | None = None,
        on_plan: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        super().__init__(
            root,
            model,
            score,
            first_action=first_action,
            repeat=repeat,
            temperature=0.8,
            proposal_temperature=1.2,
            plan=plan,
            on_plan=on_plan,
        )
        self.behavior = Chooser(model, score, continuation_seed(root["root_id"], repeat), "greedy")
        self.behavior.navigation = self.navigation

    def __call__(self, public: dict[str, Any]) -> dict[str, Any]:
        # Keep native ownership through forced prefixes and end-turn nested menus.
        self.behavior.combat(public)
        if self.index >= len(self.root["prefix"]) and self.root_reached and not self.turn_complete:
            end = boundary(self.root["public_input"], public, end_turn_sent=self.end_turn_sent)
            if end is not None:
                self._freeze(end)
        if self.turn_complete:
            self.index += 1
            return {
                **self.behavior(public),
                "policy_contract": CONTRACT,
                "continuation_policy_contract": BEHAVIOR,
                "teacher_phase": "greedy_combat_matched_noncombat_continuation",
            }
        return {**super().__call__(public), "policy_contract": CONTRACT}


def reconstruct(
    case: dict[str, Any],
    task: dict[str, Any],
    model: CachedContextModel,
    score: TrainingScoreSpec,
    root: dict[str, Any] | None,
    plan: dict[str, Any] | None,
) -> dict[str, Any]:
    if (
        case["status"] != "terminal"
        or case["seed"] != task["seed"]["seed"]
        or case.get("recovered") is not False
        or case.get("privileged_fixture") is not False
        or case.get("native_ending_evidence_agrees") is not True
        or case.get("policy_contract") != CONTRACT
        or case.get("ordinary_PPO_eligible") is not False
        or case.get("privileged_fixed_world_teacher") is not (task["stage"] != "source")
        or case.get("student_inputs_public_only") is not True
    ):
        raise ValueError("Only clean explicitly scoped fixed-world teacher records may reconstruct")
    chooser: SourceChooser | GreedyTurnChooser = (
        SourceChooser(task["seed"], model, score)
        if task["stage"] == "source"
        else GreedyTurnChooser(
            root if root is not None else {},
            model,
            score,
            first_action=task["first_action"],
            repeat=task["repeat"],
            plan=plan if task["stage"] == "comparison" else None,
        )
    )
    noncombat: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for row in case["decisions"]:
        expected, saved = chooser(row["public_input"]), row["choice"]
        if expected != saved:
            raise ValueError("Saved greedy-turn action, probability, ownership or draw differs")
        phase = saved["teacher_phase"]
        counts[phase] = counts.get(phase, 0) + 1
        if saved.get("behavior") == "sampled_noncombat":
            noncombat.append(
                {
                    k: saved[k]
                    for k in (
                        "draw_key",
                        "draw",
                        "effective_input_id",
                        "action_index",
                        "policy_log_probability",
                    )
                }
            )
    if isinstance(chooser, SourceChooser):
        if chooser.root != root:
            raise ValueError("The first public source root or no-root outcome changed")
    else:
        chooser.finish(case)
        if not chooser.root_reached or not chooser.turn_complete or chooser.plan != plan:
            raise ValueError("Frozen turn or complete boundary did not exactly reconstruct")
    return {
        "decisions_reconstructed": len(case["decisions"]),
        "counts": counts,
        "noncombat": noncombat,
    }
