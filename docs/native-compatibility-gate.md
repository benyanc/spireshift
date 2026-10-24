# Checkpoint compatibility with the shipped game

Update: the shared converter and current-checkpoint live adapter are now implemented.
The short actual-game delivery control passes, with original numeric weights/full
Adam preserved, while current Neow input exports still differ. The next owner
diagnostic and exact scope are in [the live-adapter guide](native-shared-live-checkpoint.md).
The saved-record result below remains preserved and does not grant compatibility.

Tracked in [#149](https://github.com/benyanc/spireshift/issues/149).

The shipped v0.111.0 game is the reference. Our fast training host uses its game
assembly through community/custom CLI, stub and connector code. Sharing an assembly
does not prove identical public inputs, legal choices or execution. Keep historical
v0.107.1 emulator results separate. This gate implements the first recurring check;
it does **not** claim the current checkpoints have passed live official-game play.

## Implemented saved-record check

`scripts/check-native-compatibility-v1.sh` reads existing records only. It:

- Verifies the exact frozen game, runtime, SDK, host build, worker/projection,
  public-input/encoder dependencies and complete checkpoint/Adam identity.
- Reconstructs four old official/CLI combat-effect sequences from two independent
  native seeds. Rechecks their scoped native effects, official action receipts,
  tutorials and shuffle evidence before comparing the 36 paired observations.
- Runs all six frozen teaching-test players through the actual current policy
  encoder and scoring path. Compares context, **every** offered action, encoded
  features and action probabilities. Menu order may differ if unique semantic
  actions can be aligned; missing actions cannot disappear from the comparison.
- Rejects stale, hidden, cross-session and incomplete supplied reads. A read
  advertised but not retained by the old capture is explicitly missing, never an
  invented empty pile. Reports limited structural difference witnesses.
- Reuses a saved receipt only for the same checkpoint, complete optimizer,
  implementation, input bank, environment and inference runtime. Changed inputs
  get a separate result directory; interrupted evidence remains untouched.

The command has a four-minute wall cap, 480 CPU seconds, 2 GB memory and 100 MB
generated-output limit. It creates no apps, launches no game, changes no model and
starts no follow-up. Repeated invocations preserve earlier resource reports.

```bash
bash scripts/check-native-compatibility-v1.sh
```

The diagnostic completed in **6.12 seconds**, using **174.44 MB peak RAM** and
retaining **0.52 MB**. It returned **BLOCKED**, which is a completed diagnosis,
not successful compatibility qualification. The same receipt was subsequently
reused without rerunning the comparison.

Verification passes: 18 focused Python tests, four explicit Node projection tests,
and the complete repository check (2,515 passed / six skipped, 553 typechecked
files, formatting/lint and C# protocol) in 151.42 seconds. The optional system-Node
test is skipped when Node is absent from PATH; its four cases were separately run
with the bundled runtime. All 443 protected frozen dependencies/full states retain
their original bytes, including the numerical weights and every Adam component.

## What the check found

1. **The environment label is stale.** Model manifest v9 names input/build v34;
   the latest experiment separately pins and verifies v35. This is an identity
   mismatch, not proof the actual game DLL changed or the experiment ran unpinned.
   Fix it with a new environment/import contract that verifies unchanged numerical
   weights and all Adam state; preserve v9 and every historical result.
2. **Old mechanics agreement does not establish policy-input agreement.** All
   four old scoped mechanics reconstructions pass. For each current checkpoint,
   however, zero of 36 paired observations pass the stricter input contract:
   20 complete menus match, zero contexts or encoded feature sets match, and only
   six distributions match. The layouts contain different context/option metadata;
   16 menus differ, including potion-discard controls. All 24 combat observations
   advertise pile reads that were not retained on either side of these old captures.
   These are **historical host records**, not a diagnosis of current host-v35 rules
   or a causal explanation for weak learning. Large differences when scoring these
   incomplete, differently shaped inputs cannot be called an estimate of live loss.
3. **Live delivery is untested by this audit.** None of the four historical build
   IDs matches v35. The official runner has not delivered this current checkpoint's
   decisions under this gate. The audit therefore cannot grant that scope even if
   all recorded inputs eventually match.

The six checkpoints reuse the same 36 states; they are not 216 independent game
states or six independent training replications. This privileged fixture bank
covers event, map and combat decisions. It does not qualify every rest, shop,
reward, nested selection, act transition or ending.

## Command guard and remaining integration

`python -m spireshift.native_compatibility require RECIPE` requires environment,
recorded-input and current-live-delivery scopes. `run RECIPE --command ...` checks
the same scopes **before** starting its explicit child command, without a shell.
The current saved-only receipt cannot certify live delivery, so both commands
intentionally refuse a training/promotion command. The real blocked-command
control exited 2 before its harmless sentinel child could run.

Historical experiment scripts and source pins are unchanged. They have not been
retroactively wrapped or declared compatible. New experiment entry points must
integrate the guard after the live adapter/receipt is qualified. Do not interpret
the presence of this standalone command as enforcement on every old entry point.

## Ordered next work

1. Define a complete shared public decision contract and a separately versioned
   official-game checkpoint adapter. Normalize transport IDs and presentation-only
   steps, preserve entity/amount/zone ownership and all legal choices, and obtain
   every advertised public read. Test the actual current checkpoint format and
   model labels. Never repair agreement by dropping meaningful fields or actions.
2. Bind a new environment to verified v35 execution with an explicit numeric/full
   Adam preservation receipt. Do not edit old models, manifests or frozen recipes.
3. Run a bounded **current host versus shipped app policy canary**: same exact game
   and matched decision states, checkpoint choices, action delivery and successor
   public effects. Include consequential cases from each supported decision family,
   optional Skip, repeated rest/shop/selection menus and encountered regressions.
   UI-only confirmations/tutorials may add steps; gameplay decisions must align.
   Cache only for that exact qualified tuple. An ordinary game loss is not a
   compatibility failure; an unsupported state or uncertain delivery is.
4. Require cheap recorded checks for every new checkpoint; repeat live canaries
   when connector, engine, worker, projection/encoder or execution semantics change
   and at declared learning milestones. New batches and resumptions validate the
   matching receipt before collecting or fitting. Keep historical inspected runs
   available for reproduction without silently admitting them to a new lineage.
5. Before promotion or substantial scaling, compare original and trained frozen
   players on fresh **official-game** seeds under matched behavior/compute. Report
   wins first, floors and failures separately; split failure sources from normal
   losses. Manage drift and affected-data lineage explicitly. Parity alone never
   grants playing-strength/readiness or adaptive-controller approval.

This is representative recurring coverage, not exhaustive proof of all mechanics.
Maintain the same private shared app and isolated profiles; no per-game app copies.
The earlier timing comparisons include startup/UI overhead, so they do not prove
an inherent engine-speed ratio. Benchmark faster faithful official execution before
considering an official-only training migration. No benchmark or game follows this
diagnosis automatically, and no long owner command is needed at this stage.

See [ADR 0006](decisions/0006-recurring-official-game-compatibility.md), the
[ordered backlog](backlog.md) and [portable result](evidence/native-compatibility-gate-v1.json).
