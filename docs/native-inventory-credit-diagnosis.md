# Saved-training credit diagnosis with deck and relic information

The diagnosis is **complete**. It reads the structured-input comparison's **384
saved TRAIN attempts**, covering 64 worlds and 12 separate player/input-arm/round
cohorts. It reconstructs **55,368 non-navigation learning decisions**; the 55,642
raw training decisions also include 274 deterministic navigation steps. No fresh
games, actor updates or Adam updates were performed. Both originals and all six
experimental final states remain unchanged. **No owner run is needed.**

## What the tool checks

The current training credit is `A(t) = G - V(state(t))`: the observed whole-game
bootstrap return minus a cross-fitted state-value forecast. Full-run victory under
128 CPU seconds remains primary; this diagnostic's forecast target is the explicitly
declared auxiliary return, not a victory probability or optimal-action label.

The tool reproduces the original four folds, all 20-feature ridge coefficients,
prediction metrics, strategic menus, navigation and batch credit mean/deviation
before accepting a cohort. Source delivery/probability audits are reused from their
verified seals. Native effects and neural policy inference are not replayed.

It then checks three things:

1. **Missing distinctions.** Find exact matches of the current 20 input features
   that contain different public deck or relic states. No rounding is used.
2. **Transferable inventory information.** Add explicit typed inventory inputs to
   a fixed copy of the coarse forecast; compare withheld whole-game errors.
3. **Effect on recorded action credit.** Report raw/normalized credit and the
   selected-logit ascent coefficient by decision family. Sign changes are not
   evidence that an action was correct or that gameplay would improve.

The new inputs are order-invariant counts of owned card definitions, native card
types, upgrades and displayed costs. Joint per-copy identity/upgrade/cost features
prevent swapping which copy is discounted. Relic definitions retain their own
visible counters and counter-availability flags. Numeric zero is observed information,
not an unfamiliar field. Cross-character definitions use the same generic schema.
Missing deck composition is rejected rather than treated as an empty deck.

Chosen actions, offered cards/relics, runtime entity slots, seeds, hidden RNG state,
future outcomes and free-text descriptions are not inventory-predictor inputs.
The current 20 features remain unchanged. This compact inventory probe omits hand
composition, detailed effects and nonlinear card/relic interactions; it is not a
lossless or exhaustive state representation. Counter values are used only where
the saved public context actually supplies them, with availability measured separately.

## Controlled prediction probe

Each 32-game cohort has four whole-world folds: 24 games fit and eight are withheld.
Policies and rounds are never pooled into one fitted value function. The shared
world assignment is the production fold assignment. Evaluation-game inputs and
targets are excluded from fitting. Cached schemas may index held-only names, but
only fitting-observed columns enter a model or its normalization.

Compare current coarse ridge, coarse plus deck information, coarse plus relic
information, coarse plus both, and an other-fitting-game constant reference. Keep
the original coarse coefficients/lambda **0.001** intact. Extra coefficients use the
existing residual-correction solver with one predeclared independent penalty **1.0**;
there is no penalty grid, inner selection, extra intercept or neural optimizer.
Fitting normalization uses only fitting choice-bearing states, with equal mass per
whole game. All withheld worlds, including rare long runs, remain in the result.

This materially changes the earlier full-description/owner-position dictionary:
typed owned-inventory counts share card/relic identities across positions and deck
orders. It reuses the tested ridge solver instead of repeating a critic architecture
or regularization search. Fixed shrinkage can still be imperfect, so a negative
screen does not prove that deck/relic information is unhelpful in every predictor.

## Completed results

Lower mean squared error is better. Values below give equal mass per cohort/game;
they are development measurements, not independent training replications.

| Forecast | Withheld MSE | Change from current |
| --- | ---: | ---: |
| Current 20-feature predictor | 4.07934e-5 | Reference |
| Add deck information | 4.20475e-5 | +3.07% |
| Add relic information | 4.17900e-5 | +2.44% |
| Add both | 4.29011e-5 | +5.17% |
| Other-fitting-game constant | 6.55847e-5 | +60.77% |

The combined correction worsens the cohort mean in **12/12 cohorts**. The first
round's three input arms have matched source traces; their repeated result is not
three independent confirmations. Do not select a different penalty or production
predictor on these outcomes. Keep the current baseline.

