# Restarting the bounded native context comparison

## Completed result, 2026-10-18

The comparison is complete: all 46 units and 288 new games are saved, with no
failed native games and zero app copies. The two successful work sessions took
861.35 seconds in total (14 minutes 21 seconds); a refused launch while the Steam
game was open adds 2.30 seconds. Peak resident memory was 1.07 GB and the new
workspace retained 280.21 MB. The original capped attempt remains preserved.

Across the two numerical replicates, each method has 32 final development games:

| Method | Initial mean floor | Final mean floor | Mean change | Final wins |
| --- | ---: | ---: | ---: | ---: |
| Original public encoding | 7.1250 | 6.9375 | −0.1875 | 0/32 |
| Public situation-by-candidate features | 7.1250 | 7.1250 | 0.0000 | 0/32 |

The crossed method is ahead of the original by 0.1875 floor in each replicate,
but has no aggregate improvement over its own initializer. Replicate 0 improves
slightly for both methods; replicate 1 worsens for both. These small exploratory
results do not establish better native play or a reliable encoding advantage.
They do not rule out benefits from more data: each player trained on only 128
whole games. They also do not justify declaring the learning workflow effective.

A read-only assessment verifies all 46 unit receipts and 5,567 source seals and
reconstructs the final comparison exactly. It plays no games and performs no
optimizer updates. The fresh players perform 318 original / 309 crossed updates;
each of their four fits ends at the configured epoch limit. Gradients are nonzero
and behavior changes, so an entirely disconnected/frozen optimizer is not supported
by these records. Small observed policy changes alone do not prove undertraining
or that increasing the learning rate will improve gameplay.

No checkpoint is promoted and no readiness/adaptive gate passes. The next planned
work under #143/#35/#146 is a bounded optimizer-efficiency study: reconstruct
existing TRAIN-only batches and check probability/credit movement, then compare
predeclared step sizes or updates per batch at a fixed game budget. Keep numerical
checks separate from evidence of better full-run play. Freeze any next native
recipe before evaluating on newly reserved development seeds; do not choose
hyperparameters using this completed final panel. No further owner run is pending
for the completed comparison.

[Completed comparison evidence](evidence/native-context-comparison-v2.json)
binds the result and resource reports. The command below now verifies and displays
the completed result; it cannot extend its finite training plan.

## Preserved restart procedure

The owner chose a fresh matched pair on 2026-10-18. The previous one-hour attempt
stopped before its fourth player finished. Preserve its files and use the new entry
point. The old launcher deliberately refuses to resume that workspace.

## One owner command

Close any running STS2 game, then run:

```bash
bash scripts/continue-native-a8-context-v2.sh
```

The first launch runs the complete repository checks, expected around 5–6 minutes
with a ten-minute cap. Only a successful result against unchanged repository files
allows training. Later launches reuse that exact-file verification receipt. Failed
check attempts stay saved; a new check attempt has its own resource report.

Each launch then performs at most 15 minutes of comparison work, using two native
workers and a 4 GB RAM / 4 GB new-workspace cap. It pauses between committed units.
After `paused_between_committed_chunks`, run the **same command** again. The fixed
46-unit plan prevents extending training through repeated launches. Completion says
`chunked_comparison_complete`; further launches only verify and show the result.
Each launch has a separate resource report. Actual total time is still to be measured;
the old 25–40 minute estimate proved too optimistic for the original runner.

Eight games make one collection unit. Four such units still form a 32-game training
round. Fitting saves both weights and complete Adam state in one sealed checkpoint.
Initializers, fits and final evaluations are separately committed. Sealed units are
checked and skipped; starting a later session does not recollect their games or
repeat their optimizer updates. Each whole-round summary shows wins, average and
best floor, acts and failures.

An operating-system kill **inside** a collection unit still needs inspection. The
runner preserves an uncommitted unit and stops; it does not clear worker markers,
reuse uncertain profiles or replay that unit's seeds. Prefer the planned clean pause
to interrupting a launch. A second writer is refused, with the locks held through
worker shutdown. A completed unit with missing, changed or additional files is also
refused. A stopped unit is not silently labeled complete.

## What is preserved and reused

The original attempt remains a 640-game plan. Its capped resource report has a zero
exit code, but `status: capped`; that does not mean the experiment completed.
There are 520 sealed terminal game headers: 496 in closed audited panels and 24 in
two interrupted workers. Another 120 planned slots lack sealed headers; the number
of unsealed attempts is unknown. The interrupted 24 remain diagnostic only.

