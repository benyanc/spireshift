# Combat-consequence learning: completed result

The experiment ran correctly, but **both supervised updates made the player worse
than its unchanged original**. Extra combat feedback has no established gameplay
benefit in this comparison. Keep the original players and every saved optimizer
state; do not promote either trained fork or repeat the unchanged recipe.

The owner completed all **192/192 planned games**, with zero failures, missing
attempts or game-app copies. These are 32 distinct development worlds shared across
two fixed players and three variants, not 192 independent worlds. No variant wins
a full game. The original players each clear one act; neither updated variant
clears an act in these fresh games.

| Player variant | Games | Wins | Total act completions | Average floor | Best floor |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original | 64 | 0 | 2 | 10.84375 | 23 |
| Recorded-return regression only | 64 | 0 | 0 | 7.96875 | 17 |
| Same regression plus combat consequences | 64 | 0 | 0 | 8.25000 | 17 |

The paired floor difference is **−2.59375** for consequence versus original, with
the declared seed-clustered 95% interval **[−3.859375, −1.3125]**. Return-only versus
original is **−2.875 [−4.125, −1.59375]**. Consequence versus return-only is just
**+0.28125 [−0.046875, +0.640625]**: that small apparent advantage is inconclusive.
The bootstrap score also declines for both updates. Pooled regression is strongest
in player 2: consequence changes its mean floor from 11.0 to 6.53125. Player 3
changes from 10.6875 to 9.96875; its individual interval includes zero.

These are exploratory intervals for two fixed parents under this greedy-combat
rule, not a multiplicity-corrected claim about all training initializers. The
all-zero observed-win bootstrap interval is degenerate; it does not prove a true
win probability or true win-rate difference is exactly zero. Genuine full-run
victory remains primary. Floor regression is an auxiliary negative result.

## What this rules out and what it does not

The collector verifies native delivery, every recorded policy choice and genuine
endings. A separate saved-only audit checks **73,174 sealed source files / 255
completed units**, decodes **192 histories / 22,842 decisions** one at a time, and
reconstructs all public trace identities, endings, CPU/score values, paired tables
and matched noncombat receipts. It launches no games or fits. It does not independently
recompute neural logits or rerun the native delivery verifier; their collector
audits remain sealed and verified. Both complete original player/Adam files have
their original byte hashes and counters **5,658 / 6,045**. All four experimental
forks also match their predeclared seals, including unchanged original critic
weights and copied Adam state. No cap or failed game explains these losses.

Matched noncombat sampling verifies **3,524 shared random-draw slots / 1,073
identical-input comparisons**, including **41 different learned choices at an
identical input** across the consequence/reference comparisons. Shared weights
can change noncombat preferences; identical random numbers do not freeze those
choices. This is an end-to-end player comparison, not a combat-only causal ablation.

The first changed choice versus the original occurs at a current identical public
input in every one of the 128 player/seed/fork comparisons. There is no unexplained
public-state divergence before an action changes. **72 first differences are combat
decisions; 56 are noncombat**, including events, paths, rewards and nested card
choices. This establishes that both kinds of behavior changed. It does not identify
which early change caused a final loss or prove a particular choice was wrong.

## Interpretation of the learning method

The earlier [prediction checks](native-combat-consequence-learning.md) showed
better immediate HP/enemy prediction from extra feedback, mixed later prediction,
and worse held-out final-return errors. Those improvements did not translate into
stronger play. The negative full-game result must take precedence over reduced
fitting error or a more informative representation.

Both experimental arms contain a common change: they regress the **existing actor's
action scores themselves** onto standardized recorded full-run returns. The loss
updates the shared encoder, actor readout and direct action path. Only the added
auxiliary encoder gradient differs between the two arms. The original critic is
unchanged. This is explicitly supervised fixed-world learning, not the earlier
on-policy PPO continuation. See `native_consequence_math.py`, `forward`,
`loss_gradient` and `fit`.

The all-TRAIN return-fitting MSE drops from approximately **0.00104 to 0.00000033**
for player 2's return-only fork, and **0.000498 to 0.000000927** for player 3. At the
same time their fresh-game play regresses. Predicting a small collection of return
numbers more accurately does not establish improved ordering of legal actions.
The corpus has only **seven independently held TRAIN worlds**, with many related
plans and mostly tied final returns. Its future-turn labels describe different
recorded continuations, not controlled causal action values. No full wins are
present in its labels. These limitations support overfitting, score-calibration or
ranking-damage hypotheses; this experiment does not isolate their contributions.
It also does not prove absolute-value regression or auxiliary learning is always
ineffective. Increasing the same update's epoch count or data reuse is unsupported.

The material next step is to **separate outcome prediction from policy learning**.
First diagnose saved-menu ranking, margins and noncombat sampling changes from the
common return-regression update. In the next version, give predicted outcomes their
own readout; do not silently replace the original action scorer with a return
predictor. An isolated prediction-only control must leave original action scores
and choices exactly unchanged. Any deliberate policy update needs its own declared
objective and gradient checks, then an original-player control and fresh whole-game
evaluation. All legal action families can remain learnable, and this does not impose
a permanent proximity constraint on the player. Do not convert these greedy
evaluation games or privileged teacher continuations into ordinary PPO experience.

No new learning recipe, gameplay batch, promotion or adaptive controller follows
this assessment. Any on-policy comparison needs separately declared fresh sampled
experience; any preference update needs qualified action-ranking evidence. Neither
is admitted by fitting-error improvements alone. Broader representative TRAIN
coverage is useful only alongside a learning update that preserves this distinction.

## Resources and preserved evidence

The owner's two gameplay sessions take **1,101.92 wall seconds (18.37 minutes)**
and **702.83 CPU seconds**, with **509.71 MB** peak RAM and **395.88 MB** final
cumulative main-workspace output. That storage includes the earlier saved-only
validation in the same workspace; do not add its old cumulative snapshot again.
The separate inherited control workspace, read-only teacher and frozen native
inputs remain excluded, as declared in the original design. Lower measured episode
CPU for the trained players is not a strength or useful-efficiency gain: they die
earlier. All variants retain the same 128-CPU-second full-run limit.

The saved audit takes **28.19 wall seconds / 16.63 CPU seconds**, with **218.84 MB**
peak RAM. Original recipes, source code, model states, resources, qualification
documentation and earlier results remain unchanged. Exact IDs and compact evidence
are in [the result evidence](evidence/native-combat-consequence-learning-result-v1.json).
