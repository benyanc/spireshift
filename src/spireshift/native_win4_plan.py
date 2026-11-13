"""One atomic answer with conditional policy factors and one native commit.

Public prefixes are internal answer construction, never new game decisions or
standalone labels. Delivered-only persistent policy memory commits at completion.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.native_flow_verification_v12 import records
from spireshift.native_live_policy import LivePolicy

PLAN = "factorized_ordered_card_answer_v1"


class AnswerPolicy:
    def __init__(self, core: LivePolicy) -> None:
        self.failed = False
        self.core = core
        self.model = core.model
        self.trial: LivePolicy | None = None
        self.answer_id: str | None = None
        self.factor = 0
        self.joint_logp = 0.0
        self.decisions = 0
        self.local_factors = 0
        self.expected_domain: str | None = None

    @property
    def planning(self) -> bool:
        return self.trial is not None

    @property
    def pending(self) -> Any:
        return self.trial if self.trial is not None else self.core.pending

    def choose(self, frame: dict[str, Any]) -> dict[str, Any]:
        surface = frame["public_input"]["context"]["interaction"]["content"].get("surface", {})
        compact = surface.get("selection_contract") == PLAN
        if self.failed or self.expected_domain is not None:
            raise ValueError("An uncertain answer factor cannot be retried")
        if not compact:
            if self.planning:
                raise ValueError("Uncommitted answer lost its public owner")
            self.expected_domain = "native"
            return self.core.choose(frame)
        prefix = surface["answer_plan"]["selected"]
        if self.trial is None:
            if prefix:
                raise ValueError("Cannot resume an uncommitted answer prefix")
            self.trial = copy.deepcopy(
                self.core,
                {id(self.core.model): self.core.model, id(self.core.score): self.core.score},
            )
            self.answer_id = manifest_identifier({"atomic_answer_origin": frame["binding_id"]})
            self.factor = 0
            self.joint_logp = 0.0
        if len(prefix) != self.factor:
            raise ValueError("Answer factors must follow the exact public prefix")
        choice = self.trial.choose(frame)
        verb = frame["public_input"]["candidates"][choice["action_index"]]["verb"]
        if verb not in {"select", "confirm", "cancel"}:
            if self.factor:
                raise ValueError("Foreign action inside conditional answer grammar")
            # Belt actions stay available at the root, before any answer factor.
            self.expected_domain = "native"
            return choice
        complete = verb in {"confirm", "cancel"}
        self.expected_domain = "native" if complete else "local_answer_factor"
        self.joint_logp += float(choice["log_probability"])
        return {
            **choice,
            "answer_plan": {
                "contract": PLAN,
                "answer_id": self.answer_id,
                "factor_index": self.factor,
                "complete": complete,
                "joint_behavior_log_probability": self.joint_logp,
                "standalone_game_decision": False,
            },
        }

    def acknowledge(self, receipt: dict[str, Any]) -> None:
        if (
            self.failed
            or receipt.get("delivery_domain") != self.expected_domain
            or self.expected_domain is None
        ):
            self.failed = True
            raise ValueError("Local answer factors and native deliveries cannot be interchanged")
        if self.trial is None:
            self.core.acknowledge(receipt)
            self.decisions += 1
        else:
            self.trial.acknowledge(receipt)
            if self.expected_domain == "local_answer_factor":
                self.factor += 1
                self.local_factors += 1
            else:
                self.core, self.trial = self.trial, None
                self.answer_id = None
                self.decisions += 1
        self.expected_domain = None


def steps(root: Path, value: dict[str, Any]) -> list[dict[str, Any]]:
    """Group every answer's factors as one label; never inflate meaningful choices."""
    result: list[dict[str, Any]] = []
    frame = None
    group: list[dict[str, Any]] = []
    group_id = None
    index = 0
    for row in records(root / value["episode_directory"] / "shared-public.jsonl.gz"):
        if row["kind"] == "policy_input":
            if frame is not None:
                raise ValueError("Missing prior choice")
            frame = row["frame"]
        elif row["kind"] == "policy_choice":
            if frame is None:
                raise ValueError("A label preceded its public factor")
            choice = row["choice"]
            factor = choice.get("answer_plan")
            label = {
                "public_input": frame["public_input"],
                "public_input_id": manifest_identifier(frame["public_input"]),
                "action_index": choice["action_index"],
                "family": frame["source_family"],
            }
            if factor:
                if factor["contract"] != PLAN or row["receipt"].get("delivery_domain") != (
                    "native" if factor["complete"] else "local_answer_factor"
                ):
                    raise ValueError("Atomic labels require the exact final native delivery")
                if factor["factor_index"] != len(group) or (
                    group and group_id != factor["answer_id"]
                ):
                    raise ValueError("Truncated or cross-answer fitting factors")
                group_id = factor["answer_id"]
                group.append(label)
                if factor["complete"]:
                    if len(group[0]["public_input"]["candidates"]) > 1:
                        result.append(
                            {
                                "family": label["family"],
                                "decision_index": index,
                                "decision_contract": PLAN,
                                "answer_factors": group,
                                "label_weight": 1.0,
                            }
                        )
                    group, group_id = [], None
                    index += 1
            else:
                if group:
                    raise ValueError("Unfinished answer cannot supply any labels")
                if not choice["navigation_only"] and len(frame["actions"]) > 1:
                    result.append({**label, "decision_index": index})
                index += 1
            frame = None
    if frame is not None or group:
        raise ValueError("An incomplete answer supplies no labels")
    return result
