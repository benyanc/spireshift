# Baseline-preserving rich correction

The previous rich linear model penalized simple and rich columns together and predicted
saved games worse than the current coarse ridge. This control keeps that original ridge
algorithm intact and asks whether additional public information can improve its residual
errors. It changes a possible **training baseline**, not either actor or its optimizer.

## Predictor and separate regularization

For public state `s`, use:

`B(s) = fixed_progress_potential(s) + original_20_features(s) @ coarse_weights`

`V(s) = B(s) + centered_standardized_rich_features(s) @ correction_weights`.

The coarse weights come from the existing `fit_baseline` implementation with its unchanged
lambda **0.001**, unpenalized bias and equal mass per complete game. Preserve game/row
order and verify the outer-fit coefficients bit-for-bit against the old cache. The rich
fit cannot alter or penalize those coefficients. There is no extra correction intercept.

Fit correction weights only on the extra 1,024 public columns, minimizing:

`mean_game(mean_choice((B + rich_correction - observed_return)^2))
 + rich_lambda * squared_norm(correction_weights)`.

The coarse fit's penalty is fixed during correction fitting and is not included in this
reported correction loss. Keep pure prediction MSE, clipped MSE and correction penalty
separate. Fit rich means/scales/centering only on fitting games, with scale floor 0.25
and standardized clipping to [-4, 4]. Solve the ridge equations directly and check their
numerical residuals. No neural initialization, Adam or epochs enter this experiment.

The explicit **no correction** candidate returns `B` directly. It is not approximated by
a large penalty. It also refits no unnecessary rich model after selection. Both forecasts
follow the prior comparator's raw matrix-product convention, clipped to [0, 1] for the
primary error metric. The production helper's per-row summation can differ by roundoff;
no production helper or clipping rule is edited.

Baseline preservation means keeping the coarse coefficients/algorithm intact. It does
**not** guarantee the combined predictor will beat it on new games. Rich columns can
correlate with coarse signals; this test does not prove a causal explanation for prior
models' failures or impose a constraint on how far an actor may learn to change.

## Nested whole-game validation

Reuse the same 128 saved ordinary TRAIN games, four separate player/round cohorts and
16 outer folds. Each fold fits 24 games and withholds eight. Never mix states from the
same game across fitting and validation or pool different behavior policies as one player.

Within each outer fitting set, use the same three whole-game folds as the previous linear
study: **16 fit / eight validate**, covering all 24 once. For each inner split:

1. Fit a fresh original coarse ridge on that split's 16 fitting games.
2. Compute its residual labels on those fitting games, fit rich normalization there,
   and solve the fixed rich-lambda grid: `1e-6, 1e-5, .0001, .001, .01, .1, 1, 10, 100`.
3. Score each correction and no correction on the eight inner validation games.

Choose by equal-game clipped validation MSE. Exact ties prefer no correction; ties among
positive penalties prefer stronger shrinkage. Refit the coarse baseline on all 24 outer
fitting games, then only the chosen correction, and score the eight outer held games.
The cached outer-fit forecast is checked **after selection**, never used for inner offsets
or residual labels. Outer-held answers cannot change selection, scaling or coefficients.

The existing dictionary was selected from outer-fitting public inputs in the prior study;
it is frozen, excludes outer-held inputs and is **not rebuilt within inner splits**.
Inner selection is conditional on that inherited schema. The same development games have
already informed our hypotheses, so this is not untouched confirmation. Overlapping
folds are not independent training replications. Rare successful outcomes retain equal
game weight and remain in the official denominator.

## Scope, preservation and execution

The target is the existing whole-game **auxiliary bootstrap return**, not victory
probability. The loaded objective still makes full-run victory primary under the fixed
whole-run computation budget. No health/upgrade rewards, action restrictions, new games,
engine processes, app copies, actor changes or Adam updates are introduced.

Versioned recipes and source hashes bind a one-fold short control and a 16-fold cached
comparison. Each complete outer fold saves its selected model arrays, inner validation
curves, outer forecasts, numerical residuals and source seals. Clean restarts verify and
reuse completed folds; interrupted or changed evidence is preserved and refused. A
saved-only verifier reconstructs selected forecasts, selections, fitting errors and
separate penalties without refitting. Both players and all their saved Adam states are
protected through inherited source seals before and after each stage.

