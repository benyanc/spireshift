# Shop navigation repair and bounded continuation

Historical preparation, 2026-10-19. This run is now complete.
See [the result, runtime repairs and next command](native-runtime-continuation.md).

Prepared for #143 / #35 / #146. Keep fixed native v0.111.0 / 41cef1ea,
Ironclad/A8, the existing public encoder, numerical model and full-run objective.

## Why the prior run stopped

The prior extension delivered 1,440 attempts: 1,437 terminal games and three failed
shop loops, with zero full wins. Each loop repeatedly opened/closed inventory after
inspection. Its current 256-game stage exceeded the two-failure allowance after
128 attempts. The historical exception's “128-game” wording came from the reused
runner; it was not a different configured failure limit.

The saved development checks were mixed. At 512/768/1024 scheduled training games,
player 2 averaged 8.59375/9.875/9.78125 floors and player 3 averaged
8.09375/8.4375/7.71875. No final holdout was opened. More unchanged training was
not established as the solution to this policy behavior.

## What changes at a shop

The new **public shop navigation contract** automatically opens inventory once on
arrival. Purchases, card removal, closing inventory, usable potions, discards and
leaving remain current public choices. After closing inventory, the learner chooses
among leaving and any current potion controls; redundant reopening is removed from
that effective menu. This is an explicit interface normalization, not a claim that
a learned score has solved navigation. It does not restrict strategic purchases or
require buying anything.

Foul Potion's merchant target remains available after closing inventory. A delivered
use permits another automatic inspection of the changed shop. Multiple consumables
remain available under the native rules. The usual native delivery/availability
checks still apply; uncertain actions stop the worker and are never resubmitted.

Only publicly observed inspection history and our own chosen merchant-potion action
control routing. No privileged state, fixed item rankings or hand-written health
rewards are introduced. Other menus, including skipping optional card rewards, keep
their current actions. The existing loop, whole-run CPU and decision caps stay in place.

Every raw snapshot and action remains in the unchanged native delivery journal.
Saved choices bind both raw and effective input IDs, the action-index mapping and
exact effective probabilities. Automatic inventory opens receive no PPO sample;
all remaining decisions use the same compact float64 storage, cross-fitted whole-run
credit and numerical optimizer. The behavior contract is recorded separately from
the preserved numerical model ID, so old behavior records cannot masquerade as new
on-policy experience. Final evaluations use this same repaired contract for both
starting and stopping players.

## Safe handling of the unfinished batch

The read-only audit verifies **221 committed units** and both latest complete fits,
absolute **round 35**, at **1,120 scheduled training games/player**. Their Adam
counters are **3,216 and 3,261**, with all first/second moments and weights retained.
These are the latest states, not the best-looking earlier checkpoints. Original
files, markers, logs, failed attempts and evaluation denominators stay unchanged.

The final uncommitted collection has eight delivered attempts: seven terminal and
one failed loop. All workers have closed/retired delivery evidence. That collection
remains diagnostic only. The whole unfitted round—32 attempts, including the three
earlier committed collections—is excluded from the new learner. We do not fabricate
a completion receipt, replay a failed seed, reset its worker, or feed old-policy
samples to the repaired policy.

The source schedule is not a claim of 1,120 clean games: one failed attempt was
excluded from player 2's earlier fitted batches. No partial failed episode supplied
ordinary PPO. The replacement excludes every old reserved seed, including unused
training/development/holdout reservations, as well as the separate short control.

## Finite replacement plan

Restore both round-35 model/Adam states exactly. The first fresh fit is **round 36**;
keep 32-game training batches, three passes, temperature 0.8, learning rates,
objective/bootstrap score, native worker and shared immutable inputs.

Allow at most **416 additional TRAIN attempts/player**, reaching the original
maximum of **1,536 scheduled games each**. Use eight-game collection chunks.
Development evaluates 32 separate seeds/player at 1120/1248/1376/1536. Pool wins
first, then floor, against the best previous result under the repaired contract.
Stop both after two consecutive checks without improvement once 256 new attempts
per player finish, or at the horizon. Thus an early plateau can stop at 1376.
Keep the current stopping states; do not select an earlier checkpoint or one player.

Only after sealing that stop decision open a separate 64-seed/player holdout,
comparing the imported round-35 starters with their stopped players under the same
repaired navigation. No development or holdout game enters fitting. The holdout
does not influence duration. This measures further learning under the repair; it
is not a controlled estimate of the repair's benefit versus the historical raw policy.

Maximum extent is **1,344 attempts / 199 units**: 832 TRAIN + 256 development +
256 paired holdout attempts, on 1,024 distinct seeds. Every failure remains counted.
The unchanged two-failure limit spans a player's full training stage (128/128/160
attempts), development panel or holdout/version panel. Missing evidence, uncertain
shutdown or an exceeded allowance stops without automatic replay.

The objective is still full-run victory subject to the whole-run CPU budget.
Floor/act progress is an explicit auxiliary bootstrap target. No automatic promotion,
value/calibration/search readiness, adaptive controller or further experiment follows.

## Verification and owner execution

Tests cover the loop, current purchase/removal/potion/leave controls, merchant potion
reinspection, exact behavior probabilities, exclusion of automatic navigation and
old/evaluation/partial data, nonzero-Adam numerical continuation, fresh partitions,
current-state stopping, uncertain-unit preservation and bounded restart behavior.
The saved-state check exits all three historical loop states without replaying games.
The separate live control uses 12 fresh attempts and two continued fits at round 36;
it passes all 12 attempts with zero failures and seven automatic shop openings. Adam
advances 3216→3225 / 3261→3267, with 15 updates and no repeated fit across two clean
launches. Resource time totals 287.45 seconds, peak RAM 764.25 MB, retained output
56.71 MB, and zero app copies. All 1,770 repository tests pass. The control
tests integration, not playing strength. Its updated weights never
replace the imported round-35 starters. Measured results are recorded in
[evidence](evidence/native-shop-continuation-v1.json).

The new workspace is recipe-owned:
`artifacts/native-shop-learning/sts2-v0.111.0-a8-continuation-v1/`.
Reuse the existing frozen game/runtime/SDK/support cache, with isolated workers and
**zero app copies**. The new workspace has 4 GB RAM / 4 GB generated-output limits.
The prior experiment and immutable shared inputs are outside that output count.
Clean 15-minute sessions continue within the same finite plan; a failed/capped
session stops. There is a three-hour invocation cap. Expect roughly **1–2 hours**
at the horizon from saved collection/fit timings, including verification overhead;
a plateau may end it earlier. The owner launches and monitors this long task.

Close any STS2 game, then run this **one command**:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/continue-native-a8-shop-v1.sh
```

The same command resumes a clean pause, preserving completed games/fits and Adam
state; a completed rerun verifies saved results without new attempts. Do not resume
the old stopped launcher. Full repository checks precede the local commit; no push
or GitHub Actions is needed. GA, other difficulties and adaptive thinking stay deferred.
