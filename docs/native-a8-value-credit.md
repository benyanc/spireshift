# Native A8 value prediction and action credit

The next experiment changes the prediction subtracted from each action's final run score.
The new predictor passes saved-data accuracy controls. Its effect on gameplay remains unknown.
All v5 sources, game traces, checkpoints and optimizer states remain intact.

## What is implemented

The actor still learns every supplied legal action from the complete public entity graph.
Its architecture, initialization, PPO settings, objective, bootstrap score and compute caps
are unchanged. A separate small training baseline uses 20 fixed, bounded public state features:
progress, health, resources, decision family and observed combat amounts. It predicts the
declared bootstrap run return, **not terminal win probability**. This deliberately limited critic
does not limit the actor's mechanics coverage or action space.

Each 32-game training batch is divided into four folds of whole games. A ridge predictor fits
the other 24 games, then supplies predictions for the eight excluded games. A game's own final
outcome never fits the predictor used to credit that game's decisions. Fitting gives each game
equal weight, regardless of its length. The two-game pipeline control uses two folds instead.
Fold membership, fitted coefficients, prediction errors and report identities are saved per round.

Actor credit is the original final return minus this independently fitted prediction. The
checkpoint's existing hashed critic continues the same diagnostic update for compatibility;
its predictions no longer supply actor credit in the new variant. Saved behavior probabilities,
chosen actions and critic targets still reconstruct exactly before credit is replaced. No
trained v5 weights are loaded into a new experiment.

The integer-zero Adam-rate defect is also fixed and regression-tested: a zero critic rate no
longer truncates a fractional actor rate. V5 used floating-point rates, so this did not cause
its earlier result.

## Saved-data evidence

The study verifies **256 training runs / 26,061 decisions**, with the old source, seed and score
seals checked. Four fixed regularization values are compared. Rounds 1–4 choose the setting;
rounds 5–8 audit it. Every prediction excludes the credited whole run, including in the later
rounds. The later control is within-round cross-fitting, not transfer of one frozen predictor
to a new policy. Confirmation and development episodes are never opened.

Errors below give each whole run equal mass, then average choice-bearing decisions within it:

| Predictor | Mean squared error, rounds 5–8 |
| --- | ---: |
| Cross-fitted constant | 0.000015280 |
| Old behavior critic | 0.000027209 |
| Selected public residual ridge, regularization 0.001 | 0.000010439 |

The new predictor's error is **31.7% below the fitted constant** and **61.6% below the old
critic**, with lower error than the constant in all four audit rounds. Its per-round explained
variance is positive throughout the eight rounds. These are auxiliary-return prediction results
on historical training data, not better win rates or calibrated full-run victory estimates.

A separate exact actor-gradient reconstruction on rounds 1 and 8 gives a mixed result. It
subtracts the production batch mean, omits entropy and the common advantage scale, and uses
100 fixed correlated half-batch resplits. In round 1, the new baseline raises median gradient
agreement from 0.127 to 0.257 and lowers the opposing-half fraction from 14% to 8%. In round 8,
it lowers raw gradient variance but **worsens** median agreement from -0.049 to -0.162; opposing
halves rise from 64% to 81%, and the descriptive signal/noise proxy falls from 0.874 to 0.702.
Lower prediction error alone is not proof of a better policy update. These resplits are not
independent training replications or a population confidence interval.

The saved-data study takes **12.79 seconds**; the gradient control takes **22.78 seconds**.
Two fresh four-game integration controls each pass: **8/8 ordinary losses, zero failures,
456 verified training decisions, 12 total PPO updates**, both actor and diagnostic critic
changed, saved action credit reconstructs, immutable checks pass, and zero app copies. Their
different two-game post-update floors do not establish stronger play. Including resource
wrappers, the controls take **23.37 and 22.58 seconds**, retaining about **14.8 MB combined**.
The full repository check passes **1,447 tests**, formatting, static types and the C# build
in **58.51 seconds**. The earlier test-annotation failure remains preserved in its resource log.

The [evidence record](evidence/native-a8-value-credit-v1.json) binds the private reports,
implementations, source seals, controls and resource measurements. The initial wrong-stage
command was rejected before launching any game; that failed resource report is preserved.

## Credit redistribution and objective checks

The implementation also tests public-progress potential differences with discount exactly one
and an absorbing terminal potential of zero. Their sum is the original terminal return minus
the initial public potential. Repeated menus, skips and return loops cannot manufacture reward;
no immediate HP, card-taking or room-count bonus is added. Synthetic loss, victory, later-act
and invalid/partial-run tests pass; all 256 saved runs pass the telescoping check.

Transforming both rewards and values consistently makes full-trace credit exactly equal to
the original return minus value. Potential redistribution alone therefore does **not** solve
the delayed-credit problem. A shorter-trace GAE calculation is implemented and tested, but is
not enabled in any admitted recipe: it introduces value-bootstrap bias. The next comparison
uses discount 1 and lambda 1, changing only the baseline estimator.

## One owner-run comparison

Run this single command after closing any open game:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/compare-native-a8-credit-v1.sh
```

It runs the old and new credit methods sequentially: **336 games each, 672 total planned
attempts**, eight rounds of 32 training games per method. Both start from the same original
seeded actor and zero optimizer state. Training seeds, action RNG, architecture, objective,
PPO update settings and compute caps match. The only treatment is the actor's return baseline.
Confirmation and development use fresh reserved native seeds shared across the two methods.
The old training seeds are intentionally reused for this controlled development experiment.

The best **trained** checkpoint is chosen on confirmation before any development game. The
retained incumbent is recorded separately and may still be the initializer. Development compares
the initializer with the best trained player, so a rejected update cannot turn the entire
evaluation into another starting-player self-comparison. Each method has only one training
replication and 16 development seeds; this pilot can guide the next change, not establish a
robust winning system.

Expect **25–40 minutes total** from v5 timings, with a hard **30-minute cap per method**.
Each method uses two isolated workers, at most 4 GB memory and 4 GB output. Both reuse the
frozen game and shared support-code cache; no game app is copied. About 0.6 GB combined retained
output is expected, not guaranteed. Each batch reports wins, average floor, best result and
failures. Failed games retain the original denominator and never supply training targets.

Both controls and read-only admission/preflight checks pass. The long comparison has **not
started**. Completed arms are preserved and skipped on rerun; unfinished evidence stops for
inspection. No adaptive controller, promotion or subsequent experiment starts afterward.
After the results, assess the paired trained-player outcomes and round-by-round prediction
quality before deciding on representation normalization, larger independent batches or GAE.
