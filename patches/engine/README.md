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
and the Proceed flag replaces UI presentation state. The original package did not qualify
Continue-save rest resumption; the later v8 restoration and rest results are recorded below.
The shipped-host differential case must start with
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

## Preserved combat, content and exact-text host

`sts2-cli-v0.111.0-localization-v6.patch` is the earlier combined local delta over the
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
admission. The subsequent owner repeat-seed panel passed; its new evidence is recorded below.

Historical configs intentionally refuse changed helper bytes. Their exact prior versions
are retained beside private attempts; reconstruction must restore those hashes rather than
reuse a current helper under an old result identity. No proprietary extraction is committed.

```bash
node --test scripts/engine-combat-surface.test.mjs scripts/engine-checkpoint-shipped-probe.test.mjs
```

## Current finished-event Proceed host and first-combat comparison

`sts2-cli-v0.111.0-event-proceed-v7.patch` replaces v6 on the same pinned base patch.
Apply **one combined local delta**, not stacked v6/v7 patches. The game DLL stays unchanged.
The shipped comparison caught v6 skipping a finished event's Proceed button. V7 implements the
exact `NEventRoom.UpdateOptions` finished-option / `NEventRoom.Proceed` UI boundary with a native
`EventOption`; choosing it sets the existing map-presentation flag. Observation does not claim
rewards or move rooms. Native map voting still owns travel. Pending selection/reward/bundle/task
states cannot dispatch an event choice. This is a declared version-bound UI seam, not a change
to native game rules or a broadly qualified event adapter.

The [v7 build](../../configs/engine-qualification/sts2-v0.111.0-cli-build-event-proceed-v7.json)
pins the combined source diff, patch, deterministic binary/MVID, compiler, runtime and unchanged
game DLL. The 28 combat/rest/shop fixtures were rerun with new v7 configs: 841 subchecks, 85 SDK
snapshots, 60 delivered actions and 34 invalid native inputs pass. Old reports/configs remain
bound to their original bytes; their results are not automatically transferred.

The common first-turn contract uses public semantic action operands across opaque host identities.
It preserves current card costs/playability, public HP/energy/block, typed status ownership,
next map options and numeric attack damage/hits. Unknown labels and missing data fail. It excludes
effect text, preview stats, relic counters, full map topology, pile contents and later mechanics;
see [scoped evidence](../../docs/evidence/actual-engine-v0.111.0-starting-and-first-combat-v1.json).
The native host creates a normal seeded A8 starting save; the shipped Host imports that save via
Continue and replays only the complete current legal menus. No named combat-state injection is
used in these prefix comparisons. The initial read-only setup calls are recorded separately.

A fresh shipped profile's three-page Combat Basics modal exposes `advance_tutorial` even on its
final Finish page. The versioned tutorial helper selects that exact current advertised forward
control, ignores Previous Page and checks underlying public combat facts before/after every
click. It never fabricates legal gameplay actions while the modal is open. Unknown tutorials fail.
The skipped-Proceed and earlier tutorial-helper failures remain preserved with separate identities.

Two single-seed/choice comparisons passed through card plays and the fresh second turn. The owner
subsequently completed eight repeated cases with zero failures, two independent seeds and four
seed/choice pairs. A pure saved-data audit rechecked 60 observations, 52 actions and 24 tutorial
steps against the raw public snapshots without launching games.

```bash
node --test scripts/engine-journey-contract*.test.mjs scripts/engine-journey-tutorial*.test.mjs
```

## Current saved-run restoration and rest action comparison

`sts2-cli-v0.111.0-save-restore-v8.patch` replaces v7 on the same pinned base. Apply one combined
local delta, not stacked v7/v8 patches. The rules DLL remains unchanged. `LoadSave` formerly used
`EnterAct`, resetting saved map/room/history state; v8 follows the actual game's saved-run lifecycle
with `Launch`, `GenerateMap` and `LoadIntoLatestMapCoord` plus the serialized previous room.
This is verified on the named rest resume; it does not establish all saved-run parity.

[V8 build pins](../../configs/engine-qualification/sts2-v0.111.0-cli-build-save-restore-v8.json)
bind the combined patch/source diff, compiler, two reproducible baseline/two repaired outputs,
MVID, runtime, Godot stub and game DLL. Builds took 16.160 seconds. V8's 28 native combat/rest/shop
fixtures were independently rerun: 841 subchecks, 85 SDK snapshots, 60 delivered actions and
34 refused invalid inputs pass. They remain privileged regressions, not bulk learning inputs.

