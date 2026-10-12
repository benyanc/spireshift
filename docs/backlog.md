# SpireShift backlog

Updated 2026-10-11 after the native reward repair and corrected second mode review.
GitHub holds acceptance criteria and historical evidence. Codex may launch short builds, audits,
tests and jobs autonomously. The owner launches and monitors tasks expected to take five minutes
or more. Use saved timings and explicit caps.

## Current handoff and direction

**Current work: #145, actual-engine public inputs and mechanics qualification.** The separately
frozen v0.111.0 / `41cef1ea` game and #144 preservation are complete. Ironclad/A8 stays fixed;
full-run victory stays primary. Preserve all v0.107.1 archives, models, encoders and results.
[ADR 0005](decisions/0005-actual-engine-v0.111.0-qualification.md) orders public/mechanics
qualification, complete-run speed, then a separately versioned neural pilot. Emulator porting,
other difficulties and larger unchanged PPO/GA batches remain deferred.

**The owner startup panel passes: 12/12 cases, zero failures.** Six independent native A8 seeds
were imported through normal Continue twice each. Starting titles/availability match and repeated
choices are identical. The batch took 454.073 seconds; all case/config/report, save and snapshot
bindings were subsequently reverified from saved files without game attempts. Cost rates remain
unknown. This is a startup check, not player quality or full mechanics parity.

**First actual actions found and repaired a skipped Proceed step.** The reproducible v7 wrapper
now exposes the native finished-event Proceed button before opening the map. Native effects/map
voting and the official rules DLL remain unchanged. Its new binary has separate source, patch,
build and runtime identities. All **841 subchecks across 28 combat/rest/shop native fixtures**
were rerun on v7 and pass, with **85 SDK snapshots**, 60 delivered actions and 34 invalid inputs
refused. These privileged regressions are not training examples or shipped parity evidence.

**The owner first-combat panel passes: 8/8 cases, zero failures.** Two seeds, Winged Boots and
Dowsing Rod, each repeated twice: **two independent seeds and four seed/choice pairs**. The
60 compared observations, 52 gameplay actions and 24 tutorial steps were independently checked
against raw saved observations and delivery records without launching games. The batch took
406.247 seconds. Starting reward, Proceed, first combat, card plays, End Turn and the next hand/
enemy state agree within the frozen scope. Historical one-seed smoke results remain preserved.

Winged Boots and Dowsing Rod prefixes
match through Proceed, first combat, card plays, End Turn and the next hand/enemy state. Current
legal actions, costs, HP, energy, owned statuses, intents and pile counts match; incomplete/unknown
public fields fail. The three native tutorial buttons are separately counted and must leave the
underlying game facts unchanged. Shipped processes took 41.531 and 36.915 seconds. Effect text,
preview stats, relic counters, full map/pile information and later families/turns remain outside
this scope. Successful copies were removed after verification; all failures and private evidence
remain. [Current evidence](evidence/actual-engine-v0.111.0-starting-and-first-combat-v1.json) preserves
historical identities and results.

**Rest save loading repaired; two shipped rest comparisons pass.** The old wrapper used
`EnterAct` when loading a save, losing the saved room/history. The separately pinned combined
v8 patch uses the official saved-run entry sequence; the game DLL stays unchanged. Two fresh
baseline/two repaired builds reproduce in 16.160 seconds. All 841 combat/rest/shop subchecks
were rerun on v8 and pass. This does not qualify every saved-run resume state.

An explicit single-card/25-HP/Miniature Tent fixture heals, cancels/reopens Smith, upgrades and
uses Proceed. Healing reaches 49 HP; both action orders preserve the correct remaining choices
and upgraded-card flag. Seven observations and six effect decisions agree per smoke; the shipped
UI takes seven actions because selecting a card opens a separate confirmation preview. That
extra step is recorded and checked for unchanged game facts before committing. The two shipped
processes took 55.886 and 51.425 seconds. This is injected mechanics evidence, not natural room
reach or player quality. The fresh rest tutorial is unsupported by the released Host; the test
uses isolated native-generated progress that has seen only that tutorial. Other tutorials remain
enabled, and its source profile/report/copy are bound and verified. Unknown controls and stale
actions remain failures. [New evidence](evidence/actual-engine-v0.111.0-first-combat-and-rest-v1.json)
records these scopes, repairs and preserved failures.

**The owner rest panel passes: 8/8 cases, zero failures or unattempted cases.** Two independent
seeds, both action orders, each repeated twice. Its 383.715-second batch and 383.922 wall /
133.795 CPU-second resource record remain separate. A pure saved-data audit verifies
**56 observations, 48 rest decisions, 56 game/UI actions and eight upgrade preview steps**.
It checks current action operands, delivery, cancellation, preview invariants, healing/upgrades,
save/report/config bindings and repeated prefixes without launching games. This historical panel
used the isolated already-seen rest tutorial baseline; it does not qualify fresh-profile control.

