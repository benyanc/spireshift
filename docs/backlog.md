## Current priority — build a base player that consistently wins A8, then A10

Owner direction, November 4, 2026. [ADR 0007](decisions/0007-a8-base-competence-first.md)
supersedes the older next-step handoffs below. The goal is genuine normal-start
full-run wins on unseen A8 worlds. CPU cost is an operational diagnostic; local
lesson fitting and passing compatibility checks are implementation milestones.
The numerical definition of sustained competence and confirmation panel must be
frozen before its assessment; no new numerical target is claimed accepted here.

| Order | Work item | Required outcome |
| --- | --- | --- |
| 1 — broaden model-owned training experience | [#134 whole-game base learning](https://github.com/benyanc/spireshift/issues/134), [#35 learning updates](https://github.com/benyanc/spireshift/issues/35) | The [48-game combat-feedback comparison](native-a8-combat-feedback-result.md) recorded one Act 1 clear and zero wins. The [practice mix](native-a8-practice-mix.md) measures the model's own successes and failures across varied training-only starts before fitting. |
| 2 — evaluate the next candidate on fresh worlds | [#146 fresh A8 gameplay evaluation](https://github.com/benyanc/spireshift/issues/146) | Keep the completed panel development-only. Compare any new fixed candidate on separate normal starts with full-run wins first and the complete planned denominator. |
| 3 — confirm sustained competence | [#78 consistent A8 base milestone](https://github.com/benyanc/spireshift/issues/78) | Demonstrate sustained full-run A8 wins across unseen worlds using prospectively frozen success and confirmation criteria. |
| 4 — targeted defects and official games at promising milestones | [#149 native and official correctness](https://github.com/benyanc/spireshift/issues/149) | The [new headless learner](native-a8-combat-feedback.md) passed the Trial confirmation lifecycle and saved ending regressions. Track the shipped-game Connector's large-selection limit and verify promising candidates through official games. |
| 5 — after consistent A8 | [#142 A10 validation](https://github.com/benyanc/spireshift/issues/142) | Verify A10 on the frozen build, train or adapt a separate lineage and measure its independent full-run win rate. |

[#143](https://github.com/benyanc/spireshift/issues/143) supports learning and
evaluation when observed failures justify representation or capacity changes.
[#5](https://github.com/benyanc/spireshift/issues/5)
defines the separate foundation/search-readiness scorecard; its closed definition
task is not evidence that a player passed it. Calibration and adaptive-search
readiness follow useful base play and do not hold up ordinary base development.

Items 1–3 form the development loop; the table orders the next implementation,
not a request to finish a large isolated study before testing gameplay benefit.
Freeze train/development/final-test ownership, candidate selection and practical
resource caps before each new run. Preserve public-state-only student inputs,
complete legal actions, original failure denominators, immutable evidence and
the game build. Old full checkpoints/Adam remain reference baselines, while new
lineages may change the architecture and learning method. Long jobs remain owner-run.

**Deferred from the critical path:** CPU attribution/profiling; matched-budget
and compute-allocation research ([#7](https://github.com/benyanc/spireshift/issues/7),
[#28](https://github.com/benyanc/spireshift/issues/28)–[#34](https://github.com/benyanc/spireshift/issues/34),
[#36](https://github.com/benyanc/spireshift/issues/36)); GA/hybrid comparisons
([#135](https://github.com/benyanc/spireshift/issues/135),
[#139](https://github.com/benyanc/spireshift/issues/139),
[#140](https://github.com/benyanc/spireshift/issues/140)); the old six-pair ending
panel and same-final routing-interference stage; unrelated platform/patch/overlay
work. Resume a supporting task only when it resolves a concrete base-learning
blocker or after the A8 milestone. This does not disable correctness checks or
relabel incomplete experiments.

The preserved canary panel stays **3 matching / 1 incomplete / 2 unattempted**;
its active marker, exact finals, original weights/full Adam and blocked command
remain unchanged. CPU profiling and completing that old scope are not the next
work. The new competence recipe/admission is implemented under
[ADR 0008](decisions/0008-native-win-curriculum-admission.md); it grants only its
declared collection scope after exact short checks, with no inherited official
qualification. The owner collection and saved assessment have now admitted the bank.

## Current handoff — Matched combat feedback completed

The [saved comparison](native-a8-combat-feedback-result.md) verified all 48
losses and 8,641 model-owned native deliveries. Each arm reached four
Act 1 bosses. The room-feedback copy had the only Act 1 clear and mean
floor 10.69 versus 10.94 for the floor-only copy. The next learning work
is to broaden the model's own experience across the acts.

## Prior handoff — Status pressure in Act 1

The partial kill on world 15 left the player with five Infections and an
Act 1 loss. Earlier damage and energy sequencing won the world 14 fight.
The [tempo comparison](native-a8-act1-status-tempo.md) then recorded
identical choices and three clears for each arm across 12 fresh starts.

## Prior handoff — Ordinary fight lethal planning

The [shared reward-exit check and saved recovery](native-a8-act1-ordinary-lethal-continuation.md)
verified the ordinary arm's Act 2 entry on world 7. Keep it as a saved
diagnostic alongside the original interrupted attempt. The final panel
has 14 sealed pairs, zero confirmed rescues, and two unsealed worlds.

## Prior handoff — Act 1 tactical teacher

The [tactical short checks](native-a8-act1-tactical-teacher.md) verified
the elite lethal sequence and the earlier Giant phase transition. The
closest Giant branches died at 17 HP plus 13 block against 30 damage.
The fresh eight-world diagnostic is prepared. The Giant rescue gate
still blocks qualification and all checkpoints remain frozen.

## Prior handoff — Act 1 combat branches verified

The [targeted branches](native-a8-act1-combat-branches.md) verified a native
Terror Eel kill with three attacks and two Waterfall Giant losses at Death
Blow. The closest Giant defense had 12 HP and 13 block against 30 damage.
Use the win as an elite lethal-sequencing regression and plan Giant
survival across the phase change. All 702 deliveries reconstructed, with
zero admitted lessons and optimizer updates.

## Prior handoff — Reward-safe Act 1 boss qualification finished

The [v2 result](native-a8-act1-boss-v2-result.md) verified eight complete
worlds, 32 losses and zero caps. The boss teacher died in five elites
and reached three bosses. Confirm the saved Terror Eel attack sequence
and an earlier Waterfall Giant defense branch before a fresh panel.
There were zero admitted lessons and optimizer updates.

## Prior handoff — Act 1 teacher qualified and collection stopped

The [owner result](native-a8-act1-rescue-result.md) records two reproduced
rescues across both initializers in qualification. Seven collection worlds
completed with zero clears. On world 8, the fitted player's Attack Potion
opened a generated card choice whose potion-belt referent was duplicated.
Saved replay verified a scoped adapter repair. Preserve the incomplete
world and four unstarted worlds in the denominator. Improve boss play
before a fresh collection. The primary evaluation goal is terminal A8 wins.

## Prior handoff — paired A8 result recovered

All 48 normal-start games ended in losses. Only fitted player 2 cleared Act 1,
once. The saved audit recovered the [paired result](native-a8-paired-finals-result.md)
after the inherited protection check rejected the CI edit. Review the existing
Act 1 journals before choosing the next base-learning change.

## Prior handoff — paired A8 comparison prepared

The [Architect persistence check](native-a8-paired-finals.md) passed with
valid native room history, explicit victory, a reloaded winning run record
and one saved profile win. The independent four-cell prefix check verified
24 deliveries and the same initial menu across both originals and both
fitted checkpoints. That control qualified the 48-game owner launch.

## Prior handoff — both fitting candidates frozen

The [fitting result](native-a8-world-balanced-fitting-result.md) verifies
400 optimizer updates across the two copied actors. Both improved offline
held-out agreement. Map agreement and shop loss moved in the wrong direction
on sparse development samples. Both finals are inputs to the paired normal-start
comparison.

## Prior handoff — world-balanced fitting preparation

The [fitting command](native-a8-world-balanced-fitting.md) uses all 25 admitted
worlds with one draw per world per update. Each copied checkpoint inherits
its full Adam state and freezes at update 200. Six held-out teacher traces
supply diagnostics only. The main run is owner-launched and stops with two
frozen candidates for a separately qualified gameplay comparison.

## Prior handoff — curriculum admitted

The [completed #152 bank](native-win-curriculum-result.md) covers all twelve
bosses and required decision families. It has 25 confirmed prepared lessons,
18 strict rescues and six successful held-out probes. The saved assessment
verified 370 seals. The 32 normal-start collection attempts recorded zero wins.
The next milestone is an independently fitted candidate and its wins on new
normal starts.

## Historical handoff — Soul Nexus repair and Soul Fysh supplement

The v6 run sealed all 56 fitting cases and ten held-out cases before the
Soul Nexus death callback faulted in held-out case 11. Support build 60
guards its combat scene lookup. [Repair and owner continuation](native-win-curriculum-soul-nexus.md)

The saved 354 seals include five complete held-out successes and confirmed
fitting lessons for eleven of twelve bosses. The v7 command imports them
and collects a Soul Fysh fitting supplement and the two remaining held-out
slots, including a fresh case 11 replacement. Six historical failures
count in the 75-slot linked denominator. Collection and quality assessment
use zero optimizer updates.

## Historical handoff — Trial support after case 42

Trial Accept stopped in case 43 before the native defendant choice because
the headless process lacked the portrait scene. The [Trial repair and v6
continuation](native-win-curriculum-trial.md) bind the frozen game and prior
Godot support DLLs. The saved audit verified 232 reusable seals and preserved
the failed prefix. The two new prepared boss lessons cover Test Subject and
Aeonglass and join the Queen lesson from case 38.

Use the owner command in the handoff to import the 42 complete cases and
collect the 26 remaining slots. Five preserved failures count in the 73-slot
linked denominator. The command assesses curriculum quality with zero
optimizer updates.

## Historical handoff — Test Subject support after case 38

Case 39 stopped when a missing Godot color setter faulted Test Subject's turn
loop during Intangible. Support build 58 supplies the setter. The native
control covers both revivals, third-form Intangible, and the boss reward owner.
The static Godot reference inventory supplies a reachability review list for
#149. [Test Subject repair and continuation](native-win-curriculum-test-subject.md)

The saved audit verifies 38 cases, 210 seals and 12,105 native deliveries. It
adds two confirmed lessons, including the prepared Queen strict rescue. The
current total is 20 lessons and 14 strict goal rescues. The failed End Turn
and the 26-action prefix stay diagnostic. Four failures remain in the 72-slot
linked denominator.

Run `bash scripts/continue-win-curriculum-v5.sh` for the 30 remaining slots.
The command imports complete cases, uses a disjoint replacement for case 39
and stops after collection and quality assessment with zero optimizer updates.

## Historical handoff — compact ordered answers after case 31

Gambling Chip's six-card replacement menu exceeds the old 512-answer bound:
1,957 ordered answers. The [new native-only contract](native-win-curriculum-large-selection.md)
constructs a complete ordered answer with bounded internal factors and sends one
native commit. All lengths/copies/orderings remain reachable. Partial plans provide
no labels; the new bank groups factors as one answer without increasing its weight.

- [x] Reconstruct 31 complete cases / 173 seals / 10,172 clean deliveries, retaining
  eighteen confirmed lessons and thirteen strict goal rescues. Preserve the
  interrupted case's three completed siblings and 187-action diagnostic prefix.
- [x] Preserve all three failures, their markers and original worlds. Prepare a
  71-slot linked denominator and one disjoint replacement for fit-032; no replay.
- [x] Reproduce the saved rejection and check all 1,957 ordered answers, a 100-card
  grammar, exact card order, empty/cancel/bounds and strict public decoding.
- [ ] Owner runs `bash scripts/continue-win-curriculum-v4.sh`, then assess the
  complete curriculum bank before a separately selected #134/#35 learning recipe.
- [ ] Support grouped answer labels in that future learner; qualify official
  compact delivery and Architect completion before full-game victory claims.

The game, original CLI56/support57 and full original/fitted weights/Adam remain
frozen. Main collection is unstarted by the repair; no optimizer updates or
adaptive control follows. Previous handoffs and commands below are historical.

## Historical handoff — Reattach support repair after thirty completed cases

The v2 collection's guard rejected an earlier missing Godot.GetIndex support
method after a native loss. Saved audits verify 138 complete episodes / 9,208
deliveries, eighteen confirmed lessons and thirteen strict goal rescues. The
failed case's 245 actions remain diagnostic only, alongside the older failed
world. The frozen game and original/fitted full states/Adam stay unchanged.

- [x] Build a separate support revision57 with only the missing Node method;
  reproduce the old JIT failure and verify two identical repaired builds.
- [x] Verify native 25-HP revival/targetability, all-segment death/rewards and
  clean shutdown, with twelve actual deliveries and fatal runtime guards intact.
- [x] Prepare thirty-case immutable imports, both historical failures in a
  70-slot linked denominator, one fresh replacement and one owner command.
- [ ] Owner runs `bash scripts/continue-win-curriculum-v3.sh`, then assess the
  completed all-boss/decision-family/held-world bank before learning.
- [ ] Prepare #134/#35 learning and #146 fresh full-game evaluation. The separate
  Architect completion repair and official candidate verification remain pending.

See [the current continuation](native-win-curriculum-reattach.md) and
[evidence](evidence/native-win-curriculum-reattach-v1.json). No automatic fitting,
promotion or adaptive controller follows. Earlier commands remain historical.

## Historical handoff — reward-belt repair; preserve and continue the collection

The owner run stopped on duplicate owned potion referents after six completed
cases. The saved audit reconstructs 1,148 deliveries and five confirmed lessons,
including three strict goal rescues. The failed case's 26 acknowledged prefix
deliveries remain diagnostic only. No main optimizer updates occurred.

The [versioned continuation](native-win-curriculum-recovery.md) preserves the old
workspace/marker, imports 35 verified seals without games, retains the failed
case in the 69-slot linked denominator and uses one fresh replacement world.
It repairs only the curriculum's full-belt reward projection. The game build,
original/fitted full states and Adam, ordinary native interface, teacher method,
data ownership and bank-quality rules stay frozen. The old command stays blocked.

- [x] Reproduce the exact saved duplicate-ID failure and repair registration
  with the same strict SDK; preserve native permissions and action operands.
- [x] Audit all six complete cases and their selected confirmations; preserve
  the interrupted worker's terminated process, raw evidence and marker.
- [x] Prepare a separate v2 recipe/import manifest, targeted fresh controls and
  one owner command, with no interrupted-world replay or automatic learning.
- [ ] Owner runs `bash scripts/continue-win-curriculum-v2.sh`, then assess actual
  all-boss/family/rescue coverage before #134/#35 learning.
- [ ] Qualify the separate Architect completion repair before native full-run
  victory claims, then measure independent normal-start A8 strength under #146.

## Historical preparation — win-focused curriculum implemented; owner collection next

See [the curriculum guide](native-win-curriculum.md) and
[evidence](evidence/native-win-curriculum-v1.json). Preserve the frozen game,
original and fitted full weights/Adam, and all old canary evidence.

- [x] Implement a separate pinned native-development scope, public student boundary,
  explicit training-only native starts, whole-world partitions and quality gates.
- [x] Declare early/middle/late acts, all twelve bosses including all three final
  bosses, diverse decks/resources and combat/strategic decision families.
- [x] Add fixed public-state teacher candidates, native outcome selection, raw
  action verification, independent confirmation and strict goal-rescue accounting.
- [x] Pass exact-source start and collect/learn/reload/act controls: 621 verified
  gameplay deliveries, two disposable copies, separate unseen-world loss gains,
  unchanged originals/build, 2,804 tests and a zero-game launch preflight.
- [ ] Owner runs `bash scripts/prepare-win-curriculum-v1.sh`. It collects only;
  clean seals resume and incomplete units remain preserved. Zero main updates.
- [ ] Assess actual bank quality across bosses, families and independent worlds.
  A prepared case list or a successful short control is not an admitted main bank.
- [ ] Prepare #134/#35 base learning and #146 independent natural-start gameplay.
  Repair the reached Architect completion gap before claiming full-run victory.

Prepared final-boss successes stop at native completed-boss reward ownership,
not a terminal full-run win. The final-event failure and all earlier provisional
controls remain preserved. No ordinary training, promotion, A10 or adaptive
controller follows automatically.

## Historical handoff — three canary pairs match; diagnose the official CPU guard

See [the assessed canary result](native-varied-final-canary-result.md) and
[evidence](evidence/native-varied-final-canary-result-v1.json). Keep the original
six-pair denominator: three matching endings, one CPU-limited incomplete pair,
two unattempted routed pairs. Exact finals and the frozen build stay unchanged.

- [x] Independently reconstruct all 1,448 actual native/official deliveries,
  three sealed genuine-ending pairs, native ending facts/public reads, official
  summary proofs and clean resets. The fourth pair matches all 239 delivered
  choices plus its last unsubmitted menu; no observed common-prefix divergence.
- [x] Identify the stop: official player-3 teacher VTV204 reaches 128.184731264
  host CPU seconds before an ending. The outer resource cap is null. Preserve
  its active marker, complete native counterpart and incomplete official prefix;
  the existing launcher correctly refuses replay. VTV205/206 remain unattempted.
- [x] Verify all 29,714 protected files, exact final/original full weights/Adam,
  game/runtime/CLI/connector/worker/converter/layout and app resets unchanged.
  Saved audits perform zero games/updates and grant no new panel qualification.
- [ ] Next separately implement CPU attribution/performance diagnostics for the
  official runner, starting with saved/source evidence. Its guard counts the
  coordinator, shipped game and SDK process; inference-only cost is not measured.
  Keep the 128-second objective and exact finals. Do not raise limits, refit,
  replay VTV204, discard its denominator or start another panel automatically.
- [ ] After a separately qualified remedy, prepare the required fresh scope and
  remaining exact-mode live qualification. Only a successful gate admits later
  withheld/fresh full-game and same-final interference evaluation. No automatic
  ordinary PPO, promotion, scaling or adaptive controller.

## Historical handoff — six exact-final live canary pairs prepared; owner run next

See [the canary-only preparation](native-varied-final-canaries.md) and
[evidence](evidence/native-varied-final-canaries-v1.json). Freeze the exact
dbcb5980… finals, original full weights/Adam, tuple48 game and historical code.

- [x] Bind the independently reconstructed 256-update assessment, all four full
  fitted states/Adam and both original routing anchors to a separate launch scope.
- [x] Retain all six predeclared worlds VTV201–206 and reference/teacher/routed
  modes. Preserve ten-minute pairs, 128 gameplay CPU seconds per host and
  384-choice guards; zero optimizer updates and no automatic follow-up.
- [x] Verify 1,752 paired saved-menu mode comparisons without starting any game
  or consuming a planned world. These checks grant no live qualification.
- [ ] Owner runs `bash scripts/compare-varied-finals-v1.sh`, about 25–45 minutes,
  with one 70-minute/7,200-CPU-second/4-GB outer session. Qualify six pairs only,
  then stop. Clean seals resume; incomplete or uncertain attempts are not retried.
- [ ] Independently assess all six genuine ending pairs, raw deliveries,
  official summaries and clean resets against their exact final/mode bindings.
- [ ] Only after that gate, separately select withheld/fresh full-game and
  same-final interference evaluation. No fitting, PPO, promotion, scaling or
  adaptive controller follows automatically from this preparation.

## Historical handoff — all 256 fitting updates verified; exact-final live canaries next

See [the assessed fitting result](native-varied-fitting-result.md) and
[evidence](evidence/native-varied-fitting-result-v1.json). Preserve all four fixed
finals, the completed bank, original weights/full Adam and frozen game tuple48.

- [x] Complete four copies × 64 updates / 2,048 draws, with exactly 256 draws per
  fitting world per copy. Original Adam stays 5,658/6,045; copies end 5,722/6,109.
- [x] Independently reconstruct every epoch: all 256 numerical updates, complete
  Adam, work records and recorded compatibility receipts match exactly. Verify
  all 67 seals and 66 unique checkpoint regressions. Critic weights stay fixed.
- [x] Assess fitting-only evidence: teacher copies greedily prefer 3/3 and 2/3
  changed teacher labels; reference copies prefer 0/3 each. These are three seen
  menus per initializer, not holdout or gameplay wins. Do not fit extra epochs.
- [ ] Prepare the six fresh exact-final/mode official/native natural-ending
  canaries on unchanged code/build, with short checks and one capped owner command.
  No completed new-policy live canary is claimed; fitting must not rerun.
- [ ] After those canaries pass, separately evaluate withheld fights and the
  fresh full-game / same-final interference comparison. Preserve failure/cap/
  missing denominators and the terminal-victory objective. No automatic training,
  PPO, promotion, scaling or adaptive controller.

## Historical handoff — 256-update copy fitting prepared; owner run next

See [the fitting-only preparation](native-varied-fitting-comparison.md) and
[evidence](evidence/native-varied-fitting-comparison-v1.json). Original recipe,
assessed bank, game/CLI56/Connector31/worker24/converter16/layout12/environment48
and original full weights/Adam stay frozen.

- [x] Prepare a separately pinned fitting-only launcher: exact assessed saved
  bank, four copies × 64 updates/2,048 draws, 67 sealed units and final barrier.
- [x] Verify actual saved-bank gradients on four disposable copies, a fresh-process
  full-Adam resume and exact numerical reconstruction. Twenty diagnostic copy
  updates and four reconstruction steps stay outside the unstarted main study.
- [x] Pin 28,855 prior files and reject stale assessment, source/runtime drift,
  withheld labels, larger work or automatic follow-up. Preserve clean seals and
  stop on unfinished updates without replay.
- [ ] Owner runs `bash scripts/fit-varied-teaching-v1.sh`, about 6–12 minutes;
  30-minute/3,600-CPU-second/4-GB session. Fit only, freeze finals, then stop.
- [ ] Independently assess all four finals/complete Adam and work before the six
  fresh changed-checkpoint/mode official/native ending canaries.
- [ ] Assess the subsequent withheld/fresh full-game and separate same-final
  interference results. No automatic PPO, promotion, scaling or controller.

## Historical handoff — varied lesson bank assessed; matched copy fitting next

See [the assessed collection](native-varied-teaching-collection-result.md) and
[evidence](evidence/native-varied-teaching-collection-result-v1.json). Keep game
v0.111.0/41cef1ea, CLI56/Connector31/worker24/converter16/layout12/environment48,
both originals and full Adam frozen. Preserve the completed collection; do not rerun it.

- [x] Complete 12 clean natural source games and all 64 planned teacher proposals;
  three selected improvements reproduce in their declared confirmations.
- [x] Independently reconstruct all 6,738 actual deliveries and 79 sealed units,
  including eight capped proposals. Rebuild all public roots, selection and the
  exact public lesson bank; all frozen inputs/profile receipts verify.
- [x] Admit 12 lessons from eight fitting worlds, both source players, eight enemy
  compositions and 12 deck compositions; retain four disjoint withheld roots.
  All three improvements are player-2-sourced floor-2 already-won fights,
  with +1/+1/+5 HP. This is a modest local teacher signal; strength is unevaluated.
- [ ] Next separately select the prepared matched fitting diagnostic: four copied
  actors, 64 updates / 2,048 draws each, full warm Adam, exact pause/resume and
  recorded compatibility checks. Give the owner one capped fitting-only command
  after short checks; no original updates, best-epoch choice or automatic evaluation.
- [ ] Freeze all finals, then separately run their six current-checkpoint/mode
  official/native natural-ending canaries. Only then evaluate withheld fights
  and the fresh full-game comparison / same-final interference ablation.
- [ ] Assess terminal-victory outcomes with original denominators before further
  learning or scaling. No automatic PPO, promotion or adaptive controller.

## Historical handoff — learner guard connected; varied curriculum and interference test prepared

See [the guarded study](native-varied-teaching.md) and
[evidence](evidence/native-varied-teaching-v1.json). Game v0.111.0/41cef1ea and
CLI56/Connector31/worker24/converter16/layout12/environment48 remain frozen.
Both original numerical players and full Adam stay unchanged.

- [x] Bind the verified two-ending result, exact original/imported full states,
  execution runtime and complete paired input regressions to the new learner
  guard. Admit only the declared copy-based diagnostic; changed finals/routed
  modes need their own live canaries. No old guard or admission label is rewritten.
- [x] Prepare eight fresh fitting/four withheld worlds, public outcome-blind
  early/later root selection, fixed teacher proposals/confirmations and a
  fitting-only diversity/improvement gate. Old finals/withheld/canary worlds
  never supply labels. Collection stops for assessment before main fitting.
- [x] Prepare matched 64-update reference/teacher copies per original, exact
  warm-Adam resumption, every-checkpoint recorded checks and an all-finals
  barrier. The separate shared-vs-original-noncombat routing test uses the
  same teacher final and zero extra optimizer work.
- [x] Qualify the exact-source native control on fresh VTC907/908 and independently
  verify 11 seals, 361 raw deliveries and all 16 copied updates/Adam.
  Both successful controls total 32 disposable-copy updates; originals/main stay
  unchanged. The relaxed control quality gate is not main teacher admission.
  Preserve failed controls, the initial test typing rejection and source snapshots.
- [ ] Owner runs `bash scripts/prepare-varied-teaching-v1.sh`: collect/qualify
  the new bank only, about 10–25 minutes with a 30-minute session cap. It is
  unstarted; clean sealed boundaries resume, uncertain units do not retry.
- [ ] Assess that teacher-quality result before main fitting. Later phases
  separately require six fresh checkpoint/mode ending canaries, then withheld
  fights and 16 fresh full-game worlds/four modes. No automatic follow-up,
  bulk PPO, promotion, scaling or adaptive controller.

## Historical handoff — two complete paired endings pass; return to learning preparation

See [the assessed result](native-render-ending-result.md) and
[evidence](evidence/native-render-ending-result-v1.json). E2E611/E2E612 pass for
both original players on frozen CLI56 / Connector31 / worker24 / converter16 /
layout12 / environment48. Every original full state/Adam and game input stays exact.

- [x] Independently reconstruct all 584 actual deliveries: 166 per host for player 2,
  126 for player 3. All 292 playable input/menu pairs and frozen choices/numerics
  match in order, through genuine losses, full terminal facts/reads and both
  official native summaries. Verify all resets with no caps or retries.
- [x] Verify three naturally completed shop purchases and Blood Potion's actual
  retained task completion in the shop; both hosts heal 36 to 52 HP. Preserve the
  source/saved scope of Body Slam and Regal Pillow, absent from these worlds.
- [x] Preserve all 21,356 prior files, original models/full Adam, frozen archive,
  fixed idle app and the completed owner reports. Record this bounded workflow
  milestone separately from global mechanics or playing-strength claims.
- [ ] Bind the scoped assessed compatibility evidence to a new learner entry/
  start-resume guard. Do not silently reuse stale historical admission labels.
- [ ] Prepare the ordered varied fitting-only teaching curriculum and separate
  shared-policy-interference comparison, with original/reference controls,
  matched work, prospective splits and held-out worlds excluded from fitting.
  Reuse the completed sibling card-zone audit; avoid repeated unchanged PPO.
- [ ] Validate changed checkpoints and declare fresh original/trained official
  evaluation before promotion/scaling. No training, broad live admission,
  controller or next experiment follows automatically. No new long command is
  prepared; do not rerun E2E611/E2E612 or the completed wrapper.

## Historical handoff — card rendering and rest text repaired; fresh endings pending

See [the repair and owner command](native-card-rendering-repair.md) and
[evidence](evidence/native-card-rendering-repair-v1.json). The original game,
CLI56 / worker24 / converter16 / layout12 and both full original players/Adam
remain exact. New official adapter is Connector31 / environment48.

- [x] Audit all 17 shared card-export calls. Require explicit display context;
  eight visible-widget callers use their actual NCard.DisplayingPile. Legacy
  helpers also require a context; no shared Hand default remains.
- [x] Share LF-to-space handling across card/rest descriptions while preserving
  every other codepoint, amount, order and glyph. Keep exact input comparison.
- [x] Pass 265 Host tests, 112 native formatter vectors, eight compiled text
  vectors, portable checks and two reproducible source builds. Delivery and
  task-completion code remains unchanged; no new live support claim yet.
- [x] Reconstruct all 781 historical actual deliveries. Diagnostic repaired
  inputs and choices match through player2 input87 and all 247 player3 choices.
  Stop player2 before the changed choice is committed; its later old suffix is
  not a repaired game. Preserve old blocked reports and all 21,356 prior files.
- [ ] Owner runs `bash scripts/compare-render-endings-v1.sh`: fresh natural
  E2E611/E2E612, about 5–15 minutes, unchanged 128-CPU-second/384-choice host guard,
  ten-minute pairs and 40-minute outer cap. Prepared; unstarted.
- [ ] Assess exact inputs/endings/summaries/task proofs/resets before broader
  admission and fitting-only teaching/interference. Source inventory and
  formatter vectors do not prove all content interactions. No automatic
  training, promotion, controller or next experiment.

## Historical handoff — shop tasks verify; two text projection gaps remain

See [the completed ending assessment](native-shop-ending-result.md) and
[evidence](evidence/native-shop-ending-result-v1.json). E2E609/E2E610 both remain
blocked. All four real losses, both official native summaries and clean resets
verify. The original game and tuple47 stay unchanged; no resource cap is hit.

- [x] Independently reconstruct all 781 actual deliveries: p2 144 native/143
  official; p3 247 per host. Preserve complete original traces and comparisons.
- [x] Isolate p2 input 87 after Attack Potion: generated Body Slam has a combat
  hint only in the Connector. Native widget and CLI use display pile None;
  Connector implicitly uses shared Hand default. The same original player
  chooses Body Slam versus Skip with the same draw key, then play diverges.
  Do not add the erroneous hint to CLI or realign the later suffix.
- [x] Isolate p3's only differing input, 168: newline versus space before
  Regal Pillow's bonus. Both choose Rest and heal 8 to 47 HP; all 247 action
  indices and standalone terminal facts/reads match diagnostically.
- [x] Verify two natural card-purchase task completions at p3 inputs 29/30.
  No locked option, Pendulum offer or repaired noncombat use is exercised;
  retain prior focused qualification without expanding its coverage.
- [x] Verify original full weights/Adam, frozen archive, idle app and all
  21,031 prior protected files. Saved-only assessment passes in 56.03 seconds;
  no game, action or completed control is replayed.
- [ ] Audit every card-export caller's native rendering context and require
  explicit display-pile binding. Cover conditional generated/simple/deck/shop/
  pile/hand/upgrade descriptions through saved/source cases.
- [ ] Standardize visible text line-break handling for rest descriptions while
  preserving words, amounts, order and glyphs. Keep exact input comparison.
- [ ] Prepare a new finite owner command only after those repairs qualify.
  No replacement long command exists yet; do not rerun the completed launcher
  or E2E609/E2E610. No automatic training, promotion or controller follows.

## Historical handoff — event/shop facts repaired; native shop tasks guarded

See [the repairs and owner command](native-shop-readiness-repair.md) and
[evidence](evidence/native-shop-readiness-repair-v1.json). The original game,
CLI56 / worker24 / converter16 / layout12 and full original players/Adam remain
exact. Official adapter is Connector30 / environment47.

- [x] Export event enablement from both the button and native option lock;
  keep surface/referent/action semantics consistent.
- [x] Split shop and owned-inventory relic rendering. Remove shop-only counter
  leakage while retaining real owned counters, zero values and other facts.
- [x] Retain the actual native wrapper task for card/relic/potion purchases
  and concrete card removal, including awaited final hooks. Gate ordinary and
  atomic authority until completion; preserve exact task-owned child overlays
  across awaits. Faults, unknown delivery and foreign identity stay blocked.
- [x] Pass 257 Host tests, 36 compiled fact vectors, eight proof tests, four
  script-safety tests and portable checks. Incremental source inventory covers
  all 158 Connector delivery methods, including the one new tracker entry.
- [x] Independently reconstruct 486 old actual deliveries and replay 486
  current inputs/choices in 62.47 seconds. Compiled diagnostic fixes resolve
  all seven differing inputs without changing historical blocked reports.
- [x] Fresh paired removal confirmation and cancellation pass all 12 deliveries
  and eight states with exact native task/child/completion proof and clean resets.
  Preserve rejected SH0P801, unattempted SH0P802 and initial saved-verifier log
  collision. No old world/action/control is replayed.
- [x] Verify all 21,031 prior files, frozen archive, idle working app and original
  full weights/Adam. Preserve preparation failures; the accidentally addressed
  old build recipe is restored byte for byte and the new recipe is separate.
- [ ] Owner runs `bash scripts/compare-shop-endings-v1.sh`: fresh natural
  E2E609/E2E610, about 5–15 minutes, same 128-CPU-second/384-choice host guard,
  ten-minute pairs and 40-minute outer cap. This panel remains unstarted.
- [ ] Assess the integration result before broader admission and returning to
  fitting-only teaching/interference. Awaited shop-task completion is guarded;
  source inventory and passing controls do not prove every background callback
  or content interaction. No automatic training, promotion or controller.

## Historical handoff — natural endings complete; two Connector facts still differ

See [the completed lifecycle ending assessment](native-action-lifecycle-ending-result.md)
and [evidence](evidence/native-action-lifecycle-ending-result-v1.json). E2E607/E2E608
both remain blocked by earlier public-input differences despite matching standalone
terminal state/reads, all four natural losses and both official native summaries.
The frozen game and CLI56 / Connector29 / worker24 / converter16 / layout12 remain exact.

- [x] Independently reconstruct all 486 actual deliveries: 106 per host for
  player 2 and 137 per host for player 3. All legal menus and selected candidates
  agree diagnostically. No realignment, game replay, optimizer update or cap.
- [x] Isolate player 2's sole differing input, index 47: locked Self-Help Book
  option exported as enabled by the Connector despite its native lock. Both
  hosts already exclude that option from legal actions.
- [x] Isolate player 3's six differing inputs, 31–36: unpurchased shop Pendulum
  has no native counter versus official zero. Owned relic facts match; the shared
  Connector exporter applies inventory-counter visibility to a merchant icon.
- [x] Keep potion evidence precise: no repaired noncombat use is exercised.
  Player 3 uses Dexterity Potion in combat. Earlier focused noncombat use/discard
  controls keep their scope; this panel supplies no new noncombat-use proof.
- [x] Verify original weights/full Adam, protected source/evidence, frozen master
  and restored idle app. Preserve the first saved-assessment report-format check
  failure and corrected saved-only assessment; no original report is rewritten.
- [ ] Repair public event enablement and shop relic counter visibility using
  saved/source regressions. Check surface/referent/menu consistency and rendering
  context while retaining legitimate owned counters. No game-rule change.
- [ ] Resolve the separate shop background-task completion qualification risk
  before broader admission. Source path inventory is not proof of every public
  semantic fact or delayed hook.
- [ ] Prepare any new finite owner command only after those repairs qualify.
  No new long command exists yet; do not rerun the completed launcher or worlds.
  Compatibility, training, promotion and controller admission remain ungranted.

## Historical handoff — action lifecycles audited; potion completion qualified

See [the lifecycle audit and repair](action-lifecycle-audit-and-potion-completion.md)
and [evidence](evidence/action-lifecycle-audit-and-potion-completion-v1.json).
Original game v0.111.0 / 41cef1ea and CLI56 / worker24 / converter16 / layout12
remain exact. Final official adapter is Connector29, environment46.

- [x] Compiler-derived audit of all 17 original and 26 current CLI gameplay
  commands, control/support mutation sites and 144/156/157 original/previous/current
  Connector delivery methods. Keep source review, tested effects and unknown
  interactions separate. Unknown action/provider additions invalidate coverage.
- [x] Attribute original CLI fallback discards/forced recovery separately from
  our Connector's enqueue-only use and premature discard completion.
- [x] Capture exact native potion use identity and wait for terminal task proof;
  preserve actual required screen/hand selectors and deferred choices. Pending
  discard also requires actual completion/cancellation, not bottle removal.
- [x] Pass 244 compiled Host tests, ten Python and nine proof tests. Fresh
  postcombat use/discard controls match seven states and all ten deliveries:
  HP 54 to 70 for use, HP 54 unchanged for discard. Native effect completion proof
  and zero-authority unfinished-heal observations verify independently.
- [x] Preserve the collector exact-eight footer rejection and native-only wrong
  discard-verb attempt. No old world/action is retried; retired markers remain.
  The original completed use is independently verified from saved captures.
- [x] Reproduce Connector29 twice and reconcile all 728 earlier deliveries and
  current inputs/menus/original-player choices under environment46 in 78.87 seconds.
  All 20,590 prior files, frozen master, restored app and full weights/Adam exact.
- [ ] Owner runs `bash scripts/compare-action-lifecycle-endings-v1.sh`: fresh
  E2E607/E2E608, about 5–15 minutes, unchanged 128-CPU-second/384-choice host guard,
  ten-minute pairs and 40-minute outer cap. Plan remains unstarted.
- [ ] Resolve the audit's explicit shop background-task qualification risk and
  assess fresh integration evidence before broader admission. Natural-game passes
  alone do not prove every delayed pickup or UI callback. No automatic learning,
  promotion, controller, exhaustive matrix or strength claim follows.

## Historical handoff — one matching ending; noncombat potion completion remains

See [the completed assessment](native-entry-text-ending-result.md) and
[evidence](evidence/native-entry-text-ending-result-v1.json). E2E606 passes the
complete declared workflow; E2E605 remains blocked. Original game and tuple44
remain exact. Do not rerun the completed launcher or either world/action.

- [x] Independently reconstruct all 620 actual deliveries: 104 per host for
  player 2, 206 per host for player 3. All four real endings and both official
  Continue/summary proofs verify, with clean shutdown/app/profile/archive resets.
- [x] Confirm live tutorial readiness: both map tutorials dismiss once without
  rejection/retry; all 45 settling captures publish zero mutation actions.
  Neither case reaches Aroma or a chest; do not expand their live coverage.
- [x] Isolate the sole player-2 input mismatch: after Blood Potion use at index
  42, inputs 43/44 expose native HP 70 versus official 54. Bottle is gone in both;
  official HP reaches 70 at index 45. All menus and selected indices agree, but
  do not realign later states or relabel this pair as a pass.
- [x] Trace source ordering: noncombat use acknowledges enqueueing before its
  asynchronous effect finishes. Bottle removal precedes hooks/presentation/effect;
  the heal amount agrees. Existing pending tracking covers discards, not uses.
- [x] Saved-only assessment passes in 44.70 seconds. All original weights/full
  Adam, frozen game, restored app and 20,569 prior files remain exact. Preserve
  the corrected offline source probe's initial failure. No new game or update.
- [ ] Repair/qualify actual noncombat potion-use completion readiness before
  another successor decision, preserving any effect-owned selector and discard
  behavior. Add saved/source and focused fresh transition controls first.
- [ ] Freeze any new finite owner proposal only after those checks. No next
  long command exists yet. No hardcoded healing/delay, historical retry, training,
  promotion, controller, exhaustive matrix or strength claim follows this result.

## Historical handoff — tutorial entry and native text repaired; fresh endings prepared

See [the repair and owner command](native-tutorial-entry-text-repair.md) and
[evidence](evidence/native-tutorial-entry-text-repair-v1.json). Original game
v0.111.0 / 41cef1ea stays frozen. New adapter tuple: CLI56 / Connector27 /
worker24 / converter16 / layout12 / environment44.

- [x] Withhold map-tutorial mutation/potion/atomic authority during native combat
  entry, then recheck before its first click. Preserve setup tutorials, an open
  map retaining a completed room, and modal-disabled public play permission.
- [x] Repair numeric rainbow parameters only in the native text formatter.
  Check all 6,902 frozen English strings: four supported formatting fixes and
  6,898 unchanged outputs. Preserve glyphs, numbers and unfamiliar facts.
- [x] Pass all 221 compiled Host tests, 142 compiled readiness vectors and
  18 text edge cases. The saved Aroma body/full diagnostic public input matches
  official exactly. Preserve E2E603's rejected receipt and counter facts.
- [x] Reproduce native/Connector builds independently. Preserve the initial
  development artifact identity rejection; canonical fresh source builds pass.
  Source/saved qualification takes 23.37 seconds and launches no games.
- [x] Independently verify all 728 historical deliveries and replay all 728
  current inputs/menus and original-player choices under environment44 in
  91.84 seconds. Full original weights/Adam and 20,380 prior files remain exact.
- [x] Freeze one fresh finite proposal using E2E605/E2E606. The existing
  genuine-ending, receipt, full-public-state, summary and shutdown/reset guards
  remain exact. Both historical pairs stay blocked; no old seed/action is retried.
- [ ] Owner runs `bash scripts/compare-entry-text-endings-v1.sh`, about
  5–15 minutes, ten minutes per pair, 128 gameplay CPU seconds and 384 choices
  per host; 40-minute outer cap. No fixture saves or forced outcomes. Gameplay
  remains unstarted; source/saved diagnostics do not grant live qualification.
- [ ] Assess the fresh result before finishing finite compatibility and
  returning to varied fitting-only teaching and separate interference work.
  No automatic training, promotion, controller or exhaustive matrix follows.

## Historical handoff — ending panel assessed; tutorial settling and text rendering remain

See [the completed result](native-chest-ending-result.md) and
[evidence](evidence/native-chest-ending-result-v1.json). The owner ran both
E2E603/E2E604 pairs; both remain blocked. No outer or gameplay compute cap occurs.

- [x] Independently reconstruct all 421 acknowledged gameplay deliveries in
  27.47 seconds, including an explicit diagnostic copy of the stopped 36-choice
  official prefix. All source/raw reports, 20,108 protected prior files, original
  full players/Adam, frozen archive and restored app remain exact.
- [x] Confirm the summary fix: player 3 reaches a real loss, Continue and native
  summary in 129 choices / 77.15 gameplay CPU seconds. The full retained proof,
  native schema, persistent state and summary reads verify independently.
- [x] Identify player 2's actual rejection: `map_select_ftue` Got it!,
  `not_delivered / stale_snapshot` while underlying context changes unknown to
  combat and Ornamental Fan's counter becomes visible at 2. Both tutorial/control
  remain the same. No resubmission; all 36 preceding policy inputs match.
- [x] Identify player 3's first input difference at index 45: native Aroma of Chaos
  body retains `[rainbow freq=0.3 sat=0.8 val=1]`; official rendered words omit
  that display tag. Menu keys agree. Do not discard or relabel the raw mismatch.
- [ ] Repair/qualify tutorial authority during incomplete combat entry, using
  saved transitions and native source predicates before the first submission.
- [ ] Inventory supported parameterized text tags and repair native rendering,
  preserving glyphs, amounts and unknown facts; add source/saved regressions.
- [ ] Freeze any required new short controls and a finite owner proposal after
  those repairs. No next owner command is prepared. Do not retry E2E603/E2E604,
  raise the budget, realign later divergent states or repeat the chest fixtures.
- [ ] On the required scoped workflow pass and saved assessment, finish finite
  compatibility and return to varied fitting-only teaching/interference work.
  No automatic learning, promotion, controller or exhaustive content matrix.

## Historical handoff — chest repair qualified; replacement ending panel prepared

See [the chest repair](native-chest-lifecycle-repair.md) and its
[evidence](evidence/native-chest-lifecycle-repair-v1.json). Preserve all earlier
blocked results and worlds. The game remains v0.111.0 / 41cef1ea.

- [x] Qualify CLI55 complete chest exports and worker24 public lifecycle/actions,
  Connector26 stable Take/Skip authority and delivery recheck, converter16 chest
  pre-sampling guard and unchanged layout12 in shared environment43.
- [x] Both short Take/Skip pairs match all seven complete states, including final
  successors. All ten deliveries reconstruct. The selected relic is added once;
  Skip preserves persistent facts/deck. All worker/app/profile/archive resets pass.
- [x] Saved assessment checks 12 partial-choice captures with zero actions,
  both actual complete Take/Skip menus, rejection of the historical premature
  menu and a corrupted receipt copy. Preserve the initial zero-action fixture
  wiring failure and its corrected fresh-seed native check.
- [x] Independently verify all 728 prior deliveries and replay all 728 current
  inputs/menus and unchanged-player choices under environment43, with exact full
  Adam. Verify all 20,108 protected prior files and unchanged original game.
- [x] Bind the corrected native summary field and proof-before-validation
  collector, strict saved proof verification, 128 gameplay CPU seconds and
  genuine-ending requirement into a fresh finite owner plan.
- [ ] Owner runs `bash scripts/compare-chest-endings-v1.sh`, about 5–15 minutes:
  fresh E2E603/E2E604, one pair per original player, ten minutes per pair and a
  40-minute outer cap. The plan is preflighted and gameplay remains unstarted.
  Long jobs stay owner-run; no fixture save, forced outcome or historical retry.
- [ ] Assess exact playable prefixes, both native endings, all public game facts,
  receipts, summary proof and clean resets. On the scoped pass, return to varied
  fitting-only teaching and the separate interference test. No automatic
  training/promotion/controller or exhaustive content matrix follows.

## Historical handoff — natural ending panel blocked; chest and summary gaps isolated

See [the assessed result](native-e2e-ending-qualification.md) and
[result evidence](evidence/native-e2e-owner-result-v1.json). Both completed pairs
remain in the denominator. Do not rerun E2E601/E2E602 or their historical launcher.

- [x] Inspect both first divergences: closed treasure chest at inputs 122/44
  (zero-based). Different action/owner shapes, relic details and delayed official
  Skip matter. In E2E601 native skips and official takes Venerable Tea Set; later
  traces cannot be realigned to claim parity.
- [x] Reconstruct all 747 acknowledged deliveries from raw captures in a separate
  saved-only assessment, including explicitly diagnostic official prefixes.
  Preserve original source/recipes/limits, all prior evidence and full Adam.
- [x] Identify E2E601's 128-CPU-second official gameplay guard as incomplete,
  with no outer resource cap, and E2E602's real native summary as a verifier
  rejection (`total_floor` versus actual `floor_reached`). All resets pass.
- [x] Prepare separate summary helper/collector v2 with the actual field and
  full proof journalling before validation; 16 regressions pass. Keep old files
  frozen. The old missing summary-read proof is not invented or retrofitted.
- [ ] Repair/qualify treasure lifecycle projection, full relic facts and stable
  Skip authority with targeted source/saved/effect checks before further games.
- [ ] Bind corrected summary collection and chest handling in a new frozen tuple;
  retain 128 gameplay CPU seconds. No replacement owner command is prepared yet.
  Do not repeat failed worlds or raise the budget to complete these cases.
- [ ] After a finite equal-input/ending/summary check passes and is assessed,
  finish compatibility and return to varied fitting-only teaching and the separate
  interference comparison. No exhaustive content matrix or automatic training.

## Historical handoff — saved evidence reconciled; natural ending panel prepared

See [the finite end-to-end plan](native-e2e-ending-qualification.md) and
[preparation evidence](evidence/native-e2e-preparation-v1.json). All production
components remain frozen at game v0.111.0 / CLI54 / Connector25 / worker23 /
converter15 / layout12 / environment42.

- [x] Independently reverify the earlier 728 deliveries and reproduce all 728
  current inputs/menus, sampled choices, draws, log probabilities and values
  with exact original numerical players/Adam. The final saved-only pass takes
  75.94 seconds. No new games or updates occur.
- [x] Verify the narrow source delta: 72 production Connector files unchanged;
  only the qualified counter guard/wiring differ. Layout changes are confined
  to rest; converter changes to its layout import. Preserve original effect
  provenance and the old final-uncaptured-successor limit.
- [x] Add/test a genuine-ending requirement, strict typed public comparison,
  final-at-choice-limit capture, independent receipts and official Continue /
  summary proof. Limits never manufacture losses or trigger action retries.
- [ ] Owner runs `bash scripts/compare-e2e-endings-v1.sh`, about 5–15 minutes:
  two natural pairs, one per original player on fresh worlds E2E601/E2E602.
  Ten minutes per pair, 128 gameplay CPU seconds and 384-choice guard per host;
  40-minute outer cap includes exact repository checks/raw verification.
  The plan is unstarted, uses one fixed app and no fixture saves/forced outcomes.
- [ ] Assess matching playable states, explicit ending facts, all receipts and
  summary/reset evidence. On that scoped pass, finish compatibility and prepare
  varied fitting-only lessons plus the separate interference check. Avoid new
  exhaustive matrices or unchanged reruns. No training/promotion is automatic.

## Historical handoff — systematic transition panel completed and verified

All four owner pairs pass in 3m47s under unchanged game v0.111.0, CLI54 /
Connector25 / worker23 / converter15 / layout12 / environment42. See
[the completed assessment](native-systematic-comparison.md) and
[owner-result evidence](evidence/native-systematic-owner-result-v1.json).

- [x] Independently reconstruct all 38 host deliveries and 23 matched states,
  including every final successor, in a 17.13-second saved-only assessment.
- [x] Verify Smith upgrades the selected card without changing deck size,
  repeated healing/Smith/Proceed effects, and two Happy Flower cycles from
  each saved starting value. All 28 activation snapshots have zero actions.
- [x] Verify uncapped execution, clean app/profile/archive resets, the frozen
  game and all 18,832 protected prior files/full original players/Adam.
  Keep every earlier failure unchanged; no new game or optimizer update occurs
  in assessment. These are privileged fixtures and no strength evaluation.
- [x] Update coverage with the observed atomic Smith card_selection root;
  leave other source UI selection variants and untested effects explicit.
- [ ] Reconcile previously valid source/saved compatibility evidence with the
  current tuple, then define one finite end-to-end/ending qualification for
  actual remaining gaps. Reuse passed evidence and targeted fixtures; the
  completed systematic panel needs no rerun or larger unchanged sweep.
- [ ] After the required compatibility gate, prepare varied fitting-only
  teaching and the separate interference comparison. Preserve the completed
  sibling card-zone audit. Training, broader admission, promotion and adaptive
  readiness remain ungranted; no new stage or owner command is frozen yet.

## Historical handoff — systematic comparison short checks passed

The frozen game and CLI54 remain unchanged. Official Connector25 / converter15 /
layout12 / shared environment42 fix rest aliases and wait for Happy Flower's
native activation display to settle. See [the systematic suite](native-systematic-comparison.md)
and [evidence](evidence/native-systematic-comparison-v1.json).

- [x] Inventory 24 surfaces and 193 compiled connector records / 1,135 properties,
  including body properties and nullable declarations. Keep inventory separate
  from paired semantics, live effects and remaining coverage.
- [x] Pass all 6,818 saved public frames, 116 generated comparisons, 38 original
  player probes, 199 connector tests and two reproducible host builds.
- [x] Match Rest/Proceed healing and map departure and Happy Flower's full cycle
  and energy effect, including both final successors. All ten actual deliveries
  independently reconstruct. Five actual counter-3 frames have zero authority.
- [x] Reject historical premature counter authority and a corrupted actual
  receipt without new games. Preserve failed development attempts and every
  prior source/result/model/full Adam; no training or app copies occur.
- [ ] Owner runs `bash scripts/compare-systematic-compatibility-v1.sh`, about
  5–12 minutes, four targeted save-based pairs with a 30-minute outer cap.
  It adds Smith, repeated rest choices and two complete Happy Flower cycles
  from different saved starting values. The fixed app and original game stay
  frozen. Uncertain/interrupted attempts are never retried. The panel is unstarted.
- [ ] Assess that result before any further compatibility admission or varied
  fitting-only teaching and interference comparison. No ordinary full-game
  strength, broad ending parity, training, promotion or adaptive readiness is
  granted by these diagnostics. Retain the completed sibling card-zone audit.

## Historical handoff — broader panel assessed; counter and rest gaps remained

The owner completed all four pairs/eight starts on 2026-11-02 in 999.55 outer wall
seconds, without a resource cap. See [the assessed result](native-reward-map-owner.md)
and [evidence](evidence/native-broader-compatibility-result-v1.json). The completed
v1 command is historical; no unchanged rerun or new game follows automatically.

- [x] Confirm both player-3 pairs match all 128 complete input/menu observations
  per host. Player 2/world417 matches 11 before Happy Flower counter 0 versus 3;
  world418 matches 112 before rest-site role/enablement/exit field differences.
  Complete menu keys agree at both first differences. Preserve all later divergent
  traces without treating them as matched effects.
- [x] Identify the stopped official action: world417/player2 has 72 completed
  acknowledgements, then Play Evil Eye returns not_delivered / stale_snapshot.
  The returned snapshot's sole non-transport change is Happy Flower counter 3
  to 0. All eight game/app/profile/archive shutdown/reset checks pass. Preserve
  this attempt without retry; do not conflate it with the old enemy-phase stall.
- [x] Explain raw-reconstruction=false: the coordinator's all-host delivery gate
  skipped its verifier. Preserve that original report. A separate saved-only
  assessment independently rebuilds 852 deliveries across seven completed host
  paths and 72 acknowledged deliveries in a declared diagnostic-only partial
  prefix, excluding rejected choice 73. Total 924 verify in 24.86 seconds, zero
  games/updates; every original journal, model/full Adam and source hash is exact.
- [x] Retain the isolated sibling actor card-zone/exhaustion audit: 48 controlled
  pairs / 96 actual-player comparisons, all distinctions preserved, 20 tests pass.
  It changed no active-run file and grants no training/native-effect admission.
- [ ] Inspect the native/official Happy Flower public counter source and settling
  lifecycle. Preserve actual amounts; a blind 0/3 alias or dropped counter is not
  a repair. Source-level cause and a qualified correction remain open.
- [ ] Repair exact rest-site option role, enabled/is_enabled and can_leave/
  can_proceed aliases with preserved current authority, false values, unfamiliar
  facts and raw action bindings. Add targeted saved/source/effect checks.
- [ ] Only after targeted qualification, freeze a new bounded owner comparison.
  No next command is frozen yet; do not replay world417/player2's stopped attempt
  or repeat a larger unchanged panel. Broader compatibility and ending parity
  remain unqualified; no training, promotion or adaptive controller follows.
- [ ] After compatibility qualifies, propose varied fitting-only teacher/student
  lessons with matched original/reference controls and a separate interference
  comparison. Preserve the completed encoder audit instead of rerunning it.

## Historical handoff — same-build broader canary prepared; owner run next

The owner requested this finite broader check on 2026-11-02. See [the current
guide](native-reward-map-owner.md) and [preparation evidence](evidence/native-broader-compatibility-v1.json).
The completed v15 panel and all older failures remain unchanged.

- [x] Freeze two fresh worlds, 417/418, both full original players and four
  paired prefixes under exactly CLI54 / official24 / worker23 / converter14 /
  layout11 / shared environment41. Check at most 128 choices per host or an
  actual ending. No game binary, adapter, numerical weight or Adam state changes.
- [x] Reuse the qualified frozen live driver and per-choice verifier. Add source-
  and checkpoint-bound orchestration, no-marker refusal for an open game, sealed
  evidence reuse after a clean pause and refusal to retry uncertain attempts.
- [x] Pass 22 focused regressions, strict types/lint/format and shell syntax.
  Final-source preflight passes in 10.19 seconds; all 728 saved v15 deliveries
  pass the new validation/coverage code in 1.05 seconds, with nine observed decision
  families and no genuine endings. These short checks launch zero games.
- [x] Scan 909 prior configuration/manifest files and 7,415 canonical seed names;
  select no outcome-dependent worlds. Protect all 1,519 current dependency/evidence
  files, both full originals and the completed v15 pass. Preserve the earlier
  unstarted coordinator preparation/preflight snapshot separately.
- [ ] Owner runs `bash scripts/compare-broader-compatibility-v1.sh`, expected
  20–35 minutes, one fixed app, four serial pairs and a 90-minute outer cap.
  Exact repository checks and saved reconstruction are included. Both long-run
  workspaces remain unstarted; no fresh stage follows automatically.
- [ ] Assess complete inputs/menus, actual checkpoint delivery, matched successor
  observations between decisions and reported family/transition/ending coverage.
  Do not claim unobserved endings or the final uncaptured successor. Ordinary
  losses can qualify ending controls; this is not a playing-strength evaluation.
  Preserve any enemy-phase stall without replaying world415 or uncertain actions.
- [ ] After required compatibility scopes qualify, resume the saved actor
  card-zone/exhaustion audit, varied fitting-only lessons and a separate
  shared-policy-interference comparison. No training, promotion or adaptive
  controller is authorized by this diagnostic alone.

Final repository/source-check receipts are recorded after freezing all files in
`artifacts/native-broader-compatibility/preparation-v1/final-handoff-v1.json`.

## Historical handoff — four targeted controls pass; broader qualification next

The owner completed v15 on 2026-11-02. See [the assessed result](native-reward-map-owner.md)
and [its evidence](evidence/native-reward-map-panel-result-v1.json). Preserve the
earlier blocked v14 result, all uncertain markers and both full original players/Adam.

- [x] Pass all four controls under unchanged CLI54 / official24 / worker23 /
  converter14 / layout11 / shared environment41: 57/77/118/112 complete matching
  choices per host, 364 decision pairs and 728 verified host deliveries. All
  eight starts reach their targets and restore the app/profile/archive cleanly.
- [x] Recheck 337 source and 1,510 evidence files, all child identities, exact
  verifier schemas/hashes/counts and successful uncapped verification receipts.
  Saved-only assessment takes 18.05 seconds; no new games or updates occur.
- [x] Account for the whole owner run: 932.78 outer wall seconds (15.55 minutes),
  390.75 CPU seconds, 988,168,192 bytes peak RAM and 2,455,195,574 bytes final
  storage including the shared app. No cap, app copy or optimizer update occurs.
- [x] Keep scope explicit: the fresh world416 selector prefix completes all
  112 choices per host; it does not establish the cause of world415's old
  enemy-phase stall. That uncertain action/seed and the scripted world412 potion
  replay are not repeated. Broader compatibility and playing strength remain
  separately unqualified. The completed v15 panel needs no rerun.
- [ ] Prepare a separately frozen finite broader compatibility proposal under
  this same tuple, covering representative public decisions/successor effects and
  genuine ending controls, with fresh worlds, bounded owner-run work and exact
  new batch/resume gate bindings. Reuse qualified evidence; do not require every
  content combination. No broader plan or next owner command is frozen yet.
- [ ] After the required compatibility scopes qualify, use saved public records
  for the actual actor's card-zone/exhaustion distinction audit. Then propose
  varied fitting-only teaching with matched original/reference controls and a
  separate shared-policy-interference comparison. Fresh full-game terminal wins
  at equal whole-run compute remain primary; no new training, promotion, larger
  unchanged experiment or adaptive controller follows automatically.

## Historical handoff — qualify the reward/map ownership correction

See [the result and correction](native-reward-map-owner.md). The owner finished
the complete v14 panel; it did not hit a resource cap. Preserve its completed
negative result, all earlier markers and both original full players/all Adam.

- [x] Confirm the three current-source passes: reward glyphs 57, status titles
  77 and modified deck 118 complete matching choices per host, with all 504
  deliveries independently verified and clean app/profile/archive restoration.
  The map-travel guard passes the earlier modified-deck regression.
- [x] Reconstruct the fourth native prefix's 112 choices and the official host's
  47 acknowledged choices before the first difference. After reward Continue,
  both hosts show the map and discard the same potion. CLI then reopens 11 skipped
  Gold; official stays on the map. Later divergent states are not matched evidence.
- [x] Implement CLI v54 presentation ownership: retain the exact dismissed native
  RewardsSet behind the open map, while allowing genuinely new reward/card owners
  to appear. Clear presentation ownership on room travel/reset. Never remove or
  claim rewards to simulate UI closure; reject stale background reward actions.
- [x] Reproduce both source builds independently, with the actual game DLL exact.
  Eight executable ownership controls pass, including equal-valued distinct reward
  owners and nested/new owners. Four isolated native fixtures reproduce the old
  bug for both discard and AnyTime use, and verify both repaired effects in 10.03
  seconds. Gold is unchanged; Fruit Juice actually increases maximum HP.
- [x] Pass both saved banks under shared environment 41: 5,889 historical and 676
  newly saved frames, plus the same 20 artificial envelopes in each bank. All
  13,172 frozen-policy probes pass, with 16,903 prior files and both full original
  players/all Adam unchanged. No official game or full run was launched by repair.
- [x] Prepare the finite new-source panel and six coordinator regression tests.
  Use the three fully completed, independently verified cases as explicitly
  labelled regressions; use fresh world 416 for the stopped selector case.
  Preserve world 415 and its final accepted End Turn without a ready successor;
  never replay that uncertain case. The existing scripted world 412 potion replay
  is not repeated. New-source evidence does not relabel earlier runs.
- [ ] Owner runs `bash scripts/compare-selection-flows-v15.sh` (about 15–25
  minutes). One shared app, four pairs, ten minutes per pair plus shutdown reserve,
  and a 90-minute outer allowance. Exact repository checks are cached separately.
- [ ] Investigate the separate official enemy-phase stall if reproduced or if a
  source-level cause is found. The saved stop has round 2/enemy phase, 56 submitted
  choices and 55 completed acknowledgements. It occurred after divergence; its
  cause and repair are not established by the reward/map fix. Do not bypass
  readiness checks, retry End Turn or count its partial trace as ordinary PPO.
- [ ] Assess the new panel before broader compatibility, learning or promotion.
  If historical training used the affected reward/map transition, audit that data
  separately before reuse; do not assume it explains earlier poor learning.
  No training, adaptive controller, promotion or automatic next stage follows.

## Historical handoff — continue three unstarted controls after the summary repair

See [the consolidated repairs and current handoff](native-modal-display-repair.md)
and [the coordination evidence](evidence/native-modal-coordination-v2.json).
Both original full players/all Adam remain exact. The game, bridge, converter,
four control recipes, seed set and launch limits are unchanged.

- [x] Assess the owner's v13 run. The reward control passes all 57 complete
  public-input/action pairs with verified app/profile/archive restoration.
  The independent verifier reconstructs all 114 native/official choices.
- [x] Identify the summary failure: the coordinator expected `evidence` in a
  verification report whose real contract binds the source report, verifier hash
  and per-host counts instead. This is not another game compatibility failure.
  Preserve the failed summary, its active marker and all completed case evidence.
- [x] Implement coordinator v2 against that actual producer contract. Check the
  exact source/engine/helper identity, verifier code hash, both host counts and
  successful uncapped verification. Retain transitive raw evidence hashes.
- [x] Add 14 regression tests, including a saved-only adoption followed by a full
  mocked continuation. Never launch the completed case; run only cases 2–4.
  Test changed evidence, invalid verification, capped checks, incomplete shutdown,
  uncertain cases and matching prefixes shorter than the declared target.
- [x] Freeze a separate coordination ledger while retaining the same finite plan.
  Saved-only adoption records the completed 57-choice control and immutable unit,
  with zero new games or verification replay. All 15,721 protected prior files
  remain exact. The three remaining control workspaces are unstarted.
- [ ] Owner runs `bash scripts/compare-selection-flows-v14.sh` (about 15–25
  minutes). This reuses case 1 and completes only the existing status-title,
  modified-deck and fresh selector/potion controls. Up to six new host starts;
  no repeat of the scripted p3/world412 replay. Exact repository checks are
  cached separately; the unchanged 90-minute outer cap covers all work.
- [ ] Assess the four completed controls before a broader comparison or learning.
  No training, promotion, adaptive controller or automatic next stage follows.

## Historical handoff — owner-run targeted comparison with the map-transition guard

See [the consolidated repairs and evidence](native-modal-display-repair.md).
Both original full players/all Adam and all prior source tuples remain exact.
No training, promotion, game copies or automatic long follow-up are authorized.

- [x] Implement all four original source repairs and targeted regressions:
  reward image glyphs, actual status titles, per-copy modifier/upgrade values,
  and owned potion permissions/identity under combat card selection.
- [x] Pass the v39 saved-only audit and current 57/77-choice reward/title controls,
  independently reconstructing all 114/154 delivered choices.
- [x] Pass the owner's single authorized potion replay: 112 matching inputs per
  host, with a queued discard, card answer and actual potion removal. Independently
  reconstruct 112 native inputs/receipts and recompute the 109 frozen choices.
- [x] Preserve the new modified-card control's interrupted official attempt:
  native 118 choices, official 82 acknowledged choices, first difference at 67.
  Independently reconstruct all 200 choices/receipts in 23.65 seconds. Preserve
  both attempt markers and the blocked worker. It is diagnostic-only evidence.
- [x] Identify old Wood Carvings controls with the new floor after a map choice,
  while native has Unrest Site. The earlier v38 and current v39 native 118-input
  prefixes are identical; do not attribute later unmatched states to card logic.
- [x] Implement a separately versioned native map-travel readiness guard. Suppress
  mutation and atomic advancement while the game's IsTraveling flag spans old-room
  exit; classify even a transient unknown surface as settling. Preserve other
  snapshot states when travel completes. All 190 Host tests pass; candidate v24
  reproduces twice from source patch v23. This guard is not live-qualified yet.
- [x] Inspect the stopped worker without resetting it: all 435 original app files
  and the account/frozen archive remain exact, no game process runs, and all five
  known added connector/settings files plus the original worker marker are backed
  up separately. Prepare the checked restoration procedure; delete nothing.
- [x] Owner approves inspected worker restoration and one longer replacement
  diagnostic. Restore the same app in 13.47 seconds, remove only the five backed-up
  additions, and recheck the original inventory. Every failed-attempt file and its
  case/plan markers remain intact; no failed game is resumed or replayed here.
- [x] Freeze CLI 52 / official candidate 24 / worker 23 / shared environment 40.
  The new saved audit passes 5,889 observations, 20 artificial envelopes and 11,782
  frozen-policy probes in 164.46 seconds; all 15,721 protected prior files remain
  exact. Both original full player/Adam files remain unchanged.
- [x] Prepare and preflight one finite owner-run panel: four separately verified
  matched controls, ten minutes per pair, a 45-second shutdown reserve, and
  15-minute per-case launch allowances. Reuse completed results; record independent
  clean-reset delivery gaps, but stop on an unverified worker. Ten operational
  regressions pass. The 90-minute outer cap includes both results and the one fixed
  app in storage accounting. No panel game has started; world 415 remains fresh.
- [ ] Owner runs `bash scripts/compare-selection-flows-v13.sh` (about 20–30 minutes).
  This requalifies all four targets under the final source tuple and the approved
  replacement for interrupted p3/world411. The potion case p3/world412 is not
  replayed again. No broader canary, training or automatic next stage follows.
- [ ] Assess the four controls before freezing a broader comparison; source changes
  require fresh qualification. The earlier canary-v2 plan remains unfrozen.
- [ ] Establish broader input/action compatibility before returning to learning.

## Historical handoff — final potion-reference qualification

See [the four repairs and current evidence](native-modal-display-repair.md).
Preserve both original full players/all Adam, every prior tuple and all failed
attempts. No training, promotion or controller follows automatically.

- [x] Implement native reward glyph rendering, virtual localized power titles,
  and game-owned per-copy dynamic previews with cleanup and detached upgrades.
- [x] Reproduce CLI v52 and connector v22 with the game assembly unchanged.
  Pass 183 Host tests, four native modifier/title/effect fixtures, and independent
  Sharp damage verification. Preserve the initial tool-runtime and fixture errors.
- [x] Match all 57/77/118 reward/title/modifier choices on source tuple v38;
  independently verify every choice and app/profile/archive restoration.
- [x] Preserve the potion control's strict duplicate-reference failure before an
  official launch: 108 acknowledged choices/109 inputs, pending last choice,
  stopped worker and unchanged markers. Quarantine it from ordinary PPO.
- [x] Assign one global-HUD reference per owned bottle and needed player target,
  retaining all inspectable context/inventory. Worker v23/atomic v6 share the
  declared identity. Tighten synthetic tests to reject duplicate IDs; all 20 pass.
- [x] Pass the strict native Headbutt/potion fixture: accepted discard waits behind
  the card answer, cannot be enqueued twice, drains after the answer and returns
  to combat with the bottle removed. Clean shutdown; 6.47 seconds, zero updates.
- [x] Pass the v39 saved audit: 5,889 observations, 20 artificial envelopes,
  11,782 frozen-policy probes and exact scalar/layout reconstruction. All 14,753
  protected prior files and both original full player/Adam states remain exact.
- [x] Owner authorizes one isolated replay of the known potion-selector case.
  Preserve the interrupted attempt; use the earlier fully completed verified
  case as the reference and explicitly label the scripted discard/answer suffix.
- [x] Pass the authorized replay in 232.06 seconds: all 112 public inputs match,
  one exact official queued-discard ID, no duplicate enqueue, card answer drains
  it and actually removes the bottle. All official app/profile/archive checks pass.
  Independently reconstruct 112 inputs/receipts and recompute 109 frozen choices
  in 12.51 seconds. Preserve the read-only verifier's two harness errors.
- [ ] Complete final repository checks before live continuation.
- [ ] Qualify the final tuple with current matched controls and the explicit
  official queued-discard/card-answer test, then prepare the next long owner task.
  Do not treat v38's controls as v39 live qualification or start training.

## Historical handoff — reward glyphs, status titles, modified cards and selector potions

See [the completed comparison assessment](native-star-cost-canary-result.md).
Both original full players/all Adam and every historical source/result stay exact.
This is an input-compatibility follow-up, with no learning or promotion.

- [x] Assess completed v10: eight clean 128-choice host prefixes, no cap or recurring
  star-cost rejection, 1,039.61 seconds, zero complete matching pairs. Preserve all
  first differences after 56/76/117/109 identical decisions and the full journals.
- [x] Independently reconstruct all 1,024 checkpoint choices and delivery receipts
  from saved observations in 24.37 seconds; no games or optimizer updates occur.
- [x] Identify four actionable first differences. Treat later divergent states as
  unmatched evidence, not independent compatibility bugs or a compatibility rate.
- [x] Normalize Energy Potion/reward rich-image glyph syntax using the shared
  visible-text contract; retain each glyph's identity, order and multiplicity.
  Cover varied reward kinds and glyphs, not a hard-coded potion description.
- [x] Resolve actual localized native status titles, preserving definition IDs,
  amounts and descriptions. Test missing-key diagnostics and other status models.
- [x] Render permanent per-copy modifiers in current deck descriptions: Nimble
  amount 2 Defend must expose the correct modified Block. Verify actual effects
  and descriptions together across representative enchantments/upgrade contexts.
- [ ] Repair potion permissions, owned identity and context under nested combat
  selectors. Qualify the actual official selection owner's current controls:
  CLI currently adds Discard during Headbutt selection; the official menu omits
  it while its sparse summary says can_use true. Do not trust that summary alone
  or remove public potion facts just to force equality. Preserve exact bindings.
- [ ] Add regressions from all four saved first differences and short targeted
  native/official controls before freezing a replacement broader comparison.
  Preserve prior tuples; no automatic long run, training, promotion or controller.
- [ ] Establish broader complete input/action compatibility before new learning.
  Finite controls do not prove all mechanics or playing strength. The completed
  v10 plan only reuses its result; repeating it cannot repair these differences.

## Historical handoff — typed star costs before joining card views

See [the diagnosis and repair](native-star-cost-normalization.md). Preserve both
full original players/all Adam and every prior source and result. No learning or
promotion occurs in this compatibility repair.

- [x] Reconstruct all 96 acknowledged choices from interrupted canary v6; reproduce
  the same Particle Wall rejection. Preserve both markers and forced-stop evidence.
  No official game starts; this partial episode is never ordinary learning data.
- [x] Normalize declared numeric/text star costs before joining current card views.
  Keep zero, absent cost, X, different costs and distinct physical copies separate.
  Leave all other public facts, permissions, resource types and raw bindings intact.
- [x] Independently restore exact raw scalar types as well as the pre-layout graph;
  make genuine conflicts and unsupported typed values fail explicitly.
- [x] Verify the rejected saved observation, all prior 96 unchanged inputs/choices,
  seven scalar tests and fifteen existing flow regressions on the repaired converter.
- [x] Pass the native Particle Wall/Gambler's Brew selection fixture: three separate
  two-star copies, combat/pile context, one committed choice and clean shutdown.
  Preserve the earlier diagnostic acknowledgement error; use a separate new seed.
- [x] Pass the 4,861-frame/20-envelope audit, 9,728 frozen-policy probes and exact
  raw scalar/layout reconstruction. Pass all 8/8/64 full input/menu controls;
  independently verify all 160 choices and app restoration. All 11,594 protected
  files and both original full players/all Adam remain exact.
- [x] Freeze/preflight the next finite comparison on fresh worlds 411/412; keep
  reserved worlds 409/410 excluded and all interrupted evidence unchanged.
- [x] Owner completed v10 in 1,039.61 seconds, within budget. Eight clean prefixes
  and all 1,024 choices independently verify. The star-cost crash is absent, but
  complete input equality still fails in all four pairs after 56/76/117/109 choices.
  Preserve the result. The current handoff supersedes this completed launcher.
- [ ] Establish broader complete input/action compatibility before new learning
  or promotion. Finite controls are not exhaustive coverage or strength evidence.

## Historical handoff — generated choices, owned previews and merchant reads

See [the repair and evidence](native-selection-owner-read.md). Preserve both original
full weights/all Adam and every prior result. No new learning or promotion occurs.

- [x] Assess completed canary v5: eight clean prefixes within budget, zero complete
  matching pairs, first differences after 1/1/53/1 equal inputs. Verify all 964 choices.
- [x] Fold the repeated owned relic preview only when all its same-owner facts are
  present under the persistent scoped preview; retain unknown/conflicting facts.
- [x] Replace the generated-choice legacy fallback with actual native ownership,
  initial presentation, card copies/views, header and canSkip. Preserve exact bindings
  and both optional/mandatory choices. Retain full combat context and public piles.
- [x] Inspect generated-choice combat callers; pass the native Discovery fixture with
  three offered copies, actual Skip permission and clean shutdown. Keep failed probes.
- [x] Consolidate only exact same-card merchant catalog/detail duplicates, retaining
  all prices, views, unknown fields and reversible source evidence.
- [x] Preserve the initial merchant control's next difference at 54 after buying a
  potion. Repair null-item visibility at the source for all three item groups, keep
  removal-service visibility separate, and remove the false Card removal potion label.
- [x] Reproduce CLI v51 twice, unchanged game DLL/connector v20. Final worker v21,
  converter v13/layout v10/environment v36 declare the changed public interface.
- [x] Pass all final 8/8/64 matched input/menu controls (45.95/
  50.75/119.83 seconds); independently reconstruct
  all 160 choices. All app/profile/archive checks pass, with zero app copies/updates.
- [x] Pass 15 Node regressions and the 4,760-frame/9,526-probe saved audit;
  10429 prior files and both full players/all Adam remain unchanged.
- [x] Freeze/preflight the next finite comparison, with the exact-file repository
  gate separate from gameplay. Preserve all development negatives and old launchers.
- [x] Owner ran v9. Canary v6 stops at observation 97 with a typed star-cost
  conflict after 96 acknowledged native choices; no official game starts.
  Preserve the interrupted workspace and both reserved worlds. Current handoff
  supersedes this launcher; never clear markers or replay it as a clean case.
- [ ] Qualify full broader inputs/actions/effects before new learning or promotion.
  Finite compatibility controls do not prove all mechanics or playing strength.

## Historical handoff — reward guidance, card-copy identity and enchantment previews

Canary v3 is complete: eight clean prefixes, all 880 delivered model choices
independently verified. It still has zero fully matching pairs. The repeat command
displayed the saved 914.72-second result in five seconds; it started no new games.
Preserve both original full players/all Adam and every earlier result.

- [x] Separate delivery success from input equality: the old `control_pass` label
  was misleading while `full_prefix_input_equivalence` was false. New reports/exit
  status require both; preserve the old report as historical evidence.
- [x] Trace all three extra reward decisions to `combat_reward_ftue`. It interrupts
  Continue, then returns to the unchanged reward owner. The prior timing fix missed
  that guidance sequence; a tutorial is not proof that the reward owner departed.
- [x] Implement one committed model Continue across the exact warning, its native
  non-gameplay dismissal, and a freshly revalidated final confirmation. Retain the
  original owner, full state/menu and accepted receipts. Unknown delivery, changed
  state or repeated warnings stop without retrying uncertain gameplay input.
- [x] Anchor selector-copy labels to ordered visible selection positions before
  unordered pile/deck reads, then resolve unordered ties with those canonical labels.
  Retain all distinct physical copies, current facts and exact raw action bindings.
  Keep selector/hand order and all unknown facts. Layout v8 is separately identified.
- [x] Reconstruct the captured seven-card Headbutt state: complete inputs/menus
  match, all seven copies remain separate and the full original layout restores.
  Replay the saved warning → rewards → map trace without a new game or update.
- [x] Pass eight targeted Node regressions and 18 focused Python tests. The saved
  audit passes 3,436 frames, 20 generated envelopes and 6,886 frozen probes; all
  8,461 protected prior files remain unchanged. No native or official game binary
  changes: CLI v46 / connector v20 / worker v16 remain pinned, shared environment v29.
- [x] Qualify the actual warning/confirmation flow in a separate 64-choice
  clean-case regression: all complete inputs/menus match in 149.59 seconds; all
  128 delivered choices independently verify, including the real warning/confirmation.
- [x] Execute the separate 112-choice selector regression. The duplicate-copy repair
  works through decision 106, including the original seven-card mismatch at 96.
  It then exposes missing native Spiral enchantment preview and event body alias
  at 107. All 224 delivered choices verify. Preserve this negative control; never
  shorten the prefix or drop public enchantment facts to hide its failure.
- [x] Export pending enchantment identity, actual amount and native formatted text
  from the exact native command, using a display clone. Preserve applied card facts;
  do not infer effects from event names. Keep the preview in atomic selection inputs.
  Normalize only declared provenance labels and the event-owner body alias, retaining
  effect/name/amount, unfamiliar fields, source reconstruction and conflict rejection.
- [x] Freeze new source versions and reproduce both CLI builds without altering the
  game DLL or official connector. Preserve the initial misplaced-export development
  build v47. V48 then exposes a patch-state type collision before any policy
  decision or official start; preserve its stopped worker/markers and nonexecution
  review. V49 separates the two capture scopes and passes an actual native event
  preview fixture in 6.82 seconds. Worker v17/layout v9 declare the new observation.
- [x] Repeat both targeted controls on v49: 64/64 inputs/menus match in 154.00
  seconds, including the actual warning/final confirmation; 112/112 match in 224.54
  seconds, including distinct copies, a committed pack and the actual Spiral preview.
  All 352 choices independently reconstruct. All app/profile/archive checks pass.
- [x] Pass 11 targeted Node regressions and 18 focused Python tests. The exact v49
  saved audit passes 3,790 frames/20 envelopes/7,594 frozen probes; all 9,043 prior
  protected files remain unchanged. Preserve both complete original weights/all Adam.
- [x] Freeze/preflight the new finite fresh-world comparison after both controls
  and independent witnesses pass. Its exact-file repository-check gate runs
  separately before gameplay. Preserve all uncertain earlier attempts and receipts.
- [x] Preserve the frozen runtime after a cosmetic line-wrap failure: one explicit
  formatting exception, exact source SHA/identical formatted AST regression, with
  full lint/type/behavioral coverage unchanged. Format future versions before freezing.
- [x] Owner completed v5 in 928.52 seconds: all eight prefixes/964 choices verify,
  but all four inputs differ. Preserve it; the current handoff supersedes its launcher.
- [ ] Full input/action/effect compatibility still gates new learning or promotion.
  These diagnostics do not establish stronger play or exhaustive game coverage.

## Historical handoff — reward departure, combat potions and merchant entry

Preserve both original complete players/all Adam and the completed canary v2.
The batch finishes within its budget; it does **not** qualify compatibility.
Three official prefixes execute their full 128 choices and one stops during
hand selection. All four pairs have input differences (after 48, 88, 6 and 88
matching decisions). Game delivery success and full input equality are separate.

- [x] Inspect all four first differences and the saved observations, choices,
  native receipts and game log together. Preserve the uncertain player-3/world-403
  selection; do not replay that attempt or clear its markers.
- [x] Keep a closing reward panel out of the next policy decision, even when its
  snapshot/signature changes. Wait for actual reward-family departure after the
  single accepted Continue; never click it again to accelerate closure.
- [x] Fix combat potion identity to the same owned inventory occurrence. Keep
  distinct copies, actual belt slots, current use/discard permission, target
  operands and hover facts. Match the existing official command labels and typed
  views; do not merge different potions or infer new legal actions.
- [x] Fix hand-selection completion: the hand display persists after its selection
  mode finishes. Retain the exact chosen-card transaction and native confirmation;
  use selection-mode lifetime instead of waiting for the whole hand to disappear.
- [x] Export the current player-openable merchant catalog while inventory is closed,
  retaining stock/prices/previews and disabled purchase authority. Match the actual
  shop-room controls; opening/closing inventory remains a real model decision.
- [x] Preserve all previous source tuples. Native CLI v46 and official connector
  v20 reproduce twice; worker v16/shared environment v28 declare the new exports.
  Saved reconstruction matches the captured potion and shop inputs/complete menus.
  This reconstruction is diagnostic evidence, not execution of a repaired game.
- [x] Pass 170 exact-game Host tests, connector portable checks, five new targeted
  Node regressions and 13 focused Python tests. Audit 2,550 saved frames plus 20
  generated envelopes / 5,122 frozen probes with 5,973 prior files unchanged.
- [x] Make progress output distinguish `INPUTS MATCH` from `INPUT MISMATCH` and
  report game delivery separately. Preserve original comparison denominators.
- [x] Pass the short paired control: 32 complete input/menu pairs in 86.47 seconds,
  all 64 delivered choices independently verified, exact selected pack added and
  app/profile/archive restoration verified. Separately exercise all 14 native
  closed-shop offers with no purchase authority. No uncertain seed is replayed.
- [x] Full repaired-code repository check passes 2,587 tests, strict types on 640
  files and C# protocol in 150.35 seconds. Preserve its exact resource receipt.
- [x] Freeze/preflight the replacement finite comparison on fresh worlds 405/406,
  both originals. Keep 30 minutes for the batch, six minutes per pair and a separate
  cached repository-check allowance. Its workspace is unstarted.
- [x] Owner completed canary v3: all eight prefixes execute cleanly, but all four
  inputs differ. Preserve its saved result, verification and cached-display launch.
  The current handoff above supersedes this historical launcher.
- [ ] Qualify complete broader inputs/deliveries and remaining consequential effects
  before compatibility admission or another learning intervention. No training,
  promotion, adaptive controller or automatic follow-up is authorized by a prefix.

## Historical handoff — consistent upgraded-card titles

See [the card-title repair](native-card-title-repair.md). Preserve both complete
players/all Adam, the stopped native prefix and every previous receipt.

- [x] Assess the owner run: repository checks pass 2,585 tests in 151.71 seconds.
  The comparison stops after 50 native choices / 51 frames, before any official
  prefix or completed pair. Preserve the stopped process, markers and world 401.
- [x] Trace the conflict to one upgraded card copy: the transform selector says
  `Strike`, while the deck says `Strike+`. Keep the strict conflict rejection.
- [x] Replace all six CLI base-name export lookups with the game's current title.
  Keep definition, physical identity, upgrades, costs and all other facts explicit.
  CLI v45 reproduces twice; shared environment v27 binds the new assembly without
  changing the frozen game, converter, official connector or either player's numbers.
- [x] Add six title/copy/conflict regressions. Reconstruct the captured state using
  its already visible same-copy deck title: all 12 choices pass the SDK decoder.
  This remains diagnostic substitution, not native execution or training evidence.
- [x] Pass the saved audit: 1,642 frames, 20 envelopes, 3,306 frozen probes and
  3,981 unchanged prior files. Prepare/preflight a 32-choice regression on the
  previously completed, clean, independently verified world 556.
- [x] Owner closes Steam. Four isolated native rendering fixtures pass: base and
  upgraded Strike, upgraded Defend and upgraded Cold Snap; all three-copy names,
  upgrade flags, SDK decoding and clean shutdown agree. No learning or app copies.
- [x] Complete the paired regression in 86.64 seconds: all 32 complete inputs/menus
  match per host, all 64 choices/receipts independently verify and exactly the
  selected pack is added in both hosts (11 → 14 cards). All prior cards stay exact.
- [x] Full repaired-code repository check passes 2,586 tests, strict types on 633
  files and C# protocol in 150.81 seconds. Preserve the earlier passing receipt.
- [x] Freeze and preflight the replacement four-pair comparison on fresh worlds
  403/404 with both originals. Keep 128 choices per host, 30 minutes overall / six
  minutes per pair, one fixed app and the separate repository-check allowance.
- [x] Owner completed the v2 batch within its allowance. Preserve its four-pair
  blocked result: all four inputs differ, and one official selection is uncertain.
  Its launcher is historical; the current handoff above supersedes it.
- [ ] Finish broader matching and consequential merchant-removal effects before
  compatibility admission or another learning intervention. These finite controls
  do not prove all card interactions or stronger full-game play.

## Historical handoff — rewards, packs and shop removal

The owner requested these consolidated compatibility repairs and enough launch
allowance for the entire comparison. Preserve both original full players/all Adam,
old canaries and failed development attempts. See [the flow guide](native-selection-flows.md)
and [#149](https://github.com/benyanc/spireshift/issues/149).

- [x] Record the previous canary as complete: four pairs/eight starts, 790 delivered
  policy choices. Card rewards/packs still differ; the last merchant removal is
  blocked by the catalog-owner validator. No parity or training admission granted.
- [x] Export actual reward cards, previews, physical identities and detail reads,
  preserving the native alternatives and mandatory/optional distinction. Keep a
  pending reward's stable identity when Skip returns to the reward list.
- [x] Define one committed pack choice. The official adapter verifies the chosen
  preview and confirms it once before acknowledging the model; ambiguous or
  uncertain input is preserved, never resubmitted.
- [x] Preserve the merchant owner and complete read-only catalog under removal.
  Require that owner and the atomic-card contract; do not manufacture purchases
  from an overlay. Keep native prices, stock, affordability and permissions.
- [x] Catch incomplete view metadata through the full SDK decoder. Retain both
  failed native development attempts and their source snapshots; never replay
  their uncertain worlds. Test empty-belt aliases without dropping nonempty facts.
- [x] In the completed short check, execute 32 choices per host and a real pack
  preview/confirm (two UI steps for one model choice); independently reconstruct
  all 64 choices/receipts. Preserve its boss-name/input mismatch as negative evidence.
- [x] Repair encountered native encounter-title and public combat-pile preview
  omissions. Use the game title/current public powers, not monster-name guesses
  or an unpowered pile description. No game rules or learner weights change.
- [x] Unify the completed combat rewards view with the empty reward list, retaining
  the public boss-room fact and waiting for Continue to leave its owner. Map the
  rendered event page to one body field without changing text or named amounts.
- [x] Declare read-only merchant slots before the worker's diagnostic graph. Keep
  combat-context card views without registering the same selectable hand card twice;
  the actual saved Armaments failure now passes the full decoder with three unique
  card referents. Preserve its failed world; no uncertain seed is replayed.
- [x] Restore actual public pile reads during combat selection and retain other
  inspectable combat operands exactly once. The saved Headbutt input/menu now
  matches the official frame, including each selected pile copy. Keep hidden draw
  order excluded. Render status-image glyphs without losing their visible meaning.
- [x] Keep launch budgets separate from immutable experiment and completed-unit
  identity. Required repository checks have a separate 10-minute allowance, cached
  against exact files. The next four-pair plan allows 30 minutes overall, six minutes per
  pair, isolated profiles, one fixed app and no extra game attempts or training.
- [x] Qualify the final CLI v44 / official v19 / worker v15 / shared helper v10 /
  layout v7 / shared manifest v26 tuple. Offline v13 passes 1,642 saved frames,
  20 envelopes and 3,306 frozen probes with 3,609 prior files unchanged. Targeted
  control v11 matches all 32 complete inputs/menus in both hosts in 88.16 seconds;
  all 64 choices/receipts independently reconstruct. Both decks add exactly the
  chosen pack's three cards (11 → 14), with prior visible cards unchanged.
- [x] Focused checks pass 11 Python tests / 26 Node cases, strict types on 632
  source files, style and C# protocol. Preserve the earlier full-check cap as
  incomplete. The owner launcher runs the full final repository check first.
- [x] Owner attempted the broader v1 plan after the full repository check passed.
  It stopped in the first native prefix on a conflicting upgraded-card title.
  No pair completed. Preserve that workspace; the current handoff above replaces
  its next command after the separately qualified repair.
- [ ] Qualify remaining consequential selector/potion effects and large selection
  domains if encountered. Current bounds reject more than 512 answers wholesale;
  source inventories and finite controls do not prove every mechanic combination.
  Full input/action/effect compatibility still gates new learning and promotion.

## Historical handoff — one model choice for a committed card answer

The owner selected the semantic committed-card contract. Keep both original full
players and every Adam moment/counter unchanged; no learning or promotion follows.
See [the selection guide](native-semantic-card-selection.md).

- [x] Implement all ordered legal card answers, legal empty answers and separate
  cancellation, with exact physical card identities, selection flags, current owner
  and full preview/detail facts. Reject oversized domains rather than truncate.
- [x] Implement official select → preview → confirm execution with native current
  owner/control checks, no repeated uncertain input and authenticated completion
  before acknowledging one model decision.
- [x] Preserve prior runtime tuples. CLI v40 uses the game's description-existence
  and formatting rules; retain v39's blocked Neow attempt and source snapshot.
  Official v16 and native v40 reproduce independently from fresh builds.
- [x] Saved audit: 832 recorded frames + 20 generated envelopes, 852 exact
  reconstructions/raw bindings, 1,694 frozen probes and 3,119 unchanged prior files.
- [x] Targeted ordered/empty/cancel, physical-copy, preference, pending, changed
  target, exact completion and read-enumeration tests; no model fitting.
- [x] Qualify all four complete inputs/action menus and deliveries in both hosts:
  actual card removal uses two native UI steps for one model choice. All eight
  choices/receipts independently reconstruct; both decks lose exactly the chosen
  Strike copy, with every other visible card unchanged (11 → 10 cards).
- [x] Use four public starting-menu observations with zero actions/outcomes to
  target the selection scenario. Preserve the earlier reward mismatch; layout v6
  maps its actual skip control and known display colors without inventing choices.
- [x] Final audit grows to **845 frames + 20 envelopes**, **865** reversible
  reconstructions/raw bindings and **1,720** frozen probes. Preserve all **3,119**
  prior files. Active tuple: CLI v40, official v16, shared layout v6/manifest v14.
- [x] Owner completed the historical semantic-selection canary: four pairs/eight
  starts, 790 delivered choices, with reward/pack differences and the merchant
  removal stop preserved. It grants no compatibility admission. Do not rerun its
  launcher; the current handoff above names the repaired comparison.
- [ ] Add specific shipped effect fixtures for remaining selector families and
  noncombat potion controls; the current source/tests do not establish their effects.
  Include nonzero/X star costs in cross-character selector/detail views, rather
  than inferring coverage from ordinary energy-only cards.
- [x] Repository checks: **2,573 tests**, **613** strict-typed files and C# protocol
  pass in **146.25 seconds**. The latest targeted suite separately passes 12 Python
  tests / 20 Node cases, with 20 C# transaction/permission checks.
- [ ] Resolve large selection domains if reached, then qualify common inputs and
  current checkpoints before the next learning intervention. Keep broader curricula,
  zone/exhaustion distinction and shared-policy interference in the learning backlog.

## Historical handoff — common official/CLI layouts and exact comparison worlds

The owner requested the remaining input repairs and targeted compatibility tests
under [#149](https://github.com/benyanc/spireshift/issues/149). Preserve both original
full players/all Adam and every old source/result. No training, promotion or
adaptive controller follows this work.

- [x] Identify a real setup mismatch: official `SeedHelper` changes O/I to 0/1,
  while the CLI accepts literal seeds. Require already canonical recipe seeds and
  verify the official mounted seed through authenticated provenance outside the
  model. Exclude previously attempted worlds and their aliases.
- [x] Implement separately versioned typed owner/duplicate/layout conversion,
  reversible evidence, exact current raw action bindings, source-scoped card
  stats/descriptions/selection, and complete optional choices. Unknown facts,
  foreign owners, nonzero block and later-act local floors remain explicit.
- [x] Consolidate CLI v38 / official connector v15 / worker v13 exports: event
  metadata, visible card keywords/preview/upgrade/affliction information,
  current enemy-intent amounts and discardable potions. Preserve the game DLL.
  Both native/official fresh builds reproduce independently.
- [x] Add protocol/status/settling, startup deadline and actual-seed tests, plus
  card-copy costs, zero/X star costs, named status owners, selection, repeated
  rest, optional Skip and Foul Potion's merchant-target regressions. Card star
  cost normalization does not change unrelated numeric fields.
- [x] Save the development filter/shop failures, startup stop and intermediate
  tuples. No uncertain action or prior seed is retried. Initial four-step matched
  live check reaches combat with identical inputs/keys/choices and clean reset;
  independently reconstruct all eight inputs, choices and actual receipts.
- [x] Keep **3,018** prior pinned files, both complete originals and every Adam
  moment/counter unchanged (5,658 / 6,045). Changed input metadata is explicit;
  unchanged numerical weights do not promise unchanged probabilities.
- [x] Final saved bank: **823 frames + 20 envelopes**, all **843** reversible
  conversions/raw bindings pass and **1,676** frozen-player input probes pass.
  Zero games/updates in this audit. The earlier live prefix matches through first
  combat; later fresh worlds correctly expose belt and selection-protocol gaps.
- [x] Implement official noncombat potion-HUD controls with exact current
  owner/slot/target checks, revalidation and queued-discard settling. Pass 11 C#
  permission cases/four native binding regressions; shipped effects need their
  targeted transition check. Do not represent an unexercised effect as qualified.
- [ ] Resolve the **selection decision boundary**, before a broader canary:
  CLI commits the chosen card immediately; official UI selects/previews/confirms.
  The compared definition/cost/ordinary-description/numeric-preview fields
  match; full selection contexts
  still differ in per-copy identities, missing selected flags, owner/layout and upgrade-preview line breaks.
  Fix those exports with the common contract. The owner is choosing one semantic choice with
  exact UI execution (recommended) versus model-controlled UI primitives.
  Preserve every legal subset/order, cancellation and optional decline. Qualify
  ownership/cancellation/uncertain-delivery behavior in a new pinned tuple.
- [x] Pass **2,562 repository tests / 599 strict-typed files**, format/lint and
  C# protocol in **150.17 seconds**. Reconstruct all eight actual choices and
  receipts of the latest blocked control in **5.37 seconds**, without new games.
  Retain current-tuple/earlier equal-prefix reconstruction and all 3,018 protected
  files. See [the guide](native-input-layout-compatibility.md) and
  [portable evidence](evidence/native-input-layout-v1.json).
- [ ] After selection transition qualification, prepare one specific owner command
  for the broader live canary for both originals/two fresh worlds. Reuse sealed pairs at clean boundaries, retain failures and stop on
  uncertain delivery. Do not realign divergent states or infer mechanics parity
  from a short prefix. No learning follows automatically.
- [ ] Add matched effects/transitions for important unobserved interfaces and
  cross-character card/resource variants. Source inventories, generated mutations
  and recorded frames find schema gaps without bulk gameplay; they do not prove
  every content combination. Complete checkpoint compatibility still gates new
  learning/resume/promotion; fresh official original/trained games gate scaling.

## Historical handoff — four adapter fixes and systematic checks from saved records

The owner completed the repaired-interface diagnostic and requested these fixes
and broader discovery without relying on more games. Track under
[#149](https://github.com/benyanc/spireshift/issues/149). Preserve both complete
players/all Adam, prior failures and the offline-layout prototype. No training,
promotion or adaptive controller follows.

- [x] Assess all four stops: public game-over controls, scoped selected-card flags,
  stale reads before the next choice, and the missing native-only shop flag.
  Verify 771 delivered choices/receipts and all app/profile/archive resets.
- [x] Repair terminal result handling, source-scoped card descriptions/legality/
  selection, explicit room/open-inventory routing and bounded read-only refresh.
  Never retry a submitted action, default an unknown Boolean or drop legal choices.
- [x] Replay all **778** completed frames with zero converter failures, including
  both formerly rejected frames. Pass **1,586** frozen-player input probes;
  these are feasibility checks, not new games or action-correctness evidence.
- [x] Cross-check **24** source-declared interfaces, generate **20** structural
  policy/terminal envelopes and **38** corruption/preservation checks. Audit literal
  public consumers and numeric value-field requirements. Keep the four startup/
  tutorial families, unobserved concrete variants and effects coverage explicit.
- [x] Retain the caught development tooltip regression, incomplete synthetic combat
  fixture and their failed receipt/snapshot. The corrected saved audit completes
  in **16.14 seconds / 247.53 MB / 6.90 MB**, with zero games or updates.
- [x] Preserve **1,644** pre-existing pinned files/full states. New shared manifest
  **v6** imports exact original numeric weights/Adam; the old v4/v5 tuples and all
  source snapshots remain preserved. Changed inputs can still change behavior.
- [x] Pass the new eight-delivery wiring control with clean app/profile/archive
  reset: **41.45 seconds / 1.18 GB / 7.12 MB**, zero app copies or updates. Rebuild
  every input/choice/actual receipt independently in **3.96 seconds** without games.
- [x] Pass **2,549 repository tests**, strict types on **573 files**, format/lint and
  C# protocol in **143.95 seconds**, plus the isolated Node/prototype suites.
- [ ] Expand targeted protocol lifecycle/status/settling tests alongside the
  remaining source-layout mappings. Structural family coverage is not complete
  transition or mechanics coverage.
- [ ] Extend remaining input-layout mappings using completed records and targeted
  property/transition tests; retain unknown facts and view ownership. The offline
  prototype is deliberately separate; full input equivalence remains unproved.
- [ ] Qualify important unobserved live interfaces/effects with bounded targeted
  fixtures. Do not demand exhaustive content combinations or repeatedly collect
  whole games to find basic schema/routing gaps.
- [ ] Qualify complete checkpoint input/action/effect compatibility, integrate the
  gate into new learning/resume/promotion, then return to learning. Fresh official
  original/trained full games remain a promotion gate.

See [repairs, offline coverage and limits](native-interface-controls.md). The new
canary stays separate from the completed blocked run; no old seed is retried.

## Historical handoff — interface-wide audit; owner panel subsequently completed

The owner authorized the coordinated audit/fix on 2026-10-24 under
[#149](https://github.com/benyanc/spireshift/issues/149). Preserve both original
players, all earlier finals and every Adam moment/counter. Fixed Ironclad/A8,
terminal victory and the whole-run compute budget stay unchanged.

- [x] Assess the completed v1 owner canary: eight prefix starts / **487 delivered
  choices**, four CLI passes and three official passes; one official shop stop
  after 39 choices. All official workers shut down/reset. Full input prefixes
  already differ at Neow. Preserve the blocked result; do not replay its seeds.
- [x] Inventory **24 declared official surfaces / four public read types / 116
  typed records / 688 declared fields**, including nullability and static limits.
  Record per-kind observed/unobserved coverage rather than claiming all interactions.
- [x] Stream **497 complete public frames** and accumulate every detectable gap,
  with field/type inventories and bounded witnesses. Distinguish unmatched schema
  coverage from matched gameplay effects. Final saved audit: **4.55 seconds /
  193.86 MB / 1.27 MB**, zero games or updates. Preserve development snapshots.
- [x] Repair all **14 public shop-slot references** using exact offer-slot relations,
  without granting read-only slots action authority or accepting arbitrary IDs.
  All 497 saved frames convert. Reject ambiguous ownership.
- [x] Build **CLI export v36** reproducibly: native event flags, relic descriptions,
  keyword/card hover previews are carried through the public projection. Game DLL
  and rules remain unchanged. Four pinned builds take **14.42 seconds / 522.80 MB**;
  224.13 MB of host/build files, zero game app copies.
- [x] Join option enablement from the same already-public bound referent; preserve
  false and reject unknown/conflicting values. Validate surface-card read target
  identity and declared nullable omissions; never guess missing Boolean flags.
- [x] Import exact original weights/full Adam into explicitly labelled shared
  manifest **v4** (5,658 / 6,045 steps), preserving every previous lineage. Pass
  the final four-action-per-host live control and all app/archive/profile checks:
  **42.04 seconds / 1.25 GB / 7.03 MB phase output**, no copies or updates.
- [x] Audit the short repaired capture: all nine frames convert; no unresolved
  declared field/reference occurrences. Reproduce all **eight choices and actual
  receipts** in **3.08 seconds**, without gameplay. Full input parity still fails;
  layout/nesting/duplicate-fact differences are not automatically game-rule bugs.
- [x] Pass **2,543 repository tests**, strict types on **568 files**, format/lint and
  C# protocol in **147.53 seconds**. Verify **1,623** prior pinned files/full states
  unchanged. Main preflight passes and its workspace remains absent.
- [x] The owner completed the repaired broader diagnostic: both original players,
  two new worlds, four pairs/eight starts and 771 delivered choices. Its four
  official stops and all 778 saved frames are assessed in the current handoff.
  Preserve the completed result and its worlds; do not rerun the old command.
- [ ] Consolidate remaining semantic layout/duplicate/read mappings using the full
  gap report. Keep meaningful costs, owners, zones, current previews, counters and
  optional choices. Never manufacture input equality by dropping unknown facts.
- [ ] Add bounded matched-effect fixtures for important unobserved rest, treasure,
  ending and selection variants. Keep source inventory, observed inputs and effects
  as separate coverage claims; exhaustive content combinations are not required.
- [ ] Qualify the full current checkpoint compatibility receipt and integrate it
  into new learning/resume/promotion entry points. Then return to the agreed
  learning order; fresh official original/trained games remain a promotion gate.
- [ ] Prepare small generic upstream fixes with minimal reproductions and tests
  where the defect belongs upstream. Our converter fixes stay here; archived
  connector/headless dependencies may need maintained forks. No contribution or
  external publication is automatic; preserve the pinned local development branch.

See [implementation, limits and the one owner command](native-interface-wide-audit.md)
and [portable evidence](evidence/native-interface-wide-audit-v1.json).

## Historical handoff — shared contract and live adapter; owner diagnostic subsequently completed

The owner authorized the shared official-game/CLI input contract and current-format
checkpoint adapter under [#149](https://github.com/benyanc/spireshift/issues/149).
Both original players, all experimental finals and every optimizer moment/counter
remain intact. This is interface qualification; no new learning or promotion.

- [x] Use one public-input converter in both hosts. Require complete snapshot-bound
  reads/menus, normalize transport/visible occurrence ordering, join already-public
  operand facts, preserve owned costs/zones/statuses/relic counters and every legal
  option, and retain unfamiliar public fields. Bind model choices to the exact
  current raw action, with no cached temporary-ID targeting.
- [x] Import both fixed initializers into an explicitly labelled shared environment
  that pins **actual CLI v35 / worker v11 / official connector v13**. Prove every
  numerical weight and full Adam state exact (**5,658 / 6,045**); preserve v9's
  historical label/results. Changed input conversion is not unchanged behavior.
- [x] Run the short **player-2/two-action paired control**: two real game starts,
  a Neow choice and card-pack selection per host, no failures, **35.31 seconds /
  1.18 GB peak RAM / 6.85 MB phase output**. One shared app, **zero new app copies**;
  exact shutdown/reset, archive and personal-profile checks pass. No updates.
  V1's Neow/Proceed pass and v2's rejected card-removal menu remain preserved.
  V2 verifies clean natural shutdown/reset on rejection. Shared manifest v2 adds
  explicit SDK selection aliases while preserving their full card/menu semantics;
  the current v3 control is separate. These are prefix checks, not full games.
- [x] Independently rebuild both input sequences and **four frozen choices and
  actual delivery receipts** from completed journals in **2.32 seconds**. Preserve
  the earlier verifier-only transport/JSON-number mismatches; no game is replayed.
  Verify **1,560 protected pre-existing files/full states** unchanged.
- [x] Find a real **current public-export gap**, not only historical schema drift:
  official Neow hover-card details and option flags are missing from the CLI view.
  Other duplicate context/layout differences remain. Complete first-state action
  keys match; full input equivalence does not. Do not drop meaningful information
  or infer a game-rules mismatch/learning cause from this limited control.
- [x] Prepare and preflight a finite broader **diagnostic** for both frozen players,
  two new worlds, **four pairs / eight game starts / up to 512 policy actions**.
  Seal/reuse completed pairs, pause at clean boundaries, preserve uncertain attempts
  and source snapshots. Main remains unstarted; there is no training follow-up.
- [x] Pass **nine explicit Node contract tests**, including all seven selection
  aliases. Recheck all protected files/full states unchanged after verification.
  Final repository checks pass **2,531 tests / seven skips**, strict types on
  **561 files**, format/lint and C# protocol in **139.94 seconds**.
- [ ] **Owner runs the diagnostic canary** using the single command in the
  [live-adapter guide](native-shared-live-checkpoint.md), about 10–15 minutes.
  Gather current combat/noncombat layouts and delivery gaps. Do not realign states
  after divergence or interpret these prefixes as a full-game benchmark/admission.
- [ ] Repair native/official public exports and explicit schema aliases using this
  evidence. Preserve hover information, flags, current numerical previews and all
  legal decisions; never default unknown flags to false to force agreement.
- [ ] Qualify complete current checkpoint input/action/successor equivalence and
  integrate the resulting receipt into new batch/resume/promotion entry points.
  The startup delivery control alone cannot satisfy the full automated gate.
- [ ] Before promotion/scaling, compare untouched and trained frozen players on
  fresh official-game full runs at matched behavior/compute. Terminal wins remain
  primary; compatibility and stronger play are separate requirements.

After fidelity qualification, keep card-zone/exhaustion actor checks, more varied
fitting-only lessons and interference tests next. Other difficulties, GA expansion,
unchanged PPO scaling and adaptive effort remain deferred. See
[implementation, limits and owner command](native-shared-live-checkpoint.md) and
[portable evidence](evidence/native-shared-live-checkpoint-v1.json).

## Historical handoff — recurring official-game compatibility before new learning

The owner requested this priority after reviewing the fast CLI, community bridges
and official game. Preserve both original players, all copied finals/full Adam,
frozen experiments, shared game apps and prior negative results. Fixed Ironclad/A8,
terminal full wins and the 128-CPU-second whole-run budget remain unchanged.
Track recurring qualification in [#149](https://github.com/benyanc/spireshift/issues/149),
with learning integration in #146 and public representation in #143.

- [x] Implement a separate checkpoint-bound saved-record regression and command
  guard. Verify exact environment/dependencies/full checkpoints, reconstruct old
  official/native evidence, compare complete menus/public inputs through the real
  encoder/scorer, retain difference witnesses and invalidate changed receipts.
- [x] Run the finite audit: **six frozen players / four historical sequences /
  36 paired observations / two independent seeds**, **6.12 seconds / 174.44 MB
  peak RAM / 0.52 MB output**, zero games, updates or app copies. All old scoped
  mechanics reconstructions pass; **zero full input checks pass per checkpoint**.
  Keep historical-build/incomplete-read limitations explicit.
- [x] Find the model-manifest **v34 label versus separately verified v35 execution**
  mismatch. Do not claim the experiment was unpinned or rewrite saved model labels.
  Context/option layouts and 16 full menus also differ in the old records; their
  24 combat states lack retained advertised pile reads. This is not proof of a
  current-host mechanics defect or the cause of weak play.
- [x] Verify identical-receipt reuse and a real blocked child command (exit 2 before
  execution). Missing live-delivery evidence always blocks new guarded training or
  promotion. A completed saved diagnosis cannot issue that scope. Historical entry
  points remain preserved; this is not global enforcement on every old script.
- [x] Pass **2,515 tests / six skips**, strict types on **553 files**, format/lint
  and C# protocol in **151.42 seconds**, plus **four explicit Node tests**. Recheck
  **443 protected frozen dependencies and complete model/Adam files** unchanged.
- [ ] **Next: common complete public-input and current-checkpoint official adapter.**
  Align semantic decisions and legitimate presentation/ID differences, retain all
  meaningful owners/zones/costs, optional actions and advertised reads. Add exact
  no-change numeric/full-Adam import into a correctly labeled environment.
- [ ] Qualify bounded **current-host versus official-game policy delivery canaries**
  covering consequential observed decisions, complete repeated menus and successor
  effects. Bind the current tuple/checkpoint and integrate the gate into new batch
  and resume commands. Renew canaries at relevant execution changes/milestones;
  historical fixture passes cannot grant current execution parity.
- [ ] Require **fresh official-game original-versus-trained evaluation** before
  promotion or substantial scaling, with matched behavior/compute, complete failure
  denominators and no evaluation feedback into fitting. Normal losses do not fail
  compatibility. Preserve drift evidence and identify affected learning lineage.
- [ ] Benchmark faster faithful official execution before deciding whether to move
  bulk training there. Existing timing ratios include startup/UI/connector overhead;
  keep the CLI fast path conditional on evidence. No new speed job starts now.

Then resume the learning order below: card-zone/exhaustion actor checks, broader
fitting-only lessons and isolated shared-policy interference. GA/hybrid work and
other ascension levels remain later options; adaptive thinking remains behind a
useful base player. Do not expand unchanged PPO or retry rejected predictor grids.
No exhaustive mechanics-combination requirement and no per-game app copies.

See [gate/result and next steps](native-compatibility-gate.md),
[ADR 0006](decisions/0006-recurring-official-game-compatibility.md) and
[portable evidence](evidence/native-compatibility-gate-v1.json). No owner-run long
task is needed from this saved-only stage; live adapter qualification comes next.

## Historical handoff — teaching learned; full-game transfer not established

The owner completed the controlled teaching comparison. Preserve both original
players, all four copied finals, every Adam moment/counter, native evidence and
all historical experiments. No new games or fitting follow this assessment.

- [x] Complete **295 sealed units / 256 copied updates / 36 fight checks / 192
  fresh full-game attempts**. Freeze all finals first. Retain the one reference
  copy's 4,096-decision-cap failure in the original denominator; no retry, replacement
  or learning from the partial game. All planned attempts are accounted for.
- [x] Both taught players independently reproduce the **entire two taught plans**:
  rescue the lost fight with **23 HP**, improve the other to **48 HP**, and make
  all three changed targets greedy. Their target probabilities reach **83.6–98.0%**.
  The changed-action learning and multi-turn execution pathway works on these roots.
- [x] Keep limited held-out gains explicit: HP improves in some already-won fights,
  but each version wins the same **two of four held-out fights per player**. No
  held-out losing fight is rescued; do not turn those selected plans into labels.
- [x] Assess fresh results: **0/64 full wins for every version**; mean floor
  **13.2500 original / 12.6406 reference copy / 12.5156 taught copy**. Teacher minus
  reference is **−0.125 floors [−0.9844, +0.7031]**; teacher minus original is
  **−0.7344 [−2.0000, +0.4219]**. No stronger full-run player is established.
  Act-completing runs are **5/64 original / 2/64 reference / 0/64 taught**.
- [x] Run the prepared saved-only main diagnosis in **73.21 seconds**: verify
  **115,651 seals / 295 receipts / 615 frozen fight distributions**, original
  full weights/Adam, fixed critics and complete comparison denominators. **316.87
  MB peak RAM / 25.61 MB reports / zero games or optimizer updates**.
- [x] Identify meaningful interference hypotheses from the same historical probe.
  Player 3's taught copy changes top combat choices on a world-balanced 81.8% of
  14 selected states/11 worlds and shop choices on 50% of seven states/four worlds.
  These balanced small samples measure movement, not causal harm or gameplay rates.
- [x] Inspect the capped reference game from saved public records: at round **1,004**,
  all five Strikes/Bash are in exhaust; the player cycles Havoc/Defend against a
  ten-HP Toadpole. Public `combat_piles` identities are present and delivery verifies.
  This supports a long-term consequence learning check, not an invented adapter bug.
- [x] Pass **2,497 tests / five skips**, strict types on **549 files**, format/lint
  and the C# protocol in **146.79 seconds**. Verify preserved full model/Adam bytes
  and both experiment recipes unchanged; only result/handoff documentation changes.

Next, in order:

1. **Qualify card-zone/exhaustion ownership in the actual actor encoding** using
   saved public situations with the permanent deck held constant. Check available
   discard/exhaust identities, current costs and ownership; distinguish missing
   representation from a policy that has not learned to use existing information.
   Do not repeat an exhaustive mechanics inventory or demand an untrained policy
   immediately choose differently. Preserve all model/optimizer files.
2. **Propose a bounded, broader fitting-only teacher/student curriculum** covering
   different fights/decks and delayed effects, including removing future attacks.
   Match teaching work, preserve the original/reference controls, split worlds
   before selection and use new final evaluation worlds. More optimizer steps on
   the same two fights are not the next default. No collection/fitting is automatic.
3. **Isolate shared-policy interference in a separately declared comparison**;
   for example, match original noncombat behavior while comparing changed combat.
   This tests a cause of transfer failure; it does not permanently freeze decision
   families, prohibit substantial improvements or reinstate weak-parent proximity
   gates. Probability movement alone does not establish the causal answer.
4. Keep full-run victory / 128 CPU seconds primary. No promotion, unchanged PPO
   scaling, repeated critic grid, GA expansion, new difficulty or adaptive effort
   controller follows automatically from local teaching success.

See [result and interpretation](native-plan-teaching-result.md) and
[portable evidence](evidence/native-plan-teaching-result-v1.json). There is no
additional owner-run command from this completed comparison.

## Historical parallel work — completed-record teaching diagnosis

The owner reports the controlled teaching test running and authorized a separate
diagnostic using completed records. Its live workspace is not inspected, locked
or changed. Keep its recipe/implementation, both numerical parents, all saved
weights and every Adam moment/counter unchanged.

- [x] Implement a separate completed-only report connecting action learning,
  independent fight execution, unrelated choice movement and full-game transfer.
  Require the final complete marker before opening source units; no partial-session
  fallback, polling, new games, fitting or automatic continuation.
- [x] Verify exact requests, predecessors, final-state barrier and original full
  parent/Adam imports. Retain per-epoch plan losses, but show the three changed
  targets' probability, greedy choice and margin separately.
- [x] Locate the first exact public-state/action departure in completed fight
  traces and reconstruct the saved frozen greedy distributions. Do not realign
  later divergent states or call an unreached target wrong. No departure alone
  establishes a mistake, and local HP/fight wins are not full-game utility.
- [x] Inspect at most **128 public menus / 16 predeclared historical TRAIN worlds**,
  excluding teacher roots and fresh panels. Reconstruct effective menus, retain
  optional choices, balance families/worlds, and report rest/card-skip/potion/shop
  probability movement without making optimal-action or causal-damage labels.
- [x] Qualify on the **completed short control** in **90.74 seconds** with zero
  new games/optimizer updates. Verify **106,365 source seals**, all **16 work
  receipts**, **79 saved fight distributions**, both originals/full Adam and
  unchanged frozen main inputs. Historical extraction accounts for **1,981 raw
  decisions / 1,515 genuine choices**; the 128-state probe covers **14 families,
  69 deck signatures and 24 relic-state signatures**, with no observed family
  omitted. Retain only one raw episode at a time, **278.38 MB peak memory /
  23.59 MB reports**, with zero app copies or new trajectories.
- [x] Prepare an explicitly selected completed-main analysis recipe. It is not
  run while the main experiment is active; no settings or model selection follow
  this control-only diagnosis.
- [x] Pass **12 new tests**, full repository verification (**2,497 passed / five
  skipped**), strict types on **549 files**, format/lint and the C# protocol build
  in **165.13 seconds**. New implementation/configuration files remain separate
  from the frozen experiment's pinned code and settings.
- [x] Reopen the identical saved report after repository checks in **53.70
  seconds**. All protected sources/checkpoints verify again, with no repeated
  analysis, extra output copies or live-experiment access.
- [ ] Assess the main result after the owner finishes it, using this report to
  distinguish example learning, execution and transfer. Keep both comparison
  controls and native-world uncertainty; do not repeat or scale automatically.

The control shows why these measurements differ: changed-action probabilities
increase, but the first taught rescue action still loses the greedy ranking.
All three control versions depart at that same choice and lose that fight.
This is a one-epoch control result, not a forecast or assessment of the running
16-epoch experiment. Continue the declared experiment unchanged.

See [report guide](native-teaching-diagnostics.md) and
[portable evidence](evidence/native-teaching-diagnostics-v1.json). No additional
owner command is needed while the teaching test runs.

## Historical handoff — controlled teaching test implemented; owner main run next

The owner authorized the matched teaching/fresh-game test. Both original full
players and every Adam moment/counter (**5,658 / 6,045**) remain unchanged. The
completed teacher and old unstarted natural-v1 curriculum stay preserved. Main
teaching/evaluation is a separate finite experiment and remains unstarted.

Implemented (#35 / #143 / #146):

- [x] Freeze the **two improved fitting plans**: single-change rescue at **23 HP**
  on world 148 and coordinated win at **48 versus 31 HP** on world 192. Select
  from fitting outcomes only, with exact menu ownership and native confirmation.
  Public inputs/action labels alone reach the learner; no held-out fitting data.
- [x] Compare improved-plan copies, reference-plan copies and untouched originals
  for both preserved initializers. Both use the same two source-player-2 worlds;
  keep that limited coverage explicit. Equal-world categorical teaching uses
  **16 epochs × four updates × 32 draws**, **64 updates per copy / 256 total**.
  Preserve the original files and start each main copy with exact warm Adam.
- [x] Record full-plan loss/probability and the **three changed-choice targets**
  separately. Keep critic/value-credit inputs, scores and rewards unchanged.
  Save full weights/Adam each epoch; seal all six final/original states in a
  barrier before any evaluation. No best-epoch selection or evaluation feedback.
- [x] Prepare **36 natural-fight checks** and **192 fresh full games** on **32
  disjoint canonical native worlds**, three versions and two fixed initializers.
  Match behavior and compute, counterbalance order, retain failure denominators,
  and report each initializer plus native-world-clustered paired intervals.
- [x] Seal/resume each work unit and optimizer predecessor exactly. Retire verified
  failed attempts and proceed within the declared two-failure allowance; uncertain
  delivery or changed receipts stop without retries. Share the app/runtime/cache,
  use isolated profiles and create zero game app copies. Display batch summaries.
- [x] Pass **14 new tests** covering fitting-only public labels, teacher selection,
  fixed work, final barriers, freshness/aliases, exact warm-Adam resumption,
  unchanged originals, failure continuation/denominators, changed checkpoints and
  open-game refusal before an evaluation marker is created.
- [x] Prepare the **28,046,877-byte** public lesson bank from preserved sources in
  **132.71 seconds**, with zero games or optimizer updates. Freeze both recipes
  and fresh panels; main excludes all inherited panels and the new control seed.
- [x] Complete the short integration control in **107.93 seconds**: **16 units /
  16 copied optimizer updates / three fight checks / six full games / no errors**.
  All four copied optimizers and the final-state barrier execute. Its three
  fitting-fight checks still lose and full-game wins remain zero; this is runner
  qualification, not a strength result or a tuning/early-stop condition.
- [x] Pass **41.06-second saved-only verification** of **106,359 sources / 16
  receipts**, exact full-state/Adam reproduction for all **16 copied updates**,
  nine repeated native audits and six reconstructed full-game traces. Main
  read-only preparation passes without creating its workspace. Preserve the v1
  verifier's raw-versus-filtered-count error; v2 checks both counts correctly.
- [x] Pass **2,485 tests / five skips**, format/lint, strict types on 544 files and
  the C# protocol build in **147.13 seconds**. Update GitHub #35 / #143 / #146 with
  prior history preserved. Main remains unstarted; originals and old pinned code
  are unchanged.

Next, in order:

1. **Owner runs the main test** using the one command in the
   [teaching-test guide](native-plan-teaching-test.md). Main imports the originals,
   not trained control copies. One worker, 15-minute sessions, 2 GB memory / 3 GB
   generated phase output; completed units survive clean pauses. No further
   collection or training experiment follows this bounded fit/evaluation.
2. Assess whether copied players learn the changed choices, execute the natural
   fitting/held-out fights and improve fresh full-run outcomes against **both**
   reference-clone and untouched controls. A probability/loss improvement alone,
   or beating a degraded reference clone, does not establish better play.
3. Keep terminal victory / 128 CPU seconds primary, world/initializer limitations
   and technical failures visible. No readiness, model promotion, adaptive effort
   controller or automatic larger run follows a local diagnostic gain.

See [implementation and owner command](native-plan-teaching-test.md) and
[portable evidence](evidence/native-plan-teaching-test-v1.json).

## Historical handoff — coordinated teacher complete; small student-transfer test next

The finite earlier/coordinated comparison is complete. Preserve both original
full players and every Adam moment/counter (**5,658 / 6,045**), all earlier finals,
the failed natural-v1 collection and its unstarted curriculum. There is no next
collection command and no student fitting or fresh full-game result yet.

Completed (#35 / #143 / #146):

- [x] Seal all **576 work units / 533 native paths / 43 unavailable proposals**,
  with **zero failed/capped paths**, all **32 cells / eight worlds** verified.
  Confirm references, both selected traces and exact original later suffixes.
  The main report's control-only boolean stays false; it is not a failed main gate.
- [x] Find useful plans in **two fitting worlds**, both from player 2: one lost
  fight becomes a win, another saves **17 HP** with coordinated changes. Simpler
  search also supplies useful lessons and a better **23-HP versus 17-HP** rescue.
  Player 3 supplies no improved fitting world in this bank.
- [x] Keep all **four held-out worlds** separate. Both methods rescue the same
  held-out fight. Single-change search selects three improved later worlds versus
  two for coordinated search; no consistent advantage of coordination or earlier
  roots is established. These are selected local fight plans, not full-run wins.
- [x] Explain the finite coverage tradeoff using saved fitting paths: four early
  single changes all lose on world 148; coordination rescues it, but wider search
  finds a better single change at candidate 10. Extending world 192 improves
  43 HP to 48 HP. Do not infer that search depth or earlier access always helps.
- [x] Preserve all four resource reports: **44.02 total wall minutes / 1,947.80 CPU
  seconds / 643.66 MB peak / 1.425 GB final cumulative output / zero app copies**.
  Do not sum cumulative storage or use the last unit-loop time as the total cost.
- [x] Pass a **171.85-second saved-only assessment** of **105,961 sealed files /
  576 receipts and request/plan reconstructions**. Independently recompute **1,175
  distributions/choices** and re-audit **64 reference/confirmation native journals**;
  all cells, paired comparisons and original full-state hashes/Adam counters match.
  No native launch or optimizer update. Other candidate audits remain sealed.
- [x] Pass repository checks in **137.76 seconds**: **2,471 tests / five skips**,
  lint/format, strict types and C# protocol. Update result documentation, portable
  evidence and GitHub #35 / #143 / #146 with prior history intact. No implementation,
  recipe, learner, original weight or optimizer file changes.

Next, in order:

1. **Design a separately declared small student-transfer comparison** using the
   useful fitting plans, with an explicit two-world data limitation. Fitting-only
   selection may combine the better verified plan from each search method. Do not
   import held-out lessons or silently resume the incompatible v1 curriculum.
2. Compare teaching the improved plans, cloning original reference behavior and
   unchanged originals at fixed work. Balance whole-world contributions. Both
   preserved initializers may learn from the same fitting bank on experimental
   copies; that does not create extra independent worlds. Preserve full originals
   and every Adam moment. No automatic training follows this assessment.
3. Check changed-choice learning and natural fight completion, then freeze finals
   before fresh full-game evaluation with matched combat/noncombat behavior and
   compute. Terminal victory remains primary; no readiness pass follows local HP.
4. Keep further teacher-search expansion, unchanged PPO scaling, predictor grids,
   capacity/GA changes, other difficulties and adaptive thinking deferred while
   testing whether these useful lessons transfer into a player.

See [result assessment](native-coordinated-teacher-result.md) and
[portable evidence](evidence/native-coordinated-teacher-result-v2.json).

## Historical handoff — coordinated control passed; owner main comparison next

The owner authorized a separate bounded search comparison after the insufficient
natural v1 result. Preserve both original full players and every Adam moment/counter
**5,658 / 6,045**, historical finals and the unstarted v1 curriculum. **V2 control
qualification passes. The main earlier/coordinated comparison remains unstarted
and is the next long owner stage.**

Implementation (#35 / #143 / #146):

- [x] Compare **single-change versus coordinated search at early/later roots of
  the same fight**. The later prefix fixes the original greedy opening and its
  reference must reproduce the exact early-reference suffix. Absent later play
  phases stay in the original world denominator, without replacement or retries.
- [x] Preserve four first-change lineages and extend them through **4 + 8 + 4**
  candidate slots, up to three edits. Losing intermediate plans can be extended.
  Every edit binds an actually observed current menu and replays prior edits;
  no guessed card physics, forecast menu or new hidden student input is used.
- [x] Give both search methods **16 candidate slots per entry**. Retain actual
  path/CPU counts and unfilled proposals; this is not an equal-CPU claim or
  exhaustive planning. Native reference and selected full traces are confirmed.
- [x] Select **eight new main worlds / two control worlds** from **918 turn-one
  positions / 256 repaired completed TRAIN games**, using public descriptors only.
  Exclude all 14 old teacher/control worlds. Split whole worlds before diversity
  selection: four fitting / four held out, balanced across both fixed parents.
- [x] Main spans **eight decks / eight relic states**, four normal fights, two
  elites, two bosses, floors **5–17**, low/middle/high HP and a maximum 217-action
  source prefix. These are new teacher positions from existing TRAIN games, not
  newly played full-game evaluation seeds or exhaustive mechanics coverage.
- [x] Count useful shorter verified wins in this new comparison; preserve the
  old four-choice gate/result. Local guarded HP gains and fight wins remain
  auxiliary fixed-world evidence, not full-run rewards or ordinary PPO labels.
- [x] Bound physical paths by **192 fight actions / 12 observed rounds / 60 wall
  seconds / 128 CPU seconds**. Share the frozen app/runtime/SDK/cache, with isolated
  profiles and zero app copies. Stop mismatched confirmations/prefixes, retire
  failed workers, preserve failures/caps and allow no automatic replacement.
- [x] Pass **20 pure/mocked tests**, including a joint improvement with losing
  single-change intermediates, observed-prefix ownership, three changed rounds,
  fixed lineages/budgets, short lessons, whole-world splits, exhausted proposals,
  late-prefix equality, cached resumption, open-game refusal before activation and
  bounded request/prefix retirement without action retry or success labels.
- [x] Preserve the v1 prototype exactly: three clean pauses and **43 sealed paths**,
  followed by one interrupted prefix and four unattempted units. Both parents
  exercise actual three-edit/cross-round plans, but only six cells are confirmed;
  this is not a complete qualification pass. The capped final driver failed to
  charge dependency checks against its unit timer. No failed delivery is retried.
- [x] Prepare v2 with fresh control worlds, unchanged main roots, 60-second whole
  path limits including prefix/initialization, request timeouts bounded by remaining
  time, a global session clock and a **150-second** new-unit reserve. Preserve old
  markers, receipts and source snapshots. Full control now needs an owner-run
  15-minute-cap session; do not manually extend another short-clock driver.

- [x] Pass a **101.66-second saved-only preservation audit**: independently recheck
  all **43 completed native journals**, reconstruct **654 action distributions /
  choices**, and verify observed proposals/confirmations. V2 read-only preparation
  passes, with both new workspaces absent. The incomplete v1 control remains
  unqualified; no native process or optimizer runs during this audit.
- [x] Pass repository verification: **2,471 tests / five skips**, lint/format,
  strict types on 537 files and C# protocol build in **132.08 seconds**. Record all
  four v1 prototype resource reports, including the cap; do not sum cumulative
  storage. Update GitHub #35 / #143 / #146 without losing earlier history.
- [x] Complete the owner's v2 control: **48 paths / eight verified cells / zero
  failures or caps**, with three actual edits across rounds for both players.
  One later-start coordinated plan saves **seven HP** over the reference and
  single-change method; the other within-entry method comparisons tie. These
  worlds supply implementation evidence, not fitting labels or stronger full-run play.
- [x] Record **304.07 total wall seconds / 186.89 CPU seconds / 372.42 MB peak /
  106.98 MB final output**. The report's 203.91-second unit-loop time excludes
  dependency checks. Keep all original full weights/Adam and historical evidence.
- [x] Independently re-audit **48 native journals / 48 sealed receipts**, reproduce
  **786 action distributions/choices**, all cells and paired comparisons, and verify
  the main recipe read-only in **120.07 seconds**. No game or optimizer runs; the
  main workspace remains absent. Original full-state hashes and Adam counters match.
- [x] Repeat repository verification in **134.53 seconds**: **2,471 tests / five
  skips**, lint/format, strict types and C# protocol pass. Change only handoff
  documents and result evidence; all qualified implementation and recipes stay pinned.

Next, in order:

1. **Owner runs only the prepared main comparison** in the
   [coordinated-teacher guide](native-coordinated-teacher.md), at most
   **576 native attempts / eight worlds**, one worker, clean resumable sessions,
   2 GB RAM / 3 GB phase output and no app copies. No optimizer updates or automatic
   student/fresh-game stage follows. Shared root banks and historical evidence
   remain explicitly outside the phase output accounting. Preserve clean units;
   never automatically retry an interrupted unit. Do not repeat the passed control.
2. Audit fitting/held-out results separately. Compare search methods within entry
   and entry timing within method, keeping world denominators, local tradeoffs,
   actual joint edit depth and CPU visible. Search packages also differ in
   expansion/menu targeting; do not claim an isolated action-count effect, optimal
   planning, 576 independent samples or stronger complete-run play.
3. If there are useful confirmed fitting plans, design a separate matched
   categorical student/reference-clone/original comparison and fresh full games.
   Preserve original weights/Adam, freeze finals before evaluation and assess
   terminal wins first. Neither the old v1 gate nor held-out lessons are adopted
   as fitting evidence automatically.
4. Keep unchanged PPO scaling, predictor grids, capacity/GA changes, other
   difficulties and adaptive thinking deferred. A failed or weak teacher comparison
   is evidence to assess, not permission to expand until it passes.

See [implementation guide](native-coordinated-teacher.md) and
[control result evidence](evidence/native-coordinated-control-v2.json). The earlier
[implementation evidence](evidence/native-coordinated-teacher-v2.json) preserves
the pre-owner handoff and prototype history.

## Historical handoff — natural teacher complete; stronger fitting lessons still needed

The owner completed the finite natural multi-turn collection. **190 native attempts /
12 worlds finish without failed or capped branches.** No student fitting follows:
the frozen fitting-only quality gate fails. Both original full players, every Adam
moment/counter (**5,658 / 6,045**) and all prior experiment finals remain preserved.

Completed (#35 / #143 / #146):

- [x] Verify all 12 natural roots and exact reference/selected confirmations:
  **12 references / 154 alternatives / 24 confirmations**, with zero missing roots,
  game-app copies, optimizer steps or fresh full-game attempts.
- [x] Separate the actual fitting signal: six of eight reference fights already
  win; selected plans still win six. One winning fitting plan preserves **seven
  HP**, but has three choices across two rounds. Four other winning plans pass
  the declared four-choice/two-round criterion; none improves its reference.
- [x] Explain the design cutoff honestly: a three-choice lesson can be useful to
  a network. It does not qualify this particular multi-turn test, and counting it
  would still supply only **one**, not the required **two**, fitting improvements.
  Preserve it as diagnostic evidence, not a reason to retroactively pass v1.
- [x] Keep the **two held-out HP improvements (+2 / +7)** out of fitting and gate
  decisions. Their reference fights already win; no death-to-win rescue occurs
  in any of the four losing reference worlds. These are local fight outcomes,
  not full-run victory rates or a teacher-trained player's evaluation.
- [x] Check whether resource restrictions caused the shortage: **zero higher-HP
  winning paths are rejected by the recorded resource guards**. All alternatives
  retain equal recorded non-HP resource views at their root; those views are not
  a complete strategic equivalence test. **131 / 154** alternatives also tie the
  reference's recorded outcome/resources. No unsupported-state repair is indicated.
- [x] Pass a **99.65-second saved-only audit** of **83,768 sealed source files /
  190 receipts / 3,124 reconstructed action distributions and selected actions**,
  exact confirmations and the unchanged fitting-only gate. No native replay,
  baseline refit or optimizer update. The v1 curriculum workspace remains absent.
- [x] Record the actual two-session collection cost: **18.24 wall minutes /
  784.30 CPU seconds / 444.58 MB peak / 495.58 MB final cumulative output**.
  Preserve both resource reports; do not present the final report's unit-loop
  duration as the whole experiment or add cumulative storage measurements.
- [x] Pass **2,451 tests / five skips**, lint, formatting, strict types and the
  C# protocol build in **138.01 seconds**. Update only result/handoff documentation
  and portable evidence; frozen collector, learner, recipes and full states remain
  unchanged. GitHub #35 / #143 / #146 record the result with history preserved.

Next, in order:

1. **Design a separately bounded teacher coverage/recoverability test**, subject
   to owner authorization. Compare the existing one-change-plus-greedy continuation
   with plans making coordinated decisions. Consider first-turn roots before
   inherited damage/resource loss. Use fitting/TRAIN worlds for development and
   new withheld worlds for assessment; do not reuse observed v1 held-out outcomes
   as unseen validation. Preserve all attempted-root denominators and finite caps.
2. Predeclare how useful shorter plans enter a future curriculum separately from
   its multi-turn qualification. Seek actual better fitting plans rather than
   loosening the old criterion or merely cloning unchanged successful behavior.
   Stronger search and earlier roots are hypotheses, not established fixes.
3. Only after a separate teacher supplies adequate verified lessons, run a
   declared matched student intervention against reference cloning and untouched
   originals, with fixed work, all finals frozen and fresh full-game evaluation.
   The implemented **v1 curriculum remains unstarted**; there is no owner command
   for the completed collection now.
4. Keep unchanged PPO enlargement, predictor grids, capacity/GA changes, other
   ascensions and adaptive thinking deferred. No checkpoint promotion or readiness
   pass follows local fight wins or HP improvements.

See [result assessment](native-natural-combat-result.md) and
[portable evidence](evidence/native-natural-combat-result-v1.json).

## Historical handoff — natural multi-turn teacher and matched curriculum implemented

The owner requested useful natural multi-turn lessons after the delayed-learning
control. Implement a separate finite teacher collection and a guarded curriculum /
fresh-game comparison. Preserve both original players and full Adam counters
**5,658 / 6,045**, all prior finals and every completed diagnostic. **The larger
teacher collection is not started; it is the next owner-run stage.**

Completed (#35 / #143 / #146):

- [x] Prepare roots from **256 completed repaired TRAIN attempts**, with **1,389
  public candidate positions**. No final floor, win, return or counterfactual
  outcome selects a root. Use the actual v11 counter view; preserve the older
  missing-counter bank without silent migration. Preparation takes **58.66s**.
- [x] Freeze **two control / eight fitting / four held-out worlds**, one root per
  world. Main covers **12 decks / 11 relic states**, six normal fights, four elites
  and two bosses, floors **5–17**, low/middle/high health and five zero-current-cost
  opportunities. This is eight of 18 available public groups, not full coverage.
- [x] Verify exact natural seed/prefix replay before every branch. Record the
  parent's remaining fight, propose up to **16 first divergences across its first
  three observed rounds**, then separately confirm the complete reference and
  selected traces/resources. Every actual legal choice remains available; bounded
  search is not exhaustive. Main upper bound: **228 native attempts**.
- [x] Keep local labels explicit: actual room rewards establish a fight win;
  death is a loss; escape/other rewards are not victories. Prefer a rescue from
  death or a higher-HP win with the declared retained-resource guards. Relic
  charges, draw/RNG changes and future utility are not completely priced. No local
  result or HP comparison silently becomes a full-run reward or trusted win gain.
- [x] Require useful confirmed multi-turn lessons on **four fitting worlds**, with
  **two strict local improvements / two enemy sets / three decks**. Held-out worlds
  cannot rescue this gate. Retain failed/capped roots and attempt denominators;
  no replacements or uncertain retries. More than two technical failures stops.
- [x] Implement **categorical action imitation**, not return-to-action-score
  regression. Compare teacher cloning, matched reference cloning and untouched
  originals. Exact inherited weights/full Adam start each copy; fixed **16 epochs /
  256 total updates / 8,192 choice presentations**; world-balanced examples and
  full checkpoints every epoch. Actor layers remain mutable; value weights and
  the coarse predictor stay fixed. These are not ordinary PPO episodes.
- [x] Freeze all four final copies before **24 withheld-fight branches + 192 fresh
  full games** on 32 distinct seeds. Keep terminal wins primary, failures in the
  original denominator, unchanged 128-CPU-second run budget and joint world-clustered
  paired intervals. No epoch selection, promotion or adaptive thinking follows.
- [x] Pass a separate **52.56s / two-branch** natural replay probe. The short
  teacher control completes **14 branches / two natural fights** in **120.48s**, no
  failures or app copies. Both already win; zero better plans are found. This is
  wiring qualification, not evidence that the main teacher gate passes.
- [x] Complete the **22-unit** student/evaluation control across two short bounded
  launches (**166.20s / 162.68s**), preserving the actual clean pause after epoch one.
  Four copies make **32 total updates**, fitting loss decreases for each, all six
  held-fight branches and six fresh-game attempts finish without technical failure.
  One fresh world / zero wins / equal mean floor 11 establishes no gameplay gain.
  The larger experiment always starts again from the preserved original full states.
- [x] Pass a **72.95s saved-only audit**: **76,724 source files / 14 teacher and
  22 curriculum receipts**, 176 recomputed teacher action distributions, fitting
  metrics, exact imports/full Adam lineage and read-only main preparation. In this
  actual no-treatment control, both arms' final weights, every Adam moment and
  withheld/fresh traces match exactly per parent. No game, fit or update is rerun.
- [x] Pass repository checks: **2,451 tests / five skips**, lint, formatting, strict
  types and the C# protocol build in **127.86s**, under a four-minute resource cap.

Next, in order:

1. **Owner runs only the teacher collection command** in the
   [natural curriculum guide](native-natural-combat-curriculum.md), approximately
   15–30 minutes with clean resumable sessions and no fitting afterward. Shared
   frozen inputs, one worker, 2 GB RAM / 3 GB output per phase; no app copies.
2. Audit and assess the actual teacher signal: availability, caps/failures, native
   replay equality, local improvements, resource tradeoffs, public state variety
   and the predeclared fitting-only gate. No automatic expansion or threshold
   relaxation if the lessons are insufficient. Do not admit old rejected preferences.
3. If the declared main gate passes, use the implemented matched curriculum/fresh-game
   stage on four new copies. Assess both trained versions against the untouched
   originals, separately by parent as well as pooled. A weaker reference clone is
   not a useful gain. Future noncombat lessons/full-run reinforcement learning
   remain separate decisions after this actual result.
4. Keep unchanged PPO enlargement, predictor grids, capacity/GA changes, other
   ascensions and adaptive thinking deferred. Do not rerun the completed controls.

See [implementation and qualification evidence](evidence/native-natural-combat-curriculum-v1.json).

## Historical handoff — delayed learning passes with learned and exact baselines

The owner completed the fixed comparison: **94 / 94 units, 204 native branches,
16,384 sampled diagnostic sequences and 868 optimizer steps on four copies**.
Both original players, their full Adam states and every historical final remain
preserved. This is a successful short-horizon learning control, not stronger
full-game play, a preferred baseline or a reason to repeat unchanged PPO scaling.

Completed (#35 / #143 / #146):

- [x] Both learned-baseline copies and both exact-baseline copies pass the frozen
  fitting and held-out criteria. Initial mean fitting success is **34.34% / 34.85%**.
  Final fitting success is **99.98% / 99.99%** for player 2 learned/exact and
  **99.91% / 99.98%** for player 3 learned/exact. Every copy is greedily successful
  on all 16 fitting and eight held-out cases.
- [x] Held-out mean success is **99.982% / 99.991%** for player 2 learned/exact and
  **99.920% / 99.979%** for player 3 learned/exact. The weakest held-out result
  is still **99.815%**. All eight public roots are distinct from fitting roots;
  they cover four worlds and the same two task patterns, not eight new mechanics.
- [x] Retain the learning curves: the fitting criterion first passes at round
  **4 / 4** for player 2 learned/exact and **8 / 7** for player 3 learned/exact,
  with no subsequent criterion failure. The earlier four-round control's player 3
  learned failure remains historical evidence; the fixed longer schedule resolves
  it without relaxing thresholds or tuning on held-out outcomes.
- [x] Explain the **222 zero-update rounds**: all 32 sampled sequences succeed in
  each, and the learned baseline leaves essentially constant centered credit.
  The existing guard skips the complete update and preserves Adam. Player 2 makes
  **42 / 382** updates and player 3 **60 / 384**, learned/exact. Different counts
  follow the frozen update rules; they do not establish method superiority.
- [x] Record **695.73 seconds / 444.96 CPU seconds / 356.94 MB peak / 244.30 MB
  retained**. No failed native branch, full-run attempt, app copy, promotion,
  readiness pass, adaptive controller or automatic next experiment is produced.
- [x] Pass the separate saved-only audit in **59.88 seconds**: **75,658 source
  files / 94 receipts / 204 native paths / 372 goal-path deliveries**, all 512
  saved rounds, eight reconstructed boundary batches and all final expected
  probabilities. Verify full imports, Adam lineage and 17 entirely zero-step
  chunks remaining bit-exact. No baseline refit, native replay or update occurs.
- [x] Pass **2,428 tests / five skipped**, strict types on 520 files,
  formatting/lint on 709 files and the C# protocol in **133.69 seconds**.
  Only assessment/handoff documents change; frozen production sources and
  recipes remain unchanged. Update GitHub #35 / #143 / #146.

Next, in order:

1. Close this diagnostic after the saved-only audit. Do not rerun it or import
   its specialized forks as ordinary full-game players. The production encoder,
   sampler and update can learn these two- and three-action terminal subgoals with
   the existing coarse baseline; full-run credit and strategic horizons remain
   unverified. Do not claim a universal optimizer or baseline defect from stalled
   full-run performance, or declare all such defects ruled out.
2. Qualify a finite teacher/curriculum sample on **natural multi-turn TRAIN-only
   situations**, including varying health, decks, relics and later encounters.
   Use the varied situation bank as provenance, not as optimal-action labels.
   Its old missing-counter inputs require explicit replay qualification under the
   repaired observation contract; no silent migration. Show reliable alternative
   consequences and held-world learning before another gameplay intervention.
3. Declare one student intervention on copies of both preserved parents, then
   freeze both final players before fresh full-game evaluation. Measure whether
   useful local learning survives the full loop and improves terminal wins or
   repeatable auxiliary progress. Keep the current full-run objective explicit.
4. Defer another unchanged PPO enlargement, predictor grids, capacity/GA changes,
   other ascensions and adaptive thinking. No next experiment starts automatically.

See the [completed comparison assessment](native-delayed-learning-result.md).

## Historical handoff — production-path delayed learning comparison prepared

The owner requested a delayed-decision test before another gameplay intervention.
Implement it separately from the completed 832-attempt comparison and preserve
both original players, all Adam moments/counters **5,658 / 6,045**, historical
forks and all four experience-test finals. No adaptive controller or new full-game
training follows this diagnostic.

Completed (#35 / #143 / #146):

- [x] Use the production v11 public projection/action delivery, encoder, sampler,
  20-feature ridge, PPO loss/settings and full inherited optimizer state. A separate
  privileged diagnostic collector enumerates finite native transition trees;
  sampled training sequences then look up those observed transitions. This is
  not the ordinary full-game episode/admission path and is never labelled as such.
- [x] Verify two genuine delayed goals: Thunderclap then Bludgeon must win the
  encounter after at least **two actions**; Footwork then Defend then End Turn must
  survive the native advertised attack after at least **three actions**. No
  immediate action succeeds. Native order/upgrade variants counter a constant
  first-option shortcut. Every current legal action has an observed continuation.
- [x] Compare only action-independent baselines: current learned public ridge
  versus exact expected terminal diagnostic success under that copy's current
  policy, not the best action. Rewards arrive only at the goal boundary; discount
  and trace lambda remain one. No HP bonus or correct-action label enters PPO.
- [x] Collect 32 own-policy sequences per round. Begin both arms from identical
  full states and matching private draw schedules; verify first-batch equality.
  Keep related families/repeats of a native world in the same value fold. Freeze
  all finals before held-out evaluation; report genuinely unseen public roots and
  aliases rather than treating new seed strings as proof of novelty.
- [x] Pass the separate **16-unit / 51-native-branch** integration control in
  **96.27 seconds / 345.55 MB peak / 52.72 MB retained**: 512 sampled diagnostic
  sequences and 43 optimizer steps on copies, zero full runs or app copies.
  Original parents remain unchanged. All four copies succeed greedily on the two
  new held-out public roots. This is just one held-out world and two task patterns.
- [x] Keep the stricter result explicit: both exact-baseline copies pass the fitting
  confidence criterion; only one learned-baseline copy does after four rounds.
  Player 3 learned has 88.47% mean fitting success but a 67.94% weakest case, below
  the frozen 80% minimum. Do not relax it or call this baseline superiority.
- [x] Prepare and validate the main recipe read-only: **12 worlds / 24 trees /
  expected 204 native branches**, eight fitting worlds and four held out. Four
  experimental copies receive 128 fixed rounds, at most **16,384 sampled diagnostic
  sequences / 1,536 optimizer steps**, with eight-round checkpoints. Main has not
  been launched. The unchanged production settings include the diagnostic value
  head's loss/rate, temperature, entropy, clipping and per-round KL stop.
- [x] Independently verify **68,172 source files / 16 receipts / 51 native paths /
  93 goal-path deliveries**, restore saved ridge coefficients without refitting,
  reproduce first sampled batches and all final probabilities, and verify exact
  imports/Adam lineage in 31.80 seconds. No native game or optimizer is rerun.
- [x] Pass **2,428 tests / five skipped**, strict types on 520 files, formatting /
  lint on 708 files and the C# protocol in 135.75 seconds. Fourteen new tests cover
  true delayed goals, complete menus, exact current-policy values, terminal-success
  finite-difference gradients, grouped folds, withheld inputs and bit-exact restart.

Next, in order:

1. Owner runs the one command in the [delayed comparison guide](native-delayed-learning.md).
   Allow about 15–25 minutes with 15-minute clean sessions. Completed native trees,
   weights and all Adam moments resume; uncertain units are preserved, never retried.
2. Assess fitting learnability separately from held-world transfer and genuinely
   new public states. Exact passes / learned fails suggests sensitivity to baseline
   quality in these tasks; both pass establishes only this narrow delayed-learning
   bridge. Both fail requires investigating the full update/representation. No
   result alone establishes the cause of stalled full-run play or readiness.
3. Use the saved-training feedback audit as needed, then qualify useful stronger
   native teacher/curriculum examples on varied TRAIN-only situations. Earlier
   rejected fixed-world preferences are not automatically admitted. Follow with
   one declared student intervention and fresh full-game evaluation.
4. Keep unchanged PPO scaling, predictor grids, capacity/GA changes, other
   ascensions and adaptive thinking separate and deferred.

See [portable implementation/qualification evidence](evidence/native-delayed-learning-v1.json).

### Preserved completed experience-budget comparison assessment

## Historical handoff — experience comparison complete; larger batches do not improve fresh play

The owner completed **832 / 832 attempts and 283 / 283 sealed units**, with zero
failed or missing games: **640 sampled TRAIN attempts + 192 frozen fresh-game
evaluations**. The saved-only audit verifies 66,324 source files, every task and
predecessor receipt, exact original numerical imports/full Adam lineage, all four
finals and the reported paired summary. It makes no games, baseline fits or updates.
Do not rerun, enlarge or select a checkpoint from this completed comparison.

Fresh evaluation pools two fixed players on the same 32 new worlds, 64 attempts
per version. All three versions win **0 / 64**. Average floor is **11.1875 original,
11.640625 batch32, 11.15625 batch128**. The smaller arm clears an act in three
games (best floor 23); the original and larger arm clear none (best floor 17).
These are auxiliary progress results; they do not establish useful full-run play.

- [x] Primary larger-minus-smaller floor difference is **-0.484375**, paired 95%
  interval **[-1.171875, +0.171875]**. Larger-minus-original is **-0.03125**, interval
  **[-0.75, +0.625]**. No improvement is demonstrated by the larger experience budget.
- [x] Smaller-minus-original is **+0.453125 floors**, interval **[-0.328125,
  +1.1875]**. Its higher bootstrap training-return score is a limited auxiliary
  signal, not a win-rate gain, confirmed floor improvement or basis for promotion.
- [x] Keep the 32-world shared dependence explicit. Intervals cluster worlds
  jointly over both fixed parents; 192 attempts are not 192 independent worlds.
  All-zero empirical victory intervals do not prove equivalence or a zero true
  win probability. The recipe changes experience, batch support and training
  compute together, not variety alone. This does not prove more data never helps.
- [x] Confirm **2,175 source optimizer steps**, all legal families still learnable,
  and sparse later-game experience: **10 / 512** larger-arm training games clear
  an act; **0 / 128** smaller-arm games do. No training victory is observed.
  More card/relic definitions were encountered without an established fresh-game gain.
- [x] Preserve both originals, full Adam counters **5,658 / 6,045**, historical
  finals and all four new experimental final states. No automatic promotion,
  readiness pass, adaptive thinking or new training follows. Zero app copies.
- [x] Pass **2,414 tests / five skipped**, strict types on 511 files, formatting /
  lint and the C# contract in 137.36 seconds. No pinned implementation or recipe
  changes were needed for this assessment. Update GitHub #35 / #143 / #146.

Next, in order:

1. Finish the already implemented saved-TRAIN feedback diagnostic's remaining
   **three cohorts / 288 old games**, if needed to guide the next intervention.
   This is owner-run analysis, not more gameplay. Check matched histories, baseline
   error and feedback signs on the same choices, per-family update movement and
   rare-choice/game weighting. Do not infer correct actions from assigned credit.
2. Qualify a finite stronger native teacher/curriculum sample using TRAIN-only
   situations, including later combat and deck/relic variety. First show useful
   alternative-action consequences and exact public menus, then test student
   learning on different whole worlds. Old bank roots need exact-environment
   replay qualification; missing public counters cannot silently migrate.
3. Test one declared teacher/student intervention on copies of both preserved
   parents with full Adam state, then fresh full runs. Privileged fixed-world
   teacher evidence remains labelled and cannot become ordinary on-policy PPO.
4. Defer another unchanged PPO enlargement, predictor grids, hidden-size changes,
   GA, other ascensions and adaptive thinking. Choose any later change separately
   from the completed evaluation; do not tune on its 32 worlds.

See [the completed result and limitations](native-experience-budget-comparison-result.md)
and [portable verified evidence](evidence/native-experience-budget-comparison-result-v1.json).

### Preserved mid-comparison status and independent diagnostics qualification

## Historical handoff — experience comparison paused; saved-update diagnostics qualified

The 32-versus-128-game comparison is **not complete**. The 2026-10-22 status
snapshot has **584 / 832 attempts and 83 sealed units**, all from training, with
no completion report, active comparison process or unfinished unit. Fresh-game
evaluation has not started. These are saved progress counts, not a performance
result; unattempted evaluation placeholders must not be treated as losses.

The owner resumes the existing finite comparison with the same command in
[the comparison guide](native-experience-budget-comparison.md). Completed games,
weights and all Adam moments/counters are reused. Do not launch it on the owner's
behalf, start a replacement experiment, or change its pinned learner/environment.

Completed independently (#35 / #143 / #146):

- [x] Adapt the existing saved-training diagnostics to the four already sealed
  first-round updates: both parents and both batch sizes, **320 TRAIN attempts /
  128 worlds**. Keep reports separate; never decode evaluation, later-round,
  active or uncommitted source units. Shared worlds are not independent repeats.
- [x] Reconstruct sampled actions, effective public menus and behavior probabilities
  using each exact pre-update full state. Restore the saved whole-game cross-fit
  coefficients rather than refitting; reproduce forecasts, raw feedback moments
  and original clean/planned denominators. Failures remain counted and excluded
  from learning examples. Decode one raw episode at a time.
- [x] Measure before/after probabilities and diagnostic gradients by decision
  family, health and public opportunities; report deck/relic signatures, rare
  choices, forced menus and game weighting. Verify shared first-round histories
  before comparing feedback signs/value errors on identical choices. These
  measurements do not identify good actions or establish stronger gameplay.
- [x] Finish the separate tiny control: **12 saved TRAIN games / 1,654 decisions**,
  four capped sessions totaling 179.66 seconds, no baseline fits, games or updates.
  Shared clean histories match for both players; the tiny sample selects no method.
- [x] Qualify one real **32-game / 4,144-decision** cohort in **91.06 seconds /
  297.09 MB peak RAM / 11.05 MB retained**. Original forecasts and normalization
  reproduce. The 99 steps describe the saved source update; this audit makes zero
  updates. Other **288 saved games / three cohorts** remain an optional owner-run
  audit, not a prerequisite for finishing the gameplay comparison.
- [x] Pass **2,414 tests / five skipped**, strict types on 511 files, formatting /
  lint on 695 files and C# protocol verification in 205.57 seconds. Both original
  weights and all Adam moments/counters **5,658 / 6,045**, historical finals and
  sealed first-round sources remain unchanged. No app copies or Actions runs.

Next, in order:

1. Owner resumes the existing comparison and finishes its **248 remaining attempts**
   (56 training, then 192 fresh evaluation). Assess paired full-run wins, floors,
   compute and failures only after all finals are frozen and evaluation completes.
2. If needed, finish the separate saved-update audit with its one command in
   [the diagnostic guide](native-experience-training-diagnostics.md). Use it to
   explain coverage/feedback/update mechanisms, never as a substitute for fresh
   game results or a reason to retune the unfinished comparison.
3. Decide the next bounded intervention from that evidence. The completed varied
   situation bank remains available; native replay and stronger teacher/curriculum
   labels still need separate qualification under the correct observation version.
4. Keep scaling, new predictor searches, capacity changes, GA, other ascensions and
   adaptive thinking deferred. No automatic promotion or subsequent training.

See [portable diagnostic qualification](evidence/native-experience-training-diagnostics-v1.json).

### Preserved varied-situation-bank qualification

## Historical handoff — varied TRAIN situation bank complete; current experiment unchanged

The owner reports the bounded experience-budget comparison is running. This parallel
work does not inspect its output units, change its pinned files, read its changing
checkpoints or add another training/game workload. Both original players, all Adam
moments/counters **5,658 / 6,045** and historical experimental finals remain unchanged.
The comparison's fresh-game result still determines the next learning intervention.

Completed independently (#35 / #143 / #146):

- [x] Build a fixed bank from the completed audited structured experiment's **384
  TRAIN attempts / 64 native worlds / 12 policy cohorts**, not its evaluation games
  or the live run. Account for all 55,642 decisions: 41,816 genuine choices, 274
  forced navigation controls and 13,552 single-choice menus. Decode one raw episode
  at a time; verify source, policy, menu and complete-game provenance.
- [x] Organize public situations by decision family, act/floor, health, encounter,
  owned cards with per-copy upgrades/current advertised costs, and relic identity /
  available counters. Preserve full original menus, including take/skip, rest
  alternatives, shops, targeting, potion use and zero-current-cost plays. These are
  opportunities, not optimal-action labels or extra rewards.
- [x] Bound repetitive early-combat sampling, remove 7,641 exact duplicate
  references from 14,121 retained candidates and select **256 situations / 14
  families**. Keep 192 fitting / 64 validation roots on disjoint **48 / 16 whole
  native worlds**, grouping every related player/arm/branch. The active v2 bank
  includes 188 deck signatures, 109 relic-state signatures, 22 take/skip menus,
  15 Heal/Smith menus, 14 shop controls and seven zero-current-cost-play opportunities.
- [x] Repair a measured sampling omission before accepting the bank: v1 misses
  validation later-game/boss roots despite their availability. Preserve its code,
  candidate pool, result and audit. Separately version coverage-first selection;
  reuse the exact world split and caps. V2 covers all **62 fitting / 53 validation
  declared public groups** with no omitted available group. No outcome labels or
  validation performance select the roots.
- [x] Resolve **all 256 selected roots** to their exact saved public/effective
  menus and recorded prefixes; verify 34,625 protected source seals. Native seeds
  and prefix actions stay outside student inputs. No root action is labelled
  correct; no native replay or public-belief teacher is qualified by saved resolution.
- [x] Complete the 32-game control in 22.69 seconds, initial candidate bank in
  **72.22 seconds / 192.14 MB peak RAM / 46.82 MB retained**, v2 coverage correction
  in **17.87 seconds / 8.25 MB**, and corrected all-root resolution in 73.38 seconds.
  No game attempts, app copies, optimizer updates or automatic follow-up.
- [x] Pass **2,396 tests / five skipped**, strict types on 506 files, formatting /
  lint on 689 files and the C# contract. The 23 new passed tests cover source/public
  boundaries, deterministic sampling, rare-group reservation, quota shortages,
  optional actions, ownership, whole-world splits, exact deduplication and resolution.

Keep limitations explicit: these are historical TRAIN worlds already seen by the
parents. Bank validation is a future teacher/student split, not fresh-game evaluation.
All 23 selected combat roots predate the public relic-counter repair; missing fields
stay unavailable and cannot silently migrate to the current worker. V2 includes
20 floor-17+ and four boss roots; **validation has just two floor-17+ roots and one
boss**. Group coverage is now satisfied, but these tiny samples cannot establish
later-game generalization. No world assignment was changed after seeing coverage.

Next, in order:

1. Let the existing comparison finish unchanged and assess its paired fresh-game
   result before deciding on more training, another predictor or an enlarged run.
   No extra owner command is needed for the completed bank.
2. If a teacher/curriculum is warranted, select a finite public-state sample from
   this frozen bank and qualify native replay/menu equality under its exact source
   environment, or explicitly recollect/qualify it under the repaired environment.
   Fill later-game/validation gaps with separately planned TRAIN experience rather
   than pretending this bank contains unseen states. Collect trustworthy alternative
   action consequences before any imitation; fixed-world evidence stays privileged.
3. Test one separately declared teacher/student or curriculum intervention on forks
   with preserved full Adam state, then fresh full games. A balanced example bank
   alone is not a learning signal, win-rate gain, readiness pass or PPO dataset.
4. Keep rich-predictor grids, hidden-size changes, GA, other ascensions and adaptive
   thinking separate and deferred. No action restrictions or HP/Smith reward bonuses.

See [bank design, use and limitations](native-training-situation-bank.md) and
[portable qualification evidence](evidence/native-training-situation-bank-v1.json).

### Preserved inventory qualification and owner experience-test handoff

## Historical handoff — inventory distinction repair qualified; owner experience test next

**The short audit, repair and learning control are complete.** The next task is the
owner-run bounded comparison of 32 versus 128 fresh games per training round. Both
original players and every Adam moment/counter **5,658 / 6,045**, plus all six
historical structured-input finals, remain unchanged. Main preparation has imported
exact numerical states with explicit new observation metadata; **zero main games
and zero main learning updates** have run.

Completed in the accepted order (#35 / #143 / #146):

- [x] Separate player inputs from the coarse credit predictor. Audit 128 saved
  TRAIN attempts / 64 worlds / 18,481 learning rows / 14 families. Eighty same-count
  controlled probes across ten deck/relic/cost/upgrade/ownership distinctions pass
  through the actual original/hashed/named encoders; 16 natural pairs also differ.
  This proves scoped wiring, not native reachability or correct strategic choices.
- [x] Find the actual upstream gap: all 12,518 inspected combat rows omit the
  counter view; 53 source attempts have a numeric native relic-counter witness.
  Add only public owned ID/counter pairs in separately versioned worker v11.
  Preserve legacy workers, game/runtime/SDK/cache and all action operands.
- [x] Qualify four short native diagnostic replays on two TRAIN worlds: 498 actions,
  336 combat observations, identical legacy public traces/actions/endings, ordered
  native/public counter equality and zero failures. Zero and null are exercised;
  nonzero ownership changes have code-level controls, not a natural-panel claim.
- [x] Keep the production 20-feature cross-fit ridge fixed. The richer inventory
  correction's held-game error remains 5.17% worse; do not silently install it or
  repeat penalty searches. New observation metadata is explicit; all numerical
  weights and full Adam state are copied exactly into future experimental forks.
- [x] Prepare two fixed parents / two arms / two rounds: 64 versus 256 training
  games per player, followed by 32 fresh evaluation worlds shared by each initial
  player and both finals. Main total **640 training + 192 evaluation = 832 attempts**,
  283 sealed units, 256 independent train worlds. This compares experience budgets
  and batch support, not data diversity alone or equal training compute.
- [x] Pass the separate 18-attempt native integration control / 19 sealed units:
  zero failures, 42 updates on copies, 143.30 seconds, 693.27 MB peak / 56.23 MB
  retained, no app copies. Its one evaluation world does not select an arm or
  establish improved gameplay. Both main forks still start from the originals.
- [x] Audit the saved control independently: 33,839 source seals, all 18 games /
  3,180 decisions / 1,654 TRAIN decisions and exact full weight/Adam imports verify
  without refitting or new games. Main saved-only preflight seals just policy checks
  and two exact imports; it cannot launch games.
- [x] Pass 2,373 tests (25 new passed, one new skipped; five total skipped), strict
  types on 498 files, formatting/lint on 676 files and C# protocol in 142.35 seconds.

Owner next:

1. Run **the one command** in the
   [experience comparison guide](native-experience-budget-comparison.md). Plan about
   60–120 minutes, with two isolated workers and restartable clean sessions. Eight
   games per collection chunk; 15-minute / 4-GB session limits. The same command
   resumes saved states and every Adam moment; uncertain work stops for inspection.
2. Assess larger versus smaller and each final versus its migrated initial player.
   Terminal full wins remain primary; report acts, paired floors/returns, CPU and
   failures, plus useful independent deck/relic/later-game experience and per-family
   credit. More attempts do not guarantee better play. Freeze all finals before
   evaluation; no checkpoint selection from its outcomes.
3. If ordinary experience remains uninformative, qualify a stronger native teacher /
   curriculum and imitation plus full-run RL as a separate intervention. Richer
   nonlinear value/typed sharing, wider hidden layers, GA and other ascensions remain
   separate later work. Preserve the failed rich-predictor results. No automatic
   scale-up, promotion, readiness pass or adaptive controller follows.

See [the input audit and repair](native-inventory-input-audit.md),
[input evidence](evidence/native-inventory-input-repair-v1.json) and
[experiment qualification](evidence/native-experience-budget-comparison-v1.json).

### Preserved completed inventory-credit diagnosis

## Historical handoff — inventory-credit diagnosis assessed; distinction audit pending

The next short task is a saved-state check of the **player's actual inputs**.
The completed diagnosis below concerns its separate state-only credit predictor;
its same-count aliases do not establish identical player encodings or action scores.
Do not launch the next long comparison until meaningful deck/relic distinctions
pass or any demonstrated information-loss bug is repaired.

The saved-data diagnosis finishes all 12 separate
cohorts / 384 prior TRAIN attempts / 64 worlds / 55,368 learning rows. Both
originals and all six experimental finals, including full Adam states, remain
unchanged. See the [diagnosis](native-inventory-credit-diagnosis.md) and
[portable evidence](evidence/native-inventory-credit-diagnosis-v1.json).

Completed (#35 / #143 / #146):

- [x] Reproduce the exact production folds, coarse coefficients, prediction
  metrics and credit mean/deviation before testing extra information. Decode
  only saved TRAIN games, reconstruct effective menus, exclude deterministic
  navigation, and retain every planned complete game. No new native attempts.
- [x] Add generic typed owned-card identities, paired per-copy upgrade/cost,
  native types and aggregate costs/upgrades; relic identities and available
  owner-bound counters. Do not encode offered/chosen actions, slots, seed or
  hidden state. Numeric zero and unavailable counters stay distinct.
- [x] Diagnose 435 cohort-level exact coarse-input groups with different
  inventory states across worlds. Test deck-only, relic-only and combined
  residual forecasts at one fixed separate penalty, with whole-world folds and
  no held-out tuning. Combined withheld MSE is **5.17% worse**, in 12/12 cohorts;
  fitting MSE improves about 42%. Keep the current predictor; do not promote.
- [x] Measure per-family credit and exact selected-logit coefficients without
  optimizer updates. Combined credit signs change on 4.90–10.30% of choice rows,
  which is not evidence of correctness. Only two act-clearing trajectories on
  one world supply 43.70% of baseline error; all remain in the denominator.
- [x] Restore 144 saved inventory models/forecasts bit-for-bit; audit 32,907
  protected files without refitting. Successful sessions total 80.15 seconds,
  750.52 MB peak RAM / 32.49 MB retained. Preserve the initial rounding-related
  failed verifier and its exact source snapshot separately; active recipe is v2.
- [x] Pass 2,348 tests (27 new; four skipped), strict types on 483 files,
  formatting/lint and C# protocol in 129.45 seconds. No player/Adam updates,
  app copies, promotion, readiness pass or adaptive-controller work.

Next material work:

1. **Audit meaningful actor inventory distinctions using saved TRAIN states.**
   Keep counts fixed while changing public card definitions, per-copy upgrades,
   displayed/current costs, relic identities and visible owner-bound counters.
   Check the actual compressed policy inputs, public/handle boundary and candidate
   ownership; do not mistake predictor aliases or isolated hash-coordinate
   collisions for identical whole player inputs. Preserve original weights/Adam.
   Use small controlled mutations and natural saved pairs, without replaying games
   or requiring different choices from a policy that has not learned the distinction.
   Repair a demonstrated bug before more collection; do not demand exhaustive
   card/relic interaction coverage or a perfect predictor.
2. **Prepare a bounded experience/learning comparison**, measuring independent
   games, rare later-game coverage, per-family credit and fresh full-game outcomes.
   Keep the verified coarse predictor fixed as the control; broader experience
   and a richer predictor are separate hypotheses. Preserve original weights/Adam;
   do not automatically launch a larger unchanged PPO run or claim that more games
   guarantee improvement.
3. If ordinary experience remains uninformative, separately qualify stronger
   native teachers/curricula and imitation plus full-run RL. Keep privileged
   teacher branches out of ordinary PPO and public-belief search claims.
4. Retain richer nonlinear state-value/typed entity sharing and a wider hidden
   network as separate evidence-driven candidates. Do not repeat the rejected
   rich linear/correction grids. GA, other ascensions and adaptive thinking remain
   later work; no next experiment has started.

### Preserved structured-input result and credit-diagnosis handoff

## Historical handoff — structured-input comparison complete; no established gain

The owner's restart completed the finite plan correctly: **640/640 attempts,
323/323 sealed units, zero failures**. No rerun or further owner command is needed.
Both originals and complete Adam state remain unchanged at **5,658 / 6,045**.
See the [completed assessment](native-structured-input-comparison-result.md) and
[portable evidence](evidence/native-structured-input-comparison-result-v1.json).

Completed (#35 / #143 / #146):

- [x] Finish 384 sampled training attempts and 256 fresh frozen evaluations.
  Each trained copy receives 64 games; shared worlds are 64 train / 32 evaluation,
  not 640 independent worlds. All methods have 0/64 evaluation wins.
- [x] Assess the predeclared equal-size named-versus-hashed comparison. Average
  floors: original 11.453125; unchanged-input PPO 11.3125; hashed supplement
  11.78125; named supplement 11.390625. Named minus hashed is -0.390625, paired
  95% interval [-1.15625, +0.34375]. No demonstrated improvement or clear floor
  regression. Sparse act clears and a highest point estimate do not select a winner.
- [x] Verify 32,677 source files, all 323 units / 640 endings / 95,266 decisions,
  six exact full-state imports and 64 identical initial player/world trace groups.
  Full optimizer continuation and paired tables verify. The wider actors' new
  input weights changed; fitting did not silently skip them. Audit: 30.49 seconds,
  zero new games or updates.
- [x] Preserve all six experimental finals, the original players and every Adam
  moment/counter. Record 1,314 actual updates, about 60.18 owner-run wall minutes,
  1.12 GB peak RAM / 1.052 GB final main artifacts. No app copies, promotion,
  readiness pass or adaptive-controller training.

Next, in the agreed order:

1. **Diagnose state-only credit on the newly saved TRAIN games.** Keep behavior
   policies separate and all fresh evaluation worlds out of fitting. Check deck,
   relic and resource distinctions, rare long runs, whole-world generalization and
   whether forecasts change useful action-credit/gradient signal. Preserve the
   negative rich neural, linear and residual-correction results; do not repeat
   their grids or silently install rejected predictors.
2. **Only advance a materially supported state-value candidate to a separate
   bounded learning comparison**, with unchanged actor/reward/engine settings,
   preserved original full states/Adam and a new frozen full-game evaluation.
   Prediction error alone cannot qualify a player. No such experiment is launched.
3. Then assess larger/more varied bounded experience and qualified teachers. A
   wider hidden-network control, GA and other ascensions remain separate later work.
   Do not automatically repeat or scale this completed 640-attempt recipe.

### Preserved structured-input preparation

## Historical handoff — structured-input comparison qualified; owner main run next

The native tactical check passes, while the earlier full-game trial still shows no
established improvement. The next agreed intervention is now implemented and qualified:
**named public-input columns versus an equally sized hashed supplement**, with a
separate unchanged-input PPO control. Both original players and every Adam moment
remain unchanged at counters **5,658 / 6,045**. See the
[design and single owner command](native-structured-input-comparison.md).

Completed (#35 / #143 / #146):

- [x] Fit a frozen input vocabulary from 128 prior TRAIN games: 18,736 distinct
  public situations / 14 families. Equal-game/family-balanced selection supplies
  1,024 named facts; full public inputs remain in the original encoder. Unfamiliar,
  unselected and free-text facts are not silently discarded. No outcome labels,
  development data or old on-policy updates fit the vocabulary.
- [x] Preserve starting behavior and all inherited weights/Adam during explicit
  dimension extension. Named and hashed variants both have 1,536 inputs, 32 hidden
  units and 52,289 total parameters; unchanged has 512 / 32 / 17,473. New input weights
  and moments start at zero; all actor paths remain trainable. Value inputs/credit
  and the full-run objective remain unchanged. A larger hidden network is separate.
- [x] Pass varied-input controls on 56 distinct natural TRAIN situations, including
  amount ownership, current-cost changes, optional declines, candidate order,
  unfamiliar facts, private-state rejection and new-column derivatives.
- [x] Complete 20 native integration attempts, zero failures, 36 updates on copies.
  Six exact state imports and four initially matched player/world trace groups
  verify. Saved audit: 27 units / 7,999 source files / 2,628 decisions, 4.20 seconds.
  Original full states unchanged; no app copies. One evaluation world is not evidence
  of improved strength. Native control sessions total 118.96 seconds, 816.38 MB peak RAM.
- [x] Prepare 384 sampled training attempts / 256 fresh evaluation attempts. Main
  actors start from the originals, never the control-trained forks. All final states
  freeze before the first evaluation; no epoch selection on evaluation outcomes.

- [x] Pass the full repository check: 2,321 tests (34 new; four skipped), strict types
  on 476 files, formatting/lint and the C# protocol, 135.94 seconds. Main saved-only
  checks/imports pass in 8.72 seconds with zero main games or optimizer updates.

Owner next:

1. Run the **one command** in the linked guide. Main training/evaluation games are
   **not started**. Budget roughly 45–90 minutes; clean resumptions use that same
   command. Two workers, 15-minute sessions, 4-GB memory/artifact caps; no app copies.
2. Assess named versus equally sized hashed inputs first, then added-block/unchanged
   controls and every final player versus its original. There are 64 training worlds
   and 32 separate evaluation worlds shared across arms: attempts are not independent
   worlds. Report terminal victories first, failures in the denominator, then acts,
   floors, CPU and unfamiliar-state coverage. The additional-block control does not
   isolate generic hidden-network capacity, and two fixed initializers are not a
   population-level training replication.
3. Preserve a negative result if it occurs. No automatic larger run, model promotion,
   base-readiness pass, changed rewards or adaptive-controller training follows.

Then separately: richer state-only credit prediction with whole-game validation and
actual learning evaluation; more varied bounded experience; qualified stronger
teachers/imitation plus RL. Wider hidden networks, GA and other ascensions remain
separate backlog work. No HP/Smith reward adjustments or silent off-policy reuse.
The original 256-attempt and tactical results remain preserved:
[full-game assessment](native-policy-update-comparison-result.md),
[tactical assessment](native-tactical-learning-result.md).

### Preserved comparison preparation (completed and assessed above)

## Current handoff — policy checks pass; owner fresh-game comparison next

**The policy-update checks and eight-game native control pass.** The bounded
main comparison is prepared, with **zero main games / zero main optimizer updates**.
Both originals and every Adam moment/counter **5,658 / 6,045** remain byte-identical.
The main copies start from those exact originals. See the
[design and single owner command](native-policy-update-comparison.md) and
[qualification evidence](evidence/native-policy-update-comparison-v1.json).

Completed (#35 / #143 / #146):

- [x] Qualify the existing PPO action-probability loss separately from outcome
  fitting. Check positive/negative advantages, both clipping directions, common
  score shifts, candidate permutations and finite differences on both originals.
  Maximum checked derivative error **3.48×10⁻¹¹**. Outcome targets with fixed
  advantages leave actor gradients unchanged; prediction-only loss gives no actor
  gradient. These are mathematical controls, not guarantees of stronger gameplay.
- [x] Preserve warm Adam exactly on import and test every moment/counter's
  continuation. Add an explicit skip when centered batch credit has zero variance:
  warm momentum alone must not move weights in that case. Keep all actor layers
  and legal decision families learnable; no permanent proximity penalty.
- [x] Complete **eight clean native control games**: four fresh sampled training
  games, then four frozen original/updated checks. Only disposable copies advance
  **5,658→5,667 / 6,045→6,054**. Native delivery, probabilities, endings, frozen
  inputs and account-profile checks pass. Native session **41.43 seconds**,
  **777.68 MB peak RAM / 19.28 MB output**; no app copies. One control evaluation
  world is not performance evidence.
- [x] Prepare **128 fresh sampled training games / 128 fresh evaluation games**,
  final-only checkpoints, two fixed initializers and unchanged-original controls.
  Bind and exclude all 32 historical v0.111.0 seed manifests and separate control
  worlds. Main data preflight imports the exact original states without launching
  games or fitting them. Completed units reuse their full state and source seals.
- [x] Keep the qualified 20-feature state-only cross-fit baseline unchanged for
  this trial. It still omits deck/relic identities. The action-conditional rich
  predictor is not silently used as a state-value baseline, policy or reward.
- [x] Saved audit verifies **444 files / 11 units**, reconstructs **682 sampled
  TRAIN / 593 evaluation decisions** and exact main-state imports in **8.20
  seconds**. Pass **2,268 tests (52 new; four skipped)**, strict types on 452 files,
  formatting/lint and the C# protocol in **121.90 seconds**.

Next work, in order:

1. **OWNER runs the one linked comparison command**, roughly 15–30 minutes from
   short-control timing. Two rounds of 32 sampled games per player; then 32 new
   worlds shared by originals/updated copies. Eight-game training chunks use two
   workers. Show each batch's best result; freeze final states before evaluation.
2. **Assess the saved paired full-game result before adding more rounds.** Report
   terminal victories first, then acts, floors, score and failed attempts. Account
   for fixed initializers and shared worlds; no checkpoint selection on these
   outcomes. Do not equate successful math or prediction fitting with better play.
3. **Use that result to choose the next material learning change.** Preserve
   the originals and all experimental states. Rich state-value representation,
   more useful independent experience, stronger action-teacher evidence and GA
   remain separate possible work; do not expand the unchanged recipe automatically.

Per-session caps: 15 wall minutes / 1,800 CPU seconds / 4 GB memory / 4 GB main
output. Clean sessions resume the same finite job; one-hour invocation cap.
Uncertain units stop for inspection. Full-run victory / 128-CPU-second budget
remain primary. No main gameplay, promotion, readiness, controller, push or Actions
has occurred. The earlier completed inspection below remains historical.

### Preserved completed ranking assessment

## Current handoff — saved rankings complete; deliberate actor learning next

**The owner has finished the inspection. Do not rerun its completed command or
repeat the rejected actor-score regression.** Outcome prediction is separated
successfully; stronger gameplay is not established. Both original players and
every PPO Adam moment/counter **5,658 / 6,045** remain byte-identical. Preserve all
four rejected forks. See the [completed result](native-action-prediction-separation-result.md)
and [result evidence](evidence/native-action-prediction-separation-result-v1.json).

Completed (#35 / #143 / #146):

- [x] Finish **192/192 saved games / 22,842 decisions**, on 32 shared development
  worlds, with source policies stratified and games equally weighted. Original
  scores/probabilities are exactly unchanged under the independently fitted
  predictor on every inspected menu. Source ownership, navigation, choices and
  probabilities replay; no new games, app copies or original PPO updates.
- [x] Confirm common ranking/scale disruption from both rejected updates. On
  original paths, consequence-fork combat score RMS shrinks **2.842→0.287 /
  1.643→0.248**; top actions change on **42.49% / 49.19%** of strategic menus.
  Return-only changes **42.94% / 49.35%**; the two forks differ on **7.49% / 6.64%**.
  Consequence versus original changes **27.00% / 25.12%** of sampled noncombat
  choices under the same draw. Compression alone cannot explain greedy changes;
  rankings also changed. This does not identify optimal actions or causal blame.
- [x] Complete all **seven whole-TRAIN-world folds / two all-TRAIN predictor fits**.
  The nine new prediction states have independent Adam counters of 128; original
  actor and optimizer remain untouched. Final-return generalization is mixed:
  player 2 slightly beats a fitting constant, player 3 does worse. Seven worlds
  do not establish causal action values, victory probabilities or a PPO baseline.
- [x] Audit **73,988 sealed files / 201 units** and rebuild all numeric ranking
  summaries in **19.22 seconds**, without fitting or neural/native replay. The
  owner's remaining saved pass takes **6.19 minutes**; total output is **84.98 MB**.
  The original collector's exact inference checks remain sealed and verified.

Next work, in order:

1. **Qualify deliberate actor learning separately from outcome fitting.** Reuse
   the existing PPO implementation where appropriate. Check known positive and
   negative advantages, relative action-probability changes, common-score-shift
   invariance and zero actor gradient from prediction-only fitting. Stop using
   raw actor scores as supervised outcome predictions. This is a learning-loss
   correction, not a permanent small-change or combat-only restriction.
2. **Prepare a bounded, matched on-policy trial from both originals.** Preserve
   each copied player's weights and complete Adam state. Collect fresh sampled
   full games with exact behavior probabilities; keep every legal family
   learnable. Qualify any state-only baseline separately. This action-dependent
   predictor, greedy development histories and privileged teacher continuations
   are not automatically valid PPO credit or experience. Freeze the schedule and
   retain unchanged-original controls before any owner-run stage.
3. **Evaluate frozen updates on fresh full games.** Terminal victory under the
   128-CPU-second budget remains primary; floors are auxiliary. Do not promote
   based on fitting loss, ranking change or prediction accuracy. Readiness before
   adaptive search remains required; GA/other difficulties stay deferred.

No new learning/game batch, owner command, promotion, push or Actions follows
this completed assessment. The preparation below is historical.

### Preserved prediction separation preparation

## Current handoff — outcome prediction separated; finish saved-menu ranking inspection

**Outcome fitting now trains a separate network and cannot overwrite the saved
player's action scores.** Both original model files and every PPO Adam moment /
counter **5,658 / 6,045** remain read-only. All four rejected experimental forks
remain preserved. See the [design and one owner command](native-action-prediction-separation.md)
and [qualification evidence](evidence/native-action-prediction-separation-v1.json).

Completed (#35 / #143 / #146):

- [x] Implement same-public-menu comparison of original / return-only /
  consequence action rankings, top-score gaps, centered score spread, strict
  inversions, entropy/KL and same-draw noncombat choices. Reconstruct historical
  ownership, shop navigation, all recorded actions and probabilities. Keep source
  policies separate and weight games equally; omit forced/singleton menus only
  from strategic comparison rates, not from source denominators.
- [x] Give recorded-return and six consequence predictions their **own 512×32×7
  network / 16,647 parameters and separate Adam state**. Copied initial hidden
  weights become independent predictor parameters. Original encoder, readout,
  direct action path and critic receive no prediction gradient. Policy/chooser
  calls never consult predictions; checkpoint schemas remain separate.
- [x] Complete **seven whole-source-world prediction folds plus two all-TRAIN
  prediction fits**, fixed initializer / 128 epochs, fitting-only scaling and
  original per-head world/plan/decision weighting. Keep masks, constant labels and
  future observations as labels only. No development menu or outcome trains this
  predictor. Its action-dependent estimates are not automatically PPO baselines,
  causal action values, victory probabilities or new action-teacher admission.
- [x] Short real-data check: **6/192 saved cases / 600 decisions**, both players /
  all three variants on one development world, **46.77 wall seconds**, zero game
  attempts, app copies or policy/PPO updates. Recorded source choices reproduce;
  fitting predictions leaves original scores/probabilities exactly unchanged on
  those menus. All nine prediction states and completed ranking units are sealed.
- [x] On the two original-player paths in that one world, the old consequence fork
  compresses combat score spread **2.739→0.296 / 1.535→0.233**, with top-action
  changes on **36.4% / 52.9%** of strategic combat menus. This supports score/rank
  disruption as a hypothesis; one world cannot establish its prevalence or blame
  individual changed choices for final losses. Original behavior remains intact
  under the new separated predictor; improved gameplay is not claimed.
- [x] Pass **2,216 tests (45 new; four skipped)**, strict types on 443 files,
  formatting/lint and the C# protocol in **134.42 seconds**. Tests cover numerical
  derivatives, held-label poisoning, all original/PPO-state preservation, exact
  nested/noncombat routing, checkpoint separation, constant/missing targets and
  safe saved-unit restart. No runtime source changes follow the qualified sample.

Next work, in order:

1. **Owner finishes the remaining 186 saved-case ranking inspections.** The
   measured 600-decision sample takes 9.61 seconds; expect **7–10 minutes** for the
   remaining full pass including source checks. Use the single linked command;
   all nine prediction fits and six ranking cases resume. It reads saved files,
   requires no game closure and starts no games. Four-minute sessions / 2 GB RAM /
   1 GB cumulative output; the same finite job has a 30-minute invocation cap.
2. **Assess complete rank/scale effects by parent, source policy and menu owner.**
   Separate common return-regression changes from extra consequence gradients.
   Do not pool repeated menus as independent worlds, create action-quality labels
   from these diagnostics, retune on development outcomes or repeat the old update.
3. **Declare the next deliberate policy-learning step separately.** The isolated
   predictor does not itself improve the actor. Qualify the policy objective and
   derivatives, collect the sampled experience or reliable preferences it actually
   requires, and compare with originals on fresh full games. All legal action
   families may remain learnable; this is not a permanent proximity restriction.

Full-run victory / 128-CPU-second budget remain primary. No promotion, search
controller, new gameplay batch, push or Actions follows this work. GA/other
difficulties remain deferred. The earlier finished comparison is preserved below.

### Preserved negative consequence-learning result

## Current handoff — consequence-learning test complete; both updates regress

**The 192-game test completed cleanly, but neither trained fork should replace
the original player.** All variants win zero full games. Keep both original
weights and every Adam moment/counter **5,658 / 6,045** unchanged. See the
[completed assessment](native-combat-consequence-learning-result.md) and
[result evidence](evidence/native-combat-consequence-learning-result-v1.json).
The preparation and its earlier prediction gains remain preserved below.

| Variant, pooled across both fixed parents | Games | Wins | Act completions | Mean floor |
| --- | ---: | ---: | ---: | ---: |
| Original | 64 | 0 | 2 | 10.84375 |
| Return-only supervised update | 64 | 0 | 0 | 7.96875 |
| Same update plus combat-consequence feedback | 64 | 0 | 0 | 8.25000 |

Completed (#35 / #143 / #146):

- [x] Finish **192/192 planned development games**, on 32 distinct worlds shared
  across two fixed parents and three variants. Zero failures, omitted games,
  app copies or production updates; original models and all four frozen forks
  remain byte/identity valid. The owner's two sessions take **18.37 wall minutes /
  702.83 CPU seconds**, with 509.71 MB peak RAM / 395.88 MB cumulative main output.
- [x] Rebuild the paired results: consequence versus original floor difference
  **−2.59375 [−3.859375, −1.3125]**; return-only versus original **−2.875
  [−4.125, −1.59375]**. Consequence versus return-only is **+0.28125
  [−0.046875, +0.640625]**, inconclusive. These are exploratory seed-clustered
  intervals for two fixed parents; zero observed wins do not prove zero true
  win probability. Better immediate prediction did not establish better play.
- [x] Saved-only audit verifies **73,174 files / 255 units / 192 histories /
  22,842 decisions** and reconstructs traces, endings, scores, paired summaries
  and randomness receipts in **28.19 seconds**, with zero games or fitting.
  Collector native-delivery/inference audits stay sealed; their semantics/logits
  are not independently recomputed by this result audit.
- [x] Verify **3,524 matched noncombat draws / 1,073 identical-input comparisons**,
  with 41 changed learned choices. All 128 original/fork comparisons first differ
  at an identical current public input: **72 combat / 56 noncombat** choices.
  This confirms shared-policy changes, not causal attribution to specific mistakes.
- [x] Identify the common update for follow-up: both arms regress the original
  actor scores onto standardized recorded returns, updating encoder/readout/direct
  path. The auxiliary gradient is their only treatment difference. Tiny fitting
  error on seven related TRAIN worlds does not establish good action ranking.
  Overfitting, score calibration and changed ranking are hypotheses, not isolated
  causes. Preserve the original critic and all historical learning recipes.
- [x] Pass the required repository check again: **2,171 tests (four skipped)**,
  strict types on 435 files, formatting/lint and the C# protocol in **133.96
  seconds**. No training source, recipe, original weights or optimizer state changes.

Next work, in order:

1. **Diagnose saved-menu ranking and calibration before more games.** Compare
   original/fork margins, action ordering and noncombat sampling changes, separating
   common return-regression effects from extra consequence feedback. Do not use
   development outcomes as new teacher labels or select a winning fork post hoc.
2. **Separate prediction from policy learning in a new bounded recipe.** Outcomes
   get their own readout; a prediction-only control must preserve original action
   scores and choices exactly. Any deliberate policy update needs a distinct
   objective and derivative checks. All legal families can remain learnable;
   this is not a permanent small-change or combat-only restriction.
3. **Only then collect the experience the declared update needs.** On-policy PPO
   requires fresh sampled behavior, not these greedy evaluation games or privileged
   teacher continuations. Preference training requires qualified ranking evidence.
   Compare with both original players on fresh whole-game seeds. Do not expand or
   repeat this rejected update merely because fitting loss is small.

No owner command, new game/fit job, checkpoint promotion or adaptive-controller
admission follows this assessment. The earlier owner command below is completed
and historical. GA/other difficulties remain separate deferred work.

### Preserved consequence-learning preparation (commands below are historical)

## Current handoff — bounded combat-consequence learning implemented; fresh-game comparison next

**Test whether extra numerical feedback from combat helps the copied players play
better.** The unchanged originals remain in the comparison. Their exact round-60
weights and every PPO Adam moment/counter **5,658 / 6,045** remain read-only. This
is a separately labeled supervised experiment, not ordinary PPO continuation.
See the [design and single owner command](native-combat-consequence-learning.md)
and [portable evidence](evidence/native-combat-consequence-learning-v1.json).

Completed (#35 / #143 / #146):

- [x] Extract **442 combat decisions / 51 plans / seven TRAIN worlds** from the
  completed teacher, one episode at a time. Average eight conditional returns per
  plan without duplicating its fight eight times. Retain the eighth no-root source
  in the historical denominator. Current public graph plus chosen legal action
  supplies inputs; later observations, plan IDs and hidden state supply no inputs.
- [x] Add explicit native-observed HP, enemy-HP, next-turn, encounter-exit/survival
  and potion-count prediction targets, with honest missing-target masks and nested
  choice boundaries. Health is a prediction task, **not an HP reward or action
  ranking rule**. Full-run victory, the 128-CPU-second budget and existing bootstrap
  score remain unchanged. These are recorded continuations, not causal or optimal
  action values; seven related worlds cannot establish broad generalization.
- [x] Implement matched return-only / consequence-assisted learning and an
  action-blind prediction control. Both principal arms fit identical extra heads;
  only their feedback into the shared representation differs. Use fitting-only
  scaling, equal source/plan/decision weights, a frozen 128-epoch schedule, separate
  fitting/held curves and leave-one-whole-world-out folds for each original player.
- [x] Copy both complete parent/Adam states into four disposable forks. Fix the
  deployment initializer and final epoch before native outcomes, rather than
  choosing a winner on validation data. Fork Adam counters are **5,786 / 6,173**;
  original critic weights and both original state files remain unchanged.
- [x] Pass mathematical gradient/stop-gradient controls and **8/8 native checks**,
  including both identical exact-repeat traces: zero failures, app copies or
  production updates. Verify **106 matched noncombat draws / 56 identical-input
  comparisons**. Shared weights can change noncombat choices; match the rule and
  random draws without falsely claiming those choices are frozen.
- [x] Preserve the preparatory work-unit naming failure and its exact inputs/code;
  it ran no games or fits. Repair key generation and add actual-journal tests.
  Seal each extraction/fit/game unit; restart only clean completed boundaries,
  never uncertain work. Reuse shared frozen engine/runtime/SDK/support files.
- [x] Complete all **63 whole-world validation fits** in **156.78 seconds**, with
  zero evaluation games. Added feedback lowers immediate-HP prediction MSE by
  **16.2% / 4.8%** for the two players and lowers enemy-HP errors, but increases
  final-return errors. Later predictions are mixed, and simple persistence still
  wins several endpoints. Constant potion/survival labels supply no evidence of
  useful mechanics learning. Preserve the predeclared forks rather than retuning.
- [x] Pass **2,171 tests (61 new; four skipped)**, strict types on 435 files,
  formatting/lint and the C# protocol in **132.00 seconds**. Original full-state
  byte hashes and every saved fork/Adam counter still match. Main gameplay remains
  **0/192 attempted**; better play, readiness and promotion are not established.

Next work, in order:

1. **Owner runs the 192-game comparison — NOT STARTED.** Use 32 fresh development
   worlds, both original players and both learned forks. Greedy combat and matched
   noncombat sampling rules apply to every arm. Keep failures in the denominator;
   no forced rest, HP heuristic, extra search, app copy or automatic next experiment.
2. **Assess prediction and actual play separately.** Report fixed-epoch whole-world
   errors against return-only, action-blind, constant and persistence controls;
   inspect fitting versus held errors. In fresh games report wins first, then acts,
   floors, score, failures and CPU. Compare both forks with the originals, not just
   with each other. Two fixed parents and seven training worlds limit conclusions.
3. **Choose the next bounded learning change from those results.** Better tactical
   prediction alone does not establish better decisions. Preserve all forks and
   Adam state; do not silently expand training, reward HP, promote a checkpoint,
   enable adaptive thinking, repeat the unchanged teacher or unfreeze difficulty.
4. **Later runner wording:** distinguish a completed teacher schedule with no
   eligible position from a crashed game, preserving old status/receipts.

The longer owner command and qualified saved-data results are recorded in the
linked handoff. No production checkpoint, push or GitHub Actions follows this work.

### Preserved greedy-turn teacher result (commands below are historical)

## Current handoff — fresh TRAIN greedy-turn teacher complete; qualify richer learning feedback next

**All 469 scheduled game attempts ended cleanly; this teacher still supplies no
admitted better-turn preferences.** Seven of eight new TRAIN source games yield
eligible positions; source `1910003` dies on floor 5 without one. Keep it in the
original denominator, with no replacement or retry. Both round-60 players and
all Adam moments/counters **5,658 / 6,045** remain unchanged. See the
[completed result](native-greedy-complete-turn-teacher-result.md) and
[portable evidence](evidence/native-greedy-complete-turn-teacher-result-v1.json).

Completed (#35 / #143 / #146):

- [x] Finish **8 source games + 53 proposals + 408 scored continuations**: seven
  roots / 51 plans, zero failed/skipped branches, blocked roots, full wins, act
  clears, app copies or optimizer updates. Six roots are normal fights, one elite;
  usable roots split four/three across the two players.
- [x] Preserve and explain `complete_with_gaps` / resource exit **1**: the frozen
  runner treats an unavailable source as a gap. This is completed collection with
  one absent eligible position, not a crashed game or exhausted resource cap.
- [x] Rebuild **352 alternative/reference pairs: 23 higher / 28 lower / 301 tied
  returns (85.5% ties)**. Nine alternatives have higher means, eight lower, 27 tie.
  The strongest has six higher/two tied streams, p **0.015625**, above its unchanged
  adjusted threshold **0.005556**. No post-hoc reversal supplies an admitted target.
- [x] Decode all **469 histories / 73,123 decisions** one at a time and verify
  **64,766 source files**, root/no-root sampling, prefixes, full plans/boundaries,
  native endings, CPU/returns, freezes and lesson tables in **91.72 seconds**.
  Check **7,654 matched noncombat draws / 3,911 identical-input choices**. Neural
  probabilities and delivery semantics are not independently recomputed here;
  the collector's sealed native and full-choice audits remain verified.
- [x] Establish that all 51 plans repeat the same current-fight trace across their
  eight streams. At six roots all plans survive; at the elite root all die. Exit
  HP differs in **168 pairs**, but **120** still reach the same final floor. One
  42-versus-20-HP comparison dies on floor 16 in every stream. Another lower-HP
  plan reaches farther on average: HP alone is not a strategic utility label.
- [x] Record **38.04 wall minutes / 1,675.50 CPU seconds**, 434.08 MB peak RAM and
  797.71 MB final cumulative output across all three collection sessions. Preserve
  original collectors, models, optimizer state, resources and qualification evidence.
- [x] Pass **2,110 tests (four skipped)**, strict types on 424 files,
  formatting/lint and the C# protocol in **129.50 seconds**. Update GitHub #35 /
  #143 / #146 while preserving their previous handoffs. No push or Actions.

Next work, in order:

1. **Qualify a bounded auxiliary combat-consequence learning test.** Turn saved
   public decisions and observed native turn/encounter consequences into explicit
   numerical targets. Check fitting, gradient direction and held-out whole-game
   prediction against simple/current-state controls. Keep every related branch and
   stream in its source game's split; seven roots alone cannot establish broad
   generalization. Both fixed players need separate coverage. Future observations
   are labels only, never extra information in an earlier student input.
2. **Separate tactical prediction from strategic value.** Keep full-run victory and
   the existing bootstrap score unchanged. Auxiliary prediction requires a separate
   versioned loss and an unchanged full-run-only control. Do not silently reward HP,
   Smith or immediate fight survival, relax the original preference gate, recycle
   privileged teacher episodes as ordinary PPO, or repeat an unchanged teacher or
   critic grid. The seven roots do not distinguish fight survival within a root.
3. **Return to a bounded student intervention, then fresh full games.** After short
   numerical controls pass, fork both exact weights and complete Adam states for a
   matched auxiliary-versus-control test. All legal decision families remain
   learnable. Report wins first, then acts/floors/failures and compute. Readiness,
   promotion and adaptive thinking remain unpassed; GA/other difficulties deferred.
4. **Clarify future runner status text** for completed schedules with no-eligible
   sources, retaining original denominators and historical failed resource receipts.

The next learning method is **backlog work, not implemented or launched**. No owner
command is needed for the completed collection. Codex ran only saved-data checks;
no game, fitting job, promotion, push or GitHub Actions follows this assessment.

### Preserved greedy-turn teacher preparation (commands below are historical)

## Current handoff — fresh TRAIN complete-turn teacher implemented; owner collection next

**The bounded teacher now uses greedy combat continuation and fresh TRAIN worlds.**
Both exact round-60 weights, every Adam moment and counters **5,658 / 6,045** remain
unchanged. The long collection has not started. See the
[design and single owner command](native-greedy-complete-turn-teacher.md) and
[portable qualification evidence](evidence/native-greedy-complete-turn-teacher-v1.json).

Completed (#35 / #143 / #146):

- [x] Freeze **eight distinct new TRAIN worlds**, alternating four per player,
  excluding all 28 earlier native seed manifests and two separate control worlds.
  Capture at most one publicly eligible later combat root per source; seal it before
  later outcomes. Failed/no-root sources remain in the eight-world denominator and
  are never replaced. Preserve the inspected development comparison separately.
- [x] Generate one greedy reference turn and a sampled remainder for **every legal
  first move**, including end turn and current potion controls. Keep native nested
  choices/costs/targets; freeze exact plans before continuations. Deduplicate only
  identical traces in fixed order. No final-return, HP or winning-plan selection.
- [x] Replay frozen turns exactly, then use greedy combat, including owned nested
  selections, and matched temperature-0.8 noncombat decisions. Root/repeat/room/family
  draw slots isolate future choices from different combat lengths and proposals.
- [x] Bound proposal CPU at **64 seconds per root / 32 per attempt**. Charge every
  alternative all proposal episode CPU, without amortization, plus its own episode;
  the greedy-only reference pays no proposal overhead. Preserve the original
  whole-run victory / 128-CPU-second objective and bootstrap score. Stop/record
  exhausted budgets and incomplete turns; block failed roots, never retry uncertain
  delivery, retain original source counts and stop beyond two pilot failures.
- [x] Complete **16/16 native controls** in **90.79 seconds**, with zero failures,
  skipped branches, app copies or updates. Both exact repeats match. Verify **28
  shared noncombat draws / 12 identical-input choices** across four candidate/reference
  pairs. Four unique turns contain 13 steps; this short native sample has no nested
  turn steps. Nested behavior is covered by unit tests and preserved earlier native
  qualification, not newly observed in these four turns.
- [x] Saved audit reconstructs **all 1,792 decisions**, first-root sampling, complete
  plans/boundaries, draws/probabilities, CPU charges, repeats and lesson tables in
  **53.29 seconds**, without games or fitting. Journal hashes verify; native delivery
  is not independently semantically reaudited. These are correctness controls,
  not strength evidence or a readiness pass.
- [x] Host-disabled main preflight verifies **75,022 protected old files** and both
  full player/Adam seals, creates no main workspace, and fills only the two passed
  control/audit references in the template frozen before native controls. Runtime
  is **72.96 seconds**, with no games or updates.
- [x] Pass **2,110 tests (52 new; four skipped)**, strict types on 424 files,
  formatting/lint and the C# protocol in **122.76 seconds**. Source checks and both
  complete player files still match; the long teacher remains unstarted.

Next work, in order:

1. **Owner runs the finite eight-world teacher — NOT STARTED.** The upper bound is
   **944 native attempts** before menu/trace deduplication: eight sources, up to
   104 proposals and 832 comparisons. Use one worker, shared frozen inputs, zero app
   copies and 15-minute sessions; 2 GB memory / 4 GB cumulative output. Completed
   attempts resume; uncertain evidence remains preserved. No automatic next stage.
2. **Assess useful lessons before fitting.** Report wins first, then acts/floors/
   bootstrap returns, ties, reliable better/worse turns, CPU and whole-world coverage.
   Keep the eight-source denominator, fixed-world scope and original preference
   rule. Eight streams vary noncombat policy actions, not independent hidden worlds;
   they may be identical under greedy combat. Do not tune on inspected development
   worlds, loosen admission or silently add HP rewards.
3. **Prepare a bounded student test only if targets support it.** Fork both complete
   saved states, preserve every Adam moment, keep legal families learnable and test
   fresh full games against frozen parents. Privileged teacher branches are not
   ordinary PPO data. Base readiness still precedes promotion and adaptive thinking.

Single owner command, from any directory with STS2 closed:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/collect-native-greedy-turn-teacher-v1.sh
```

Codex runs only short controls, saved audits and checks. No long collection,
training, promotion, push or GitHub Actions has started.

### Preserved fresh combat comparison result handoff (commands below are historical)

## Current handoff — fresh combat comparison complete; improve teacher continuation next

**Greedy combat improves average progress for both fixed players, with no full wins.**
The owner completed all 256 fresh-game attempts. Both exact round-60 weights and
every Adam moment/counter **5,658 / 6,045** remain unchanged. See the
[completed assessment](native-combat-behavior-result.md) and
[portable result evidence](evidence/native-combat-behavior-result-v1.json).

Completed (#35 / #143 / #146):

- [x] Complete **64 fresh development worlds × two players × two arms = 256/256
  games**, with zero failures, unattempted games, app copies or optimizer updates.
  The sole change is combat sampling at temperature 0.8 versus exact argmax,
  including nested combat choices. Preserve all legal menus and noncombat behavior.
- [x] Measure **0/128 wins in both arms**, **0 → 2 act-clearing games**, mean floor
  **10.523 → 11.305**, best floor **17 → 27**, mean bootstrap return
  **0.023875 → 0.025864**. Mean game CPU is **2.470 → 2.561 seconds**, under the
  unchanged 128-second whole-run ceiling. This is behavior benefit, not a learned
  weight improvement, search benefit or readiness pass.
- [x] Rebuild the predeclared whole-world paired bootstrap: pooled floor gain
  **+0.781 [95%: +0.242, +1.344]**. Individual gains: player 2 **+0.734
  [−0.078, +1.625]**, player 3 **+0.828 [+0.234, +1.469]**. Resample 64 worlds
  jointly across both fixed players; zero observed wins do not prove equivalence.
- [x] Verify **5,403 shared noncombat draws / 1,392 identical-input choices** across
  128 paired player/seeds. Saved audit checks **256 receipts / 45,281 files**, all
  bindings/endings/returns/CPU, compact RNG receipts and tables in **42.46 seconds**.
  Both full player/Adam seals match. Collection audited every decision; this short
  outcome check does not repeat neural inference or semantic delivery auditing.
- [x] Record **39,343 decisions / 252 nested combat selections** and two collection
  sessions totaling **19.16 wall minutes / 927.23 CPU seconds**, 437.03 MB peak RAM
  and **421.91 MB final cumulative output**. Do not sum cumulative storage or use
  only the last session's time as the entire experiment.
- [x] Pass **2,058 tests (four skipped)**, strict types on 414 files, formatting/lint
  and the C# protocol in **123.75 seconds**. Tracked changes are documentation only;
  the private audit uses saved evidence and both complete player files still match.

Next work, in order:

1. **Prepare a bounded complete-turn teacher test with greedy combat continuation.**
   Use fresh TRAIN worlds and matched noncombat behavior. Compare alternative turns
   against the cheap greedy-only reference; charge any search separately. This
   result supports the continuation choice, not additional search or useful labels.
2. **Check teaching signal before another student update.** Count ties, reliable
   better/worse turns and independent-world coverage under the original rule. Keep
   fixed-hidden-world teacher data explicitly privileged and separate from ordinary
   PPO. Do not tune on these inspected development worlds, enlarge the old flat
   teacher, loosen admission or silently add HP rewards.
3. **Test supported targets in a bounded student comparison.** Fork both full
   weights and every Adam moment, keep all legal action families learnable and
   evaluate fresh complete games against the frozen parents at equal CPU ceilings.
   Greedy evaluation does not replace the actual sampled behavior required for
   ordinary PPO. Foundation readiness still precedes promotion and adaptive thinking.

**No owner command is needed for this completed comparison.** No new long task,
training, promotion, push or GitHub Actions follows this saved assessment.

### Preserved combat-behavior preparation handoff (commands below are historical)

## Current handoff — fresh greedy-versus-sampled combat comparison qualified; owner run next

**The requested combat-only comparison is implemented and qualified.** Both exact
round-60 players, full weights, every Adam moment and counters **5,658 / 6,045** remain
unchanged. The long comparison has not started. See
[design and single owner command](native-combat-behavior-comparison.md) and
[portable evidence](evidence/native-combat-behavior-comparison-v1.json).

Completed (#35 / #143 / #146):

- [x] Change only combat behavior: temperature-0.8 sampling versus the current
  policy's exact argmax, including combat-owned nested selections. Preserve every
  advertised strategic option and existing shop navigation. Use observed public
  ownership/exits; unknown owners fail instead of inventing actions. No search,
  privileged future plans, HP reward, model fitting or automatic promotion.
- [x] Match outside-combat policy, temperature and RNG by game seed, public room,
  family and visit. Combat choices do not advance noncombat streams; an extra reward
  cannot shift another floor's rest draw. Same public inputs/slots produce identical
  choices; differing HP/resources can legitimately change noncombat decisions.
- [x] Freeze **64 fresh development game seeds × two players × two arms = 256
  attempts**, excluding all 26 historical native seed manifests and two new control
  seeds. Counterbalance arm order without outcomes. Summarize both players and
  bootstrap paired complete-game seeds jointly across them; do not treat 128
  player/seed pairs as independent worlds or infer true win equality from zero wins.
- [x] Complete **12/12 native control games** with zero failures/app copies/updates:
  eight primary cells plus four matching exact repeats. Verify **207 shared
  noncombat draw slots / 50 identical-input choices**. Observe 13 nested combat
  selections plus noncombat selections, generated cards, rests, shops and rewards.
  Scoped correctness coverage, not playing-strength evidence.
- [x] Reconstruct **all 2,053 saved decisions**, ownership, draws/probabilities,
  endings, scores, repeat traces and paired tables in **36.51 seconds**. Native
  control takes **76.00 seconds**, 56.05 CPU seconds, 398.02 MB peak memory and
  35.80 MB retained. Collection audits delivery; saved recheck verifies journal bytes.
- [x] Pass **2,058 tests (33 new; four skipped)**, strict types on 414 files,
  formatting/lint and C# protocol in **120.25 seconds**. Verify **63,176 protected
  old files / 35,038 control-source files** and both full player/Adam byte seals.
  Main preflight passes with native hosts disabled and creates no comparison
  workspace. Only passed control/audit references change from the frozen template.

Next work, in order:

1. **Owner runs the finite fresh-game comparison — NOT STARTED.** Allow **20–35
   minutes**; one native process, shared frozen files, zero app copies, 15-minute
   sessions, 2 GB memory / 4 GB cumulative outputs. Resume sealed games at clean
   boundaries. Preserve uncertain work, never retry it automatically or replace seeds.
2. **Assess playing benefit before more teacher collection or fitting.** Compare
   full wins first, then acts/floors/declared bootstrap returns, failures and actual
   CPU. Keep each player's result and whole-seed uncertainty. Verified failures and
   unattempted games retain the original denominator and zero evaluation value.
3. **Choose the next bounded learning change from that evidence.** Better combat
   continuation or candidate quality remains the goal; do not scale the prior flat
   teacher, loosen its preference rule, silently reward HP or tune on the old eight
   inspected worlds. Preserve both full states and require fresh complete-game
   evaluation. Foundation readiness still precedes adaptive thinking.

Single owner command, from any directory with STS2 closed:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/compare-native-combat-behavior-v1.sh
```

Codex ran only short controls, saved audits and checks. No long comparison, training,
promotion, push or GitHub Actions was started. No next experiment follows the command.

### Preserved combat-planning result handoff (commands below are historical)

## Current handoff — combat-planning pilot complete; isolate cheap greedy behavior next

**The finite planner comparison finished cleanly, with mixed strategic results and
no reliable new better-turn labels.** Neither player was trained. Both exact weights,
all Adam state and counters **5,658 / 6,045** remain unchanged. See
[completed assessment](native-bounded-combat-planning-result.md) and
[portable result evidence](evidence/native-bounded-combat-planning-result-v1.json).

Completed (#35 / #143 / #146):

- [x] Finish **756/756 native attempts**: 252 combat proposals + 504 selected-plan
  evaluations, reusing 504 verified old baselines. Zero failures/skips/blocked turns,
  app copies, full wins or optimizer updates. Eight original TRAIN worlds / 63 turns;
  dependent branches are not independent fresh games or ordinary PPO experience.
- [x] Measure the mixed outcome: tested encounter exits alive **332 → 344 / 504**,
  average floor **11.377 → 11.784**, act-clearing branches **5 → 3**, best floor
  **22 → 22**, mean bootstrap return **0.025742 → 0.026040**. Planning versus its
  paired baseline gives **96 higher / 34 lower / 374 tied returns**. Four worlds
  have identical paired returns; three have positive mean changes and one negative.
- [x] Rebuild alternative-turn feedback: **25/65/350 higher/lower/tied** becomes
  **39/84/317** (79.5% → 72.0% ties). The unchanged rule admits **zero** better-turn
  preferences; smallest positive-mean sign p remains **0.1445**. No readiness pass.
- [x] Decompose proposals: **51/63 selections use the greedy remainder**. Twelve
  choose another sample: one survival rescue, eleven higher-HP alive exits. Eleven
  turns have four identical proposals; all four die for twenty turns. The original
  comparator samples actions, so the benefit of search over cheap greedy combat
  remains unmeasured. Do not equate surviving with better full-run play.
- [x] Verify **756 receipts / 63,175 source files**, all bindings, endings, returns,
  CPU charges, selection and tables in **130.06 seconds**. Decode 38,460 proposal
  decisions / 252 exits and reconstruct 2,453 remainder steps. Preserve both full
  states. Scored continuation probabilities are not independently reconstructed;
  retained native journals and collection delivery audits remain verified.
- [x] Reconcile all sessions: **37.76 wall minutes**, 1,842.17 CPU seconds,
  465.16 MB peak RAM / 1.282 GB cumulative output. Mean charged case CPU is
  **2.125 → 10.464 seconds**, inside the same 128-second ceiling. Repeated search
  accounting charges are separate from physical experiment CPU.
- [x] Pass **2,025 tests (four skipped)**, strict types on 406 files,
  formatting/lint and C# protocol in **119.54 seconds**. Tracked changes are
  documentation only; both complete player/Adam byte seals still match afterward.

Next work, in order:

1. **Prepare a small matched sampled-versus-greedy combat control.** Use both
   preserved players, identical noncombat behavior, explicit RNG streams and fresh
   whole-game seeds. If reusing the old roots to compare search, include an
   always-greedy remainder arm. Measure wins, acts, floors, failures and actual CPU;
   do not tune against these already inspected eight worlds.
2. **Improve continuation or candidate quality from that evidence.** Do not expand
   the unchanged four-proposal teacher, loosen its preference rule, silently reward
   HP or launch another critic grid. Local survival alone has not supplied reliable
   strategic targets. Freeze any changed teacher/student method separately and
   validate across whole worlds.
3. **Use supported targets for a bounded student test.** Fork both exact full
   weights and every Adam moment, keep all legal action families learnable, separate
   privileged teacher data from ordinary PPO and evaluate fresh complete games.
   Foundation readiness still precedes model promotion and adaptive thinking.

**No owner command is needed for this completed comparison.** No new long task,
training, promotion, push or GitHub Actions follows the saved assessment.

### Preserved bounded-combat preparation handoff (commands below are historical)

## Current handoff — bounded combat-planning comparison qualified; owner pilot next

**The bounded native planner comparison is implemented and qualified.** It preserves
both exact players and all Adam state, reuses the complete-turn pilot's baseline,
and tests whether completing a fight with sampled planning improves full-run feedback.
See [design and owner command](native-bounded-combat-planning.md) and
[portable evidence](evidence/native-bounded-combat-planning-v1.json).

Completed (#35 / #143 / #146):

- [x] Generate four combat remainders per original initial turn: one greedy and
  three sampled continuations. Native transitions handle subsequent turns and nested
  choices. Seal each encounter exit before later decisions; reject unknown ownership,
  incomplete traces, changed observations/costs/targets and decision/storage caps.
- [x] Select by observed alive exit, remaining public HP and fixed proposal order.
  The selector accepts no later run scores, floors or wins. This is an explicit
  tactical heuristic, not a new HP reward. Original full-run victory and bootstrap
  score remain unchanged; fixed-world teacher branches are not ordinary PPO.
- [x] Charge every evaluation for all four search episodes plus its own execution,
  without amortization, inside the original 128-CPU-second whole-run ceiling. Search
  is capped at 64 CPU seconds total / 32 per proposal. Retain actual resource usage
  separately; equal ceilings do not mean equal CPU spending.
- [x] Complete **28/28 native control attempts** with zero failures/skips/blocked
  turns or app copies. Exact duplicate selected traces and two fresh original
  baseline traces match. Eight old baseline episodes are reused. Two sessions use
  **247.23 wall seconds**, 158.20 CPU seconds, 372.93 MB peak memory and 56.26 MB
  cumulative output. The two-world control is a correctness check, not better play.
- [x] Reconstruct all **4,338 saved public decisions**, probabilities, plans,
  encounter exits, tactical selection, charged costs and tables in **60.92 seconds**.
  Native delivery is audited during collection; saved verification checks those
  journal bytes without claiming a new independent delivery semantic reaudit.
- [x] Pass **2,029 tests (50 new)**, strict types on 406 files, formatting/lint and
  C# protocol in **129.17 seconds**. Verify **51,213 original evidence files** and
  **34,547 control-source files**, preserving both full player/Adam byte seals and
  counters **5,658 / 6,045**. Main preflight passes with native hosts disabled and
  creates no pilot workspace. Only control/audit IDs change from the predeclared
  main template; roots, proposals, ranking and budgets stay fixed.

Next work, in order:

1. **Owner runs the finite comparison — NOT STARTED.** Reuse all 504 old baseline
   episodes. Eight original TRAIN worlds / 63 initial turns require 252 search
   attempts plus 504 selected-plan evaluations: **at most 756 new attempts**. Allow
   roughly 60–90 minutes, shared immutable game/runtime/support files, one process,
   15-minute sessions, 2 GB memory / 4 GB outputs. Clean pauses resume sealed work;
   uncertain or changed evidence stops for inspection. No automatic retry/repair.
2. **Assess actual benefit before more collection or fitting.** Compare full-run
   wins, floor/return changes, encounter exits, failures, actual/charged CPU and how
   often initial turns still tie. One hidden world per root; conditional streams
   are not independent seeds. Keep the original preference rule and uncertainty.
   HP selection can spend scarce resources; it is not proof of strategic improvement.
3. **Choose a bounded student intervention from the evidence.** Keep public-only
   current inputs and whole-world fitting/selection, fork both exact full states
   and every Adam moment, keep all legal families learnable, and test fresh complete
   games at equal declared compute. No future plan observations in student features.
4. **Keep the foundation priority.** No new critic grid, other difficulties, large
   GA, model promotion or adaptive controller follows this collector. Readiness
   still precedes variable thinking budgets. Revise a flat method rather than
   automatically scaling it.

Single owner command, from any directory with STS2 closed:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/compare-native-combat-planning-v1.sh
```

Codex ran only the short control, saved audits and repository checks. No long pilot,
training, promotion, push or GitHub Actions was started. The command resumes only
this finite comparison; no subsequent experiment or fitting follows completion.

### Preserved complete-turn result handoff (commands below are historical)

## Current handoff — complete-turn pilot finished; test combat continuation before scaling

**The finite complete-turn teacher completed cleanly, but it has not established
better play or reliable better-turn labels.** Both exact players and all Adam state
remain intact. See [completed result](native-complete-turn-teacher-result.md),
[portable evidence](evidence/native-complete-turn-teacher-result-v1.json) and the
[preserved collection design](native-complete-turn-teacher.md).

Completed (#35 / #143 / #146):

- [x] Finish **569/569 native attempts**: 65 proposals become 63 unique plans,
  followed by 504 scored branches across eight original TRAIN worlds. Zero
  failures/skips/full wins/app copies or optimizer updates. Five dependent branches
  clear an act; best floor 22. No nested-selection decisions occur in this pilot.
- [x] Reconstruct all outcome tables: **25 higher / 65 lower / 350 tied paired
  returns (79.5% ties)**. Greedy reference has the highest sampled mean, including
  ties, in six of eight positions. No alternative passes the unchanged preference
  rule; smallest positive-mean improvement sign p is 0.1445. Two positions are flat.
- [x] Check why turns tie: **40 alternatives change the exact public boundary; 18
  still have identical paired final returns**. An elite turn leaves 28 HP against
  53 enemy HP, another 20 against 84, yet both lose every continuation on floor 7.
  This is a feedback limitation, not proof that HP alone should become a reward
  or that stronger continuation will necessarily recover these source positions.
- [x] Verify **569 receipts / 33,426 source files**, terminal evidence, bindings,
  returns, candidate freeze and all tables in **33.56 seconds**. Decode 9,942
  proposal decisions and verify 65 proposal boundaries / 225 turn steps. Preserve
  both complete model/Adam seals and counters **5,658 / 6,045**. Scored continuation
  probabilities are not independently reconstructed by this saved-only assessment;
  native journal bytes verify and collection delivery audits remain preserved.
- [x] Reconcile all three collection sessions: **28.71 wall minutes**, 1,391.65 CPU
  seconds, 425.44 MB peak memory and 850.26 MB cumulative output. Do not add
  cumulative storage or mistake the final-session duration for the experiment total.
- [x] Pass **1,979 tests**, strict types on 396 source files, formatting/lint and C#
  protocol checks in **119.65 seconds**; tracked changes are documentation only.

Next work, in order:

1. **Qualify a bounded combat planner as continuation and candidate source.** Keep
   frozen public roots/plans, native transitions, outcome-blind proposals and equal
   declared compute. Start with a short correctness/cost control, then freeze one
   finite owner-run comparison. Record fight completion, postfight health and loss
   location as diagnostics alongside genuine complete-run outcomes and the explicit
   bootstrap score. No silent HP reward, outcome-selected positions or claim of
   stronger play before measurement. Weak continuation, limited candidates and
   already difficult source positions remain competing explanations.
2. **Declare a bounded student intervention only if feedback supports it.** Preserve
   uncertainty and whole-source-world validation; fork both players and every Adam
   moment, keep every legal decision family learnable, and test fresh complete games
   at equal compute. Teacher counterfactuals remain separate from ordinary PPO.
3. **Do not scale the unchanged teacher or loosen its preference rule.** No further
   critic grid, other difficulty, large GA or adaptive controller is required here.
   Foundation readiness still precedes variable thinking budgets.

**No owner command is needed for this completed collection.** No new game, fitting,
model promotion, push or GitHub Actions follows the saved assessment. Long tasks stay
owner-run; the next command will accompany a separately implemented and qualified plan.

### Preserved complete-turn preparation handoff (commands below are historical)

## Current handoff — complete-turn teacher ready; owner-run pilot next

**The complete-turn comparison teacher is implemented and qualified.** It compares
complete remaining-turn sequences through an observed native boundary. Both players,
full Adam states and the coarse predictor remain unchanged. No new fitting or model
promotion occurs. See [design, evidence and owner command](native-complete-turn-teacher.md)
and [portable metrics](evidence/native-complete-turn-teacher-v1.json).

Completed (#35 / #143 / #146):

- [x] Preserve the eight public TRAIN roots, both continuation players, native A8
  rules, full-run objective and score. Propose one greedy reference turn and one
  sampled complete turn for every legal first action; all offered moves remain in
  scope. Include nested choices and native early endings; reject unknown ownership
  and truncated/capped turns. Bound plans to 64 decisions / 1 MB each.
- [x] Seal proposals before their continuation choices and freeze all candidate sets
  before scored comparisons. Exact trace deduplication retains aliases/reference;
  selection accepts no final-return/floor/win fields. Native proposal games finish
  for clean closure, but their outcomes do not rank or filter candidates.
- [x] Complete **39/39 native control branches** (13 proposals, 12 distinct plans,
  26 comparisons), including exact duplicate reference traces. All public turn
  boundaries match; zero failures/skips/wins/app copies or optimizer updates.
  Two sessions total **142.37 seconds**, 390.59 MB peak RAM / 66.46 MB cumulative
  output. This control has no native nested selection; unit regressions cover those
  paths and the existing bridge's qualification remains separate.
- [x] Reconstruct **6,077 saved public decisions**, proposal sampling, forced choices,
  boundaries, continuation probabilities, returns, candidate sets and all tables.
  Saved audit takes **32.52 seconds**; main admission requires this exact control
  and audit. Fixed-world streams remain ineligible for ordinary PPO/public-belief
  optimality claims. Native delivery is audited during collection; saved recheck
  verifies journal bytes, not an independent native-delivery semantic reaudit.
- [x] Pass **1,979 tests (52 new)**, strict types on 396 files, formatting/lint and C#
  protocol checks in **118.44 seconds**. Verify **30,487 protected original/control
  files** and both exact full model/Adam checkpoints unchanged (counters 5,658 / 6,045).
  Cached control reuse and main preflight pass with native hosts explicitly disabled.
- [x] Freeze the main recipe and one owner wrapper: eight original worlds, 65 proposals
  plus at most 520 comparisons (**585 total attempts**), eight matched continuation
  streams per unique plan. Proposal temperature 1.2, continuation temperature 0.8;
  independent namespaces avoid consuming continuation randomness during generation.

Next work, in order:

1. **Owner runs the finite pilot — NOT STARTED.** Allow roughly 30–45 minutes from
   current timing, one process, shared immutable game/runtime/support files, zero
   app copies, 15-minute sessions, 2 GB memory / 4 GB outputs. Clean resumption reuses
   sealed attempts; uncertain evidence is preserved and never retried automatically.
   Verified failed workers block their root while other planned worlds may continue.
   All source worlds, failures and skipped work remain reported.
2. **Assess whether coherent turns provide useful lessons.** Reconstruct tables,
   examine uncertainty, ties, rare outcomes and source diversity. Original worlds
   stay the independent units; 585 attempts do not mean 585 independent seeds.
   Retain the original preference rule and full wins as primary. Do not manufacture
   winning labels, choose a convenient outcome subset or treat a best sample as a
   stronger player. If still flat, assess stronger continuation before scaling.
3. **Declare a bounded student/credit experiment only if feedback supports it.**
   Future student inputs are only the public state at the decision being taught,
   never later plan observations. Fork both players and complete Adam state, keep
   all legal families learnable, and test fresh complete games at equal compute.
   Teacher counterfactuals are separate supervision, not ordinary PPO episodes.
4. **Keep foundation work focused.** No new critic grid, other difficulties, large
   GA or adaptive controller is required for this pilot. Source/world-aware input
   or continuation improvements remain conditional. Readiness precedes adaptive
   thinking; no automatic training or next experiment follows collection.

Single next command (from any directory, with STS2 closed):

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/collect-native-complete-turn-teacher-v1.sh
```

No long collection, new fitting, model promotion, push or GitHub Actions is started
by Codex. Historical teacher/value results and implementation bytes remain preserved.

### Preserved completed later-turn teacher assessment

## Current handoff — later-turn teacher complete; improve the feedback before more training

The owner completed **456/456 native branches**, with zero failures/skips/wins or app
copies. The saved assessment reconstructs terminal returns and action tables, verifies
all receipts / 28,943 source files, and preserves both players and complete Adam states.
No fitting, model promotion or adaptive-controller work occurred.
See [result and evidence](native-later-combat-teacher-result.md) and
[original collection design](native-later-combat-teacher.md).

Completed (#35 / #143 / #146):

- [x] Collect all 57 actions across eight later combat menus with eight continuation
  streams each. Eight original hidden worlds are the independent source units;
  the 456 fixed-world branches are not ordinary PPO games or 456 independent seeds.
- [x] Rebuild the full paired comparison: **23 higher, 79 lower and 290 tied returns**
  (74.0% ties), six varied menus / two flat. Zero alternatives pass the unchanged
  improvement rule; the smallest improvement sign p-value is 0.3633. Three dependent
  branches clear an act and reach floor 21; no full-run wins or policy gain established.
- [x] Inspect negative examples and rare gains. Ending the turn is clearly worse in
  two menus, but its current policy probability is already only 0.0066% / 0.1011%.
  Some apparent better choices depend heavily on one continuation or rare act clear.
  Post-hoc reverse tests and leave-one-out checks do not admit new trusted labels.
- [x] Verify exact bindings, sealed headers/traces, native ending fields, whole-run
  scores, uncertainty and tables in a **17.49-second saved-only check**. Both full
  player/Adam byte seals and counters (5,658 / 6,045) agree. Eight current public-root
  policy distributions reproduce the reference choices. Full continuation probabilities
  across 68,524 declared decisions are not rerun by this assessment; the prior 24-branch
  control reconstructed all of its 3,950 choices. Do not imply a full behavior reaudit.
- [x] Reconcile both collection resource sessions: **23.01 minutes total wall time**,
  1,127.77 CPU seconds, 391.79 MB peak RAM, 674.54 MB cumulative output. The main report's
  wall-time field covers the final collector session only. Do not add cumulative storage.

Next work, in order:

1. **Implement a small coherent-turn comparison teacher.** Compare bounded legal move
   sequences through end turn, instead of forcing one card and immediately reverting
   to the same continuation. Freeze generation, roots and budgets before outcomes.
   Preserve the existing teacher and all results; this is a hypothesis, not a proven
   improvement. No larger repeat of the unchanged one-action batch is the next task.
2. **Qualify the changed feedback and run one finite owner pilot.** Native transitions,
   public-only student inputs, fixed-world ownership, repeated continuations and the
   declared full-run outcomes/auxiliary score remain explicit. No handwritten HP or
   upgrade rewards. If turns remain flat, assess stronger continuation before scaling.
3. **Test a declared numerical learning intervention only when useful signal exists.**
   Use uncertain sequence/action targets, whole-source-world fitting/selection and
   fresh complete games at equal compute. Fork both players and every Adam moment;
   all legal decision families remain learnable. Do not manufacture confidence labels
   or treat hindsight branches as on-policy PPO. Wins remain primary.
4. **Keep the current critic and difficulty.** No new critic grid, other ascensions,
   large GA or adaptive budget controller is required here. Rich shared representation
   and independent outcome coverage remain conditional follow-ups. Foundation readiness
   still precedes adaptive thinking.

**No owner command is needed for this completed collection.** Long collection/fitting
remains owner-run. No new games, training, push or GitHub Actions follows automatically.
Result documentation passes formatting/lint and strict types. The full repository
suite stops at its 240-second cap; this is not a new full pass. Preserve the capped
resource receipt rather than automatically launching a longer check. Learner code
and all player/optimizer files remain unchanged.

### Preserved completed rich-correction handoff

## Current handoff — baseline-preserving rich correction completed; retain the current predictor

**The controlled correction test is implemented and complete.** It reuses 128 saved
ordinary TRAIN games in 16 outer whole-game folds, preserving both players and every
Adam state. The original 20-feature ridge keeps lambda 0.001; only extra rich slopes
receive a separately selected penalty. No correction is an explicit candidate.
Each inner split refits its own coarse offset, without validation-return leakage.
See [design and result](native-residual-value.md) and
[portable evidence](evidence/native-residual-value-v1.json).

- **No useful gain:** equal-game withheld MSE is **5.512797865e-5 baseline** versus
  **5.532921364e-5 correction** (+0.365%). No correction is selected in 10/16 folds;
  four choose lambda 100, two choose 10. Two cohorts improve slightly, two worsen.
- **Baseline preservation passes:** all 16 original coarse coefficient arrays and
  forecasts match bit-for-bit. Saved-only verification reconstructs all selected
  models, choices, predictions, pure fitting errors and separate penalties.
- **All 128 games remain in the official result.** The rare act clear and ordinary
  127-game sensitivity both fail to reveal a useful gain. Do not remove rare successes
  or reinterpret reused development evidence as untouched confirmation.
- **Short execution only:** control 24.97 seconds, complete comparison 44.27 seconds,
  saved verification 27.62 seconds; zero new games, app copies or actor/Adam steps.
  The main comparison uses 730.07 MB peak RAM and 4.49 MB new output. Source checks
  protect 11,755 files including the two full model/optimizer checkpoints.

Next work, in order (#35 / #143 / #146):

1. **Keep the current predictor; return to informative action learning.** Do not
   integrate this correction, repeat unchanged PPO at greater scale or search another
   critic grid on these same outer targets. The negative result does not prove that
   rich information is useless or that regularization alone caused the earlier gap.
2. **Predeclare a revised finite action-comparison pilot.** The completed first native
   combat teacher has 78.1% ties and zero admitted preferences from fight-entry roots.
   Use more consequential later-turn positions or coherent turn choices, retaining
   whole-run outcome labels, uncertainty and source/policy/world ownership. Keep
   confidence thresholds intact; dependent fixed-world branches are not new ordinary
   PPO games or public-belief-optimal labels. Use existing diagnosis rather than
   another general audit with no proposed change. Long collection remains owner-run.
3. **Test whether useful lessons change the actor and improve fresh games.** Preserve
   both players and full Adam in separate forks. Declare any auxiliary supervision
   separately, keep all legal decision families learnable, and compare gameplay on
   fresh whole-game seeds at equal compute. Forecast MSE alone is not the goal.
4. **Representation/data follow-ups remain conditional.** A compact shared entity/field
   encoder or additional independent act-clear coverage may help, but are not a new
   mandatory critic-tuning sequence before action learning. Qualify policy conditioning
   before pooling different players' outcomes. No strategic reward redesign is implied.
   Full wins remain primary, readiness precedes adaptive thinking, GA/other difficulties
   remain deferred.

**No owner rerun is needed for this completed test.** No new learning, collection,
promotion, push or GitHub Actions follows automatically.

**Verification passes:** 1,904 repository tests (18 new controls), formatting/lint,
strict types on 381 files and the C# protocol contract in **113.76 seconds**, with
399.16 MB peak RAM and no cap hit. The post-check audit verifies all protected source
bytes and both full model/Adam checkpoints unchanged. Their optimizer counters remain
5,658 and 6,045, with every first and second moment preserved.

### Preserved completed prediction-error diagnosis

## Current handoff — saved errors show rare outcomes, dictionary omissions and coupled shrinkage

**Saved prediction-error diagnosis is complete.** All 128 ordinary TRAIN games and
13,793 choice-bearing public inputs reconstruct exactly; published held-game errors
match, with no refits, game attempts, actor/Adam changes or promotion. The current
ridge remains the best tested baseline. See [diagnosis](native-value-error-diagnosis.md)
and [portable evidence](evidence/native-value-error-diagnosis-v1.json).

Material findings (#143 / #35 / #146):

- **One Act 1 clear contributes 54.75% of current-ridge squared error.** Its own fitting
  fold has no act clears. Most error is before the eventual advancement; after entering
  Act 2 its progress-aware prediction is close to the observed auxiliary return. This
  does not prove the rare outcome was predictable from early public information.
- **The rich models also lose on the other 127 games:** rich linear +30.05% MSE;
  rich neural +65.21%. Removing the rare game is a sensitivity analysis, never a new
  official denominator or a reason to reduce successful outcomes' weight.
- **Unfamiliar content is only part of the picture.** About 6.34% of public fact
  occurrences are new to the fitting games; 74.01% are familiar, varying facts omitted
  by the bounded dictionary. These are redundant encoder-fact counts, not semantic
  information percentages. Unseen entity definitions correlate with baseline error,
  but weakly with the rich model's excess error; causality is not established.
- **One penalty also suppresses the simple features.** The rich arm's simple-feature
  coefficient norm is a median 2.63% of the coarse-only arm's. Removing its rich term
  makes its own forecast worse; the issue is not evidence that all rich information
  is useless. Correlated columns can redistribute coefficients too: this motivates a
  controlled test, not a causal conclusion or a validated alternative predictor.
- **Broader saved TRAIN coverage is still sparse:** five act-clearing trajectories,
  zero wins in 512 games across different behavior policies. Do not pool them as one
  unchanged player's on-policy data or count exploration-arm repeats as independent
  successful seeds. Critic dictionary omissions do not imply missing engine mechanics.

Next work, in order:

1. **Implement one coarse-baseline-preserving rich correction comparison.** Refit the
   current coarse baseline separately within each inner fitting set; learn a rich
   residual with its own regularization, including no correction as a candidate. Select
   only on inner whole games, then refit outer train and test outer held games. Preserve
   the current predictor, both actors and all Adam state. An outer-fitted baseline must
   never supply inner-fold offsets. This tests coupled shrinkage without another
   large architecture change or any new actor restriction.
2. **If needed, test a compact shared entity/field representation.** Keep identity,
   ownership and current numeric values; measure coverage and generalization instead
   of enlarging the owner/full-text dictionary blindly. No exhaustive mechanics sweep
   or alternate ascension support is a prerequisite for this A8 learning work.
3. **Plan additional independent outcome coverage only with a declared purpose.**
   Measure learning curves and act-clear coverage, retain policy ownership or qualify
   policy conditioning, and consider an explicit curriculum if weak play cannot
   generate informative outcomes. Leave long collection/training to the owner. Do not
   silently alter the victory objective, add strategic rewards or relabel historical
   counterfactual games as fresh PPO experience.
4. **Fresh confirmation, then useful action credit.** Freeze a supported recipe before
   untouched whole-game forecasts and bounded equal-compute learning from both saved
   players/full Adam. If the one controlled correction test has no useful signal,
   return to the actor/action-learning bottleneck rather than endlessly tuning critics.
   Adaptive thinking remains behind base readiness; GA and other difficulties deferred.

All diagnostic jobs finished within short caps (10–77 seconds each); zero app copies,
optimizer updates and game attempts. Existing model reports/code remain immutable.
All **1,886 repository tests**, formatting/lint, strict types and the C# protocol
contract pass in **124.02 seconds** (105.77 CPU seconds, 388.92 MB peak RAM). The
post-check audit verifies **11,842 source files**, including both players and every
Adam moment/counter, unchanged. The diagnosis is ready for local commit; no push,
GitHub Actions, new training or owner-run task follows this inspection.

### Preserved completed linear-comparison handoff

## Current handoff — regularized public linear values with whole-game validation

The **matched-input neural study is complete**, 16 encoded folds / 48 paired fits,
128 saved TRAIN games, three numerical initializers. At the fixed primary update 24,
held MSE is **5.5128e-5 current ridge**, **5.5841e-5 coarse masked neural** and
**7.1256e-5 rich neural**. Rich is **29.3% worse** than ridge, in all four cohorts and
all three initializer summaries. Fitting error falls as held error rises; 99.4% of the
combined fitting-loss decrease is a smaller weight penalty. This supports testing
regularization and generalization, not adopting this network or assuming more games
alone will fix it. Existing reports/code and both players/full Adam states are preserved.

Ordered work (#143 / #35 / #146):

1. **Regularized rich-input linear value — implemented and benchmarked.**
   Compare current ridge, tuned coarse linear and tuned rich linear on the sealed input
   cache. Closed-form ridge removes neural initialization, Adam and epoch count. Keep
   separate pure prediction errors and penalties; do not tune on outer-held targets.
2. **Whole-game nested selection.** Each outer fold fits on 24 games and holds eight.
   Select ridge strength using three 16-fit/eight-validation inner splits, separately
   for each arm; refit all 24 and score the untouched outer eight. Each game has equal
   mass. Keep the four player/round cohorts separate. The progress offset is fixed;
   never reuse the old outer-fit ridge as an inner offset, which leaks validation returns.
3. **Freeze the cached dictionary honestly.** It was selected using outer-fitting inputs
   in the previous study; it excludes outer-held inputs but is not rebuilt within inner
   folds. Means/scales/centering and coefficients fit only the current fitting games.
   Reused development games cannot provide untouched confirmation, and overlapping folds
   or numerical repeats cannot be counted as independent games/players.
4. **Require fresh confirmation before credit integration.** Only a supported frozen
   value recipe advances to fresh whole-game forecast validation and then bounded
   learning from both saved players/full Adam states. Measure gameplay at equal compute;
   wins remain primary and auxiliary floor/acts secondary. No automatic adoption, PPO
   expansion, reward redesign, adaptive controller or game attempts follow this study.
5. **Later follow-ups remain evidence-driven.** More informative combat teacher roots,
   policy-conditioned values, additional independent games or another model are separate
   choices. GA/direct evolution, other difficulties and large sequence models remain
   deferred; useful base play/readiness precedes adaptive thinking.

The short control uses one real cached 24/8 outer fold; the main comparison has 16
independently sealed restartable folds. It reuses public inputs without decoding histories,
never touches the saved actors/optimizers, and verifies source bytes before and after.
See [design, validation boundaries and execution guide](native-linear-value.md).

**Completed result:** all 16 folds / 128 whole-game predictions, **896 closed-form
ridge solutions**, in **84.96 seconds** (495.50 MB peak RAM, 5.30 MB output). Current
ridge MSE is **5.5128e-5**; tuned coarse linear **5.5328e-5** (+0.36%); tuned rich linear
**6.3903e-5** (+15.92%). Rich remains worse in every cohort. Most rich folds select
strong shrinkage (lambda 10; three choose 1, two choose 100). **No replacement is adopted.**
All 32 saved models and chosen lambdas reconstruct; forecasts agree bit-for-bit, separate
fitting error and penalty terms agree, and **11,681 source seals** verify unchanged.
The saved-only audit takes 10.00 seconds, no refits or games.

**Next evidence-driven item:** inspect whether remaining errors concentrate in rare long
runs and unseen public facts before selecting a new data/representation intervention.
Do not search another grid on outer targets or blindly expand PPO. More independent
whole games, stronger interaction features or better training lessons remain hypotheses;
none is established as the fix by this negative study. Any new collection is separately
bounded and owner-run when long. Keep both players and all Adam state as starting points.

**Final repository verification passed on 2026-10-20.** The owner completed the full
formatting/lint, strict typing, test suite and C# protocol check in **116.07 seconds**,
with **99.39 CPU seconds** and **385.27 MB** peak RAM. Receipt:
`sha256:bf55e76c5586d10008893d30f0aaf68c3bcbfd7aae4b5d188f7f937efc80ee33`.
The earlier four-minute capped check remains preserved as incomplete historical evidence;
the completed owner receipt supersedes its pending handoff. All **11,681 protected source
files**, including both players and full Adam states, verify unchanged after the check.
The 17 focused regression tests also pass. The implementation is ready for a local commit;
no push, GitHub Actions or long follow-up is started by Codex.
[Portable results, receipts and limitations](evidence/native-linear-value-v1.json).

**No rerun is needed.** The comparison and final verification are complete. The next
work item is the saved-prediction diagnosis above, not another unchanged training run.

### Preserved teacher preparation (completed above)

## Current handoff: collect native combat comparisons, then test numerical lessons

The owner completed the **512-TRAIN-game / 71,293-decision** feedback audit. All 16
behavior and credit reports reconstruct exactly; 96 finite input probes, 16 order checks
and all disposable teaching controls pass. The actual credit predictor beats the
other-fold constant in every batch. Training changes probabilities with assigned credit,
but the prior fresh-game comparisons still do **not** confirm stronger play. This supports
testing better action-level lessons rather than repeating an unchanged PPO recipe.

Implemented the separately versioned **native combat comparison teacher**. It replays a
sealed TRAIN prefix in a fresh isolated native worker, verifies the exact public root,
forces one offered action, then continues with the unchanged round-60 player to a genuine
full-run ending. Eight distinct seeds cover four ordinary fights, two elites and two
bosses across both players. Every action in each selected menu is compared: **48 actions
× eight continuation-policy streams = 384 planned branches**. All original and final
weights, Adam moments/counters, runtime, SDK, frozen game and account profile are preserved.

The short native control passes **24/24 terminal branches**, zero failures/skips/wins/app
copies, both duplicate public traces identical. It takes **75.04 seconds**, **373.26 MB**
peak RAM and **34.01 MB** private outputs. It verifies exact prefix/root delivery and
complete menus; two policy samples per action do not qualify training targets. No optimizer
updates or checkpoint promotion occur. The main pilot is preflighted and remains unstarted.

This first teacher is explicitly **privileged fixed-world evidence**: each root keeps its
original native seed/hidden world. Only continuation-policy sampling varies; it does not
resample unknown draw orders. Student inputs remain public. It is not an optimal-action
oracle, a public-belief search result or ordinary on-policy PPO experience. All failures
remain visible; a failed root supplies no lessons and its remaining branches are skipped
after verified worker retirement. Prefix drift or uncertain delivery stops for inspection.

Next, in order:

1. **Owner runs the finite teacher pilot.** Collect full-run wins and declared auxiliary
   floor/act returns, with matched policy streams, native delivery audit, complete candidate
   coverage, sampling uncertainty and source provenance. No HP/Smith rewards or strategic
   masks. Eight roots are a feasibility pilot, not enough diversity to establish good play.
2. **Audit lesson quality and feed numerical targets into a separate training fork.** Check
   action binding, signal/uncertainty and behavior across independent roots. Use an explicitly
   privileged-teacher supervised value/ranking loss; preserve both players' full Adam state.
   Historical/counterfactual data must never be relabeled fresh PPO. A pilot with no reliable
   preferences is a result to inspect, not a reason to loosen its gate after seeing outcomes.
3. **Compare fresh full-run learning with matched compute.** Test teacher-assisted versus
   unchanged training from both saved players, with untouched evaluation seeds. Judge wins
   first, then auxiliary floor/act progress, failures and compute. Expand root diversity or
   revise the teacher only in a new predeclared study. No automatic follow-up or promotion.
4. **Qualify public-consistent hidden-world sampling before public-belief search claims.**
   More policy samples in one original world do not solve hidden-information bias. Separate
   this experimental teacher from the eventual low/medium/high thinking controller.
5. **Readiness before adaptive thinking.** Strong base play, value/calibration and equal-compute
   search benefits remain unmet. GA/direct evolution and other difficulties remain deferred.

**One next owner command (approximately 20–30 minutes):**

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/collect-native-combat-teacher-v1.sh
```

One native worker, 15-minute sessions, 2 GB RAM / 4 GB generated-output caps. Clean reruns
reuse sealed branches; an interrupted uncommitted branch is preserved for inspection.
No app copies, optimizer updates, adaptive controller or automatic next experiment.
See [design and limits](native-combat-teacher.md),
[completed audit](evidence/native-learning-feedback-result-v1.json) and
[teacher evidence](evidence/native-combat-teacher-v1.json).
Full local verification passes **1,830 tests**, formatting/lint, strict types and C#
contracts. GitHub #143 / #35 / #146 reflect this handoff with prior history retained.
No push or GitHub Actions.

### Preserved feedback-audit preparation (the owner completed it above)

# SpireShift backlog

Updated 2026-10-19 after the completed rest-exploration comparison and owner discussion.
Codex runs short checks; the owner launches/monitors tasks expected to take ≥5 minutes.

## Current handoff: turn completed-game diagnosis into numerical learning improvements

The rest-exploration experiment is complete: **896/896 genuine terminal attempts, zero
technical failures, zero full wins, zero app copies**. Its 512 TRAIN attempts and 384 final
test attempts remain distinct. The final 128-game/version test means are **11.0859375 original,
11.453125 standard, 11.3203125 exploration**. Exploration minus standard is **−0.1328125**,
95% paired-seed interval **[−0.8125, 0.546875]**. Neither training arm establishes stronger play.
All four round-60 forks, their original round-56 states and every Adam moment/counter are kept.

Smith is card upgrading. Its rarity is **not an error or failure criterion**: poor earlier
combat can make healing necessary. Training Smith counts rise 1→30 under exploration, but
this alone supplies neither an optimal-action label nor a reason to reward upgrades.
The correct mixture gradient can give very unlikely exploratory actions weak direct feedback;
this is a mechanism to measure, not proof that changing it would win games.

The next work must produce a corrected input/learning mechanism or trustworthy numerical
lessons. Written assessments do not train a neural network. Do not launch another unchanged
large continuation, invent HP/Smith bonuses, or treat old-policy records as fresh PPO data.

Ordered work (#143 / #35 / #146):

1. **Current completed-TRAIN feedback and learning controls.** Reconstruct the exact 16 saved
   32-game batches (512 attempts), their behavior likelihoods, whole-game cross-fitted credit,
   and before/after probabilities. Compare prediction errors against same-fold constant and
   current-progress references, expose game/menu weighting, rest health context and observed
   final combat encounters. Check finite public-fact perturbations and candidate order, then
   teach an explicitly invented numerical label to a disposable full model/Adam copy. Reuse the
   earlier successful conditional-input controls; do not repeat an exhaustive mechanics gate.
   No evaluation histories, native game attempts, production updates or causal action labels.
   Run a short control first; leave the complete audit to the owner if ≥5 minutes.
2. **Repair a measured defect or qualify native action comparisons.** If actual inputs or
   arithmetic fail, fix and verify them before collecting again. Otherwise qualify bounded,
   public-information native combat branches and produce state/action/return comparisons with
   exact seeds, budgets, uncertainty and provenance. A single losing trajectory does not identify
   the bad action. Native short-horizon targets remain auxiliary to full-run victory.
3. **Feed verified lessons into training and test fresh play.** Use a declared supervised
   action-ranking/imitation or value loss; keep historical/off-policy lessons separate from
   fresh on-policy PPO. Verify target binding, loss/gradient direction and generalization before
   a bounded teacher-versus-PPO comparison with preserved weights/Adam and independent seeds.
   Measure wins first, floor/act progress, failures and compute; no forced strategic choices.
4. **Readiness before adaptive thinking.** Strong base play, value/calibration and equal-compute
   search benefits remain unmet. GA/direct evolution and other difficulties remain deferred.

The completed source experiment is immutable. New diagnostics live in their own workspace.
The short control and full-audit handoff are documented in [learning feedback](native-learning-feedback.md).
The short control passes on **64 saved TRAIN games / 9,462 decisions** in 81.92 seconds,
320.52 MB peak RAM. Both actual credit reports reconstruct exactly; finite health, energy,
cost, damage, block, target-health and candidate-order checks pass. Both disposable actors
memorize their artificial numerical targets (>99.8% after 64 steps); this is not native
action-quality or PPO-discovery evidence. The actor's credit predictor beats a same-fold
constant in both batches. The complete 16-batch audit is preflighted and remains unstarted.

**One next owner command (saved-data analysis only, approximately 8–12 minutes):**

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/diagnose-native-learning-feedback-v1.sh
```

One numerical thread, 15-minute launch cap, 2 GB RAM / 100 MB generated outputs. Completed
32-game analyses are reused on a clean rerun. No games, production training or automatic follow-up.
Full local verification passes **1,822 tests**, formatting/lint, strict types and C# contracts.
GitHub #143 / #35 / #146 reflect this handoff with prior history preserved. No push or GitHub Actions.

### Preserved selection repair and exploration preparation (main run now completed above)

# SpireShift backlog

Updated 2026-10-19 after the completed round-56 continuation and selection-menu repair.
Codex runs short checks; the owner launches/monitors tasks expected to take ≥5 minutes.

## Current handoff: selection repair and matched rest-exploration comparison

The repaired-runtime run finished **960 attempts / 958 terminal / two failed**, zero full wins.
One TRAIN and one development game exceeded the old subset-menu limit. The failed TRAIN game
was excluded. All final comparison games completed. On 128 paired fresh test seeds, mean floor
rose **10.6796875→11.3671875**, gain **0.6875**, 95% fixed-initializer seed-bootstrap interval
**[-0.09375, 1.4609375]**. This does **not** confirm stronger play. Three clean TRAIN games
cleared Act 1; neither final trained player cleared it on the final test. Both current round-56
states remain intact, **1,792 scheduled TRAIN slots/player; Adam 5268 / 5589**.

Implemented: large card subsets now use an ordered public selection cursor instead of enumerating
every combination. All subsets/orders, true native cancellation and allowed empty confirmation
remain available. Only final confirmation/cancellation reaches the game. Small menus stay
unchanged. Four scoped native checks pass: Pael five-of-21 removal twice (including reverse
order), Kifuda up-to-three enchantment and empty confirmation. Native host, game/SDK/runtime and
existing helpers stay unchanged. UI prefixes have a separate exact streaming replay audit.
No app copies or changes to the Steam account profile.

Prepared **standard versus rest-only 20% uniform exploration** from BOTH same round-56 states,
including every Adam moment/counter. Every current legal strategic action stays learnable;
there are no Smith/HP bonuses, forced upgrades or permanent baseline-proximity guards.
Rest exploration includes any currently offered potion/Proceed controls. All other sampling
stays unchanged. PPO differentiates and verifies the actual mixture; zero-mixture updates
match the existing trainer exactly. Final tests turn exploration off for all players.

The bounded comparison has four 32-game batches per method/player, **rounds 57–60**. Same fresh
TRAIN seeds across methods, independent players, separate matched final tests, final states
only. At most **896 attempts: 512 TRAIN + 384 tests**, with exact state/chunk resumption,
worker retirement, streaming memory bounds and 4 GB generated-output/RAM caps. The separate
control passes **20/20 attempts**, zero failures, four round-57 fits and 33
optimizer updates. Adam: player 2 standard **5274**, exploration **5277**; player 3 both
**5598**. Resumption reconstructs exactly; original states are unchanged. The main comparison
uses the original round-56 states and excludes control seeds/weights. It remains unstarted.

[Design, qualification and next command](native-rest-exploration.md).

**One next owner command (integration control passed; the runner verifies local checks):**

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/compare-native-a8-rest-exploration-v1.sh
```

Expected **30–60 minutes**, two-hour launch cap and clean 15-minute sessions; two private-profile
workers share immutable inputs. Close STS2. A clean rerun resumes completed work; a failed or
uncertain session stops for inspection. No automatic extension/promotion/adaptive controller.

Ordered remaining work:

1. **Assess the frozen exploration comparison.** Wins first, act clears, paired floors and
   uncertainty, failures, both initializers and computation. Check TRAIN Rest/Smith/other counts
   to establish whether exploration actually happened; counts alone do not prove better play.
2. **Improve elite/boss decisions if this remains weak.** Test a declared combat/deck exploration
   intervention or qualify a native search teacher. Preserve the current models/Adam states;
   use fresh paired evaluation. Do not replace learning with arbitrary health or upgrade rewards.
3. **Pass policy/value/calibration/search readiness before adaptive thinking.** Full-run victories
   remain missing. GA/direct evolution and other difficulties remain deferred.

#143 / #35 / #146 remain open. Local checks precede the commit; no push or GitHub Actions.

### Preserved runtime-repair preparation (before the now-completed owner run)

# SpireShift backlog

Updated 2026-10-19 after the completed shop continuation and native runtime repairs.
Codex runs short checks; the owner launches/monitors tasks expected to take ≥5 minutes.

## Current handoff: repaired native mechanics and bounded round-48 continuation

The shop run finished **1,344 attempts / 1,342 terminal / two failed TRAIN**, zero full wins.
The 128-pair fresh holdout improved **9.484375→10.3671875** mean floor (+0.8828125,
95% seed-bootstrap interval [0.2734375, 1.5078125]); no held-out Act 1 clears. This is
modest auxiliary progress, not strong play or victory readiness. Both current round-48
states remain intact, **1,536 scheduled training slots/player, Adam 4470 / 4692**.

Implemented: native **Crystal Sphere** grid/tools/payment/curse/rewards and missing Godot
ABI for **Rolling Boulder**. New v35 builds reproduce; six scoped native effect checks pass.
Covered grid contents stay hidden; native models own all game effects. Old binaries/results
are preserved, no app copies, and old coverage is not relabeled as new-host parity.

Read-only TRAIN audit: **830 clean games**, no evaluation histories. Only 51 of 17,823 end
turns still had a playable card. Terminal fights: 352 elite / 107 boss / 368 ordinary;
boss losses began at 73.7% average health. **747 Rest versus two Smith**, including 37
full-health rests with Smith available. Optional card Skip remains available and was used
377 times. These observations prioritize exploration/deck/combat strength, not hard-coded
health rewards, forced cards, or a claim that simply adding volume must work.

Next bounded step preserves BOTH latest weights and all Adam moments/counters; first fit
**round 49**, same 32-game batches / three passes / temperature / credit / objective.
At most **256 new TRAIN attempts/player** to 1,792 each, development at 1536/1664/1792,
then a separate 64-seed/player paired holdout versus imported states on the repaired host.
Maximum **960 attempts**, including 512 TRAIN, 192 development and 256 holdout attempts.
All old consumed/reserved seeds and the integration control are excluded. No failed or
recovered episode enters PPO; existing retirement/failure/session caps stay enforced.

The live integration control passes **12/12 attempts**, zero failures, two round-49
fits; Adam **4470→4476 / 4692→4698**. Originals remain unchanged; clean resumption
reuses both fits, with zero app copies.

[Repair, loss findings and next run](native-runtime-continuation.md) /
[evidence](evidence/native-runtime-continuation-v1.json).

**One next owner command; main continuation remains unstarted:**

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/continue-native-a8-runtime-v1.sh
```

Close STS2. Expect **60–90 minutes**, two-hour invocation cap, clean 15-minute sessions,
two workers, **4 GB RAM / 4 GB generated outputs**, shared immutable inputs, zero app copies.
Clean reruns retain committed games/fits/full Adam; uncertain or failed work is preserved.
No automatic promotion/readiness/adaptive controller or further extension follows.

Ordered remaining work:

1. **Assess this finite repaired continuation.** Full wins, paired final holdout, both players,
   failures, optimizer continuity and resources; do not treat development as independent test.
2. **Improve exploration and action quality if progress remains weak.** Prioritize the strong
   Rest-over-Smith skew and weak elite/boss play. Test a declared exploration intervention or
   qualify a native combat teacher; preserve both players and use fresh paired evaluation.
   Measure the effects instead of imposing arbitrary HP rewards or fixed strategic masks.
3. **Prove policy/value/calibration/search readiness before adaptive thinking.** Full victories
   remain missing. GA/direct evolution and other difficulties remain deferred.

#143 / #35 / #146 remain open. Full local checks precede the commit; no push or GitHub Actions.

### Preserved shop-repair preparation (before its now-completed owner run)


Updated 2026-10-19 after the stopped extension is audited and shop repair is implemented.
Codex runs short checks; the owner launches and monitors tasks expected to take five minutes
or more. Keep prior scientific evidence, source files, seeds and numerical states unchanged.

## Current handoff and direction

**Shop navigation repair and bounded continuation prepared (#143 / #35 / #146).**
The old extension stops after 1,440 attempts / three shop loops. Its 221 completed units and
both latest round-35 full model/Adam states are verified. Preserve the uncommitted eight-game
collection (seven terminal, one failed) diagnostically, and exclude the whole unfitted 32-game
round. No fabricated completion, worker reset, uncertain seed replay or old-policy PPO follows.
All three recorded loop states now choose Leave shop under the repaired public contract,
without replaying a game. Original states/markers/records remain unchanged.

Automatically inspect inventory once. Purchases, removal, potion use/discard, closing and
leaving remain real current choices; redundant reopening after closing is navigation rather
than a learned action. Foul Potion still targets the closed merchant and permits fresh
inspection after use. Keep every raw delivery; exclude automatic opening from PPO and verify
exact effective-menu probabilities under a separate behavior contract. Other menus and
optional card skipping are unchanged. No arbitrary HP rewards or strategic item rankings.

Restore BOTH latest states: 1,120 scheduled training games/player, Adam counters **3216 / 3261**.
Continue absolute round **36** with fresh seeds, 32-game batches / three passes and the same
native v0.111.0 / 41cef1ea Ironclad/A8 inputs, model, numerical kernel, temperature and objective.
At most **416 new TRAIN attempts/player**, preserving the original 1,536-game ceiling. Evaluate
32 development seeds/player at 1120/1248/1376/1536 under the repaired contract. Wins first then
floor; stop both after two stale checks once 256 new attempts/player finish, or at the horizon.
Keep current states, not best-seen. Then open a separate 64-seed/player paired holdout comparing
round-35 starters with stopped players under the same repair. No evaluation data enters PPO.
Maximum **1,344 attempts / 199 units**, on 1,024 distinct fresh seeds. Every old reserved seed,
including unfinished/unused reservations, plus the new control is excluded.

[Repair, audit and continuation](native-shop-continuation.md) /
[evidence](evidence/native-shop-continuation-v1.json).

The live control passes **12/12 attempts**, zero failures, seven automatic shop openings and
15 optimizer updates: **3216→3225 / 3261→3267**. It resumes cleanly across two launches without
repeating a fit. Total 287.45 s / 764.25 MB peak RAM / 56.71 MB output; zero app copies.
All **1,770 tests** pass. This is an integration check, not a strength claim; its trained
weights never start the main continuation.

**One next owner command; main continuation remains unstarted:**

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/continue-native-a8-shop-v1.sh
```

Close STS2. Expect **1–2 hours** at horizon, possibly less at plateau. Three-hour invocation
cap; clean 15-minute sessions, two workers, **4 GB RAM / 4 GB generated output**. Shared frozen
game/runtime/SDK/cache and zero app copies. Clean reruns resume games/fits/full Adam state;
failed/capped sessions stop without automatic retry. Do not resume the old stopped launcher.
No automatic promotion, readiness pass, adaptive controller or further experiment follows.

Ordered remaining work:

1. **Assess the owner-run repaired continuation.** Genuine wins, paired final holdout,
   per-player curves, failures/navigation counts, resource use and full Adam/round continuity.
   Starting and stopping players use the same repair; do not attribute their difference solely
   to navigation or reuse the old development results as a fresh holdout.
2. **If progress remains weak, improve action credit or qualify actual-engine teachers.**
   Do not blindly scale a stalled recipe, add arbitrary health rewards or permanently constrain
   strategic actions. The old extension's development gains became mixed; zero full wins remain.
3. **Full policy/value/calibration/search readiness before adaptive thinking.**
   GA/direct evolution and other difficulties remain later work.

The old fresh confirmation remains preserved: mean floor 7.2890625→8.859375, zero full wins.
The stopped continuation's pooled development mean is 8.34375→9.15625→8.75 at 512/768/1024;
its final holdout was never opened. These are auxiliary observations, not strong play or a
readiness pass. #143/#35/#146 stay open; no push or GitHub Actions.

### Preserved initial continuation preparation

**Bounded standard continuation implemented; owner launch is next (#143 / #35 / #146).**
Restore BOTH confirmed final 512-game players, original weights and all Adam moments/counters.
First continued fit is absolute **round 17**, with source counters **1,353 / 1,413**; no reset,
new initializer, selecting one player or permanent baseline-proximity/action restriction.
Keep native v0.111.0 / 41cef1ea Ironclad/A8, original public inputs/objective/bootstrap score,
temperature 0.8, **32-game batches / three passes**, qualified collector/worker and compact kernel.

Finite extent: **up to 1,024 new TRAIN games/player**, reaching at most 1,536 total each. Collect
in eight-game chunks; evaluate on 32 separate development seeds/player at 512/768/1024/1280/1536.
At each check pool wins first, then floor; stop BOTH after two checks without exceeding the best
previous pooled result, once at least 512 new games/player complete, or at the horizon. Keep the
current stopping states, never the earlier best checkpoint. Then open a separate 64-seed/player
holdout comparing the 512-game starters to their stopping states. No holdout result affects
training duration. Maximum **2,624 attempts / 398 units** (2,048 TRAIN + 320 development + 256
holdout attempts; 2,240 distinct seeds). All 18 prior native manifests and the new control are
excluded from every new partition; evaluation games never supply PPO samples.

The short continuation control **passes 12/12 attempts**, zero failures, two fits at round 17,
15 updates: Adam **1353→1362 / 1413→1419**. Original states/shared inputs remain unchanged;
zero app copies. Measured resource time **140.10 s**, peak RAM **754.55 MB**, retained **37.70 MB**.
It proves delivery/restoration/fit integration, not strength. Its two-game batches/updated states
never replace the original 512-game starting states for the main extension. Unit tests prove
exact uninterrupted-versus-restored nonzero-Adam parity and reject seed leakage/reset/corruption,
uncertain replay and holdout peeking. Full repository checks pass before the local commit.
[Plan and execution](native-policy-continuation.md) /
[evidence](evidence/native-policy-continuation-v1.json).

**One next owner command; main extension has not started:**

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/continue-native-a8-policy-v1.sh
```

Close STS2. Expected **2–3 hours** at the horizon; plateau may end it earlier. Four-hour invocation
cap, clean 15-minute sessions, two workers, **4 GB RAM / 8 GB generated output**, shared frozen
game/runtime/SDK/cache and no app copies. Re-running resumes clean committed work; once complete
it only verifies results. Uncertain/uncommitted units or a failed/capped session stop without
replay/reset/automatic retry. Inherited failure allowance spans the whole 256-game/player TRAIN
stage, 32-game development panel or 64-game holdout/version panel, not individual chunks.
The owner runs and monitors this long task. No further experiment/promotion follows automatically.

Ordered remaining work:

1. **Assess the bounded continuation.** Review genuine wins first, independent final holdout
   paired floors/failures, individual curves, actual endpoint and plateau reason. Confirm
   optimizer-state/absolute-round continuity, budgets and source/worker isolation. Repeated
   development checks are not independent holdout seeds. No automatic base-readiness claim.
2. **Respond to the evidence.** Continue a measured positive trend only under another declared
   finite plan. If improvement stalls, prioritize action-credit or qualified actual-engine teachers;
   do not blindly scale the same recipe. No arbitrary HP rewards or permanent action masks.
3. **Full readiness before adaptive thinking.** Establish full wins and policy/value/calibration/
   search quality. GA/direct evolution and other difficulties remain deferred.

The prior confirmation remains preserved: 256 clean attempts, originals **7.2890625** versus
trained **8.859375** mean floor; paired gain **1.5703125**, 95% seed-bootstrap interval
**[0.9296875, 2.2265625]**. Both players improve; 66 pairs higher, 34 tied, 28 lower. Still zero
full wins / completed acts in that confirmation, trained best floor 17. It supports testing this
finite continuation, not strong play or population-level algorithm superiority. See
[fresh confirmation result](native-policy-confirmation-result.md). Original optimizer study and
completed-TRAIN diagnostic remain intact. No push or GitHub Actions; #143/#35/#146 remain open.

### Preserved optimizer preparation and parallel diagnostic (completed above)

**Parallel saved-record diagnostic complete; owner reports the learning curve running.**
The new tool analyzes only the two completed historical TRAIN cohorts: 64 games / 6,995
records, in 45.81 seconds / 291.23 MB, with zero games, policy updates or running-record reads.
All 36 protected experiment files remain unchanged. Reopening its sealed result reuses it.
Mandatory menus are 24.3% of records, but excluding them from advantage normalization alone
changes the sign on only 9/5,297 real choices. Combat supplies 75.2% of real choices; rest sites
only 19 and shops 88. Card skipping occurs 30/181 times; end turns with plays remaining are
39/1,254 chosen end turns. These are observed behaviors, not proven mistakes or optimal actions.
The actor changes probabilities on saved inputs; useful new-game learning is still unproven.
[Method and first interpretation](native-completed-training-diagnostics.md) /
[evidence](evidence/native-completed-training-diagnostics-v1.json). No new owner command or
additional learning gate is introduced. Complete the current comparison unchanged; then assess
its fresh results before choosing a credit/teacher change. Do not tune the running recipe.

**Optimizer study and compact learning-curve runner implemented; owner comparison awaiting results
(#143 / #35 / #146).** The previous input comparison remains flat: original combined mean floor
7.1250→6.9375, crossed 7.1250→7.1250; both 0/32 final wins over two numerical replicates.
Its 46 units / 288 new games and historical results are unchanged. Useful native learning,
full wins and base/adaptive readiness remain unproven.

A frozen TRAIN-only study reuses two clean 32-game first-round cohorts. Standard updates exactly
reproduce both historical model IDs. Nine passes fit the assigned in-sample training signal
2.4–2.6× more than three passes; higher-rate fits are also preserved. None reaches the existing
per-update KL cap. Separate 16-game halves suggest weakly related directions (cosine −0.1019 and
+0.0057); these single-split diagnostics do not establish causality, optimal batch size or stronger
play. Study: 88.42 s, 723 MB peak RAM, 825 numerical updates, zero new games or promotions.

Compact sparse inputs preserve float64 values, loss, gradients, credit, model weights and complete
Adam state. A saved 32-game batch exactly reproduces its historical model after 81 updates with
about 168 MB additional preparation memory. The short native control passes 8/8 games / 24 updates
across three launches: 54.45 s, 681 MB peak RAM, 11.55 MB output, zero failures or app copies. Its
two-game batches prove integration and resumption, not actual 128-game memory or learning quality.

**One next owner command:** `bash scripts/train-native-a8-optimizer-v1.sh`.
Close the Steam game. Expected 2–3 hours; three-hour invocation budget, two workers, 4 GB RAM,
6 GB retained output. Clean 15-minute sessions continue within the same finite plan; failed/capped
sessions stop without automatic retries. The same command resumes a clean pause and verifies
complete results on repeat. Required complete repository checks precede any game collection.
The owner reports this comparison running; Codex has not launched or monitored it.
[Protocol](native-optimizer-learning.md) /
[evidence](evidence/native-optimizer-learning-v1.json).

Ordered remaining work:

1. **Assess the frozen learning curve, owner-run:** standard 32-game batches / three passes versus
   candidate 128-game batches / up to nine passes. Each player gets 512 fresh training games;
   two new numerical initializers, paired seed plans, 16 reserved development games at
   0/128/256/384/512. Total 2,368 attempts, 340 sealed units. This deliberately bundles larger
   independent batches and reuse, has equal game budgets but different fitting compute, and
   cannot attribute a gain to either component alone. Final-only comparison; no promotion.
2. **Improve action credit if fresh play remains flat:** stop at the fixed horizon; do not
   automatically extend unchanged PPO. Test better return/action-value estimates or qualified
   search/demonstration lessons. The earlier full-trace score timing change was numerically
   identical; arbitrary HP bonuses are not a repair. Diagnose noise versus fitting with saved
   evidence before changing the objective or adding restrictions.
3. **Better lessons and practice:** qualify actual-engine action branches before fixed-budget
   search/demonstrations become teachers. Keep hidden information out of policy inputs, quantify
   label noise and retain full-run A8 evaluation. Saved diagnostic fits are not fresh PPO data.
4. **Scale only after repeatable progress:** confirm a promising method on fresh seeds, then
   justify larger owner-run learning curves. Count games, decisions, updates, failures and CPU
   separately. The current two-replicate development comparison cannot certify strong win rate.

Keep fixed Ironclad/A8, all public legal choices, the declared floor/act bootstrap score and
primary terminal-victory objective. No arbitrary health rewards, permanent action restrictions,
automatic adaptive thinking or difficulty expansion. GA/direct evolution remains a separate
later comparison. Shared frozen game/runtime/SDK/support code are reused with isolated workers;
no app copies. Interrupted prefixes remain diagnostic only; original denominators and historical
source/config/result bytes stay preserved. #143/#35/#146 remain open. Full repository checks are
required before a local commit; no push or GitHub Actions is needed.

### Preserved completed input comparison

**Comparison complete; useful native learning remains unproven (#143 / #35 / #146).**
The fresh matched pair finishes all 46 units / 288 new games, with zero failed games and no app
copies. Both successful sessions total 861.35 seconds (14 min 21 s), peak RAM 1.07 GB and new-workspace
storage 280.21 MB. One refused launch while Steam's game was open is retained separately. There is
no pending owner command for this completed comparison; rerunning its launcher only verifies it.

| Method, two numerical seeds | Initial mean floor | Final mean floor | Final wins |
| --- | ---: | ---: | ---: |
| Original encoding | 7.1250 | 6.9375 | 0/32 |
| Public numeric-by-candidate features | 7.1250 | 7.1250 | 0/32 |

The crossed method is ahead by only 0.1875 floor in each replicate and has no aggregate improvement
over its own initializer. Both methods improve slightly in replicate 0 and regress in replicate 1.
These are exploratory development results, not a significance claim or a useful base player. Each
player has only 128 training games; the result does not prove more data cannot help. Preserve the
successful synthetic control as synthetic evidence, without claiming it fixed actual-game learning.

A read-only assessment verifies all 46 unit receipts / 5,567 source seals and reconstructs the
reported comparison. It launches no games and performs no fitting. All fresh fits reach their epoch
limit, gradients are nonzero and policies change: these records do not support a completely frozen
optimizer. They also do not establish that larger steps or more epochs improve gameplay.
[Results and method](native-context-restart.md) / [evidence](evidence/native-context-comparison-v2.json).

The old 640-game attempt and its 520 sealed games remain unchanged: 496 closed audited games,
24 interrupted-prefix games excluded from PPO, and 120 original slots without sealed headers.
The primary completed comparison uses the old seed-0 pair, the 32 verified old seed-1 starting
panels and the fresh matched seed-1 pair. The extra old seed-1 baseline stays diagnostic. No unsafe
worker/profile reset, uncertain seed replay, checkpoint promotion or readiness/adaptive pass occurs.

Ordered remaining work:

1. **Optimizer efficiency, next implementation:** reconstruct the saved TRAIN-only batches and
   measure probability movement against their assigned advantages, losses and independent-game
   gradient evidence. Compare predeclared step sizes or update counts with matched initialization,
   game budget and whole-game ordering. Numerical fitting success is not stronger play. Use new
   reserved development seeds for the next frozen native experiment; do not tune on these final
   panels. Record every attempted setting and actual work. Leave long experiments owner-run.
2. **Action credit:** if updates fit their noisy lessons without improving independent play, test
   better return/action-value estimates and narrower credit only when prediction evidence supports
   them. Moving the same score earlier under full-trace credit already leaves the update unchanged.
3. **Better lessons and practice:** qualify actual-engine action branches before fixed-budget
   search/demonstrations become teachers. Keep hidden information out of policy inputs, quantify
   label noise and retain full-run A8 evaluation. Separate supervised studies from ordinary PPO.
4. **Measured scaling:** use owner-run learning curves and larger independent batches after the
   next bounded check, with a declared stop/plateau rule. More games are a testable intervention,
   not an assumed cure. Count games, decisions, updates, failures and CPU separately.

Keep fixed Ironclad/A8, the declared floor/act bootstrap score and primary terminal-victory
objective. No arbitrary health rewards, permanent action restrictions, automatic adaptive thinking
or difficulty expansion. GA/direct evolution remains a separate deferred comparison. The cache,
restart mechanism, short control and native comparison work are complete; broader learning issues
remain open. Run the full repository check before committing changes; no push/Actions is needed.

### Preserved restart preparation (completed above)

**Implemented: immutable model-ID cache and restartable comparison; owner fresh matched pair next
(#143 / #35 / #146).** The original one-hour attempt did not complete. Keep the declared floor/act
bootstrap score, terminal-victory evaluation, all legal choices and existing PPO settings unchanged.
No health rewards, action masks or adaptive controller are added. Stronger native play is unproven.

The old 640-game plan retains **520 sealed games**: 496 in closed audited panels, 24 in interrupted
workers (diagnostic only), and 120 original slots without sealed headers. Unsealed attempt count is
unknown. Its capped report's zero exit code is not experiment completion. Original and crossed
seed-0 players change mean floor 6.4375→6.5625 and 6.4375→6.7500; the extra old baseline seed-1
changes 7.8125→7.2500. All have zero wins in their 16-game final development panels. This is weak,
exploratory evidence, not success of the synthetic repair in the actual game.

The owner chose a **fresh matched seed-1 pair**. Preserve the completed seed-0 pair in the primary
comparison and the old extra baseline as diagnostic evidence. Reuse both verified seed-1 starting
panels (32 games), including reconstruction of saved behavior probabilities. Collect 128 fresh TRAIN
seeds per method, paired across methods and disjoint from legacy TRAIN/uncertain seeds, then 16 final
reserved development games each: **288 new games**. Never admit the interrupted prefix as PPO data.
The primary comparison has two numerical replicates, with final-only evaluation and no promotion.

IDs, serialized models, probabilities and draws are unchanged by the cache; new weights get a new
cache. Saved-decision processing is 5.10–6.76× faster in a small profile, not a whole-game speed claim.
The new runner commits eight-game collections and complete model/Adam checkpoints separately; the
training batch remains 32, with historical two-lane ordering restored before deterministic fitting.
Each launch lasts at most 15 minutes, two workers, 4 GB RAM / 4 GB new-workspace cap. Pauses happen
between committed units. Abruptly interrupted units remain preserved and require inspection; no seed
replay, profile clearing or pretending partial work is complete. The two-failure allowance applies to
an entire logical round/evaluation. Shared frozen game inputs/cache are reused; no app copies.

The short native restart control passes **8/8 games, 12 updates**, across three launches paused after
units 3 and 6: **63.04 total resource-tracked seconds / 697.30 MB** peak RAM, no failures or shared-input
changes. Reopening it performs no new games or updates. A read-only import seals every historical
file and verifies saved models, case/trace seals, worker audits and stopped interrupted processes.
Targeted checks plus repository lint/types pass; the complete release check is still pending.
[Protocol, evidence and limits](native-context-restart.md). Historical pinned sources stay unchanged.

**One next owner command:** `bash scripts/continue-native-a8-context-v2.sh`.
It first runs the required full repository checks (about 5–6 minutes, ten-minute cap), then one bounded
comparison session if they pass. Reuse the same command after a clean pause; completed collections,
fits, Adam state and the exact-file release-check receipt are verified and reused. The long comparison
has **not** been launched. No commit/push or GitHub Actions run before the complete check passes.

Ordered remaining work:

1. **Representation and execution repairs, implemented:** the earlier synthetic context-by-action
   control passes 3/3 seeds (68.68–69.32% versus 48.07–54.26%, 70% optimum). Its native bridge/projection
   and this cache/restart control pass. Synthetic learning and plumbing are not native strength.
2. **Finish and assess the controlled native comparison:** owner runs the new fresh-pair command.
   Compare paired final-minus-initial floors, terminal wins, failures and actual optimizer work;
   preserve the original interruption and the extra unpaired baseline. Do not select on final panels.
3. **Optimizer efficiency:** if the method remains flat, bounded tests of initialization, learning
   rate and updates per collected game; retain every attempted setting and negative control.
4. **Earlier action credit:** improve action-value/return estimates when prediction evidence supports
   them. Moving the same score earlier with full-trace credit already leaves the update unchanged;
   no arbitrary HP rewards. The previous improved baseline did not establish better gameplay.
5. **Better lessons and practice:** qualify actual-engine action branches before fixed-budget search
   or demonstrations become teachers. Keep hidden information out of policy inputs and preserve
   full-run A8 evaluation. Recovered/stale episodes may serve separate supervised studies, not PPO.
6. **Measured scaling:** after repeatable improvement, owner-run thousands-game learning curves and
   larger budgets if justified. Count games, decisions, updates, failures and CPU separately.

Selectable difficulties, larger unchanged GA and adaptive thinking remain deferred. The complete
repository check followed by a bounded fresh-pair session is the sole pending owner command.

### Preserved conditional comparison (interaction follow-up now being implemented)

**Direct teaching versus PPO implemented and assessed (#35 / #146): conditional learning remains weak.**
The same synthetic HP task, initial numerical weights, public inputs and actual optimizer
work are paired across three seeds. Each primary method uses 288 updates / 36,864 decision
presentations / 6,144 choice presentations. PPO receives terminal outcomes only; the
teacher gets separate oracle action labels. All three PPO final IDs/evaluations exactly
reproduce the historical control. Frozen-actor and missing-HP controls pass. All 96 round
records / 99 round-and-pair file seals verify. No native input or checkpoint is opened.

Neither method meets the frozen learning criterion in any seed. The teacher's expected
victory is 51.49–51.66% against a 70% optimum; it learns a small HP-dependent preference.
One seed has 100% greedy accuracy but only about 50–52% optimal-action probabilities,
well below the 75% criterion. This does not prove inadequate model capacity or a unique
PPO defect. It shows that sampled reward noise alone does not explain this control's gap.
The comparison completes in **37.43 seconds / 166.07 MB** peak RAM, retaining 1.56 MB,
with 6,144 sampled synthetic episodes / 2,052 synthetic updates including controls;
zero native games, production updates, app copies or promotions.

The initialization probe retains HP correctly, but the shared linear context cancels
between these candidate scores. The hidden branch's conditional-contrast gradient norm
is only 0.027–0.040% of the ordinary preference gradient norm. This is a local sensitivity
measurement, not an Adam speed ratio or proof of native causality. **Next implementation:**
a finite, separately versioned public context-by-candidate interaction control at the same
network size and controlled work/initial policies. Test this measured representation gap
before another native learning change; do not retune or extend the completed comparison.
[Method, results and limits](native-conditional-teaching.md). No owner command is pending.
Stronger play, full wins and base/adaptive readiness remain unmet.

### Preserved recovered-pool result (conditional comparison now complete)

**Recovered-pool analysis complete (#35 / #146); larger batches alone are not an established repair.**
The owner analysis finishes in **114.20 seconds / 3.917 GB** peak RAM with no cap, no new
games, optimizer steps or app copies. All 256 diagnostic games' saved likelihoods verify;
the independent numerical gradient reference passes on four games / 549 decisions only.
A separate saved-result check verifies 596 source seals and recomputes recorded partition
summaries without differentiating again. [Results, evidence and limits](native-a8-recovered-gradient-result.md).

At 32 / 64 / 128 games per disjoint group, median game-driven direction agreement is
-0.017 / +0.020 / +0.061, with 53.1% / 50.0% / 37.5% opposing pairs. Agreement remains
near zero; the trend is not uniformly improving. Including exploration at 128 games gives
-0.093 median agreement and 65.6% opposing pairs. Its full-pool norm is 35.8% of the
game-driven norm; this does not prove domination or a cause of weak learning. Partitions
reuse one finite frozen-player pool, not independent training replications. No optimal
batch size, actual learning benefit or impossibility of improvement is established.

**Completed follow-up above:** a bounded direct-teaching versus PPO conditional-HP control on
the same public inputs, with matched/reportable actual optimizer work and all attempted
settings preserved. The earlier learner misses the conditional rule while learning a
constant delayed choice; distinguish available capacity/optimization from reward-driven
conditioning before another native training change. This is a short synthetic diagnostic,
not a new mechanics gate. No owner command is pending. Stronger play, full wins and
base/adaptive readiness remain unmet; no larger unchanged PPO/GA or difficulty work follows.

### Preserved memory-repair handoff (analysis now complete)

**Memory repair and diagnostic recovery complete (#35 / #146).**
The owner collection hit its 4 GB RAM cap in 399.52 seconds. It saved 254 terminal records,
left seed 700253 interrupted and 700255 unstarted, and produced no final audit/summary.
The old collector retained full histories and its auditor loaded whole journals. The
new streaming implementation retains sealed paths/compact outcomes, releases each trace,
and verifies logs in order. Historical pinned sources and the original failure remain.

All 254 saved delivery/ending chains now verify in **25.15 seconds / 116.33 MB** peak RAM,
with zero replays, marker edits or worker reuse. Four repeated-control-seed games pass
the new collector/auditor and exact numerical reference; two short workers complete only
the unstarted 700255 and explicitly added fresh 700257. Seed 700253 is never retried.
The union contains **256 clean diagnostic games from 257 actual diagnostic attempts**;
the original interruption stays counted. Four control starts are separate. The old
collection is not relabelled clean, and recovered inputs are not ordinary PPO admission.
Mixed-origin saved verification passes on two recovered/two new games, 422 decisions.
No optimizer steps, promotions or app copies; the full native 256-game collection was not replayed.

**Completed owner command:** `bash scripts/analyze-native-a8-recovered-pool-v1.sh` from the repository.
Saved-data analysis only; up to ten minutes, one numerical thread, 8 GB memory, 2 GB output.
It is complete; its wrapper now shows saved results. Do not rerun/clear the capped
folder. [Recovery, measurements and accounting](native-a8-memory-recovery.md).
The full-pool findings are assessed above. The toy conditional-learning follow-up is next;
stronger play and base/adaptive readiness
remain unmet. No new action masks, model changes, larger GA or difficulty work is added.

### Preserved synthetic-control and earlier batch handoffs

**Synthetic end-to-end learning controls implemented and assessed (#35 / #146).**
The unchanged native numerical learner runs three tiny known-solution tasks, three training
seeds each, using fresh sampled binary terminal outcomes and no supervised action labels.
The delayed task learns from about 7.6% to 99.3–99.6% expected victory in all three seeds.
Immediate choice improves to 46.3–50.9% but misses the frozen 75% action-probability criterion;
it receives only 96 optimizer steps, versus 288 with continuation menus. Contextual risk
stays at 48.1–54.2%, below its 70% optimum; every final greedy player makes the same choice
at both HP levels. Frozen-actor and missing-HP negative controls behave as expected.
The overall learning check **does not pass**. This is not native skill/readiness evidence
or proof of a unique causal defect. Preserve the result; do not tune the frozen experiment
or increase its budget just to get a pass. [Method, measurements and limits](native-ppo-known-task-controls.md).

The control finishes in 34.09 seconds, 121.37 MB peak RAM and 4.11 MB retained output:
18,688 synthetic episodes / 2,052 synthetic updates, zero real games or production updates.
All 24 Python inputs pinned by the owner's running gradient study remain unchanged.
At that point the owner reported the larger pool running; Codex did not monitor it.
Its later capped outcome and recovery are assessed above; that handoff supersedes the
historical batch command below.
Independent next follow-up: a bounded direct-teaching-versus-PPO conditional control on the
same synthetic inputs, matching/reporting optimizer work and preserving every attempted
setting. Assess the larger pool before freezing any new native training comparison.

**Independent-game gradient and batch-size checks are implemented and pass (#35 / #146).**
The study reconstructs the production actor gradient at behavior to at most 2.15e-16 error,
including the full cross-fitted return baseline, all menus, normalization and entropy. Four
separate 32-game TRAIN cohorts verify 128 trajectories / 12,741 decisions from 64 native seeds;
cohorts/models are never pooled. No reserved evaluation episode is opened, no actor is updated.

Every pair uses disjoint games, separately fitted predictors and its own advantage moments.
Repeated partitions are correlated finite-pool descriptions, not independent replications.
At 16 games/group, median game-driven cosine is 0.200 / 0.039 / -0.035 / 0.322 for unscaled
rounds 1/8 and normalized rounds 1/8; opposing pairs range 12.5–53.1%. The full-batch entropy
term is 3.53–9.77% of the data-gradient norm and does not dominate these initial gradients.
These observations do not identify the best batch size or prove a cause of weak gameplay.
The saved-only study takes 58.01 seconds and 1.150 GB peak memory. Sizes 32/64/128 per independent
group remain unmeasured because the saved pool contains only 32 games per behavior model.

**Historical owner command:** `bash scripts/check-native-a8-batch-sizes-v1.sh` from the repository.
It collects 256 fresh TRAIN games with one frozen normalized pre-round-eight model, then
compares genuinely disjoint 32/64/128-game groups. This player is fixed by training phase,
not chosen from development rankings. It never updates/promotes a player. Expected 15–25
minutes; collection cap 20 minutes / two workers / 4 GB RAM, analysis cap 10 minutes / one
worker / 8 GB RAM, 2 GB retained-output cap per stage. One shared frozen game/code cache;
zero app copies. It reports batch progress, preserves source failures and requires every
planned clean game for analysis. The collection later hit its RAM cap; use the recovery above.

The four-game / 360-decision native collector/analysis control passes with zero failures,
missing games, optimizer steps or protected-input changes. A memory bound retains sparse
menus for only four numeric reference games while verifying behavior and retaining derivatives
for every game. The v1 control/preparation stays preserved; the launch script selects v2.
These four control seeds repeat across the two short source versions, not eight independent
outcomes. Collection control and preflight pass. [Method, evidence, caps and exact command](native-a8-independent-gradients.md).
Strong-base readiness, full wins and adaptive thinking remain unmet. After the larger pool,
freeze an equal-game-budget learning comparison only if the TRAIN evidence justifies it.

### Preserved completed normalization comparison

**The owner-run normalization comparison is complete: numerical conditioning improves,
but stronger play remains unproven (#143 / #146 / #35).** Both methods finish 336/336 normal
endings: 672 total, zero failed/missing games, wins, completed acts or app copies. On the
same 16 fresh development seeds, the unscaled player rises from 6.5 to 7.25 average floors;
normalized rises from 6.5 to 7.0625. Both gain intervals include zero. Normalized-minus-unscaled
is -0.1875 floors, interval [-1.625, +0.875]; its nonlinear auxiliary score is slightly higher,
also uncertain. No demonstrated superiority, inferiority or equivalence; one training replicate
per method. Both real round-eight trained models were frozen on confirmation before evaluation.

Normalization remains at **0% saturation in all recorded before/after training probes**;
unscaled reaches **52.36%** after round eight. The saved-only assessment reconstructs all probes
and verifies 672 episodes, 67,963 decisions and 2,878 source files in 33.62 seconds. Actual work
is 25,917 / 25,883 TRAIN decisions and 615 / 618 updates; identical collection rules are not
identical realized work. Owner runtime is 32.16 minutes combined; 599.37 MB retained, peak
memory 1.976 GB, protected inputs unchanged. See [results and limits](native-a8-normalization-comparison-result.md).

**Follow-up implemented above: #35's independent-run gradient/batch-size controls**, beginning with bounded
saved-TRAIN checks of whether different complete games recommend consistent changes. Do not
pool rounds from different behavior policies, count correlated decisions as independent games,
or treat resampling as new evidence. A justified larger-batch comparison must fix total games,
score and method, use fresh reserved evaluation seeds and report actual work. The owner
frozen-pool command above is now prepared. Keep both candidates/results frozen; do not promote or
choose normalization from this inspected development panel. Base readiness/adaptive thinking
remain unmet. #143's normalization ablation is complete under this finite scope; broader
representation changes need a demonstrated gap, not another saturation-only test.

### Preserved normalization launch handoff (completed)

**Input-normalization checks and native integration pass (#143 / #146).**
The explicit `native-actor-hash-quarter-v1` transform scales hashed actor coordinates by 0.25,
preserving direct action signals, critic inputs, all actions and every existing encoded fact.
All 278 sampled TRAIN states / 1,175 candidate vectors recover exactly; zero new aliases.
With old round-8 weights, probe saturation falls from 21.48% overall / 66.70% in combat to zero;
this is a sensitivity result, not a newly trained player. Artificial conditional learning passes
on 28 examples from 14 held TRAIN games; removing HP information gives chance performance.
A coherent three-view HP supplement also passes. Both four-game native controls pass, with
456 verified training decisions / 12 updates, zero failures or app copies. The unscaled
checkpoint exactly reproduces its prior control. Legacy model identities remain intact.

**Completed owner command:** `bash scripts/compare-native-a8-normalization-v1.sh` from the repository.
One scaling factor changes; both methods keep the cross-fitted credit estimator and all other
training settings. Each has 336 attempts, 672 total, run sequentially; expected 25–40 minutes,
30-minute cap per method. Fresh confirmation/development seeds, each method's own initializer
and best trained player, plus per-update saturation measurements. Admissions/preflight pass;
both methods have now completed. See [the original checks, limits and launch command](native-a8-input-normalization.md).

### Preserved completed credit experiment

**The owner-run credit comparison is complete: no clear gameplay gain (#35 / #146).**
Both methods finish 336/336 ordinary endings: 672 attempts total, zero failures, missing games,
wins, completed acts or app copies. On the same 16 independent development seeds, both trained
players average **7.1875 floors**, versus **7.0625 initially**. Their +0.125-floor differences
have paired intervals including zero. The new predictor improves its training return estimates,
but this does not establish a better policy. Best-trained checkpoints were actually evaluated;
neither comparison silently repeated the initializer. All 64 shared initial-policy traces match.
The saved-only audit checks every episode, 68,929 decisions and 2,866 files without new play.
See [the results and limitations](native-a8-credit-comparison-result.md).

**Follow-up now implemented above:** #143's short saved-TRAIN normalization and conditional
controls preserve public entity/amount relations and every legal action family. No fields are
deduplicated by this scaling treatment. #35's independent-run batch-size/gradient-agreement
control remains important; lower prediction error alone does not justify short-trace GAE or
a larger unchanged run. Both the credit comparison and the scaling comparison above are now
complete. Base readiness/adaptive thinking remain unmet.

### Preserved pre-comparison handoff

**Native A8 pilot v5 completed reliably but retained no trained improvement (#146 / #143).**
All 336 attempts ended normally: zero failures, missing games, wins or completed acts. It ran
eight training rounds, 627 updates and 26,061 verified training decisions in 14.82 minutes,
retaining 300 MB with zero app copies. All unchanged-input checks passed. Worker v9 and host
v34's cache/queued-discard repairs worked throughout this panel.

The starting player scored 7.5625 average floors on confirmation seeds; checkpoints after
rounds four and eight scored 6.8125 and 7.1875. Both also lost under the exact declared auxiliary
score. Selection correctly retained the initializer. The final two development panels therefore
used the same original player and RNG, each averaging 7.375 floors. They do not independently
evaluate a trained checkpoint. The best recorded game reached floor 17. The saved-only audit
verified every case and 1,427 source files; no games or updates followed.

**Diagnosis completed; next is a controlled learning repair (#35 / #143 / #146 / #134).**
The critic increases choice-bearing target variance in six of seven rounds after its first fit;
round-8 actor-gradient trace variance is 18.5% above a centered-constant reference. Thirty-two
independent runs per update produce weakly agreeing gradients; 26,061 decisions are only 256
whole-run outcome lessons. A sampled combat probe shows hidden saturation rising from 10.2%
to 58.9%, but no exact candidate-vector aliases and little hard clipping. Both initial/trained
networks learn an artificial HP-conditioned rest choice on 18 held-aside training examples.
Gradient derivatives pass real-state checks. No unique causal explanation or native ablation
is claimed. See [the measured diagnosis](native-a8-pilot-v5-learning-diagnosis.md).

**Historical pre-comparison state: value/credit implementation complete (#35 / #146).**
The integer-zero optimizer edge case is fixed. A small public-state predictor is cross-fitted
by whole games, with equal-game fitting weights and no self-outcome leakage. Using only v5's
256 TRAIN runs, its later-round squared error is 31.7% below a fitted constant and 61.6% below
the old critic; it improves all four audit rounds. Gradient agreement improves in round 1 but
worsens in round 8, so lower prediction error is not yet a demonstrated learning improvement.
Objective-preserving credit telescopes on all saved runs; lambda=1 recovers the original
return-minus-value credit exactly. Shorter-trace GAE stays disabled. Both new four-game pipeline
controls and saved-credit reconstruction pass, with zero failures or app copies.

**Completed owner command:** `bash scripts/compare-native-a8-credit-v1.sh` from the repository.
This is a matched old/new credit comparison: 672 planned attempts, two sequential methods,
the same actor/training seeds/RNG/score/update budget, and fresh confirmation/development seeds.
Both explicitly evaluate the best trained player, keeping the incumbent separate. Expect
25–40 minutes total; 30-minute cap per method. The owner has now finished both arms in 30.84
minutes. The [implementation guide](native-a8-value-credit.md) preserves the launch contract.

Remaining ordered work:
1. #35 / #146: completed comparison and saved outcome audit above; retain as exploratory evidence.
2. #143: test representation normalization/reduced duplication against saturation and conditional
   learning controls if needed after this one-factor comparison. Preserve every action family
   and public entity/amount relation; do not enlarge the model without demonstrated need.
3. #35 / #134: address remaining run-level gradient noise using measured independent-batch-size
   controls and/or shorter-trace credit only if value evidence supports it. Do not assume either
   method helps from prediction error alone. No larger unchanged PPO/GA, sweep or controller now.

All v5 sources, checkpoints, optimizer states and results remain preserved. Re-running its
training script only shows the saved result; both comparison methods are also now complete. V4 remains
stopped with five training rounds, 191 normal losses, one failure and 144 unplayed; do not
restart it under repaired sources. [Repair evidence](native-a8-worker-potion-repairs.md) and the
[v4 stop report](native-a8-pilot-v4-stop.md) retain the earlier chronology.

Base readiness and adaptive thinking remain unpassed. Patch transfer, other difficulties and
larger unchanged GA/PPO batches stay later work.

### Preserved pre-v4 handoff

The finite native mechanics package was completed under its declared scope (#148).
Host v33 supports all five AnyTime potions outside combat, exact real/fake merchant targets for
Foul Potion, inventory open/close and current-slot discard. Native effects and game rules remain
in the original DLL. Twenty-five potion controls, two merchant purchase/exit checks, new lifecycle
fixtures and a 12-game isolated worker panel pass with zero app copies.

The composed gate retains the **host-v32** 1,849-case sweep and its true scope, rechecks saved
hashes, binds the reviewed presentation delta and requires new controls. A first short greedy
learning check failed on legal loops and stays preserved. Merchant inspection now reaches the
learner's public memory; the new explicitly stochastic control passes **4/4 games, 228 verified
training decisions and six updates**. Fixed evaluation RNG streams are shared across checkpoints;
every action remains selectable. These are four losses and pipeline evidence, not stronger play.

**Earlier handoff, superseded by the stopped result above:** let the pilot finish, then use the
[saved-only assessment](native-a8-pilot-assessment.md). Pilot v4 starts from the original seeded
network and zero optimizer state: eight rounds, 336 planned games, independent development
evaluation and bounded failed-worker continuation. The assessment checks ownership, ending
evidence and the original confirmation selection, reports paired uncertainty, and keeps failed
games in the denominator with zero progress in the main comparison. It reads no partial games
before the final summary and launches nothing. No live results were inspected during its
implementation; all pinned pilot inputs remain unchanged. A historical v3 regression reproduces
its inconclusive result. Assess generalization and failure types before scaling; restore
greedy-quality checks before base readiness. Adaptive thinking, cross-patch work and larger GA
batches stay later.

### Preserved earlier milestones

**The actual-engine v3 pilot and first mechanics sweep are complete (#148 / #146, 2026-10-15).**
The owner finished all 336 attempts: **332 normal endings, four failures, 627 PPO updates and
26,416 verified sampled training decisions**. There are no wins. Independent average floor is
8.75 selected versus 7.4375 initial (8.625 selected with its failed game scored zero); the paired
interval includes zero. Preserve every checkpoint, the four failures and the inspected development
panel. This is inconclusive quality evidence, not base readiness or permission to scale blindly.

The new private inventory joins all **1,660 native model types** without missing/extra classes.
Host v31 and public combat v3 remove hero-only resource assumptions, preserve foreign orbs,
companions and current star costs, and fix reentrant choices plus reward-to-bundle waiting.
The owner finished **1,824/1,824 contexts** in **44 minutes**: 1,691 native effects,
83 observed prerequisite blocks and 50 failures. The failures share three causes: 45 disabled
multiplayer-card geometry checks, three invalid uninitialized Mad Science fixtures, and two
Particle Wall plays incorrectly marked undelivered after returning to hand. Original results stay
unchanged. Host v32/public combat v4 repair these causes; native Tinker Time previews supply nine
valid card forms, and exact new manual-play history confirms return-to-hand delivery. The expanded
plan has **1,849 cases**, including a same-card repeat check. Shared frozen inputs/cache created
zero apps and retained about **357 MB** for the original sweep.

**The repaired controls pass 90/90:** 44 effects and 46 native prerequisite blocks, zero failures,
127.81 seconds, 19.08 MB retained evidence. Same physical Particle Wall replay and nine distinct
configured card forms verify. All original and repaired case hashes verify; 1,339 repository tests
and 19 focused new Node checks pass.

**The repaired sweep passes 1,849/1,849 checks:** 1,721 native effects, 128 observed prerequisite
blocks and zero failures/unattempted cases. All saved case hashes and the original denominator
verify. The owner finished it in **45m30s**, retaining **353.07 MB**, with **379.31 MB** peak memory
and zero app copies. The original failed sweep remains preserved.

**The [short follow-ups](actual-engine-mechanics-followups.md) also pass.** Codex ran all nine
random-action games: **522 decisions**, nine observed decision families, zero interface failures
or truncations, and an identical exact-repeat trace. Skip and offered shop choices were exercised.
Privileged act-transition/Architect/zero-HP-victory fixtures pass on the same v32 build; these
are zero player wins and zero PPO examples. Combined wall time **33.83s**, peak memory
**302.87 MB**, retained evidence **7.20 MB**, zero app copies. Saved-only verification passes.
The earlier blocked launch reports remain intact. [Current evidence](evidence/actual-engine-mechanics-sweep-and-followups-v1.json)
binds the sweep, follow-ups, native build and resources.

**Historical pre-potion handoff, now completed above:** outside-combat potion controls and
Foul Potion's merchant target were the remaining declared requirements. Do not repeat completed
batches, reinterpret random play as model quality or automatically migrate old models.
Strong-base readiness still comes before adaptive thinking.

The following paragraphs describe the earlier pre-potion handoff. Other cases continue only after a failed worker is proved stopped; keep unsupported/prerequisite-
blocked/untested mechanics explicit. Resolve the remaining potion requirements before a new
environment/worker/neural admission.
The new all-pool path has a coverage gate; historical pilot results are not retroactively upgraded.
The earlier v1/v2 stops and their event-presentation repairs remain preserved.

**The owner's repaired second seed is complete (#145).** It plays **104 actions** and ends in a
native **loss on floor 5**, with no unsupported states, recovery, delivery failures or caps.
Its saved trace and shared-app reset verify. Together with the original first seed's **144-action,
floor-6 loss**, we have two independent naturally played shipped endings. They use explicitly
recorded diagnostic policy revisions; this is environment evidence, not a common-policy strength
estimate. The old repeated-card-offer failure remains unchanged. The old command now audits saved
results; no new game is required.

**Targeted later-act, victory and cleanup handling is implemented.** Native v22–v24 restore missing
graphics/call bindings and the absent test-mode audio service used by a boss death hook, retaining
the original game rules DLL. A new explicit cleanup gate catches shutdown failures.
A separately marked fixture reaches all three transitions through native Proceed and the final
Architect dialogue. The shipped app verifies Act 1→2 and Act 2→3, including the fresh map tutorial.
A saved-only supplemental audit verifies the already played final sequence through explicit win;
its original batch still records the JSON key-order verifier failure. Zero HP alone is not loss,
and entering the Architect's victory room alone is not yet a completed win.

All targeted app checks reuse the same app/inode with fresh profiles, zero new copies and verified
reset. Forced boss defeats are privileged fixtures: **zero player victories and zero learning
examples**. Imported boss saves re-offer rewards, so these checks compare act targets/endings,
not full reward/RNG resume parity. Unknown states, missing fields and uncertain delivery remain
failures. [Current evidence](evidence/actual-engine-v0.111.0-progression-v1.json) retains the owner
result, new repairs, passing checks and every preceding failed diagnostic.

**The current native regression passes 8/8 clean endings and shutdowns:** 775 decisions across
10 decision families, 25.855 seconds of summed case wall time, zero failed/unattempted cases or
new app copies. One saved successful case is reused and seven new games finish in the final
collection. All are losses; the old v21 1,115-decision/15-family panel stays separate. A capped
v23 cleanup failure and a private collector error remain preserved.

**The temporary target-ID bug is fixed (#146).** New diagnostic policy v5 and the actual-engine
public entity graph replace runtime handles with visible local occurrences and retain target
HP/statuses/intents, ownership and per-copy facts. All **783 saved observations** pass **2,349**
renaming comparisons. Old helpers, recipes and results remain unchanged. The weak diagnostic
initializer's historical floor differences were not learned-model comparisons.

**Worker isolation and the neural connection now pass.** The final versioned panel completes
**12/12 games and 1,214 decisions**, including eight serial seeds and two parallel workers each
repeating its seed after reset. Semantic traces match; profiles/processes are separate, sibling
profile access is denied, protected inputs stay unchanged and shutdown verifies. It takes
**19.07 seconds including the resource wrapper**, retains **66.57 MB**, and creates **zero app
copies**. Earlier startup/sandbox/controller failures stay preserved and are not admitted.

The final actual-engine learning control completes **four games**, verifies **209 sampled
decisions**, applies **six PPO updates**, changes both actor and critic, reloads the checkpoint
and checks saved public input/action/delivery/ending chains. Its two greedy control games reach
floors 17 and 14; **all four games are losses**. Their different seeds/behaviors do not establish
improvement. The workflow reuses the tested PPO mathematics with a new public encoder and model;
no old v0.107.1 input or trained weights are silently migrated. Every decision family remains
learnable, including Skip and public memory of previously declined offers.

**The v3 neural pilot is now historical, not the next command.** Its finite learning and
independent comparison are complete. Use the coverage guide for the current owner handoff.
Strong-base readiness and adaptive thinking remain unpassed. GA, other difficulties and patch
transfer remain later; a useful native checkpoint still needs its new schema connected to the
reused shipped-app runner before a neural UI demonstration.

**Current finish line:** [the bounded Ironclad/A8 contract](actual-engine-a8-finish-line.md)
supersedes the open-ended mechanics queue below. Build the complete unattended public-action
loop, qualify normal startup/later acts/endings and representative consequential interactions,
then complete an eight-seed natural-run panel. Normal deaths count as completed environment
tests; wins are not required for training admission. Known encountered gaps require repair.
During the bounded learning pilot, isolate newly failed games under the explicit two-per-panel
allowance without training on partial data; unknown delivery is never retried. Speed/isolation
and the short neural/PPO connection checks are complete. Exhaustive combinations,
every static mode reference, other heroes/difficulties and repeated fixture matrices are later
coverage work. Historical evidence below keeps its original scope.

**Current work: #146 owner pilot and assessment; #145's bounded Ironclad/A8 environment gate is complete.** The separately frozen v0.111.0 / `41cef1ea` game and #144 preservation are complete. Ironclad/A8 stays fixed;
full-run victory stays primary. Preserve all v0.107.1 archives, models, encoders and results.
[ADR 0005](decisions/0005-actual-engine-v0.111.0-qualification.md) orders public/mechanics
qualification, complete-run speed, then a separately versioned neural pilot. Emulator porting,
other difficulties and larger unchanged PPO/GA batches remain deferred.

## Historical qualification notes

**The v21 natural headless loop completes 8/8 candidate endings**, with zero unsupported states,
unknown actions, liveness failures or runtime errors in this frozen panel. It records **1,115
decisions across 15 decision families** and takes **28.813 seconds** in total case wall time,
including launches/integrity checks. All eight ordinary losses retain their original native death
evidence; no wins, later-act coverage, playing-strength claim or training admission follow.
Saved-only reconstruction verifies advertised actions, reads, delivery chains, counts and native
ending flags. Managed simulations share frozen inputs and create **zero app copies**.

The short diagnostics repaired native event text, per-card modifiers, generated-card selection
permissions, upgrade-preview text and missing Godot math APIs. Two fresh native builds reproduce.
The original game DLL remains unchanged; earlier failed and literal-seed runs stay preserved.
New seeds explicitly use the game's canonical `1`/`0` alphabet; old `I`/`O` runs are not relabeled.

**Two normal shipped starts pass** through Single Player/Standard/Embark, without imported runs.
Their initial deck, HP/resources, act, starting offers, A8 and seed match the native references.
The new Host also gets through **54 gameplay actions and two combats** before the short cap;
the exact Power-card tutorial and a partial-hand reshuffle are supported. A saved-only audit
reconstructs all five startup actions and 54 gameplay actions. This partial run has not reached
a shipped ending. One fixed app/inode is reused, with zero copies and verified reset.

**Historical owner stage:** `scripts/check-natural-a8-run-v1.sh` has the saved 73-action incomplete
attempt described above and now audits it without replay. Its original 15/16-minute caps, failures
and [foundation evidence](evidence/actual-engine-v0.111.0-natural-run-foundation-v1.json) stay unchanged.
The two-seed discovery command above supersedes that handoff; no old recipe is retried or relabeled.

**Remaining before the new neural pilot:** close the current-build environment checklist and
encountered public-input/selection omissions; measure bounded
worker isolation and whole-run costs; connect the new public experience/encoder to the existing
learner and pass a short learning control. Broader combinations and repeat matrices stay deferred.

**Completed profile stage:** the owner profile/description panel passes **8/8 cases**, zero failures or
unattempted cases. Four independent fixed-A8 seeds were each repeated twice with identical public
prefixes. Independent saved reconstruction verifies eight initial observations/Continue actions,
88 deck descriptions, 16 potion descriptions, eight relic descriptions and 24 starting options.
The native initial-context catalogue passes 1,517 descriptions per case, with one native mock
potion explicitly excluded. Overgrowth and Underdocks appear as the first act; normal act
selection/RNG agrees with the original method for the declared all-acts-seen profile. Tutorials
remain enabled/unseen and real account history is untouched.

Resource wall time is **258.689 seconds** (about 4 minutes 19 seconds), CPU **152.970 seconds**,
peak memory **975,060,992 bytes**; no cap was hit. All eight cases use one app/inode, eight private
profiles, **zero new app copies** and verified resets. The idle worker and frozen master remain
intact. **The stage is complete; no rerun is needed.** Its helper displays and audits saved results
only. [Completed panel evidence](evidence/actual-engine-v0.111.0-profile-panel-v1.json) preserves
counts, identities, storage scope and remaining gaps; the
[implementation evidence](evidence/actual-engine-v0.111.0-profile-descriptions-v13.json) stays unchanged.

**Completed combat stage:** all eight owner comparisons and an independent saved-only audit
pass, zero failed or unattempted cases. Two independent seeds × both fixtures × two repeats have
identical public prefixes. The audit verifies 72 observations, 64 effect decisions, 104 game/UI
actions, 24 combat tutorial pages and eight reshuffle confirmations. Corruption cost/exhaust,
Strength/Dexterity expiry, potion consumption, Pen Nib and the second turn agree in this scope.

Resource wall/CPU is **404.901/182.310 seconds**, peak memory **945,356,800 bytes**, with no cap hit.
One app/inode, eight fresh profiles and **zero new copies** have verified reset receipts. Evidence
retains 71,543,111 logical bytes of case records and 1,461,424 bytes of external profiles; tracked
storage includes the one shared app. **This stage is complete; no rerun is needed.** Its helper only
displays/audits saved results on repeat invocation. These assigned fixtures are not training data
or player-strength evidence. [Completed panel evidence](evidence/actual-engine-v0.111.0-combat-panel-v1.json)
preserves all counts/identities; the earlier short-check evidence remains unchanged.

**Current implementation under #145:** exact-slot combat potion discard is implemented in
separately identified Host v9 and passes two short native/shipped checks plus saved audits.
An automatic potion is discardable without a manual-use choice; two identical Strength Potions
retain distinct slots. Discarding one leaves the other unchanged, and using the second gives
exactly one Strength bonus. The new menu compares all offered play/use/discard/end-turn choices.
Seven Host checks, five identity/menu tests and 1,213 repository tests pass. The original game DLL,
older recipes and completed eight-case audit remain unchanged.

**Prepared optional follow-up:** `scripts/compare-combat-potion-discard-v1.sh` retains its
original eight-case recipe, preflight and 6–9-minute estimate. It has not been launched. The
owner's tighter finish line prioritizes a complete-run diagnostic over another repeat matrix;
the two passing exact-slot comparisons and negative checks remain evidence. New discard gaps
still block admission. [Guide](actual-engine-combat-potion-discard.md) and
[evidence](evidence/actual-engine-v0.111.0-combat-discard-v1.json) preserve its original scope.

**Historical queue before the bounded diagnostic:** broader current-wrapper/Host mechanics and complete public
facts: transient costs/effects/relic counters, mandatory/optional/nested selectors, consequential
mode references, shipped new-run initialization, later-act advancement and actual terminal
endings. Initial checkpoint inspection does not test the shipped lobby or act progression.
After required qualification, #146 measures full-run speed and connects a separate A8 neural
lineage. The current diagnostic results and owner handoff above supersede this queue's ordering.

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

**The owner completed the v3 bundle panel: 8/8 pass**, zero failures or unattempted cases, with
identical repeated public prefixes across two independent A8 seeds/four seed-pack pairs. The raw
saved audit verifies 24 observations, 16 effect decisions, 40 game/UI actions and 16 previews; an
independent saved-only recheck reproduces it without games. All eight attempts reuse the same app
path/inode with distinct profiles, zero new app copies and verified reset receipts. Both the frozen
master and current idle worker match the original inventory. No per-case `game` directories remain.
Resource wall/CPU is **319.079/193.116 seconds**, peak memory 850,165,760 bytes, with no cap hit.
Tracked final storage includes the existing working app; newly retained results are about 27 MB
and profiles about 0.9 MB. V1's zero-case space failure and unused v2 recipe remain immutable.
Details: [completed panel evidence](evidence/actual-engine-v0.111.0-bundle-panel-v3.json) and
[working app reuse](working-app-reuse.md). No rerun, full game or learning follows this result.

**Reward pickup implementation and four short shipped checks now pass:** Calling Bell claim-all
and claim-one/skip, Cauldron fill/discard/replace/skip and fill/skip. Raw reconstruction verifies
21 observations, 17 effect decisions, 23 game/UI actions and four real tutorial clicks. The cases
reuse one app/inode with four fresh profiles, zero new app copies and verified reset. They are
explicit serialized one-Strike/1,000-gold fixtures, not naturally reached rooms or full runs.
The missing first-relic tutorial is repaired in a separately pinned Host; two fresh builds and
three focused tests pass. Observed rendering/operand differences are normalized without changing
values or weakening current item/price/potion/slot bindings. Sixteen corrupted saved records
are refused. Original game/SDK/Host, failures and earlier proposals remain preserved.
Details: [reward pickup evidence](evidence/actual-engine-v0.111.0-reward-pickup-v1.json).

**The owner reward panel now passes 8/8**, with zero failures/unattempted cases and identical
repeat prefixes across four independent A8 seeds/scenario pairs, each twice. Saved re-auditing
checks **42 observations, 34 effect decisions, 46 game/UI actions and eight real tutorials**,
launching no games. Resource wall/CPU is **351.598/208.263 seconds**. Eight fresh profiles reuse
one app/inode with zero new copies and verified resets; the master and current idle worker are intact.
The historical wrapper tracked its output folder instead of the recipe-owned case folder, so its
storage figure is incomplete. Preserve the result and missing-peak limitation. The repaired helper
derives all cache/output/tracking paths from the recipe; completed invocation only displays/audits
saved data. Two runner regressions cover this mismatch without game launches. No rerun is needed.
[Completed panel evidence](evidence/actual-engine-v0.111.0-reward-panel-v8.json) records the scope.

The v13 profile/text package above implements the pending contract and exporter repair.
Its owner repeat panel is complete. The combat-effects repeat panel above is also complete; then
continue the remaining mode reviews alongside encountered mechanics coverage. Broader rest/relic options,
full public effects and remaining decision coverage follow. Remaining work includes
remaining modifier/expiry/relic-counter interactions beyond the two assigned turn-two fixtures,
remaining reward/selection families and large choice spaces, out-of-combat potions, native relic
purchases/discount interactions, skipping a merchant before opening its inventory, other public
decisions, later acts and actual endings. Inventory coverage is not exhaustive reachable-state
coverage. The new Host's finite prior-family checks remain separate from historical repeat panels.
The legacy persistent-potion fallback remains historical; v13 uses native formatted text.
Qualify the current Host's broader decision families and transient modifier/expiry states
before learning admission. Registry text and finite reward fixtures do not exhaust nested hooks.

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
| Serial reuse implemented and owner repeat panel verified; maintenance remains | Eight cases reuse one protected app with fresh profiles, zero new app copies and verified resets. Explicit blocked-worker repair/retirement remains; parallel reuse follows under #146. | [#147](https://github.com/benyanc/spireshift/issues/147), [#145](https://github.com/benyanc/spireshift/issues/145), [#146](https://github.com/benyanc/spireshift/issues/146) |
| Complete for the bounded Ironclad/A8 environment gate | Two ordinary shipped losses, explicit later-act/endings, the ID-safe public input and representative mechanics stand. Native serial/parallel/reset and short neural integration controls pass. Earlier failures stay preserved; new encountered omissions still require repair. | [#145](https://github.com/benyanc/spireshift/issues/145), [#141](https://github.com/benyanc/spireshift/issues/141), [#143](https://github.com/benyanc/spireshift/issues/143) |
| Finite mechanics package complete ([#148](https://github.com/benyanc/spireshift/issues/148)) | Preserve prior pilots and failed sweep. Repaired 1,849-case sweep, nine random-action games, act/endings, outside-combat potions and Foul Potion merchant controls pass. The composed gate preserves the sweep's host-v32 scope and binds new v33 controls. These are interface checks, not playing strength or base readiness. | [#146](https://github.com/benyanc/spireshift/issues/146), [#35](https://github.com/benyanc/spireshift/issues/35), [#78](https://github.com/benyanc/spireshift/issues/78) |
| Controlled PPO comparison assessed; native tactical learning controls next | Preserve the clean 256-attempt result: no demonstrated improvement. Proceed through native tactical controls, structured inputs/separate capacity, richer whole-game value prediction, bounded varied experience and qualified teachers, one assessed intervention at a time. No automatic scaling. | [#35](https://github.com/benyanc/spireshift/issues/35), [#143](https://github.com/benyanc/spireshift/issues/143), [#146](https://github.com/benyanc/spireshift/issues/146), [#78](https://github.com/benyanc/spireshift/issues/78) |
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
