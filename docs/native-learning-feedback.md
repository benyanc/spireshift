# From completed games to useful numerical lessons

The completed rest-exploration comparison is reliable but does not establish stronger play.
Across 896 terminal attempts there are no technical failures, full wins or app copies.
The 128-test-game/version mean floors are 11.0859375 original, 11.453125 standard and
11.3203125 exploration. Exploration minus standard is −0.1328125, with a paired-seed
95% interval of [−0.8125, 0.546875]. The six resource-tracked sessions total 3,650.37 wall
seconds and 3,848.87 CPU seconds; the final report's 432.63 seconds is its last session only.
Peak recorded RAM is 1.064 GB. This is auxiliary progress evidence, not victory readiness.

Low Smith use is not itself a defect. Healing can be necessary after poor combat, and
neither a high-health rest nor a losing run supplies an optimal-action label. The owner
requested a diagnosis that leads to a corrected mechanism or numerical training targets,
rather than treating a written explanation as training data.

## Implemented audit

The new, separately versioned tool reads the exact **16 completed 32-game TRAIN batches**
from the rest experiment: 512 recorded attempts, four rounds, both initializers and both
methods. It never pools their experiences into one PPO batch. Histories from evaluation
are not decoded; the completed source's full file seals, including evaluation file bytes,
are still checked for integrity.

For each own-behavior batch it:

- Reconstructs every strategic action's actual softmax/mixture probability, public input,
  model and score identities using the unchanged training preparer. The entire reconstructed
  credit report must equal the one the real update saved, including whole-game fold ownership.
- Compares the before/after actors on identical old inputs. Reports base-policy and actual
  mixture probabilities separately, chosen-action credit alignment, and the mixture's
  responsibility multiplier. A multiplier is not a percentage of the eventual Adam change.
- Reports decision-family and health-band opportunities, including choosing/declining cards,
  potion use, shop controls and Rest/Smith. These are menu presentations, not independent
  room visits, mistakes, causal effects or reasons to impose new action masks.
- Compares the cross-fitted baseline used for actor credit against an other-fold constant,
  the recorded critic and an unfitted current-progress reference. Games receive equal
  weight, then their choice-bearing decisions share that weight. The critic is a separate
  predictor; it is not substituted for the ridge baseline that supplied this actor's credit.
- Exposes mandatory menus, whole-game weighting and normalization, alongside last observed
  combat encounters and health at the first observed combat state on that act/floor.
  Act/floor grouping is not a unique engine encounter identifier, and no exact death cause
  is invented from the final observation.
- Perturbs finite public health/energy/card-cost/damage/block/target-health facts when present
  and checks that the encoder distinguishes them. Candidate-order reversal must permute rows
  exactly. This does not exhaustively prove native mechanics, sensible probability direction,
  adequate capacity, or that an omitted field is unnecessary.

## Numerical teaching control and its limits

On one actual public combat input per batch, a **disposable copy** of the behavior model and
all Adam moments/counters receives an explicitly invented target: prefer its currently least
likely legal action. The same actor architecture, encoder, gradient machinery and Adam run
64 fixed cross-entropy steps, with no value/entropy objective and no extra work selected by
the result. The predeclared memorization criterion is target probability ≥75%.

The label deliberately has **no claim to native action quality**. It tests whether numerical
labels can change a current, confident actor; it does not test generalization, PPO's ability
to discover labels from outcomes, the native collector, or which card should be played.
The small synthetic teaching loss is already an existing tested repository component.
No diagnostic model or optimizer is saved as a production candidate, and original state
files remain sealed and unchanged. Synthetic optimizer steps are counted separately.

This makes the next decision concrete:

1. Repair an exercised input loss or credit-reconstruction error before more game training.
2. If direct numerical teaching cannot change the actor, investigate optimization/representation.
3. If these checks work but full-run progress remains weak, qualify native action branches
   to produce better lessons. Do not assume repeating unchanged PPO is sufficient.

Native action comparisons must bind the public state, legal candidate order, engine version,
continuation policy, independent future sampling and compute budget. Hidden-state exploitation,
short-horizon bias and uncertainty must be explicit. A combat result is an auxiliary target;
full-run victory remains primary. Separate supervised imitation/ranking/value losses can consume
verified historical lessons. Old behavior records must not be relabeled as fresh on-policy PPO.

## Preservation and execution

The admitted short control completes in **81.92 seconds**, using **320.52 MB** peak RAM and
2.95 MB output. Both actual standard batches verify: **64 TRAIN games / 9,462 strategic
decisions**, exact saved credit reports, whole-game fold separation and original states.
Twelve finite perturbations (six facts per initializer) and both candidate-order checks pass.
The current cross-fitted baseline's MSE beats the other-fold constant in both batches;
the original recorded critic does not supply the actor's cross-fitted credit.

On identical old combat choices, the average credit-aligned probability movement is
0.00830 and 0.00894 for the two initializers. This is evidence of a connected update on
assigned feedback, not proof that the feedback identifies good moves. The two artificial
labels rise from 0.00380% / 0.00174% to 99.98% / 99.85% after 64 steps each, with complete
copied Adam state. This is a one-input memorization test, not learned game strategy.

These findings do not justify calling the learner disconnected or the baseline useless.
They prioritize checking the complete current batches and then qualifying better native
action comparisons if the remaining checks agree. The full 512-game audit is prepared,
preflighted and **not started** by Codex.

The historical training implementation, recipes, source report, models and full Adam states
are unchanged. New code/configs and reports use their own workspace. The initial development
control v1 is preserved with exact copies of its 65 Python sources and launchers under
`artifacts/validation/native-feedback-v1/development-source-v1`; it is superseded by control v2,
which repairs type annotations, exercises native string costs and binds the launchers.
It is not silently relabeled as the admitted control.

The full audit checks the matching short control before running. It uses one numerical thread,
2 GB RAM and a 100 MB generated-output cap. It commits one completed 32-game analysis at a time;
clean reruns reuse those results. A partially written analysis chunk is preserved and stops for
inspection rather than being silently replaced. No native games or production optimizer
updates occur. There is no automatic training, promotion, adaptive controller or next study.

The one owner command for the complete saved-record audit is:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/diagnose-native-learning-feedback-v1.sh
```

Allow roughly **8–12 minutes**, with a 15-minute launch cap. A clean pause can be continued
using the same command. This performs analysis of existing games, not another training run.
The short control runs under a four-minute cap and belongs to Codex; the full audit belongs
to the owner under the five-minute execution boundary.

Measured control and local-check evidence: [learning feedback evidence](evidence/native-learning-feedback-v1.json).

Repository verification passes **1,822 tests** (117.69 seconds), formatting/lint, strict types
on 352 source files, and C# build/protocol checks with zero warnings/errors. The resource-tracked
check takes 122.10 seconds and 377.29 MB peak RAM. Reopening the completed control with analysis
disabled verifies its saved result in 8.46 seconds; no extra numerical updates occur.