**The fresh rest tutorial now works in two short shipped checks.** A separate MIT Connector Host
patch exposes only the exact current rest popup's visible confirmation button. Unknown popups
stay unsupported. Two fresh builds reproduce the separately pinned binary in 7.711 seconds;
the game DLL, original Host and original seal stay untouched. Each settings-only profile has
no copied tutorial progress. Both rest orders pass popup dismissal, unchanged underlying facts,
heal/cancel/reopen/upgrade/Proceed; the shipped processes take **36.164 and 35.118 seconds**.
Independent raw audits pass both cases. These are privileged single-card fixtures, not naturally
reached rooms, a full-game test or training admission. The changed Host needs its own subsequent
startup/combat regression evidence; old Host results do not qualify the new binary automatically.
[Current evidence](evidence/actual-engine-v0.111.0-rest-panel-and-tutorial-v1.json) preserves all
historical identities, failed attempts and new scopes.

**The owner fresh-profile rest panel passes: 8/8, no failures or unattempted cases.** Two independent
seeds and four seed/order pairs, each repeated twice. All eight fresh popups were clicked with
no copied tutorial progress. The saved audit checks **56 observations, 48 rest decisions,
56 game/UI actions, eight upgrade previews and eight popup clicks** without new games.
Batch/resource wall time is **428.762/428.978 seconds**, CPU **149.838 seconds**. Repeated native
prefixes match. This qualifies the named injected fixture, not full runs or model strength.
Two targeted startup/combat checks also pass on that rest-patched Host; they are not a new repeated panel.

**Shop comparisons found a rules-relevant TestMode shortcut.** The v8 managed wrapper omitted
the game's random potion-price adjustment and its RNG calls. The combined v9 MIT wrapper patch
restores the original calculation for that method alone; the official DLL's stored bytes and
global TestMode setting stay unchanged. Two baseline/two repaired builds reproduce. V9's 28
native fixtures again pass all **841 subchecks**. Audit other rule/RNG-changing TestMode branches
under #145; passing a local build does not establish complete rules fidelity.

**Two short shipped shop sequences pass and their raw saved audits pass.** Ordinary purchases
and Courier restocking agree on all current stock/prices, legal menus, gold, deck and occupied
potion slots through purchases, full potion capacity, cancel/reopen/confirm removal and map exit.
There are **19 compared observations, 17 effect decisions and 25 shipped game/UI actions** total,
including two first-potion tutorial clicks. The new cumulative MIT Host patch adds only the exact
obtain-potion confirmation and keeps rest support. Single-card removal selects directly into a
preview, then confirms; it does not need a separate Open-preview control. Full raw menus and
all failed attempts remain private. Saved comparison handles object-key reordering and independent
read timestamps while preserving state/action/read bindings. The cumulative Host/native-v9 pair
also passes its own fresh rest and first-combat regressions and saved audits. These are finite
checks, not transferred repeat-panel results. **1,071 repository tests, 88 standalone Node tests,
four focused Host tutorial tests, formatting/types and the C# protocol contract pass.**

**The first repeated shop batch stopped: one pass, one failure, six unattempted cases.** The owner
explicitly authorized Codex to run and assess this otherwise owner-launched stage. It took
**52.596 batch / 52.754 resource wall seconds**, with **21.256 CPU seconds**. The first ordinary
case passes its independent saved audit: nine observations, eight effect decisions, twelve
game/UI actions and one fresh potion tutorial. The next Courier case fails in native effect
checking before the shipped game is launched; repeatability is not established.

The bought Whirlwind is present, deck size rises from two to three and its 57-gold quote is charged
correctly (961→904). The native shop exports its energy cost as **0**, while the deck correctly
exports **X**. The effect checker therefore reports a missing purchased card despite its presence.
The native shop exporter uses numeric resolved energy cost without the `CostsX` handling already
used for deck/hand observations. This is a public-information export defect, not a failed purchase.
All results/inputs remain preserved. The old script now displays its failed result; do not rerun
it expecting new comparisons.

The first batch identified the need for native X-cost display handling in shop offers,
retaining X as distinct from a free zero-cost card. Its source/build/config lineage and failed
results remain immutable; the repair and repeat panel below are separate.
[Shop panel assessment](evidence/actual-engine-v0.111.0-shop-panel-v1.json) records the denominator,
saved audit and exact cause; [earlier evidence](evidence/actual-engine-v0.111.0-fresh-rest-and-shop-v1.json)
retains the successful prior smokes and reconstruction metadata. No full runs or training follow.

**The X-cost repair and new repeated shop panel now pass.** The cumulative v10 MIT wrapper uses
the existing game-owned cost display helper used by deck/hand. It neither infers X from card IDs
nor changes game rules, prices/RNG or comparison tolerances. The energy-cost read is outside the
unrelated stats-preview exception fallback, so an error cannot invent a free zero-cost card.
Two baseline/two repaired builds reproduce in **15.147 seconds**. Its own 28 privileged native
fixtures pass **841 subchecks**. The previously failing Courier case passes ten native/shipped
observations and its raw saved audit; the shipped process takes **36.032 seconds**.

