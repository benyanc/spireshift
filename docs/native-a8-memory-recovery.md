# Bounded collection and recovery of the capped A8 pool

Implemented and verified 2026-10-17 under #35 / #146. The owner has completed saved-data
gradient analysis: 114.20 seconds, 3.917 GB peak RAM, no cap. See the
[analysis result and next work](native-a8-recovered-gradient-result.md). No replay or
player training followed. The implementation and pre-analysis measurements below remain
historical evidence; the original portable recovery summary is unchanged.

## What failed and what changed

The v2 owner collection hit its 4 GB memory cap after 399.52 seconds, at 4,054,319,104
resident bytes. It preserved 254 sealed terminal episodes. Its collector kept every
episode's decisions in RAM, and its closing auditor loaded all three worker journals
into lists. One worker closed after 128 games; the other retained its active marker.
Neither closing audit nor the complete original collection/analysis was produced.

The new version retains sealed episode paths and compact outcome metadata. It releases
each live decision trace before checking its sealed copy. Verification consumes the
private, public-observation and receipt journals in order, retaining the current episode
and a bounded record window. Memory no longer grows with the accumulated histories.
The original numerical learner, encoder, game, native worker, SDK and old pinned
collector/auditor remain available unchanged for historical reproduction.

Portable tests exercise a 256-episode collector: two lanes retain at most two episode
objects total, pass only paths to the auditor, and stop an uncertain lane without retry.
The streaming auditor matches the old clean/retired fixture results, rejects hidden
input, changed targets, uncertain delivery, broken successors, fixture mutations,
missing/truncated records and an expired deadline. A separate retention check verifies
that completed episode objects are released. These are synthetic memory controls;
the entire 256-game native collection was not replayed to measure its new peak RAM.

## Safe recovery and explicit attempt accounting

The original source bytes, configuration, checkpoint, cap receipt, case seals and traces
are bound. Both recorded owner/native process IDs of the interrupted worker are absent,
and no matching controller is present. No process was signalled, profile reused, active
marker cleared, exit receipt fabricated, or source file changed.

The ordered delivery chain and original public/native ending agree for all **254 saved
games**: 126 from the interrupted worker's completed prefix and 128 from the clean worker.
Each advertised input, chosen action, delivered target, successor and native ending is
checked. Saved sampling/model ownership and original CPU/score boundaries also verify.
At recovery, full-pool numeric behavior verification was still pending. The completed
analysis now reconstructs all saved likelihoods; its separate exact gradient reference
covers four games / 549 decisions. The earlier mixed-origin check below covers four games.

The native logs prove seed **700253 was started but did not finish**; it is not retried.
Seed **700255 was never started**. Two short fresh workers play 700255 and one explicitly
registered new TRAIN seed, **700257**. Both finish normally and pass streaming delivery
audits; frozen/shared inputs and the account profile remain unchanged in those checks.

| Accounting | Count |
| --- | ---: |
| Original planned seeds | 256 |
| Original finished games recovered | 254 |
| Original interrupted attempt, still counted | 1 |
| Original unstarted seed, now completed | 1 |
| Explicit additional independent seed, now completed | 1 |
| Clean games in the diagnostic union | 256 |
| Actual diagnostic-pool attempts including the interruption | 257 |
| Separate control game starts, excluded from the union | 4 |

The four controls repeat the previously declared control seeds; they are not four new
independent outcomes or part of the 257 diagnostic attempts. Their costs remain separate.
The interrupted worker and old failed collection stay preserved. No whole-pool copying
is needed: the union references old/new sealed cases in place.

**Recovery is diagnostic evidence only.** It does not retroactively grant the interrupted
worker a clean shutdown, prove an uncaptured original before/after profile check, complete
the original clean-collection protocol, or admit these records to ordinary PPO training.
The salvaged set is explicitly different from the originally planned clean 256-game pool.
Its gradient geometry is descriptive; it supplies no gameplay improvement or population
confidence guarantee. Repeated partitions remain correlated finite-pool descriptions.

## Measured short checks

All durations below include the resource wrapper; no cap was reached.

| Step | Wall time | Peak resident memory | Result |
| --- | ---: | ---: | --- |
| Saved recovery | 25.15 s | 116.33 MB | 254 delivery/ending chains verified; zero replays |
| New collector control | 38.25 s | 598.57 MB | 4 clean games / 360 decisions; no player updates |
| Two completion games | 32.38 s | 617.46 MB | 2 clean games / 186 decisions; no retries |
| Union preparation | 1.94 s | 84.36 MB | 256 unique clean diagnostic games; interruption counted |
| Mixed-origin numerical check | 2.94 s | 221.40 MB | 4 games / 422 decisions; exact gradient reference passes |

The collector control's maximum actor-gradient error is 4.02e-17. The mixed-origin check
uses two recovered cases and both additions, verifying their different source-config
bindings before differentiation; maximum error is 7.25e-17. It does not cover all 256.
All phases perform zero optimizer steps, model promotions and app copies. The recovery
directory retains about 5.69 MB, mainly the four controls and two additions. Original
preserved source storage, 211.91 MB at the cap, is outside that new resource root and is
not represented as newly generated output or deleted to make the measurement smaller.

## Completed owner command

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/analyze-native-a8-recovered-pool-v1.sh
```

Allow up to **10 minutes**, one numerical thread, **8 GB memory**, 2 GB output cap.
The saved Jacobians alone need approximately 3.54 GB; bounded input verification does
not eliminate the explicitly budgeted derivative arrays. This full-size analysis has
been completed by the owner. It uses existing files and never starts games or updates a
player, so closing Steam is unnecessary. No automatic next experiment follows.

The wrapper reads its workspace and limits from the pinned recipe. Finished results
are displayed without recomputation. Resource attempts use distinct receipts. The
old `check-native-a8-batch-sizes-v1.sh` command is historical and stops on its preserved
unfinished folder; it must not be used to clear/restart the capped source.

## Evidence and follow-up

Recipe: `configs/native-gradient/sts2-v0.111.0-a8-stream-recovery-v1.json`.
Separate seed extension: `manifests/splits/sts2-v0.111.0-native-a8-gradient-recovery-v1.json`.
Private workspace: `artifacts/native-gradient/sts2-v0.111.0-a8-stream-recovery-v1`.
Reports: `recovery.json`, `control.json`, `completion.json`, `union.json`, and
`union-binding-control.json`; completed analysis adds `gradient-report.json`.
Portable summary: `docs/evidence/native-a8-memory-recovery-v1.json`.

The [completed assessment](native-a8-recovered-gradient-result.md) finds no clear direction
agreement even at 128 games/group. A native learning comparison still needs a justified game/update
budget and fresh reserved evaluation. The toy HP-dependent learning gap remains open.
No foundation/adaptive readiness, improved player, or new training admission follows
from this memory repair. Future large collections must use the bounded streaming path.