The rest bridge intentionally injects a single-card Miniature Tent fixture into a native save,
resumes it in a fresh managed process and imports the same save into the shipped Host via Continue.
Two short comparisons pass heal-before-Smith and Smith-before-heal on different seeds, including
cancel/reopen, actual upgrade confirmation, remaining choices and explicit Proceed. Healing is
25→49 HP. The native wrapper confirms a selected card atomically; the shipped UI selects, previews
and confirms. The extra UI step is recorded and must not mutate public game facts before commit.
Only the observed operand-free Proceed control and boolean rest schema spellings are normalized.
The single-card effect-menu normalization refuses unknown controls or multiple-card fixtures.
Raw complete menus are retained; preview-toggle/back execution and effect text/stats remain outside
this scope. The shipped helper waits for 600 ms of unchanged complete state to avoid the preserved
stale-after-cancel failure; delivered actions are never silently retried.

The fresh rest tutorial is unsupported by the released Host. The scoped test imports native-generated
progress with only that tutorial already seen; it verifies the original report/profile and copied
bytes while leaving other tutorials enabled. Fresh-profile unattended control stays unqualified.
[Scoped evidence](../../docs/evidence/actual-engine-v0.111.0-first-combat-and-rest-v1.json) binds
successful comparisons, private failures, lineage and the unlaunched eight-case owner rest recipe.
No naturally reached rest/full-run claim, training admission or old-model promotion follows.

```bash
node --test scripts/engine-rest-bridge-contract.test.mjs
```

## Local Connector rest tutorial candidate

`sts2-connector-v0.111.0-rest-tutorial-v1.patch` changes the MIT-licensed
`rsgcsg/STS2-Connector` Host at tag `v1.1.0-rc.1`, revision
`e0651024117d22bdeb95142766917103d87c0185`. Keep its separate
[MIT notice](sts2-connector-MIT-LICENSE.txt). It does not alter proprietary game code, the SDK,
game DLL or GodotSharp. The released Host previously classified the rest-site tutorial as
unsupported and offered no controls.

The patch recognizes only the current exact `NRestSiteFtue` modal. It reads the visible native
title/body/confirmation label and exposes one enabled `dismiss_tutorial` action through the
existing protocol. Delivery resolves the current visible enabled confirmation button and invokes
its native click handler. Unknown modals, incomplete facts, disabled buttons and unrelated
operations remain refused. No generic modal close, tutorial-progress editing or gameplay action
is invented while the popup is open. A focused Host test enforces the exact modal/action scope.

[Build recipe v2](../../configs/engine-qualification/sts2-v0.111.0-connector-rest-build-v2.json)
creates two fresh source trees, applies the patch and compiles against the frozen game. A fixed
local commit/date, SDK 10.0.401, deterministic output and source-path mapping reproduce both
SHA/MVID pairs. The local source commit is `01139c3207378ffff14daaa2d07930b56a928a2a`;
Host SHA is `cb287fc1798b75ac7de05b991217c357092f4dabf604981915231392c64812a8`
and MVID `16c8b163-b3c2-450c-b68c-6f10600871f1`.
[Connector config v2](../../configs/engine-qualification/sts2-v0.111.0-connector-rest-tutorial-v2.json)
pins the new identity and separately inventoried local toolchain. It removes the copied original
runtime seal/release manifest; it cannot claim upstream release authority or silently fall back
to the original binary. Failed initial build attempts remain private and preserved. The v1
build/config pair refers to those attempts; use the v2 pair for the completed candidate.

The owner's original eight-case rest panel passes, with 56 independently audited observations
and 48 rest decisions, on the original Host and already-seen tutorial baseline. Two new short
checks pass both action orders on the patched Host using settings-only profiles with no copied
tutorial progress. Each actually dismisses the popup, then heals/cancels/reopens/upgrades/leaves.
The popup click is separate from seven game/UI actions and must preserve public game facts.
Both raw audits and all three focused Host tutorial tests pass. The patch requires its own
subsequent repeat panel and prior-family regressions; old Host results do not qualify it.
[Current evidence](../../docs/evidence/actual-engine-v0.111.0-rest-panel-and-tutorial-v1.json)
records identities and limits. No full-run, general mechanics or training admission follows.

Portable synthetic checks require no proprietary observations or game files:

```bash
node --test scripts/verify-engine-rest-saved.test.mjs
```

