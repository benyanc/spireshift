# Fixed working apps and bounded storage

The frozen master stays unchanged. New serial qualification uses one fixed working app at
`artifacts/engine-working-apps/sts2-v0.111.0-41cef1ea-macos-arm64-v1/worker-00/game`.
It is copied once with independent APFS clones when supported, then reused across attempts.
There are no hard links to the master.

Every run keeps its own small profile, checkpoint, raw snapshots, logs and result directory.
A lock prevents overlap. The launcher verifies the complete base file inventory before use,
installs the pinned Host and writes the current profile override. After verified child exit it
checks the run's complete app inventory, removes only owned mods/override files, restores the
executable's original permissions and checks the original frozen inventory again. Begin/reset
receipts record ownership, policy/game identity, whether an app was created, and the app inode.
Raw evidence and receipts can be audited without retaining a separate app beside every result.

A failed gameplay comparison can still restore a physically intact, naturally exited app; its
failure reports remain. Interrupted setup, an abnormal exit or unknown file mutation keeps the
single worker blocked for inspection. Rerunning never automatically replaces it or clears its
marker. Deliberate repair/retirement is follow-up work under #147, not a reason to accumulate new
copies. Parallel reuse/isolation remains under #146; the current policy is serial only.

The managed pool has a global maximum of two apps / 5,000,000,000 logical bytes. Creating a new
app requires 3.5 GB free. Owner resource accounting includes both case results and the pool.
The inventory preview lists managed apps and every other `game` directory found beneath private
artifacts, including partially generated copies; it deletes nothing. Logical sizes can overstate
recoverable space when APFS clones share blocks.

Two short real checks on different A8 seeds/pack choices reuse the same app path/inode with
separate profiles, one total app copy, successful resets and passing saved raw audits. This does
not qualify every mechanic, parallel workers, full-run speed or a useful player. The startup
API also passes a separate short native boot using the same working app. Its historical diagnostic
errors remain preserved; this proves boot/profile isolation and reset, not a clean general runtime.

One startup attempt exposed a bookkeeping error after successful reset: the launcher tried to
hash an already removed override file. That failure remains immutable. The hash is now captured
before reset, a focused regression test passes and a separately recorded retry passes.

## Completed owner repeat panel

The owner completed `scripts/compare-bundle-actions-v3.sh`: all **eight Scroll Boxes comparisons
pass**, across two independent A8 seeds, both packs, each twice. The raw saved audit passes and an
independent recheck reproduces it without launching games. All cases use the same app path/inode
and eight distinct profiles, create **zero additional app copies**, and have verified reset
receipts. The master and current idle worker still match the original frozen file inventory.

Resource wall time was **319.079 seconds (5 minutes 19 seconds)**, CPU 193.116 seconds and peak
memory 850,165,760 bytes. The batch retains about **27 MB of results and 0.9 MB of profiles**,
with no per-case `game` directories. The 2.43 GB final tracked storage includes the one pre-existing
2.41 GB working app. These are logical sizes; APFS clones can share physical blocks.

No rerun is needed. Invoking the completed helper again displays and audits saved results without
game replay. Earlier v1/v2 scripts retain their historical behavior. No full run or training
followed. [Completed panel evidence](evidence/actual-engine-v0.111.0-bundle-panel-v3.json) records
the results. Serial reuse is confirmed for this scope; deliberate blocked-worker repair/retirement
remains under #147 and parallel reuse/throughput under #146. The next mechanics work under #145
is full Calling Bell/Cauldron pickup and reward choices.

## Launcher integration

The new bundle template binds `sts2-v0.111.0-working-app-serial-v1.json` by content ID.
Menu/bootstrap commands accept `--working-app-config` explicitly. Their legacy recipes remain
unchanged for historical reproduction. Managed-engine projections already use shared frozen data
and do not require a full app copy per simulation.

For a read-only storage preview, use the `engine inventory-working-apps` command with the frozen
qualification config. Preserve the master, current worker app, build/toolchain dependencies and
all evidence. Nothing outside the active lease's own added mods/override files is deleted by reuse.

Public metadata and limits: [reuse evidence](evidence/actual-engine-v0.111.0-working-app-reuse-v1.json).
