# SpireShift Project Charter

## Mission

SpireShift develops a full-run Slay the Spire 2 agent that maximizes the probability of terminal
victory under a fixed whole-run computation budget.

At every decision, the agent chooses the game action and the amount of computation to spend before
committing to it. Routine decisions should use a strong inexpensive policy. Costly search should
be reserved for decisions where it is expected to improve final victory probability.

## Primary objective

For a state `s`, the value target is:

```text
V(s) = P(terminal victory | s, policy)
```

The constrained objective is:

```text
maximize E[1(terminal victory)]
subject to E[sum(decision compute)] <= whole-run budget
```

The terminal-victory definition is versioned for every supported patch.

## Auxiliary targets

Current-combat survival, end-of-combat HP, potion use, floor reached, act completion, and deck
strength may be predicted and reported. They do not replace terminal victory as the optimization
target.

## Foundation principle

Adaptive search is valid only on top of a demonstrably capable cheap policy. The foundational
system must provide mechanics-aware representations, legal-action masking, policy and run-value
predictions, tactical-risk predictions, calibrated uncertainty, and deterministic safety checks.

Adaptive-budget training cannot begin until a frozen readiness evaluation establishes that:

- the cheap policy handles routine decisions competently;
- learned search improves the policy at equal compute;
- high-confidence catastrophic errors are sufficiently rare;
- run value and death risk are acceptably calibrated;
- expensive search has concentrated value rather than being necessary everywhere.

Readiness thresholds will be set from a pilot and frozen before adaptive-controller experiments.

## Evaluation hierarchy

1. **Primary:** terminal victory rate at a fixed whole-run computation budget.
2. **Secondary:** area under the victory-versus-compute curve and patch retention/recovery.
3. **Diagnostic:** act completion, floor distribution, HP, resources, regret, calibration, latency,
   invalid actions, and crashes.

## Patch robustness

The frozen pre-patch system is evaluated zero-shot on the new official patch before adaptation.
Adaptation methods receive identical data and compute budgets. Search uses current mechanics and
acts as an anchor when learned priors become stale.

## Scientific stopping conditions

Negative results remain valid deliverables. The project will report if search value cannot be
predicted, the cheap policy cannot meet readiness requirements, adaptive allocation fails to beat
simple thresholds, or search does not improve patch robustness.