The owner-authorized same shop stage was repeated in a new v2 folder: **8/8 completed, zero failed
or unattempted, identical repeated prefixes**, two independent seeds/four scenario pairs repeated
twice. Independent saved auditing verifies **76 observations, 68 effect decisions, 100 game/UI
actions, 24 other UI steps and eight fresh potion tutorial clicks**, with no games launched by
the audit. Batch/resource wall time is **387.725/387.921 seconds**, CPU **140.186 seconds**;
peak memory/storage are **1.172/2.462 GB**. No cap was hit; cost rates remain unknown.
The failed v1 denominator stays separate. The unchanged Host/SDK and semantic verifiers retain
their original identities; new native source/build/config pins bind this panel.

[V10 repair and panel evidence](evidence/actual-engine-v0.111.0-shop-energy-v10-and-panel-v2.json)
records all reconstruction metadata and scopes. **1,071 repository tests, 90 standalone Node
tests, formatting/types and the C# protocol contract pass.** These are privileged finite shop
fixtures, not naturally reached shops, full-game qualification or model-strength results.
The completed v2 helper only displays saved results when run again. No new long stage, full
games or neural training follow automatically.

**The repeatable compiled mode inventory is implemented.** It reads metadata/IL without loading
or executing game code, covering all **50,816 game method bodies / 1,457,929 instructions**, with
zero undecoded bodies. There are **434 direct references** to `TestMode` and its
`NonInteractiveMode` alias in **383 source-method groups**. The audited v10 wrapper has two
direct references. The separate private source extraction, game/wrapper SHA/MVID, inspector
binary/source and local inspection runtime host are bound. The audit took **1.468 seconds**,
launched no games and preserves all raw source/reference rows under ignored artifacts.

This is complete direct-reference enumeration, **not a completed semantic or fidelity audit**.
The first **24 method-group reviews cover 25 references; 409 references remain unreviewed**.
Reviews bind the actual method IL hashes and need an explicit rationale. Unknown/changed rows
stay visible; neither a complete inventory nor a fully reviewed static list can admit training.
Reflection, other aliases, Godot stub behavior and runtime differences remain outside this scan.

The original native test branch returns **preset Calling Bell relics and Cauldron potions**,
replacing normal generated rewards/RNG paths. The bundle branch also defaults to bundle one,
but the wrapper already has a prefix that presents a choice. **Correction to the first review:**
unconditional first-bundle play was not established. Warning-only hook installation and
missing-simulator/invalid-index fallbacks still need explicit checks. Conditional selector cleanup
and an act-selection preference change when alternative acts remain undiscovered. Fully
unlocked content does not define act discovery. Reward selection is an existing wrapper control
seam; multiple rewards/capacity/cancel still need coverage. Rolling Boulder changes damage
dispatch from visual-hit callbacks to a batch; damage/death hook ordering needs a comparison.
The known potion-price branch is already restored by v9/v10 and retains its separate shop evidence;
it is not counted as another unfixed price bug.

**V11 restores the two normal reward-generation branches.** It checks exact method IL hashes
before replacing only their local test-mode predicates; game-owned constructors, population,
RNG and pools remain unchanged. Two fresh baseline/two repaired outputs reproduce in
**13.832 seconds**. A new bounded comparison passes **8/8 cases across two seeds/four pairs
repeated twice**, using **24 disposable native fixture starts**. It compares the original-normal,
legacy-test and repaired-test paths: starting RNG/pools match; generated rewards and complete
final RNG/pool state match the original-normal reference; old presets differ; repeats agree.
This takes **19.046 seconds** and does not test pickup, curse delivery, capacity, choices or UI.
The new v11 combat/rest/shop regressions also pass **841 subchecks across 28 native fixtures**.

The separately versioned **mode review v2** binds v11 and corrects the bundle-hook interpretation.
The game inventory and **409 unreviewed references** stay unchanged; v11 has three direct mode
references. **1,102 repository tests**, formatting/types, the standalone reward checker build
and C# protocol contract pass. No shipped v11 parity, full-run win, training admission or model
promotion follows. Previous shipped panels retain their own v10/Host scope. Details:
[reward repair and corrected review evidence](evidence/actual-engine-v0.111.0-reward-rng-v11-and-mode-review-v2.json).

**V12 bundle choice repair and short checks pass.** Hook installation now checks the exact native
method and fails explicitly. Current player/selection/pack bindings reject malformed, stale and
duplicate commands; no invalid input becomes pack one. Native reservation, synchronization and
logging precede task completion. Cleanup cancels the pending task and clears bindings.

Eight seed/pack/repeat cases pass with **12 native starts, 34 public SDK snapshots, 22 delivered
actions and 64 refused invalid inputs**. A separate synchronization fixture passes **58 subchecks
across four starts/two seeds**, including callback ownership, overlap, cancellation and missing
simulator behavior. V12's combat/rest/shop and reward-generation regressions also pass under new
identities. One natural Scroll Boxes shipped comparison passes second-pack selection,
preview/cancel/reopen/confirm and exact deck award: **three observations, two semantic decisions,
five game/UI actions**, in **31.915 shipped-process seconds**. Saved raw reconstruction passes
and rejects five intentionally corrupted action/source/runtime/award records without games.

Earlier helper-binding, public-role, serialization-order and low-space failures remain preserved.
Canonical multiset comparison keeps all card values/duplicates; JSON key order cannot invent a
game mismatch. Large private disposable assets now use independent APFS clones when available,
with ordinary-copy fallback and unchanged full inventory validation. No hard links are used.
Details: [v12 evidence](evidence/actual-engine-v0.111.0-bundle-choice-v12.json).

