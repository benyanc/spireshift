# Tactical-to-run value handoff

Combat search must compare actions by their effect on terminal victory, including the persistent
state that leaves combat. SpireShift therefore passes tactical leaf states through the same public,
mechanics-aware representation used by the run-value model. Immediate HP, combat survival, and
floor completion are diagnostics; none can replace the declared terminal-victory objective.

## Typed boundary

`RunValueEstimator` accepts a nonterminal public observation and its complete legal-action list. It
returns a terminal-victory probability together with the source state hash, representation hash,
estimator identity, and represented state paths. `ModelRunValueEstimator` builds
`model-input-v1` and accepts either the base three-head model or its calibrated wrapper.

`model_run_value_estimator_from_checkpoint` is the safe construction path for learned artifacts. It
validates the checkpoint identity, exact ruleset-manifest ID, and `terminal-victory-v1` objective.
When calibration is supplied, it also verifies that the calibration belongs to the checkpoint and
uses the calibration ID as the estimator identity.

The compositional representation recursively retains all public scalars and collections. Tactical
leaves therefore retain HP and max HP, potions, deck contents and upgrades, relics and counters,
gold, progression, future path options, and other public mechanics available from the backend.
Hidden seeds, draw order, and future outcomes remain forbidden by the representation boundary.

## Leaf-value mixture

Each legal combat action receives the same number of independently resampled public-information
worlds. Its successor leaves are evaluated from three possible sources:

1. exact binary terminal returns when the successor or a rollout reaches run victory or defeat;
2. run-value estimates at nonterminal truncated-rollout endpoints; and
3. a direct run-value estimate at the tactical leaf.

The three source weights, candidate worlds, rollout samples, and rollout horizon are configurable.
Available components are normalized by their configured weights. An already-terminal leaf always
uses its exact binary return and never calls the model.

The evaluator rejects any estimator whose objective is not `terminal-victory-v1`. This prevents a
combat-survival, HP, or floor proxy from silently entering the search backup.

## Compute boundary

The current portable accounting unit is one simulated transition or one run-value inference. Before
sampling begins, the ranker computes the worst-case cost needed to give every candidate its declared
worlds and rollouts. It rejects the decision if the configured limit cannot finish that equal
comparison. The result reports transitions, model inferences, sampled worlds, and total units.

This local accounting makes the handoff usable by fixed search. Issue #33 will connect planner
charges to the hard episode-wide ledger and measured CPU time.

## Reproduce the mock ablation

```bash
uv run spireshift tactical-handoff benchmark-mock \
  artifacts/tactical-handoff/mock-report.json

uv run spireshift tactical-handoff verify \
  artifacts/tactical-handoff/mock-report.json
```

The checked fixture uses three seeds and a 128-unit decision limit. Its local ablation ranks the
same successors by post-combat HP alone. See the
[mock tactical-handoff evidence](evidence/mock-tactical-handoff-v1.md) and the
[report schema](../schemas/tactical-handoff-report-v1.json).

The mock proves the objective, representation, mixture, and compute contracts. It does not establish
STS2 model quality or combat-search improvement; those require an admitted simulator, representative
states, and the equal-compute learned-PUCT benchmark.
