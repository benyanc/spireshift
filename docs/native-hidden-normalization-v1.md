# A8 learner assessment and hidden-normalization comparison

The November 25 owner audit completed successfully. Its independent saved
assessment verifies 16 training cohorts / 256 games / 44,811 native decisions
from both initializers, both widths and rounds 1/16/32/64. The full raw-public
recount also verifies all 768 development games and 5,120 linked capacity units.
No source checkpoint changed; the audit made 32 discarded copy steps, launched
no games and saved no trained checkpoint.

## What the evidence supports

All 64 numerical gradient probes passed, including both advantage signs. Both
inherited and reset Adam reduced the same local surrogate loss in all 16
cohorts. Median behavior KL was 0.000217 versus 0.002124, and reset moved farther
in every cohort. These are local mathematical checks, not evidence that reset
Adam wins more games.

The learned critic had negative explained variance in 8/16 cohorts. Actor
advantages use a separate cross-fitted ridge baseline, whose explained variance
was positive in 15/16; fixing critic regression alone would not change that
actor credit. The sampled cohorts contain no native victory targets. Return
credit still has variation, so the actor is not restricted to an all-zero label.

Expanded hidden units were about 14% saturated at round 1 and 66–69% at round 64
(absolute tanh output above 0.95). Continued-32 units were 61–63% saturated at
round 64. This motivates testing numerical conditioning. It does not establish
causality, prove sufficient observations or rule out credit and representation
limitations. Existing mechanics evidence remains scoped, including open #149
Connector queue eligibility and broader combinations.

The preceding completed comparison won **0/256 in every policy**. Act 1 clears
were reference 15, continued-32 13 and expanded-128 7; no policy cleared Act 2.
Extra width has not supplied a useful base player under that learner. Neither
its wider final nor any probe is promoted.

## Controlled change

Both treatments use the exact two pre-capacity round-64 shared source finals:

- Player 2: state `99a4bfd9edb53f9eba6c8b9cad51cbc136f012327c0f32ea4cfc0507b0b71ff9`.
- Player 3: state `fae8e125cfbd43dcc90974add15ea6320485fdcbf84f34166eca3509e49afb64`.

Each actor scores a candidate as **frozen reference score + trainable shared
correction**. The correction has 32 hidden units and the same 564 public input
columns. Its output and direct linear coefficients start at zero, so every
starting logit, probability and choice equals the source. Both treatments have
identical fresh hidden parameters, zero correction Adam moments/clock, and
identical copied critic weights and full critic Adam. Source and original
weights/Adam stay immutable. The trainable actor has 18,676 parameters in either
treatment; its frozen reference adds another 18,676 nontrainable parameters.

The raw treatment applies tanh to the correction's preactivations. The normalized
treatment first subtracts their hidden-unit mean and divides by the square root
of their hidden-unit variance plus 10⁻⁵, **within each individual candidate**,
then applies tanh. It never pools legal alternatives, unrelated observations or
games. Inference and training use identical calculations. No extra learned
gain/bias is added after normalization, keeping trainable parameter counts equal.
This uses the central per-case operation from
[Layer Normalization](https://arxiv.org/abs/1607.06450); that paper does not establish
an STS2 benefit.

Both corrections can override any reference preference. Every legal combat,
reward, shop, path, potion, event and selector option stays available to the
same model, including skips and compound answers. There are no scripted tactics,
teacher actions, forced outcomes or imitation labels. Input encoding, training
score, full-run victory objective, cross-fitted credit, PPO settings and native
limits stay unchanged. Critic copies learn through the existing kernel.

The primary treatment contrast is **normalized versus raw**. Comparisons with
the plain frozen source assess whether either new learner improves gameplay;
they also change optimizer initialization and the correction architecture relative
to the earlier continued-weight recipe. Do not attribute that entire difference
to normalization.

## Depth, data ownership and checks

There are 64 rounds × 16 new worlds × 2 initializers × 2 treatments: **4,096
training games** and 256 complete fitting opportunities. Actual updates retain
the existing epoch/KL stops; equal optimizer work is not claimed. Only complete
verified training endings enter PPO. Failed and capped cells remain counted.
At least twelve terminal worlds are required for each round's fit.

Freeze each round-64 final before launching **768 new development games**:
128 worlds × 2 initializers × plain reference/raw/normalized. Report native
full-run wins first, Act 1/2 clears and terminal floor second, with world-clustered
descriptive uncertainty. These are two fixed initializers on the same 128 worlds,
not 256 independent worlds. All-zero observed wins do not establish zero true
win probability. Reserved final-test worlds remain sealed. No automatic promotion,
controller, A10 evaluation or next experiment follows.

Manual derivatives are checked against finite differences across every correction
parameter. Tests cover candidate independence, degenerate variance, exact full
state/Adam reload, a real PPO update, frozen reference weights, grouped choice
weighting, old-kernel rejection and dispatch restoration. Short native controls
compare all 114 qualified public menus against both treatments and the plain
reference, then require four equal initial trajectory pairs, eight disposable
PPO updates on four copies and four complete post-reload games. Fixture menus
only test encoding/inference and provide no training labels.

These controls passed: **12 complete native games**, **751 matching model
choices in four initial pairs**, **eight real disposable copy updates**, and
exact reloads followed by four complete games. All frozen-input checks pass.
The first bounded session stopped cleanly before unstarted reload work; a
49.77-second continuation reused its exact seals and finished the final two
games. Total short-session time was 247.47 seconds. These losses and local
updates establish execution only, not stronger play. In this small control
sample raw correction saturation was 0%, while normalized correction saturation
was 6–8%; the sustained study must measure how geometry evolves and whether
either treatment improves outcomes.

Each fit records bounded, world-balanced before/after correction geometry from
its own training cohort, with compound answers weighted once. Lower saturation
is a diagnostic; fresh full-run outcomes decide whether it helps play.

## Owner command

Close STS2, then run:

```bash
bash scripts/compare-a8-hidden-normalization-v1.sh
```

Allow about **14–24 hours**, based on the previous 13.6-hour capacity continuation,
with a **48-hour outer cap**, 24-GB output cap and 4-GB resident-memory cap. Per-game
128 gameplay CPU seconds, 90 wall seconds and 2,048 choices remain unchanged.
The pinned script sets the numerical thread settings. Clean exact seals resume;
uncertain or incomplete units stop and are preserved without retry/replacement.
Long experiments are owner-run.

The frozen game remains v0.111.0 / 41cef1ea, host60 and the qualified potion-queue
adapter. Outputs live under `artifacts/native-hidden-normalization/`; historical
studies, original full states, source finals, full Adam and personal game profile
stay protected. The current recipe pins executable inputs separately from these
administrative docs. Exact assessment and control IDs are in the linked
[evidence](evidence/native-hidden-normalization-v1.json).
