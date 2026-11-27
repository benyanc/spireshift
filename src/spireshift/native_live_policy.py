"""Frozen production-policy inference; delivered choices alone advance public memory."""

from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import NativeActorCritic, validate_public_input
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Adam
from spireshift.native_compatibility_contract import checkpoint
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import load_state
from spireshift.native_structured_policy import Chooser
from spireshift.native_structured_state import load, save
from spireshift.training_objective import TrainingScoreSpec

CONTRACT = "official_cli_shared_public_graph_v1"
POLICY = "frozen_current_checkpoint_delivered_memory_v1"


def import_checkpoint(
    root: Path,
    ref: dict[str, Any],
    environment: dict[str, Any],
    score: TrainingScoreSpec,
    destination: Path,
) -> tuple[CachedContextModel, Adam, dict[str, Any]]:
    """Explicit new metadata on a copy; no numerical/optimizer change or old-file edit."""
    original, identity = checkpoint(root, ref, environment["parent_environment_id"], score.spec_id)
    path = root / ref["path"]
    try:
        _, adam, _ = load(path)
    except ValueError:
        _, adam, _ = load_state(path)
    native = NativeActorCritic(
        replace(original.actor, environment_id=environment["manifest_id"]), original.value_weights
    )
    model = replace(original, native=native)
    if model.weights() != original.weights() or model.feature_spec_id != original.feature_spec_id:
        raise ValueError("Environment import changed numerical weights or the credit contract")
    if destination.exists():
        restored, optimizer, _ = load(destination)
        if restored.as_dict() != model.as_dict() or optimizer.as_dict() != adam.as_dict():
            raise ValueError("Preserve a changed or partial imported checkpoint")
        state = {
            "state_id": manifest_identifier(
                {
                    "schema_version": "native-structured-model-optimizer-v1",
                    "model": model.as_dict(),
                    "optimizer": adam.as_dict(),
                }
            )
        }
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        state = save(destination, model, adam)
    if _sha_file(path) != ref["sha256"]:
        raise ValueError("Original checkpoint changed during import")
    receipt = {
        "schema_version": "shared-input-exact-state-import-v1",
        "source": identity,
        "destination": str(destination.relative_to(root)),
        "state_id": state["state_id"],
        "model_id": model.model_id,
        "environment_id": environment["manifest_id"],
        "shared_input_contract": CONTRACT,
        "numeric_weights_exact": True,
        "all_Adam_moments_and_counter_exact": True,
        "optimizer_id": manifest_identifier(adam.as_dict()),
        "optimizer_steps": adam.steps,
        "optimizer_updates": 0,
        "original_bytes_unchanged": True,
        "initial_policy_behavior_unchanged_claimed": False,
    }
    receipt["report_id"] = manifest_identifier(receipt)
    receipt_path = destination.with_suffix(".import.json")
    if receipt_path.exists():
        import json

        if json.loads(receipt_path.read_text()) != receipt:
            raise ValueError("Exact-state import receipt changed")
    else:
        atomic_json(receipt_path, receipt)
    return model, adam, receipt


class LivePolicy:
    def __init__(self, model: CachedContextModel, score: TrainingScoreSpec, seed: str) -> None:
        self.model, self.score = model, score
        self.chooser = Chooser(model, score, seed, False)
        self.pending: tuple[dict[str, Any], dict[str, Any], Chooser] | None = None
        self.failed = False
        self.decisions = 0

    def choose(self, frame: dict[str, Any]) -> dict[str, Any]:
        if self.failed or self.pending is not None:
            raise ValueError("An uncertain or unacknowledged choice cannot be retried")
        public = frame["public_input"]
        validate_public_input(public)
        actions = frame["actions"]
        if (
            frame.get("schema_version") != "shared-public-decision-v1"
            or frame.get("contract") != CONTRACT
            or frame.get("terminal") is not False
            or not frame.get("binding_id")
            or not actions
            or len(actions) != len(public["candidates"])
            or len({a["bound_action_id"] for a in actions}) != len(actions)
            or len({a["key"] for a in actions}) != len(actions)
            or len({a["raw_index"] for a in actions}) != len(actions)
        ):
            raise ValueError("Incomplete shared decision or ambiguous current action binding")
        # Cheap copy of only navigation/counters. Immutable weights/score are shared,
        # never copied or updated per decision. Public memory commits after delivery.
        trial = copy.deepcopy(
            self.chooser, {id(self.model): self.model, id(self.score): self.score}
        )
        choice = trial(public)
        result = {
            **choice,
            "binding_id": frame["binding_id"],
            "adapter_contract": POLICY,
            "shared_input_contract": CONTRACT,
            "bound_action_id": actions[choice["action_index"]]["bound_action_id"],
            "optimizer_updates": 0,
        }
        self.pending = frame, result, trial
        return result

    def acknowledge(self, receipt: dict[str, Any]) -> None:
        if self.failed or self.pending is None:
            raise ValueError("No pending delivered choice; duplicate acknowledgement rejected")
        frame, choice, trial = self.pending
        if (
            receipt.get("binding_id") != frame["binding_id"]
            or receipt.get("delivery") != "delivered"
            or receipt.get("bound_action_id") != choice["bound_action_id"]
            or receipt.get("runtime_instance_id") != frame["observation"]["runtime_instance_id"]
            or receipt.get("before_snapshot_id") != frame["observation"]["snapshot_id"]
            or not receipt.get("successor_snapshot_id")
        ):
            self.failed = True
            raise ValueError(
                "Uncertain or wrong-runtime action delivery; preserve evidence, no retry"
            )
        self.chooser, self.pending = trial, None
        self.decisions += 1
