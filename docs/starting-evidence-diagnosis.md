# Saved starting-choice learning diagnosis

[Issue #42](https://github.com/benyanc/spireshift/issues/42) now has an audit for the completed
base-v8 experiment. That experiment selected no update: its best overall selection-loss gain
was 0.000926394179, below the frozen 0.001 minimum. Higher-floor comparisons improved more,
while weaker enemy-damage comparisons slightly worsened. Accepted base-v2 remains unchanged.

The audit checks whether similar visible starting situations receive opposing fitting targets,
whether weaker targets pull against stronger targets, and how the original policy constraint
acts locally. It also reconciles the saved learning curves and frozen rejection checks. It does
not assume that any one of these mechanisms caused the rejection.

## Completed owner-run result

The owner completed the full source audit on 2026-10-05 (Toronto time). Reconciliation passed:
the sources, saved checkpoint, recorded history and frozen rejection checks agree. The report's
content identity, frozen bindings and JSON schema also pass bounded saved-file verification.
No update was accepted; base-v8 retains epoch zero and accepted base-v2 remains unchanged.

| Fitting diagnostic | Result |
| --- | --- |
| Opposing semantic-contrast groups | 9 of 115 groups |
| Independent runs within each opposing group | 2 |
| Incompatible strict margins after parent offsets | 1 group |
| Different semantic contrasts sharing an identical hashed contrast | 0 |
| Zero residual contrasts | 0 |
| Initial strong/weak gradient cosine | +0.280803741259 |
| Opposing original teacher-target matches | 14 across 11 preference runs and 12 anchor runs |

All nine opposing groups share the encoded resource/act context but have different full public
states and starting menus. Eight involve weaker frontier comparisons; one opposes two higher-floor
comparisons. They are examples of differing realized lessons, not nine proven contradictions in
expected value. Only one group's strict margins cannot all be satisfied by its shared residual
contrast after parent offsets. Different menus and other omitted public context remain possible
explanations alongside variation in seeded futures.

The positive initial gradient cosine does not support an initial aggregate tug-of-war between
strong and weak fitting targets. It says nothing about discarded later weights. The absence of
complete hashed-contrast aliases does not prove that the representation is sufficient or that
individual coordinates never collide. The 14 opposing teacher-target matches have no exact public
state matches; the optimizer's actual anchor remains the parent distribution, not those targets.
Local anchor curvature is a constraint, not proof that anchoring caused rejection.

The audit took **41.903 wall seconds**, 33.825 CPU seconds, 551,993,344 bytes peak resident memory
and 1,339,231 bytes output. No resource cap was hit. It took zero optimizer steps, replayed zero
games and promoted no checkpoint. Report identity:
`sha256:e2b7bbc906863488289f33cc05bb00bced9366130fee47261a5a8aa6d9759280`.
Resource identity:
`sha256:82a34d11a711eac1ae3ed6b72d7949801948db05905374007db49507c864c155`.

The subsequent [issue #128](https://github.com/benyanc/spireshift/issues/128) study completed
all 192 fresh seeds and 576 terminal branches. Its frozen primary matching covered only two
confirmation seeds and no non-tied strong comparisons; the result was inconclusive. The stop
rule ends the starting-choice experiment. The cause of the rejected update remains unresolved.
The next owner command is the saved-data check in the [combat foundation guide](combat-foundation.md),
which prepares explicit public card/target features before another combat policy experiment.
Do not repeat this diagnosis or the starting study as the next task.

## Archived owner command

The completed audit used this command; it is not the next task:

```bash
bash scripts/diagnose-starting-evidence-policy-v1.sh
```

The owner launches and monitors the full saved-data audit. It uses one worker with caps of
**10 wall minutes**, 600 CPU seconds, 4 GB memory and 50 MB output. Reading and verifying the
original curricula can take more than 30 seconds before the diagnostic calculations start.
The script prints when the audit starts. There is no optimization, new collection, engine
replay, game attempt, follow-up training, candidate selection or promotion.

The full report is saved outside Git at
`artifacts/diagnostics/sts2-v0.107.1-base-v8-starting-evidence-v1/diagnostic.json`.
Resource reports use
`artifacts/resources/starting-evidence-base-v8-diagnostic-v1-attempt-N.json`.
An interrupted attempt preserves its resource report; another attempt uses a new report path.
An existing completed diagnostic is displayed after its content identity and frozen bindings
are checked. That display does not repeat the source audit. Existing outputs are never replaced.

## Frozen inputs and scope

The config is `configs/starting-evidence-diagnostic/sts2-v0.107.1-base-v8-v1.json`, identity
`sha256:93f66b34670c7f70196f26cc4176c6897d194ffe272afbc7ecde237d68727680`.
It binds the unchanged starting-option training config, the actual base-v8 checkpoint/report,
and the completed training resource report. The original training recipe binds the parent,
evidence, source assignment, curricula, ruleset, complete-run groups and terminal-victory objective.
The resource command's paths, output roots and objective must agree with those actual sources.

Source loading and saved-model verification run once. The same checks used by the training-result
verifier reconstruct coverage, the frozen parent and final saved predictions. Fitting anchors keep
their 49/15 groups; new evidence keeps its 48/16 groups. Neither selection nor validation contributes
to fitting gradients, target-conflict evidence or categorical vocabulary.

Each recorded epoch is checked against the actual fitting/selection inventory: run IDs, counts,
effective weights, integer accuracy counts, component coverage and run-normalized loss arithmetic.
Frozen advancement and original selection-anchor safety checks are reconciled by the saved-report
loader. The report retains all epoch losses by run and rank component, and shows gains against
the parent, the best recorded epoch and its distance from the frozen minimum.

**Discarded intermediate weights were not saved.** Those history checks verify recorded arithmetic,
ownership and gates; they cannot independently reproduce intermediate predictions or gameplay.
The final all-204 validation checks describe the unchanged epoch-zero fallback, not epoch 40.
No discarded epoch is reconstructed or promoted by this audit.

## Conflicting evidence and local learning constraints

The diagnostic uses the same public option tokens as inference, before feature hashing. This
preserves the existing encoder and lets the report distinguish shared semantic features from
different semantic contrasts that happen to have identical hashed coordinates. Shared individual
coordinates alone do not establish an unusable contrast. Unknown categories retain the original
fitting-only fallback. Menu indices remain execution bindings, not learned numeric identities.

Every comparison retains its complete run, public context, option identities, rank component,
parent margin and initial fitting-gradient association. Coverage is grouped by option and role;
these overlapping comparison counts are not additional independent samples. Semantic conflict
groups include only fitting comparisons and show both directions explicitly. Identical feature
contrasts with opposite realized labels may reflect omitted context or randomness in future play;
they do not prove contradictory expected values or a bug. Frozen parent logits may differ even
when residual contrasts match. The report computes the bounds on a shared residual margin after
these parent offsets, distinguishing opposite labels from genuinely incompatible strict margins.

Strong and weak gradient components use the **same full fitting-run denominators**. Filtering
and renormalizing each component separately would misrepresent their relative influence. Their
sum is checked against the shared trainer's analytic derivative at immutable base-v2. Initial
descent effects on fitting and selection margins are associations, not a saved AdaGrad update.

The anchor audit uses only original fitting anchors. It reports preference/teacher disagreements
under matching public features, teacher confidence multipliers and initial descent directions.
The actual optimizer anchors to the **parent policy distribution**, not teacher utilities. Its
anchor and proximal gradients are zero at the parent. The audit computes the local curvature
along a unit preference-descent direction without taking a step. Curvature shows a local
constraint; it does not establish that anchoring prevented acceptance.

## Limits on the next decision

The completed report recommends measuring fitting-label repeatability. It does not identify a
causal mechanism or authorize a training update. A best loss at the final epoch alone cannot
justify training longer against the inspected selection set. Do not lower the 0.001 minimum,
accept epoch 40 or repeat the identical recipe.

Any later experiment needs a new frozen recipe, resource cap and fresh confirmation plan.
The existing selection and development-validation data have been inspected and cannot become an
untouched final test. No threshold is relaxed. Floor and frontier comparisons remain auxiliary:
zero terminal victories still block terminal-value promotion and adaptive-controller training.
Full-run victory under the whole-run compute budget remains the primary objective.

The coding agent implements and runs short deterministic toy tests and bounded metadata/feature
checks only. The full source audit remains owner run. Code is not pushed and GitHub Actions is not
triggered while the Actions budget is constrained.