**The original bundle UI batch was blocked before any case:** v1 has zero completed/failed
cases and eight unattempted cases because its free-space guard stopped it. Its saved failure and
resource report remain immutable. Rerunning v1 displays that failure rather than restarting.

**Storage/reuse work under [#147](https://github.com/benyanc/spireshift/issues/147):** future serial
qualification uses one locked working app, bound to the unchanged frozen master. Every attempt
gets a fresh small profile and immutable evidence; app-local connector/settings additions are
removed after verified child exit, then the complete original file inventory is checked. Interrupted
setup or unknown mutation leaves that one worker blocked; another full app is not silently made
on retry. The managed pool is capped at two apps / 5 GB, with a read-only inventory covering both
managed workers and other existing `game` directories. It never deletes historical copies.

**Short real reuse checks pass:** two different A8 seeds/pack choices use the same app path and
inode, distinct profiles, and one total app copy. Both return to the frozen baseline and pass raw
saved-evidence checks. A separate short native startup passes using that same app. Parallel isolation/throughput and deliberate blocked-worker repair/retirement
remain later work; old recipes keep their original identities and retention policy.

**Next under #145:** the owner runs `scripts/compare-bundle-actions-v3.sh`. The same eight-case
natural Scroll Boxes panel now explicitly binds the reuse policy and uses a new workspace
(two seeds × both packs × two repeats, approximately 6–9 minutes; 15-minute cap). Resource tracking
includes the persistent app pool. The complete v3 panel has not started; v1's zero-case space failure
and the prepared v2 copy-per-case recipe remain preserved. The script verifies saved evidence after
success without game replay. Details: [working app reuse](working-app-reuse.md).
Then qualify full Calling Bell/Cauldron pickup and reward
choices against the shipped game and freeze the content-plus-act-discovery contract. Continue
the remaining mode reviews alongside encountered mechanics coverage. Broader rest/relic options,
full public effects and remaining decision coverage follow. Remaining work includes
full modifier/expiry/relic-counter facts, combat beyond the first turn,
remaining reward/selection families and large choice spaces, out-of-combat potions, native relic
purchases/discount interactions, skipping a merchant before opening its inventory, other public
decisions, later acts and actual endings. Inventory coverage is not exhaustive reachable-state
coverage. The new Host's finite prior-family checks remain separate from historical repeat panels.

[Mode audit evidence](evidence/actual-engine-v0.111.0-mode-audit-v1.json) records the exact scope,
findings and incomplete review denominator. **1,083 repository tests**, the inspector's synthetic
IL/async/string/switch/truncation checks, formatting/types and C# protocol contract pass. No long
stage, training or game launch follows this static audit. Both #145 and #146 remain open.

#146 then measures complete-run speed/failures at one worker before bounded parallel workers,
versions a new actual-engine public encoder/model/experience lineage and connects existing
neural/PPO machinery. Useful independent A8 full-run gains remain the aim. Adaptive budgets
stay behind foundation readiness. No larger PPO/GA, difficulty change or controller follows
automatically. Changes stay local; no push/PR/Actions run is required.

## Preserved v0.107.1 direction and evidence

**Historical prepared stage, now deferred:** [test learning with repaired public inputs](full-run-relational-a8-v3.md).
The v2 encoder pooled each list item's identity and numeric properties independently. It cannot
separate **2 Strength / 7 Dexterity** from **7 Strength / 2 Dexterity**, nor a swap of counters
between two relics. This is an exact information-loss counterexample, not a measured explanation
of every previous defeat. A separately versioned v3 encoder binds properties to their public
owners, including card upgrade/enchantment descriptors. Both actor and bootstrap critic use it.
It retains the same **256 inputs, 16 tanh units and 4,384 actor parameters**, public legal choices,
PPO algebra and terminal-victory/auxiliary score contracts. Historical sources and results remain
unchanged; new models and experience cannot silently load the old format.

The [bounded input audit](evidence/public-a8-entity-bound-input-repair-v3.json) checks 189 states
from four saved **training** runs, verifies all candidate bindings, and distinguishes both swaps.
The repaired actual network learns two opposite synthetic preferences to **98.37% / 98.42%**
correct-action probability after 250 short synthetic updates. Identical old inputs impose a 50%
mean expected success ceiling on that particular balanced task. These are artificial learning
controls, not optimal-gameplay labels, wins or model promotion. The sample also observes hard
feature clipping and hidden-unit saturation; their effect on game strength is not established.

The [tiny actual-simulator check](evidence/public-a8-relational-pipeline-v3.json) completes
**14 attempts / 2,125 public decisions / 10 optimizer steps in 26.676 wall / 31.289 CPU seconds**,
with no failed attempts and no full wins. All 14 saved traces and 305 sampled decisions verify.
Its two development pairs are integration evidence only, and their seeds are excluded from the
owner stage. The initial summary-printing failure is preserved separately. All **897 repository
tests**, formatting/type checks and the C# protocol build pass;
[verification evidence](evidence/public-a8-entity-bound-verification-v3.json) records the short check.

The next owner recipe has at most **eight rounds of 128 sampled games / 1,920 attempts**,
including separate 128-seed train confirmations every two rounds and a frozen paired 128-seed
independent development comparison. It excludes earlier declared/inspected seeds and the tiny
pipeline check. Each round shows wins, average floor, best game and failures. The whole stage
has one **60-minute elapsed / 12,000-CPU-second budget**, 12 GB memory and 4 GB artifacts;
explicit resumption subtracts previous launch costs. There is no automatic next job, deployment
promotion, adaptive controller or final-test opening. A real independent gain is still required.
The guide contains **one specific owner command**.

The owner completed the earlier PPO-seeded GA: **16 generations, 5,248 actual attempts and
757,944 public decisions in 1,987.806 wall / 8,628.793 CPU seconds**. There were zero full wins.
The selected player is **exactly the original initializer**, not a new successful mutation.
On 128 fresh development seeds, PPO reaches mean floor **12.125** and clears Act 1 twice;
the selected initializer reaches **11.296875** and clears Act 1 four times. No repeated useful
improvement is demonstrated. Across the stage, 22 liveness failures and four unsupported runs
remain counted. The [owner outcome assessment](evidence/public-a8-actor-evolution-owner-v1-assessment.json)
preserves the negative result; selected-versus-initializer is a self-comparison. #139's follow-up
fine-tuning/alternation is deferred, and #140's matched-total-cost methods experiment remains open.

The preceding PPO v2's **32 rounds, 5,504 attempts, 659,118 decisions and 14,696 optimizer steps**
selected round 24. Its original 128-seed development result remains inconclusive: **11.6641 /
11.9922 mean floor, three / two first-act clears, zero wins**, approximate paired auxiliary 95%
interval **−0.65 to +1.31 floors**. The two launches cost 5,938.579 wall / 11,625.372 CPU seconds.
All development pairs completed normally; 16 liveness failures and one unsupported training
attempt remain counted. The [original assessment](evidence/public-a8-ppo-pilot-v2-assessment.json)
is preserved. More unchanged PPO or GA batches are not the next step.

The repaired simulator remains admitted for scoped policy learning, with coverage limitations
in [ADR 0004](decisions/0004-scoped-a8-simulator-learning.md) and
[admission evidence](evidence/public-a8-policy-admission-v2.json). #141 retains empirical later-act
UI parity and broader mechanics; neither a clean pipeline nor simulator learning establishes
complete live-game fidelity. Foundation #78 remains unready. Keep adaptive thinking behind #5;
selectable ascensions stay deferred under #142.

The history below remains bound to its original engines, schemas and experiments. The current
handoff above supersedes earlier repair-before-training instructions.

The owner completed 832 unified evolution attempts in 80.858 elapsed / 592.289 total CPU seconds.
Both players have zero full wins on 64 paired development seeds. The evolved player reaches mean
floor 9.46875 versus 11.0 initially, with 12 versus 8 failed attempts. No model is promoted.
[The diagnosis](full-run-pilot-v1-diagnosis.md) identifies premature Act 2 endings around floor 19,
stale combat-win flags, truncated public selections, a fourth reward encoding defect and an invalid
Ascension-0 label. The full-run guard correctly refused the premature wins. These defects block
more sustained learning and prevent a valid A0/full-game claim; larger training is not the next step.

[#141](https://github.com/benyanc/spireshift/issues/141) owns the repairs. The owner successfully
published the separate ending/reward candidate in 10.284 seconds; all nine targeted regressions
passed. The earlier missing-runtime failure and cached check remain preserved in
[runtime evidence](evidence/full-run-repair-runtime-check-v1.json). The owner then published the
public-choice candidate in 9.588 seconds with all 23 native synthetic regressions passing and its
actual public-list exports checked. It exposes every offered combat card, correct pile/generated
card identities, selected bundle and confirmation state, plus a source declaration of fixed A8.
The new versioned adapter and unified player consume these readouts, retaining every legal choice
and normal enemy targeting. Its fresh 4,384-parameter model can change every decision family.
Two short real native replays passed the previously reproduced fourth-reward and overflow-menu
errors: 410 transitions and 412 scored observations in 3.387 seconds, with no optimizer steps.
[Integration evidence](evidence/public-choice-integration-v2-evidence.json) preserves build, model,
adapter, configuration and replay identities. This is compatibility evidence, not playing strength
or real-game parity. The owner subsequently checked all 89 failed training attempts in 92.495 wall
/ 91.416 CPU seconds, replaying 11,947 transitions. **85 passed; four remain failed.** The successful
endpoints cover 65 overflow menus, seven premature endings, 12 bundle confirmations and one reward.

All four remaining cases stalled at Dense Vegetation or Punch Off: an unconditional fallback
offered action 3 on a committed fight page, while its handler accepts only action 0. Existing event
tests inspected slots 0–2 and missed this extra action. A third isolated source correction offers
only the accepted continuation on those pages and the matching Lantern Key page. All 32 targeted
managed regressions passed in 6.753 seconds, including nine new full-mask/progress/resource checks.
[Event repair evidence](evidence/event-continuation-repair-v1-evidence.json) retains the owner's
85/89 failed audit and the initial short-check compile failure as separate records. The corrected
native library subsequently published in 7.393 wall / 8.581 CPU seconds with all 32 tests passing.
Codex derived its separate public-adapter manifest and completed a new audit under a four-minute
cap: **89/89 passed**, 11,939 transitions, 89.677 wall / 88.861 CPU seconds. The four event cases
replay the exact saved prefix to the first rejected action, verify the removed button, then score
and execute the engine's sole continuation into the correct playable fight. Their 12 historical
noops are explicitly recorded as replaced; other action drift fails. All 89 original attempts
remain in the denominator, and the old 85/89 result is unchanged.
[Native integration evidence](evidence/event-native-integration-v1-evidence.json) preserves the
new native, public adapter, fresh model, original cases, audit and resource identities. Real-game
difficulty, endings and broader event-action conformance, plus re-admission, remain before learning.
The new native/adapter also passes all ten environment interface checks in a 0.825-second job.
[Interface/reference evidence](evidence/event-native-contract-v1-evidence.json) preserves that
result and its initial reporting failure. Existing real-game captures show initial options 0 and 1
at the three repaired events, while the current source still offers an extra skip there. All 32
saved full-run reference traces observe Act 1 only. These are concrete remaining action-parity
and later-act evidence gaps; passing the 89 inspected prefixes does not settle them.
Those remaining captured event-choice differences are now repaired in a fourth isolated candidate.
It removes the invented fallback skip and rejects locked or nonexistent event choices before
changing state. **All 109 captured choice lists match**: 52 initial screens and 57 settled later
event screens. The full mask is compared; genuine Leave choices remain. The one unsettled Dense
Vegetation page is explicitly excluded from settled-mask comparison, and other screen types and
uncaptured events are not presented as new coverage.

The final candidate published in 17.641 seconds with all 240 targeted checks passing, including
99 captured outcomes and the prior 32 regressions. The complete native suite passed **4,942 tests**
with one optional timing probe skipped in 54.545 seconds. Ten public interface checks also passed.
A fresh untrained player completed eight training-seed attempts without crashes or stalls in
7.687 seconds; all eight lost. Zero optimizer steps, no admission or promoted model followed.
[Event choice evidence](evidence/event-choice-repair-v1-evidence.json) preserves these results and
all failed build, stale-assertion and preflight attempts. The old 89/89 replay result remains bound
to its earlier candidate; it is not reassigned to the changed initial choices.

A short audit of the preserved game assembly confirms that earlier bosses advance to the next
act and that total floor is distinct from current-act progress. It also identifies the real UI's
forced Architect dialogue after the last boss; the simulator collapses this closing sequence.
Each settled dialogue page has one continuation, so this adds UI steps without a strategic choice.
The assembly confirms A8 activates harder rules and that Double Boss begins at A10, not A8.
[Frozen-rule evidence](evidence/frozen-run-rule-audit-v1-evidence.json) records the private extracted
type hashes and source findings. It does not establish full A8 fidelity or add empirical Act 2/3
captures. The owner chose **fixed A8** for the next learning workflow. Selectable A0 and other
difficulties are deferred under [#142](https://github.com/benyanc/spireshift/issues/142); they do
not block A8 learning. Relabelling A8 would not implement A0. The original evidence snapshot's A0
recommendation is historical and is superseded by [ADR 0003](decisions/0003-fixed-a8-learning-priority.md).

All original engine binaries, results, recipes and failed cases are preserved; final test is sealed.

[#136](https://github.com/benyanc/spireshift/issues/136) supplies the versioned training score.
[#137](https://github.com/benyanc/spireshift/issues/137) now supplies a standalone whole-run neural
player with 4,384 mutable parameters and public candidate binding. [#138](https://github.com/benyanc/spireshift/issues/138)
has complete-run experience recording, separate train/development indices and saved-input checks.
The first direct neural-weight evolution pilot under [#135](https://github.com/benyanc/spireshift/issues/135)
has completed its owner pilot with rotating common training panels, independent elite confirmation
and a final 64-seed development comparison. That is infrastructure/negative evidence, not a
competent player, matched cross-method result or foundation readiness.

**Historical v0.107.1 priority, superseded by ADR 0005:** prove a useful learning loop on **Ironclad / A8**, using the repaired public
player and truthfully declared rules. Difficulty is decided; there is no A0 implementation prerequisite.
The new scoped admission and A8 PPO recipe are ready. The next owner stage collects complete
runs, updates all policy components, and compares the frozen player with its initializer on
independent development seeds. Broader live-game parity remains separate work under #141/#37;
neither old teacher imitation nor a larger population alone establishes a useful learning method.
Stop or revise a method if independent progress stalls.
Wins remain primary; intermediate act/floor gains support development without claiming competence.
The historical A0-labelled score/runner and its population remain preserved; the new path must bind
its actual A8 scope, public-model version, corrected native identity and new experience lineage.
No completed check needs rerunning. Codex handles short jobs; any stage expected to take five
minutes or more gets one specific owner command when it is ready. Additional ascension support
is later work after a useful A8 player, unless the owner explicitly changes priority.

Earlier foundation evidence remains: the separately versioned [neural discard-choice comparison](neural-selection-repair.md)
had 32 normal terminal losses per player, zero wins/first-boss reaches/Act 1 clears, mean floor
6.84375 each and 27 changed traces without demonstrated gain. This is inspected-seed compatibility
evidence, not a fresh/final benchmark. Historical base-v2 remains accepted; base-v11 is unpromoted.
Comparison: `sha256:2bc12a35ee21e5ac285424cab8e19bcb236bb650c88d51aaa9d91e7ea8843ce6`.
Resources: `sha256:c8e246e7455f5df0913bc55d6585b694643aba26eabcf5186004c76f9947786d`.

Build a player that wins complete runs, then teach it when to spend little, medium or substantial
thinking effort. The primary evaluation objective remains **terminal full-run victory probability
under a fixed whole-run computation budget**. [ADR 0002](decisions/0002-full-run-bootstrap-training.md)
explicitly declares auxiliary learner returns for new bootstrap experiments, separate from the
real win/loss result. A strong inexpensive base player remains the foundation.

New experimental recipes may learn all policy components and depart substantially from weak
base-v2. Strategic learning no longer waits for combat-only improvement. Old saved lessons are
optional warm starts rather than permanent behavior targets. Legal/public-input checks,
independent evaluation, numerical stability and historical evidence preservation remain.

## Ordered implementation work

| Order | Work | GitHub items |
| --- | --- | --- |
| Complete; exact download/archive independently verified | Preserve and preflight the v0.111.0 actual-game copy and pinned sources. Keep old v0.107.1 artifacts immutable; file identity alone does not admit gameplay. | [#144](https://github.com/benyanc/spireshift/issues/144), parent [#37](https://github.com/benyanc/spireshift/issues/37) |
| Current; fixed app reuse and short checks implemented | Reuse one protected working app, fresh profiles, ownership/reset checks and a global storage cap; qualify the repeated v3 panel. Parallel reuse follows under #146. | [#147](https://github.com/benyanc/spireshift/issues/147), [#145](https://github.com/benyanc/spireshift/issues/145), [#146](https://github.com/benyanc/spireshift/issues/146) |
| Current; reward generation and bundle choice repaired; 409 mode references pending | Run the v3 bundle UI panel using the fixed working app; qualify full reward pickup/choices; freeze act discovery, then continue mode/mechanics coverage. Earlier shipped panels retain their original scope. | [#145](https://github.com/benyanc/spireshift/issues/145), [#141](https://github.com/benyanc/spireshift/issues/141), [#143](https://github.com/benyanc/spireshift/issues/143) |
| After mechanics qualification | Benchmark actual-engine full-run speed/failures at one and bounded parallel workers, integrate a new public engine/encoder/experience lineage with existing neural/PPO machinery, and prepare a finite owner A8 learning pilot. | [#146](https://github.com/benyanc/spireshift/issues/146), [#35](https://github.com/benyanc/spireshift/issues/35), [#78](https://github.com/benyanc/spireshift/issues/78) |
| Scoped learning admission complete; broader parity open | Repaired A8 source/native/public adapter admitted with all captured evidence and explicit limitations. Empirical Act 2/3 UI parity and complete mechanic fidelity remain before exact/live claims. | [#141](https://github.com/benyanc/spireshift/issues/141), [#37](https://github.com/benyanc/spireshift/issues/37) |
| Implemented | Versioned bounded bootstrap score, win-first population ranking, failures/caps and terminal-only staging rules. | [#136](https://github.com/benyanc/spireshift/issues/136) |
| Implemented | Unified compact full-run neural policy, public features, legal candidate scoring and deterministic genome/gradients. | [#137](https://github.com/benyanc/spireshift/issues/137), parent [#78](https://github.com/benyanc/spireshift/issues/78), iteration [#134](https://github.com/benyanc/spireshift/issues/134) |
| Implemented; owner pilot saved | Complete-run public experience, actual returns, milestones, lineage, immutable split-specific indices and verification; original failures remain represented. | [#138](https://github.com/benyanc/spireshift/issues/138) |
| Completed owner PPO; inconclusive improvement | Preserve 32-round PPO v2 and its complete independent comparison; no larger PPO launch is automatic. The earlier evolution pilot remains negative/compatibility-compromised. | [#35](https://github.com/benyanc/spireshift/issues/35), [#135](https://github.com/benyanc/spireshift/issues/135) |
| Input repair implemented; large emulator pilot deferred | Retain the entity-bound v3 encoder and synthetic/short pipeline checks. Carry the relational design into qualified actual-engine inputs before another large run; review credit assignment/capacity if learning stalls. | [#143](https://github.com/benyanc/spireshift/issues/143), [#78](https://github.com/benyanc/spireshift/issues/78), [#35](https://github.com/benyanc/spireshift/issues/35) |
| Completed owner hybrid; negative result | Preserve the 16-generation result, all costs/failures and initializer self-comparison. No larger unchanged GA or automatic fine-tuning follows. | [#139](https://github.com/benyanc/spireshift/issues/139), [#140](https://github.com/benyanc/spireshift/issues/140) |
| Later; after a useful repaired-input learner | Freeze genuinely matched total costs and terminal-only reference before cross-method superiority claims. Existing incremental hybrid evidence is not that comparison. | [#140](https://github.com/benyanc/spireshift/issues/140) |
| Deferred; current hybrid did not help | Preserve originals; revisit neural fine-tuning/alternation only when evolution produces a useful independent gain. | [#139](https://github.com/benyanc/spireshift/issues/139) |
| When affected search is needed | Repair legal-action preservation during hidden-world resampling. Whole-run policy evolution does not require action-branch cloning. | [#105](https://github.com/benyanc/spireshift/issues/105) |
| Foundation milestone | Establish repeatable held-out progress, then wins and credible run-value/risk evidence. Apply the foundation scorecard before adaptive thinking. | [#78](https://github.com/benyanc/spireshift/issues/78), contract [#5](https://github.com/benyanc/spireshift/issues/5) |
| Deferred; after a useful A8 learning workflow | Implement genuine selectable ascension levels and separate per-difficulty validation. This does not block the current learning work. | [#142](https://github.com/benyanc/spireshift/issues/142) |
| After the foundation | Integrate strategic/full-run learned search and demonstrate gains at equal compute. | [#46](https://github.com/benyanc/spireshift/issues/46), [#27](https://github.com/benyanc/spireshift/issues/27), [#28](https://github.com/benyanc/spireshift/issues/28), [#7](https://github.com/benyanc/spireshift/issues/7) |
| After useful search | Measure value of additional thinking, enforce whole-run spending and learn low/medium/high allocation. | [#29](https://github.com/benyanc/spireshift/issues/29)–[#34](https://github.com/benyanc/spireshift/issues/34), [#36](https://github.com/benyanc/spireshift/issues/36) |
| Later research | Freeze the final pre-patch bundle; measure zero-shot behavior and fixed-budget recovery after rule changes. | [#37](https://github.com/benyanc/spireshift/issues/37)–[#40](https://github.com/benyanc/spireshift/issues/40) |
| Final evidence | Reproduce public baselines, refresh competition and publish the final paired benchmark/report/demo. | [#49](https://github.com/benyanc/spireshift/issues/49), [#50](https://github.com/benyanc/spireshift/issues/50), [#41](https://github.com/benyanc/spireshift/issues/41), [#44](https://github.com/benyanc/spireshift/issues/44) |
| Optional product | Recommendation overlay and packaged Advisor, after player quality. | [#16](https://github.com/benyanc/spireshift/issues/16), [#43](https://github.com/benyanc/spireshift/issues/43) |

[#42](https://github.com/benyanc/spireshift/issues/42) retains negative-result analysis. Existing
adapters, public binding, rollouts, splits, accounting and owner scripts are reused. Closed
historical issues/recipes are not retroactively reclassified as successes.

## Learning and evaluation rules

- Keep one character, frozen game version and fixed difficulty for initial experiments. Ascension
  chooses difficulty, not an additive reward; report different difficulties separately later.
  The owner selected Ironclad / A8; do not reprioritize A0 or other difficulty support before a
  useful A8 learning workflow. The neural player continues learning every decision family.
  The profile must match actual implemented engine rules, not just a configuration label. The
  first unified pilot's Ascension-0 claim is invalid and remains disclosed as historical evidence.
- Full-run wins remain primary in population ranking/evaluation. The versioned bootstrap learner
  score distinguishes losing runs. Floors/acts are intermediate progress, not a victory-value
  target, foundation pass or permission for adaptive thinking.
- Experimental policies may change every phase. Do not impose permanent proximity to base-v2,
  frozen strategic choices or improvement on every old teacher metric. Use new recipes and
  whole-run gameplay evidence rather than relax a failed historical gate.
- The current PPO-seeded stage is incremental and retains prior PPO cost; do not claim it beats
  from-scratch PPO or GA under matched total cost. Later compare gradient training and direct
  evolution of the same compact NN at genuinely matched total cost.
  Use common seed panels within generations, rotate train panels and confirm apparent elites.
  Preserve diversity and reevaluate fine-tuning before replacing an evolved player.
- Freeze panels, exploration, updates/generations, tuning, caps and plateau stops before launch.
  Training/development/final-test ownership is at the complete-run boundary. Inspected development
  results are disclosed; final-test seeds stay sealed.
- Keep failures/caps/truncations/missing outcomes in denominators and count all actual work,
  including discarded candidates and teacher/fine-tuning costs. Repeated actions earn no reward.
- Stages expected to take five minutes or more have one clear owner command, progress, immutable
  outputs, explicit resume and a definite stop. Only the owner launches and monitors those jobs.
  Codex may run shorter stages with explicit caps; the short audit does not authorize admission,
  promotion or a longer collection/training/evaluation job.

## Preserved real-game milestone

The owner launched the privately archived v0.107.1 app outside Steam's managed library. Its
executable, pinned bridge and read-only menu identity were verified. [The frozen-game guide](frozen-live-game.md)
records its launcher and location.

Retesting after a normal future Steam update, save/profile isolation and watching a useful trained
policy through the live adapter remain under [#37](https://github.com/benyanc/spireshift/issues/37).
A menu launch establishes neither model strength nor full simulator parity. The final pre-patch
model/data/protocol bundle remains unfinished.
