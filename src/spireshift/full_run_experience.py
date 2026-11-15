"""Complete-run experience for unified policies; no action-branch cloning."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.protocols import EnvironmentAdapter
from spireshift.core.types import DecisionType, LegalAction, Observation
from spireshift.full_run_policy import FullRunPolicy
from spireshift.training_objective import (
    RunStatus,
    TrainingOutcome,
    TrainingScoreSpec,
    score_training_outcome,
)

CASE_SCHEMA = "unified-full-run-experience-v1"
TRACE_SCHEMA = "unified-public-decision-v1"
ACT_SEQUENCE = ({"overgrowth", "underdocks"}, {"hive"}, {"glory"})


@dataclass(slots=True)
class PublicProgress:
    """Count observed act transitions, never infer act ordinal from an identity/floor."""

    acts: list[str] = field(default_factory=list)
    maximum_floor: int = 0
    milestones: list[dict[str, Any]] = field(default_factory=list)

    def observe(self, observation: Observation, decision: int) -> None:
        state = observation.public_state
        act, floor = state.get("act"), state.get("floor")
        if type(floor) is not int or floor < self.maximum_floor:
            raise ValueError("Public full-run floor is missing or regressed")
        if not isinstance(act, str):
            raise ValueError("Public act identity is missing")
        if not self.acts or self.acts[-1] != act:
            index = len(self.acts)
            if index >= len(ACT_SEQUENCE) or act not in ACT_SEQUENCE[index]:
                raise ValueError("Unexpected public full-run act transition")
            self.acts.append(act)
            self.milestones.append(
                {"decision": decision, "act": act, "floor": floor, "completed_acts": index}
            )
        self.maximum_floor = max(self.maximum_floor, floor)

    def completed_acts(self, victory: bool) -> int:
        if victory and len(self.acts) != 3:
            raise ValueError("Terminal victory did not traverse all three public acts")
        return 3 if victory else max(0, len(self.acts) - 1)


def implementation_id() -> str:
    # Resuming after a feature/runner/model/score change must not mix artifacts.
    root = Path(__file__).parent
    return manifest_identifier(
        {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in (
                "full_run_features.py",
                "full_run_policy.py",
                "full_run_experience.py",
                "training_objective.py",
                "combat_features.py",
                "representations.py",
                "neural_combat_features.py",
            )
        }
    )


def case_binding(
    ruleset: RulesetIdentity,
    policy: FullRunPolicy,
    score: TrainingScoreSpec,
    seed: int,
    partition: str,
    split_id: str,
    maximum_decisions: int,
) -> dict[str, Any]:
    if partition not in {"train", "development"}:
        raise ValueError("Unified pilot never opens final-test seeds")
    if ruleset.manifest_id != score.scope.ruleset_manifest_id:
        raise ValueError("Full-run score belongs to another ruleset")
    if score.scope.character != "ironclad" or score.scope.ascension != 0:
        raise ValueError("The frozen full-run backend supports this pilot at Ironclad A0")
    if type(seed) is not int or seed < 0 or not 1 <= maximum_decisions <= 10000:
        raise ValueError("Invalid full-run seed or decision cap")
    return {
        "ruleset_manifest_id": ruleset.manifest_id,
        "patch_id": ruleset.patch_id,
        "model_id": policy.model_id,
        "policy_id": policy.policy_id,
        "training_spec_id": score.spec_id,
        "evaluation_objective_id": score.evaluation_objective.objective_id,
        "scope": score.scope.as_dict(),
        "split_manifest_id": split_id,
        "seed": seed,
        "partition": partition,
        "maximum_decisions": maximum_decisions,
        "whole_run_cpu_seconds": score.evaluation_objective.whole_run_budget,
        "behavior": "greedy_argmax",
        "implementation_id": implementation_id(),
    }


def collect_episode(
    environment_factory: Callable[[], EnvironmentAdapter],
    ruleset: RulesetIdentity,
    policy: FullRunPolicy,
    score: TrainingScoreSpec,
    *,
    seed: int,
    partition: str,
    split_id: str,
    maximum_decisions: int = 4096,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    binding = case_binding(ruleset, policy, score, seed, partition, split_id, maximum_decisions)
    cpu_start, wall_start = time.process_time(), time.perf_counter()
    environment: EnvironmentAdapter | None = None
    trace: list[dict[str, Any]] = []
    progress = PublicProgress()
    counts: Counter[tuple[str, str, str]] = Counter()
    phase_counts: Counter[str] = Counter()
    status, error = RunStatus.ERROR, None
    inference_seconds = 0.0
    observed_terminal = observed_victory = False
    final_hash: str | None = None
    final_observation: dict[str, Any] | None = None
    try:
        environment = environment_factory()
        if environment.ruleset != ruleset:
            raise ValueError("Full-run environment ruleset differs")
        observation = environment.reset(seed)
        progress.observe(observation, 0)
        while not observation.public_state.get("terminal"):
            if time.process_time() - cpu_start >= score.evaluation_objective.whole_run_budget:
                status = RunStatus.BUDGET
                break
            if len(trace) >= maximum_decisions:
                status = RunStatus.TRUNCATED
                break
            actions = tuple(environment.legal_actions())
            if not actions:
                raise ValueError("Nonterminal state has no public legal candidates")
            started = time.perf_counter()
            decision = policy.predict(observation, actions)
            inference_seconds += time.perf_counter() - started
            if time.process_time() - cpu_start >= score.evaluation_objective.whole_run_budget:
                status = RunStatus.BUDGET
                break
            action = decision.selected_action
            if action not in actions:
                raise ValueError("Unified policy selected an illegal candidate")
            transition = environment.step(action)
            trace.append(
                {
                    "schema_version": TRACE_SCHEMA,
                    "decision_index": len(trace),
                    "observation": observation.as_dict(),
                    "legal_candidates": [a.as_dict() for a in actions],
                    "candidate_bindings": list(decision.inputs.bindings),
                    "selected_index": decision.candidate_index,
                    "policy_softmax": list(decision.probabilities),
                    "behavior": "greedy_argmax",
                    "behavior_probability": 1.0,
                    "environment_reward": transition.reward,
                    "next_state_hash": transition.next_observation.state_hash,
                    "terminal": transition.terminal,
                    "victory": transition.victory,
                }
            )
            phase_counts[observation.decision_type.value] += 1
            repeated = (
                observation.state_hash,
                action.action_id,
                transition.next_observation.state_hash,
            )
            counts[repeated] += 1
            observation = transition.next_observation
            progress.observe(observation, len(trace))
            if counts[repeated] >= 3 and not transition.terminal:
                status = RunStatus.LIVENESS
                break
        else:
            observed_terminal = True
            observed_victory = bool(observation.public_state.get("victory"))
            status = RunStatus.VICTORY if observed_victory else RunStatus.LOSS
        final_hash = observation.state_hash
        final_observation = observation.as_dict()
        if time.process_time() - cpu_start >= score.evaluation_objective.whole_run_budget:
            status = RunStatus.BUDGET
        completed = progress.completed_acts(status == RunStatus.VICTORY)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        status = RunStatus.UNSUPPORTED if isinstance(exc, ValueError) else RunStatus.ERROR
        completed = max(0, len(progress.acts) - 1)
    finally:
        close = getattr(environment, "close", None)
        if callable(close):
            try:
                close()
            except Exception as exc:
                status, error = RunStatus.ERROR, f"Environment close failed: {exc}"
    outcome = TrainingOutcome(
        seed, status, completed, progress.maximum_floor, len(trace), time.process_time() - cpu_start
    )
    scored = score_training_outcome(score, outcome)
    body = {
        "schema_version": CASE_SCHEMA,
        "binding": binding,
        "outcome": {
            "seed": seed,
            "status": status.value,
            "completed_acts": completed,
            "maximum_floor": progress.maximum_floor,
            "decisions": len(trace),
            "cpu_seconds": outcome.cpu_seconds,
        },
        "score": scored,
        "observed_terminal": observed_terminal,
        "observed_victory": observed_victory,
        "error": error,
        "milestones": progress.milestones,
        "decision_types": dict(phase_counts),
        "inference_seconds": inference_seconds,
        "wall_seconds": time.perf_counter() - wall_start,
        "final_state_hash": final_hash,
        "final_observation": final_observation,
        "trace_digest": manifest_identifier(trace),
        "claim_scope": "actual_complete_run_public_experience_not_causal_action_labels",
    }
    return {**body, "case_id": manifest_identifier(body)}, trace


def atomic_json(path: Path, value: object) -> None:
    """Publish once, including after interruption; never overwrite an existing result."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.partial")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def save_episode(path: Path, case: dict[str, Any], trace: list[dict[str, Any]]) -> None:
    trace_path = path.with_suffix(".jsonl.gz")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = trace_path.with_name(f".{trace_path.name}.{os.getpid()}.partial")
    with gzip.open(temporary, "wt", encoding="utf-8") as handle:
        for decision in trace:
            handle.write(json.dumps(decision, sort_keys=True, allow_nan=False) + "\n")
    try:
        os.link(temporary, trace_path)
    finally:
        temporary.unlink(missing_ok=True)
    atomic_json(
        path, {**case, "trace_file_sha256": hashlib.sha256(trace_path.read_bytes()).hexdigest()}
    )