## Current native potion pricing and shop comparison

`sts2-cli-v0.111.0-potion-pricing-v9.patch` replaces the combined v8 delta on the same pinned
upstream/base patch. Apply **one combined local delta**, not stacked v8/v9 patches. The original
game DLL on disk remains byte-identical. The shop comparison found that TestMode skips the
native potion price random adjustment and its shop-RNG consumption: one native quote was 75
gold while the shipped game quoted 79.

V9 installs a Harmony transpiler only on `MerchantPotionEntry.CalcCost`. It requires exactly
one `TestMode.IsOff` call and changes that branch predicate to true so the original native
formula and RNG call execute. Missing or ambiguous bindings fail rather than silently skipping
the repair. Global TestMode remains unchanged. This runtime interception is a candidate wrapper
repair, not automatic game authority. Other TestMode branches that affect rules/RNG remain a
required audit before broad qualification.

The [v9 build recipe](../../configs/engine-qualification/sts2-v0.111.0-cli-build-potion-pricing-v9.json)
reproduces two baseline/two repaired outputs in 21.596 seconds. The repaired SHA is
`c47fafb1dab14f73227f8709f542cf2fc8c49232a8559dfda16aade0384d4ab8`, MVID
`a813471b-2515-4267-95b6-3553a9ae4f49`, on separately pinned .NET 9.0.7. This reproduces
the local toolchain candidate, not the upstream binary. New v9 combat/rest/shop regression
configs rerun all 28 fixtures: 841 subchecks, 85 SDK snapshots, 60 delivered actions and 34
refused invalid inputs pass. Old results retain their own identities.

The shop bridge injects a single Strike, 1,000 gold and two empty A8 potion slots, with or
without The Courier. It imports that same native shop save through shipped Continue. The
current contract compares stock/prices/legal menus, deck/potion ownership, gold, capacity,
card removal cancel/reopen/confirm and explicit exit. The native atomic removal and shipped
select/automatic-preview/confirm flows are represented separately. Fresh current operands,
preview invariants and complete delivery receipts are required. Sold-out display model identity,
relic purchases, other discounts, out-of-combat potion use and skipping the merchant before
opening inventory remain unqualified.

One ordinary case and one Courier case pass on different seeds, together with raw saved audits:
19 common observations, 17 effect decisions and 25 game/UI actions, including two fresh potion
tutorial clicks. Their shipped processes take 39.387 and 37.200 seconds. These are privileged
finite fixture comparisons, not naturally reached rooms, repeatability evidence or player
strength. The [eight-case recipe](../../scripts/compare-shop-actions-v1.sh) was then explicitly
authorized for Codex to run: one case passed, one native case failed and six were unattempted.
The restocked Whirlwind is present and charged correctly, but the native shop exports energy
cost 0 while the deck exports X. The shop exporter still uses numeric resolved cost instead
of the X-cost display helper used by deck/hand. Repair that gap on a new source/build lineage
before repeating. The failed batch is preserved; its recipe does not restart it silently.
[Assessment](../../docs/evidence/actual-engine-v0.111.0-shop-panel-v1.json) records the exact scope.

## Current local rest-and-potion Connector candidate

`sts2-connector-v0.111.0-rest-potion-tutorial-v2.patch` replaces the rest-only patch on the
same pinned MIT Connector revision. Do not apply both local patches. Preserve the separate
[MIT notice](sts2-connector-MIT-LICENSE.txt). It retains exact `NRestSiteFtue` confirmation and
adds only the exact current `NObtainPotionFtue` visible enabled confirmation. Unknown/incomplete
popups still fail; no progress is copied/edited and no generic modal close is exposed.

The [v3 build recipe](../../configs/engine-qualification/sts2-v0.111.0-connector-rest-potion-build-v3.json)
reproduces two fresh builds in 16.621 seconds. Local source revision is
`3769f2a20b3d122959047b25bc9af876a1fcd887`, Host SHA
`0c6833f8dc426c3ca1951aaaa1cd9f6735a1639eb15289e34eb80cc3ca3b4d92`, MVID
`3bacb44d-f16f-4240-9e30-7aa62ce62e50`. The
[v3 Connector config](../../configs/engine-qualification/sts2-v0.111.0-connector-rest-potion-tutorial-v3.json)
binds the separately inventoried local toolchain. It cannot inherit upstream release/seal
authority; original Host/seal, SDK, game DLL and prior evidence are preserved.

