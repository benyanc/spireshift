# Fresh neural combat gameplay comparison

[Issue #134](https://github.com/benyanc/spireshift/issues/134) now has a trained, eligible
base-v11 neural combat candidate. This comparison is implemented and its saved-artifact checks
pass. Gameplay has not run. The owner launches and monitors the next stage.

## Run this one next command

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/confirm-neural-combat-policy-v1.sh
```

It plays **64 simulated full-run attempts: 32 reserved seeds with neural base-v11, and the same
32 seeds with accepted base-v2**. Runs are serial, with progress after each saved attempt. It
uses the frozen simulator, without launching the Steam game UI. It stops after the comparison;
there is no fitting, search, collection, automatic extra cohort or follow-up experiment.

The outer caps are **30 minutes wall time, 10,000 CPU seconds, 8 GB memory and 1 GB output**.
These are limits, not a measured runtime estimate. Both models receive the original **128 CPU
seconds per run** and 4,096-decision safety limit. Numerical-library thread pools are limited
to one. Share the final summary and resource report before the next experiment.

## Frozen models and seed ownership

Plan: `configs/combat-confirmation/sts2-v0.107.1-base-v11-neural-fresh-train-v1.json`,
`sha256:0b7364a5e85ff44a4bced69e798a5e2e5036d519aa0ee70b47ce56f1f245d69a`.

- Candidate base-v11 model:
  `sha256:8f7d86ab9b5bb066e6e010e8977a71da3925f197e907f7a9bf2c4495e4c09b5d`.
- Candidate training report:
  `sha256:38eda1dbb76055d133f46e938c97401b48f348b411789aaf19eed4e25e710959`.
- Completed owner training resources:
  `sha256:ae52e58c01ffa86e81f01b5d3e51a58f42cc55b1c321d58e187f6a6fb8701767`.
- Reference base-v2 model:
  `sha256:b0b727319ecd5544df519d703c190a01d08b0aa37f8098a3bc8bcbcfd33a0571`.
- Reference training report:
  `sha256:246f9a1ae30ee77f52ea22d3eb70a98828ba2f31d06191cf4a80ea64b2b9a434`.

The plan binds the [neural training recipe](neural-combat-policy.md), both checkpoints/reports,
the completed resource report, admitted patch/ruleset, original objective, milestone rules
and action guards. The comparison format and execution protocol are reused unchanged; the
training recipe and model schema explicitly identify the neural architecture.

Use the **32 train development seeds at split offsets 536–567**, reserved before neural fitting.
They are separate from fitting/selection, original validation, all seven earlier inventories
and the inspected base-v10 comparison at offsets 504–535. The neural preflight verifies its
diagnostic report identity and inspected-seed inventory as well as the new reservation. The
linear recipe embedded in neural training retains its old reservation as historical provenance;
that cohort cannot replace the neural reservation. Final test seeds remain sealed.

The implementation check loaded only saved model/report/recipe, resource and compact seed
metadata in under one second. Predictions, fitting, source-case audits and backend loading
were explicitly blocked. This establishes that the next command's saved inputs bind correctly,
not that the candidate plays well. Synthetic tests exercise neural inference in the paired
loop, invalid source/cohort rejection and resuming without new predictions.

## Results, interruptions and failures

Results go to
`artifacts/evaluations/sts2-v0.107.1-base-v11-neural-fresh-train-v1/production-policy-evaluation.json`,
with an immutable `confirmation-plan.json` and one case per seed/model. Resource reports use
numbered `artifacts/resources/neural-combat-base-v11-confirmation-v1-attempt-*.json` paths.

Rerun the same command after an interruption to validate saved cases and execute only missing
ones. Saved failures remain failures; they are never replayed to obtain a better outcome.
Completed reruns verify/display the saved comparison without loading the backend or predicting
new actions. Changed plans, source identities, saved cases or summary arithmetic stop execution.
Previous attempt reports remain preserved and each resumed attempt gets a new resource path.

Work counters record actual new attempts and completed transitions after every saved case.
They start at zero before preflight, and cached cases are not counted as new work. Work inside
an unsaved forcibly interrupted case has incomplete counters; its measured CPU/wall use is
still charged and must not be described as a measured zero.

All **32 seeds per model** remain in the denominator, including exceptions, unsupported combat
menus, CPU exhaustion, cycles and decision-limit truncations. Existing public/legal-action,
no-op and cycle guards are unchanged. There is no unreported parent-policy fallback for an
unsupported neural input. Both arms consume only public observations and the supplied legal menu.

## Interpretation and compute accounting

Full-run victories are the primary result, with paired uncertainty. Auxiliary diagnostics
include first-act boss reaches/clears, floor progress, failures, truncated/unsupported runs,
guard use, action-trace changes, transitions, run CPU/wall time and inference latency. A changed
trace can include decisions on diverged paths; it does not prove a particular action caused
the run difference. Existing milestone rules support both Overgrowth and Underdocks and
recognize Hive as an act clear; reaching floor 17 alone is only a boss reach.

The CPU clock starts after reset returns and includes public-state handling, legal-action
queries, inference, simulator transitions, liveness checks and bookkeeping. Initialization and
cleanup are recorded separately; loading and job overhead remain in the outer resource report.
Runs are serial so another concurrent run cannot consume an arm's process CPU budget.
Cooperative checks occur around inference and transitions; an outcome arriving after the
allowance is truncated and cannot count as a budgeted win. The outer wrapper caps a blocking job.

Win-rate intervals use approximate Wilson scores; the paired win difference uses a conservative
Hoeffding bound under an independent-seed assumption. The sample is small and development-owned.
All-zero wins do not prove equivalence or competence. After inspection, these seeds are used
development evidence and cannot be called fresh again.

There is no automatic model promotion, readiness pass or learned thinking-budget controller.
Review the owner's result before another learning round. Better floors are useful intermediate
evidence but do not replace terminal full-run victory or establish a calibrated victory-value
head. Accepted base-v2 remains in place pending actual separate-run evidence.
