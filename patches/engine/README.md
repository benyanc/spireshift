# Private exact-game CLI repair

The patch modifies the MIT-licensed `wuhao21/sts2-cli` host, not the proprietary game.
Keep its [MIT notice](LICENSE). It applies on top of STS2 Headless's pinned
`sts2-cli-d11aa88-v01110.patch`, against upstream revision
`d11aa883b582dd68bd39b331f3370746b30d447e`.

The exact target is **v0.111.0 / 41cef1ea, macOS arm64**. The original and runtime
`sts2.dll` remain byte-identical. The locally compiled Godot stub is distinct from the
rendered game's Godot. Historical rest-v1 probes ran on .NET 10; the selection/shop
package below requires the separately pinned, game-matching .NET 9.0.7 runtime.

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

## Current shop and selection adapter

`sts2-cli-v0.111.0-selection-shop-v3.patch` replaces the earlier rest delta on the same
base patch. Do not apply both local deltas. The preserved v2 patch lacks the upgrade
selection observation boundary and is not the current complete rest interface.

The v3 host observes eight explicit native command boundaries using Harmony prefixes,
postfixes and finalizers with scoped `CardSelectorPrefs`. The original native commands,
effects and selection tasks still run. Unknown preferences are not replaced with defaults.
Current `selection_ref` is required for confirmation/cancellation; cancellation also requires
native permission. Per-instance references stay private. This interception failed on .NET 10
and must not be silently skipped: current probe configs bind official .NET 9.0.7, its whole
runtime file inventory and actual process-reported runtime version separately from the compiler.

Purchases require the current entry, item and quoted gold price. Restocking cannot reuse a stale
item request. Successful removal calls the same native `SetUsed` method as the rendered merchant's
completion handler; a canceled purchase does not. Native potion capacity/procurement rules own
enablement. While a card selection is open, purchases/leave are refused. The canonical surface
keeps prices, definitions and preferences public while retaining native operands privately.

The [current build](../../configs/engine-qualification/sts2-v0.111.0-cli-build-selection-shop-v3.json),
[rest panel](../../configs/engine-qualification/sts2-v0.111.0-cli-rest-projection-v3-retry1.json) and
[shop panel](../../configs/engine-qualification/sts2-v0.111.0-cli-shop-projection-v3-retry1.json)
have separate frozen identities. The panels run nine rest and seven shop fixtures through the
strict SDK and exactly-once ledger. Earlier failed/scope-limited configurations and reports remain
preserved; their pins must not be reused for this host. Use
`engine-selection-shop-surface.mjs` and the current v3 projection probe with this build.

Remaining work includes native discounts and relic purchases, other selection mechanics,
large selections beyond finite enumeration, out-of-combat potion controls, card costs/effect
ordering and shipped differential comparisons. No full-run or training admission follows these
panels. Eight installed observation boundaries are not an exhaustive mechanics pass.

```bash
node --test scripts/engine-selection-shop-surface.test.mjs
```

## Current combat, content and exact-text host

`sts2-cli-v0.111.0-localization-v6.patch` is the current combined local delta over the
unchanged pinned base patch. It includes the earlier rest/shop/selection fixes, combat
bindings, explicit native content policy and exact-text override. Apply **one** local delta;
do not stack v2/v3/v4/v5/v6. The v4 combat and v5 content deltas remain reconstruction
history, with their own candidate and failed/scoped reports.

The v6 host preserves native per-copy costs, X-cost identity, targeted potion validation,
hand upgrade operands and selection copy references. It installs nine observed selection
boundaries. `FromHandForUpgrade` has no `CardSelectorPrefs` argument: that boundary uses the
version-bound native UI contract with an explicit one-card upgrade preference. This is a
documented UI seam, not a claim of observing a parameter that does not exist. Native card
effects, target legality and tasks still run; a shipped comparison remains required.

`sts2-headless-player-projection-v2.patch` replaces the v1 hook on the same upstream source.
It adds an optional read projector without changing historical defaults. Current combat
reads use `engine-combat-surface.mjs` to remove hidden pile enumeration/indices and sort
public facts and opaque copy identities. Current cost, status amount and intent hit/count/
total facts retain their public owner. Missing modifier definitions or unqualified companion,
orb or target semantics produce unavailable actions rather than a guessed menu.

The fresh-profile tutorial route and old bundled text were separate startup defects.
`native_all_unlocked` explicitly uses the game-owned `UnlockState.all`; historical
`local_progress` stays the default. `STS2_NATIVE_LOCALIZATION` points only at privately
extracted, hash-verified text from the exact pack, checked before/after v6 probes. The
host can optionally call the game's current-room save path for a Continue fixture; the
historical pre-room save behavior remains available.

[Current build](../../configs/engine-qualification/sts2-v0.111.0-cli-build-localization-v6.json)
and [public evidence](../../docs/evidence/actual-engine-v0.111.0-combat-and-starting-inputs-v1.json)
bind all source/runtime/text/SDK identities. The 28 named combat/rest/shop fixtures pass
841 subchecks with 85 SDK snapshots; one native A8 starting save passes 14 shipped startup
gates. Neither result establishes full-run parity, exhaustive mechanic coverage or training
admission. The owner repeat-seed panel is separate and has not been launched.

Historical configs intentionally refuse changed helper bytes. Their exact prior versions
are retained beside private attempts; reconstruction must restore those hashes rather than
reuse a current helper under an old result identity. No proprietary extraction is committed.

```bash
node --test scripts/engine-combat-surface.test.mjs scripts/engine-checkpoint-shipped-probe.test.mjs
```
