# Native A8 credit comparison: completed, no clear gameplay gain

Both methods finish **336/336 ordinary endings**, with zero failed/missing games, wins or
completed acts. The new value predictor improves return-prediction quality but does not
establish a stronger policy in this experiment. No new games, training, checkpoint selection
or promotion followed the assessment.

## Reserved development games

Each player is evaluated on the same **16 reserved native seeds**, with the same action-RNG
stream per seed and the same frozen Ironclad/A8 game and budget. Repeating the initializer
across the two methods does not create another independent 16 seeds.

| Player | Wins | Average floor | Best floor | Completed acts |
| --- | ---: | ---: | ---: | ---: |
| Original initializer | 0/16 | 7.0625 | 11 | 0 |
| Old-credit trained player, round 4 | 0/16 | 7.1875 | 14 | 0 |
| Cross-fitted-credit trained player, round 8 | 0/16 | 7.1875 | 11 | 0 |

Both trained players gain just **0.125 average floors** versus the initializer. Exploratory
95% paired-seed bootstrap intervals include zero:

- Old credit minus initial: **[-0.8125, +1.0000] floors**.
- New credit minus initial: **[-0.6250, +0.8750] floors**.
- New credit minus old credit: **0.0000**, interval **[-0.8750, +0.9375] floors**.

These are 10,000 fixed-seed resamples of the 16 development pairs, not independent training
replications. Exact marginal win-rate intervals for 0/16 extend to 20.6%; zero observed wins
does not prove a zero underlying win probability. This small experiment supports neither
useful improvement nor equivalence of the two methods.

The official bootstrap score is nonlinear in progress, so identical mean floor does not mean
identical score or trajectories. The new trained player's mean auxiliary score is 0.0191370,
old trained is 0.0190379, and initial is 0.0189310. These small auxiliary differences do not
establish terminal-victory improvement. No checkpoint is promoted using this inspected panel.

## What the experiment establishes

Both arms have the same actor, original numerical initializer, training seeds, sampling rules,
PPO settings and resource caps. Only the actor-return baseline changes. The realized number of
decisions and updates differs because the two policies produce different trajectories:
**26,061 training decisions / 627 steps** for old credit, **25,917 / 615** for new credit.
This is equality of collection/update rules and caps, not identical realized optimizer work.

The training runs use 256 shared native seeds per method, 512 trajectories altogether. Each
method is trained once. All 64 shared initial-policy traces match exactly across methods:
16 initial confirmation, 16 initial development and the first 32 training games. This verifies
that the arms began from the same player and behavior, not merely similar summary scores.

Confirmation chooses the old method's round-4 model and the new method's round-8 model under
the original full auxiliary score, not rounded mean floor. The audit reconstructs these choices
and verifies the separate best-trained/retained-incumbent freeze before development. Unlike
v5's old report, this development result genuinely tests trained models. Confirmation progress
does not by itself generalize: old credit's confirmed mean rises from 6.875 to 8.3125, while
new credit reaches 8.1875, but both average only 7.1875 on development.

The new cross-fitted baseline has positive choice-bearing explained variance in all eight
training rounds, ranging from approximately **0.000065 to 0.392**. Its mean per-round squared
prediction error is about **51% below the diagnostic hashed critic** on its own training
trajectory distribution. Round 7 is effectively zero explained variance, so this is not
uniformly strong prediction. Saved report identities, fold ownership and update bindings
verify; predictions are not refitted in this outcome assessment. These are value-estimation
results, not proof of better action credit or a calibrated win-probability model.

## Execution and audit

Including resource wrappers, old/new arms take **928.36 and 921.99 seconds**, approximately
**30.84 minutes total**. Retained artifacts total **607.04 MB** (304.51 + 302.53 MB); peak memory
is **2.095 GB**, and both create **zero game-app copies**. All protected-input/profile checks pass.
The best game anywhere in either complete collection reaches floor 17 with no completed act.

The saved-only audit verifies every episode, trace seal, public-input/action identity, native
ending, worker delivery evidence, source-at-launch hash, checkpoint chain, seed ownership,
selection freeze and summary denominator. It checks **2,866 source files**, inspects **68,929
recorded decisions** and finishes in **13.68 seconds**, with no engine replay or optimizer.
Its code and private outputs are pinned in the
[evidence record](evidence/native-a8-credit-comparison-result-v1.json).

## Next work

The value-baseline change alone has not solved learning. Keep it as a separately measured
candidate, preserving both results and all historical source bytes. Next is **#143's short
input-normalization and duplication controls**, using saved TRAIN examples to measure saturation
and conditional learning while retaining entity ownership, current amounts/costs, public memory
and every legal action. Then freeze a one-factor native comparison only if those controls pass.

The remaining weak agreement of independent-run gradients also warrants a measured batch-size
control. More optimizer steps are not more independent outcomes. Shorter-trace bootstrapping
still needs explicit bias/variance evidence; it is not automatically enabled by lower value
error. Other difficulties, larger unchanged training/GA batches and adaptive thinking stay
deferred. Full-run wins and base readiness remain unmet.
