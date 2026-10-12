# Actual-engine v0.111.0 qualification

The owner accepted [ADR 0005](decisions/0005-actual-engine-v0.111.0-qualification.md).
Exact acquisition and preservation [#144](https://github.com/benyanc/spireshift/issues/144) are
complete. Public control/mechanics [#145](https://github.com/benyanc/spireshift/issues/145) are current;
full-run speed and neural integration [#146](https://github.com/benyanc/spireshift/issues/146) follow.

## Current status — bundle selection repaired; fresh repeated UI retry prepared

V12 makes bundle-hook installation mandatory, rejects invalid/stale choices, preserves native
choice synchronization and clears pending bindings on reset. The public menu includes exact
card identities and current X/free costs. Eight native seed/pack/repeat cases and a separate
two-seed synchronization fixture pass. One natural Scroll Boxes comparison also passes in the
shipped game: choose the second pack, cancel its preview, reopen and confirm, then receive
exactly those cards. It compares visible identities/costs/upgrades and persistent ownership;
it does not qualify general card text/effect semantics or all bundle mechanics.

The original v1 batch stopped at its free-space guard before attempting any of its eight
cases. Its failed result and resource report remain immutable; rerunning v1 only displays that
failure. It did not find a game-mechanics mismatch.

The next owner stage is [compare-bundle-actions-v3.sh](../scripts/compare-bundle-actions-v3.sh):
the same eight shipped comparisons across two independent seeds, both packs, each twice, using
one fixed working app. Each attempt has a fresh profile; connector/settings additions are removed
after verified shutdown and the app returns to the frozen file baseline. Two short real cases pass
with the same app path/inode, distinct profiles and one total app copy. Their raw saved audits pass. A separate short native startup also reuses and restores the same app.

The reuse policy under [#147](https://github.com/benyanc/spireshift/issues/147) locks the app, binds
its exact game inventory and limits the managed pool to two apps / 5 GB. Interrupted or changed
apps block later reuse and stay preserved for inspection. A read-only inventory reports managed
apps plus other existing `game` payload directories. Menu/bootstrap APIs also accept the explicit
reuse policy. Historical recipes retain their original behavior; parallel workers remain under #146.
Details: [working app reuse](working-app-reuse.md).

Expect 6–9 minutes for the v3 panel; its cap is 15 minutes and the first difference stops it. The
resource wrapper counts the app pool, and a saved raw audit follows success without another game
launch. This complete repeat panel has not started. The v1 failure and unused v2 recipe remain
separate; [retry evidence](evidence/actual-engine-v0.111.0-bundle-retry-v2.json) records the earlier
preflight repair.
[V12 evidence](evidence/actual-engine-v0.111.0-bundle-choice-v12.json) records native checks, the
single successful prototype, preserved failures, source/build identities and limits. No complete
run or learning follows this package. Full reward pickup, discovery/profile state, remaining
mode references, broader mechanics and actual endings still precede #146.

## Acquisition and preservation

The owner successfully downloaded the exact macOS depot using the pinned licensed
DepotDownloader route. The downloaded executable, rules DLL and GodotSharp match **v0.111.0 /
41cef1ea**. The request was app `2868840`, depot `2868842`, manifest `5045320271505434676`, with
explicit `public-beta` context. The owner reports **1,323,157,968 bytes downloaded /
2,406,415,347 bytes extracted**. The earlier Steam-cache transfer estimate remains historical;
the successful result does not prove which change resolved the earlier access failure.

Codex froze the copy at
`~/Library/Application Support/SpireShift/frozen-games/sts2-v0.111.0-41cef1ea-macos-arm64-v1`,
with the full game at `steamapps/common/Slay the Spire 2`. All **435 files / 2,406,594,686 bytes**
matched the source, including depot metadata. Freezing took **6.046 seconds**; a separate current
integrity check passed in **1.411 seconds**. No old Steam app manifest was borrowed or fabricated.
The download, frozen archive and existing v0.107.1 game remain distinct copies. Details:
[acquisition/preservation evidence](evidence/actual-engine-v0.111.0-acquired-and-frozen-v1.json).

## Earlier combat and startup package

The earlier v6 host reproduces two fresh baseline and two fresh repaired binaries in
**16.667 seconds**, leaves the official game DLL unchanged, and runs on the separately pinned
**.NET 9.0.7** runtime. Twelve combat, nine rest and seven shop fixtures pass **841 subchecks**
plus the separate integrity/isolation gates. All **85 canonical SDK snapshots** have complete
metadata/action menus; 60 actions deliver and 34 deliberately invalid native inputs are refused.
These are subchecks inside **28 privileged fixtures**, not 841 independent experiments.

Combat preserves per-copy current costs, X-cost display, generated/drawn/exhausted copies,
player/enemy status ownership and per-hit/count/total intent amounts. Native target validation
and effects still own potion use. Hand upgrade selects the intended copy. The public pile
projection discards native enumeration and indices before sorting public facts and opaque copy
identities; merely labeling the original list unordered did not hide its draw order.

A settings-only native profile entered the tutorial path and skipped the normal starting reward.
The new explicit `native_all_unlocked` policy takes the game's `UnlockState.all`; it does not
invent a local content list or silently change the historical `local_progress` default. When
that path exposed missing current localization in the old wrapper, 92 exact tables were privately
extracted from the frozen Godot 4.5.1 PCK V3: 46 English and 46 Simplified Chinese tables, with
7,028 and 6,937 keys respectively. Pack, table inventory and extraction evidence are verified
before and after each v6 probe. The pack parser follows the
[official Godot 4.5 directory format](https://github.com/godotengine/godot/blob/4.5/core/io/file_access_pack.cpp).
No game text/assets are committed or treated as independently qualified mechanics.

The native host now optionally saves the **current room** instead of rolling back to the
historical pre-room state. One native Ironclad/A8 Neow save imports into the shipped Host through
its normal Continue action. **14/14 gates pass in 30.460 seconds**: native seed and A8 survive;
offered starting option titles/availability agree; the fresh canonical snapshot is complete;
process identity, natural exit, shared-save and game/archive integrity pass. The check compares
those visible option facts only, not the full text/semantic payload or combat/rest/shop effects.
The 1,090 errors and two warnings remain preserved headless diagnostics, not a clean-runtime
claim. The successful disposable game copy was removed after verification; saves, logs, profiles
and reports remain. Failed copies are preserved.

[Combat and starting-input evidence](evidence/actual-engine-v0.111.0-combat-and-starting-inputs-v1.json)
records the distinct source/patch/build, native text, runtime, SDK and report identities. The
baseline AnyPlayer potion, X-cost/upgrade-copy, fresh-profile tutorial, stale localization and
entry-path failures remain private evidence. Unknown enchantment/affliction details, companions,
orbs and unsupported targets fail closed. Nine installed preference boundaries include a
version-bound hand-upgrade UI seam; they do not qualify every possible selector.

## Completed starting panel and first combat actions

The owner completed **12/12 startup comparisons with zero failures**: six independent A8 seeds,
each imported twice. Starting reward titles/lock availability match, and repeated seeds offer
identical choices. The batch took **454.073 seconds**; its resource wrapper recorded 454.287 wall
and 175.134 CPU seconds. A separate saved-file verifier rechecked all twelve case/config/report,
snapshot and native-save bindings without launching games. Unknown cost rates remain unknown.

The first actual-action comparison found a genuine wrapper omission: after a starting reward,
the shipped game offers **Proceed**, while v6 skipped straight to the map. The new combined
**v7 event-Proceed patch** exposes that native UI step. Its callback opens map presentation;
actual native map voting still owns travel, and the official rules DLL is unchanged. Two fresh
baseline and two repaired builds reproduce the newly pinned binary in **43.857 seconds**.
The v7 combat/rest/shop panels were rerun rather than inheriting v6 results: **841/841 subchecks**
across 28 fixtures pass, with 85 SDK snapshots, 60 delivered actions and 34 invalid native inputs
refused. Those remain privileged regressions, not shipped-game comparisons or training data.

Two short comparisons on **one seed**, choosing Winged Boots or Dowsing Rod, now pass through
starting reward, Proceed, first map node, card plays, End Turn and the next hand/enemy state.
There are **eight and seven compared observations**, with seven and six delivered game actions.
The shipped processes took **41.531 and 36.915 seconds** and exited naturally. A fresh shipped
profile displays the three-page Combat Basics tutorial; the adapter resolves each current public
forward control, records it separately from gameplay actions, and checks unchanged underlying
public combat facts after every click. Successful disposable payloads were removed after all
18 control/comparison/integrity gates; failed attempts, reports, logs, profiles and saves remain.

This first-turn comparison covers current legal actions, public hand costs/playability, owned
status amounts, enemy health/block and numeric attack intents, energy, pile counts, immediate
map choices and persistent player facts. It explicitly excludes effect text, card preview stats,
relic counters, full map topology, pile contents, other decision families and later turns/acts/
endings. It is not broad engine parity. Exact public numeric attack labels are normalized;
unknown labels or missing fields fail rather than becoming zeros.

[Starting and first-combat evidence](evidence/actual-engine-v0.111.0-starting-and-first-combat-v1.json)
binds the owner batch, saved verification, v7 build/patch, rerun panels, successful comparisons,
preserved failures and the then-next recipe. Historical evidence and configurations remain
immutable. The second seed's native prefixes were preflighted in 2.757 and 2.253 seconds before
the owner's batch. That package's 1,054 repository and 49 standalone adapter test results remain
historical.

## Completed owner first-combat panel and rest package

The owner completed **8/8 first-combat comparisons with zero failures or unattempted cases**.
Two independent seeds × Winged Boots/Dowsing Rod × two repeats constitute four seed/option
pairs. All **60 observations, 52 gameplay actions and 24 tutorial steps** agree within the scoped
first-turn contract. The batch took **406.247 seconds**; resource wall/CPU time was
406.475/139.826 seconds. A new read-only audit reconstructs facts from the raw native and shipped
snapshots, verifies unique current action operands, tutorial invariants and delivery receipts,
and checks frozen configs/report/save/snapshot identities. No games were launched for that audit.

Rest loading exposed a separate wrapper defect: `LoadSave` used `EnterAct`, reopening map
presentation and resetting saved room/history information. The new combined **v8 save-restore
patch** follows the frozen game's `Launch`, `GenerateMap` and `LoadIntoLatestMapCoord` saved-run
sequence with its serialized previous room. Two baseline/two repaired builds reproduce in
**16.160 seconds**. The official game DLL stays unchanged. V8's 28 privileged combat/rest/shop
fixtures were rerun: **841 subchecks, 85 SDK snapshots, 60 delivered actions and 34 refused invalid
inputs** pass. This repairs the tested rest resume, not every possible saved-run situation.

Two short shipped comparisons now pass a deliberately injected **Ironclad/A8, 25/80 HP,
single Strike, Miniature Tent rest fixture**. One heals before Smith; the other upgrades before
healing. Both cancel and reopen the upgrade picker, confirm the upgrade, retain the correct
remaining options, and explicitly use Proceed. HP reaches **49**. Seven matched observations and
six effect decisions are recorded per case; the shipped UI takes seven delivered actions because
it selects the card before a separate preview/confirmation. The preview retains the chosen card,
shows the expected current cost/upgraded flag and leaves game facts unchanged before commitment.
The shipped processes took **55.886 and 51.425 seconds**. The other two seed/sequence pairs also
pass short native preflights; their shipped comparisons belong to the next owner batch.

The rest comparison includes run/player facts, relic definitions, complete public deck definition/
cost/upgraded flags, remaining rest choices/enablement/Proceed, single-card selection bounds and
cancelability, effect-relevant choice menus and subsequent map options. The full raw shipped menu
is retained; its observed preview toggle is classified as presentation and is not exercised.
Native atomic upgrade and shipped select/preview/confirm are explicitly different control flows.
This is a **privileged single-card mechanics fixture**, not a naturally reached room, general
selector parity, effect-text/preview-stat comparison or evidence of model strength.

The released Host marks the **fresh rest-site tutorial** unsupported and advertises no controls.
That failed attempt remains saved. The isolated rest fixture copies progress generated by that
native process, with only `rest_site_ftue` already seen and other tutorials enabled. Its source
report, source profile and copied bytes are verified. This does not qualify unattended play from
a fresh profile. A later cancelled-picker animation caused a stale-state refusal; that failure
also remains. The helper now requires an unchanged complete observation for 600 ms before acting.
No failed action is silently retried. Successful copied game payloads were removed after natural
shutdown and integrity checks; failed copies, reports/logs/profiles/saves remain.

[First-combat and rest evidence](evidence/actual-engine-v0.111.0-first-combat-and-rest-v1.json)
binds the completed owner batch/audit, v8 source/build, rerun regressions, two rest comparisons,
preserved gaps and next recipe. **1,058 repository tests, 61 standalone Node tests,
formatting/types and the C# protocol contract pass.** Portable checks do not establish gameplay
strength. No training admission, full-run attempts or checkpoint promotion follow.

## Completed rest panel and fresh tutorial repair

The owner completed **8/8 rest comparisons with zero failures or unattempted cases**. Two seeds,
two action orders and two repeats give **two independent seeds and four seed/sequence pairs**.
The batch took **383.715 seconds**; resource wall/CPU time was **383.922/133.795 seconds**.
A separate read-only audit reconstructs **56 observations, 48 rest decisions, 56 game/UI actions
and eight upgrade preview steps** from the raw saved evidence. It verifies current action
bindings, unique delivery receipts, unchanged selection/preview facts, healing/upgrades,
configuration/report/save bindings and identical repeated prefixes. No game or learning follows
that audit. The completed panel uses the historical isolated already-seen rest tutorial baseline.

The fresh tutorial blocker has a separately versioned **MIT Connector Host patch**. It reads
only the exact current `NRestSiteFtue` popup and exposes its live visible confirmation through
the existing legal-action contract. It clicks the native button; it does not edit progress or
close arbitrary modals. Unknown/incomplete controls still fail. The original Host and runtime seal
are preserved; this local canary has its own source commit, SHA/MVID, build report and inventory,
and cannot inherit the original release seal. The SDK and official rules DLL remain unchanged.
Two fresh deterministic builds reproduce in **7.711 seconds**.

Two new short checks use settings-only profiles with **no copied tutorial progress**. The first
heals before Smith; the second upgrades before healing. Both dismiss the actual rest popup,
verify unchanged underlying deck/player facts, then heal, cancel/reopen Smith, select and confirm
the upgrade, retain remaining choices and use Proceed. Each compares seven common observations,
six rest decisions and seven shipped game/UI actions; one popup click is counted separately.
The shipped processes take **36.164 and 35.118 seconds**. Both saved raw audits pass, and successful
payloads were removed after verification. The first smoke predates the explicit outer
progress-absence gate; its consent record includes that check. The second smoke and owner recipe
require both progress absence and verified popup dismissal before success cleanup.

[Rest panel and tutorial evidence](evidence/actual-engine-v0.111.0-rest-panel-and-tutorial-v1.json)
records the owner result, independent audit, source patch/build identities, both new checks and
the next recipe. **1,064 repository tests, 75 standalone Node tests, three focused Host tutorial
tests, formatting/types and the C# protocol contract pass.** These are privileged single-card
mechanics checks, not naturally reached rooms, broad selector coverage, full-game compatibility
or player strength. Because the Host binary changed, earlier shipped startup/combat results must
be rechecked on it before relying on those families.

## Completed fresh-profile rest panel and shop package

The owner completed **8/8 fresh rest comparisons** with zero failures or unattempted cases. Two
seeds × two orders × two repeats provide four seed/order pairs. Each settings-only profile has
no copied tutorial progress and actually clicks the fresh popup. The independent saved audit
verifies **56 observations, 48 rest decisions, 56 game/UI actions, eight upgrade previews and
eight tutorial clicks**. Batch/resource wall time is **428.762/428.978 seconds**, CPU **149.838
seconds**. All repeated prefixes agree. No games or optimizers ran for that audit.

The rest-patched Host also passes two targeted startup/first-combat checks on different existing
seeds, taking **41.097 and 39.618 shipped-process seconds**. One earlier installation timeout is
preserved; the explicit new-directory retry passes. This is two finite regressions, not a new
repeated panel or proof about all combat.

Shipped shop testing found that the native wrapper's TestMode skipped the game's random potion
price adjustment: one initial quote was **75 versus 79 gold**. The original native method also
advances the shop RNG. The separately pinned **v9 cumulative MIT wrapper patch** enables that
method's original branch without replacing its formula or changing global TestMode. Stored game
DLL bytes stay unchanged. Two baseline/two repaired builds reproduce in **21.596 seconds**; all
**841 native subchecks across 28 combat/rest/shop fixtures** pass again. Other rule/RNG-changing
TestMode branches still need auditing; this fix does not qualify all native behavior.

Obtaining the first potion exposed another fresh tutorial that the earlier Host could not control.
The cumulative **rest-and-potion Host patch** recognizes only the exact current obtain-potion
popup and clicks its visible enabled confirmation. It retains rest support, leaves tutorials enabled,
and never copies already-seen progress. Two fresh builds reproduce in **16.621 seconds**; the new
source/SHA/MVID/toolchain remain distinct from earlier Hosts and upstream release authority.
Four focused Host tutorial tests pass. A fresh rest sequence on this Host/native-v9 pair passes
seven observations and six effect decisions in **42.700 shipped-process seconds**. The matching
first-combat regression passes eight observations, seven gameplay actions and three tutorial
steps in **41.168 seconds**. Both saved audits pass. These are targeted regressions, not new
repeat-seed panels.

**Two shipped shop comparisons and both saved audits pass.** Ordinary purchases on one seed and
Courier restocking on another compare every current offer, price, availability and legal menu,
then card/potion ownership, gold, both potion slots, removal cancellation/reopening/confirmation
and exit to the map. Totals: **19 common observations, 17 effect decisions and 25 shipped game/UI
actions**, including two potion tutorial clicks and six other shop/preview UI steps. Shipped-process
times are **39.387 and 37.200 seconds**. A first-removal
selection enters preview immediately; the native wrapper's atomic selection and shipped select/confirm
flows are explicitly accounted for. Card purchases and removal charge the current quote once.
Courier replacement items and new prices bind to fresh controls; full potion slots disable purchases.

This is a privileged **single-Strike, 1,000-gold shop fixture**, with/without Courier, imported
through Continue. It is not a naturally reached shop, general effect-text/stat comparison,
relic-purchase or out-of-combat potion-use qualification. Sold-out display model identity is outside
scope; current stock, prices and availability still compare. Opening the inventory avoids the native
merchant-exit tutorial; skipping the merchant before opening inventory remains unqualified.
Saved audits rebuild facts from raw observations, validate current operands/delivery and preview
invariants, and accept reordered JSON object keys and independent read timestamps without losing
card ownership or snapshot binding. All failed harness, unsupported-popup, comparison and storage
attempts remain private. A 3.5-GB pre-copy guard prevents another partial-copy disk failure.

[Fresh rest and shop evidence](evidence/actual-engine-v0.111.0-fresh-rest-and-shop-v1.json) records
all exact identities, measured scopes, failed attempts and saved audits. No full-run attempts,
training admission or model promotion follow these fixture results. **1,071 repository tests,
88 standalone Node tests, four focused Host tutorial tests, formatting/types and the C# protocol
contract pass.**

## First shop batch assessment and next implementation

The owner explicitly authorized Codex to run and assess `scripts/compare-shop-actions-v1.sh`.
The configured two seeds × ordinary/Courier × two repeats remain **eight planned cases**, two
independent seeds and four seed/scenario pairs. The batch stopped on its first failed case:
**one passed, one failed, six unattempted**. Repeatability is not established. Batch/resource wall
time was **52.596/52.754 seconds**, CPU **21.256 seconds**. No resource cap was hit. The ordinary
first case passes an independent saved audit: nine observations, eight effect decisions, twelve
game/UI actions and one fresh potion tutorial. That audit launches no games.

The second case fails before a shipped-game launch. Courier replaces the first offer with
Whirlwind. The native offer calls its energy cost **0**; after purchase the deck correctly calls
it **X**. The card is present and deck size rises from two to three. Gold falls **961→904**,
exactly the 57-gold purchase quote. The checker expects the offer's definition/cost/upgraded tuple
to appear in the deck and rejects the inconsistent cost, reporting a missing card. The native
shop exporter uses numeric resolved energy cost, bypassing the `CostsX` display handling already
used elsewhere. This is a public-information export gap. It is distinct from the earlier gold
price/RNG repair.

The required repair uses the same game-owned X-cost display handling as deck and hand, keeps
free zero-cost cards distinct, and binds fresh source/build/config identities before repeating.
The completed repair and panel are recorded below. The failed batch/raw inputs/profiles are preserved; the
old helper displays its saved failure and never restarts it silently. No new long job or neural
training follows this assessment.

[Shop panel assessment](evidence/actual-engine-v0.111.0-shop-panel-v1.json) records the successful
audit, failed denominator, resource report and exact source gap. The earlier smoke/build evidence
remains immutable and keeps its original scope.

## Completed X-cost repair and repeated shop panel

The cumulative v10 MIT wrapper patch uses the existing `VisibleEnergyCost` helper for the current
shop card, preserving native `CostsX` and otherwise `GetAmountToSpend`, exactly as deck/hand exports
already do. Energy cost stays separate from the gold quote. It removes the numeric-only fallback
from the stats-preview exception handler; a failed cost read cannot invent zero. No card-ID table,
game rule, price/RNG change or comparison relaxation is introduced. The official stored game DLL,
shipped Host, SDK and semantic/saved verifiers remain unchanged.

Two fresh baseline and two repaired builds reproduce the new pinned identity in **15.147 seconds**.
New v10 native panels rerun **841 subchecks across 28 combat/rest/shop fixtures**, with 85 SDK
snapshots, 60 delivered actions and 34 refused invalid inputs. The exact failed Courier scenario
now passes ten observations, nine effect decisions and thirteen game/UI actions, including a fresh
potion tutorial; both the live Whirlwind offer and obtained deck retain X. Its shipped process takes
**36.032 seconds** and its independent raw saved audit passes.

Codex continued the same owner-authorized shop stage using a separately versioned recipe/result
folder. **8/8 cases pass, zero failures or unattempted cases**, across two independent seeds and
four seed/scenario pairs, each repeated twice. Repeated public prefixes are identical. The independent
saved audit reconstructs **76 observations, 68 effect decisions, 100 game/UI actions, 24 other UI
steps and eight fresh potion tutorial clicks**. It verifies exact frozen configuration/report/save
bindings, unique current operands, raw public facts, delivery receipts and preview/popup invariants
without launching games. Native atomic removal and shipped multi-step confirmation stay explicit.

Batch/resource wall time is **387.725/387.921 seconds**, CPU **140.186 seconds**; peak memory
**1.172 GB**, peak generated storage **2.462 GB**, final storage **57.533 MB**, four peak processes.
No resource cap is hit. Unknown rates/energy/GPU usage remain unknown costs. Verified successful
game payloads are removed after natural exit/integrity checks; profiles/logs/saves/reports and the
failed first batch remain preserved. Its one-pass/one-failure/six-unattempted denominator is never
combined with this new lineage's eight passing cases.

[V10 repair and panel evidence](evidence/actual-engine-v0.111.0-shop-energy-v10-and-panel-v2.json)
binds new patch/source/build/runtime/config identities and unchanged Host/SDK/verifiers.
**1,071 repository tests, 90 standalone Node tests, formatting/types and the C# protocol contract
pass.** The fixtures inject one Strike, 1,000 gold and two potion slots with/without Courier.
They do not qualify naturally reached shops, other relic/discount effects, preview stats, all
selectors, full-game endings or a learned player's strength. No full games, optimizer steps,
training admission or model promotion follow. The completed `compare-shop-actions-v2.sh` helper
only displays its saved result on rerun; no owner command is needed for this completed stage.

#145 remains open for the remaining rule/RNG-changing TestMode reviews and repairs, broader
rest/relic and shop interactions, full modifier/expiry/relic-counter facts, remaining selectors,
combat beyond the first turn, other public decisions, later acts and actual endings. #146 then
measures complete-run speed before connecting a separately versioned A8 neural lineage.

## Compiled mode inventory and first semantic review

`engine audit-mode-references` uses the repository's standalone metadata reader. It never loads
or executes the inspected game assembly. All **50,816 game method bodies / 1,457,929 IL
instructions** decode, with zero skipped bodies. The exact game contains **434 direct references**
to `TestMode` and `NonInteractiveMode`, across **383 normalized source-method groups**. The audited
v10 wrapper has **two direct references**, including mode enablement and its known price repair's
reflective type operand. Async state machines map to their owning source method; strings/comments
and token-shaped integer/switch operands do not become fabricated references.

The audit binds game/wrapper SHA/MVID, the completed private source extraction and full source
inventory, the inspector's compiled/source hashes and inspection runtime host. It rechecks archive,
source and candidate inputs. Complete reference rows and source stay private. The canonical audit
took **1.468 seconds** and launched no games. Its **24 initial method-group reviews cover 25
references**, leaving **409 references unreviewed**. Missing/stale/duplicate or unexplained reviews
are refused. This is complete enumeration of two exact mode types' direct IL references; reflection,
other aliases, Godot stubs and runtime equivalence are not exhaustively established.

Reviewed native source confirms two previously uncorrected reward changes: Calling Bell uses
preset relic rewards and Cauldron preset potion rewards in test mode. Their normal generated
rewards and RNG consumption needed restoration and comparison, completed in the v11 scope below.
**The bundle interpretation is corrected in review v2:** the original native test branch chooses
bundle one, but the wrapper already has a prefix for a pending player choice. Unconditional
first-bundle play was not established. Hook installation can fail as a warning, and missing
simulator or invalid-index paths fall back to bundle one; those require checks. Native selector
cleanup is conditional on test mode;
interrupt/reset behavior needs verification. Act selection bypasses the preference for undiscovered
alternative acts, so the initial-run content/discovery contract needs to be declared separately
from merely unlocking content. The existing reward-selector override and direct-versus-animation
Rolling Boulder damage dispatch are control/ordering seams needing targeted coverage. These latter
items are source findings, not measured live failures. The already repaired merchant potion-price
branch retains its v9/v10 scoped shop comparisons and is not another unresolved price defect.

[Mode audit evidence](evidence/actual-engine-v0.111.0-mode-audit-v1.json) binds the inventory/reviews
and lists limits. **1,083 repository tests**, the managed inspector's synthetic decoder/async/
literal/switch/truncation checks, formatting/types and the C# protocol contract pass. The new
inventory is a qualification/debugging artifact, never a policy/model input. Even fully reviewed
static coverage cannot admit training; no game, full-run attempt or optimizer step follows.
The original v1 evidence stays immutable; v2 records the corrected wrapper interpretation.

## Native reward repair and corrected mode review v2

The cumulative v11 MIT wrapper patch checks both exact original reward-method IL hashes before
interception. It replaces only each method-local `TestMode.IsOn` call with false. Original reward
constructors, population, relic/potion pools and RNG remain game-owned; global TestMode stays on.
Initialization is marked complete after the reward hooks install. Stored official game bytes,
existing selectors, shipped Host and SDK remain unchanged.

Two fresh baseline/two repaired builds reproduce in **13.832 seconds**, with a distinct
source/SHA/MVID. The separately pinned .NET 9.0.7 native checker passes **8/8 cases**, two seeds
× two relics × two repeats, using **24 disposable native fixture starts** in **19.046 seconds**.
Every case compares original-normal, legacy-test and repaired-test generation/population.
Initial complete RNG/pool state agrees; repaired rewards and final RNG/pool state match the
original-normal reference; original presets differ; repeats agree. The shared profile, archive,
candidate inventories, runtime, localization and checker remain unchanged.

This reference shares the wrapper's native initialization, stubs and population paths. It does
not test AfterObtained, curse delivery, reward claims, capacity, skip/cancel, nested pickup hooks
or shipped UI. No whole-run or shipped parity claim follows. New v11 combat/rest/shop regressions
pass **841 subchecks across 28 native fixtures**; previous shipped panels retain their own
v10/Host scope.

Mode audit v2 binds v11 and the corrected bundle-hook rationale, with **three wrapper mode
references**. The game inventory remains unchanged: 24 method groups/25 references reviewed,
**409 references unreviewed**. Static coverage still cannot qualify runtime fidelity or training.
**1,102 repository tests**, formatting/types, the standalone reward checker build and C# protocol
contract pass. Reconstruction metadata and limits:
[v11 repair and review v2 evidence](evidence/actual-engine-v0.111.0-reward-rng-v11-and-mode-review-v2.json).

At that stage, the next work was to qualify complete reward pickup/choices against the shipped game, verify existing bundle
hook installation/nonfirst choices/invalid rejection/reset and freeze the act-discovery profile
contract. No new long task or training follows automatically.

The remaining sections preserve earlier prerequisite packages and their scoped results.

## Completed first native prerequisite package

The repeatable `engine bootstrap-profile` command starts one unmodded shipped-game headless
process in a new disposable working copy and uses a fresh native profile. The depot's launcher
arrived with permission `0644`; the working copy alone changes it to `0755`. Its content hash,
all game rules DLLs and assets remain unchanged. The preserved source retains its original mode.

A small `override.cfg` beside the working executable selects a private save folder under
`~/Library/Application Support/SpireShift/engine-profiles`. Godot documents this exported-game
settings override; see [ProjectSettings](https://docs.godotengine.org/en/4.5/classes/class_projectsettings.html)
and its [4.5.1 loader](https://github.com/godotengine/godot/blob/4.5.1-stable/core/config/project_settings.cpp).
The game itself creates schema-8 settings, progress and preferences. The process keeps operating
system directory environment variables unchanged, disables Steam before platform initialization,
and has file-write restrictions over shared saves, Steam's managed directories and frozen archives.
This first unmodded boot also denies networking.

The canonical capped stage completed in **45.279 wall / 11.226 CPU seconds**; the native process
used **35.670 seconds**, exited naturally, and used the expected private save location. All eight
checks passed: native settings creation/schema, logged save path, Steam disabled, unchanged shared
saves, unchanged working payload, preserved archive integrity and natural exit. The shared save
sentinel covers 404 entries, including content, permissions and modification times. Every retry
gets a fresh attempt and profile; incomplete logs/markers stay private.

There were **1,090 error lines and two warnings**, including rendering/shutdown diagnostics.
They are retained rather than treated as clean runtime evidence. This is a **boot/profile pass**,
not a verdict about interactive menus, action completion, mechanics, full runs or model strength.
The earlier exploration's permission failure also remains recorded: the sandbox wrapper exited
before the game could start. Its old launcher-invocation count is not a completed game launch.

The separate `engine model-inventory` command verifies the frozen archive, pinned clean source
checkouts and local ILSpy launcher/command/decompiler fingerprints before targeted inspection.
It binds the game's generated `AbstractModelSubtypes.All` entries to exact declared types, checks
all indices/counts and refuses missing, duplicate or ambiguous entries. The command completed in
**3.821 wall / 2.808 CPU seconds** and resolved **all 1,660 types** with zero unresolved bindings.

The registry includes **603 card, 299 relic, 66 potion, 283 power, 98 encounter, 69 event, five act
and eight character type entries**, plus pools, monsters, enchantments and other families.
Those are declared type counts, including test and retired content; they are not counts of content
actually offered in normal play. In particular, eight character types are not eight selectable
heroes. The 65 mock/test/deprecated name or namespace hints are incomplete availability diagnostics.
Every offered-content flag stays unknown. This static registry is distinct from the lazily
instantiated live `ModelDb.All`, runtime effect properties and the reachable game state space.
No extracted inventory is a policy input. Raw inventories/decompiled sources remain under ignored
private artifacts; public evidence contains only counts, hashes and scoped conclusions.

The [native prerequisite evidence](evidence/actual-engine-v0.111.0-native-prerequisites-v1.json)
binds the configuration, archive, inspection, boot and resource reports. It includes the earlier
exploration and keeps zero full-run attempts, optimizer steps and training admission explicit.

## Completed shipped-game menu control

The pinned Connector Host **1.1.0-rc.1** and official SDK are installed only in a fresh disposable
copy of the frozen game. Release archives, SDK and validator dependency, embedded Host identity,
and exact-game runtime seal are fingerprinted. Downloads execute no npm lifecycle scripts.
The seal and this local result have **source-canary authority**, not broad mechanics certification.

The canonical check passes **all 13 gates in 30.355 wall / 9.543 CPU seconds**. The native process
uses **21.622 seconds** and exits normally. It verifies the loaded game/Host/modset, proves that the
launched process owns the loopback endpoint, reads a complete public menu, submits its advertised
start action, and observes a completed transition to character selection. Repeating the same
request is idempotent; submitting an old snapshot with a new request is rejected as stale.
Delivery alone never counts as a completed action. The transient shutdown secret stays in memory,
child environment and client stdin, outside command lines and saved files.

The private profile starts with only a copy of native settings, no progress, unlocks or saves.
Only mod consent and Early Access acknowledgement change, with a backup; the canonical native
settings template remains intact. A predeclared Host default configuration and the installation
form the working-copy baseline. Shared saves, Steam directories and frozen archives stay protected;
networking is restricted to local control. All 404 shared-save entries and the complete working
payload/archive remain unchanged. The check retains **1,090 error lines and two warnings**, so it
is a menu-control result, not a clean-runtime or gameplay verdict.

Two earlier attempts remain failed. The first used an unsupported sandbox IPv4 filter and did not
enter the game; its historical `games_launched` field counted the wrapper, not a native launch.
The second completed the action but correctly failed integrity when the Host created its default
configuration. The third starts a fresh copy with that exact file declared before inventorying;
it does not weaken the integrity check or rewrite earlier evidence.

## Historical upstream CLI binary mismatch

The faster managed candidate uses the headless project's exact **d11aa88** CLI baseline and pinned
v0.111.0 source patch. This is distinct from the preserved **084d1aa** comparison checkout. The
local build passes the exact source ledger and keeps both original and runtime game DLLs unchanged.
It compiled in a **9.165-wall / 4.945-CPU-second** capped stage, but its artifact differs from the
upstream frozen binary. The strict upstream audit rejected it, without launching gameplay.
The cause of that upstream difference remains unestablished. The separate local repair below
does not waive this old artifact pin or transfer the upstream binary's qualification.

Two initial source-ledger failures also remain preserved. Local Git's `apply --intent-to-add`
left an incomplete index. Initializing the index, applying the same patch, and marking its one
new file explicitly restores the exact ledger comparison; it adds no gameplay source changes.
Source/stub/lifecycle and public-observation behavior still need comparison with the shipped game.
The [menu/build evidence](evidence/actual-engine-v0.111.0-menu-control-v1.json) records fingerprints,
scoped results and failed attempts; all raw game files and source remain private.

## Completed private source extraction and first assessment

The owner explicitly authorized Codex to run this extraction. It completed successfully in
**18.621 wall / 141.328 CPU seconds**, with a **16.950-second tool process**, about **1.42 GB peak
resident memory**, and **18.74 MB of extracted source**. The single launched tool uses multiple
CPU threads. There were **3,537 C# files and one generated project**, empty stdout/stderr logs,
and zero matches for the known decompiler failure markers scanned. That scan is not proof that
every reconstructed method is perfect. The five extraction/integrity checks passed, and a fresh
source inventory matches the report. All **1,660 registered model types** bind uniquely to
extracted top-level source declarations, with zero missing or ambiguous bindings.

The first targeted static review found a concrete candidate transition discrepancy: the actual
rest-site synchronizer can preserve unchosen options after a successful action when a relic allows
it. The CLI candidate forces map presentation after nonselection rest actions and after a
rest-site card selection. That loses the opportunity to choose again. Repair and verify those
paths against native state, including cancelled/unsuccessful choices, before CLI learning.
That report records a source-level finding. The subsequent scoped native repair is recorded below.

The review also traces these requirements to actual-game implementations:

- Card costs combine per-copy local changes and global combat hooks, with separate expiration
  and X-cost rules. The candidate already calls the native spending-cost getter; it is not shown
  to use only printed costs. Complete public modifiers and timing behavior still need verification.
- Shop prices are dynamic; purchases may restock and update the inventory. Refresh visible prices,
  stock, capacity and legal actions after purchases and any selection they open.
- Card choices have minimum/maximum counts, cancellation and manual confirmation. Preserve those
  states rather than assuming every selection finishes after one card.

[Source assessment evidence](evidence/actual-engine-v0.111.0-source-assessment-v1.json) records
hashes, counts and scoped findings. Raw source and the full type-to-file bindings remain private
under ignored artifacts. The extraction covers the game rules assembly, not PCK localization/
assets, external assemblies or native engine code. The generated project was not compiled, and
no normal-play eligibility or exhaustive interaction/state-space proof is claimed.

There is **no pending extraction command**. The helper
`scripts/inspect-actual-engine-source-v1.sh` remains available for an explicit fresh extraction,
with the existing 20-minute tool / 22-minute outer cap. Its initial 5–15-minute estimate was
conservative; the observed first duration is now recorded. No game attempts, training, publication
or automatic next job ran. The owner exemption applies to this completed extraction; the usual
boundary for future long tasks remains unchanged.

## Reproducible local build and completed native rest repair

The new local build keeps both game DLL copies unchanged and pins its own source delta, compiler,
reference pack, stub, dependencies and binary SHA/MVID. Two fresh baseline builds reproduce the
earlier local `f15144…` artifact, and two fresh repaired builds agree on `4f660b…` /
MVID `7331d8d9-19aa-4e88-a116-b66a7f800f0d`. The capped build completes in **15.132 seconds**.
The compiler is SDK **10.0.401**, target reference pack **9.0.20**; native regressions run on
**.NET 10.0.12** with an explicitly fingerprinted Godot stub. This is a separate local candidate,
not the shipped Godot/.NET 9 execution environment or the upstream frozen binary.

A local clone initially omitted the upstream SourceLink metadata and produced another binary.
Restoring the real upstream origin URL reproduced the prior local binary in two fresh locations.
This explains that cache-clone difference, not the still-unknown upstream binary mismatch.
Failed attempts and all raw build/source evidence remain private and unchanged.

The MIT host [patch](../patches/engine/README.md) awaits the native rest choice, re-exports the
synchronizer's current remaining options, and exposes explicit Proceed after a successful choice
or when no options remain. Native map voting owns the subsequent room exit. Cancellation and
errors no longer fabricate map progress. Smith retains cancellation/manual confirmation even
with one eligible card, and invalid selection counts/indices are refused. Native relic obtain is
used only for marked privileged fixtures, so ownership and hooks actually participate.

The short `engine probe-cli-rest` check passes **all 75 native checks and five isolation/integrity
gates in 2.583 seconds**. Nine named Ironclad/A8 fixture bootstraps cover normal healing, Miniature
Tent in both orders, cancellation/retry, Girya's extra option, disabled Smith, single-card manual
confirmation, reset during a pending choice, stale references, and leaving with options remaining.
The loaded process/host/game/stub identities bind. Native travel exits the rest without hanging;
the process exits normally. All 404 shared-save entries, candidate files and the frozen archive
remain intact. The 130 retained diagnostic entries remain private; this is not a clean-runtime
claim. There are **zero full-run attempts and optimizer steps**, and training stays disallowed.

[Rest repair evidence](evidence/actual-engine-v0.111.0-cli-rest-repair-v1.json) binds the reports,
source and artifact identities. These are **managed native regressions**, not shipped cross-host
parity, complete mechanic coverage or evidence of model strength. That first report remains
immutable and predates the public projection package below. Legacy privileged relic list insertion
is not adopted as a valid fixture.

The canonical rest interface is now adapted with a separate, fingerprinted MIT projection hook.
Pinned upstream sources remain untouched; the hook applies only in a disposable copy. It binds
both current rest objects privately, exposes native remaining options/enablement and Proceed,
and includes native selection bounds, cancellation and manual confirmation. Single-card Smith
still offers explicit confirmation and cancellation. Empty confirmation is distinct from cancel.
Missing authority or unknown selection preferences produce an unavailable action menu.

The same nine fixtures pass through the actual canonical SDK and request ledger in **3.130 seconds**:
**226/226 checks plus seven integrity/isolation gates**, 20 rest and seven selection snapshots,
21 delivered actions and 21 deliberately invalid native inputs. Replaying a request returns its
saved receipt without executing again; a conflicting request id or stale snapshot is rejected
before native delivery. Native A8 is explicitly forwarded on every start/reset. All snapshots and
receipts validate; private native operands stay out of agent snapshots. These counts are checks
inside nine named scenarios, not 226 independent mechanics experiments.

[Projection evidence](evidence/actual-engine-v0.111.0-cli-rest-projection-v1.json) binds the unchanged
game/CLI build, hook, helpers and complete installed SDK/dependency inventory. The 130 diagnostic
entries remain private. There are no full-run attempts, training steps or training admission.
That historical package qualified Smith's cancellation/confirmation only. It does not establish
shipped-host parity. Its report and source pins remain unchanged.

The subsequent shop/selection package found **17 failed baseline shop checks**. The repaired host
uses the current native item and price as purchase operands, rejects purchases during a pending
selection, and restores the merchant's native one-use removal callback after successful completion.
Cancellation leaves the service, deck and gold intact. Potion purchase availability uses native
capacity and procurement hooks, including Sozu. Restocking receives a fresh item binding even when
the merchant entry object remains the same. Public inventory prices and card energy costs remain
distinct; native references and quoted purchase operands stay in private bindings.

Selection instances now have private bindings. Eight fixed native command boundaries observe
the actual `CardSelectorPrefs` without replacing their card effects or selection tasks. Prompt,
minimum/maximum, cancellation, manual confirmation and preview settings are exposed as public
facts. Smith and merchant removal both use the captured preferences, including single-card choices.
Commands without captured preferences remain unavailable. Eight installed observation hooks do
not mean eight independently tested selection mechanics; hand upgrades, choose-a-card/bundle,
mandatory/optional choices and large combinatorial selections still need qualification.

The game's Harmony version refused the installed **.NET 10.0.12** runtime. An official .NET 9.0.7
runtime was downloaded separately, verified against Microsoft's SHA-512 and bound by its complete
file inventory. The runtime version now matches the shipped game's declared runtime; Godot stubs,
TestMode and presentation differences still require shipped comparisons. The compiler remains
SDK 10.0.401 with the same 9.0.20 reference pack. The game DLLs, system runtime, frozen archive,
Steam installation and shared saves were not replaced.

The final host has two matching fresh baseline and two matching repaired builds in **29.405 seconds**.
The canonical rest panel passes **235 checks in 6.817 seconds**, and the shop panel passes
**179 checks in 4.533 seconds**; each also passes eight integrity/isolation gates. Across **16 named
fixtures**, 49 SDK snapshots have complete public metadata and action menus, 37 actions deliver,
and 30 deliberately invalid native inputs are rejected. Duplicate/stale/conflicting requests
execute no additional action. There are zero full-run attempts and optimizer steps. Training
remains disallowed. The initial runtime rejection, missing upgrade observation boundary and
incorrect raw-versus-visible prompt assertion remain recorded as failures.

[Shop/selection evidence](evidence/actual-engine-v0.111.0-selection-shop-v1.json) binds the final
build, runtime, hook, SDK and separate panel results. These are scoped managed native checks,
not shipped parity or exhaustive mechanics coverage. No owner command was pending at that stage.

The historical v3 package left current card costs/modifiers and effect ordering, status/counter/intent ownership,
other selectors, native shop discounts/relic purchase effects and out-of-combat potion controls.
The current package above addresses scoped combat/startup; shipped mechanics comparisons still precede learning.

Then qualify reset/seed behavior, actual A8 rules and terminal victory, complete public observations
and refreshed legal choices, and the targeted 25–30-scenario mechanics panel. Costs/modifiers,
status amounts, counters, secondary intents and repeated rest/shop/reward choices must stay attached
to their public owners. Add discovered omissions to the content-driven coverage matrix. This is
systematic coverage, not an exhaustive proof over every possible interaction.

Measure complete-run speed and failure rates after those gates. New learning has new engine/input/
data identities; v0.107.1 weights, encoders and experience are not silently migrated. Ironclad/A8
and terminal full-run victory remain fixed. Adaptive thinking waits for a useful base player.
Codex runs short capped checks; the owner launches and monitors stages expected to take five
minutes or more. This package has zero full-run attempts, optimizer steps or training admission.

## Historical acquisition helpers and developer reference

The first Steam-console request failed with **No connection**; the local content log reported
**Access Denied** with an empty branch. The owner then reported two **InvalidPassword** attempts.
Those failures remain evidence, with no credentials copied into SpireShift records. The subsequent
licensed download passed the unchanged game fingerprints. DepotDownloader owns its local .NET
authentication storage; SpireShift does not read Steam client credentials.

The pinned 3.4.0 source supports branch-specific manifest requests and interactive password/Steam
Guard or mobile QR authentication; see the
[pinned README](https://github.com/SteamRE/DepotDownloader/blob/c553ef4d60c00a4f5fd16c9fe017f569001589ff/README.md).
`scripts/acquire-headless-game-v0.111.0-v2.sh` remains a historical/reconstruction helper with a
one-hour cap and exact-manifest validation/resumption. It has no latest-beta or branch-switch
fallback. Its release-asset digests are observed fingerprints, not publisher-signed checksums.
The v1 console helper and `scripts/freeze-headless-game-v0.111.0-v1.sh` also remain available.

Identity commands are `engine preflight`, `engine freeze` and `engine verify-archive`; acquisition
commands are `engine download-command`, `engine download-plan` and terminal-only `engine download-game`.
The `engine bootstrap-profile` and `engine model-inventory` each take the unchanged identity
configuration and the separate `sts2-v0.111.0-native-bootstrap-v1.json` configuration. Output paths
are write-once. Native attempts are fresh, have private failure markers and do not reuse a cached
boot success. The game process has a 60-second cap plus bounded child-group cleanup, and registry
tool calls each have a 45-second cap. Actual canonical jobs also used the existing resource wrapper
with 240/180-second elapsed caps, explicit CPU/memory/storage limits and immutable reports.

The source/decompiler checks and file archive never admit a training backend. Profile bootstrap
is distinct from a supported GUI/offline launcher, and this check does not establish long-term
credential-independent playback. The older verified live-menu procedure remains in
[frozen-live-game.md](frozen-live-game.md).

`engine prepare-connector` verifies the pinned toolchain; `engine probe-connector-menu` performs
one capped native menu check. `engine build-cli-candidate` builds only, preserving rejected output;
`engine probe-cli-rest` performs the separate, short privileged rest regressions;
`engine inspect-game-source` performs the separate source extraction. They use their own
versioned configurations, write-once summaries and private attempt records. SDK/client gates also
have standalone Node tests; fixtures do not establish gameplay mechanics.
