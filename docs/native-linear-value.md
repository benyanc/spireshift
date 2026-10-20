# Regularized rich-input linear values

The completed matched-input neural experiment predicts other games worse than the current
20-feature ridge: **7.1256e-5 versus 5.5128e-5** equal-game MSE at the fixed primary update.
Its pure fitting error improves while withheld error worsens. Most of the combined loss
reduction is a smaller weight penalty. Keep that experiment, its negative result, both
players and all Adam states unchanged. A simpler model removes neural initialization,
epoch count and Adam as explanations for the next comparison.

## Predictor and objective

For public state facts `x`, predict the declared whole-game **bootstrap return** as
`V(x) = progress_potential(x) + intercept + standardized(x) @ coefficients`.
This is an experimental credit baseline, not a win probability or an action score.
Terminal full-run victory under the fixed computation budget remains the primary objective.

Fit equal total weight per complete game and equal weight per genuine choice within it:

`mean_game(mean_choice((V - observed_return)^2)) + lambda * sum(coefficients^2)`.

Fit means/scales and the post-clipping center on fitting games only. Use the prior
normalization floor of 0.25 and clip standardized inputs to [-4, 4]. The intercept is
unpenalized. Solve the ridge normal equations using a shared eigensystem for a fixed
grid, checking numerical residuals. There are no random initializers, optimizer moments,
training epochs, strategic reward adjustments or actor changes.

## Whole-game validation

Reuse the sealed cache from the completed matched experiment: 128 ordinary TRAIN games,
four separate player/round cohorts, four outer folds per cohort. Every outer fold has
24 fitting games and eight withheld games. Do not pool different behavior players or
rounds into one fitted value function.

Within the 24 fitting games, use three deterministic whole-game folds: fit on 16 games,
validate on eight, covering all 24 validation games exactly once. For **each arm separately**,
select lambda by equal-game clipped validation MSE over the fixed grid
`1e-6, 1e-5, 1e-4, .001, .01, .1, 1, 10, 100`. Exact score ties select stronger shrinkage.
Refit on all 24 fitting games, then evaluate the eight outer withheld games.

Compare:

- Current fixed 20-feature ridge, unchanged.
- Tuned coarse linear ridge with the extra public columns masked.
- Tuned rich linear ridge using the same cached public columns.
- Other-fitting-game constant reference.

Both linear arms use the same inner splits, normalization rules, potential and lambda
grid. Report pure fitting MSE, validation MSE, clipped errors and weight penalty
separately. Save the selected model arrays and outer predictions. Outer targets cannot
select lambda, normalization, input columns or stopping. Do not scan outer error across
the lambda grid. The cached outer-fit ridge is a comparison only: using it as the inner
offset would leak inner-validation returns. The new fits use only fixed progress potential.

## Scope of dictionary reuse and conclusions

The bounded public dictionary was fitted on each **outer-fitting** population in the prior
study. It excludes outer-withheld inputs. This experiment freezes those cached schemas;
it does **not** rebuild vocabulary selection within inner folds. Inner validation therefore
selects regularization conditional on an existing outer-training schema. Its means, scales,
centers, slopes and intercepts still use inner fitting games only. This is not a claim that
an entirely new input-discovery pipeline was fitted independently within every inner fold.

The same 128 development games have already informed our choices. Nested splits prevent
row-level mixing and outer-target tuning inside this experiment, but cannot make reused
development games an untouched confirmation set. A supported candidate needs a frozen
recipe and fresh whole-game forecast confirmation before a bounded gameplay/credit test.
Better prediction does not by itself demonstrate stronger play, victory readiness or a
useful adaptive thinking controller. Overlapping folds are not independent experiments.

## Execution and saved evidence

`configs/native-controls/linear-value-control-v1.json` runs one real 24/8 fold. The main
recipe covers all 16 outer folds and requires that matching short-control receipt. Both
verify the parent report, source histories, encodings, original players and full Adam states
before and after execution. Every outer fold is independently sealed and restartable.
Changed or uncommitted evidence is preserved for inspection; no overwrite or automatic
replay. Each clean pause writes a distinct progress snapshot.

The wrapper reads its workspace and resource caps from the pinned recipe, uses one numerical
thread, and records each launch separately. It creates no game app, re-encodes no histories,
launches no games and performs no automatic promotion or follow-up training. Maximum main
launch: 15 minutes, 2 GB RAM, 500 MB output. The owner runs work expected to take five
minutes or more; short controls and sufficiently fast cached stages are agent-run.

## Completed result and verification

All 16 outer folds / 128 held-game predictions are complete in **84.96 seconds**,
with 495.50 MB peak RAM and 5.30 MB generated outputs. There are 896 closed-form
ridge solutions, not 896 independent games. Equal-game clipped MSE:

| Predictor | Held MSE | Change from current ridge |
| --- | ---: | ---: |
| Current ridge | 5.5128e-5 | Reference |
| Tuned coarse linear | 5.5328e-5 | +0.36% |
| Tuned rich linear | 6.3903e-5 | +15.92% |
| Other-game constant | 8.1534e-5 | +47.90% |

Rich remains worse in all four cohorts despite stronger regularization. Its selected
lambda is 10 in 11 folds, 1 in three and 100 in two. This is a negative development
result; keep the current credit baseline. It does not prove all rich representations
are useless or that more games alone would fix the generalization gap. Next inspect
error concentration in rare long runs and unseen facts before choosing another change.

The saved-only audit reconstructs all 32 models, lambda selections and fitting-error/
penalty terms; held forecasts agree bit-for-bit. It verifies 11,681 source seals,
including both saved players and every Adam state. No games or refits are needed for
that audit. All 17 focused regression tests pass, including known-signal learning,
normal-equation equivalence, equal-game mass, held-target noninterference, prevention
of leaked outer offsets, restoration, corruption and interrupted-evidence handling.

The owner completed the full repository check on 2026-10-20: formatting/lint, strict
types, the full test suite and the C# protocol contract all pass. It took **116.07
wall seconds / 99.39 CPU seconds**, with **385.27 MB** peak RAM and no resource cap.
Receipt: `sha256:bf55e76c5586d10008893d30f0aaf68c3bcbfd7aae4b5d188f7f937efc80ee33`.
All 11,681 protected sources, including saved players and Adam states, verify unchanged
afterwards. The earlier capped check is preserved separately; it is superseded by the
completed check, not relabeled as a pass. **No rerun is needed.**

Historical full-check entry point — the owner has completed this step:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/verify-linear-value-repository-v1.sh
```

See [the backlog](backlog.md) and [portable evidence](evidence/native-linear-value-v1.json)
for exact report/resource identities and preserved provisional checks. No new player
training or automatic next stage follows this command.
