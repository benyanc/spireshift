# A8 action-credit collection

**Completed.** The [saved audit](native-a8-action-credit-result.md)
verified nine informative pairs against a minimum of twelve.
The pairs remain diagnostic evidence.

The [matched practice result](native-a8-matched-practice-result.md)
verified 72 Act 1 losses. Each fitted arm reached the Act 1 boss twice,
and each recorded zero clears. The next experiment tests whether model
exploration can produce direct learning evidence about a single action.

## Comparison design

Each pair starts a normal Ironclad/A8 run with the same world,
same original checkpoint, and same sampled choices up to a
predeclared root. The root is the first eligible public menu at or
beyond its assigned floor. The declared strata cover combat,
route, and resource decisions, including rewards, events, and shops.
Root menus offer at least two visibly different legal choices.
Compact ordered answers retain their normal delivery and remain
outside the branching roots in this pilot.

The reference samples its full menu. At the root, the alternate
samples from the same actor probabilities conditional on a different
displayed choice. Both branches otherwise use the same sampler and
seed. The log records the alternate's conditional probability and
its original probability separately. The verifier checks equality
through the offered root, the two native deliveries, their observed
successors, both full continuations, and the actual ending.

The existing full-run training score compares the resulting terminal
outcomes. A native victory outranks any loss. Within losses, completed
acts and floor progress supply bootstrap feedback. Only matched
roots with different public successors and different training
returns count toward the candidate. A pair measures the effect on
one matched continuation. Stronger claims require independent data
and fresh normal-start evaluation.

## Verified controls

Three fresh control pairs verified combat, map, and reward roots.
Each pair had different legal deliveries and observed successors.
All six games ended in native losses, with 536 reconstructed
deliveries. Each pair tied on its full-run training score, so the
controls supplied zero preferred actions. They verified execution.
[Control evidence](evidence/native-a8-action-credit-control-v1.json).

## Owner collection

The plan contains 18 fresh training worlds, with both initializers
and two arms per world. It samples root floors 2, 4, and 6 across
the three strata. Control, earlier development, and final-test
worlds stay separate. The candidate gate requires 12 informative
pairs overall, at least two per stratum, and at least three per
initializer. Missing roots, tied returns, caps, and failed games
remain visible in the collection report.

Close STS2. Allow about 20–35 minutes for the 72 games.

```bash
bash scripts/collect-a8-action-credit-v1.sh
```

The run collects training evidence and makes zero optimizer updates.
It preserves the build, original checkpoints, full Adam, and earlier
studies. A later fit would use a separately declared recipe on copies.
Uncertain delivery preserves the active marker and blocks replay.
