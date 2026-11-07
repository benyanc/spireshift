# Public combat features and saved-data audit

[Issue #129](https://github.com/benyanc/spireshift/issues/129) implements this foundation package.

Starting-choice study #128 completed all 192 seeds and 576 branches, without failures,
truncations or victories. Its frozen primary result was inconclusive: three qualified matched
groups covered only two confirmation seeds, with no non-tied strong confirmation comparisons.
Agreement was 0.5 with interval [0, 1]. The stop rule ends that starting-choice experiment;
it does not prove that option values are universally noisy or that missing context caused failure.
Base-v2 remains accepted. We now return foundation work to combat and full-run competence.

The first owner audit completed in 90.350 wall seconds, verifying all 1,299 source records.
It bound 528 of 529 combat states. Useful advancement evidence covers 35 fitting and 13 selection
runs (327 and 130 learnable comparisons), passing the frozen signal/coverage checks. The remaining
state, `train-seed-000211-combat-078`, is a public "choose a card to upgrade" screen that the
ordinary-combat decoder correctly refused. All saved outcomes still have zero terminal victories.
The initial data gate failed; no threshold was lowered.

Audit v2 adds explicit binding for this upgrade screen and preserves the original report
`sha256:bbc8f06283407ec80648e98d358d55d3710e05ce9c9d4428a805e738fbffe994`.
The first audit's resource report is
`sha256:68b8ada770dd9d71a23f2015c8ba7cdd43bc2596514ba1d9534fd8f481f194b0`;
its game/simulation/transition counters are all zero. The owner subsequently completed the
corrected v2 audit: **529/529 combat states bind, zero failures, all frozen coverage checks pass**.
The same 35 fitting and 13 selection signal runs remain, with 327/130 learnable comparisons.

## Completed owner audit and next step

Audit report `sha256:57666476aa7c42ce76cb46a44e9eb422ab7bfb21abf4b752e8cb0110ab3948fd`
verified all 1,299 records and 112 complete train runs in **71.490 wall / 56.792 CPU seconds**,
with 1,133,805,568 bytes peak resident memory and 5,310,629 bytes output; exit zero, no cap hit.
Resource report: `sha256:cae8892187eabbd0ce0905d2214008684826e658eadf1573358e03552b797f6d`.
All game/simulation/transition counters are zero. The result is saved at
`artifacts/combat-foundation/sts2-v0.107.1-base-v2-audit-v2/combat-foundation-audit.json`.
Both audit scripts now only display their completed cached results. No audit rerun is needed.

The owner subsequently completed combat training, but its 40 epochs all failed an impossible
absolute selection gate: frozen non-combat choices alone exceed the required error limit.
Base-v9 retained an empty correction. The [combat policy training guide](combat-policy-training.md)
records that rejection and the completed recipe-v3 scope correction. The corrected owner run
reconciled the proof against source data, selected eligible epoch 20 into base-v10 and passed
every safeguard, with no games run during training. The owner completed the
[reserved fresh comparison](combat-policy-confirmation.md): both models lose all 32 runs,
neither reaches the first boss and their auxiliary mean floors are nearly identical. This
eligible adjustment did not establish better play. The next task is the
[public combat replay diagnosis](combat-confirmation-diagnosis.md) before another training
change. Full-run competence, terminal-value readiness and adaptive effort are still unproven.
Base-v2 remains accepted.

## What changed

The existing generic encoder includes combat as numbered vector slots and action/target indices.
The separate public card/target feature space directly binds each legal action to
the visible card, upgrade and enchantment, a potion, or ending the turn, and its visible enemy
target. It encodes identifiers categorically, public numeric properties separately, player/enemy
statuses, intents, hand composition, promised cards and orbs. Enemy position remains a categorical
public locator because position can matter to mechanics. It does not infer cost, damage or a
hidden future from a card ID. Action handles and hand execution indices are absent from features.

Binding follows the pinned engine's public action convention: hand slots play cards, hand count
ends the turn, and subsequent indices bind potion slots. The 682-field layout, patch, ruleset and
five observation/action/constant/status/selection source-file hashes are frozen. In this layout Strength's
status ID is zero; a nonzero amount distinguishes it from empty padding. Missing fields, invalid
targets, unsupported selection screens and inconsistent public fields fail closed and remain in
the audit denominator. Non-combat decisions retain the parent path.

The versioned `evangambit-public-card-target-v2` layout reads the visible upgrade selection's
kind, count and candidate cards, and binds each action to the selected unupgraded card in hand.
Selection indices are execution locators, not feature magnitudes. The pinned engine ignores enemy
targets on this screen; historical target decorations keep their original source handles and
candidate alignment but do not become enemy-choice features. Duplicate encodings of one choice
remain semantically identical, not independent learning signal. The complete public choice set
must be present. Malformed, out-of-range, missing or invisible choices and skip/end-turn/potion
indices fail closed. Other selection kinds remain unsupported; no unseen source-card identity,
selection amount or hidden future is inferred. The old v1 namespace and cached report stay valid.

This audit modifies neither the original encoder nor any checkpoint. The new feature space is
preparation for the separate combat policy residual; the real training job remains owner-run.
Hand permutation tests establish equivalence of these new features alone, not invariance of the
original parent policy. The codec is not an exact mechanics solver or evidence of patch robustness.

## Frozen audit and decision

The current configuration is `configs/combat-foundation/sts2-v0.107.1-base-v2-audit-v2.json`, identified by
`sha256:7a2f0faedda78573834935a6d304e556fd4011b067a393b9b82d7ad329f527c5`.
It binds accepted base-v2, composed dataset
`sha256:bf26c88358111fd70a1a30c8e9bd59be29080a3d69d93d3714223955545c22ac`,
the completed starting study, complete-run train ownership and the whole-run `ObjectiveSpec`.
An outcome-independent salted split assigns 84 fitting and 28 selection seeds before this audit.
The v2 repair retains exactly the v1 source corpus, parent, folds, objective, resource caps and
signal thresholds. Only the public encoder/layout binding and selection source hash change.
These are reused development seeds, including some already seen by the parent. No validation or
test data are read and no untouched evaluation claim follows.

For each combat state, the report retains public candidate bindings, semantic feature digests,
hash aliases, the parent's saved-teacher auxiliary regret and every paired comparison. A reliable
advancement comparison needs at least 16 completed paired samples, matching strict directions in
both sample halves and a preference margin above 0.25. Its rank compares terminal victory first,
then maximum floor. Censored samples, ties, unstable pairs and semantically indistinguishable or
hash-aliased choices cannot qualify as learnable advancement. Comparison and state counts are
reported separately from independent complete-run coverage.

The pilot data gate needs every combat state to bind, signal on eight fitting and four selection
seeds, four distinct fitting card IDs in qualifying comparisons, and two fitting source-floor bins.
The completed passing result permits a frozen residual-training recipe with fresh complete-run
confirmation; it does not start training, promote a model or establish good gameplay. Insufficient labels call
for a bounded combat teacher plan; binding failures require repair before training. No automatic
collection, gate relaxation or experiment extension follows.

The owner task verifies all curriculum cases and linked paired batches, and checkpoint/report
identities. Layout hashes verify source provenance, not new native-engine conformance. The prior
starting-study check verifies its cached report identity and frozen stop decision without replaying
its branches. Completed display checks cached identity, bindings, row/summary reconciliation and
the coverage decision; it does not re-audit source files. New game-work counters are explicitly zero.
Raw examples and reports remain ignored under `artifacts/`.

Full-run terminal victory under the whole-run compute budget remains the project goal. Floor and
teacher-regret labels stay auxiliary. The terminal-value readiness gate and learned adaptive
controller remain blocked. A future combat residual must preserve non-combat behavior and the
parent's non-policy heads, then demonstrate benefit on a newly frozen run cohort before promotion.
