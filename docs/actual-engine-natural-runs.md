# Natural Ironclad/A8 runs

The bounded finish line is [the environment contract](actual-engine-a8-finish-line.md).
This stage exercises the interface with a simple player; it is not model training or a strength
benchmark. Keep the frozen v0.111.0 / `41cef1ea` archive and `native_benchmark_full_v1` profile.

## Run this one command next

From the SpireShift repository:

```bash
bash scripts/check-reward-decline-a8-run-v1.sh
```

Close any running STS2 game first. This runs **only the previously blocked second seed**.
Allow approximately **5–10 minutes**; a blocking screen or ordinary death can end it earlier.
The game has a **15-minute process cap**; the whole command has a **16-minute elapsed cap**,
**1,800 CPU seconds**, **8 GB memory** and **4 GB tracked storage**. Tracked storage includes
pre-existing shared app/pool and external profile files, not just newly written files.

The command checks its pinned case first, then starts a natural standard Ironclad/A8 run through
normal menus. It imports no saved run, injects no gameplay fixture and uses no learned checkpoint.
It reuses the fixed app, creates a fresh private profile, shows numeric progress every 25 actions
and retains every advertised choice/delivery. An ordinary loss is a valid environment completion
and remains a loss. The successful first seed is not replayed.

Every persistent unsupported observation retains all missing fields and reached floor/act/HP.
Only existing verified current native exits/declines can recover a diagnostic case. Unknown
modals, stale/truncated menus and mandatory choices without an exit get no invented fallback.
Limits remain 16 recoveries, 64 distinct missing-field issues and 128 distinct observations.
Blocking unsupported states, uncertain delivery, repeated public states and caps stop the game.
Recovered/incomplete cases cannot count as clean passes or ordinary learning examples.

The final summary includes **case_outcomes** and **failures_by_kind**, alongside the original
failure/omission denominators. It distinguishes a completed loss/victory from repeated states,
unsupported screens, delivery errors and caps, including the original error text. Zero missing
fields can coexist with a failed game. `discovery_complete` means the finite collection was
finished and audited; it does not mean its game completed successfully.

Saved results are audited on rerun, never automatically retried. Interrupted output stays blocked
for inspection. No training, promotion, next experiment or bulk-learning admission follows.
Share the printed summaries. The recipe pins the outputs/resources, complete helper dependency
inventory, Host, starting reference, profile, objective and finite limits.

## Latest verified results, 2026-10-14

The owner two-seed batch takes **357.933 resource seconds**. One game reaches a genuine shipped
loss on **floor 6 after 144 gameplay actions**. The second stops alive on floor 2 after 42 actions:
opening its card reward, choosing Skip and reopening the same still-available offer repeatedly.
Both cases and app resets audit correctly with zero app copies; all failed attempts remain counted.
This is the first verified naturally played shipped ending, not a win or training admission.

The repaired initializer remembers a delivered Skip for that particular public reward handle and
room, then prefers other legal rewards/exits. Its identity is used only to associate that offer
with its earlier preview, never as a preference tie-breaker. Same-text offers remain separate;
a custom learned scorer can still take, decline or revisit any advertised choice.

A fresh short check declines the card, claims gold and continues to **floor 5 in 95 actions**,
with zero unsupported issues, before its 165-second client cap (**177.461 resource seconds**).
Saved auditing independently reconstructs the navigation, decisions and progress and verifies reset.
The new policy also matches all **137 non-tutorial actions** in the successful first seed's saved
trace; tutorial controls and Host stay unchanged. Keep that success and run only the affected seed.
This comparison opens no games and proves equality only on the already observed trace.

Repository checks pass **1,256 tests** and **53 current Node controls**. The new one-case recipe
passes read-only preflight and has not run. The old two-case wrapper now audits its saved batch;
use only the command above for the new stage.
[Evidence](evidence/actual-engine-v0.111.0-reward-decline-v1.json) preserves every original outcome,
the repair, short cap, trace comparison, reporting revision and owner-stage limits.

## Four repairs and short checks, 2026-10-13

The original owner attempt made 73 gameplay actions in 130.735 resource seconds, then stopped alive
at a floor-5 shop with 44/80 HP and zero current controls. Logs point to the previously unsupported
map-selection tutorial. Its historical floor-4 counter and failed report are unchanged.

