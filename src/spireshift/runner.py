from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from spireshift.core.objective import ObjectiveSpec
from spireshift.core.protocols import BudgetController, EnvironmentAdapter, Policy, Recorder


@dataclass(frozen=True, slots=True)
class RunResult:
    seed: int
    victory: bool
    decisions: int
    compute_used: int
    record_path: Path


def run_episode(
    *,
    environment: EnvironmentAdapter,
    policy: Policy,
    budget_controller: BudgetController,
    recorder: Recorder,
    objective: ObjectiveSpec,
    seed: int,
) -> RunResult:
    ruleset = environment.ruleset
    if environment.patch_id != ruleset.patch_id:
        raise RuntimeError("Environment patch does not match its ruleset identity")
    observation = environment.reset(seed)
    if observation.patch_id != ruleset.patch_id:
        raise RuntimeError("Initial observation patch does not match the ruleset identity")
    remaining_budget = objective.whole_run_budget
    decisions = 0

    recorder.record_header(
        {
            "schema_version": "run-v1",
            "seed": seed,
            "patch_id": environment.patch_id,
            "ruleset": ruleset.as_dict(),
            "objective": objective.as_dict(),
            "policy_id": policy.policy_id,
            "controller_id": budget_controller.controller_id,
            "initial_state_hash": observation.state_hash,
        }
    )

    victory = False
    while not bool(observation.public_state["terminal"]):
        legal_actions = environment.legal_actions()
        tier = budget_controller.choose_tier(observation, remaining_budget)
        cost = tier.nominal_cost
        if cost > remaining_budget:
            raise RuntimeError("Selected compute tier exceeds whole-run budget")
        action = policy.choose_action(observation, legal_actions)
        transition = environment.step(action)
        if environment.ruleset != ruleset:
            raise RuntimeError("Environment ruleset changed during the run")
        if transition.next_observation.patch_id != ruleset.patch_id:
            raise RuntimeError("Observation patch changed during the run")
        remaining_budget -= cost
        decisions += 1

        recorder.record_step(
            {
                "decision_index": decisions - 1,
                "budget_tier": tier.value,
                "compute_cost": cost,
                "remaining_budget": remaining_budget,
                "legal_actions": [candidate.as_dict() for candidate in legal_actions],
                "transition": transition.as_dict(),
            }
        )
        observation = transition.next_observation
        victory = transition.victory

    compute_used = objective.whole_run_budget - remaining_budget
    recorder.record_summary(
        {
            "victory": victory,
            "terminal_reward": 1.0 if victory else 0.0,
            "decisions": decisions,
            "compute_used": compute_used,
            "final_state_hash": observation.state_hash,
        }
    )
    return RunResult(seed, victory, decisions, compute_used, recorder.path)
