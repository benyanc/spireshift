# Completed structured-input comparison

The restart resumed the saved experiment correctly and completed **323/323 sealed
units and 640/640 attempts**, with **zero failed or missing games**. All seven
gameplay sessions completed within their caps; the separate initial session was
offline preparation. No work needs to be repeated.

The experiment contains **384 sampled training attempts and 256 frozen evaluation
attempts**. Each of the six trained copies received 64 training games, not 640.
There are 64 training worlds and 32 separate evaluation worlds, shared across
methods and the two fixed parent players. Finals were frozen before evaluation.

## Fresh full-game results

Terminal victories remain primary: **every method wins 0/64 evaluation attempts**.
Zero observed wins do not establish a zero true win probability or equivalent policies.
The following are auxiliary progress measurements, pooled equally over both parents:

| Version | Average floor | Total completed acts across 64 games | Average CPU seconds/game |
| --- | ---: | ---: | ---: |
| Original, without new training | 11.453125 | 2 | 2.68 |
| Further PPO, unchanged inputs | 11.3125 | 0 | 2.55 |
| Further PPO, hashed supplement | 11.78125 | 1 | 3.04 |
| Further PPO, named supplement | 11.390625 | 3 | 3.11 |

| Fixed parent | Original | Unchanged inputs | Hashed supplement | Named supplement |
| --- | ---: | ---: | ---: | ---: |
| 2, average floor | 11.78125 | 11.59375 | 12.4375 | 11.78125 |
| 3, average floor | 11.125 | 11.03125 | 11.125 | 11.0 |

The primary comparison, **named minus hashed**, is **-0.390625 floors**, with a
paired 95% interval **[-1.15625, +0.34375]**. Named minus original is **-0.0625**,
interval **[-1.03125, +0.859375]**. Hashed minus unchanged inputs is **+0.46875**,
interval **[-0.203125, +1.171875]**. These floor intervals include both improvement
and decline. The extra completed acts are sparse; the named-minus-hashed mean act
difference is +0.03125, interval [0, 0.078125]. Its bootstrap-return difference also
has an interval crossing zero. They do not establish a useful improvement.

Intervals resample the 32 shared worlds jointly across the two fixed parents.
They do not describe the population of possible training initializations. The
all-zero win-difference bootstrap interval is degenerate because no wins were observed;
it is not evidence that the true difference must be zero.

**Giving these selected facts separate columns has not demonstrated stronger play.**
There is also no statistically clear floor regression. Do not promote the hashed
method just because its point estimate is highest, or tune and retest on these worlds.

## What the checks establish

The saved-only audit verifies **32,677 source files / 323 units / 640 games /
95,266 decisions**. It reconstructs outcomes, scores, denominators and paired tables;
all six initial imports preserve every inherited weight and Adam moment exactly.
All **64 initial player/world groups** have identical native public/action traces
across the three methods. The audit reuses sealed native delivery and probability
checks; it does not rerun native effects or policy inference.

There are **55,642 training decisions across 14 families**, and **1,314 actual
optimizer steps**. Updates were not skipped. The four wider actors have nonzero
new input weights after fitting: 33,099/33,792 named parameters in each parent,
and 21,747 / 21,780 hashed parameters. Their inherited parameters also changed.
These checks establish that fitting reached the additional inputs; they do not
establish that the learned changes are useful.

Both original full-state files remain byte-identical at Adam counters **5,658 /
6,045**. Experimental copies retain complete weights and optimizer state. The
native engine, objective, bootstrap score, credit baseline and pinned collector
sources remain unchanged. No app copies, model promotion, readiness pass or adaptive
controller followed.

The owner-run gameplay sessions total **3,610.59 wall seconds (60.18 minutes)**,
3,717.85 CPU seconds, **1.12 GB peak resident memory** and **1.052 GB final main
artifacts**. Storage is the last cumulative workspace size, not a sum of session
snapshots. The initial offline session is separate. The saved-only audit takes
**30.49 wall seconds**, creates no games and performs no optimizer updates.
See [portable result evidence](evidence/native-structured-input-comparison-result-v1.json).

Repository verification after the assessment passes **2,321 tests (four skipped)**,
strict types on 476 source files, formatting/lint and the C# protocol contract in
**137.88 wall seconds**. Receipt:
`artifacts/resources/native-structured-result-repository-check-v1.json`,
`sha256:c618c778af60c7d3029cdc57b2b3499554cb78a18db7a8c7366c65666a9db625`.
No runtime, collector or training recipe was changed for this assessment.

## Interpretation and next work

This tests a **1,024-fact supplement**, with the original compressed encoder retained.
It is not an exhaustive explicit representation of every card interaction or state.
Named and hashed methods have equal size. Hashed versus unchanged inputs also changes
redundancy and conditioning, so it is not a pure hidden-network capacity experiment.
Different policies reach different inputs; unfamiliar-fact occurrence counts are
coverage diagnostics, not a matched test of which representation understands more.

The result does not isolate the cause of stalled learning. Limited independent
experience, useful exploration, the shared credit predictor, optimization and
representation remain possible contributors. No variant received positive full-win
training labels. More input columns alone did not fix those shared limitations.

The next agreed factor is **state-only value/credit prediction**, kept separate from
action selection. First use the newly saved TRAIN games to check whether the current
predictor distinguishes strategically different decks, relics and combat resources,
and whether a regularized public-state alternative predicts entirely withheld games
better. Keep fitting/selection within whole training worlds, behavior policies
separate, and evaluation worlds out of fitting. Report prediction errors and the
resulting action-credit/gradient signal separately. A useful prediction candidate
then needs a bounded matched fresh-game learning test from both preserved originals.

The [earlier rich neural/linear studies](native-linear-value.md) and
[baseline-preserving correction](native-residual-value.md) already failed to improve
their development forecasts. Preserve those results: do not repeat their grids or
silently adopt their rejected predictors. The new diagnosis must identify a material
change or useful new evidence before another predictor/gameplay experiment. Better
prediction alone still does not prove a better player.

Larger or more varied experience, a separate wider hidden network, qualified teachers,
and GA remain later alternatives. No larger training launch is authorized by this
result alone. The [preparation and owner command](native-structured-input-comparison.md)
are historical; rerunning the completed command only verifies/displays its saved result.
