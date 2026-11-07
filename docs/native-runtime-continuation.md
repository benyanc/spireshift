Historical preparation: the owner has now completed this continuation. Its final 960-attempt
result and the next bounded comparison are recorded in [rest exploration](native-rest-exploration.md).

# Native runtime repairs, combat losses and the next A8 step

Prepared 2026-10-19 for #143 / #35 / #146. Keep native v0.111.0 / 41cef1ea,
Ironclad/A8, the public encoder, full-run objective and both numerical players.

## Completed result

The shop continuation finished all **1,344 attempts / 199 committed units**:
1,342 terminal games and two failed TRAIN games, both excluded from fitting.
There were zero full victories and no app copies. The final 128 paired fresh
seeds compared round-35 starters with round-48 players under the same shop routing:
mean floor **9.484375 → 10.3671875**, difference **0.8828125**, seed-bootstrap 95%
interval **[0.2734375, 1.5078125]**. Player differences were +1.03125 / +0.734375.
This is modest auxiliary progress; the final holdout had no Act 1 clears.

The 830 clean TRAIN games included five Act 1 clears. Six were reported across
all TRAIN outcomes before excluding the failed Crystal Sphere game. Do not count
its partial progress as a clean training success. The old result, all failed
markers, source checkpoints and unused seed reservations remain unchanged.

## Repair scope

**Crystal Sphere:** the missing `Vector2I.One` exposed a previously unsupported
minigame. The new host supplies the exact math accessor and a presentation bridge
for the native grid. Both Small and Big Divination and all 121 coordinates remain
selectable. The interface reports visible cells; a covered cell never exposes its
item, footprint, contents or native RNG. It uses the existing event-choice public
schema, with 242 tool/coordinate choices. The native model still owns gold payment,
Debt, grid generation, divination counts, item reveals and reward synchronization.
The replacement screen waits for actual completion; it never skips the minigame
or automatically chooses good cells. Native reward/card selection and optional
skip controls remain available afterward.

**Rolling Boulder:** the native async method references Godot `Connect` and
`CallDeferred` even though its original TestMode branch applies damage without
VFX. The added exact ABI signatures make that branch executable. The stub bodies
fail if presentation signal calls actually execute; they do not supply fake damage.
The original power still damages all hittable enemies and increases its amount.

A separately pinned cumulative v35 patch changes exactly three source files:
Godot Core, Godot Math and RunSimulator. Two fresh repaired builds match. The
original game assembly, frozen archive, runtime, SDK, localization and public JS
projection remain unchanged. Old mechanics evidence belongs to its old host;
reviewed source-delta checks and new native effect evidence compose the admission.
The numerical game/environment ID is retained for exact model/Adam restoration;
the changed host and newly exposed screen are explicit recipe and worker identities.
This does not claim exhaustive mechanics or shipped-UI cross-host parity.

Six isolated privileged checks pass: both payment options × both tools, plus base
and upgraded Boulder over two successive turn starts. Gold payment remains native
and seed-dependent; Payment Plan adds Debt. The larger grid fixtures collect native
gold/cards. Boulder amounts are **5→10→15** and **10→15→20**, with corresponding
native enemy HP loss. These fixtures are not ordinary learning games. All checks
preserve shared inputs/account and create zero app copies.

## What the saved losses show

The read-only audit opens **830 clean TRAIN games** and no development/holdout
histories. It retains at most one raw game at a time. Failed games stay counted
in the 832-attempt source denominator and supply no action-quality labels.

- 78,225 combat decisions; 17,823 end turns. Only **51** end turns still had a
  playable card (**0.29%**), five had a usable potion, and seven low-health end
  turns had a block card available. These are opportunities, not proven errors.
- The last observed terminal fights were 368 ordinary fights, **352 elites** and
  **107 bosses**; three losses were not attributed to a current combat.
- There were 112 observed boss entries, at 74.8% average maximum health. The
  terminal boss cohort entered at 73.7% average health. Starting every hard fight
  nearly dead is not a sufficient explanation for weak boss play.
- **Rest 747 times versus Smith twice**; Smith was available on all 747 Rest
  choices. There were 37 Rest choices at full health and 146 at ≥75% health.
  Average recorded probability of the chosen Rest was 98.1%; 507 exceeded 99%.
  Specific relics can change a rest's value, so this does not label each Rest wrong.
- Card rewards were taken 3,272 times and skipped 377 times. Skip is supported and
  used. Terminal boss decks averaged 19.48 cards. Nobody had a nonempty potion
  belt at their last observed terminal combat decision.

The next learning investigation should focus on **combat ordering/defense, deck
strength and upgrade exploration**, rather than forcing all energy to be spent,
removing card skip, adding fixed HP bonuses, or claiming more volume is sufficient.
The audit is descriptive; it does not simulate alternative choices or prove their
causal value. Qualifying a native combat teacher or a measured exploration change
remains a separate follow-up if this finite continuation fails to improve.

## Bounded continuation

Import both **latest round-48** states at **1,536 scheduled training slots/player**.
Preserve every weight, Adam counter and first/second moment exactly. Source Adam
counters are **4,470 / 4,692**. The first main fit is absolute **round 49**; never
use a fresh initializer, an earlier best checkpoint, or the integration control's
updated weights.

Keep 32-game batches, three passes, temperature 0.8, existing learning rates,
whole-game cross-fitted credit, objective and explicitly auxiliary bootstrap score.
Every strategic public action family stays learnable. The shop navigation contract
and compact streaming collector are unchanged; the new qualified host is explicit.

Allow **256 fresh TRAIN attempts/player**, reaching round 56 / 1,792 scheduled
slots each. Check separate 32-seed/player development panels at 1536/1664/1792.
Pool wins first, then floor, and retain both current stopping states. The minimum
256-new-game plateau threshold coincides with this short horizon; development
checks cannot extend it. After sealing the stop, open a separate 64-seed/player
paired holdout comparing imported and stopped players under the same repaired host.

Maximum **960 attempts**: 512 TRAIN + 192 development + 256 paired holdout, on
704 distinct seeds. All earlier consumed **and reserved** seeds and the new short
control are excluded. No evaluation game supplies PPO. Two failures/player/stage
remain allowed; uncertain workers are retired and proven stopped, failed episodes
are excluded, and missing evidence or an exceeded allowance stops without replay.

The separate control passes **12/12 attempts with zero failures** across two clean
launches. Both round-49 fits are reused exactly; Adam advances **4470→4476 /
4692→4698** with 12 updates total. It preserves original states and creates no app
copies. Resource time totals 327.81 seconds, peak RAM 732.95 MB and retained output
61.12 MB. Its tiny batches test integration, not strength. The next main run is
still unstarted.

## Owner launch

Close STS2, then run this one command:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/continue-native-a8-runtime-v1.sh
```

Expected **60–90 minutes**, based on the last 1,344-attempt run taking 108.5
minutes including verification. Two-hour invocation cap; clean 15-minute sessions,
two workers, 4 GB RAM and 4 GB generated-output caps. Frozen game/runtime/SDK/support
code are shared; no app copies. The script prints round averages, best training
progress, wins, failures and optimizer counters. The same command resumes clean
pauses or verifies completed results; failed/capped sessions do not automatically
retry. The recipe owns all output paths. Codex does not launch/monitor this long run.

Full wins remain the primary goal. No automatic checkpoint promotion, readiness
pass, adaptive controller, GA or further experiment follows. Evidence is recorded
in [the result and repair receipt](evidence/native-runtime-continuation-v1.json).
