"""Withhold model-owned actions already shown to return to an identical public state.

The saved effect-free cycle scan (docs/native-effect-free-cycles-v1.md) found
that full-menu policies repeat UI round trips: shop inventory open/close, card
reward claim/skip, rest Smith/cancel and merchant removal/cancel. None of them
changes any player-visible state. Every legal native choice stays on offer
until the model has taken it from an identical public input (same
``public_input_id``) and the run came back to exactly that input. After that,
the same action from the same input is withheld, because it can only reach
states the model already had and left. Any public change produces a new input
id, which restores the full menu. If every candidate would be withheld, the
full menu is kept.

The guard uses only the public inputs the policy already saw and its own
delivered choices. It reads no hidden or native-only state. Execution, the
saved journal, the raw native verifier and the historical recipes are
unchanged; new recipes opt in through ``using_cycle_guard``.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_head_policy, native_a8_own_experience, native_a8_own_policy
from spireshift.core.manifest import manifest_identifier
from spireshift.native_a8_own_policy import AllActions, OwnPolicy
from spireshift.native_a8_rescue_game import TRACE, decisions, receipt
from spireshift.native_flow_verification_v12 import records
from spireshift.native_live_policy import LivePolicy
from spireshift.native_win4_plan import PLAN

CONTRACT = "native_a8_all_actions_effect_free_cycle_guard_v1"


def candidate_key(candidate: dict[str, Any]) -> str:
    return manifest_identifier(candidate)


class CycleGuard(AllActions):
    """Public-only memory of effect-free round trips within one game."""

    def __init__(self) -> None:
        super().__init__()
        self.taken: dict[str, set[str]] = {}
        self.withheld: dict[str, set[str]] = {}
        self.current: str | None = None

    def view(self, public: dict[str, Any]) -> tuple[dict[str, Any], list[int], bool]:
        state = manifest_identifier(public)
        # Arriving again at an input we already left proves each action taken from it
        # returned here with no public change.
        if state in self.taken and self.current != state:
            self.withheld.setdefault(state, set()).update(self.taken[state])
        self.current = state
        candidates = public["candidates"]
        blocked = self.withheld.get(state, set())
        indices = [i for i, c in enumerate(candidates) if candidate_key(c) not in blocked]
        if not indices:
            indices = list(range(len(candidates)))
        if len(indices) == len(candidates):
            return public, indices, False
        return {**public, "candidates": [candidates[i] for i in indices]}, indices, False

    def advance(self, public: dict[str, Any], action: int) -> None:
        state = manifest_identifier(public)
        self.taken.setdefault(state, set()).add(candidate_key(public["candidates"][action]))
        # Leaving resets the "same state" marker so a later return counts as a round trip.
        self.current = None


class GuardedOwnPolicy(OwnPolicy):
    """The model samples over every candidate the guard has not proved effect-free."""

    def __init__(self, *args: Any, **values: Any) -> None:
        super().__init__(*args, **values)
        self.chooser.navigation = CycleGuard()

    def choose(self, frame: dict[str, Any]) -> dict[str, Any]:
        selected = LivePolicy.choose(self, frame)
        assert self.pending is not None
        trial = self.pending[2]
        assert trial.last is not None
        rows, _, effective, forced = trial.last
        public = frame["public_input"]
        if (
            forced
            or len(rows) != len(effective["candidates"])
            or not 0 < len(rows) <= len(public["candidates"])
            or selected["effective_input_id"] != manifest_identifier(effective)
            or effective["candidates"][selected["effective_action_index"]]
            != public["candidates"][selected["action_index"]]
            or selected["behavior"] != "sampled_softmax"
            or selected["draw_used"] is not True
        ):
            raise ValueError("The model must sample over every action not proved effect-free")
        selected["policy_contract"] = CONTRACT
        selected["withheld_effect_free_actions"] = len(public["candidates"]) - len(rows)
        return selected


def groups(directory: Path, model_id: str) -> Iterator[list[tuple[dict[str, Any], dict[str, Any]]]]:
    """Stream verified experience, re-deriving every withheld candidate from public inputs.

    Each yielded frame carries the effective public menu the model scored, and each
    choice carries its index in that menu, so PPO reconstructs the actual behavior.
    """
    raw = records(directory / "worker/public-observations.jsonl.gz")
    guard = CycleGuard()
    pending: list[tuple[dict[str, Any], dict[str, Any]]] = []
    successor = None
    for (_, frame, delivered), row in zip(decisions(directory / TRACE), raw, strict=True):
        snapshot = row["snapshot"]
        snapshot_id = frame["observation"]["snapshot_id"]
        if snapshot["snapshot_id"] != snapshot_id or (
            successor is not None and successor != snapshot_id
        ):
            raise ValueError("Observed native successor differs from the delivery receipt")
        if delivered is None:
            if pending:
                raise ValueError("An incomplete answer supplies no native decision")
            continue
        menu, actions = snapshot["bound_actions"], frame["actions"]
        native = menu["actions"]
        if (
            menu["status"] != "complete"
            or menu["total_count"] != len(native)
            or sorted(a["raw_index"] for a in actions) != list(range(len(native)))
            or any(
                a["bound_action_id"] != native[a["raw_index"]]["bound_action_id"] for a in actions
            )
        ):
            raise ValueError("Every advertised native binding must reach the guard")
        public, choice, ack = frame["public_input"], delivered["choice"], delivered["receipt"]
        index, logp = choice["action_index"], choice["log_probability"]
        domain, successor = ack["delivery_domain"], ack["successor_snapshot_id"]
        # Answer factors advance a copied policy that commits on its delivered
        # completion; incomplete answers raise, so one sequential guard is exact.
        effective, indices, forced = guard.view(public)
        if (
            choice["policy_contract"] != CONTRACT
            or choice["model_id"] != model_id
            or choice["behavior"] != "sampled_softmax"
            or choice["draw_used"] is not True
            or choice["navigation_only"] is not False
            or forced
            or choice.get("intervention") is not None
            or choice["optimizer_updates"] != 0
            or choice["public_input_id"] != manifest_identifier(public)
            or choice["effective_input_id"] != manifest_identifier(effective)
            or choice["withheld_effect_free_actions"] != len(public["candidates"]) - len(indices)
            or len(actions) != len(public["candidates"])
            or type(index) is not int
            or not 0 <= index < len(actions)
            or indices[choice["effective_action_index"]] != index
            or not math.isfinite(logp)
            or logp > 0
            or not successor
            or choice["bound_action_id"] != actions[index]["bound_action_id"]
            or ack != receipt(frame, choice, domain, successor)
        ):
            raise ValueError("Experience requires an exact guarded sample and delivered binding")
        guard.advance(public, index)
        scored = (
            {**frame, "public_input": effective},
            {**choice, "action_index": choice["effective_action_index"]},
        )
        answer = choice.get("answer_plan")
        if answer is None:
            if pending or domain != "native":
                raise ValueError("A local factor cannot become standalone experience")
            yield [scored]
            continue
        origin = pending[0][0] if pending else frame
        verb = public["candidates"][index]["verb"]
        complete = verb in {"confirm", "cancel"}
        if (
            verb not in {"select", "confirm", "cancel"}
            or answer["contract"] != PLAN
            or answer["factor_index"] != len(pending)
            or answer["answer_id"]
            != manifest_identifier({"atomic_answer_origin": origin["binding_id"]})
            or answer["standalone_game_decision"] is not False
            or answer["complete"] is not complete
            or domain != ("native" if complete else "local_answer_factor")
        ):
            raise ValueError("Conditional factors must lead to one exact native answer")
        pending.append(scored)
        joint = math.fsum(c["log_probability"] for _, c in pending)
        if not math.isclose(
            answer["joint_behavior_log_probability"], joint, rel_tol=0, abs_tol=1e-10
        ):
            raise ValueError("Joint behavior probability differs from the conditional factors")
        if complete:
            yield pending
            pending = []


@contextmanager
def using_cycle_guard() -> Iterator[None]:
    """Bind the guard into inference, independent replay and PPO reconstruction."""
    with (
        patch.object(native_a8_head_policy, "AllActions", CycleGuard),
        patch.object(native_a8_own_policy, "AllActions", CycleGuard),
        patch.multiple(
            native_a8_own_experience,
            OwnPolicy=GuardedOwnPolicy,
            groups=groups,
            CONTRACT=CONTRACT,
        ),
    ):
        yield
