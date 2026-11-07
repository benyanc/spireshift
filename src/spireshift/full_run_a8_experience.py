"""Fresh A8 episodes with genuinely sampled behavior and complete-run returns."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import random
import time
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from spireshift.adapters.evangambit_public_choices import choice_view
from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.protocols import EnvironmentAdapter
from spireshift.core.types import DecisionType, LegalAction, Observation
from spireshift.full_run_a8_admission import PROFILE_ID
from spireshift.full_run_experience import PublicProgress
from spireshift.full_run_ppo_math import ActorCritic, Sample, log_softmax, state_features
from spireshift.full_run_public_policy import PublicFullRunPolicy
from spireshift.representations import build_model_input
from spireshift.splits import SplitManifest, SplitName
from spireshift.training_objective import (
    RunStatus,
    TrainingOutcome,
    TrainingScoreSpec,
    score_training_outcome,
)

CASE_SCHEMA = "public-a8-sampled-experience-v1"
TRACE_SCHEMA = "public-a8-behavior-decision-v1"


def implementation_id() -> str:
    root = Path(__file__).parent
    files = (
        "full_run_a8_experience.py",
        "full_run_ppo_math.py",
        "full_run_experience.py",
        "full_run_features.py",
        "full_run_policy.py",
        "full_run_public_policy.py",
        "training_objective.py",
        "combat_features.py",
        "representations.py",
        "neural_combat_features.py",
        "public_run_choices.py",
        "adapters/evangambit.py",
        "adapters/evangambit_public_choices.py",
    )
    return manifest_identifier(
        {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files}
    )


def episode_binding(
    ruleset: RulesetIdentity,
    model: ActorCritic,
    score: TrainingScoreSpec,
    splits: SplitManifest,
    seed: int,
    partition: str,
    maximum_decisions: int,
    behavior: str,
    temperature: float,
    sampling_seed: int,
) -> dict[str, Any]:
    expected = {"train": SplitName.TRAIN, "development": SplitName.VALIDATION}.get(partition)
    if expected is None or splits.split_for_seed(seed) != expected:
        raise ValueError("A8 episode crosses complete-run split ownership; final test stays sealed")
    if (
        ruleset.manifest_id != score.scope.ruleset_manifest_id
        or splits.ruleset_manifest_id != ruleset.manifest_id
        or splits.objective_id != score.evaluation_objective.objective_id
        or score.scope.character != "ironclad"
        or score.scope.ascension != 8
        or model.actor.ruleset_manifest_id != ruleset.manifest_id
        or model.actor.patch_id != ruleset.patch_id
    ):
        raise ValueError("A8 episode rules, model, objective or difficulty differ")
    if type(maximum_decisions) is not int or not 1 <= maximum_decisions <= 10000:
        raise ValueError("Invalid A8 decision cap")
    if (
        behavior not in {"sampled_softmax", "greedy_argmax"}
        or type(temperature) not in (int, float)
        or not 0.1 <= temperature <= 2
        or type(sampling_seed) is not int
        or sampling_seed < 0
        or (partition == "development" and behavior != "greedy_argmax")
    ):
        raise ValueError("Invalid A8 behavior specification")
    return {
        "ruleset_manifest_id": ruleset.manifest_id,
        "patch_id": ruleset.patch_id,
        "model_id": model.model_id,
        "actor_id": model.actor.model_id,
        "training_spec_id": score.spec_id,
        "evaluation_objective_id": score.evaluation_objective.objective_id,
        "scope": score.scope.as_dict(),
        "split_manifest_id": splits.manifest_id,
        "seed": seed,
        "partition": partition,
        "maximum_decisions": maximum_decisions,
        "whole_run_cpu_seconds": score.evaluation_objective.whole_run_budget,
        "behavior": behavior,
        "temperature": float(temperature),
        "sampling_seed": sampling_seed,
        "implementation_id": implementation_id(),
    }


def choose_sample(probabilities: Sequence[float], rng: random.Random) -> int:
    if not probabilities or abs(math.fsum(probabilities) - 1) > 1e-9:
        raise ValueError("Invalid sampling distribution")
    if any(not math.isfinite(p) or p < 0 for p in probabilities):
        raise ValueError("Invalid sampling probabilities")
    draw, cumulative = rng.random(), 0.0
    for index, probability in enumerate(probabilities):
        cumulative += probability
        if draw < cumulative:
            return index
    return len(probabilities) - 1


def collect_a8_episode(
    environment_factory: Callable[[], EnvironmentAdapter],
    ruleset: RulesetIdentity,
    model: ActorCritic,
    score: TrainingScoreSpec,
    splits: SplitManifest,
    *,
    seed: int,
    partition: str,
    behavior: str,
    sampling_seed: int,
    temperature: float = 1.0,
    maximum_decisions: int = 4096,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    binding = episode_binding(
        ruleset,
        model,
        score,
        splits,
        seed,
        partition,
        maximum_decisions,
        behavior,
        temperature,
        sampling_seed,
    )
    policy = PublicFullRunPolicy(ruleset, model.actor)
    rng = random.Random(sampling_seed)
    cpu_start, wall_start = time.process_time(), time.perf_counter()
    environment: EnvironmentAdapter | None = None
    trace: list[dict[str, Any]] = []
    progress = PublicProgress()
    counts: Counter[tuple[str, str, str]] = Counter()
    phases: Counter[str] = Counter()
    status, error, completed = RunStatus.ERROR, None, 0
    observed_terminal = observed_victory = False
    final: Observation | None = None
    try:
        environment = environment_factory()
        if environment.ruleset != ruleset:
            raise ValueError("A8 environment identity differs")
        observation = environment.reset(seed)
        profile = choice_view(observation).fixed_profile
        if (
            profile.get("profile_id") != PROFILE_ID
            or profile.get("source_declared_ascension_level") != 8
        ):
            raise ValueError("Actual native run is not the fixed A8 profile")
        progress.observe(observation, 0)
        final = observation
        while not observation.public_state.get("terminal"):
            if time.process_time() - cpu_start >= score.evaluation_objective.whole_run_budget:
                status = RunStatus.BUDGET
                break
            if len(trace) >= maximum_decisions:
                status = RunStatus.TRUNCATED
                break
            actions = tuple(environment.legal_actions())
            decision = policy.predict(observation, actions)
            logs = log_softmax(decision.logits, temperature)
            probabilities = tuple(math.exp(p) for p in logs)
            chosen = (
                choose_sample(probabilities, rng)
                if behavior == "sampled_softmax"
                else decision.candidate_index
            )
            old_value = model.value(state_features(decision.inputs.context, model.actor.dimension))
            if time.process_time() - cpu_start >= score.evaluation_objective.whole_run_budget:
                status = RunStatus.BUDGET
                break
            transition = environment.step(actions[chosen])
            if transition.reward not in (0, 1) or transition.reward != float(
                transition.terminal and transition.victory
            ):
                raise ValueError("Engine reward must stay binary terminal victory")
            trace.append(
                {
                    "schema_version": TRACE_SCHEMA,
                    "decision_index": len(trace),
                    "observation": observation.as_dict(),
                    "legal_candidates": [a.as_dict() for a in actions],
                    "candidate_bindings": list(decision.inputs.bindings),
                    "selected_index": chosen,
                    "policy_softmax": list(probabilities),
                    "behavior": behavior,
                    "behavior_probability": probabilities[chosen]
                    if behavior == "sampled_softmax"
                    else 1.0,
                    "behavior_log_probability": logs[chosen]
                    if behavior == "sampled_softmax"
                    else 0.0,
                    "old_bootstrap_value": old_value,
                    "environment_reward": transition.reward,
                    "next_state_hash": transition.next_observation.state_hash,
                    "terminal": transition.terminal,
                    "victory": transition.victory,
                }
            )
            phases[observation.decision_type.value] += 1
            repeated = (
                observation.state_hash,
                actions[chosen].action_id,
                transition.next_observation.state_hash,
            )
            counts[repeated] += 1
            observation = final = transition.next_observation
            progress.observe(observation, len(trace))
            if counts[repeated] >= 3 and not transition.terminal:
                status = RunStatus.LIVENESS
                break
        else:
            observed_terminal = True
            observed_victory = bool(observation.public_state.get("victory"))
            status = RunStatus.VICTORY if observed_victory else RunStatus.LOSS
        completed = progress.completed_acts(status == RunStatus.VICTORY)
    except Exception as exc:
        status = RunStatus.UNSUPPORTED if isinstance(exc, ValueError) else RunStatus.ERROR
        error = f"{type(exc).__name__}: {exc}"
        completed = max(0, len(progress.acts) - 1)
    finally:
        close = getattr(environment, "close", None)
        if callable(close):
            try:
                close()
            except Exception as exc:
                status, error = RunStatus.ERROR, f"Environment close failed: {exc}"
    elapsed = time.process_time() - cpu_start
    if elapsed >= score.evaluation_objective.whole_run_budget:
        status = RunStatus.BUDGET
    outcome = {
        "seed": seed,
        "status": status.value,
        "completed_acts": completed,
        "maximum_floor": progress.maximum_floor,
        "decisions": len(trace),
        "cpu_seconds": elapsed,
    }
    body = {
        "schema_version": CASE_SCHEMA,
        "binding": binding,
        "outcome": outcome,
        "score": score_training_outcome(score, TrainingOutcome.from_mapping(outcome)),
        "observed_terminal": observed_terminal,
        "observed_victory": observed_victory,
        "error": error,
        "milestones": progress.milestones,
        "decision_types": dict(phases),
        "wall_seconds": time.perf_counter() - wall_start,
        "final_state_hash": None if final is None else final.state_hash,
        "final_observation": None if final is None else final.as_dict(),
        "trace_digest": manifest_identifier(trace),
        "claim_scope": "actual_public_a8_game_outcomes_not_causal_action_teacher_labels",
    }
    return {**body, "case_id": manifest_identifier(body)}, trace


def load_a8_episode(
    path: Path, expected_binding: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    case = json.loads(path.read_text())
    if case.get("schema_version") != CASE_SCHEMA or case.get("binding") != expected_binding:
        raise ValueError("Saved A8 behavior or scope differs")
    body = {k: v for k, v in case.items() if k not in {"case_id", "trace_file_sha256"}}
    if case.get("case_id") != manifest_identifier(body):
        raise ValueError("Saved A8 case identity differs")
    trace_path = path.with_suffix(".jsonl.gz")
    if hashlib.sha256(trace_path.read_bytes()).hexdigest() != case["trace_file_sha256"]:
        raise ValueError("Saved A8 trace bytes differ")
    with gzip.open(trace_path, "rt", encoding="utf-8") as handle:
        trace = [json.loads(line) for line in handle]
    if (
        case["trace_digest"] != manifest_identifier(trace)
        or len(trace) != case["outcome"]["decisions"]
    ):
        raise ValueError("Saved A8 trace content or denominator differs")
    return case, trace


def _observation(value: dict[str, Any]) -> Observation:
    return Observation(
        value["schema_version"],
        value["patch_id"],
        DecisionType(value["decision_type"]),
        value["public_state"],
        value["state_hash"],
    )


def verified_samples(
    case: dict[str, Any],
    trace: list[dict[str, Any]],
    ruleset: RulesetIdentity,
    model: ActorCritic,
    score: TrainingScoreSpec,
) -> list[Sample]:
    """Recompute public bindings and the true behavior, without any game replay."""
    policy, binding = PublicFullRunPolicy(ruleset, model.actor), case["binding"]
    if binding["model_id"] != model.model_id or binding["training_spec_id"] != score.spec_id:
        raise ValueError("Off-policy model or score supplied to PPO")
    if binding["behavior"] != "sampled_softmax" or binding["partition"] != "train":
        raise ValueError("PPO requires genuinely sampled training episodes, never greedy lessons")
    outcome = TrainingOutcome.from_mapping(case["outcome"])
    target = score_training_outcome(score, outcome)
    if case["score"] != target:
        raise ValueError("A8 training return differs from the declared score")
    rng, progress = random.Random(binding["sampling_seed"]), PublicProgress()
    samples: list[Sample] = []
    previous: str | None = None
    for index, entry in enumerate(trace):
        observation = _observation(entry["observation"])
        actions = tuple(
            LegalAction(a["action_id"], a["kind"], a["payload"]) for a in entry["legal_candidates"]
        )
        decision = policy.predict(observation, actions)
        logs = log_softmax(decision.logits, binding["temperature"])
        probabilities = tuple(math.exp(p) for p in logs)
        chosen = choose_sample(probabilities, rng)
        state = state_features(decision.inputs.context, model.actor.dimension)
        value = model.value(state)
        if (
            entry["schema_version"] != TRACE_SCHEMA
            or entry["decision_index"] != index
            or entry["behavior"] != "sampled_softmax"
            or entry["selected_index"] != chosen
            or entry["candidate_bindings"] != list(decision.inputs.bindings)
            or len(entry["policy_softmax"]) != len(probabilities)
            or any(
                abs(a - b) > 1e-9 or not math.isfinite(a)
                for a, b in zip(entry["policy_softmax"], probabilities, strict=True)
            )
            or any(
                type(entry[k]) not in (int, float) or not math.isfinite(entry[k])
                for k in ("behavior_probability", "behavior_log_probability", "old_bootstrap_value")
            )
            or abs(entry["behavior_probability"] - probabilities[chosen]) > 1e-9
            or abs(entry["behavior_log_probability"] - logs[chosen]) > 1e-9
            or abs(entry["old_bootstrap_value"] - value) > 1e-9
            or (previous is not None and previous != observation.state_hash)
            or entry["environment_reward"] != float(entry["terminal"] and entry["victory"])
            or (entry["terminal"] and index != len(trace) - 1)
        ):
            raise ValueError("Saved sampled probability, public binding or state chain differs")
        progress.observe(observation, index)
        previous = entry["next_state_hash"]
        samples.append(
            Sample(
                decision.inputs.vectors,
                state,
                chosen,
                logs[chosen],
                target["training_return"],
                target["training_return"] - value,
            )
        )
    if case["final_observation"] is not None:
        final = _observation(case["final_observation"])
        build_model_input(ruleset, final, ())
        progress.observe(final, len(trace))
        if final.state_hash != case["final_state_hash"] or (
            previous is not None and previous != final.state_hash
        ):
            raise ValueError("Saved final public state differs")
        if outcome.status in {RunStatus.LOSS, RunStatus.VICTORY} and (
            final.public_state.get("terminal") is not True
            or bool(final.public_state.get("victory")) != (outcome.status == RunStatus.VICTORY)
            or case["observed_terminal"] is not True
            or case["observed_victory"] != (outcome.status == RunStatus.VICTORY)
        ):
            raise ValueError("A completed outcome requires a matching public terminal state")
    observed_full_win = (
        case["observed_terminal"] and case["observed_victory"] and len(progress.acts) == 3
    )
    if (
        outcome.maximum_floor != progress.maximum_floor
        or outcome.completed_acts != progress.completed_acts(observed_full_win)
        or len(trace) != outcome.decisions
    ):
        raise ValueError("Recorded full-run progress differs from public observations")
    return samples
