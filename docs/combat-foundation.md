# Public combat features and saved-data audit

[Issue #129](https://github.com/benyanc/spireshift/issues/129) implements this foundation package.

Starting-choice study #128 completed all 192 seeds and 576 branches, without failures,
truncations or victories. Its frozen primary result was inconclusive: three qualified matched
groups covered only two confirmation seeds, with no non-tied strong confirmation comparisons.
Agreement was 0.5 with interval [0, 1]. The stop rule ends that starting-choice experiment;
it does not prove that option values are universally noisy or that missing context caused failure.
Base-v2 remains accepted. We now return foundation work to combat and full-run competence.

## Run this one next command

The owner launches and monitors this saved-data task. It starts no game, simulation, training,
controller fitting or follow-up job:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/audit-combat-foundation-v1.sh
```

It verifies the existing 1,299-record train corpus, including 529 combat records from 112 complete
train runs. This may take several minutes because the linked teacher evidence is approximately
1 GB. Caps are one worker, 600 wall seconds, 1,200 CPU seconds, 4 GB memory and 1 GB output.
Interrupted attempts retain their resource reports. Rerunning repeats the saved-data audit with
a fresh resource-report name; completed reruns only check/display the cached result.
The final result is `artifacts/combat-foundation/sts2-v0.107.1-base-v2-audit-v1/combat-foundation-audit.json`.
Share its final summary before training or collecting anything else.

## What changed

The existing generic encoder includes combat as numbered vector slots and action/target indices.
The separate `evangambit-public-card-target-v1` feature space directly binds each legal action to
the visible card, upgrade and enchantment, a potion, or ending the turn, and its visible enemy
target. It encodes identifiers categorically, public numeric properties separately, player/enemy
statuses, intents, hand composition, promised cards and orbs. Enemy position remains a categorical
public locator because position can matter to mechanics. It does not infer cost, damage or a
hidden future from a card ID. Action handles and hand execution indices are absent from features.

Binding follows the pinned engine's public action convention: hand slots play cards, hand count
ends the turn, and subsequent indices bind potion slots. The 682-field layout, patch, ruleset and
four observation/action/constant/status source-file hashes are frozen. In this layout Strength's
status ID is zero; a nonzero amount distinguishes it from empty padding. Missing fields, invalid
targets, open card-selection screens and inconsistent public fields fail closed and remain in
the audit denominator. Non-combat decisions retain the parent path.

Neither the original encoder nor any checkpoint is modified. The new feature space is preparation
for a separate combat policy residual, not a trained residual or a stronger playing agent.
Hand permutation tests establish equivalence of these new features alone, not invariance of the
original parent policy. The codec is not an exact mechanics solver or evidence of patch robustness.

## Frozen audit and decision

The configuration is `configs/combat-foundation/sts2-v0.107.1-base-v2-audit-v1.json`, identified by
`sha256:f589db7864141cfe5de236a9eb15b7ab77c61fe97b7bcd40b88df7c4f09265f7`.
It binds accepted base-v2, composed dataset
`sha256:bf26c88358111fd70a1a30c8e9bd59be29080a3d69d93d3714223955545c22ac`,
the completed starting study, complete-run train ownership and the whole-run `ObjectiveSpec`.
An outcome-independent salted split assigns 84 fitting and 28 selection seeds before this audit.
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
Passing permits designing a frozen residual-training recipe with fresh complete-run confirmation;
it does not start training, promote a model or establish good gameplay. Insufficient labels call
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
