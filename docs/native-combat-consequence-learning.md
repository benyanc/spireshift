# Bounded combat-consequence learning test

This test asks whether learning the observed consequences of combat moves helps
the existing player learn more from its saved games. It compares three players:
the unchanged original, a copy taught only the recorded final run score, and a
copy also taught what happened during combat. **Health is an additional prediction
task, not a reward or a rule forcing the player to preserve HP.** Genuine full-run
victories within the existing 128-CPU-second budget remain the goal.

The original round-60 weights and every PPO Adam moment/counter remain read-only:
**5,658 for player 2 and 6,045 for player 3**. Both learned copies start from those
complete states. This is a separately labeled, off-policy supervised experiment;
it does not resume ordinary PPO, promote a checkpoint, or enable adaptive search.
The earlier [teacher result](native-greedy-complete-turn-teacher-result.md), including
its zero admitted better-turn preferences, remains unchanged.

## Saved examples and information boundary

Use all **51 frozen plans from seven usable TRAIN worlds** in the completed greedy
turn teacher. The eighth source, which never reached an eligible root, remains in
the original source denominator and supplies no invented lesson. Source coverage
is four worlds for player 2 and three for player 3; six normal fights and one elite.

Decode one sealed episode at a time, selecting repeat zero for each plan's current
fight. Earlier verification established identical fight traces across all eight
repeats. Average their eight full-run returns for that plan, but do not duplicate
the combat examples eight times or call them independent hidden worlds. Exclude
source-prefix replay and postfight menus. The measured corpus has **442 combat-turn
decisions**. Related plans can reconverge to identical public states; these are not
442 independent games.

The predictor receives the current public graph and selected legal candidate,
using the parent's unchanged 512-dimensional action encoder. Source/plan IDs,
native seed, private state, later observations and endpoint indices do not enter
the feature vector. They may identify provenance, group folds or define labels.
Native observations supply these numerical targets:

| Target | Definition |
| --- | --- |
| Recorded full-run return | Existing declared bootstrap score, averaged over the plan's eight conditional futures |
| Next public HP change | Observed next HP minus current HP, divided by current maximum HP |
| Next public enemy HP sum change | Change in the visible total enemy HP, divided by current total enemy maximum HP |
| Next-turn HP change | HP at the next observed native turn/postcombat boundary minus current HP, with the same HP scale |
| Encounter-exit HP change | HP at the first alive postfight observation minus current HP; genuine in-encounter death has zero exit HP |
| Alive encounter exit | Whether the original encounter reaches an observed alive exit |
| Next public potion-count change | Observed belt-count change, divided by current slot capacity, with a minimum scale of one |

A next public selection menu can precede resolution of the played card. The next
public target measures that step; the turn/encounter labels follow the native
selection sequence through its actual boundary. Nested choices remain in the
observed trace but are not standalone fitting rows in this version. No enemy HP
is invented on a reward/selection screen, and no terminal potion belt is guessed:
those targets are masked. Known terminal combat death supplies the observed zero
HP endpoint. Missing exits, incomplete games, wrong ownership or changed evidence
stop extraction rather than create convenient targets.

Later-horizon labels describe the **recorded continuation**, including its frozen
turn remainder. They are not causal action values under an identical continuation
policy, optimal-action labels, public-belief search targets or victory probabilities.
This limitation is a reason for the independent full-game comparison.

## Matched learning mechanism

Keep the existing 512-input / 32-hidden-unit tanh actor, including its action-score
readout and direct path. Add six small linear prediction heads on the shared
hidden layer, **198 additional training-only parameters**. They are not evaluated
when the player acts. The original coarse critic's weights remain unchanged.

Both principal arms fit the same heads on identical inputs and targets. In the
`return_only` arm, auxiliary gradients stop before the shared hidden layer; in
`consequence`, they also update that layer. Both still train the action-score
readout on the recorded final return. This isolates the added representation
feedback; the control does not handicap its auxiliary heads by leaving them unfit.
An additional **action-blind prediction control** replaces the chosen row with the
mean of all current legal-menu rows. It has the same dimension and architecture,
but cannot identify the selected move. It is never deployed as a game player.