The owner's rest-only Host panel passes eight fresh-profile repeated cases. Prior-family
regressions on that Host pass two first-combat prefixes. The current cumulative Host/v9 native
pair has its own passing fresh rest, first-combat and two shop checks; none inherits a previous
binary's test result. Four focused Host tutorial tests pass. First-potion popup dismissal must
leave the already completed purchase's public facts unchanged. All failed comparisons/builds/
copy attempts and partial payloads remain private; successful copies are removed only after
verified natural shutdown/integrity. A 3.5-GB free-space guard runs before another game copy.

[Fresh rest and shop evidence](../../docs/evidence/actual-engine-v0.111.0-fresh-rest-and-shop-v1.json)
records frozen configs/build/runtime/adapter identities, saved audits and exact scopes. No
full-run, general mechanics, learning admission or model promotion follows.

```bash
node --test scripts/engine-shop-bridge-contract.test.mjs scripts/verify-engine-shop-saved.test.mjs
uv run pytest tests/unit/test_engine_shop_bridge.py
```

## Current X-cost shop export repair

`sts2-cli-v0.111.0-shop-energy-v10.patch` replaces the combined v9 delta on the same pinned
upstream/base patch. Apply one combined local delta; do not stack v9/v10 patches. The native
shop exporter previously called numeric `GetResolved()` for card energy cost, while deck/hand
exports handled `CostsX`. Courier restocking exposed this with Whirlwind: the offer said 0,
the obtained deck card said X, and the strict ownership/cost check failed despite the correctly
completed 57-gold purchase. The failed first batch remains preserved with one pass, one failure
and six unattempted cases.

V10 uses the existing `VisibleEnergyCost` function for a shop card's current model. That function
checks the native `CostsX` property and otherwise calls `GetAmountToSpend`, as existing deck/hand
exports do. Energy cost stays separate from the merchant's gold quote. It neither guesses from
card definitions nor changes rules, prices, RNG, purchase effects or comparison tolerances.
The cost read occurs outside the unrelated stats-preview try/catch so an exception cannot be
reported as a made-up zero. Sold entries with no model retain null energy cost; live stock still
requires an actual current model. The official stored game assembly is unchanged.

The [v10 build recipe](../../configs/engine-qualification/sts2-v0.111.0-cli-build-shop-energy-v10.json)
reproduces two fresh baseline and two repaired outputs in **15.147 seconds**. Repaired SHA is
`4b2c132520da2159823aabd599a3eb86c3c1504cb8874b2f2da5aaa92784e726`, MVID
`3b42f25b-62b8-45dc-805b-7e67f5d341be`. Source diff, patch, compiler/reference pack, .NET 9.0.7
runtime, original DLL and Godot stub have separate exact pins. This is local build reproduction,
not the upstream binary. V10's new combat/rest/shop configs rerun **841 subchecks across 28
privileged fixtures**, with 85 snapshots, 60 delivered actions and 34 invalid inputs refused.

The observed Courier seed now passes the native/shipped sequence and an independent raw saved
audit: ten observations, nine effect decisions and thirteen game/UI actions, including a fresh
potion tutorial. Whirlwind is X in both the live offer and purchased deck. The shipped process
took **36.032 seconds**. New synthetic checks retain X versus free zero through shop projection,
restocking, gold-quote binding and saved purchase auditing; relabeling X as zero still fails.
Existing semantic/purchase verifiers and the shipped Host remain unchanged.

The [separately versioned eight-case recipe](../../scripts/compare-shop-actions-v2.sh) writes new
results and never resumes or overwrites v1. Its two seeds/four seed-scenario pairs each repeat
twice under the original finite resource caps. This same shop comparison stage was authorized
for Codex to run. Its results and scope belong to
[the v10 evidence](../../docs/evidence/actual-engine-v0.111.0-shop-energy-v10-and-panel-v2.json).
The [compiled mode inventory](../../mod/SpireShift.ModeInventory/README.md) now enumerates all
direct references to the two named mode controls without executing game code. Its
[initial review](../../docs/evidence/actual-engine-v0.111.0-mode-audit-v1.json) confirms preset
Calling Bell/Cauldron rewards and automatic first-bundle selection; these remain unfixed in
v10. The review covers 25 of 434 game references, leaving 409 unreviewed. The broader semantic
audit, preview/effect metadata, other mechanics, later acts and endings remain unqualified.
No full-run or neural-training admission follows the shop fixtures or static mode inventory.
