# Native A8 independent-game gradient and batch checks

Implemented 2026-10-17 under #35 / #146. The checks reconstruct the exact actor gradient at
the player that generated each batch, then ask whether disjoint groups of complete games
recommend similar changes. They do not optimize a player, establish a win rate or promote
a checkpoint. All previous experiments, models, source bytes and admissions stay unchanged.

## What is checked

The saved-data study uses the first and last TRAIN batches from both completed normalization
methods: **four separate 32-game cohorts, 128 games and 12,741 decisions**. The late cohort uses
the player before round eight, not the checkpoint produced by that round. Different behavior
models or rounds are never pooled. No confirmation/development episode is opened or used to
choose settings. Each cohort keeps its exact native environment, score, model and temperature.
There are 64 distinct run seeds across the four cohorts: the two methods reuse the same seed
panels. They are not counted as 128 independent seeds or pooled as one 128-game batch.

For each observed menu, the kernel reconstructs saved action probability and critic value,
then differentiates the chosen action's log probability through every actor layer. Single-choice
menus have zero policy gradient but retain their original role in batch centering/scaling.
No action family or optional choice is removed. The whole-game vectors are combined using the
production full-return, cross-fitted baseline, decision-weighted centering/standard deviation
and temperature of 0.8. The resulting ascent gradient, including the entropy term, matches the
negative gradient of the separate production PPO loss to **2.15e-16 maximum absolute error**
across all four cohorts. The original 32-game baseline folds and advantage moments also match.

This is the gradient **at behavior**, before Adam, gradient clipping or PPO's repeated updates.
It does not reconstruct a multi-epoch optimizer trajectory. Unit controls also check numerical
derivatives in every actor layer, zero/opposed/aligned directions, exploration-dominated
directions, duplicated decisions, mixed-policy/round rejection and the public information boundary.

For each pair of groups:

1. Choose disjoint complete games from one behavior cohort.
2. Fit each group's cross-fitted return predictors using only that group's games. A credited
   game's outcome never fits its predictor; neither group's outcomes fit the other's predictor.
3. Compute centering and scaling separately inside each group.
4. Compare the game-driven gradients and separately the gradients including entropy.

Sharing a predictor or the full-pool advantage mean across both groups would couple their
outcomes and would not be this independent-group check. The earlier shared-baseline resplits
remain preserved as descriptive diagnostics; they are not substituted for the new controls.

## Saved TRAIN results

Each table entry describes 32 fixed random partitions of the same finite cohort. Resplits
overlap across repetitions: they are not new independent games, training replications or
population confidence intervals. Cosine 1 means the same parameter direction, 0 means
perpendicular, and negative means opposed. Zero-norm pairs are explicitly undefined, not wins.

| Behavior cohort | Median data-gradient cosine, 4 games/group | 8 games/group | 16 games/group | Opposing 16-game pairs |
| --- | ---: | ---: | ---: | ---: |
| Unscaled, round 1 | -0.025 | 0.079 | 0.200 | 18.75% |
| Unscaled, round 8 | 0.098 | -0.105 | 0.039 | 31.25% |
| Normalized, round 1 | -0.097 | -0.088 | -0.035 | 53.13% |
| Normalized, round 8 | 0.062 | 0.080 | 0.322 | 12.50% |

Agreement is variable and is not uniformly monotonic in this small observed pool. These results
do not identify an optimal batch size or prove that 32 games cause the gameplay plateau.
Gradients also depend on parameterization, so cross-arm cosine rankings are not player-strength
rankings. Within a pair, the model and parameterization are identical.

The full 32-game exploration-gradient norm is **3.53–9.77%** of the game-driven gradient norm,
and game-driven versus total gradient cosine exceeds **0.997** in all four cohorts. Exploration
does not dominate these full-batch initial gradients. Entropy-only directions agree strongly
across groups, which is why reporting just that agreement would be misleading. This conclusion
does not cover later Adam steps or every small subgroup.

