# STS2 compute-quality pilot v0.107.1

The first 32-state production generation run completed without case or simulation failures, but it
did not produce an action-quality signal. This is negative evidence about the continuation policy,
not evidence that 32 simulations match 256 simulations.

The content-addressed benchmark report is
`sha256:772b0c41f556690c7fe0cc8a68ccec104fe7c9df7f7d8c2e1554613675de495f`. Its resource report is
`sha256:6c02ecf06286a6a3ca94f08bf0fe34d6b0e3a872042cb34d2b2063d546e47b10`.

## Result

| Measurement | Observed |
| --- | ---: |
| Frozen states | 32 |
| Completed states | 32 |
| Search simulations | 11,264 |
| Independent evaluation simulations | 16,192 |
| Total transitions | 2,960,515 |
| Legal candidates evaluated independently | 253 |
| Independent terminal victories | 0 |
| States with within-state candidate-value variation | 0 |
| States with a unique independently best action | 0 |
| States where the three tiers chose different actions | 0 |

Every independently evaluated action had terminal value zero. Therefore all reported regrets are
zero, every selected action is counted as tied for best, and all three tiers choose through the
planner's deterministic tie breakers. The nominal 100% best-action rate is not a quality result.
The exact replay job was deliberately not launched because it would only certify the same
uninformative all-loss evidence.

## Diagnosis

The search continuation policy is deliberately minimal: outside multi-select completion it chooses
the first legal action. Starting from the first combat decision, none of its complete-run
continuations wins. A terminal-victory objective is still the final optimization and evaluation
target, but it is too sparse to bootstrap this policy directly.

The next base-policy stage must add dense auxiliary prediction targets or imitation data while
leaving environment reward binary. Candidate examples are terminal-floor distributions, combat
outcome models, or labels from a stronger heuristic search policy. Fixed-budget search should be
re-run only after a policy-only pilot produces nonzero terminal victories or otherwise demonstrates
within-state terminal-value variation on the frozen validation protocol.

## Resource-accounting finding

The benchmark's linked worker reports contain 13,167.41 aggregate CPU-seconds, while the resource
wrapper recorded 69.87 CPU-seconds. The wrapper retained only the largest currently live process-tree
sample and lost CPU from completed worker generations. The resource tracker now preserves CPU time
per observed process identity across samples. The old resource report remains immutable and its CPU
fields must not be used for a cost claim.
