# Frozen public combat policy training

[Issue #130](https://github.com/benyanc/spireshift/issues/130) tracks this owner-run training
experiment. [Issue #131](https://github.com/benyanc/spireshift/issues/131) tracks the separate
fresh gameplay confirmation and is blocked on an eligible, reviewed training result.

The owner completed combat audit v2: all 529 combat states bind, with zero failures. Its frozen
coverage checks pass. Reliable learnable comparisons span 35 fitting and 13 selection seeds
(327 and 130 pairs). This permits a small training experiment. All saved continuations still
lose; the audit establishes usable lessons, not good gameplay.

## Run this one next command

The owner launches and monitors this job:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/train-combat-policy-v1.sh
```

It verifies the saved evidence, trains one combat adjustment for 40 epochs, checks the original
validation data and saves a separate base-v9 candidate. No game attempts, hidden-world resampling,
fresh collection or evaluation follow. The trainer prints progress every ten epochs. Share the
final summary and resource report before the separate fresh-run comparison is implemented/launched.

One worker; caps of **30 minutes wall time, 3,600 CPU seconds, 8 GB memory and 1 GB output**.
Expected duration is several minutes, including re-reading the approximately 1 GB source corpus;
the new training step has not been timed on that corpus. These caps are safeguards, not an ETA.
Interrupted attempts keep separate resource reports. Completed reruns check/display only the
saved checkpoint and report; they do not re-audit the corpus or retrain. Partial model outputs
are preserved and cause a clear stop instead of overwriting them.

Results are saved under `artifacts/models/sts2-v0.107.1-base-v9/` as `checkpoint.json` and
`training-report.json`. Resources use numbered `artifacts/resources/combat-policy-base-v9-train-v1-attempt-*.json`
paths. Accepted base-v2 stays unchanged. No automatic promotion or adaptive-controller fitting occurs.

## Frozen experiment

Configuration: `configs/combat-policy/sts2-v0.107.1-base-v2-combat-residual-v1.json`,
`sha256:0a2b3411f1c41bb9cb59ecc0a23cf6f20b0b583e1d88bf51a277e1c31b962b3f`.
It binds the completed owner audit
`sha256:57666476aa7c42ce76cb46a44e9eb422ab7bfb21abf4b752e8cb0110ab3948fd`,
the full original audit configuration, accepted base-v2 checkpoint/report, composed train corpus,
original 204-record validation-v2 corpus, frozen non-policy validation metric hashes and ObjectiveSpec.
The owner verification reconstructs the entire audit from source once and requires an exact match.
No game engine is initialized.

The model adds a sparse combat-only correction using the versioned public card/target features.
Its 8,192 features encode visible card identities, upgrades, enchantments, potions, end turn,
enemy targets and public combat context. It supports the admitted ordinary combat and public
UpgradeInHand selection layouts. Other selection kinds fail explicitly and must remain failed
runs in subsequent evaluation; no unsupported choice silently becomes a parent-policy choice.
Card cost/damage and exact rules are not inferred from an identifier. This is a bounded linear
residual, not a completed mechanics model or a proven strong agent.

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

An epoch needs at least 0.001 lower selection soft pair loss and all frozen safeguards: no more
than 0.01 worse original pair loss, 0.02 lower accuracy, 0.0002 higher auxiliary regret or 0.05
mean probability drift, plus the original auxiliary policy gate. Additional combat-only safeguards
apply these same tolerances to complete-run-balanced combat metrics, so unchanged non-combat
decisions cannot hide combat damage.

The original development validation is checked after the train-selected epoch is frozen; it
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
