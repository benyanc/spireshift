# Fresh paired combat-policy comparison

[Issue #131](https://github.com/benyanc/spireshift/issues/131) is complete: the owner played all
64 attempts on October 8, 2026 (Toronto time). The eligible combat update from
[issue #132](https://github.com/benyanc/spireshift/issues/132) showed **no playing benefit** in
this development comparison. Accepted base-v2 stays in place; base-v10 is not promoted.

## Completed owner result

| Result | Candidate base-v10 | Reference base-v2 |
| --- | ---: | ---: |
| Complete terminal runs / original seeds | 32 / 32 | 32 / 32 |
| Terminal full-run victories | 0 | 0 |
| First-act boss reaches / clears | 0 / 0 | 0 / 0 |
| Mean maximum floor (auxiliary) | 6.625 | 6.65625 |
| Failed / truncated / CPU-exhausted runs | 0 / 0 / 0 | 0 / 0 / 0 |
| Run CPU seconds, all 32 runs | 17.029370 | 15.648463 |

One paired seed improves its maximum floor, two regress and 29 tie; the paired mean difference
is **-0.03125**. Action trace digests change on 29/32 seeds, but those traces include decisions
on different paths and do not locate the first aligned choice difference. Neither arm uses the
no-op fallback or hits a cycle/decision limit. No unsupported combat failure occurs.

Comparison report:
`sha256:3ae9c8644e653321f81d7ee3c28cc1bc9724a5225c238932d3daa31db1e7c850`.
Completed resources:
`sha256:9e50a55d6116b2160b66039137fe79e075af5971ee76070850bb2ff68656141f`,
**38.193 wall / 35.495 CPU seconds**, 162,955,264 bytes peak resident memory and 566,590 bytes
output, exit zero and no cap hit. Counters reconcile to **64 attempts, zero simulations and
5,457 transitions**. Strict saved-report, case and resource validation passed without replaying
games. These all-zero wins do not prove equivalence or either model's competence; the uncertainty
intervals remain broad. No terminal-positive labels, model promotion or readiness follows.

The sole next owner task is the [bounded combat replay diagnosis](combat-confirmation-diagnosis.md)
in [issue #133](https://github.com/benyanc/spireshift/issues/133). It inspects the same cohort,
which is now development evidence and must never be called fresh again. No extra training,
seed search or comparison rerun is needed before that diagnosis.

## Saved comparison and original execution protocol

The completed comparison used **64 game attempts: the same 32 reserved seeds with each of two
frozen models**, one worker and progress after every saved attempt. It stopped after the
comparison. The job caps were **30 minutes wall time, 10,000 CPU seconds, 8 GB memory and
1 GB output**; these were safeguards, not an estimate.

Results go to
`artifacts/evaluations/sts2-v0.107.1-base-v10-fresh-train-v1/production-policy-evaluation.json`,
with an immutable `confirmation-plan.json` and one JSON case per seed/model.
Resource reports use numbered
`artifacts/resources/combat-policy-base-v10-confirmation-v1-attempt-*.json` paths.
The completed owner summary and resources have been reviewed.

An interrupted job preserves completed cases. Running the same script again validates those
cases and executes only missing ones. Saved failed cases remain failed; they are never replayed
to seek a better outcome. A completed rerun verifies/displays saved evidence and initializes no
game. Changed plans, models, identities, cases or summary arithmetic cause a clear stop.
Partial work counters are saved after each completed case; work inside a forcibly interrupted
unsaved case is not recoverable from these counters and must not be represented as measured zero.

## Frozen inputs

Plan: `configs/combat-confirmation/sts2-v0.107.1-base-v10-fresh-train-v1.json`,
`sha256:faa09afa7ee9f08b0ea329e53b3a5a6d4c27d2167edd88353920b32769425752`.

- Candidate base-v10 checkpoint:
  `sha256:79aa82b8e1109fd968875ff2e025e2320461e3eb5027d5fa414d64afaf382705`.
- Candidate training report:
  `sha256:5a70198d8bb9dd1100d7d78cfe55eb8e7f4e2c839efa430b882958ff03f2e56b`.
- Reference base-v2 checkpoint:
  `sha256:b0b727319ecd5544df519d703c190a01d08b0aa37f8098a3bc8bcbcfd33a0571`.
- Reference training report:
  `sha256:246f9a1ae30ee77f52ea22d3eb70a98828ba2f31d06191cf4a80ea64b2b9a434`.

The plan also binds the completed owner training/resource IDs, original recipe-v3 settings,
split, admitted patch `sts2-v0.107.1-59260271`, objective and milestone rules.
It uses the **32 train seeds at split offsets 504–535**, reserved before training beyond the
inspected prefix and disjoint from all seven prior inventories. The preflight checks compact
saved inventories and model/report eligibility; it does not reopen teacher case files or fit
weights. This is fresh development confirmation, not a sealed final test. After inspection,
this cohort cannot be described as fresh again.

Both policies use public state, policy-only inference and the same pre-existing no-op action
guard and cycle detector. Other unsupported public combat layouts cause counted failures.
There is no unreported parent-policy fallback, seed replacement or new tuned safeguard.

## Whole-run computation

Both models have the versioned objective's **128 CPU seconds per run**, plus a **4,096-decision
safety limit**. CPU charging starts immediately after reset returns and ends before cleanup;
it includes public-state handling, legal-action queries, inference, native simulator transitions,
liveness checks and result bookkeeping. Factory/reset and cleanup CPU/wall times are reported
separately. Model/backend loading and other job overhead remain in the outer resource report.
Thus initialization overhead is visible and does not silently consume a policy's decision budget.

Runs are serial so the process CPU clock cannot charge another concurrent game to the current
one. CPU limits are checked around policy and transition calls. This is a cooperative limit:
one blocking native or inference call may overshoot it. The measured overshoot is retained,
and an outcome that arrives after the cap is truncated and cannot count as a budgeted win.
The outer resource wrapper enforces the wall/CPU job caps if a call hangs.

This is a comparison of two policy-only models under the same budget. It does not measure
adaptive low/medium/high search or establish that either model uses its full allowance.

## Read the result

Terminal **full-game wins** are primary. All **32 seeds per model** stay in the denominator,
including runtime/unsupported failures, CPU exhaustion, cycles and decision-limit truncations.
The paired summary also counts a failed arm as a non-victory, rather than dropping its seed.
Completed-pair floor differences are separately labeled and do not replace this denominator.

Auxiliary results include first-act boss reaches/clears, public floor by act, changed action
trace digests, guard use, actual attempts/transitions, run CPU/wall time and inference latency.
The summary's latency statistic is the maximum of per-case 95th-percentile completed inference
times, not the overall 95th percentile. Trace differences can include diverged states and do
not measure aligned counterfactual choices.
First-act milestone rules explicitly support both Overgrowth and Underdocks and recognize Hive
as the next act; floor 17 alone is a boss reach, not an act clear.

Individual win-rate intervals use the approximate Wilson score method. Paired win differences
use a conservative Hoeffding bound for values in [-1, 1], assuming independently sampled seeds.
These intervals describe sampling uncertainty for this small development cohort; they are not
a final-test generalization claim. They remain broad when no wins occur.

The saved decision always requires owner-result review. Improved floors, all-zero wins or
better saved-teacher loss cannot establish full-run competence, terminal-value learning or
foundation readiness. A negative or inconclusive result calls for an explicit diagnosis and
bounded next plan, not automatic extra seeds or tuning against this inspected cohort.
The foundation and adaptive-controller gates remain closed.