| Saved player | Initial mean floor | Final mean floor | Wins |
| --- | ---: | ---: | ---: |
| Original encoding, numerical seed 0 | 6.4375 | 6.5625 | 0/16 |
| Crossed encoding, numerical seed 0 | 6.4375 | 6.7500 | 0/16 |
| Original encoding, numerical seed 1 | 7.8125 | 7.2500 | 0/16 |

These are exploratory development results; they do not establish stronger play.

The completed seed-0 pair stays in the primary comparison. The extra old seed-1
baseline remains diagnostic evidence. Both fresh seed-1 players use the same 128
new TRAIN seeds, disjoint from every legacy comparison seed. Their verified saved
starting development evaluations are reused: identical numerical initializer,
model IDs, public inputs, menus, temperature, reserved seeds and sampling draws.
All saved starting-evaluation behavior probabilities reconstruct with the cache.

This leaves **288 new games**: 128 training plus 16 final development games per
method. The primary comparison eventually contains two matched numerical pairs,
640 game records including reused history. The old attempt's denominator and
interrupted work remain separately reported. The two numerical replicates use
different training seed sets; comparisons are paired within each replicate. With
only two replicates and 16 development seeds each, this is exploratory evidence.
There is no checkpoint selection using final evaluation, automatic promotion,
readiness pass or permission for adaptive search.

## What changed in execution

`CachedContextModel` caches the content-derived ID of an immutable model. New
weights construct a fresh object and cache. Serialization, IDs, action scores,
probabilities, draws, score function and game rules remain identical. No observations,
actions or model predictions are cached. Historical pinned code is unchanged.

A finite saved-decision profile measured 6.76× original and 5.10× crossed speedups
for repeated inference plus saved-probability verification. This is **not** a
whole-game speed claim. Model arithmetic, native simulation, worker startup,
credit fitting and evidence checks still take time.

Chunk boundaries do not change the 32-game batch or random seeds. Before fitting,
paths are restored to the historical two-lane whole-round order, preserving
deterministic minibatch shuffling. Cross-fitting still excludes each game's own
outcome when estimating its baseline. Failures stay in the planned denominator;
at most two failed games are allowed across an entire logical round/evaluation,
not two per chunk. Failed episodes never supply PPO targets.

The frozen actual game, runtime, SDK and support cache stay shared. Each worker has
its own mutable profile. No game apps were created. Old archives and the historical
463 MB attempt are outside the new-workspace storage cap; they are referenced and
sealed, not copied. Full-check resource tracking counts its retained validation
reports, not all temporary test/build files elsewhere on disk.

## Verification and evidence

The eight-game native control passed in three short launches, pausing after units
3 and 6. It completed eight games and 12 optimizer updates with no failures or
shared-input changes, zero app copies, 63.04 total resource-tracked seconds and
697.30 MB peak resident memory. Reopening the completed control performed zero
new games or updates and returned the same saved report. This qualifies restart
plumbing, not gameplay quality or whole-experiment throughput.

Unit checks cover identity/probability equality, concurrent cache reads, new-weight
invalidation, exact Adam continuation, changed/missing/unexpected evidence, exclusive
writers, interrupted-unit preservation, seed ownership, whole-round ordering,
evaluation denominators and the outer repository-check gate. The complete repository
check remains owner-run because its prior test suite alone took 298.59 seconds.
Do not commit or push before it passes for the current files.

- [Evidence summary](evidence/native-context-restart-v2.json)
- Read-only legacy import: `artifacts/native-context/restart-v2-checks/legacy-import.json`
- Decision profile: `artifacts/native-context/restart-v2-checks/profile.json`
- Short control: `artifacts/native-context/sts2-v0.111.0-a8-context-chunks-control-v2/report.json`
- Long recipe: `configs/native-controls/action-context-chunks-comparison-v2.json`
- Owner workspace: `artifacts/native-context/sts2-v0.111.0-a8-context-fresh-pair-v2`

After the comparison, assess both paired final-minus-initial changes and terminal
wins, actual optimizer work and failures. If the representation remains flat, move
to controlled optimizer-efficiency and action-credit/teacher experiments under
#143/#35/#146 before another unchanged bulk rollout. Fixed Ironclad/A8, genuine
full-run wins and foundation-before-adaptive-search remain the goals.