def load_episode(path: Path, expected_binding: dict[str, Any]) -> dict[str, Any]:
    case = json.loads(path.read_text(encoding="utf-8"))
    digest = case.pop("trace_file_sha256")
    if case["binding"] != expected_binding or case["schema_version"] != CASE_SCHEMA:
        raise ValueError("Saved full-run episode bindings differ")
    body = {k: v for k, v in case.items() if k != "case_id"}
    if case["case_id"] != manifest_identifier(body):
        raise ValueError("Saved full-run episode identity differs")
    trace_path = path.with_suffix(".jsonl.gz")
    if hashlib.sha256(trace_path.read_bytes()).hexdigest() != digest:
        raise ValueError("Saved public experience bytes differ")
    # Byte integrity is cheap enough for resume. Semantic input checks are separate
    # from this operation and never claim to replay a game or prove action causality.
    return {**case, "trace_file_sha256": digest}


def verify_episode_trace(
    path: Path,
    ruleset: RulesetIdentity,
    policy: FullRunPolicy,
    score: TrainingScoreSpec,
    expected_binding: dict[str, Any],
) -> dict[str, Any]:
    case = load_episode(path, expected_binding)
    trace = []
    with gzip.open(path.with_suffix(".jsonl.gz"), "rt", encoding="utf-8") as handle:
        trace = [json.loads(line) for line in handle]
    if case["trace_digest"] != manifest_identifier(trace):
        raise ValueError("Saved decision content identity differs")
    if len(trace) != case["outcome"]["decisions"]:
        raise ValueError("Saved decision denominator differs")
    previous_next: str | None = None
    for index, entry in enumerate(trace):
        if entry["schema_version"] != TRACE_SCHEMA or entry["decision_index"] != index:
            raise ValueError("Saved decision ordering differs")
        d = entry["observation"]
        observation = Observation(
            d["schema_version"],
            d["patch_id"],
            DecisionType(d["decision_type"]),
            d["public_state"],
            d["state_hash"],
        )
        actions = tuple(
            LegalAction(a["action_id"], a["kind"], a["payload"]) for a in entry["legal_candidates"]
        )
        prediction = policy.predict(observation, actions)
        if (
            entry["selected_index"] != prediction.candidate_index
            or entry["candidate_bindings"] != list(prediction.inputs.bindings)
            or entry["behavior"] != "greedy_argmax"
            or entry["behavior_probability"] != 1.0
            or len(entry["policy_softmax"]) != len(prediction.probabilities)
            or any(
                type(a) not in (int, float) or not math.isfinite(a) or abs(a - b) > 1e-9
                for a, b in zip(entry["policy_softmax"], prediction.probabilities, strict=True)
            )
        ):
            raise ValueError("Saved candidate binding or behavior probability differs")
        if previous_next is not None and previous_next != observation.state_hash:
            raise ValueError("Saved public state chain differs")
        previous_next = entry["next_state_hash"]
        if entry["environment_reward"] not in (0, 1) or (
            entry["environment_reward"] == 1 and not (entry["terminal"] and entry["victory"])
        ):
            raise ValueError("Saved environment reward differs from terminal victory")
    if case["final_observation"] is not None:
        d = case["final_observation"]
        final = Observation(
            d["schema_version"],
            d["patch_id"],
            DecisionType(d["decision_type"]),
            d["public_state"],
            d["state_hash"],
        )
        from spireshift.representations import build_model_input

        build_model_input(ruleset, final, ())
        if final.state_hash != case["final_state_hash"] or (
            previous_next is not None and previous_next != final.state_hash
        ):
            raise ValueError("Saved final public state differs")
    outcome = TrainingOutcome.from_mapping(case["outcome"])
    if case["score"] != score_training_outcome(score, outcome):
        raise ValueError("Saved complete-run training score differs")
    return {
        "valid": True,
        "case_id": case["case_id"],
        "public_decisions": len(trace),
        "games_replayed": 0,
        "action_causality_established": False,
    }
