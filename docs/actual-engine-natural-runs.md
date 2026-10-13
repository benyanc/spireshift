# Natural Ironclad/A8 runs

The bounded finish line is [the environment contract](actual-engine-a8-finish-line.md).
This stage exercises the interface with a simple player; it is not model training or a strength
benchmark. Keep the frozen v0.111.0 / `41cef1ea` archive and `native_benchmark_full_v1` profile.

## Run this one command next

From the SpireShift repository:

```bash
bash scripts/discover-natural-a8-runs-v1.sh
```

Close any running STS2 game first. This runs **two independent seeds, one at a time**. Allow
approximately **5–10 minutes per game / 10–20 minutes total**; a blocking screen or ordinary
death can end a case earlier. Each game has a **15-minute process cap**;
the whole command has a **32-minute elapsed cap**, **3,600 CPU seconds**, **8 GB memory** and
**4 GB tracked storage**. Storage includes the existing shared app/pool and external profile
area, including pre-existing retained files there; it is not a 4 GB allowance for new app copies.

The command checks both pinned cases first, then starts natural standard Ironclad/A8 runs via
the normal menus. It imports no saved run, injects no gameplay fixture and uses no learned
checkpoint. It reuses the fixed serial app, gives the attempt a fresh private profile, shows
numeric progress every 25 actions and records every advertised choice/delivery. An ordinary
loss is a valid environment completion and remains a loss.

Every persistent unsupported observation records all its missing fields and reached floor/act/HP.
In discovery mode, a complete current native menu may provide a verified operand-free Skip,
leave, close, cancel or Proceed control even if descriptions are incomplete. Only those existing
controls can recover the case. Unknown modals, unavailable/truncated/stale menus and mandatory
choices without an exit get no invented fallback. At most 16 recoveries, 64 distinct issue records
and 128 distinct unsupported observations are retained per case. Identity, information-boundary,
delivery and compute checks remain mandatory.

A blocking unsupported state, uncertain delivery, repeated public state or decision/compute/time
cap stops that game. After verified app reset and saved auditing, the next planned seed continues.
Integrity failures stop the batch. Reports deduplicate common omissions across seeds and retain
every failed/unattempted denominator. Recovered games remain diagnostic and cannot count as clean
environment passes or training examples. “Discovery complete” means all planned cases were
collected/audited; it does not mean they completed the game. All evidence stays saved.

A saved result is displayed and audited on repeat invocation; it is not automatically retried.
Interrupted attempts without a sealed summary stay blocked for inspection. No training,
promotion, next experiment or bulk-learning admission follows. Share the printed summaries.

The recipe controls the output/resource paths and binds all transitive local helper dependencies, the
exact Host build, public starting reference, profile policy, objective and finite limits.
Saved observations/action receipts are checked after the run without opening another game.

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
Repository checks and 44 current Node controls pass. Both longer owner cases pass read-only
preflight; the long batch has not run.
[Short-check evidence](evidence/actual-engine-v0.111.0-shop-navigation-v1.json) preserves the two
new attempts. Full shipped endings, later acts, other remaining controls, worker isolation and
neural integration remain pending. Close any running Steam game before the command above.

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
counts, timings and scope. Shipped full-run endings, later-act/victory semantics, outstanding
input/large-selection gaps, parallel isolation and a useful neural learner remain unqualified.
After the bounded environment gate, #146 connects existing neural/PPO machinery and runs a short
learning control. The owner launches the subsequent finite learning pilot.
