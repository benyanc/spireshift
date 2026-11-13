# Bounded continuation of both standard A8 players

Prepared 2026-10-18 for #143 / #35 / #146.

**Stopped 2026-10-19 after three shop-navigation loops. Preserve this historical
recipe; use the [audited shop repair and continuation](native-shop-continuation.md)
for the next owner run.**

Original preparation follows. The fresh-seed confirmation improved
mean floor from 7.2890625 to 8.859375 in both trained players, with zero full wins.
This finite extension tests how far the same learner continues to improve.
It preserves the confirmed numerical method rather than introducing another treatment.

## What continues

Restore the two final standard players after 512 training games each, numerical
initializers **2 and 3**, including every model parameter and the complete Adam
counter and first/second moment vectors. Their starting Adam counters are **1,353**
and **1,413**. Their original files stay unchanged. Small private model/optimizer
snapshots go into the new workspace; no game app is copied.

The first continued fit is **absolute round 17**, followed by rounds 18–48 if the
full horizon is reached. Keep the original minibatch ordering, round shuffle seed,
compact float64 experience, cross-fitted credit, 32-game batches, three passes,
learning rates and temperature 0.8. All legal public decision types stay learnable.
Use the same native v0.111.0 / 41cef1ea Ironclad/A8 startup profile, mechanics
admission, public input encoding, objective/bootstrap score and whole-run budget.
No permanent baseline-proximity constraint or new hand-written reward is added.

## Finite extent and fresh seeds

Each player receives **at most 1,024 additional TRAIN games**, reaching at most
**1,536 total training games**. Collection stays in eight-game chunks; four chunks
form one 32-game training batch. The two players have disjoint training seeds.

The seed manifest separates three purposes before execution:

| Purpose | Distinct seeds per player | How used |
| --- | ---: | --- |
| Training | 1,024 | One current-behavior collection per seed; fitting only |
| Development | 32 | Frozen evaluation at 512/768/1024/1280/1536; stopping only |
| Final holdout | 64 | Compare the 512-game starting player to its stopping-point player |

At the full horizon: **2,048 training attempts + 320 development attempts + 256
final holdout attempts = 2,624 attempts maximum**. There are 2,240 distinct seeds;
repeated development checks and paired holdout games are not additional independent
seeds. The loader checks IDs and native seed strings against all 18 prior native
seed manifests and the separate continuation control. None of the consumed fresh
confirmation seeds enters training or these new evaluation panels.

Development and holdout episodes remain ineligible for PPO. Holdout games open
only after the sealed stopping decision; neither their results nor earlier
holdout panels influence how long to train. The short control's updated players
are never used as the main extension's starting states.

## Stop rule declared before execution

At each 256-new-game milestone, pool the two development panels, with **wins first,
then mean maximum floor** in lexicographic order. An improvement must exceed the
best previous pooled development pair, including the new 512-game starting check.
Count a failed evaluation attempt as zero wins / zero floor; retain its actual
reached progress and error separately in the raw summaries.

Stop **both** players after two consecutive checks without improvement, after at
least 512 additional games per player, or at the finite horizon. Thus the earliest
plateau stop is 1,024 total training games/player. Use the **current states at the
stopping point**, not the earlier best-looking checkpoint and not just the better
initializer. The best previous score is used only for stopping. This is a resource
rule based on noisy development data, not proof that learning has reached its limit.

After stopping, freeze the current states and run the separate paired holdout:
both 512-game starters versus their respective stopped players on 64 seeds each.
Report genuine wins, failures, paired floor changes and conditional seed-bootstrap
intervals using the existing fixed-player comparison. The old 512-game player is
the baseline here; the original untrained initializer is not the baseline.

The objective remains full-run victory under the whole-run compute budget. Floor
progress is explicitly auxiliary; another positive floor result with zero wins
cannot grant base/value/calibration/search readiness or adaptive thinking. No
checkpoint is automatically promoted and no further experiment follows completion.

## Evidence, resumption and resources

Reuse the qualified two-worker collector, streaming audit, support cache and native
game/runtime/SDK. Keep profiles and mutable ledgers separate. The original weights,
Adam states, past results and shared inputs are sealed and checked for changes.
Every collection, fit and stopping decision has its own exact predecessor receipt.
Clean restarts reuse completed work and full Adam state. Uncommitted/uncertain
units stop for inspection; no game or fit is replayed automatically.

Continue after verified worker retirement within the inherited failure allowance:
at most two failures per player's complete 256-game training stage, per 32-game
development panel, or per 64-game holdout/version panel. This allowance spans chunks.
Missing games, evidence corruption or unverified shutdown stop the run. Failed
episodes stay counted and never supply ordinary PPO samples.

The wrapper automatically continues clean 15-minute sessions inside the same
finite plan. Failed/capped sessions stop without automatic retries. The whole
invocation has a **four-hour cap**, with **4 GB RAM / 8 GB generated-output limits**.
Existing shared immutable inputs, source experiment and short control are outside
that new-workspace storage count and remain protected by hashes.

Expect roughly **2–3 hours** at the full horizon; a plateau may stop it earlier.
This estimate uses prior standard-arm receipts (median fit 24.09 seconds, median
eight-game collection 14.13 seconds), with margin for longer games and verification.
The owner launches and monitors this task under the five-minute execution boundary.
Close any running STS2 game, then run this **one command** from any directory:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/continue-native-a8-policy-v1.sh
```

The workspace is recipe-owned:
`artifacts/native-continuation/sts2-v0.111.0-a8-standard-continuation-v1/`.
The same command resumes a clean pause; once complete it verifies saved results
without additional games or updates. Each completed batch shows wins, average
floor, best result and the best sampled training game so far. Development checks
show both-player pooled progress and stopping patience separately.

## Short verification

Unit tests verify exact nonzero-Adam serialization/resumption parity at round 17,
fresh partitions, final holdout timing, current-state stopping, source immutability,
uncertain-unit preservation, and wrapper caps/resumption. The live control is
separately versioned: two training games and two development seeds per player,
development before/after one continued fit, **12 attempts / two fits** total.
Its two-game batches exercise integration; the unchanged standard 32-game trainer
and compact memory path already have prior qualification. It does not measure
strength or supply the main extension's weights or seeds.

The live control **passes all 12 attempts with zero failures**, two continued fits
at round 17 and 15 optimizer updates. The full counters advance 1,353→1,362 and
1,413→1,419; original states and shared inputs remain unchanged. Its resource time
is **140.10 seconds**, peak RAM **754.55 MB**, retained output **37.70 MB**, with
zero app copies. Its tiny development-panel changes are not a strength claim.
The main extension remains unstarted.

See [prepared evidence](evidence/native-policy-continuation-v1.json) for the measured
control result and exact identities. Full repository checks precede the local
commit. GA, other difficulties and adaptive-controller training remain deferred.
