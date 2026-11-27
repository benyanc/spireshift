# What the saved value-prediction errors show

The current small predictor remains the best tested baseline. The negative rich-model
result has more than one cause worth investigating; the evidence does not justify
another unchanged training batch or simply increasing the neural network size.

This audit reads **128 ordinary TRAIN games / 13,793 choice-bearing states**, across
two saved players and four behavior-policy/round cohorts. Every reconstructed public
input agrees exactly with its original cached coarse and rich columns. It uses the
saved outer-held forecasts, averages neural-repeat **errors** rather than creating an
ensemble, and reconstructs every published equal-game MSE. No value fitting, actor
training, game attempts, optimizer updates, app copies or promotion occurs. Both players
and all Adam states remain unchanged. Evaluation histories are not decoded.

## A rare good run dominates the headline error

Only **one of the 128 games** clears Act 1: it reaches floor 21 and loses. That game
accounts for **54.75%** of the current ridge's total squared prediction error. Its 24
fitting games contain **zero act clears**. Its full-game auxiliary return is 0.097973;
the current ridge predicts about 0.020875 during floors 1–5, 0.033101 during late Act 1,
and 0.096063 after the run has entered Act 2. These are bootstrap-return forecasts,
not win probabilities.

The largest error therefore occurs **before the eventual success**, not because all
observed Act 2 states are inexplicable. After entering Act 2, the declared fixed public
progress offset already reflects the completed act. This is consistent with sparse
examples of future advancement and noisy early-game returns. One successful trajectory
does not prove its future was predictable from early public information.

Removing this game is a diagnostic sensitivity analysis, **not** a new evaluation rule:

| Saved held-game population | Current ridge MSE | Rich linear MSE | Rich neural MSE |
| --- | ---: | ---: | ---: |
| All 128 games | 5.5128e-5 | 6.3903e-5 | 7.1256e-5 |
| 127 games without an act clear | 2.5143e-5 | 3.2699e-5 | 4.1541e-5 |

Rich linear remains **30.05% worse**, and rich neural **65.21% worse**, on the other
127 games. The rare run does not explain the rich models' disadvantage. Keep every
game in the official denominator; do not reduce the importance of successful outcomes
or change terminal victory as the binding objective.

A metadata-only check of the full 512-game TRAIN collection finds **five act-clearing
trajectories and zero wins**. These belong to different behavior policies and must not
be pooled as one unchanged player's on-policy value data. Their number also does not
establish five independent successful game seeds across the exploration arms.

## Familiar details are often excluded from the critic's dictionary

Compared against each game's own 24 fitting games, the equal-game mean of per-state
public fact-occurrence fractions is:

| Public fact category | Fraction |
| --- | ---: |
| Represented by the 1,024-coordinate dictionary | 11.95% |
| Seen in fitting, varying, but omitted | 74.01% |
| Seen in fitting, constant, and omitted | 7.70% |
| Never observed in fitting games | 6.34% |

These are **encoder fact counts, not percentages of game information**. The encoder
produces many redundant and owner/text-specific coordinates, while shared features can
convey several facts. Constant facts often deserve omission. This audit does not prove
that any particular omitted fact is necessary for prediction or that keeping all facts
would help with only 24 fitting outcomes per fold.

The distinction nevertheless matters: most omitted occurrences were **already seen and
varying**, rather than newly introduced by the held game. About 59.03% of observed public
definition occurrences have no explicit identity-specific coordinate in the selected
dictionary; indirect descriptive or numerical signals may still distinguish them.
Definition measures count each distinct definition ID once per state, not every card copy.
This concerns the experimental **critic** representation, not missing engine mechanics
or proof that the actor cannot observe those public entities.

About 7.17% of the unique public entity definitions within a typical state were unseen
in that fold's fitting games. States containing at least one unseen definition account
for a game-weighted 57.68% of choices. Entirely unseen decision families are much rarer:
0.0565% of choice states under the same weighting. New entity types and new decision
families are different measures of unfamiliarity.

