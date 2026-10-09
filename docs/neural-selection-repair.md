# Neural discard-choice repair

## Completed owner comparison, 2026-10-08

The corrected comparison is complete. Both players finish 32/32 attempts as terminal losses,
with zero failures/truncations, zero wins or first-boss reaches/Act 1 clears, and mean maximum
floor 6.84375. There are 27 changed traces without demonstrated playing gain. This confirms the
menu compatibility correction on inspected seeds; it is not a fresh/final strength benchmark.
The original failed comparison remains preserved.

Comparison ID: `sha256:2bc12a35ee21e5ac285424cab8e19bcb236bb650c88d51aaa9d91e7ea8843ce6`.
Resources: `sha256:c8e246e7455f5df0913bc55d6585b694643aba26eabcf5186004c76f9947786d`.

The next work is the unified full-run policy under #137, after the implemented score under #136.
There is no new owner-run task here. See [the backlog](backlog.md). The command and pending-stage
notes below describe the preserved historical protocol; they are not a request to rerun it.

## Original implementation and owner-run protocol

[Issue #134](https://github.com/benyanc/spireshift/issues/134) now repairs the two card-choice
failures in the [original neural comparison](neural-combat-confirmation.md). This is a public
input compatibility correction, with no fitting or model promotion. The next sustained job is
one owner-run comparison of the correction against accepted base-v2.

## Run this one next command

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/confirm-neural-selection-repair-v2.sh
```

It plays **64 simulated attempts: the same 32 inspected train seeds with the repaired neural
policy and with base-v2**, one worker. Each arm keeps the original 128 CPU seconds per run,
4,096-decision limit and public action/cycle guards. Outer caps are **30 minutes wall time,
10,000 CPU seconds, 8 GB memory and 1 GB output**; these are limits, not an ETA. The earlier
comparison took about 35 seconds, but the corrected policy can continue beyond its old failures.
No training, teacher search, extra cohort or automatic follow-up starts.

The plan is `configs/combat-confirmation/sts2-v0.107.1-base-v11-neural-selection-repair-v2.json`,
ID `sha256:f17e662ee7a84e61fa9727393e39e51db88967a5f62f843d42af9a07c22dc99d`.
Results go to
`artifacts/evaluations/sts2-v0.107.1-base-v11-neural-selection-repair-v2/production-policy-evaluation.json`.
Resource attempts use `artifacts/resources/neural-combat-base-v11-selection-repair-v2-attempt-*.json`.
Interrupted jobs resume only missing cases. Saved failures remain failures. Completed reruns
verify/display the saved result without games. Neither original results nor resource attempts
are overwritten.

## What failed and what changed

A short public-input reproduction identified both menus, checking the original error, action
counts and progress without reading hidden game state into the policy:

| Seed | Public menu | Supplied legal actions |
| --- | --- | --- |
| 686 | Choose a discarded card to put on top of the draw pile (kind 1) | One visible card, one action |
| 689 | Choose a discarded card to return to hand (kind 13) | Nine visible cards, nine choices and a legal decline |

These offered cards need not be in hand. Layout v4 binds the public selection slots to the
offered discard cards, preserves the original action order/handles and recognizes decline only
when it is in the supplied kind-13 legal menu. Historical selector actions can carry an enemy
target decoration; the pinned engine consumes only the selection index. The decoder does not
turn that decoration into a target-dependent card choice. Missing/extra choices, invisible
cards and other unsupported selection kinds still fail explicitly.

The runtime wrapper uses **all of base-v11's original learned weights and printed card catalog**.
It changes only the explicitly versioned binding layout. The old checkpoint and layouts v1–v3
keep their original behavior. Previously supported feature coordinates and full model predictions
are preserved; non-combat, run-value, tactical-risk and floor heads are unchanged. The new
runtime policy has a separate identity despite retaining the source model ID. It does not use a
parent-policy fallback. Card-selection quality itself has not been trained or established by
this correction.

The new plan binds both source checkpoints/reports, the original comparison and resources, every
failure capture and three frozen engine source hashes defining menu semantics. It preserves the
original cohort, objective and budgets. The claim is explicitly
`paired_inspected_train_neural_selection_compatibility`: these seeds have already been inspected
and cannot be called fresh or final-test evidence. Final test seeds remain sealed.

Future occurrences of the original `not a supported combat action space` error are counted as
`unsupported_public_combat`, correcting the phrase matcher. Original cases labelled
`runtime_error` remain immutable and readable; their zero unsupported counter remains a known
historical accounting limitation. Every failed attempt stays in the denominator.

## Short checks already completed

The user authorized short jobs. Both reproduction stages and a two-run repair smoke used
15-second wall/CPU caps. The saved corrective preflight also passed with predictions, fitting
and backend creation explicitly blocked.

- Captures: two attempted reproductions, 168 transitions, zero simulations/optimizer steps.
  Collection `sha256:738f68c3cee678c81231352c6a96f50dba6e54728a36da8f94df656bd7278364`.
- Repair smoke: all **168 supported-prefix predictions** match exactly. The repaired policy
  completes both previously failing seeds as ordinary terminal losses, at floors 7 and 9.
  Two attempts, 246 transitions, zero simulations/optimizer steps; 4.558 wall / 4.298 CPU seconds,
  no cap. Smoke `sha256:a992c3e542ed870a43a0063a3c04342c7b9552d4d98cac14ce28ca11d8dbae86`,
  resources `sha256:a32184303e2327dbb40163ee8c0d2b0a6368d9139a29026f72392d573de68da8`.

The first capture invocation saved seed 686 and then failed while updating its metrics file.
Its original resource record reports zero counters, which is incomplete: it actually attempted
one game and completed 74 transitions. A separate reconciliation records that work; the resumed
capture played only seed 689, one new attempt and 94 transitions. Both resource attempts and
their measured CPU/wall use are retained. The first attempted game is never described as zero
work or silently discarded.

Private evidence and diagnostic code used for the checks are under
`artifacts/planning/neural-selection-repair-2026-10-08/` and
`artifacts/diagnostics/sts2-v0.107.1-base-v11-selection-failures-v1/`.
The tracked `scripts/capture-neural-selection-failures-v1.py` checks completed captures without
replay, preserves partial cases and counts only new attempts. New captures require a resource
wrapper with explicit limits. Reconstructing evidence requires reviewing its new identities;
it must not silently replace the plan's pinned captures. Raw public traces and game source
remain outside Git.

These checks establish that the two crashes are repaired. They are **not** the full paired
comparison or evidence of a stronger player. Base-v2 stays accepted, base-v11 stays unpromoted,
terminal-positive training labels remain zero and foundation/adaptive-controller readiness
remain false. Review the owner's next comparison before freezing a better or broader lesson
recipe for the next neural round.