Calibrate the return readout with a fitting-only mean offset of the parent's
action logits. Standardize each target with fitting-only weighted mean and scale:
minimum standard deviation 0.01 for return, 0.05 for consequences. The optimizer
sees standardized return MSE plus **0.25 / 6 times each active consequence MSE**,
with L2 regularization 0.0001. Constant or absent fitting consequences are inactive.
This defines an auxiliary loss, not a change in environment rewards or the
versioned run score. Predictions are not clipped to make primary errors look better.

Every available source world has equal mass; within it, every plan has equal mass;
within a plan, every valid decision has equal mass, separately per target. Longer
fights and eight repeated future streams cannot dominate by raw row count.

All fits use **128 full-batch epochs**, learning rate **0.001**, gradient norm cap
**5**, and the exact inherited PPO Adam state. New heads have separate zero-start
Adam moments. Both original player files remain unchanged. Disposable all-TRAIN
forks finish at Adam counters **5,786 / 6,173**. Every current legal action family
remains available; shared representation changes can also change noncombat choices.

## Whole-world validation and fixed model choice

Leave one complete source world out at a time, separately for each parent. Keep
every related plan, decision and future stream in the same split. There are four
folds for player 2 and three for player 3. Use three declared new-head initializers
**20261022, 20261023 and 20261024**, giving **63 fits** across three prediction arms.
These are not three independent parent policies or additional game worlds.

Save fitting and held errors separately at epochs 0, 1, 4, 16, 32, 64 and 128.
Compare with fitting-world constant and current-state persistence baselines.
Held outcomes choose neither epochs, regularization, loss weights nor a player.
Seven conditional worlds cannot establish broad generalization, especially for
unfamiliar enemies or rare effects. Report missing/constant targets explicitly.

The actual gameplay forks are fixed in advance: fit all of each parent's usable
TRAIN worlds, use **initializer 20261022 and epoch 128**, and retain both return-only
and consequence forks regardless of the cross-validation ranking. Their weights,
complete Adam state, new-head state and calibration are sealed before any native
control outcome. A model that predicts tactical consequences more accurately
still needs to demonstrate useful complete-run play.

## Native control and full-game test

The short control uses two separate new worlds, one per parent, with all three
gameplay variants and an exact consequence-fork repeat per world: **eight games**.
It checks mathematical gradients, saved-state preservation, native delivery,
complete endings, every recorded behavior probability, matched noncombat random
draws and identical exact-repeat traces. Controls establish implementation
correctness, not stronger play. All 30 earlier native seed manifests are excluded.

The main test uses **32 fresh development worlds × both parents × three variants =
192 full-game attempts**, excluding the two control worlds as well. Every variant
uses greedy combat, including owned nested choices, and temperature-0.8 noncombat
sampling with world/room/family/visit random slots. Uniform draws and the decision
rule match; learned weights may legitimately make different noncombat choices,
even at identical inputs. No HP ranking, extra search or forced strategy is used.

Report wins first, then acts, floors, declared return, failures and actual CPU.
Compare consequence versus return-only, consequence versus original, and
return-only versus original. Seed-clustered percentile intervals resample a whole
development world jointly across the two fixed parents. These multiple comparisons
are exploratory; they do not establish a multiplicity-corrected victory claim.
Failures remain in the original denominator. Uncertain/uncommitted native work is
preserved and never retried automatically; more than two main failures stop work.

## Execution and storage

Use one serial native worker sharing the frozen v0.111.0 game, runtime, SDK and
support cache: **zero game-app copies**. Each unit is sealed before another begins.
Clean session boundaries reuse finished extraction, fits and games; changed or
uncommitted evidence stops for inspection. The original parents and all earlier
teacher records remain protected.

Short controls and saved-only invocations have four-minute caps. Main sessions
have 15-minute / 1,800-CPU-second / 2-GB-memory / 4-GB-output caps, with a two-hour
invocation cap for the same finite plan. Gameplay reserve checks preserve the
per-game 120-second wall / 128-CPU-second budget. No further training or experiment
follows completion.