On the 127 non-clearing games, unseen-definition fraction has a descriptive game-level
Spearman correlation of **0.271** with current-ridge error, but only **0.064** with the
rich linear model's excess error. Novelty also varies with run length and content.
The rich model loses in every unfamiliar-definition bucket, including states where all
observed definition IDs were seen in fitting. These conditional buckets include
overlapping game populations; their MSEs are not additive or causal estimates.

## The latest ridge test also shrinks the useful simple features

Both linear arms standardize the same columns, but each selects one penalty strength
for all its active coefficients. The rich arm generally needs a much stronger penalty.
Across the 16 saved models, its first 20 coefficient norms are a median **0.0263 times**
those of the separately tuned coarse arm. A coefficient norm is not a direct measure
of semantic importance, particularly with correlated inputs, but this reveals a design
tradeoff: penalizing the extra features also penalizes the already useful simple ones.
Correlated rich columns can also absorb simple-feature signals, so the small norm does
not prove that a corresponding percentage of useful information was lost.

Deleting terms from the saved rich model gives the following **post-hoc diagnostic**
forecasts, without refitting:

| Fixed-coefficient decomposition | MSE |
| --- | ---: |
| Original rich linear model | 6.3903e-5 |
| Extra-feature contribution removed | 7.4683e-5 |
| Simple-feature contribution removed | 6.5132e-5 |
| Fixed progress potential plus fitted intercept only | 7.7115e-5 |

The rich terms help relative to that model's own heavily shrunk simple component, yet
the complete model still loses to current ridge at 5.5128e-5. These deletions are not
validated replacement models and do not establish that a residual model will win.
They do support testing whether we can add rich information **without discarding the
simple baseline's useful behavior** before investing in a larger architecture.

## Updated work order

1. **One controlled baseline-preserving value test.** Refit the current coarse baseline
   on each inner fitting partition, then learn an independently regularized rich
   correction. Include no correction as a candidate. Inner held games choose the
   correction strength; untouched outer games evaluate it. An outer-fitted baseline
   must never leak inner-validation returns. This is an experimental critic control,
   not an actor proximity constraint or a permanent cap on policy changes.
2. **Improve sharing if this bounded test still fails.** Investigate a compact typed
   entity/field encoder that preserves ownership, identity and current numeric values,
   rather than expanding the existing full-description/owner dictionary blindly.
   Use coverage and whole-game generalization measurements; do not require another
   exhaustive game-mechanics qualification pass before learning work can proceed.
3. **Address outcome scarcity with an explicit collection or curriculum plan.** Measure
   learning curves against independent complete games and rare act-clear coverage.
   Preserve behavior-policy ownership; any broader dataset needs separate policy strata
   or qualified policy conditioning. More weak-policy games may still produce too few
   good examples. Full-run wins remain primary, floor/acts auxiliary; do not reshape
   rewards or discard rare runs to improve a forecast metric.
4. **Require fresh confirmation and actual learning benefit.** This reused pool informs
   development only. A supported frozen critic needs fresh-game validation, then a
   bounded equal-compute action-credit/gameplay comparison from both saved players and
   full Adam states. If the single controlled critic test adds no useful signal, return
   to the action-learning bottleneck instead of an open-ended critic architecture search.

All diagnosis stages are short resource-capped jobs: cached accounting 10.43 seconds,
four public-state cohorts 42.98–76.35 seconds each, summary 52.53 seconds and saved
coefficient decomposition 10.90 seconds. Raw public facts and trajectories remain private
under `artifacts/`; generated outputs total about 89 MB, with no game app copies.
See [portable evidence and report identities](evidence/native-value-error-diagnosis-v1.json)
and the [diagnostic chart](/Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/artifacts/native-value-errors/sts2-v0.111.0-a8-v1/error-diagnosis.png).

Final verification passes all **1,886 tests**, formatting/lint, strict types and the
C# protocol contract in **124.02 seconds**. A subsequent source audit verifies
**11,842 files**, including both current players and every Adam moment/counter,
unchanged. No long job or rerun is required to complete this diagnosis.
