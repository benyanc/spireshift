# Direct teaching versus PPO on the synthetic health task

Implemented under #35 / #146 on 2026-10-17. This short diagnostic asks whether the
unchanged native model can learn a situation-dependent choice with correct-action
labels, compared with learning from sampled terminal outcomes. It changes no native
player, game rules, input encoding or production training recipe.

**Completed:** all three pairs and both controls pass their integrity checks, but
neither primary method meets the predeclared learning criterion in any seed. The
result is preserved without adjusting settings or extending training.

## Measured result and next work

All primary players receive **288 actual Adam updates**, 36,864 decision presentations
and 6,144 choice presentations each. The comparison samples 6,144 fresh artificial
episodes total, not once per teacher: teachers reuse PPO's contexts. There are 2,052
synthetic updates including the missing-HP and frozen-actor controls, 96 sealed round
records and 99 verified round/pair files. All three PPO final model IDs and exact
evaluations reproduce the earlier known-task result.

| Training seed | PPO expected victory | Taught expected victory | Taught minimum optimal-action probability | Taught greedy accuracy |
| --- | ---: | ---: | ---: | ---: |
| 0 | 54.25% | 51.50% | 49.89% | 50% |
| 1 | 48.06% | 51.66% | 50.14% | 100% |
| 2 | 51.56% | 51.49% | 49.61% | 50% |

The teacher develops a small conditional preference. Seed 1 greedily selects both
correct actions, but with probabilities only slightly above 50%; none approaches the
75%-in-every-context criterion. This is not evidence that the network cannot represent
the rule. It does show that weak conditional learning in this setting is not exclusively
a consequence of sampled terminal rewards: it persists with oracle action labels.
PPO's different reward objective and the teacher's extra information preclude a method
superiority claim from these numbers.

A saved-only initialization probe confirms that HP survives encoding. In these menus,
the HP-induced feature change is identical for both candidates; the direct linear
branch therefore contributes **zero** to the HP-dependent difference in action scores.
The hidden branch can represent an interaction, but its initial conditional-contrast
gradient norm is only **0.027–0.040%** of the ordinary action-preference gradient norm.
The contrast is `(Commit - Decline at high HP) - (Commit - Decline at low HP)`; the
reference is the mean Commit-versus-Decline score gap. These are local derivatives in
this parameterization, not actual Adam changes, a learning-rate ratio, or proof of the
cause of native failures. The probe makes no change to inputs or weights.

**Next work:** a separately versioned, finite synthetic comparison that makes public
context-by-candidate interactions explicit while preserving every input/action and
the current network size. Keep work and initial policies controlled; retain unchanged
encoding as the reference. The measured gap justifies testing a specific representation
change, rather than enlarging the model or starting more unchanged game training.
Earlier supervised Rest/Smith successes remain valid for their different examples,
loss setup and learning rate; this result does not silently replace those controls.

The comparison takes **37.43 seconds**, 37.23 CPU seconds, **166.07 MB** peak resident
memory and **1.56 MB** retained output at completion; no cap is reached. The later saved
assessment adds a small separate report. No native game, production model update or
app copy occurs. No owner task is pending; the wrapper now displays the saved result.

## Fixed comparison

The task is the existing `contextual_risk` control, including its five forced
continuation menus. At low HP, Commit wins 10% and Decline 55%; at high HP, Commit
wins 85% and Decline 55%. Both HP levels and both candidate orders are enumerated
in exact evaluation. The optimal expected victory is 70%, and the best unconditional
choice achieves 55%. These are artificial probabilities, not STS2 gameplay estimates.

For each of seeds 0/1/2, both methods start with identical numerical weights and zero
Adam state. They keep the native 512-input / 32-hidden-unit actor, quarter scaling,
direct linear branch, diagnostic critic, temperature, learning rates, clipping and
entropy coefficient. All actor layers remain mutable. PPO collects 64 fresh episodes
per round for 32 rounds, using only sampled binary terminal outcomes and the original
whole-game cross-fitted baseline. No action label is supplied to PPO or policy inputs.

The teaching method receives those **same ordered public inputs**, plus the known
optimal action as a separate loss target. Its actor loss is cross-entropy plus the
same entropy term. Its diagnostic critic fits the same sampled outcomes. Forced
menus retain their zero actor derivative and their place in the averaging denominator.
The teacher replays PPO's actual completed epochs, shuffled minibatches and update
count each round, including any PPO KL stop. It does not select extra training from
its own performance. Actual updates, choice presentations and total decision
presentations must match within every pair.

This matches optimizer work and observed contexts, **not information or CPU budgets**.
Direct teaching has an oracle label; PPO has one sampled outcome. The loss and clipping
semantics also differ. A positive teaching result can demonstrate representability and
learnability under that treatment, but does not isolate a unique PPO defect or establish
supervised learning as the better real-game method. A negative teaching result does not
prove insufficient model capacity: the fixed optimizer/settings/budget may be inadequate.

Final players alone are scored; no best-epoch selection. The predeclared criterion
requires at least 75% probability for the optimal action in every context and at least
10 percentage points improvement in exact expected victory. All attempted seeds and
settings remain saved even when no method passes. Evaluation checks a known finite
task, not held-out generalization or native readiness.

## Controls and evidence

Seed 0 also fits a teacher with HP removed coherently from actor and critic inputs,
while retaining the contradictory conditional labels. Its best possible unconditional
expected victory is 55%, and greedy optimal-choice accuracy is 50%. A four-round
frozen-actor teacher executes Adam updates: actor/performance must stay identical while
the diagnostic critic changes. These controls reuse sampled contexts and draw no extra
episodes.

The new teaching derivative is checked against finite differences in hidden weights,
bias/output, action-linear and critic coordinates. Tests cover candidate-order labels,
outcome/label separation, masked inputs, forced-menu derivatives, real frozen updates,
PPO early-stop schedule matching, and exact reproduction of the historical PPO path.
Recipes bind sources, objective and budgets. Changed sources/results or an interrupted
output directory cannot silently restart. Every completed round is sealed separately;
an incomplete run reports failed/unattempted pairs and explicitly unknown unsealed work.

No game worker, native episode, production checkpoint or account profile is opened.
Synthetic outputs remain in `artifacts/synthetic-learning/native-conditional-teaching-v1`.
The old known-task controls, native source hashes and recovered pool remain unchanged.

## Reproduce or inspect

```bash
bash scripts/check-native-conditional-teaching-v1.sh
```

The wrapper reads its workspace and limits from the pinned recipe. One numerical thread,
three-minute wall/CPU cap, 1 GB memory and 20 MB output; no automatic next experiment.
Completed results are displayed with file seals checked and no repeated fitting. An
experiment can complete correctly while failing its learning criterion; inspect
`passing_training_seeds` separately from `comparison_integrity_pass`.

Recipe: `configs/native-controls/conditional-teaching-v1.json`.
Result: `artifacts/synthetic-learning/native-conditional-teaching-v1/report.json`.
Round/pair records and `assessment.json` are saved beside the result. The saved-only
assessment can be reproduced with `python -m spireshift.native_conditional_assessment
configs/native-controls/conditional-teaching-v1.json`; it cannot start fitting if the
source result is missing. Portable measurements:
`docs/evidence/native-conditional-teaching-v1.json`.
