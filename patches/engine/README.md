# Private exact-game CLI repair

The patch modifies the MIT-licensed `wuhao21/sts2-cli` host, not the proprietary game.
Keep its [MIT notice](LICENSE). It applies on top of STS2 Headless's pinned
`sts2-cli-d11aa88-v01110.patch`, against upstream revision
`d11aa883b582dd68bd39b331f3370746b30d447e`.

The exact target is **v0.111.0 / 41cef1ea, macOS arm64**. The original and runtime
`sts2.dll` remain byte-identical. The locally compiled Godot stub and .NET 10 runtime
are distinct from the rendered game's Godot and bundled .NET 9 runtime.

The repair awaits the native rest choice and re-exports the synchronizer's remaining
options. It retains Smith cancellation and manual confirmation, including a single
eligible card. Native option enablement and card selection bounds stay authoritative.
Only explicit Proceed opens the map; the subsequent native map vote owns room exit.
The host exposes Proceed after a successful choice or when no options remain,
matching the inspected native UI path. Failed or canceled choices cannot create it.

Rest `choose_option` now requires `room_ref`, `option_ref`, and the current
`option_index`. Rest `leave_room` requires `room_ref` and available Proceed.
The local canonical projection below consumes this repaired contract. The unmodified
upstream projection does not. Other card selectors' cancellation/confirmation preferences
remain unqualified; unknown fields produce unavailable actions, not invented defaults.

Drift risk remains high: TestMode and Godot stubs run outside the rendered SceneTree,
and the Proceed flag replaces UI presentation state. Continue-save rest resumption
has not been qualified. The pending shipped-host differential case must start with
matching visible HP/deck/relics, run Miniature Tent in both orders and cancel Smith,
then compare remaining options, enablement, HP/upgrades, Proceed and native map travel
after every action. Record the first divergence; the managed fixtures do not substitute
for that comparison.

`set_player.obtain_relics` is **privileged fixture setup**, using the native obtain
command to bind relic ownership and hooks. It is not a policy action or a source of
training examples. Existing legacy list-injection fixtures remain unqualified.

[Build configuration](../../configs/engine-qualification/sts2-v0.111.0-cli-build-rest-v2.json)
pins the upstream manifest and patch, this delta, complete source diff, compiler,
reference pack, binary SHA/MVID and runtime dependencies. Two fresh baseline and two
fresh repaired builds must agree. Local clones restore the real upstream origin URL,
because SourceLink/PDB metadata contributes to binary identity. The old upstream
binary mismatch remains preserved; this local result does not reproduce its binary.

[Rest probe configuration](../../configs/engine-qualification/sts2-v0.111.0-cli-rest-probe-v1.json)
binds the completed build and a capped, isolated native regression panel. Named
Ironclad/A8 scenarios cover ordinary rest, Miniature Tent in both orders, cancellation,
Girya, disabled Smith, single-card confirmation, reset during a pending choice,
explicit early leave and stale/invalid inputs. Generated transcripts and profiles
stay under ignored private artifacts. Shared saves, Steam files and archives are
write-protected. These are managed native regressions, **not shipped cross-host parity**.

Rollback means selecting the original build-only configuration and its original
pins, while keeping all failed and repaired results. Never reuse the repaired build's
evidence for that host, a changed game, another runtime, or a training admission.

Portable checks need no game files:

```bash
node --test scripts/engine-cli-local-build.test.mjs
uv run pytest tests/unit/test_engine_cli_probe.py
```

## Canonical rest projection hook

`sts2-headless-player-projection-v1.patch` targets MIT STS2 Headless revision
`4961b52a587777277816bc4407108f6f4274f801` and its exact
`src/managed-player-environment.mjs`. It adds an optional public-surface projector,
explicit ascension forwarding and a trusted host observation entry point for named fixture setup.
The latter is not a policy command and does not clear the request ledger or revive a tainted
session. The existing launcher still enforces upstream artifact pins; this package constructs a
session only after separately verifying the repaired local CLI. It does not bypass that launcher.

The [projection configuration](../../configs/engine-qualification/sts2-v0.111.0-cli-rest-projection-v1.json)
binds the source/hook, resulting source bytes, local surface/probe helpers and all 620 installed
SDK/dependency files. `engine-player-projection.mjs` stages the patch in a fresh private checkout;
`engine-rest-surface.mjs` projects native choices into canonical actions with private operands.
It distinguishes cancellation from empty confirmation and never clamps an impossible minimum
to the number of available cards. Unknown selection preferences fail closed. Existing projections
of other decision families are retained but receive no new mechanic qualification from this package.

The bounded native panel validates canonical SDK snapshots/receipts, explicit A8, refreshed
remaining choices, single-card confirmation/cancel, stale-snapshot rejection and exactly-once
delivery. Its full transcripts stay private. Shipped-host differential comparisons remain pending.
Rollback selects the earlier raw rest probe and unmodified Headless projection; preserve each
report's distinct source and adapter identities and never mix them in a resumed experiment.

```bash
node --test scripts/engine-rest-surface.test.mjs
```
