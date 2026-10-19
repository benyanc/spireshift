# Fresh-seed A8 confirmation result

Assessed 2026-10-18. **The predeclared auxiliary-progress confirmation passes.**
Both trained standard players improve on fresh game seeds. Full-game wins remain
zero, so strong play and base/value/search readiness are still unmet.

## Frozen players, fresh games

Each final standard player had 512 training games under 32-game batches / three
passes. Compare it to its own original numerical initializer, using 64 new paired
complete-run seeds per initializer: **128 distinct seeds / 256 attempts**. These
seeds were excluded from the earlier training, development and runner controls.
All models, temperature 0.8 sampled behavior, rules and whole-run budgets stay fixed.

| Player pair | Original mean floor | Trained mean floor | Paired gain | Trained full wins |
| --- | ---: | ---: | ---: | ---: |
| Initializer 2 | 6.953125 | 8.640625 | +1.687500 | 0/64 |
| Initializer 3 | 7.625000 | 9.078125 | +1.453125 | 0/64 |
| Combined | **7.289063** | **8.859375** | **+1.570313** | **0/128** |

The combined floor gain is about **21.5%** relative to the original mean floor,
not a win-rate improvement. The paired floor-change 95% bootstrap interval is
**+0.929688 to +2.226563**. For initializer 2 it is +0.890625 to +2.546875;
for initializer 3, +0.484375 to +2.468750. Out of 128 pairs, the trained player
reaches a higher floor in **66**, ties in **34** and reaches a lower floor in **28**.

The criterion declared before execution requires positive mean gain in both
players, positive pooled lower interval bound, no observed win regression and
zero failed games. All conditions pass. Both originals also have zero wins.
All 256 attempts finish; **no games fail or go missing**.

These intervals resample whole game seeds within each fixed initializer. They
describe these two frozen players, with one sampled trajectory per player/seed;
they do not establish superiority over a population of training initializers.
The earlier development mean of 6.28→9.09 used different seeds. Do not compare
that 9.09 directly to this 8.86 and call it a regression. The valid fresh comparison
is 7.29→8.86 on matched seeds.

The best trained game in this confirmation reaches floor 17; **none completes an
act or wins the full game**. The older sampled TRAIN run reaching floor 27 / one
act stays separate. This is evidence that learning transfers to new games, not
evidence of a good full-run player or calibrated terminal-victory prediction.

## Evidence and actual cost

A saved-only audit reconstructs all **32 committed chunks, 256 episode headers
and the comparison**, and checks **28,447 sealed source files**. Player states,
original reports and shared inputs remain unchanged. It decodes no raw trajectories,
plays no games and fits no models. Audit cost: **31.56 seconds / 132.92 MB**.

The owner-run comparison uses two successful resource-tracked sessions totaling
**721.13 wall seconds (12 min 1 s)** and 752.13 CPU seconds. Peak RAM is **971.26 MB**;
retained comparison output **275.79 MB**. No app copies, optimizer updates or
checkpoint promotions occur. The final report's 108.31 seconds describes only
the last session, not the full comparison. No additional training follows.

Source report: `sha256:fadc40d9d80e48e776cc118e54c23c0ed451763d7eceabf95b4cbb7df7ecb487`.
The [machine-readable evidence](evidence/native-policy-confirmation-result-v1.json)
records the exact assessment/resource references and observed endpoints. The
[prospective protocol](native-policy-confirmation.md) remains preserved. Re-running
its completed command verifies saved results and does not play more games.

## Next implementation

Prepare a **bounded continuation of both standard players**, preserving their
learned weights and complete Adam state, under the same 32-game / three-pass recipe.
Continue the round/minibatch randomness schedule rather than silently restarting it.
Use fresh training seeds and separately reserved evaluation panels, excluding all
consumed confirmation seeds from training. Declare a finite horizon, evaluation
milestones, final-only comparison and plateau/resource stopping rule before execution.

This fresh confirmation supplies evidence for testing more training; it is not
a promise that more games will produce wins. Reuse the qualified worker/trainer
and perform only the short continuation checks needed for the new recipe. Do not
insert another unrelated mechanics sweep or repeat this completed confirmation.
If continued progress plateaus, prioritize action credit or qualified actual-engine
teachers. GA and other difficulties remain deferred, and adaptive thinking still
requires the full policy/value/calibration/search readiness evaluation.

#143 / #35 / #146 remain open. No continuation recipe or new long task is launched
in this assessment; the next package must make that finite experiment reviewable.
