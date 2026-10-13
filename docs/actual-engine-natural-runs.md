# Natural Ironclad/A8 runs

The bounded finish line is [the environment contract](actual-engine-a8-finish-line.md).
This stage exercises the interface with a simple player; it is not model training or a strength
benchmark. Keep the frozen v0.111.0 / `41cef1ea` archive and `native_benchmark_full_v1` profile.

## Run this one command next

From the SpireShift repository:

```bash
bash scripts/check-natural-a8-run-v1.sh
```

Close any running STS2 game first. Expect approximately **5–10 minutes** based on the short
54-action shipped prefix and complete native runs. One game has a **15-minute process cap**;
the whole command has a **16-minute elapsed cap**, **1,800 CPU seconds**, **8 GB memory** and
**4 GB tracked storage**. Storage includes the existing shared app/pool and external profile
area, including pre-existing retained files there; it is not a 4 GB allowance for new app copies.

The command checks pinned inputs first, then starts one natural standard Ironclad/A8 run via
the normal menus. It imports no saved run, injects no gameplay fixture and uses no learned
checkpoint. It reuses the fixed serial app, gives the attempt a fresh private profile, shows
numeric progress every 25 actions and records every advertised choice/delivery. An ordinary
loss is a valid environment completion and remains a loss.

The first unsupported state, uncertain delivery, repeated public state, decision/compute/time
cap or integrity failure stops the attempt. All records remain preserved. A partial/failed
saved result is displayed and audited on repeat invocation; it is not automatically retried.
Interrupted attempts without a sealed summary stay blocked for inspection. No training,
promotion, next experiment or bulk-learning admission follows. Share the printed summaries.

The recipe controls the output/resource paths and binds 14 local helper dependencies, the
exact Host build, public starting reference, profile policy, objective and finite limits.
Saved observations/action receipts are checked after the run without opening another game.

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