The wrapper reads workspace/caps from the recipe. Use one numerical thread, 2 GB memory
and 500 MB new output. The short control is capped at four minutes; the full resumable
recipe at 15 minutes per launch. Codex runs only work expected under five minutes, using
measured control timing and a short external cap when appropriate. The owner runs any
long collection/training. No next experiment or checkpoint promotion follows automatically.

Only a supported frozen candidate can advance to fresh whole-game forecast confirmation
and then a bounded matched action-credit/gameplay test from both preserved players and
full optimizer states. If this control adds no useful signal, return to the action-learning
bottleneck rather than continuing an open-ended critic search. Readiness still precedes
adaptive thinking; other difficulties and GA remain deferred.

## Completed development result

The real-input control passes in **24.97 seconds**; its numerical fold takes 0.94 seconds.
That supports running the complete cached comparison as a short job, with an external
four-minute cap. All 16 outer folds finish in **44.27 seconds** (28.16 CPU seconds,
730.07 MB peak RAM, 4.49 MB output), without any cap hit.

| Predictor | Equal-game withheld MSE | Change from current baseline |
| --- | ---: | ---: |
| Current coarse ridge | 5.512797865e-5 | Reference |
| Baseline plus selected rich correction | 5.532921364e-5 | +0.365% |
| Previous jointly penalized rich linear model | 6.390337021e-5 | +15.92% |

The nested selector chooses **no correction in 10/16 folds**, lambda 100 in four and
lambda 10 in two. Two cohort means improve slightly and two worsen. All 16 outer coarse
coefficient arrays and raw forecasts reproduce the old cache **bit-for-bit**. Keeping the
simple predictor intact avoids the earlier large regression, but supplies no useful
development improvement. This is not a claim that every rich representation is useless
or that shared regularization alone caused the previous gap.

The rare Act 1 clear still contributes a large error. Its MSE is 0.00386318 for the
baseline and 0.00386690 with correction. A post-hoc sensitivity calculation on the other
127 games is 2.51433e-5 versus 2.53169e-5. The primary result retains **all 128 games**;
neither outcome group determines lambda, model selection or adoption. These summaries
reuse development data and do not establish a significant difference between methods.

**Keep the current predictor in training.** No candidate is promoted and no new gameplay
experiment is warranted for this correction. The saved-only check reconstructs all 16
models/forecasts bit-for-bit and verifies inner selections, fitting errors and penalties
without fitting. It takes **27.62 seconds**, verifies **11,755 protected source files**
and confirms both players and full Adam states unchanged.

Full repository verification passes **1,904 tests**, including 18 new regression cases,
strict types on 381 source files, formatting/lint and the C# protocol contract. It takes
**113.76 wall seconds / 100.97 CPU seconds**, with **399.16 MB** peak RAM and no cap hit.
The controls cover original-baseline equivalence, independent penalties, planted rich
signal learning, a no-signal off selection, whole-game ownership, held-answer isolation,
equal game mass, source corruption, interruption preservation and sealed resumption.
Saved-only verification is also tested; neither it nor ordinary resumption refits work.

The next priority is more informative **action learning**, using the already completed
diagnoses. The first combat teacher has 78.1% tied comparisons and zero admitted
preferences from fight-entry roots. A revised finite pilot should predeclare more
consequential later-turn positions or coherent turn choices, preserve uncertainty/world
ownership and use the unchanged whole-run return. Do not lower confidence gates merely
to obtain labels or relabel dependent teacher branches as fresh ordinary PPO data.
Any ensuing supervised/credit intervention must use separate forks from the preserved
players and Adam, then fresh whole-game gameplay comparisons at equal compute. A compact
shared entity representation remains an optional later control, not another prerequisite
for returning to action learning. No further task starts automatically.

The complete implementation and this cached test require **no owner rerun**. For
historical reproduction, the wrapper is `scripts/compare-native-residual-value-v1.sh`
(`--control` selects the control, `--verify` reconstructs saved results). Reusing the
completed main workspace verifies and displays results; it does not refit or play games.
See [portable evidence](evidence/native-residual-value-v1.json) and [backlog](backlog.md).