The largest game's share of summed contribution norms is 7.04–11.53%. Contributions cancel
substantially; norm shares are sensitivity diagnostics, not effective independent sample sizes.
Thousands of decisions still come from only 32 independent whole-game outcomes per cohort.

**32-, 64- and 128-game independent-group comparisons remain unmeasured**: a pool of 32 cannot
provide two disjoint groups of 32. The report lists these sizes as unsupported rather than
comparing the full pool with itself or inventing additional games through resampling.

The saved-only study finishes in **58.01 seconds**, using 1.150 GB peak memory and retaining
0.882 MB. It refits diagnostic return predictors but performs **zero actor/Adam steps**, starts
zero games and writes no production checkpoint. Report:
`artifacts/native-gradient/sts2-v0.111.0-a8-independent-v1/report.json`.

## Qualified larger-pool check

The new collector and analyzer pass a separate **four-game / 360-decision control**, with zero
failures, missing games, optimizer steps or app copies. Public input/action delivery and native
endings are audited against worker receipts. Actor gradient error is 4.02e-17 or less. The source
player, candidate, game archive, runtime, SDK and account profile remain unchanged. The control
does not establish policy strength or independent larger-batch agreement.

The next collection freezes the **normalized model before its last training round**, chosen by
declared training phase and numerical conditioning, not development ranking. This is not a
decision that it is the stronger/default player. It plays **256 fresh TRAIN seeds** using the
existing Ironclad/A8 native rules, complete public menus and sampled policy. Four new control
seeds are separate from those TRAIN seeds; no old reserved evaluation seed is reused. Model
weights remain identical from the first game through the last.

Two groups of 128 games can then be observed directly, alongside 4/8/16/32/64-game groups. Each
group again fits its own predictors and advantage normalization. Thirty-two repeated partitions
remain descriptive and correlated, even with a larger pool. This checks whether more independent
games stabilize the direction at this one frozen player, not whether larger-batch PPO learns
better or wins. A later learning comparison still needs equal declared total-game budgets,
actual compute accounting, fresh reserved evaluation and explicit experiment scope.

The collector preserves a failed game and retires its worker with verified shutdown before
moving to the next seed; it never retries that failed seed. Uncertain worker failures stop that
lane. Failures and unplayed games retain the original denominator. Analysis requires **every
planned game** to be clean and audited; it cannot silently drop failures into a smaller pool.

## One owner command

Close any open game, then run:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/check-native-a8-batch-sizes-v1.sh
```

Expected total: **15–25 minutes**. Collection has a **20-minute cap**, two workers and 4 GB memory;
the subsequent saved-data analysis has a **10-minute cap**, one worker and 8 GB memory. Each stage
has a 2 GB retained-output cap, read from the same pinned recipe workspace. Expected retained
output is a few hundred MB; gradient arrays are held in memory, not saved as per-decision files.
Encoded menus are retained for only four games for a separate numeric comparison with the
production PPO loss; all 256 games have their saved behavior probabilities/values verified and
retain score-function derivatives for the batch comparisons. This prevents the encoded-menu
cache from growing alongside the large derivative arrays. The 32-game saved-data study above
checks the production loss on each complete original batch. The current owner recipe is
`sts2-v0.111.0-a8-frozen-pool-v2.json`; the earlier v1 control and unstarted preparation remain
preserved after this memory bound was added. Four control seeds are repeated across the two
control source versions, not counted as eight independent outcomes.
Collection progress reports wins, average floor, best floor and failures every eight games.
The player is frozen, so those progress lines are not a learning curve.

The original frozen game and verified support-code cache are reused with zero app copies.
The script preserves a finished collection and can analyze it without replaying games. An
unfinished collection stops for inspection. Finished analysis is shown without new games or
fitting. **The 256-game collection has not started.** No actor training, model promotion,
adaptive controller or subsequent experiment starts afterward.

The [evidence record](evidence/native-a8-independent-gradients-v1.json) binds the controls,
implementation, private sources and resource receipts. Strong-base readiness and full-run
wins remain unmet.
