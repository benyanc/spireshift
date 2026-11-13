# Saved action rankings and independent prediction: completed result

The inspection is complete: **192 saved games / 22,842 decisions**, covering
32 development worlds shared across two fixed players and three source policies.
It launches no new games. Both original players and their complete PPO Adam
states remain byte-identical, with counters **5,658 / 6,045**. Their four rejected
experimental forks remain preserved too.

The new independent predictor leaves the original action scores and probabilities
**exactly unchanged on every inspected menu**. Outcome prediction now has its own
parameters, readout and Adam state. Prediction fitting cannot overwrite the saved
player's preferences. This control passes; stronger gameplay is not established.

## What happened to the unsuccessful players

The earlier learning experiment changed the original actor's action scores to fit
recorded returns. Both the return-only and extra-consequence versions subsequently
played worse. This inspection measures their scores on identical public menus,
including menus from the unchanged originals' paths.

Each table entry below first averages strategic menus within a game, then weights
the 32 games equally within that fixed player and source-policy stratum. Forced
navigation and single-action menus stay in the source counts but not these rates.

| Original-path diagnostic, original → old consequence fork | Player 2 | Player 3 |
| --- | ---: | ---: |
| Centered action-score RMS | 2.842 → 0.287 | 1.643 → 0.248 |
| Top-two combat score gap | 1.056 → 0.285 | 0.775 → 0.155 |
| Strategic combat menus with a different top action | 42.49% | 49.19% |
| Strategic noncombat choices changed under the same random draw | 27.00% | 25.12% |

The score spread shrinks approximately **9.92× / 6.63×**. Compression alone would
not change the winner of a greedy combat choice: multiplying every action score
by the same positive constant preserves its ordering. Here the ordering changes
as well. Smaller gaps also affect noncombat sampling, where the temperature is
unchanged and the same random draw need not select the same option.

Return-only fitting produces almost the same pattern: combat top actions change
on **42.94% / 49.35%** of original-path menus; score RMS becomes **0.282 / 0.245**.
Comparing the two unsuccessful forks directly changes the top combat action on
**7.49% / 6.64%** of these menus. Their mean combat KL divergence is only
**0.001717 / 0.000854**, versus **0.417943 / 0.395770** for consequence versus
original. Both arms' score compression and ranking disruption therefore have a
substantial common component. These comparisons do not isolate which changed
choices caused the observed full-game losses or prove the extra feedback harmless.

The same qualitative disruption appears separately on each fork's own paths;
these remain separate strata. Menus and related trajectories are not additional
independent worlds. Changed rankings are observations, not labels establishing
which action was optimal. No development outcome is used to fit or select a model.

## What prediction fitting establishes

All nine independent prediction fits are complete: seven whole-source-world
folds and two all-TRAIN fits, with 128 independent Adam steps each. Fitting uses
the same **seven TRAIN worlds / 51 related plans / 442 combat rows**, one fixed
predictor initializer and fitting-only scaling. No original PPO Adam step occurs.

The separate predictor's held-out errors remain mixed. Mean held recorded-return
MSE is **0.00002229** versus **0.00002425** for a fitting-only constant in player 2;
player 3 is **0.00002882** versus **0.00002573**, worse than that constant. Immediate
HP-change errors improve over the constants in both parents, but fitting errors
are much smaller than held errors. Constant potion targets and player 3's constant
survival target provide no evidence of learned discrimination.

These estimates describe recorded action-conditional continuations. They are not
causal action values, full-victory probabilities or an automatically valid
state-only PPO baseline. The differing prediction architecture and optimizer
also prevent a matched claim against historical predictors. There is no new
full-game result from this diagnostic and no checkpoint is promoted.

## Verification and cost

The owner finishes the remaining 186 cases in **371.37 wall seconds / 331.52 CPU
seconds**, with **274.38 MB peak RAM** and **84.98 MB cumulative output**. Including
the earlier six-case check, the finite inspection uses **418.14 wall seconds**.
Cumulative storage snapshots are not added together. There are no game-app copies.

A separate **19.22-second saved-only audit** checks **73,988 sealed source files /
201 completed units**, restores the nine independent predictor/Adam states without
fitting, and rebuilds every numeric-history summary and equal-game stratum. It
counts **12,549 strategic combat / 4,941 strategic noncombat menus**, plus all
single-option and forced-navigation records. The collector's exact original-score,
probability and recorded-choice replays remain sealed. This result audit does not
independently rerun neural inference or native delivery.

The fresh repository check passes **2,216 tests (four skipped)**, strict types on
443 files, formatting/lint and the C# protocol in **225.97 wall seconds**. The
first attempt reaches its 240-second wall cap and remains preserved as capped,
not passed. The single-thread numerical retry completes within that same cap.
Exact receipts and evidence seals are recorded in
[the result evidence](evidence/native-action-prediction-separation-result-v1.json).
The [preparation and six-case sample](native-action-prediction-separation.md)
remain historical; their owner command has finished.

## Next learning work

1. **Declare and test an actor-learning objective separately from prediction.**
   Reuse the existing PPO implementation where appropriate; verify that known
   positive/negative action advantages change relative choice probabilities in
   the expected direction, that common score shifts have no effect, and that
   outcome-only fitting gives the actor no gradient. Do not repeat raw actor-score
   regression just because its fitting MSE is small.
2. **Prepare one bounded, matched on-policy learning comparison.** Start copies
   from both original players with every saved Adam moment preserved. Keep all
   legal decision families learnable. Use fresh sampled full-game experience,
   exact behavior probabilities and the declared full-run bootstrap score. Retain
   an unchanged-original control and freeze any update before fresh full-game
   evaluation. The old greedy development games and privileged teacher branches
   are not ordinary PPO experience. A state-only, action-independent baseline
   must be qualified separately if used; this action-conditional predictor does
   not silently replace it.
3. **Judge the result by fresh full games.** Preserve terminal victory as primary
   under the 128-CPU-second whole-run budget. Floor gains remain auxiliary.
   Prediction error, score spread and ranking change diagnose learning; none is
   a standalone promotion gate. Do not impose historical combat-only or permanent
   proximity restrictions, or start an adaptive controller before base readiness.

This assessment starts no new learning recipe, parameter fit or gameplay batch.
There is no owner command to rerun at this stage. GA and other difficulties remain
deferred. No push or GitHub Actions follows.
