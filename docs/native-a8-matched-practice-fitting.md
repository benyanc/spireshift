# Matched A8 practice fitting

**Completed.** The [saved assessment](native-a8-matched-practice-result.md)
verified 72 Act 1 losses across the three arms.

The previous normal-start panel recorded 48 losses and one Act 1
clear. The [practice bank](native-a8-practice-continuation.md)
adds 64 model-owned segments from 32 matched training worlds,
including seven prepared Act 2 and Act 3 boss reward outcomes.
This comparison tests whether room feedback from the added states
transfers to genuine normal-start A8 wins.

## Fitting on checkpoint copies

| Arm | Full-run actor and value targets | Auxiliary actor batch |
| --- | --- | --- |
| Original | Frozen reference | None |
| Normal-only | Same 12 original normal-start trajectories per initializer | 32 normal-start room decisions |
| Mixed | Same 12 original normal-start trajectories per initializer | 16 shared normal-start draws and 16 prepared room draws |

The two fits start from identical original weights and Adam for
each initializer. They share the optimizer settings, trajectory
order, cross-fitted whole-run targets and auxiliary loss weight of
0.5. The two fits use two passes over the normal trajectories.
The three-pass preparation stopped before sealing a fit when the
mixed actor crossed the policy-change limit on prepared data.
That attempt is preserved. The two-pass recipe keeps the same
limit and the development worlds were still unused at that point.
The sampler balances worlds, then rooms within a world, then
eligible choices within a room. A resolved room receives credit
from its verified native reward or death, relative to other worlds
with the same encounter type. A prepared boss reward supplies
room feedback. Binary full-run victory remains the evaluation
target and the critic uses normal-start targets only.

Every fitting choice came from the original models' own samples.
The same public-input actor scores the complete legal menu,
including each factor of an ordered answer. The normal-start
worker carries forward the checked ending, Trial confirmation
and combat selector potion bindings.

## Verified preparation

| Initializer | Updates per fitted copy | Prepared draws in the mixed arm | Final value weights match |
| --- | ---: | ---: | --- |
| Player 2 | 24 | 384 | Yes |
| Player 3 | 30 | 480 | Yes |

The highest measured policy change was 0.02213 KL against a
0.03 limit. All six checkpoints reloaded and delivered four
choices each from the same fresh start. The separate two
ending controls verified native losses after 112 and 176
decisions. The controls use separate seeds from development.
The frozen game build v0.111.0 (`41cef1ea`), native executable,
runtime, SDK, existing weights and full Adam states passed
verification. [Preparation evidence](evidence/native-a8-matched-practice-fitting-v2.json).

## Fresh normal-start comparison

The evaluation runs 72 full games on 12 fresh normal-start
Ironclad/A8 worlds, with all three arms and both initializers on
each world. It uses the exact sealed checkpoints and zero optimizer
updates. It requires matching initial public inputs, verifies native
deliveries and endings, and retains every planned game in the win
rate denominator. The report keeps floor and act progress as
diagnostics. It bounds the win-rate difference when games are
capped, failed or unattempted.

Allow roughly 15–30 minutes after closing Slay the Spire 2.

```bash
bash scripts/compare-a8-practice-fitting-v2.sh
```

These worlds are development-only. The reserved final-test worlds
stay separate. Any candidate that wins here still needs prospective
confirmation and official-game validation before a competence claim.
