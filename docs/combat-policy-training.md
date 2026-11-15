# Frozen public combat policy training

[Issue #130](https://github.com/benyanc/spireshift/issues/130) records the completed, rejected
base-v9 experiment. [Issue #132](https://github.com/benyanc/spireshift/issues/132) completed the
corrected owner training into base-v10. It selected an eligible epoch-20 combat adjustment and
passed every validation safeguard. This is saved-lesson evidence, not demonstrated playing
strength. The owner completed the separate [fresh paired comparison](combat-policy-confirmation.md)
in [issue #131](https://github.com/benyanc/spireshift/issues/131): both models lose all 32 games
without reaching the first boss, with no demonstrated playing benefit. The next owner task is
the [public replay diagnosis](combat-confirmation-diagnosis.md) in
[issue #133](https://github.com/benyanc/spireshift/issues/133). No retraining is needed yet.

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

## Completed owner training

The owner ran `scripts/train-combat-policy-v2.sh` on October 7, 2026 (Toronto time). It verified
the saved corpus and reconciled the gate proof before fitting. All **40 epochs** completed in
**86.824 wall / 70.110 CPU seconds**, with zero game attempts, simulations or transitions.
Epoch **20** was selected; status is `requires_fresh_confirmation`, and every original and
combat validation check passes. No checkpoint was promoted.

On train-selection combat lessons, soft pair loss improved from **0.691820304228 to
0.663125910126**, directional accuracy from **0.732289549621 to 0.805421339858**, and mean
run auxiliary regret from **0.001518543956 to 0.001400767759**. Choices changed on 26/126 states.
These are development scores under auxiliary labels.

On the original validation combat lessons, pair loss improved from **0.686691295139 to
0.669815816415**. Directional accuracy dipped from **0.760828195585 to 0.753058136507** within
the unchanged tolerance; auxiliary regret stayed **0.003378004808**. Only **3/69 combat choices**
changed, and all **135 non-combat predictions** and original model heads remain identical.
Thus the result is an eligible bounded update; it does not establish a stronger game-playing agent.

Saved under `artifacts/models/sts2-v0.107.1-base-v10/`:

- Checkpoint: `sha256:79aa82b8e1109fd968875ff2e025e2320461e3eb5027d5fa414d64afaf382705`.
- Training report: `sha256:5a70198d8bb9dd1100d7d78cfe55eb8e7f4e2c839efa430b882958ff03f2e56b`.
- Completed resource report: `artifacts/resources/combat-policy-base-v10-train-v2-attempt-1.json`,
  `sha256:2fdc83ae868ddf691b032c4f03dd074ae18c95bcd81325e88b53b2efae29727d`.

Peak resident memory was 1,155,366,912 bytes and output 3,549,066 bytes; exit zero, no cap hit.
Both training scripts now only check/display their respective completed results. No source audit
or retraining is needed. The rejected base-v9 remains preserved; accepted base-v2 remains unchanged.
The completed fresh comparison is archived in [its guide](combat-policy-confirmation.md).
The sole next owner command is in [the replay diagnosis guide](combat-confirmation-diagnosis.md).

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
These were fresh development confirmation runs, not a new final-test claim. The comparison
paired frozen base-v2 with the eligible frozen candidate, policy-only, with the same ObjectiveSpec
whole-run budget of 128 CPU seconds and a 4,096-decision safety cap. Model identities must be
fixed before any confirmation game is played. The separate implementation now binds these
identities to a frozen comparison plan. The owner completed all 64 attempts with zero victories
or boss reaches. See [combat-policy-confirmation.md](combat-policy-confirmation.md) for the
completed evidence and [combat-confirmation-diagnosis.md](combat-confirmation-diagnosis.md)
for the sole next command. This cohort has now been inspected.

Report terminal full-run victories first, with failures, unsupported decisions and truncations
in the original denominator; then paired floors, act milestones, latency and resource use.
Floor-only gains or all-zero wins cannot establish victory improvement or foundation readiness.
Do not tune against this cohort and describe a repeat on it as fresh confirmation. No automatic
extension, retry-driven seed replacement or promotion follows an inconclusive/negative comparison.

This experiment trains an auxiliary combat policy component. Terminal-value learning and the
readiness gate remain blocked by all-zero terminal outcomes. The project goal remains full-run
terminal victory under the whole-run computation budget; learned low/medium/high effort comes
after a competent base policy/value system passes readiness.
