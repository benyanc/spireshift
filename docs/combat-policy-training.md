# Frozen public combat policy training

[Issue #130](https://github.com/benyanc/spireshift/issues/130) records the completed, rejected
base-v9 experiment. [Issue #132](https://github.com/benyanc/spireshift/issues/132) corrects an
impossible selection check in a new experiment version. The next owner task is one training
run into base-v10. [Issue #131](https://github.com/benyanc/spireshift/issues/131) remains blocked
on an eligible, reviewed result before any fresh gameplay comparison.

The owner completed combat audit v2: all 529 combat states bind, with zero failures. Its frozen
coverage checks pass. Reliable learnable comparisons span 35 fitting and 13 selection seeds
(327 and 130 pairs). This permits a small training experiment. All saved continuations still
lose; the audit establishes usable lessons, not good gameplay.

The first owner training attempt stopped after 79.224 seconds, before any optimizer step or
model output. Original validation state `validation-seed-000225-combat-024` asks which hand card
to transform into Minion Strike (public selection kind 20). The prior decoder supported ordinary
combat and in-hand upgrades only. The failed resource report is preserved as attempt 1,
`sha256:d31f46c9e76d2717ea09d49e19ef6bcd1e4554f5fd370176a388c179c523b32c`.
This is a screen-support bug, not a measured training rejection or gameplay result.

The corrected residual layout v3 supports that public choice explicitly. A bounded compatibility
check of the saved validation inputs passed **69/69 combat screens** (68 ordinary, one transform)
in 0.562 seconds, with zero teacher batches opened, labels analyzed, optimizer steps or games.
The owner trainer now performs this check before the large source audit. No screen is removed,
no threshold or training setting is changed, and the completed foundation audit v2 stays intact.

The owner retry completed all 40 epochs in **87.820 wall / 69.952 CPU seconds**, with zero new
games, simulations or transitions. Every epoch failed the absolute selection quality gate;
epochs 21–40 also exceeded the unchanged 0.05 combat drift limit. Base-v9 saved epoch zero and
an empty correction. Its passing final validation describes the unchanged base-v2 fallback,
not any discarded training epoch. Base-v9 is rejected/no-update and has not been promoted.

Saved checkpoint: `sha256:78c2b31aa3ca4e61c02b4214ee6572b4c9a5eb794377872d4f300eb603d83a85`;
training report: `sha256:c15666034fe6a08e481b68fe949bd8fddaf6d94a7f77f97dce25f5259a6c0dec`;
attempt-2 resource: `sha256:8d280b1c8238e2dff45520b2b1be1a8cce56d797ac17bd3e653b68aed65d4b0a`.
All remain preserved under the original base-v9 and numbered resource paths.

## Why the selection check needs correction

We mistakenly required a combat-only update to pass an absolute quality check on all choices
in the train-selection data. That data includes **126 combat and 195 frozen non-combat choices**.
Even perfect combat would leave at least **0.002502875629** mean auxiliary regret from the frozen
choices alone. The check requires less than its **0.001992810927** source-order reference.
It was therefore impossible to pass. Another part of that gate reused a soft-target reference
from the original validation population on this different train-selection population.

The bounded diagnostic reads only already-verified saved training, resource, parent and foundation
artifacts. It opens no source cases and does no fitting or games. Its result is
`artifacts/diagnostics/sts2-v0.107.1-base-v9-combat-gate-v1/diagnostic.json`,
`sha256:9cee3b31d58b406ef456403aa130284e16e92f061429ab19a2d4aef6e5cce71b`.
The next owner trainer checks this arithmetic against the actual source examples before its first
optimizer step. A discrepancy stops training.

Recipe v3 applies all numerical parent-relative safety checks to train-selection. It keeps the
absolute overall quality check on the original validation data, where the reference belongs.
This is an explicit protocol correction after inspecting development results. The numerical
tolerances, optimizer, source data, folds and unused fresh-run reservation do not change. It
does not reinterpret the rejected v9 result as successful or reconstruct discarded epoch weights.
The improved recorded combat scores are auxiliary evidence, not demonstrated playing strength.

## Run this one next command

The owner launches and monitors this job:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/train-combat-policy-v2.sh
```

It first checks public validation screen compatibility, verifies the saved evidence and reconciles
the diagnostic against the source examples. It then trains one combat adjustment for 40 epochs,
checks the original validation data and saves a separate base-v10 candidate. No game attempts, hidden-world resampling,
fresh collection or evaluation follow. The trainer prints progress every ten epochs. Share the
final summary and resource report before the separate fresh-run comparison is implemented/launched.

One worker; caps of **30 minutes wall time, 3,600 CPU seconds, 8 GB memory and 1 GB output**.
Allow several minutes, including re-reading the approximately 1 GB source corpus. The previous
40-epoch job took about 88 seconds on the owner's Mac; the corrected version has not been timed.
These caps are safeguards, not an ETA.
Interrupted attempts keep separate resource reports. Completed reruns check/display only the
saved checkpoint and report; they do not re-audit the corpus or retrain. Partial model outputs
are preserved and cause a clear stop instead of overwriting them.

Results are saved under `artifacts/models/sts2-v0.107.1-base-v10/` as `checkpoint.json` and
`training-report.json`. Resources use numbered `artifacts/resources/combat-policy-base-v10-train-v2-attempt-*.json`
paths. Accepted base-v2 stays unchanged. No automatic promotion or adaptive-controller fitting occurs.
The old v1 script only displays the completed v9 result. Use the new v2 script above for the
scope correction. Failed preflights also record explicit zero game counters.

## Frozen experiment

Configuration: `configs/combat-policy/sts2-v0.107.1-base-v2-combat-residual-v3.json`,
`sha256:5dca8903d483a6d510f7266c8a41bb3390b8f32807b08783265e437c7c836cce`.
The v1 recipe remains archived with the failed binding attempt; v2
(`sha256:ff6d4537526d831c555e3f3a9d8da7ebad8aaaf3f3ff4fcab7b94df2fa40d122`) binds the
completed rejected v9 result. Recipe v3 changes the selection gate's scope and embeds the saved
diagnostic. Reconstructing v2 from it must reproduce the original configuration hash exactly:
source datasets, original audit, optimizer, complete-run folds, numerical safety limits and
reserved fresh-run cohort are identical. Legacy v1/v2 gate semantics remain unchanged.
It binds the completed owner audit
`sha256:57666476aa7c42ce76cb46a44e9eb422ab7bfb21abf4b752e8cb0110ab3948fd`,
the full original audit configuration, accepted base-v2 checkpoint/report, composed train corpus,
original 204-record validation-v2 corpus, frozen non-policy validation metric hashes and ObjectiveSpec.
The owner verification reconstructs the entire audit from source once and requires an exact match.
No game engine is initialized.

The model adds a sparse combat-only correction using the versioned public card/target features.
Its 8,192 features encode visible card identities, upgrades, enchantments, potions, end turn,
enemy targets and public combat context. It supports the admitted ordinary combat, public
UpgradeInHand and TransformHandToMinionStrike selection layouts. A transform action chooses
the visible card rather than playing it. Historical enemy-target decorations are ignored by
the pinned selection resolver and do not become features. The generated upgrade flag and source
card are not observable and are not inferred. Other selection kinds fail explicitly and must remain failed
runs in subsequent evaluation; no unsupported choice silently becomes a parent-policy choice.
Card cost/damage and exact rules are not inferred from an identifier. This is a bounded linear
residual, not a completed mechanics model or a proven strong agent.
Layout v3 preserves every existing v2 token and its hashed vector coordinates; only the newly
supported selection receives new semantic tokens. Its independent encoder/layout identity
records the compatibility extension without changing the archived audit's feature space.

The original policy weights and all value/risk/floor heads remain byte-for-byte unchanged.
Non-combat predictions remain identical. The parent policy may still depend on execution indices;
permutation invariance of the new correction does not make the combined policy invariant.
Serialized inference is checked against training scores on every original validation decision.

Only the audited **84 fitting seeds** update the residual. The unchanged **28 selection seeds**
choose an epoch. These are reused train/development seeds, some previously seen by the parent.
Qualified labels retain the original audit rules: 16 terminal paired samples, matching strict
directions in both halves and a margin above 0.25; terminal victory precedes floor. Soft empirical
pair probabilities are retained, rather than turning each observed winner into a certain target.
Every informative complete run receives equal weight, every informative state within its run
receives equal weight, and margins distribute that state's weight among correlated pairs.
All fitting combat states also anchor probabilities to the parent.

One recipe: 40 full-batch Adagrad steps, learning rate 0.0005, parent-anchor strength 0.5,
residual shrinkage 0.1, gradient clip 5 and epsilon 1e-8. The small step size accounts for the new
feature space's scale in synthetic checks; no production result was used to tune it.
Metrics use exactly the quantized weights that can be serialized. No grid search or selection refit.

An epoch needs at least 0.001 lower selection soft pair loss and all numerical safeguards: no more
than 0.01 worse original pair loss, 0.02 lower accuracy, 0.0002 higher auxiliary regret or 0.05
mean probability drift relative to the parent. Additional combat-only safeguards
apply these same tolerances to complete-run-balanced combat metrics, so unchanged non-combat
decisions cannot hide combat damage. The history continues to report the failing absolute
train-selection gate for transparency, but recipe v3 does not use it to select an epoch.

The original development validation, including its absolute auxiliary quality gate, is checked
after the train-selected epoch is frozen; it
does not choose a different epoch or update weights. If no selection epoch qualifies, the saved
head is empty and reproduces base-v2 exactly. If a selected epoch fails final validation, its
candidate is preserved for diagnosis and blocked from policy execution. A passing result is only
eligible for fresh confirmation. None of these outcomes promotes a checkpoint.

## Reserved fresh gameplay comparison

Before training, reserve 32 complete train seeds at split offsets **504–535**, beyond the prior
starting-study cohort. Seed metadata from all seven prior inventories is checked for overlap.
These are fresh development confirmation runs, not a new final-test claim. The comparison will
pair frozen base-v2 with the eligible frozen candidate, policy-only, with the same ObjectiveSpec
whole-run budget of 128 CPU seconds and a 4,096-decision safety cap. Model identities must be
fixed before any confirmation game is played. It needs a separate owner command and implementation.

Report terminal full-run victories first, with failures, unsupported decisions and truncations
in the original denominator; then paired floors, act milestones, latency and resource use.
Floor-only gains or all-zero wins cannot establish victory improvement or foundation readiness.
Do not tune against this cohort and describe a repeat on it as fresh confirmation. No automatic
extension, retry-driven seed replacement or promotion follows an inconclusive/negative comparison.

This experiment trains an auxiliary combat policy component. Terminal-value learning and the
readiness gate remain blocked by all-zero terminal outcomes. The project goal remains full-run
terminal victory under the whole-run computation budget; learned low/medium/high effort comes
after a competent base policy/value system passes readiness.
