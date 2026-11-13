# Policy-update qualification and bounded fresh-game comparison

**Completed:** all 256 attempts ended cleanly, with no demonstrated improvement.
See the [saved-result assessment and agreed follow-up order](native-policy-update-comparison-result.md).
The preparation and zero-game statements below are historical; its command now displays
the saved result. Do not rerun the experiment or scale it automatically.

The numerical policy checks and **eight-game native bridge control pass**. Both
original players and every saved PPO Adam moment/counter remain byte-identical:
**5,658 / 6,045**. The main comparison is prepared but has played **zero games**;
its three completed units only check the math and import the original full states.
Its copies start from the originals, not the short control's trained copies.

## What changes

The rejected supervised method fitted the original action scores directly to
recorded returns. This experiment uses the existing **clipped PPO probability-ratio
loss**. Actions receive positive or negative advantages from fresh sampled full
games; their absolute logits are not supervised outcome predictions.

The existing state-value head has separate parameters and a diagnostic value loss.
Actor credit uses the previously qualified **20-feature, whole-game cross-fitted
residual ridge baseline**, refitted on other fresh training games in the batch.
It does not fit the credited game's own outcome. This baseline is intentionally
unchanged; it still omits deck composition and relic identity. The seven-output
action-conditional prediction network stays separate and supplies no PPO baseline,
action scores, teacher labels or reward in this trial. Richer return prediction
and stronger play are not claimed as prerequisites already achieved.

There is one new empty-signal safeguard: if the batch's centered advantages have
zero numerical variance, skip the entire update and retain its copied model and
Adam state exactly. Merely sending zero gradients to warm Adam can otherwise move
weights using its previous momentum. This safeguard does not reset Adam, freeze
action families or impose proximity to the original policy.

The finite schedule keeps the previous standard PPO settings: three epochs per
round, minibatches of 128 decisions, temperature 0.8, clip 0.2, entropy coefficient
0.015, actor rate 0.001, diagnostic value coefficient 0.5 / rate 0.003, gradient
cap 1 and round-local KL stop 0.03. A later round collects fresh behavior. There
is no permanent baseline-proximity penalty or combat-only restriction.

The full-run objective and bootstrap score remain unchanged: genuine terminal
victory is primary under the **128-CPU-second whole-run budget**. Floors and acts
remain auxiliary measures. No health, block, upgrade or combat-survival bonus is
introduced into the reward.

## Qualification completed

Signed-gradient checks on both original models verify that a small step along the
policy descent direction raises a positively credited action's probability and
lowers a negatively credited one's probability. The maximum sampled numerical
derivative error is **3.48×10⁻¹¹**. These are derivative controls, not a guarantee
that every shared-weight Adam minibatch improves every individual choice.

Other checks cover clipping in both directions, common-score-shift and candidate
permutation invariance, zero actor gradient from a prediction-only loss, actor
gradient independence from outcome targets when advantages are held fixed, exact
continuation of every old Adam moment/counter, and unchanged original full states.
Tests also cover the zero-signal momentum trap, deterministic state restoration,
fresh seed ownership, source-policy binding and sealed-unit restart behavior.

The native bridge control completes **four sampled training games and four
frozen-player evaluation games**, with zero failures. The copied optimizers move
**5,658→5,667 / 6,045→6,054**, while the original files remain unchanged. All native
delivery, sampled-probability and genuine-ending checks pass; frozen game, runtime,
SDK and account-profile checks pass. No game app is copied. The native session
takes **41.43 wall seconds / 44.04 CPU seconds**, with **777.68 MB peak RAM** and
**19.28 MB cumulative output**. The earlier math/import session takes 0.89 seconds.

Only one control evaluation world is shared by both original/updated pairs. Its floor
differences are not evidence of stronger play. The control qualifies the data
path and updater, not the main experiment's result or base readiness.

A saved-only audit verifies **444 sealed files / 11 completed units**, reconstructs
all **682 sampled TRAIN decisions** from their recorded random seeds and all
**593 evaluation decisions**, and confirms exact main-state imports. It takes
**8.20 seconds**, with zero new games or updates. Native delivery is not semantically
rerun by this audit; its source audit seals remain verified. The repository check
passes **2,268 tests (52 new; four skipped)**, strict types on 452 files, formatting,
lint and the C# protocol in **121.90 seconds**.

## The fixed main experiment

| Stage | Scope | Game attempts |
| --- | --- | ---: |
| Fresh on-policy training | Two rounds × 32 games × two original initializers | 128 |
| Fresh frozen evaluation | 32 different worlds × two initializers × original/updated | 128 |
| Total | One finite comparison | 256 |

The two initializers share the same 64 training worlds. Every legal strategic
action family is learnable, including combat, rewards and Skip, deck choices,
paths, events, rest sites and shops. Verified navigation-only controls supply no
policy gradient. Each training chunk contains eight games over two isolated
workers. Keep compact features and sealed paths; decode at most one whole history
at a time. Greedy evaluation histories and privileged teacher branches cannot enter
PPO. The new header checks also bind the exact recipe, behavior checkpoint, native
world, seed manifest, TRAIN role and complete collection denominator.

Both final updated states are frozen before any development game. No evaluation
outcome selects a round, epoch or hyperparameter. Evaluation uses the same greedy
combat / sampled noncombat rule for original and updated players. Room-local
noncombat draws match by native world and public sampling slot; learned noncombat
preferences may differ. The two versions' order rotates across worlds.

Report victories first, then acts, floors, bootstrap score and failures. Failure
and unattempted values stay zero in the original declared evaluation denominator;
partial results remain labeled partial. Seed-clustered paired intervals keep both
fixed initializers together when resampling worlds. They do not describe a
population of training initializers. An all-zero win bootstrap interval does not
prove zero true win probability. No result automatically promotes a checkpoint,
passes base readiness or starts an adaptive controller or further experiment.

Fresh seed manifests exclude all **32 prior v0.111.0 seed manifests**, plus the
separate control worlds in the main experiment. Main training and development
worlds are disjoint. Historical code, configurations, games, prediction fits and
all original/rejected models remain preserved.

## One owner command

Close any running STS2 game, then run:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/compare-native-policy-updates-v1.sh
```

Expect approximately **15–30 minutes**, extrapolating from the small control;
longer games and machine load can change that. The script prints each training
chunk's best game, mean floor, wins and failures, and each round's optimizer
continuation. Evaluation progress appears every eight games.

Sessions have **15-minute / 1,800-CPU-second / 4-GB-memory / 4-GB-generated-output
caps**. The wrapper continues only this same finite schedule across clean session
boundaries, with a one-hour invocation cap. If it reaches a clean invocation pause,
run the same command again. Completed units, trained weights and every Adam moment
resume; they are not regenerated. An interrupted or changed unit remains preserved
for inspection and is not silently cleared or replayed. Confirmed failed training
games supply no PPO samples and remain counted. More than two failed games in a
training round or evaluation, unknown delivery or missing evidence stops the work.

The output cap covers the main workspace only. The read-only short control,
original checkpoints and shared game/runtime/SDK/support cache are excluded.
No app copies, push, Actions or other experiment follow. Main provenance, completed
controls and test receipts are in [the evidence](evidence/native-policy-update-comparison-v1.json).