Fitting error does improve: mean equal-fold MSE falls from **3.48863e-5 to
2.03777e-5**, about **42%**, with the combined correction. The extra inputs can
explain fitting outcomes, but that improvement fails to transfer to withheld games.
These are raw fitting errors; primary withheld errors use the production [0, 1]
clipping rule. Clipped fitting error and the separate weight penalty are also retained.
This is evidence of a generalization problem in this probe, not a disconnected
input path or proof that more input nodes alone will improve the player.

Across the separate cohorts, **435 exact coarse-input groups** contain different
inventory states across worlds, affecting 1,341 learning rows. These are cohort
observations with repetitions, not 435 independent mechanics or proven differences
in true expected value. Coarse equality means the same information is supplied;
different cross-fitting folds can still use different coefficient arrays.

The combined predictor changes the sign of normalized credit on **4.90–10.30%**
of choice-bearing rows per cohort. The exact unaveraged, per-decision selected-logit
coefficient at behavior is `A_normalized * (1 - p_selected) / 0.8`. The tool uses
sealed probabilities to measure that component; it does not calculate a full
network gradient, add entropy, take an Adam step or assess counterfactual actions.
Changing credit without improving forecasts does not establish better learning.

There are **zero full wins and only two act-clearing trajectories**, both from
one world under two later policies. Together those two observations contribute
**43.70% of current-predictor squared error**. They remain in the primary result.
Current error on the other 382 cohort/game observations is 2.30850e-5; that is a
sensitivity description, not a reason to delete the rare outcomes. Unfamiliar
inventory features occur in 313/384 cohort/game observations. The combined predictor
also loses in the 71 observations where every inventory feature was seen in fitting.

Those two unusually long runs give positive raw credit to about **97%** of their
choices; after production batch normalization, about **75–76%** remain positive.
This does not prove those choices were wrong. It illustrates the remaining delayed
credit problem: many different decisions share one final return, without direct
evidence about what would have happened under alternatives. A state-only baseline
can reduce variance; it does not rank alternative actions within a menu.

## Preservation, verification and runtime

Each cohort retains compact arrays, four whole-world fold assignments, 12 small
inventory predictor states, forecasts, coverage, alias counts and credit summaries.
At most one raw episode is decoded at once. A sealed journal reuses completed
cohorts and refuses to overwrite incomplete or changed evidence. Original full
weights and all optimizer moments/counters **5,658 / 6,045** remain protected.

The two successful sessions total **80.15 wall seconds**, peak at **750.52 MB RAM**
and retain **32.49 MB**. A separate 14.10-second saved-only assessment verifies
**32,907 source seals**, restores all **144 inventory models and their forecasts
bit-for-bit**, and reconstructs fitting errors without refitting. No game apps
are copied. See [portable evidence](evidence/native-inventory-credit-diagnosis-v1.json).

The initial v1 check stopped on a verifier batch-layout difference of at most
**6.94e-18**. Its partial arrays, failed receipt, recipe and exact source snapshot
remain preserved. V2 evaluates restored models in the original matrix batch layout;
the bit-for-bit threshold was not weakened. No gameplay or player update occurred
in the failed check. Use only the active v2 recipe/entry point for this diagnosis.

Repository verification passes **2,348 tests (27 new; four skipped)**, strict types
on 483 source files, formatting/lint on 659 files and the C# protocol in **129.45
seconds**. Tests cover identity/copy ownership, private-state rejection, planted
learnable inventory signal, whole-world target isolation, held-only names, observed
numeric zero, numerical restoration, exact logit derivatives, sealed resumption,
tamper detection and preserving original model/Adam bytes.

The active entry point is `scripts/diagnose-native-inventory-credit-v2.sh` and recipe
`configs/native-controls/inventory-credit-diagnosis-v2.json`. The complete result is
already cached: reusing it verifies and displays saved results, without refitting.
There is no owner command to run for this completed step.

## Next work

The original credit calculation reproduces; missing inventory distinctions are real,
but this correction is not a supported replacement. Preserve the negative result
and stop repeating small rich-predictor searches. The next material work should
address the scarcity and usefulness of independent experience: a predeclared bounded
learning/data comparison, with successful later-game coverage and per-family credit
diagnostics, followed by fresh full-game evaluation. Larger batches or more games
are hypotheses, not guaranteed fixes. A qualified stronger teacher/curriculum is a
separate alternative if ordinary experience still supplies too few informative outcomes.

Keep both saved players and complete Adam state for any ensuing forks. Do not
silently install this probe, reshape health/Smith rewards, scale unchanged training,
promote a checkpoint or start an adaptive thinking controller. A richer nonlinear
state predictor remains a separate later candidate requiring new evidence and its
own actual-learning test. No next experiment follows this diagnosis automatically.