The main workspace reuses encoded data and four trained forks in the separate
control workspace. Its output cap excludes that inherited workspace, the read-only
teacher corpus and frozen native inputs. Control output has its own measured 1-GB
cap. When assessing total generated storage, sum distinct workspace totals once;
do not sum cumulative storage across repeated resource reports. The earlier
preparatory key-format failure, its seven encodings, recipe and matching source
snapshots remain preserved; it launched no games and performed no model fits.

## Owner handoff

The remaining native comparison is owner-run once the short control and saved-only
checks pass. The command is the same after a clean pause and displays a saved final
result without playing again after completion. Close STS2, then run:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/test-native-combat-consequences-v1.sh
```

This is a bounded learning feasibility test, not automatic bulk-training admission,
proof of a strong base player, checkpoint promotion or an adaptive-search launch.

## Qualification completed before owner gameplay

Both mathematical controls pass, including finite-difference derivative errors
below **4 × 10⁻¹¹**, the stopped-gradient control and unchanged original states.
The eight native checks finish without failures; both exact-repeat traces match.
Their four model/world comparison cells verify **106 shared noncombat random draws**
and **56 identical-input pairs**. These two short worlds establish delivery and
repeatability, not gameplay improvement. No control game wins or clears an act.

All **63 whole-source-world validation fits** are saved, with fitting/held curves
separate and no main evaluation games attempted. The following are equal-world,
equal-head-initializer mean held MSEs at the predeclared final epoch. HP and enemy
HP changes use their declared scales; these are not raw HP errors.

| Held prediction | Player 2: score-only → extra feedback | Player 3: score-only → extra feedback |
| --- | --- | --- |
| Next public HP change | 0.005623 → 0.004711 | 0.001778 → 0.001693 |
| Next public enemy HP change | 0.006297 → 0.006113 | 0.010102 → 0.009734 |
| Next-turn HP change | 0.014831 → 0.013360 | 0.005535 → 0.005491 |
| Encounter-exit HP change | 0.018837 → 0.017100 | 0.003322 → 0.003349 |
| Recorded final return | 0.00002533 → 0.00003033 | 0.00003948 → 0.00004004 |

The added feedback improves immediate HP/enemy predictions in both players, but
final-return errors increase and later predictions are mixed. Action-blind inputs
also predict final return more accurately in this tiny corpus. Current-state
persistence remains stronger for several HP endpoints; the experiment does not
establish a generally better value function. Potion-count changes are constant
zero here, so their head is inactive; player 3 has no death examples in its measured
encounters, so its alive-exit head is also inactive. Player 2's elite is the only
death world. Its held-out survival test cannot be solved by learning variation
absent from the other worlds. Do not call zero error on constant labels useful
mechanics coverage or eight continuation streams independent training worlds.

The four deployment forks remain exactly those sealed before the control, using
initializer 20261022 / epoch 128 regardless of these errors. Their predictions do
not select a model, alter rewards, admit a preferred action or establish improved
play. The independent original/score-only/consequence game comparison is still
needed. Expect roughly **20–40 minutes** for its 192 attempts based on the small
serial control; actual time depends on game length. It has **not started**.

The full repository check passes **2,171 tests (61 new; four skipped)**, strict
types on 435 source files, formatting/lint and the C# protocol. The native control
uses **217.63 wall seconds / 109.54 CPU seconds** across two clean sessions, with
465.39 MB peak RAM and 67.98 MB cumulative output. Saved-only full validation takes
156.78 wall seconds / 105.30 CPU seconds, with 285.84 MB peak RAM and 115.88 MB of
separate cumulative output. The check itself takes 132.00 seconds. These are
measured short invocations; no long gameplay batch was launched by Codex.

Exact report IDs, preserved preparation/probe evidence, parent/fork seals, masks,
full held errors and excluded inherited storage are in the
[portable qualification evidence](evidence/native-combat-consequence-learning-v1.json).