The separately built Host v12 adds the native map tutorial. The first short check of the new runner
records 35 gameplay actions / 82.171 resource seconds before encountering a distinct combat-reward
tutorial, alive at floor 2. Its two missing fields are both retained; saved auditing independently
reconstructs reached progress and verifies the app reset. This is not a death or clean pass.

Host v13 additionally binds the standard combat-reward, can-play-card, cannot-play-card and merchant
tutorials, using their audited native controls. The merchant/end-turn highlight choices remain
separate from ordinary confirmation; unknown or unavailable controls remain unsupported. The
diagnostic player confirms guidance before choosing from the refreshed gameplay menu. Two fresh
builds reproduce; the original game DLL and older Host artifacts stay unchanged.

Native and shipped card Skip/leave actions now share a diagnostic semantic contract. They have no
automatic take-card/spend-gold preference, accept an external scorer over every legal choice, and
break ties using public facts instead of generated action IDs/menu order. Costs and named amounts
remain distinct; mandatory menus receive no invented Skip. This initializer is not trained deck
quality, and the two interfaces' full policy trajectories are not claimed identical.

Two short native runs using the shared policy reach genuine candidate deaths (86 and 75 decisions,
floors 6 and 5) and pass saved audits with zero app copies.

After the owner closed Steam's game, Host v13 handled both the combat-reward and map tutorials
in a fresh shipped run. That check reached floor 5 but exposed a separate initializer loop:
opening and closing the same shop repeatedly. Its 99 actions and incomplete result stay preserved.
The initializer now remembers a delivered inventory inspection using only public act/floor history,
then prefers the existing shop exit when inventory closes. This is a navigation preference for the
simple player; an external learned scorer can still select buying, leaving or reopening.

The new short check performs **101 gameplay actions**, including opening, closing and leaving the
shop, and reaches **floor 6** with **zero unsupported issues**. It stops alive at the short
165-second client cap; resource wall time is **177.328 seconds**. Saved auditing reproduces the
navigation memory, choices and reached progress, and verifies reset with **zero new app copies**.
At that stage repository checks and 44 current Node controls passed; the subsequent owner batch
and its remaining repair are recorded above.
[Short-check evidence](evidence/actual-engine-v0.111.0-shop-navigation-v1.json) preserves the two
new attempts. Broader shipped ending coverage, later acts, other remaining controls, worker
isolation and neural integration remain pending.

## What already passes

- Eight natural headless candidate endings: **1,115 decisions**, **15 decision families**,
  **28.813 seconds total measured case wall time**, zero runtime/unsupported/delivery failures.
  All eight end in ordinary deaths in Act 1; the highest floor is 17. Shared frozen inputs need
  no app copies. Case wall time includes integrity checks and is not parallel throughput.
- Two normal fresh shipped starts match their native starting states, with no Continue/imported
  run. Their processes take 19.440 and 18.838 seconds and reuse app inode 347602255.
- The new Host's short natural prefix records five startup actions, **54 gameplay actions**,
  two combats and five tutorial actions, reaching floor 3 before its 105-second client cap.
  The last reward appears just before the deadline; this is a capped prefix, not a completed run.
  Saved reconstruction verifies these actions and the fixed-app reset.
- Native event text, card modifiers, generated-choice permissions, upgrade-preview descriptions
  and missing math API bindings have targeted repairs. The original game DLL stays byte-identical.
  Reproduced builds, 45 numerical checks, portable negative controls and raw private failures
  remain preserved. These checks do not prove exhaustive mechanics fidelity.

The game canonicalizes seed letters `I`/`O` to `1`/`0`. New cross-host recipes use explicit
canonical seeds; earlier literal-seed observations retain their historical identities.

[Evidence](evidence/actual-engine-v0.111.0-natural-run-foundation-v1.json) records identities,
counts, timings and scope. Broader shipped ending coverage, later-act/victory semantics, outstanding
input/large-selection gaps, parallel isolation and a useful neural learner remain unqualified.
After the bounded environment gate, #146 connects existing neural/PPO machinery and runs a short
learning control. The owner launches the subsequent finite learning pilot.
