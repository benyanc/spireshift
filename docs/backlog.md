# SpireShift backlog

Updated 2026-10-10 after native rest choices and their canonical agent interface pass.
GitHub holds acceptance criteria and historical evidence. Codex may launch short builds, audits,
tests and jobs autonomously. The owner launches and monitors tasks expected to take five minutes
or more. Use saved timings to estimate duration and explicit caps to bound short jobs.

## Current handoff and direction

**Current work: #145, actual-engine public control and mechanics qualification.** Exact acquisition
and preservation under #144 are complete. The owner downloaded the unchanged v0.111.0 / `41cef1ea`
macOS arm64 manifest using the licensed DepotDownloader route. Current executable, rules assembly
and GodotSharp fingerprints match. The private archive contains **435 files / 2,406,594,686 bytes**;
freezing took **6.046 seconds**, followed by a fresh integrity pass in **1.411 seconds**.
The earlier console access failure and two owner-reported password failures remain historical
evidence. The successful request does not prove why the earlier request failed.
There is no pending acquisition command for the owner; [the guide](actual-engine-v0.111.0.md)
records the completed stage and next development work.
The owner accepted [ADR 0005](decisions/0005-actual-engine-v0.111.0-qualification.md): preserve the
launchable v0.107.1 archive and every old result, acquire a separate exact v0.111.0 game, qualify
actual-engine public state/mechanics, then measure full-run speed before new A8 neural learning.
Updating Steam alone does not align the v0.107.1 emulator with v0.111.0. Its port is deferred.

The first #145 package implements a repeatable, capped shipped-game bootstrap in a disposable copy,
using Godot's save-directory override, Steam disabled before initialization, fresh native settings
and shared-save write protection. The downloader's launcher permission is repaired only in that
working copy; game DLLs/assets are unpatched. A canonical **45.279-second** job passes native save
schema/path, normal exit, shared-save sentinel and complete working/archive integrity checks.
It preserves **1,090 error lines and two warnings**, including rendering/shutdown diagnostics;
profile bootstrap is not a clean-runtime or interactive-control verdict.

A separate **3.821-second** no-game registry inspection resolves **all 1,660 generated base model
types**, including 603 card, 299 relic and eight character type entries. These counts include test
and retired types; eight declared character types are not eight selectable heroes. All offered-content
flags remain unknown; 65 name/namespace hints are diagnostics, not an exhaustive exclusion list.
Raw registry/decompiled material remains private. See the
[acquisition evidence](evidence/actual-engine-v0.111.0-acquired-and-frozen-v1.json) and
[native prerequisite evidence](evidence/actual-engine-v0.111.0-native-prerequisites-v1.json).

The shipped-game Connector now passes **13 menu/control/isolation gates in 30.355 seconds**,
including a completed native transition to character selection, loaded mod identity, loopback
process ownership, idempotency and stale-snapshot rejection. Fresh settings-only profiles leave
the canonical template, shared saves and frozen files unchanged. Rendering/shutdown diagnostics
remain preserved; this is not full-run or mechanics qualification.

The historical CLI candidate's source ledger and unchanged game DLL pass, but its binary differs
from the upstream artifact. That rejection and two Git-index failures remain preserved. A new
local lineage pins the compiler/reference pack, MIT host repair, complete source diff, binary
SHA/MVID and dependencies. Two fresh baseline builds and two fresh repaired builds agree in a
**15.132-second** job. The baseline reproduces the earlier local binary, not upstream's binary;
the upstream mismatch's cause remains unestablished. Local cache clones must restore the real
origin URL because SourceLink metadata changes binary identity. Artifact gates remain explicit.
[Menu/build evidence](evidence/actual-engine-v0.111.0-menu-control-v1.json) records these results.

**Private source extraction is complete; no owner command is pending.** The owner explicitly
authorized Codex to run it. It finished in **18.621 wall / 141.328 CPU seconds**, with 3,537 source
files, one generated project, empty diagnostic logs, and preserved game/tool integrity. All
1,660 registered model types bind uniquely to source declarations. Raw source and bindings stay
private, outside policy inputs. The initial 5–15-minute estimate is superseded by this measured
result; future long jobs still follow the owner-run boundary.

**Rest-site host repair is implemented and tested.** It awaits native choice completion and
refreshes remaining options; only explicit legal Proceed opens the map. All **75 native checks
plus five isolation/integrity gates** pass in **2.583 seconds** across nine named Ironclad/A8
fixture bootstraps. Miniature Tent works in both orders, canceled Smith preserves choices,
Girya's extra action commits, disabled/stale actions are refused, single-card Smith still asks
for confirmation, pending-choice reset drains correctly, and native travel exits a rest with
options remaining. Original/runtime game DLLs, shared saves and the candidate stay unchanged.
These are privileged managed native regressions, not rendered-game parity or training examples.
See [rest repair evidence](evidence/actual-engine-v0.111.0-cli-rest-repair-v1.json).

**Canonical rest projection is implemented and checked.** A pinned MIT hook in a disposable
Headless copy exposes refreshed choices, Proceed, cancellation and explicit upgrade confirmation,
with native operands kept in private bindings. All **226 checks and seven integrity/isolation gates**
pass in **3.130 seconds** through the strict SDK: 27 rest/selection snapshots, 21 delivered actions
and 21 invalid inputs across the same nine fixtures. Duplicate requests do not execute twice;
stale snapshots and conflicting request identities are rejected before delivery. Start/reset
explicitly forwards native A8. Missing selection preferences fail closed. No training or complete-run
attempt follows. See [projection evidence](evidence/actual-engine-v0.111.0-cli-rest-projection-v1.json).

**Next implementation within #145:** check public inputs and legal actions for the remaining
decision families, beginning with shop purchase/restock and card removal. Complete the same-game
25–30-scenario panel,
including per-copy card costs/modifier expiry/X-cost effects, status/counter ownership, shops with
price/restocking refresh, other selection preferences, A8 bootstrap/reset and real ending semantics.
Compare the named managed results with the shipped host; keep every unsupported case visible.
The candidate already reads native spending costs, so printed-only cost is not a proven defect.
Legacy privileged relic list injection remains unqualified; the new fixture obtain path uses
the game's ownership/hooks. [Source assessment](evidence/actual-engine-v0.111.0-source-assessment-v1.json)
retains the initial findings. **No owner command is pending.**

Source extraction is not a runtime correctness pass. #145 remains open for complete public
projections, A8/reset/ending semantics and the 25–30-scenario panel. #146 speed/integration follows.

Refresh menus after repeated rest/shop/reward/submenu actions. The generated type registry is not
live database instantiation, offered content, complete effects or exhaustive reachable-state
coverage. Qualification and speed evidence precede large learning; no new game campaign,
neural/GA pilot or adaptive controller is started by these prerequisites.

Ironclad/A8, full-run terminal wins and the strong cheap foundation before adaptive effort remain
binding. Preserve the relational repair and PPO math for the separately versioned actual-engine
inputs. Do not silently migrate emulator IDs, weights, experience or seed ownership across patches.
The prepared large v3 emulator pilot below is **deferred**, not the current next owner command.

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
| Current; native bootstrap, menu control and rest agent interface checked | Qualify remaining public inputs/legal actions, shops/selections/cards, live offered content, modset/reset/seed/terminal behavior and 25–30 same-build scenarios; compare shipped headless and patched CLI results. | [#145](https://github.com/benyanc/spireshift/issues/145), [#141](https://github.com/benyanc/spireshift/issues/141), [#143](https://github.com/benyanc/spireshift/issues/143) |
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
