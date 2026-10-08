# Compact neural combat pilot

[Issue #134](https://github.com/benyanc/spireshift/issues/134) starts with this bounded
representation experiment. Implementation is ready; actual source verification and training
are for the owner. No production fitting, new games or automatic follow-up have run.

## Run this one next command

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/train-neural-combat-policy-v1.sh
```

This verifies the existing saved lessons and fits **one network for 40 epochs**, with one worker.
It stops after saving and displaying the result. It does not collect data, start the game,
simulate alternative futures, run gameplay confirmation or begin a second round.

The caps are **30 minutes wall time, 3,600 CPU seconds, 8 GB memory and 1 GB output**. These are
limits, not a measured runtime estimate. The script limits numerical-library thread pools as
well as declaring one worker. NumPy is the only added numerical dependency; inference itself
uses the standard library and needs neither a GPU nor NumPy.

Outputs are `artifacts/models/sts2-v0.107.1-base-v11/checkpoint.json` and `training-report.json`.
Resource reports use numbered `artifacts/resources/neural-combat-base-v11-train-v1-attempt-*.json`
paths. Completed reruns verify/display saved results without source re-audit or fitting. Failed
attempt reports remain preserved; a new attempt uses a new resource path. A partial model/report
pair stops for review rather than overwriting output. Interrupted fitting is restarted from the
frozen initialization, not falsely described as resuming an optimizer checkpoint.

Share the final summary and resource report before the next experiment. Base-v2 stays accepted
regardless of training completion; an eligible candidate still needs separate gameplay evidence.

## Evidence and hypothesis

The [completed public diagnosis](combat-confirmation-diagnosis.md) reconciles all 64 inspected
comparison replays. Both players lost all 32 runs and never reached the first boss. The linear
combat correction mostly altered potion use and some card choices; recorded card coverage gaps
remain. On seed 631's shared public prefix at decision 14, both policies target the same enemy
but choose different visible cards. This is an observed disagreement, not evidence that either
card would win the run. No diagnostic counts are converted into new training labels.

The old combat encoder broadcasts each context feature under the chosen card/potion identity.
Its linear correction therefore learns many context rules separately for different identities.
The hypothesis is that **shared printed card properties and nonlinear state/action interactions
transfer existing lessons better**, especially when a card lacks reliable fitting labels.
This does not establish that representation is the sole cause of weak play or that the current
continuation teacher is strong enough. The saved-data stage can reject a candidate before
spending more games.

## Network and information boundary

The candidate adds a neural combat score to the accepted sparse policy's score. It uses 512
shared feature coordinates, a fully trainable 32-unit `tanh` hidden layer and a trainable scalar
output: **16,448 parameters**. Hidden weights and biases, not just output weights, receive
gradients. The output starts at zero, reproducing the parent before any update.

Inputs reuse the verified public combat binding: visible player resources/statuses, hand,
potions, enemy HP/block/intents/targets, orbs and publicly promised incoming cards. Chosen card
type, target class, printed cost/damage/block, upgrade deltas and selected printed keywords
come from 577 pinned card definitions. IDs remain categorical; operational action indices locate
objects, and handles, seeds, hashes, RNG and hidden draw order do not become neural features.

Printed descriptors are not exact resolved damage, effective cost or block. Special card code,
multi-hit effects, buffs, relics and keyword changes can alter those effects. The network must
learn from outcomes rather than treating these descriptors as a complete combat simulator.
Unknown metadata, changed backend source hashes or reliable pairs that become identical encoded
features fail explicitly. The output has exactly one score per supplied legal action; no action
outside the legal menu is sampled. Public upgrade and hand-transform selections reuse layout v3.

All non-combat choices and original run-value/risk/floor heads remain frozen. Both-layer
gradients are checked numerically, and serialized predictions are checked against training
scores. Epoch-zero rejection reproduces the parent and cannot be deployed as an advanced player.

## Frozen experiment and stop rules

Recipe: `configs/neural-combat/sts2-v0.107.1-base-v2-neural-v1.json`,
`sha256:576afc9e851e16535e879d5253f39db531c45812e36badd0f453fcb04dab65d7`.
It binds the previously verified train corpus (1,299 states, 112 complete runs), accepted parent,
original validation corpus, complete-run fitting/selection folds, corrected gate arithmetic,
diagnostic evidence, printed catalog/source hashes and terminal-victory objective.

- Use the same reliable, uncertainty-aware action comparisons and equal-run/equal-state pair
  weighting as the combat audit. Labels remain auxiliary because all saved terminal outcomes lose.
- Optimize once with Adam, learning rate 0.003, anchoring 0.5, L2 0.0001 and gradient clipping 5.
  This is a disclosed new recipe after inspecting prior development results, not retroactive
  acceptance of an old checkpoint or an untouched-test claim.
- Choose the epoch only on the train-selection runs, using unchanged advancement/non-regression
  tolerances. Original development validation is scored after selection and cannot select an
  epoch. The absolute original-validation quality requirement remains mandatory.
- Reserve 32 separate train development seeds at offsets **536–567** for later policy-only
  comparison, excluding the already inspected 504–535 cohort. The source linear recipe's old
  reservation is retained as historical data provenance and is not the neural comparison cohort.
  Final test seeds remain sealed. No reserved games run in the training script.
- Terminal victory under the original whole-run compute budget remains primary. Floor/combat
  gains are intermediate evidence; no all-loss corpus establishes a calibrated victory head.
  There is no automatic promotion, readiness pass, adaptive-controller fitting or GA fallback.

A bounded check bound three existing public snapshots and all their legal candidates against
the new metadata/feature encoder, without teacher-source re-audit, model fitting or games. It is
binding evidence only. The owner's training command performs the full source checks before any
gradient; every audit denominator and original complete-run fold is retained.

## Later stages in #134

After the owner result is reviewed, an eligible candidate can receive the separate frozen
gameplay comparison at the original 128-CPU-second-per-run budget. Only actual separate-run
benefit supports the next collection/teacher-label/train round. Existing on-policy collection,
action guards and full-run rollouts accept the new checkpoint through the shared policy loader.
No new collection framework is needed.

The first round is the saved-data representation pilot. Later recipes must bind their own
sources and resource budgets before launch. Review the direction after at most three frozen
rounds without repeatable gameplay gain; the coding agent does not run those rounds automatically.
The deferred [genetic/hybrid option](https://github.com/benyanc/spireshift/issues/135) remains an
owner choice. #134 stays open until the owner-run learning/gameplay cycle has useful evidence.
