# SpireShift engineering instructions

## Binding objective

SpireShift's current priority is a base player that consistently wins complete Ironclad/A8 runs
from normal starts on unseen worlds, followed by separately validated A10 play. Terminal full-run
victory is the primary optimization and evaluation outcome. Act completion, floor, HP and
resources are auxiliary diagnostics. CPU costs are secondary operational measurements; CPU
profiling, equal-budget studies and adaptive allocation must not displace base-player learning.

Every experiment must load a versioned `ObjectiveSpec`. Changes to the primary objective,
terminal condition, or compute constraint require an architecture decision record and explicit
test updates before execution. Historical experiments retain their fixed whole-run constraints,
including the 128-CPU-second guard. ADR 0007 changes future work priority and compatibility scope;
it does not silently mutate an existing objective, guard, recipe or result.

New full-run learning may also declare a versioned `TrainingScoreSpec` for an explicit bootstrap
learner return (ADR 0002). Keep it separate from binary environment rewards and terminal-victory
evaluation, and never interpret it as a victory probability or readiness pass. New experimental
policies may learn every decision family and depart substantially from the weak baseline;
historical combat-only/proximity guards are not permanent requirements for these new recipes.

## Foundation before adaptive search

Do not train or promote an adaptive budget controller until the base policy/value system passes
the frozen readiness evaluation. The readiness evaluation must cover policy-only performance,
value regret, calibration, confident catastrophic errors, held-out generalization, and whether
model-guided search improves at equal compute.

## Current learning priority

The owner reprioritized the program on 2026-11-04: build a useful full-game base player and
demonstrate sustained A8 wins, then attempt A10. This directive and ADR 0007 supersede the
older handoffs below that put CPU attribution or completing the six exact-final canaries next.
The ordered current backlog is docs/backlog.md. Parent #78 owns the base milestone; #152's
win-focused curriculum implementation spans all acts, strategic decisions and final bosses.
Its sustained owner-run collection and assessment precede the actual base-learning recipe.
#134/#35 own whole-game learning, #143 demonstrated model/input needs, #146 fresh-game strength,
#149 targeted parity/final official validation and #142 later A10 support.

Use the frozen native engine for learning/development with current source/public-input/action,
known-gap and reset checks. Prepare a separately versioned admission/recipe before new work;
the old six-case live gate is not silently bypassed or declared passed. For the new program,
target official checks to changed interface/mechanisms and promising candidate milestones,
with genuine official validation before claiming official-game competence. Repeated full
official endings for every numerical checkpoint and renderer CPU profiling are off the critical
path. A demonstrated input/action/effect defect still requires a targeted fix/regression.

The present teaching studies establish narrow fitting, not a useful player: prior full-game
versions won 0/64, and the latest three teacher gains are +1/+1/+5 HP in already-won floor-2
fights. Seek successful varied continuations and meaningful later-game/boss learning, not
merely more copies of weak early labels. Explicit training-only late-act/boss starts are a
prospective curriculum tool; qualify their state/reset semantics and keep their outcomes
separate from normal-start full-run evaluation. No privileged teacher state reaches student
inputs, and held-out worlds never become labels.

Keep original/fitted full states and Adam as immutable baselines. New lineages may change all
learnable decision families, representation, architecture and policy/value training; exact warm
Adam, a fixed critic and proximity to a weak original are not universal requirements. Choose
material changes from evidence rather than automatically repeat or enlarge failed recipes.
Measure unseen natural-start wins, failure denominators and uncertainty; freeze the competence
threshold and confirmation scope before the assessment. Base competence precedes A10 and the
separate value/risk/search-readiness requirements for adaptive controllers.

Preserve the old canary result as three passes, one incomplete and two unattempted, its marker,
all frozen files and the blocked launcher. Do not retry VTV204 or relabel this as qualification.
Its completion, the old same-final interference experiment, CPU/budget research, GA/hybrid
bakeoffs and unrelated platform work are deferred. Practical wall/memory/storage caps remain
for bounded execution. This reprioritization launches no training, game, promotion or long job.

On 2026-11-05 the owner requested implementation of #152. ADR 0008 and
docs/native-win-curriculum.md define the separate native-only curriculum admission,
56 fitting / 12 development cases, all four act definitions and twelve bosses,
constructed training starts and quality gates. The owner command collects only,
with zero main updates; no automatic base training follows. Preserve original
full weights/Adam and every prior result. Use only fitting labels; final-test
seeds stay unlaunched. Short collect/learn/reload/act controls use disposable copies.

The final-boss control newly reaches the frozen headless Architect completion
failure. Prepared final-act goals stop at the native completed-boss reward owner
after actual boss combat, not a fabricated terminal victory. Keep its failure
evidence, explicit known-gap flag and unchanged natural-start terminal-win rule.
Targeted completion repair/qualification under #149/#146 is required before
full-run victory claims. Do not replay the failed control worlds or silently
patch CLI56. The sustained bank still needs owner collection and assessment.

The first owner #152 collection stopped on a full-belt reward referent collision
after six completed cases. The saved audit verifies 35 reusable seals, 1,148
complete-gameplay deliveries, five confirmed lessons and three strict goal rescues.
Preserve study-v1 and the interrupted fit-007 marker/world, including its 26
acknowledged diagnostic prefix actions; do not replay or train on that prefix.
The v2 continuation in docs/native-win-curriculum-recovery.md imports the six
completed cases, retains the historical failure and declares one fresh replacement.
The 61 unattempted cases and all quality/data-ownership rules remain unchanged.
Only the new curriculum wrapper repairs full-belt reward registration; game,
CLI56, Connector31, ordinary worker24 and converter16 remain frozen. The new
owner command collects only and stops, with zero optimizer updates. The linked
case denominator is 69, including the historical failed case; old commands stay
blocked. Architect completion and full-game competence remain unqualified.

The v2 #152 owner run completed thirty cases before a runtime-error stop in
fit-031/reference. The saved audits verify 168 reusable seals, 138 complete
episodes / 9,208 deliveries, eighteen confirmed lessons and thirteen strict goal
rescues. Keep both failed worlds/markers and all old data unchanged. The observed
fit-031 loss is not a clean outcome: an earlier Reattach death-visual call hit the
missing Godot.Node.GetIndex(Boolean) support API. Its 245 actions are diagnostic only.

docs/native-win-curriculum-reattach.md defines the separately qualified support
build57 and v3 continuation. Only a Godot stub method is added; the archived
CLI56, CLI/gameplay source, frozen game assembly and original/fitted full Adam
remain intact. Native controls must preserve 25-HP segment revival/targetability
and all-segment combat completion; runtime errors are never whitelisted. The
new execution manifest retains the same public input contract without inheriting
official qualification. Import the thirty verified cases without games, retain
both historical failures and use one fresh replacement for fit-031. The linked
denominator is 70. The 37 unattempted cases and quality/ownership rules remain
unchanged. The owner command collects only, then stops with zero updates.

The v3 collection completed the case-31 replacement, then reached Gambling
Chip's six-card any-number selector in fit-032/scaling. Its 1,957 ordered answers
exceed the documented 512-answer adapter domain. Preserve all three failures and
the latest 187 acknowledged diagnostic actions plus unacknowledged next action.
Thirty-one complete cases / 173 seals / 10,172 deliveries remain reusable, with
eighteen confirmed lessons and thirteen strict goal rescues. The three completed
siblings of interrupted case 32 stay diagnostic only; they supply no labels.

docs/native-win-curriculum-large-selection.md defines a separate native-only v4
contract. Bounded internal policy factors construct one ordered answer; only final
commit/cancel reaches the game. Preserve every admissible length, physical copy
and ordering, exact native bounds/permissions and delivered-only persistent memory.
Partial plans provide no labels; group all factors as one answer with weight one.
Future fitting must explicitly support the grouped version-2 bank. The game,
CLI56/support57, original/fitted full states and all older code remain fixed.
Import the 31 completed cases without games, preserve three failed worlds/markers
and the linked 71-slot denominator, leave 36 unattempted cases unchanged and use
one fresh disjoint replacement for fit-032. Owner collection only; zero updates.
Official Connector31's large-domain limit and Architect completion remain explicit
#149 gaps; the new inference contract inherits no official qualification.

The v4 curriculum sealed case 38, then stopped in fit-039/reference when
Test Subject's Intangible color callback hit the missing CanvasItem setter.
Preserve its 26 acknowledged diagnostic actions, unknown End Turn and marker.
Support build 58 supplies SetSelfModulate(Color) on the existing property and
uses the frozen game assembly. The native control must reach both revivals,
third-form Intangible application and removal, and the boss reward owner.
The ABI reference inventory is a source audit rather than runtime reachability.

The v5 declaration derives the plan from v4 with one disjoint replacement for
case 39. It imports 38 complete cases and 210 seals with 20 confirmed lessons
and 14 strict goal rescues, including the prepared Queen rescue. Collect the
30 remaining slots with the owner command in docs/native-win-curriculum-test-subject.md.
Keep four historical failures in the 72-slot linked denominator. Treat the
failed prefix and diagnostic controls as evidence only. Owner collection and
quality assessment use zero optimizer updates.

The v5 curriculum sealed case 42 and stopped at Trial Accept in
fit-043/reference. Preserve its 89 acknowledged diagnostic actions, unknown
Accept receipt, sealed start and active marker. Support build 59 gates the
three Trial portrait calls in TestMode and uses the exact prior game and Godot
DLLs. Keep the native RNG, verdicts and public choice contract. Track Trial
Double Down's abandon confirmation separately under #149.

The v6 declaration imports 42 complete cases and 232 seals, with 22 confirmed
lessons and 16 strict goal rescues across the partial bank. The Queen, Test
Subject and Aeonglass each have a confirmed prepared boss lesson. The owner
command in docs/native-win-curriculum-trial.md collects the 26 remaining slots,
including one disjoint replacement for case 43. Preserve five historical
failures in the 73-slot linked denominator. Collection and quality assessment
use zero optimizer updates.

The v6 run sealed all 56 fitting cases and ten held-out cases. Held-out case 11
stopped at Soul Nexus's death callback on a delivered Bludgeon. Its 134
acknowledged actions, unaccepted final successor, start and successful
reference sibling stay diagnostic. Support build 60 guards the absent scene
lookup and preserves the native death event and rewards.

The v7 declaration imports 66 complete cases and 354 seals. The partial bank
has 24 confirmed lessons and 18 strict goal rescues. Soul Fysh is the only
missing boss lesson. The owner command in docs/native-win-curriculum-soul-nexus.md
collects one fitting-only Soul Fysh supplement, a fresh held-out case 11 and
the original case 12. Preserve both original Soul Fysh losses and six
historical failures in the 75-slot linked denominator. Keep the same quality
thresholds and held-out ownership. Collection uses zero optimizer updates.

The v7 owner run completed and admitted the #152 bank. The saved assessment
in docs/native-win-curriculum-result.md verifies 370 seals, 25 confirmed
prepared fitting lessons and all twelve bosses, including Soul Fysh. The
32 normal-start collection attempts recorded zero wins. Next prepare a
separately versioned #134/#35 fitting recipe bound to this exact bank and
full-state copies. Keep held-out worlds for diagnostics and final-test
seeds sealed. Qualify the native Architect victory endpoint under #149
before counting #146 normal-start wins. The collection and assessment
performed zero optimizer updates.

The owner requested #134/#35 world-balanced fitting from the admitted bank.
Use docs/native-a8-world-balanced-fitting.md and its versioned owner command.
Each copy starts with the full original weights and Adam and receives one
decision per admitted world per update for 200 updates. The fitting-only scope
uses public action labels and fixed critic weights. Keep development metrics
separate from update and final selection. The short checks use disposable
copies. The owner run stops after freezing both candidates and leaves the
normal-start evaluation to #146.

The world-balanced owner run completed. The saved assessment in
docs/native-a8-world-balanced-fitting-result.md verifies both update-200
finals and the original full-state hashes. Offline held-out agreement
improved on both. Map and shop results warrant separate gameplay readings.
Keep both finals frozen for a paired normal-start development comparison
against their originals. First qualify the Architect endpoint with valid
native history under #149. The preserved failed fixture has an Ancient map
visit with no event-room record.

The owner chose fixed Ironclad / Ascension 8 on 2026-10-09. First establish a workflow that improves
full-run play at that difficulty. Selectable A0 or other ascension levels are deferred under #142;
they are not prerequisites for A8 training and must not displace learning work. New recipes must
declare the actual A8 rules and repaired source/native/adapter identity. Preserve the historical
pilot's invalid A0 label and results; never silently relabel or resume them under changed rules.

The owner accepted a separately frozen v0.111.0 actual-engine qualification track on 2026-10-10
(ADR 0005; #144–#146). This supersedes v0.107.1 as the next bulk-learning path, not the fixed A8
priority. Preserve the old archive, scoped admission, encoders, models and results; do not silently
migrate or resume them on new rules. Obtain the exact new game, qualify public inputs/mechanics and
measure complete-run speed before a new neural pilot. The prepared large v3 emulator pilot is
deferred. Emulator porting, other difficulties and larger GA batches are not prerequisites.

On 2026-10-12 the owner tightened the qualification finish line: complete the unattended
Ironclad/A8 public decision loop and genuine endings, test representative consequential
mechanics and fix encountered gaps, measure full runs/isolation, then integrate the existing
learner and perform a short learning check. Do not require exhaustive content interactions or
repeated fixture matrices before returning to learning. Bulk training still requires explicit
admission; a diagnostic run cannot grant it. Follow `docs/actual-engine-a8-finish-line.md`.

The owner authorized bounded diagnostic issue collection on 2026-10-13. Record every missing
field and reached public progress, continue only through existing verified current exit/decline
controls, and try other planned seeds after verified reset. A blocking unknown owner still stops
that game. Recovered/incomplete runs never count as clean admission or ordinary learning data;
uncertain delivery is not resubmitted. Preserve old failures, and keep optional Skip/leave actions
selectable without inventing permissions for mandatory choices.

On 2026-10-14 the owner authorized isolated failed-game continuation in the native learning pilot.
Retire and prove shutdown of the affected worker, preserve its marker/logs and audit any earlier
clean episodes before starting a fresh worker for the next planned seed. Never retry the failed
seed, reset an uncertain process or train on its partial episode. Count failures in the original
evaluation denominator. The pilot allows at most two failed games per panel; evidence corruption,
unverified shutdown, missing games or failures beyond that allowance still stop learning.

After v2 stopped with three completed training rounds, the owner chose on 2026-10-14 to start
the repaired v3 pilot afresh for a clean comparison. Use the original seeded numerical
initializer and zero Adam state; preserve v2's trained checkpoints and results separately.
Do not automatically resume those trained weights in this pilot.

On 2026-10-15 the owner requested a systematic native mechanics coverage pass after the v3
pilot finished with four failures. Inventory every registered model and test all card pools,
including cross-character resources on Ironclad/A8, current costs, nested choices and representative
rest/shop/reward interactions. Distinguish inventoried, observed, effect-exercised and untested
mechanics; do not claim exhaustive interaction proof. Large generated sweeps are owner-run.
Keep this finite pass and its known-gap gate separate from PPO experience and prior admissions.
See `docs/actual-engine-mechanics-coverage.md`.

The next v0.111.0 startup contract is explicitly `native_benchmark_full_v1`: native full content,
all native acts discovered, Ironclad/A8, the shipped lobby's seeded random act selection and
enabled tutorials with no completed entries. It uses synthetic isolated benchmark progress,
never real account history. Do not substitute content unlocks for act discovery, silently use
the legacy default-act list, or admit other progress profiles from these scoped checks. Public
descriptions must use native formatted model/option text, preserving named amounts, order and
image-glyph multiplicity; do not guess smart-format substitutions from base variables.

Use complete-run outcomes to improve the unified policy across every decision family, then test
the frozen player on independent seeds at equal compute. Repeatable auxiliary progress is a
development milestone; genuine full wins remain the goal. More games alone do not establish a
useful workflow. Revise a stalled method using evidence, and keep the readiness gate before
adaptive thinking. See ADR 0003 and the ordered backlog.

On 2026-10-21 the owner chose to finish and assess the already prepared policy-update
comparison before scaling or changing the learner. Its saved 256-attempt result is now
complete, with zero failures and no demonstrated improvement. Preserve it, both original
players and their complete Adam state; do not repeat or enlarge it automatically. The
agreed follow-up order is small understandable native A8 learning controls, structured
public inputs with a separate capacity comparison, a richer state-only value baseline
validated on whole games, larger/more varied bounded experience, and qualified stronger
teachers. Implement and evaluate each separately. Prior synthetic controls are historical
evidence, not proof that the native tactical cases are learned. Diagnostic subtask rewards
and privileged branch outcomes must never silently replace full-run rewards or become
ordinary PPO experience. See `docs/native-policy-update-comparison-result.md`.

The native tactical follow-up is complete and passes for both players and both methods.
It uses privileged short-horizon fixtures and an oracle diagnostic baseline; only two
held-out public inputs are genuinely unseen. Do not rerun it, promote its forks or
interpret it as qualification of full-run credit. Next compare structured public inputs
with hashing, keeping capacity effects separate; preserve all original full states/Adam.
See `docs/native-tactical-learning-result.md`.

The owner authorized the bounded structured-input comparison after the tactical result.
Use the named supplement, equal-size hashed supplement and unchanged-input control,
with exact inherited weights/Adam and matched starting behavior. Keep the native engine,
full-run reward/score, public-only boundary and current value baseline unchanged. The
20-game integration control passes; main games are owner-run. The layout uses saved TRAIN
inputs only; new PPO experience must come from each arm's own sampled games. Freeze all
finals before fresh full-game evaluation. This bounded supplement is not a lossless
whole-state encoder. See `docs/native-structured-input-comparison.md`.

The structured-input comparison is now complete: 640 attempts / zero failures and
1,314 updates on experimental copies; named inputs show no established improvement
over equal-size hashing or the originals. Preserve its result and every full
model/Adam state; do not repeat, scale, select a winner or train an adaptive controller
automatically. Next assess state-only credit using the newly saved TRAIN games,
with whole-world validation and separate behavior-policy cohorts before any new
gameplay intervention. Prior rich neural/linear and residual-correction studies were
negative; do not repeat their grids or silently adopt rejected predictors. A better
forecast still needs its own bounded fresh-game learning comparison. See
`docs/native-structured-input-comparison-result.md`.

The saved-TRAIN inventory-credit diagnosis is complete on 384 prior attempts / 64
worlds / 12 policy cohorts. Original folds, coarse coefficients and credit reproduce;
typed deck/relic information exposes real omissions but its fixed linear correction
increases withheld MSE by 5.17%. Keep the existing production baseline and all full
player/Adam states. Do not rerun predictor grids or silently promote this probe.
The owner has now put a short saved-state actor distinction audit before that
comparison: hold inventory counts constant while checking card definitions,
per-copy upgrades/costs, relic identities and owner-bound visible counters through
the actual policy encoders. Distinguish missing predictor inputs from lost player
inputs; differing inputs do not require an untrained policy to choose differently.
Repair any actual information-loss/ownership bug before new training. This audit
does not require lossless encoding of every state or adoption of a rejected rich
predictor. Then prepare a bounded experience/learning comparison and useful later-game
outcome coverage, then qualified teachers/curricula as a separate intervention. Prediction
error and changed credit signs do not establish better action selection. The active
diagnostic recipe/entry is v2; its v1 failed numerical verifier and source snapshot
remain preserved. See `docs/native-inventory-credit-diagnosis.md`.

The accepted actor-inventory distinction audit is now complete: 80 controlled
probes preserve meaningful deck/relic/upgrade/cost/ownership information in the
checked policy inputs. It separately found the upstream combat relic-counter
omission. Worker v11 adds only public owned ID/counter pairs; four native diagnostic
replays preserve every legacy input/action/ending and verify ordered counter
delivery. Do not resume old recipes under this changed observation. New environment
manifest v9 explicitly changes observation metadata while preserving the frozen
game and every imported numerical weight/Adam moment/counter.

The experience-budget comparison is now complete: 832 attempts / zero failures,
640 training and 192 fresh evaluation attempts, 2,175 updates on experimental copies.
Neither the larger batch nor the smaller batch establishes a fresh full-game gain;
all three frozen versions win 0/64. Preserve its result, four finals, both original
full players and all Adam state. Do not rerun, enlarge or select a winner automatically.
The recipe changes experience/batch/compute budget, not data variety alone.
See `docs/native-experience-budget-comparison-result.md`.

The subsequent production-path delayed-decision comparison also completes: 94 units,
204 native branches, 16,384 sampled diagnostic sequences and 868 copied-optimizer
updates. Both learned-baseline and exact-current-policy-baseline copies pass fitting
and all eight new held-out public roots for both original players. Preserve the
four-round control's earlier player 3 learned failure; the fixed 128-round study
resolves it without relaxed thresholds. This qualifies two- and three-action native
subgoals, not strategic horizons or full-run credit. The 222 skipped learned-arm
rounds have all-success batches and effectively constant centered credit; the
existing guard preserves warm Adam rather than drifting without signal. Do not
promote these specialized forks or rerun the completed study. Next qualify useful
natural multi-turn TRAIN teacher/curriculum examples with explicit observation
replay ownership, then one declared student intervention and fresh full games.
Earlier fixed-world preferences and old missing-counter bank roots are not silently
admitted. Jobs expected to take five minutes or more stay owner-run. No promotion,
larger unchanged follow-up or adaptive controller is automatic.
See `docs/native-delayed-learning-result.md` and the ordered backlog.

The natural multi-turn teacher collection now completes on 12 natural worlds: 190
native attempts, no failed/capped paths and no optimizer updates. Preserve its result
and the qualified collector. The fitting-only quality gate fails: four usable winning
fitting plans contain zero improvements. A separate three-choice/two-round plan saves
seven HP but falls outside the declared four-choice criterion; even admitting that
short example would supply only one of the required two improved fitting worlds.
Two held-out improvements must not become fitting labels. Resource guards reject no
higher-HP winning alternative; all four losing reference worlds remain losses.
The prepared v1 curriculum/fresh-game comparison stays unstarted. Do not relax its
gate, repeat the collection, rerun unchanged PPO or import old rejected preferences.
The next proposed work is a separately frozen teacher coverage/recoverability test
with earlier combat roots and coordinated decisions, not an automatically authorized
search expansion. Short successful lessons are not inherently unlearnable; declare
their use prospectively. Preserve both original full states/all Adam and all prior
finals. Local fixed-world lessons remain auxiliary, never full-run strategic proof
or ordinary PPO. See `docs/native-natural-combat-result.md` and the ordered backlog.

The owner subsequently authorized the separate bounded earlier-turn/coordinated
teacher comparison. Preserve the insufficient v1 collection and unstarted curriculum.
The new 2x2 design compares single-change versus coordinated search, each from a
turn-one root and after the same original greedy opening. Later roots must reproduce
that original reference's exact suffix. Main uses eight new TRAIN worlds, split
four fitting/four held out before selection, excluding all 14 previous teacher/control
worlds. Four lineages expand through 4 + 8 + 4 candidate slots, preserving earlier
edits and extending losing intermediates; all actual legal menus remain available.
Equal candidate limits do not imply equal CPU. Short verified lessons are counted
without retroactively changing the old gate. This is an offline fixed-world local
teacher comparison, never ordinary PPO or proof of full-run utility. It makes zero
optimizer updates and starts no student or fresh full-game stage automatically.
Prototype v1 preserves 43 sealed paths, one wall-capped interrupted prefix and four
unattempted units; it does not grant main admission. The agent's final control driver
started its unit clock after dependency reads and hit the unchanged outer cap.
Do not retry that seed or clear either active marker. V2 uses fresh controls, the
same eight unstarted main worlds, strict whole-path/prefix/request deadlines and
a 150-second session reserve. The owner completed v2 control: all 48 paths/eight
cells, no failures/caps, confirmed three-edit/cross-round execution for both
players. A later-start coordinated plan saves seven HP on one control world;
the other within-entry method comparisons tie. This is implementation qualification,
not fitting evidence, a stronger full-game player or approval to fit a student.
Saved-only assessment independently rechecks 48 native journals/receipts and
reconstructs 786 action distributions/choices, all cells, confirmations and exact
later suffixes. Main read-only preparation passes without creating its workspace.
The owner subsequently completed the eight-world main comparison: 576 sealed work
units, 533 native paths and 43 unavailable proposals, no failures/caps, all 32
cells verified. Both methods rescue the same two fights (one fit, one held out);
the two improved fitting worlds both come from player 2. Coordinated search has
no demonstrated advantage over single changes; its four initial lineages also
miss alternatives found by wider single-change coverage. Preserve the result and
do not repeat or enlarge this collection. Saved-only assessment reconstructs all
576 receipts/requests/plans and independently rechecks 64 reference/confirmation
journals and 1,175 distributions/choices; original full-state hashes/Adam match.
No student or full-game evaluation has run. Next propose a separately frozen,
small teacher/reference-clone/original transfer test using useful fitting plans
only, with explicit two-world coverage.
Held-out plans remain excluded, the old v1 curriculum/gate is not relaxed and local
fixed-world labels are never ordinary PPO. Preserve both full original states/all
Adam and every previous final. No automatic fitting, promotion or adaptive
controller. Keep long jobs owner-run, reuse frozen inputs and retain old evidence.
See `docs/native-coordinated-teacher-result.md` and the current backlog.

The owner has now authorized the separate controlled teaching/fresh-game test.
Use the sealed two-world fitting bank: the single-change 23-HP rescue on world
148 and coordinated 48-HP plan on world 192, selected with fitting outcomes only.
Both source worlds belong to player 2; both fixed initializers may learn the same
public lessons on copies without manufacturing more independent worlds. Keep
the four held-out worlds excluded from fitting and selection. Compare improved
plan cloning, reference cloning and untouched originals. Four trained copies
receive 16 epochs/four updates/32 choices, 64 updates each; inherit numerical
weights and full warm Adam exactly and leave all original files unchanged.
Critic weights, credit predictor, full-run score and primary objective stay fixed.
Seal all finals before any native evaluation; do not select an epoch from results.
Main then checks 36 fitting/held-out fights and 192 fresh full games across
32 common new worlds and both initializers, with matched greedy combat/sampled
noncombat evaluation. This is categorical imitation, not ordinary PPO. The short
control completes nine native attempts without errors, but does not demonstrate
stronger play. Main subsequently completes as assessed below. Preserve sealed full states,
receipts and uncertain attempts; never retry failed seeds or clear active markers.
No promotion, adaptive controller or next experiment is automatic. See
`docs/native-plan-teaching-test.md`.

The owner completed the controlled teaching test: 295 sealed units, 256 updates
on four copies, 36 completed fight checks and 192 fresh full-game attempts.
Both taught players independently reproduce both complete improved plans, saving
the lost fight at 23 HP and finishing the other at 48 HP. Every version still
wins 0/64 full games; improved-plan copies average 12.5156 floors versus 13.2500
for originals and 12.6406 for reference copies. One reference-copy game exhausts
all attacks and reaches the 4,096-decision cap; keep its failure in the denominator,
do not retry or use the partial game for learning. Its public pile identities
are present; do not mistake summary pile counts for a missing adapter field.
Saved-only diagnosis verifies 115,651 seals/295 receipts and 615 fight
distributions, with exact original weights/all Adam preserved. No promotion or
unchanged expansion follows. Next qualify public card-zone/exhaustion distinctions
through the actual encoder, then propose a more varied fitting-only curriculum
with matched work and a separate shared-policy-interference comparison. Noncombat
matching is a diagnostic, not a permanent restriction or a proximity guard.
Do not reuse the 32 final evaluation worlds or held-out plans as fitting labels.
Preserve every full state, outcome, source pin and old gate. No new collection,
training or adaptive controller starts automatically. See
`docs/native-plan-teaching-result.md` and the current backlog.

The owner accepted recurring official-game compatibility checks on 2026-10-23
after discussing the community CLI/bridge and shipped-game distinction. The next
priority is ADR 0006, before another learning intervention: exact batch/resume
identity, complete recorded policy-input/action regressions for every checkpoint,
current checkpoint delivery canaries at execution changes/milestones, and fresh
official-game original/trained evaluation before promotion or substantial scaling.
The first saved-only gate is implemented and BLOCKED: model manifest v9 names
v34 while the separately pinned experiment uses v35; four historical mechanics
pairs also differ as complete current-policy inputs and lack retained pile reads.
Do not infer a current rules mismatch, silently normalize missing information or
edit historical model labels. Qualify a versioned common public-input/checkpoint
adapter and explicit numeric/full-Adam-preserving environment import next. The
standalone guard rejects training without environment, recorded-input and live
delivery scopes; saved fixtures cannot certify that last scope. New experiment
entry points must use the qualified guard; preserved old runners are not globally
wrapped or retroactively admitted. No new game, fitting, promotion or controller
follows this diagnosis. Keep card-zone/exhaustion, broader curricula and policy
interference next in the learning backlog, rather than restarting unchanged PPO.
See `docs/native-compatibility-gate.md` and the current backlog.

The owner then authorized the shared input contract/current checkpoint live adapter.
The converter and actual-game delivery control now pass: one new player-2 world,
two actions per host (Neow choice and card-pack selection), zero updates/app
copies. Both original numerical weights/all Adam are exactly preserved in explicitly
labelled shared-environment copies binding CLI v35, worker v11 and official v13;
the old v9 label and all prior files remain unchanged. New input conversion can
change behavior despite exact numeric imports. Saved-only verification reproduces
all four choices/actual receipts. Full input equivalence remains blocked by current
Neow hover-card/option-flag export gaps and duplicate layouts. Do not filter those
facts or assume absent flags false. The prepared owner diagnostic covers both
initializers/two fresh worlds/four paired prefixes, up to 64 decisions per host;
it is not PPO, a full-game evaluation or automatic compatibility admission. No
main game has run. Preserve completed units and uncertain attempts, do not realign
divergent states, and leave this approximately 10–15-minute task to the owner.
Then repair complete public exports and qualify current-host checkpoint equivalence
before another learning intervention. The active short control is v3/shared manifest
v2; retain the v1 pass and v2 selection-name failure. That failure verifies clean
shutdown/reset. Explicit SDK selection aliases preserve card lists, ownership,
bounds and controls; do not discard meaningful fields to force parity. See
`docs/native-shared-live-checkpoint.md`.

The owner subsequently completed the v1 live diagnostic and authorized a coordinated
interface audit/repair. Preserve its eight prefix starts/487 delivered choices and
official shop stop after 39 deliveries; every shared app reset verifies. The new
saved audit inventories 24 surface kinds, four reads and 116 record declarations,
streams all 497 current complete frames, and keeps schema differences distinct
from matched-state effect evidence. Shop-slot declarations use existing public
offer-slot relations, never new action authority. Exact option enablement joins,
card-detail target checks and typed nullable omissions are separately validated.
CLI export v36 carries native event/hover facts; shared manifest v4 preserves
both original numerical weights/all Adam. The active short control is interface
control v2; old development sources/configs/results remain preserved.

The final four-choice-per-host control and eight saved choice/receipt reconstructions
pass, with zero app copies or optimizer updates. Declared short-sample field checks
have no remaining gaps, but full input equality still fails on layouts/duplication;
do not confuse that narrow pass with full compatibility or stronger play. Main
interface canary v1 is owner-run: two fresh worlds/both originals/four paired
prefixes, up to 128 choices per host, 15-minute session cap and clean resumption.
Its workspace is unstarted. Audit every saved public frame afterward, retain
unknown/uncertain attempts, and do not realign divergent games. No new learning,
adaptive controller, promotion or upstream publication is automatic. Add targeted
matched effects for important unobserved interfaces rather than requiring every
possible content combination. See `docs/native-interface-wide-audit.md`.

The owner subsequently completed interface canary v1: eight starts, 771 delivered
choices/receipts, 778 raw public captures and four official stops. Normal public
loss/result controls, transform-selection view flags, a stale read before sampling
and an absent native-only shop flag caused the stops; all app/profile/archive
shutdown/reset checks pass. Preserve this completed blocked report and its worlds.
The owner authorized four repairs and systematic discovery without more bulk games.

New shared helper v3 scopes selection/description/legality by owned public view,
keeps exact result-screen controls outside policy delivery, maps typed shop-room/
open-inventory state and refreshes only explicit stale reads before any new choice.
No submitted or uncertain action is retried. A source inventory, 20 generated
policy/terminal envelopes, 38 mutation checks and all 778 saved frames now pass;
1,586 frozen input probes make zero optimizer updates or new game attempts.
They do not prove all content combinations, effects or playing strength. The
caught development tooltip regression/fixture omission and earlier receipts remain.
The active offline recipe is interface-controls-offline-v3 / shared manifest v6;
new numerical weights and all Adam are exact imports of both original players.
Do not resume old recipes under these changed inputs or use the separate offline
layout prototype as a live contract. The short live wiring control now passes all
eight delivered choices with exact
app/profile/archive reset (41.45 seconds, no app copies). Saved-only verification
rebuilds every input, frozen choice and actual receipt in 3.96 seconds. Repository
checks pass 2,549 tests, strict types on 573 files and C# protocol in 143.95 seconds.
A fresh broader live canary is prepared/preflighted but remains unstarted; do not
run it automatically. Next consolidate remaining semantic layouts and targeted
effects/protocol transitions before new learning. Source changes invalidate
qualification; long jobs remain owner-run.
See `docs/native-interface-controls.md` and the current backlog.


The current input-layout repair is implemented as CLI v38, official connector v15,
worker v13, shared helper v7/layout v4 and shared manifest v11. New recipes reject
ambiguous O/I seed aliases and verify the official mounted seed outside model
inputs. Both original full weights/all Adam remain exact; 3,018 earlier pinned
files are protected. Typed reversible layouts keep owners, costs, card previews,
optional actions and unfamiliar facts. The saved bank passes 823 public frames,
20 envelopes, 843 exact reconstructions/raw bindings and 1,676 frozen input probes.
The earlier four-choice paired control matches completely through first combat,
with independent saved receipt reconstruction. Preserve all intermediate tuples,
startup/filter/shop failures and later fresh controls.

The owner chose one committed model card answer on 2026-10-24. The current
semantic tuple is CLI v40 / official connector v16 / worker v14 / shared helper
v9 / layout v6 / shared manifest v14. All earlier tuples and failed attempts remain
preserved. Native selected-card IDs now reuse their actual deck/pile identities;
source flags, selector ownership and upgrade-preview text are explicit. The
official adapter executes only the chosen cards and required native confirmation,
checks each current owner/control, never resubmits uncertain input and acknowledges
the model only after authenticated completion. Empty answers and cancellation
remain distinct. More than 512 ordered answers rejects the entire state rather
than silently truncating; a compact large-domain protocol remains a follow-up.

The targeted control passes all four complete inputs/action menus and deliveries
in both hosts, including one actual card removal via two native UI steps for one
model choice. Independent saved verification reconstructs all eight choices and
receipts. Both decks change from 11 to 10 cards, exactly the chosen Strike copy
is removed and every other visible card is unchanged. A preceding observation-only
scan checked four new starting menus, submitted no actions and used only public
menus/frozen choices to select this scenario; it is not fresh strength evidence.
Keep the v39 missing-description failure and the completed v40 reward-layout
mismatch. V40 uses the game's description-existence/formatting check; layout v6
maps the actually advertised reward skip control and visible color markup without
inventing an exit or removing unknown text. Never replay an uncertain seed.

The saved audit now passes 845 complete frames plus 20 generated envelopes, all
865 reversible reconstructions/raw bindings and 1,720 frozen input probes. All
3,119 earlier pinned files and both original numerical weights/all Adam remain
byte-exact. These controls do not qualify every selector/potion effect or stronger
play. The prepared broader canary is unstarted and preflighted: both originals,
two new worlds, four paired prefixes, up to 128 choices per host, 15-minute launch
cap and clean resumption. Only the owner launches this long task using
`scripts/compare-semantic-selection-v3.sh`; the v1/v2 launch prototypes remain
historical and must not be used. No fitting, promotion, automatic collection or
adaptive controller follows. Source changes invalidate qualification. See
`docs/native-semantic-card-selection.md` and the current backlog.

The previous semantic-selection canary is now complete, with four pairs/eight
starts and 790 delivered policy choices. Preserve its blocked result: reward/pack
layouts differ and the merchant-removal catalog has a valid owner that the old
validator rejected. Its final uncertain attempt must not be replayed.

The owner requested consolidated reward/pack/removal repairs and a longer whole
batch allowance. The new tuple is CLI v44, official connector v19, worker v15,
shared helper v10/layout v7 and shared environment v26. Actual reward alternatives
and mandatory/optional permissions remain native. Preserve pending reward identity
across preview/Skip returns. Packs are one committed model choice: verify the
advertised preview and exact native confirmation before acknowledging delivery.
A merchant-owned atomic selector may retain its read-only catalog; it gains no
purchase authority. Current energy/star costs and detail/card-copy facts stay
explicit. Empty belt aliases collapse only under an actually empty owned belt.
The encountered encounter-title and combat-pile preview omissions are repaired
at their source. Status glyphs retain their visible image meaning. Combat selectors
retain public pile reads and declare selected/context operands exactly once; do
not drop other inspectable combat facts to avoid duplicate IDs. No numerical
weights/Adam or game rules change.

Keep all development failures and source snapshots. A complete decoder check is
required in addition to surface-only tests. Short pack controls are targeted
compatibility evidence, never playing-strength evidence; the earlier 32-choice
control delivered the pack but retained a boss-name mismatch. Current offline v13
checks 1,642 saved frames/20 envelopes and 3,306 frozen probes. Targeted control
v11 passes all 32 complete input/menu pairs in 88.16 seconds, with 64 independently
reconstructed choices/receipts and exactly the chosen three-card pack added in
both hosts (11 to 14 cards). Both original full states/all Adam and all 3,609 prior
pinned files match. This is scoped delivery/effect evidence; actual paid merchant
removal and broader prefixes remain for comparison. The broader recipe is
preflighted and unstarted. The next owner launcher is
`scripts/compare-selection-flows-v1.sh`; the previous semantic-selection launcher
is historical. Its finite four pairs/up to 128 choices per host allow 30 minutes
per launch and six minutes per pair, after a separately capped 10-minute full
repository check cached for exact files. Capped checks cannot grant a receipt.
Operational launch limits have a separate
versioned receipt and never change completed-unit identity or add game attempts.
Reuse sealed pairs after interruption; retain uncertain attempts for inspection.
No training, promotion or adaptive controller follows automatically. Source
changes invalidate qualification. See `docs/native-selection-flows.md`.

The owner subsequently ran selection-flows canary v1. Full repository checks pass
2,585 tests/types/C# protocol in 151.71 seconds. The first native prefix stops
after 50 delivered choices/51 public frames, with no official start or completed
pair: a transform selector exports an upgraded Strike's base name while its deck
read exports the current Strike+ title. Preserve its active markers, confirmed
stopped process and world 401; never replay that uncertain attempt. The existing
converter's intrinsic-name conflict rejection remains correct and unchanged.

CLI v45 replaces all six base-name exports with the game's current CardModel.Title
through its visible-text renderer. Both fresh repaired builds reproduce, the game
DLL is unchanged and shared environment v27 explicitly binds the new source.
All existing execution/conversion helpers, official connector v19, both complete
original numerical players/all Adam and 3,981 prior pinned files remain exact.
Six new title/copy/conflict regressions pass. Saved-view reconstruction reproduces
the original rejection and admits 12 choices only after a separately labelled
same-copy public-title substitution. It is not repaired-source execution evidence.

The new saved audit passes 1,642 frames/20 envelopes/3,306 frozen probes. A new
32-choice-per-host regression is preflighted on fully completed, independently
verified clean control world 556. Keep its explicit regression replay declaration;
it is not a fresh strength test. The owner closed Steam and the short validation
now passes: four native three-copy rendering fixtures (base/upgraded Strike,
upgraded Defend and upgraded Cold Snap), then all 32 complete public inputs/menus
per host in 86.64 seconds. Saved-only verification reconstructs all 64 choices and
receipts. Both decks add exactly the chosen three-card pack (11 to 14 cards), with
prior cards unchanged and exact app/profile/archive restoration. The repaired code
passes 2,586 tests/types on 633 files/C# protocol in 150.81 seconds. Preserve both
full repository receipts; do not treat a new metadata/configuration file as an
old exact-file check receipt.

The replacement broader plan is frozen, preflighted and unstarted on worlds
403/404, excluding the old attempted/reserved 401/402. It checks four pairs and up
to 128 choices per host. Keep 30 minutes per launch/six per pair, a separate cached
10-minute exact-file repository check, one fixed app, no promotion or training.
The owner next runs `scripts/compare-selection-flows-v2.sh`. Do not run the long
comparison automatically or rerun the interrupted v1 launcher. Preserve uncertain
attempts and both full original players/all Adam. These finite controls do not
grant exhaustive mechanic parity or playing-strength qualification.
See `docs/native-card-title-repair.md`.

The owner completed selection-flows canary v2 within its allowance (779.82 seconds).
Three official prefixes execute all 128 choices and one stops during hand selection,
but all four pairs have input differences after 48/88/6/88 matching decisions.
Official execution success is not complete input equality. Preserve all four units,
the uncertain player-3/world-403 transaction and every prior source tuple. Never
replay that uncertain attempt or interpret the result as playing-strength evidence.

The separate repair is CLI v46 / official connector v20 / worker v16 / shared
environment v28, with converter v10/layout v7 and the frozen game unchanged.
Wait for actual reward-family departure after a single accepted Continue, rather
than admitting a still-closing reward panel with a new snapshot/signature. Combat
potions use the same owned inventory occurrence, physical copy, belt slot and exact
native targets; preserve current permissions and hover facts. A persistent hand
node stops owning an atomic selection when its native selection mode finishes,
not when the hand disappears. Exact chosen-card/confirmation checks and fail-closed
unknown delivery remain. Export the actual closed merchant's inspectable catalog
without purchase authority, with the same shop-room controls in both hosts.

Both source builds reproduce twice; 170 exact-game Host tests and portable Connector
checks pass. Captured potion/shop reconstruction matches full inputs and menus.
The saved audit passes 2,550 frames/20 envelopes/5,122 frozen probes; all 5,973 prior
protected files and both original full weights/all Adam remain exact. A privileged
native fixture verifies 14 actual closed-shop offers and their unchanged prices,
stock and identities on opening. It is not ordinary learning or a full-run attempt.
The new short paired control passes all 32 complete inputs/menus in 86.47 seconds;
all 64 choices/receipts independently verify, including the exact three-card pack.
App/profile/archive restoration passes; zero app copies/optimizer updates occur.
The full repaired-code check passes 2,587 tests/types on 640 files/C# protocol in
150.35 seconds with no cap. The final owner wrapper checks/caches its exact file
set separately; never forge a new metadata snapshot into an older check receipt.
The hand/potion lifetimes still need broader live coverage; finite controls never
establish exhaustive mechanics parity. Progress messages now distinguish INPUTS
MATCH from INPUT MISMATCH, reporting game delivery separately.

The replacement owner comparison is separately frozen/preflighted on fresh worlds
405/406, both unchanged players, four pairs/up to 128 decisions per host. Use
`scripts/compare-selection-flows-v3.sh`, with 30 minutes for the whole comparison,
six minutes per pair and a separate cached 10-minute repository-check allowance.
Do not start this long task automatically or rerun either historical launcher.
No training, promotion or adaptive controller follows. Preserve completed pairs and
uncertain evidence. See `docs/native-transition-owner-repair.md` and the current backlog.

The owner next supplied canary v3's cached result. Its original batch takes 914.72
seconds and all eight prefixes/880 choices verify, but zero complete input pairs
match; the subsequent five-second command only displays the saved result. The old
control-pass label described delivery, not input equality. Preserve that report.
New status and exit success require both delivery and full input/menu equality.

The separate reward-guidance/card-copy repair is now qualified by targeted controls.
One model Continue includes only the exact combat_reward_ftue warning dismissal
and a freshly revalidated same-owner/state/menu final confirmation, ending only
when rewards actually depart. Unknown delivery is never retried. Layout v8 anchors
copy IDs to visible selector order before unordered reads and keeps distinct cards,
raw bindings and complete reversible evidence. Its 112-choice control fixes the
original Headbutt mismatch at 96, then reveals a genuine missing Spiral preview at
107. Preserve that negative result and all 224 verified receipts; never truncate
it or discard public effects to conceal another discrepancy.

The final tuple is CLI v49 / official connector v20 / worker v17 / converter v12 /
layout v9 / shared environment v32. Capture actual native enchantment model/amount,
format a display clone and retain the pending preview on card selection. Do not
infer it from event names. Keep Harmony capture-state owners separate; preserve
v47's misplaced-export build and v48's startup rejection/stopped worker/markers.
V48 submits no policy actions and starts no official game; its nonexecution review
is retained. V49's privileged native event fixture exports the actual nine-card
Spiral amount-one preview and shuts down cleanly in 6.82 seconds. It is not PPO data.
Alias only declared event body fields and preview provenance; preserve identities,
amounts, effects, unfamiliar facts and conflicting-value rejection.

Both targeted v49 regression controls pass: all 64/112 complete inputs and menus
match in 154.00/224.54 seconds; all 352 choices independently reconstruct, with
actual reward confirmation, distinct copies, pack delivery and enchantment preview.
App/profile/archive restoration passes; no app copies or optimizer updates occur.
Eleven Node regressions and 18 focused Python tests pass. The saved audit passes
3,790 frames/20 envelopes/7,594 frozen probes with 9,043 prior files and both original
full weights/all Adam unchanged. These are completed-clean-case regression replays,
never uncertain-seed retries or fresh playing-strength evidence.

The next long owner command is `scripts/compare-selection-flows-v5.sh`; old v3 is
historical and development v4 is unstarted. The new plan is frozen/preflighted and
unstarted on fresh worlds 407/408, four pairs, both originals/up to 128 decisions
per host. Keep six minutes per pair/30 minutes for the batch and a separate cached
10-minute exact-file repository check. Run short checks autonomously; do not launch
this long comparison. Preserve all earlier sources/evidence. No training, promotion
or adaptive controller follows automatically. Source changes invalidate qualification.
See `docs/native-reward-guidance-identity.md` and the current backlog.

Keep the one cosmetic frozen-source formatting exception exact: `.ruff.toml`
inherits unchanged `pyproject.toml` and excludes only native_flow_inputs_v4.py
from formatting. Lint/types/behavioral checks still include it; the regression pins
its full SHA-256 and checks identical AST after formatting. Do not edit the frozen
runtime, broaden the exception or skip full checks. Format new versions before
freezing any recipe; preserve the initial failed formatting-check receipt.

The owner has completed canary v5: all eight clean prefixes/964 model choices
verify, within 928.52 seconds, but zero complete pairs match (1/1/53/1 equal inputs).
Preserve it. Source/adapter repairs address repeated owned relic card previews,
the generated-choice legacy fallback and duplicate merchant detail reads. Fold only
same-owner exact duplicate facts, with all unknown/conflicting data and reversible
source evidence retained. Generated choices use actual native owner/presentation,
canSkip and current offered copies/details; preserve full combat/pile context too.
The native Discovery probe passes on actual three-card data and actual allowed Skip.
Its source-delivery fixture is privileged, never ordinary PPO or full-game evidence.
Keep earlier failed probes and incorrect diagnostic assertions as negative evidence.

The first 64-choice shop regression fixes the initial difference at 53, then exposes
empty-slot visibility and the false Card removal label at 54 after a potion purchase.
Keep its 128 verified receipts and negative result. CLI v51 follows the native item
widget null-model visibility conditions, with removal-service visibility separate.
Empty potion slots keep their cost/stock/identity and null label; purchase rules stay
native. Both fresh builds reproduce. Connector v20/game DLL remain unchanged.
The final tuple is worker v21 / converter v13 / layout v10 / shared environment v36.
All final 8/8/64 complete input/menu controls pass; 160 choices independently verify,
with app/profile/archive restoration and zero app copies/updates. The saved audit
passes 4,760 frames/20 envelopes/9,526 probes; 10429 prior files and both original
full weights/all Adam are unchanged. Fifteen Node regressions pass. Do not broaden
the existing frozen-source formatting exception; new files are formatted before pins.

The replacement owner command is scripts/compare-selection-flows-v9.sh. V5 is
historical/completed; development v6–v8 main launchers remain unstarted. New worlds
409/410, four pairs/both originals, up to 128 choices per host, six minutes per pair
and 30 minutes total, plus a separate cached exact-file repository check. The plan
is frozen/preflighted and unstarted. Do not launch this long comparison. No training,
promotion, controller or follow-up is automatic. Preserve uncertain attempts and
source tuples; source changes invalidate qualification. See docs/native-selection-owner-read.md.

The owner's selection-flows v9 stops after 96 acknowledged native choices at
observation 97: the same Particle Wall star cost is number 2 in hand and text 2 in
selection. Converter v13 joins these views before layout conversion. No official
game starts. Preserve both active markers, forced-stop code 143, complete source
snapshot and reserved worlds 409/410. A saved-only review reconstructs all 96 choices,
reproduces the old rejection and verifies converter v14 accepts that state while
leaving the preceding 96 inputs/choices exact. This is not clean PPO or admission.

The separate declared DTO scalar normalization precedes joining/sorting. Preserve
zero/no-cost/X, distinct physical copies, unknown facts, current energy costs and
raw bindings; genuine conflicts still reject. Reversible scalar evidence outside
the model restores raw types separately from the pre-layout graph. CLI v51,
connector v20 and worker v21 remain unchanged; converter v14/layout v11/shared
v37 explicitly declare this interface. The native Particle Wall/Gambler's Brew
fixture passes three two-star copies and one confirmed selection back to combat
in 7.02 seconds. Preserve its earlier diagnostic missing-ack failure; the corrected
fixture uses a fresh seed/workspace. It is privileged delivery, not full-run or
shipped-host parity. All 4,861 saved frames/20 envelopes/9,728 probes pass, with
11,594 prior files and both full original players/all Adam exact. All 8/8/64
full input/menu controls pass (47.55/49.79/119.96 seconds); all 160 choices independently
verify, with app/profile/archive restoration and zero app copies/updates. All 22
Node regressions pass on the repaired converter.

The next owner command is scripts/compare-selection-flows-v10.sh: separately
frozen/preflighted and unstarted, fresh worlds 411/412, four pairs/both originals,
up to 128 choices/host, six minutes/pair and 30 minutes/batch, plus the separate
cached exact-file 10-minute repository gate. Do not launch this long comparison
or rerun historical v9. No training, promotion, controller or follow-up is automatic.
Finite controls do not establish exhaustive parity or stronger play. Source changes
invalidate qualification. See docs/native-star-cost-normalization.md.

The owner completed selection-flows v10 on worlds 411/412 in 1,039.61 seconds,
within its 30-minute allowance. All eight host prefixes execute 128 choices and
stop cleanly with app/profile/archive restoration. The star-cost rejection is
absent. Saved-only verification reconstructs all 1,024 inputs/choices/receipts in
24.37 seconds; both original full weights/all Adam retain their exact hashes.
No learning or new experiment follows. Preserve this complete negative result;
zero complete input pairs match after 56/76/117/109 identical initial decisions.

The four first differences are Energy Potion's rich-image energy glyph syntax,
an untranslated SETUP_STRIKE_POWER.title status name (matching ID/amount 3/effect),
Nimble amount 2 Defend's deck description (5 versus 7 Block), and potion permissions/
identity during Headbutt's card selection. Only the last also changes the action
menu: CLI advertises Discard while the official interface does not. Its sparse
official potion summary also says can_use true; qualify current modal controls
rather than trusting that summary or silently dropping potion facts. Retain all
identities, permissions, modifier effects and raw bindings. Do not hide the real
5/7 difference through a text alias. Fix source formatting/localization/display
contexts and qualify actual effects/current owner permissions with targeted tests.
Use the saved first differences as regressions; later diverged worlds cannot be
realigned into matched evidence. The counts are not a compatibility percentage.
Keep all prior source versions and results, update the ordered backlog, and run
short checks autonomously. A replacement long comparison needs its own frozen
qualified tuple; do not repeat the completed v10 run or start training automatically.
See docs/native-star-cost-canary-result.md and the current backlog.

The owner authorized all four source repairs and targeted tests. CLI v52 uses
native visible reward text, virtual power Title dispatch and actual dynamic
preview refresh/cleanup for current copies and detached upgrades. Native effect
fixtures verify Nimble 2 Defend 7/upgraded 10, Sharp 3 Strike 9 (enemy 40 to 31) and
Setup Strike title/amount 3. Connector v22 preserves legitimate global belt actions
under known combat selectors, exact accepted deferred-discard identity, current
permissions and the card answer needed to drain that queue. All 183 Host tests pass.

V38's 57/77/118 matched controls pass (140.76/141.88/237.06 seconds); keep their
independent verifications. Its potion control then fails native strict decoding
because context and global belt each register the same bottle. No official game
starts. Saved-only review verifies 108 acknowledgements/109 inputs with a pending
last choice. Preserve the forced stop 143, both markers, all journals and the
negative tuple; it is not clean PPO or a completion to overwrite.

Worker v23/atomic-selection v6 skip only the exact owned context operands which the
global belt registers, keeping their sparse inspectable context and inventory.
Include the player-targeted AnyTime case. All 20 strict Node tests pass; the native
Headbutt/potion queued-discard/answer/removal fixture passes in 6.47 seconds with
clean shutdown and zero app copies/updates. Final proposed shared environment v39
retains CLI v52, connector v22, converter v14/layout v11; never alter the pinned v38 tuple.
The v39 saved-only audit passes 5,889 observations/20 envelopes/11,782 frozen
probes with 14,753 protected prior files exact. The owner explicitly authorized
one isolated replay of the known case from its earlier fully verified clean
parent. Preserve its later interrupted attempt. Use the single replay for the
scripted discard/answer/effect regression; a separate unchanged-policy control
uses fresh world 415, not another known-case replay. Preserve both original
full states/all Adam; no training, promotion, controller or automatic follow-up.
See docs/native-modal-display-repair.md and the current backlog.

The current v39 reward/title controls pass 57/77 choices per host and independently
verify 114/154 deliveries. The single owner-authorized potion replay passes all
112 inputs, exact queued discard/card answer/removal, and clean shutdown; all
109 frozen-prefix choices independently recompute. Do not replay it again.

The v39 modified-card control is now interrupted: native 118 choices, official 82
acknowledged choices, first difference at 67 (new floor with old Wood Carvings
controls after map travel; native Unrest Site). All 200 acknowledged choices and
receipts reconstruct in 23.65 seconds. The native 118-input trace matches the
earlier clean v38 trace exactly. Natural official shutdown fails; preserve the
active case/plan markers and blocked shared app. No fresh control 415 or main runs.

Separate patch sts2-connector-v0.111.0-map-settling-v23.patch / connector candidate
v24 suppresses mutation and atomic advancement while NMapScreen.IsTraveling spans
old-room exit/new-room entry. Seven new Host tests pass (190 total), and both
canonical builds reproduce; the guard is not live-qualified yet. Preserve failed
v23 SourceLink-origin binary mismatch and all prior tuples.

Read-only stopped-worker-inspection-v1 verifies all 435 official files plus the
frozen archive/account profile, no running game, and exactly five known backed-up
connector/settings additions. No reset was performed. A checked restoration
procedure is prepared; the agent has asked the owner to approve that reset and
one longer replacement diagnostic. Do not apply while the reply is pending.
The earlier approval covered the potion case only. Preserve both original full
players/all Adam. Continue independent short checks; see the current backlog and
docs/native-modal-display-repair.md. No main plan is frozen or launched.

The owner has now explicitly approved inspected worker restoration and preparation
of one longer replacement diagnostic. The checked reset completes in 13.47 seconds
on the same app inode, removing only five backed-up additions and restoring the
original inventory/mode. All failed case/plan files and markers remain exact.
Do not request that approval again or replay the earlier potion case again.

The new separately frozen tuple is CLI52 / official candidate24 / worker23 /
shared environment40. native_flow_{inputs,audit,live,session,verification}_v12 and
modal-panel-session-v1.py implement ten-minute matched pairs with a 45-second
shutdown reserve, startup refusal when insufficient time remains, and strict
physical-reset checks before any independent next case. Ten operational tests pass.
The v40 saved audit passes 5,889 observations/20 envelopes/11,782 frozen probes
in 164.46 seconds, preserving 15,721 prior files and both full original models/Adam.

Owner launch is scripts/compare-selection-flows-v13.sh, about 20–30 minutes, with
a 90-minute outer cap including separate checks and verification. It runs four
targeted controls under one tuple, uses the owner's approved p3/world411 replacement
and fresh p3/world415, and never repeats p3/world412's scripted potion replay.
Four-case preflight passes with zero games; the panel workspace remains absent.
Leave this long stage for the owner. Completed controls are reused. A clean-reset
delivery gap may be recorded before the next planned independent case; an unverified
worker or interrupted case stops without retry. Storage includes the fixed app.
No broader main canary, training, promotion or automatic next stage is launched.
Older v12/v11 wrappers and unfrozen canary-v2 are not the current owner command.

Final static checking found the frozen v12 clock-patching tests refer to a real
imported module attribute that strict mypy does not implicitly re-export. mypy.ini
mirrors the strict pyproject settings for src and tests, with Python re-export
semantics enabled only for spireshift.native_flow_session_v12; no error codes or
implementation/test checks are disabled. Preserve these already pinned bytes.
Do not broaden that exact-version setting; use qualified string patch targets and
run type checks on tests as well as source before freezing new versions. The
existing .ruff.toml exception is unchanged.

The owner subsequently ran v13. Its first reward control passes 57/57 complete
input/action pairs with exact app/profile/archive reset. Independent verification
reconstructs all 114 decisions. The parent coordinator then stops on KeyError
`evidence`: the real verification contract has no evidence map. This is a metadata
consumer failure, not another game failure. Preserve the parent report/active
marker and all first-case evidence; the other three cases never started.

Coordinator v2 uses the real verifier schema, source-report identity, exact verifier
hash and per-host counts, plus the successful uncapped resource receipt and source
report's transitive evidence. Its separate ledger pins the stopped parent and uses
the same original four control recipes/launches/seeds/source tuple v40. Do not
change or replay those recipes to repair bookkeeping. Fourteen new tests exercise
saved-only adoption, complete continuation, no replay and failure rejection.
Actual saved-only adoption records one complete 57-choice unit, zero new games,
zero optimizer updates, and three unstarted cases; all 15,721 protected files and
both original full players/all Adam are unchanged. The current owner command is
scripts/compare-selection-flows-v14.sh, about 15–25 minutes for the remaining
three pairs, under the unchanged 90-minute outer cap. V13 is historical.
Do not clear the old marker or rerun completed/uncertain cases. The three remaining
cases include the already approved p3/world411 replacement and fresh p3/world415;
no additional p3/world412 replay is authorized. No gameplay runtime or rules changed.
Run exact-file repository checks before owner continuation. Leave this long stage
to the owner; assess results before broader qualification or any new learning.
See docs/native-modal-display-repair.md and docs/evidence/native-modal-coordination-v2.json.

The owner completed v14: all four controls finish and reset cleanly, with no cap.
Reward/status/modifier controls match all 57/77/118 choices per host and their 504
deliveries independently verify. The fourth control diverges after 47 matching
choices: Continue opens the map, then a global potion discard reopens the CLI's
background RewardsSet and its skipped 11 Gold; the official map stays open. Native
completes 112 choices; official later submits End Turn during its 56th input but
never gets a ready successor (55 completed acknowledgements, round 2/enemy phase).
Preserve the completed blocked result and world415; never retry that uncertain
action/seed. Do not realign later divergent traces or infer that the map fix also
repairs the separate enemy-phase stall.

CLI v54 adds exact reward/map presentation ownership and stale background-reward
action rejection. The native synchronizer still owns rewards, effects and skips;
new/nested owners remain selectable. The independent duplicate builds reproduce
with the original game assembly unchanged. Eight executable C# ownership checks
and four isolated native fixtures pass (old and repaired discard/AnyTime use,
actual Fruit Juice HP effect, unchanged Gold, stale-action rejection). Both native
workers close cleanly; no official game, full run, training or app copy is started.
Preserve the failed v53 fingerprint-tool launch and unqualified preparation files;
the final build uses the existing tool-only Major roll-forward, never a changed
native game runtime. The prototype launch-v1 points to an old recipe and is not
the current launch receipt; preserve it without use. Current child launches are v2.

Shared environment41 binds CLI54 / official24 / worker23 / converter14 / layout11.
The two bounded saved audits pass 5,889 old plus 676 new frames, reusing the 20
artificial envelopes in each and making 13,172 frozen-policy probes. All 16,903
protected prior files and both full original players/all Adam stay exact. The
next finite panel uses three explicitly declared clean completed-case regressions
under the new source, and fresh p3/world416 for the stopped selector case. This
is not a retry of world415 or another scripted p3/world412 replay. Earlier v40
passes remain scoped to v40 until new-source checks complete. Use coordinator v3,
the source-pinned four-control plan, cached exact repository checks and one shared
app. The next owner command is scripts/compare-selection-flows-v15.sh, about
15–25 minutes with the unchanged per-case reserves and 90-minute outer cap.
Leave this long comparison to the owner. Assess the panel and any enemy-phase
failure before broader qualification or new learning. No promotion, controller,
training or automatic next stage follows. See docs/native-reward-map-owner.md.

The owner completed v15 on 2026-11-02. All four source-matched controls pass:
57/77/118/112 matching choices per host, 364 matched decision pairs and 728
independently verified deliveries. All eight starts reach their declared targets
and restore cleanly. Outer wall time is 932.78 seconds, CPU time 390.75 seconds,
peak RAM 988,168,192 bytes; no resource cap, optimizer update or app copy occurs.
Both original full players/all Adam and the earlier negative results remain exact.
Saved-only assessment rechecks 337 source and 1,510 evidence files, every child
identity/verifier/count and uncapped verification receipt in 18.05 seconds, with
no new games. Preserve this completed pass; do not rerun the v15 panel.

This qualifies the four declared prefixes under CLI54 / official24 / worker23 /
converter14 / layout11 / shared environment41. It does not grant broader live
qualification, training, promotion or adaptive readiness. Fresh world416 reaches
112 choices per host without reproducing world415's enemy-phase stop; its old
cause remains unresolved and the uncertain action/seed is never retried. Next
prepare a separately frozen finite broader compatibility proposal under this
unchanged tuple, preserving current passes and checking representative decisions,
effects, ending controls and new batch/resume gate bindings. No new broader panel
or next owner command is frozen yet; no collection starts automatically. Keep the
subsequent card-zone/exhaustion actor audit, varied fitting-only lessons and
separate interference test in order. See docs/native-reward-map-owner.md and
docs/evidence/native-reward-map-panel-result-v1.json.

The owner authorized preparation and short checks for the broader same-build
canary on 2026-11-02. The separately frozen plan uses fresh canonical worlds
417/418 with both originals: four paired prefixes, up to 128 choices per host
or an actually observed ending. CLI54 / official24 / worker23 / converter14 /
layout11 / shared environment41, both complete players/all Adam and every
qualified v15 file remain unchanged. The existing frozen v12 execution and
per-choice reconstruction paths are reused; the new coordinator only checks
the plan, preserves source/attempt evidence and reports observed coverage.

All 22 focused regressions, strict types/lint/format and the wrapper syntax check
pass. Final-source preflight passes in 10.19 seconds; a separate 1.05-second check
consumes all 728 unchanged v15 deliveries through the new validation/coverage
code. It sees nine decision families and no endings, never inventing terminal
coverage. No short-check game or optimizer update occurs. Final exact repository
check evidence is recorded separately after these files are frozen at
artifacts/native-broader-compatibility/preparation-v1/final-handoff-v1.json.

The next owner command is scripts/compare-broader-compatibility-v1.sh, expected
20–35 minutes. It includes exact-file repository checks, four serial pairs with
ten minutes each, independently reconstructed raw choices/receipts and a 90-minute
outer cap accounting for the shared app. Completed units resume only after a
declared clean pause; uncertain delivery/worker shutdown preserves markers and
stops without replay. The coordinator also refuses an open game before creating
its marker. Both long-run workspaces remain unstarted. Do not launch this stage
automatically. A pass qualifies only observed current-checkpoint prefixes and
endings; missing families/endings and the final uncaptured successor are not
qualified. Assess its coverage and failures before any broader gate admission,
new learning, promotion or adaptive controller. See docs/native-reward-map-owner.md
and docs/evidence/native-broader-compatibility-v1.json. Historical v15 is complete.

The owner completed the broader v1 panel on 2026-11-02: all four pairs/eight
starts, 999.55 outer wall seconds / 393.46 CPU seconds, no resource cap. Both
player-3 pairs match all 128 choices per host. Player 2/world417 first differs
after 11 inputs (Happy Flower counter native 0 / official 3); world418 first
differs after 112 inputs (rest option roles, enabled and exit field names), with
complete menu keys equal at each first difference. All eight workers shut down
and reset cleanly. Preserve the completed blocked result and both players/all
Adam; this is not a Steam update, a bookkeeping cap or a playing-strength test.

Player 2/world417 has 72 acknowledged official deliveries and a rejected 73rd
Play Evil Eye: receipt not_delivered / stale_snapshot. The only non-transport
change in its returned snapshot is Happy Flower counter 3 to 0. The old generic
uncertain-delivery message is not evidence that the play executed. Still never
retry that historical action/seed, realign later divergent states or use the
partial game as ordinary PPO. Inspect counter semantics/settling; do not silently
alias 0 with 3 or attribute it to world415's separate enemy-phase stop.

The coordinator skipped batch reconstruction because one host was blocked; retain
its original raw_choices_and_receipts_independently_reconstructed=false. A separate
24.86-second saved-only assessment now reconstructs all seven completed host paths
(852 choices), plus the exact 72 acknowledged choices of the stopped official
path in an explicitly declared diagnostic-only copy. The 73rd rejected choice is
excluded; original limit 128 and the blocked game remain unchanged. All 924
acknowledged deliveries verify, with zero new games/updates and all source/raw
hashes unchanged. No broader gate or matched ending is admitted.

Do not rerun compare-broader-compatibility-v1.sh. Next inspect/correct counter
projection and pre-choice settling, repair exact rest-site aliases and add
targeted saved/source/effect controls before a new frozen owner panel. No next
owner command or gameplay stage is frozen yet. The separate sibling branch
codex/card-zone-exhaustion-audit-v1 also completed the saved actor zone audit:
48 controlled pairs / 96 player comparisons and 20 tests pass, with no active
checkout changes or training. Preserve its scoped result rather than repeating
it or using synthetic probes as lessons. After compatibility qualifies, propose
varied fitting-only teaching and a separate interference test. See the current
guide and docs/evidence/native-broader-compatibility-result-v1.json.

The owner authorized the systematic comparison suite and both encountered repairs
on 2026-11-02. Keep game v0.111.0 / 41cef1ea, CLI54 and ordinary worker23 frozen.
Separate Connector25 / converter15 / layout12 / environment42 validate exact rest
aliases/authority and withhold all policy actions during native Happy Flower's
activation display. Neither counter values nor the energy rule are rewritten.
The 6,818-frame saved pass, 116 generated checks, 38 frozen-player probes, 199 host
tests and two reproducible host builds pass. Rest healing/proceed and Flower's
counter/energy cycle match both hosts including final successors; all ten actual
deliveries independently reconstruct. Five observed activation frames have no
actions. Historical premature authority and a corrupted receipt reject offline.
All 18,832 protected prior files and original full players/Adam remain exact.

Preserve development protection/save/loading/entry failures and their source
snapshots/markers. The two successful short controls are complete and need no
replay. Current owner command is scripts/compare-systematic-compatibility-v1.sh,
about 5–12 minutes: four finite save-based pairs for Smith/repeated rest and two
Flower cycles from different saved starting values, with a 30-minute outer cap.
The longer panel is unstarted; leave it owner-run. Earlier transitions-v1 wrapper
is scaffolding without the final semantic effect gate. This is privileged
fixture qualification, never ordinary PPO, full-game strength, all-interaction
proof, broader admission, promotion or adaptive readiness. Assess the owner
result before further compatibility or new learning. See the systematic guide,
its evidence and current backlog. The separate completed card-zone audit stands.

The owner completed the systematic compatibility panel on 2026-11-02 Toronto
(2026-11-03 UTC): all four paired fixtures pass in 226.86 seconds / 119.46 CPU
seconds, 1.235 GB peak RAM, no cap. Smith/repeated rest and both Happy Flower
counter starts agree, including every final successor. All 28 actual activation
snapshots have zero actions. Eight workers/app/profile/archive resets are clean.
A separate 17.13-second saved-only assessment reconstructs all 38 host deliveries
and 23 matched states, checks effects and all 18,832 protected prior files plus
the frozen archive/working app. Both full original players/Adam stay exact.
No new games, optimizer updates or app copies occur in assessment.

Preserve all completed owner/short/development/older failed reports. The v2 owner
assessment ledger scopes Smith to the observed derived public card_selection
root; do not infer that every source UI selection variant is qualified. The
first assessment ledger is retained; v2 corrects that coverage attribution without
replaying any game. Current systematic owner command is completed/historical
and needs no rerun. Next reconcile earlier valid evidence by source/saved replay,
then define one finite end-to-end/ending check for real remaining gaps; avoid
exhaustive content matrices. No next gameplay stage or owner command is frozen.
No broader admission, training, promotion, adaptive readiness or full-game strength
is granted by this privileged fixture pass. Preserve the completed sibling
card-zone audit; varied fitting-only teaching/interference follow compatibility.
See the current backlog, systematic comparison guide and owner-result evidence.

The owner authorized the next reconciliation/end-to-end item. The final saved
reconciliation-v2 independently verifies all 728 v15 deliveries under their
original source, then reproduces all 728 current inputs/menus and frozen-player
choices, RNG draws/log probabilities/values in 75.94 seconds. Original numerical
players/full Adam remain exact. Preserve v1 and its source snapshot; v2 follows
a strict JSON false/zero comparison guard correction. No new games/updates occur.
Seventy-two production Connector files are unchanged; changes are confined to
the qualified Flower guard/wiring, rest layout and versioned converter import.
Historical effects are not relabelled as newly executed current-host effects.

Current owner command is scripts/compare-e2e-endings-v1.sh, about 5–15 minutes,
two natural checkpoint-controlled pairs (p2/E2E601, p3/E2E602) on unchanged frozen
game/CLI54/Connector25/worker23/converter15/layout12/environment42. No fixture
save, forced outcome or policy change. Each host has 128 gameplay CPU seconds
and a 384-choice guard; each pair ten minutes; outer cap 40 minutes includes
repository checks and independent raw verification. Node/Python/uv bytes and host
release are pinned and drift refuses before gameplay. No update settings change.
The panel is prepared/unstarted; leave it owner-run. Do not repeat prior panels.

Require exact ordered playable inputs/menus, actual native ending Booleans,
matching full public persistent state/all reads and official native Continue to
summary with stable game facts. Retain full terminal graph/UI differences;
there is no actor action after termination. A limit without an ending remains
incomplete, never an inferred loss. Preserve uncertainty/interrupted markers
without retry; prove reset before another independent planned case. Assess the
result before admission. On the scoped pass, finish this finite compatibility
line and return to planned varied fitting-only teaching and interference work;
do not require exhaustive content combinations. No automatic training, promotion,
adaptive readiness or playing-strength claim follows. See the current backlog,
end-to-end guide and preparation evidence. The completed card-zone audit stands.

The owner completed natural-ending panel v1 on 2026-11-02 Toronto (2026-11-03
UTC): both natural pairs blocked, 718.77 outer wall seconds / 273.62 CPU seconds,
no outer cap. Native p2/p3 reach explicit losses in 262/125 choices. Official p2
has 235 acknowledged choices and stops at the unchanged 128-gameplay-CPU-second
guard with a nonterminal input; do not infer a loss or raise the budget. Official
p3 reaches an explicit loss in 125 choices, delivers Continue once and reaches
the native summary, but the verifier requires total_floor instead of the actual
floor_reached. Its saved summary shows score144/floor8/A8. All four host shutdowns
and both official app/profile/archive resets pass. Frozen game/production tuple
and both original full players/Adam remain unchanged.

Both first input differences are closed treasure chests, after 122/44 matching
inputs (zero-based). Native separate chest/relic/completed stages and owned
activate/select/close actions differ from official treasure_room open/activate;
relic fields and Skip availability also differ. The shipped NTreasureRoom enables
Skip after 2.5 seconds while the relic holder may already be actionable; the CLI
offers Skip immediately. P2 actually skips natively but takes Venerable Tea Set
officially. Do not hide this through label aliases, invented permissions, omitted
relic facts or later trace realignment. Repair and qualify the lifecycle/details/
stable Skip boundary before another finite ending check.

Saved-only owner-assessment-v1 independently reconstructs all 747 acknowledged
deliveries in 35.28 seconds: native387 and official360. Official paths use explicit
diagnostic acknowledged-prefix copies/recovery manifest with original reports,
384-choice recipes, ending failures and CPU guard preserved. No game replay or
update occurs. All 19,737 protected prior files plus original weights/full Adam,
frozen archive and restored working app verify. No workflow candidate or broader
admission is granted. The old summary collector stores its full proof only after
validation; its error leaves summary deck reads unretained. Do not fabricate that
missing proof or relabel the historical case as a pass.

Separate engine-natural-summary-v2 / engine-natural-checkpoint-v2 files correct
floor_reached and record full proof before validation. Sixteen new Node checks
pass; all 30 old/new ending tests, ten existing Python E2E guards and collector
syntax pass. Old source/recipe bytes are untouched. These prepared files are not
live-qualified or bound into a new owner command; production stays environment42.
Do not rerun compare-e2e-endings-v1.sh or either completed/stopped world. No next
long command is prepared. Next repair/target-test the chest contract, bind a new
frozen tuple and finite prospective panel if needed, then return to planned
fitting-only teaching/interference after compatibility. No automatic training,
promotion, adaptive controller, exhaustive matrix or playing-strength claim.
See the end-to-end guide, owner-result evidence and current backlog.

The owner authorized the chest lifecycle repair on 2026-11-03. The original
v0.111.0 / 41cef1ea game is unchanged. New CLI55 changes only TreasureState public
export; worker24 projects the actual closed/relic-choice/completed lifecycle,
complete title/keyword/card-preview facts and exact raw room/relic bindings.
Connector26 waits for both actual single-player Take/Skip controls and rechecks
Skip readiness when delivering Take. Mutation, potion and atomic authority stay
suppressed during that transition. Converter16 adds only the chest pre-sampling
guard; layout12 is unchanged. Shared environment43 binds this separate tuple.
Preserve every old source/config/report, original full player and all Adam.

Both short Take/Skip pairs pass: seven complete matched states including final
successors, ten independently reconstructed actual deliveries, selected Tungsten
Rod added once and Amethyst Aubergine declined without persistent/deck change.
All four host shutdowns and both official app/profile/archive resets pass.
Outer time 85.10 seconds / CPU 51.62 seconds, no cap, 1.041 GB peak RAM, 2.413 GB
peak retained storage including the one fixed app. No app copy or update occurs.
Saved qualification takes 22.36 seconds and rechecks all ten receipts/effects.
All 12 observed partial-choice snapshots have zero actions; both sampled relic
menus include actual Take and Skip. The precise Take-ready/Skip-unready live
variant is not observed in these two controls; its historical raw menu rejects
offline and all partial combinations are covered by compiled Host tests.
An intentionally corrupted receipt copy rejects; originals remain exact.

Preserve the initial native-only fixture-loader wiring failure and source
snapshot: zero policy actions, both workers clean, no official launch. The
corrected wiring passes on a different seed; do not replay either development
seed. All 209 Host tests pass, including ten new readiness cases, plus 24 chest
projection/authority regressions, four saved-summary bridge regressions and the
earlier 16 summary checks. The new collector binds actual floor_reached and
journals raw proof before validation; full verification binds it to the captured
ending facts and matching completion. The old E2E602 missing proof remains absent.

Saved current-source reconciliation independently verifies all 728 earlier actual
deliveries, then reproduces all 728 v16 inputs/menus and unchanged-player choices
under environment43 in 77.13 seconds. Every numerical weight/all Adam, draw,
probability and value remains exact under declared metadata imports. All 20,108
protected prior files, frozen archive and restored app verify. These saved
effects retain their historical source, not newly executed Connector26 identity.

Current owner command is scripts/compare-chest-endings-v1.sh, about 5–15 minutes:
two new natural pairs, p2/E2E603 and p3/E2E604, no fixture saves/forced outcomes,
128 gameplay CPU seconds and 384-choice guard per host, ten minutes per pair,
40-minute outer cap including exact-file repository checks/raw verification.
The plan is frozen/preflighted; its gameplay workspace is unstarted. Do not run
it automatically, repeat completed short controls, retry E2E601/E2E602 or raise
the budget. Assess ordered inputs/menus, genuine endings, full public game facts,
native Continue/summary proofs and clean reset before admission. On the scoped
pass finish compatibility and return to varied fitting-only teaching and the
separate interference check. No exhaustive matrix, automatic training, promotion,
adaptive controller or playing-strength claim. Final exact repository-check
evidence is recorded separately after source freeze. See the chest repair guide,
its evidence, current backlog and preserved earlier ending result.

The owner completed chest-ending panel v1 on 2026-11-03: E2E603/E2E604 both
blocked, 384.60 outer wall seconds / 162.34 CPU seconds, no outer cap and no
official gameplay CPU guard. Both native paths reach explicit losses (127/129
choices). Official p3 completes 129 choices, explicit loss, native Continue and
summary in 77.15 gameplay CPU seconds; full retained proof independently verifies.
This confirms the summary schema/proof correction. Neither pair reaches a chest;
it adds no chest coverage and does not revoke the earlier qualified Take/Skip
controls. All four host shutdowns and both official app/profile/archive resets
pass. Frozen game/tuple43 and both original full players/Adam stay exact.

Official p2 has 36 matching observed policy inputs and 36 acknowledged choices.
Its next map_select_ftue Got it! presentation is actually not_delivered /
stale_snapshot, not evidence of an executed click. Tutorial surface and bound
action remain identical while background context changes unknown to initializing
combat, reads/referents/hidden declarations change and Ornamental Fan's counter
goes from absent to visible 2. Do not normalize absence to zero, infer a counter
rule mismatch or attribute this to Happy Flower. Inspect tutorial/background
entry readiness before its first submit; never resubmit this historical action
or retry E2E603. Its generic uncertain-delivery message is not the receipt fact.

P3 first differs after 45 matching inputs (index 45): Aroma of Chaos native body
retains [rainbow freq=0.3 sat=0.8 val=1] while official rendered words omit that
formatting token; menu keys agree. The native formatter misses parameterized tags
with spaces/decimals. Repair supported rendering at source with systematic
saved/tag regressions; preserve image glyphs, amounts and unfamiliar facts. Do
not silently filter raw inputs, realign the later trace or relabel the completed
blocked pair as a pass. Standalone final ending facts compare equal, but the
earlier prefix mismatch still blocks ordered workflow qualification.

Separate owner-assessment-v1 rechecks all 421 acknowledged deliveries in 27.47
seconds: 385 across completed ending hosts and 36 in an explicitly declared
diagnostic stopped-prefix copy/recovery manifest. Original 384-choice recipes,
reports, raw captures and rejected receipt remain unchanged; partial data is not
ordinary PPO. All 20,108 protected prior files, full original weights/Adam, frozen
archive and restored app verify. No game replay, optimizer update or automatic
next stage occurs. Do not rerun compare-chest-endings-v1.sh or E2E603/E2E604.
Next qualify tutorial/combat-entry settling and parameterized native text rendering
using source/saved controls, then freeze any new finite proposal. No next long
command exists yet. The finite compatibility gate remains blocked; no training,
promotion, controller, exhaustive matrix or playing-strength claim follows. Keep
varied fitting-only teaching/interference next after compatibility. See the new
chest-ending result, evidence and current backlog.

Tutorial-entry/text repair is now source/saved qualified under the same original
game v0.111.0 / 41cef1ea. New adapters are CLI56 / Connector27 / worker24 /
converter16 / layout12 / environment44, ID
sha256:33b7174b6cc5d09fbfcbc303a93f04219c84fbfb8adf0d2a72cb1936cd6b51f0.
Native changes are confined to StripVisibleText's numeric rainbow parameters;
four of 6,902 English localization outputs change, with glyphs/amounts and
unfamiliar facts preserved. Connector changes only map-tutorial entry readiness,
snapshot wiring and its pre-click recheck. Wait for native player Phase.Play
through combat setup; do not wait for modal-disabled public IsPlayPhase. Open maps
retaining completed combat and other tutorials keep their own controls. Native
phase is diagnostic readiness only. No gameplay rule or counter is rewritten.

All 221 Host tests, 142 compiled actual-assembly readiness vectors and 18 text
edge cases pass. Saved E2E604's repaired Aroma body/full diagnostic public input
matches official exactly; E2E603's not_delivered/stale_snapshot and Ornamental
Fan's absent-to-visible-2 facts remain unchanged. Source/saved qualification takes
23.37 seconds, no game launch. Both adapter builds reproduce independently.
Preserve the initial development binary identity rejection and proposal; the
canonical fresh-clone artifact has its own reproduced configuration. No game or
action occurred in that failed build attempt. Saved reconciliation verifies all
728 old actual receipts and reproduces all 728 current inputs/menus/choices in
91.84 seconds under environment44. Full original weights/all Adam and all 20,380
protected prior files remain exact. Historical live effects retain old identity;
do not relabel either blocked pair or realign its divergent trace.

The new owner command is scripts/compare-entry-text-endings-v1.sh: two fresh
natural pairs p2/E2E605 and p3/E2E606, no fixture saves/forced outcomes. The same
128 gameplay CPU seconds, 384 choices, ten-minute pair and 40-minute outer limits,
exact playable inputs/menus, genuine endings, full public terminal facts, native
Continue/summary proof and clean shutdown/reset remain mandatory. Working app
reuse/fresh profiles remain fixed; derive workspace from the pinned recipe.
The long panel is unstarted and owner-run. Do not rerun any historical panel,
retry E2E603/E2E604 or repeat unchanged chest fixtures. Live qualification is still
pending; assess the new result before finishing finite compatibility and returning
to varied fitting-only teaching and separate interference. No automatic training,
promotion, controller, exhaustive matrix or playing-strength claim follows. See
docs/native-tutorial-entry-text-repair.md, its evidence and current backlog;
final exact checks are recorded separately after source freeze.

The owner completed the entry/text ending panel on 2026-11-03: E2E605 blocked,
E2E606 passes, one genuine matching pair. Overall qualification remains blocked.
Keep the original game/tuple44, all source/raw receipts and both original full
players/Adam unchanged. Owner wall 685.70 seconds / CPU 246.31, no outer cap;
official gameplay CPU 72.89/99.39, below 128. All four hosts reach explicit losses,
both official Continue/native summaries verify (score 144 / floor 8 / A8), all clean
shutdown/app/profile/archive resets pass. No app copies or optimizer updates.

Saved owner-assessment-v2 reconstructs all 620 deliveries in 44.70 seconds: 104 per
host p2, 206 per host p3. Both map tutorials dismiss once without rejection/retry;
all 45 settling captures have zero actions (24/21). No Aroma or chest occurs, so
do not expand their live coverage. All 20,569 protected prior files, frozen master,
idle app and original weights/full Adam verify. Preserve the first offline source
probe failure: it expected a direct await; native source uses branching choice
context. Its corrected saved-only assessment passes; no game was replayed.

P2 first differs at input 43 (44th input), only persistent/player/hp, after exact
Blood Potion use at choice 42. Both begin 54/80; native next HP 70, official next HP 54
with consumed bottle and enqueue-only delivery evidence. Input 44 still differs;
official reaches 70 at input 45. Only those two nonterminal inputs differ; menus,
all 104 selected indices and standalone final facts agree diagnostically. Never
realign those later states or relabel p2 as passing: two decisions used different
HP. The comparison's early-return false ending flag does not prove differing
final facts; separate endpoint equality is diagnostic without prefix admission.

Next repair actual noncombat potion-use effect completion readiness. The frozen
PotionModel removes the bottle before awaits and effect; its conditional VFX
path waits 0.5s, then Blood Potion heals 20% (16 here). NativeNonCombatPotions
acknowledges EnqueueManualUse, with pending tracking only for discards. Do not
change healing/game rules, force HP, use hardcoded waits or retry the old use.
Potion effects can pause for child choices: preserve those required selectors
while withholding unrelated decisions until actual completion. Start with
saved/source regressions and focused fresh transition controls, then freeze any
necessary finite proposal. No new long command is prepared by this assessment;
do not rerun compare-entry-text-endings-v1.sh or E2E605/E2E606. No automatic
training/promotion/controller follows. See docs/native-entry-text-ending-result.md,
its evidence and current backlog; varied fitting-only teaching/interference
remains next after the required finite compatibility qualification.

Action lifecycle audit and potion repair are now prepared under unchanged game
v0.111.0 / 41cef1ea and CLI56 / worker24 / converter16 / layout12. Final adapter
is Connector29, shared environment46 ID
sha256:c7f1b750a7c863a8aba837e8873f91b925de27ced45c8eaec41685e5b9675ace.
The compiler-derived audit covers all 17 original/26 current CLI gameplay commands,
control/support mutation sites and 144/156/157 original/previous/current Connector
NativeInputResult methods. Counts include routers/helpers; never call them proven
independent mechanics or exhaustive content interactions. Original CLI fallback
discard/forced recovery is attributed separately from our Connector defects.

Connector29 captures the actual action made by EnqueueManualUse, retaining initial
acceptance identity even if native IDs change on resumption. Ordinary successor
authority waits for native terminal action plus matching CompletionTask, never
bottle removal or a timer. Unknown, duplicate, foreign or faulted delivery remains
blocked. Discard pending state now uses terminal-task completion too. Required
native child/deferred choices retain exact owner proof; both ScreenEntityId and
HandEntityId are covered. Gate before atomic advancement and all policy/potion
bindings. Authenticated lifecycle provenance is diagnostic only, never policy input.

All 244 Host tests, ten Python and nine proof tests pass. Both fresh postcombat
paired effects match: use HP 54 to 70, discard HP 54 unchanged, seven states and ten
actual deliveries independently reconstructed. All unfinished-heal captures have
zero actions. Preserve the first use collector's exact-eight footer rejection;
its complete effect is independently verified from saved data under its original
declared stop, without replay. Preserve the first native-only discard script's
wrong-verb failure and verified retirement with original marker/profile. Corrected
discard uses a new world. Prototype Connector28, compile/inventory/seed development
attempts remain separate; only final Connector29 is qualified here. All 20,590
prior files, full original weights/Adam, frozen archive and idle app verify exact.
Saved reconciliation reproduces all 728 prior actual inputs/menus/choices in
78.87 seconds under environment46; historical live effects keep old provenance.

The audit explicitly leaves shop purchase/removal background-task completion as
an open source risk: those native tasks are started without a retained barrier.
Existing passed effects and future natural pairs do not qualify every delayed
pickup/hook. Keep generic UI-callback interaction limits explicit; source inventory
is not a live-effect pass. Broader admission/training remains ungranted until
remaining consequential qualification is assessed.

One new owner command is scripts/compare-action-lifecycle-endings-v1.sh: two fresh
natural pairs E2E607/E2E608 using original players, fixed leased app/fresh profiles,
128 gameplay CPU seconds and 384 choices per host, ten-minute pairs, 40-minute
outer cap. It is unstarted and owner-run. No old seed/action/fixture retry, forced
ending, automatic training, promotion or controller. Assess the result and explicit
open audit entries before fitting-only teaching/interference. See
docs/action-lifecycle-audit-and-potion-completion.md, its evidence and current
backlog. Final exact repository/preflight receipts are recorded separately after
source freeze.

The owner completed lifecycle ending panel E2E607/E2E608: both blocked, zero
qualified pairs. All four hosts reach natural losses; both official native
Continue/summaries and clean resets pass. Standalone terminal persistent state
and every public read match diagnostically. No cap causes this result: owner
wall 556.26 seconds / CPU 141.80; official gameplay CPU 27.99 / 36.73. Original
game and tuple46 stay unchanged. Do not rerun the completed launcher or worlds.

Saved-only assessment reconstructs all 486 acknowledged deliveries, 106 per host
p2 and 137 per host p3. Legal menus and selected candidates agree throughout.
P2 differs only at input 47: locked Self-Help Book option 2 has native enabled
false versus official true, repeated in surface/referent fields. Shipped button
release rejects its native lock; Connector actions already exclude it, but the
observation exports the generic button flag. P3 differs at inputs 31–36 only in
an unpurchased Pendulum's absent-versus-zero shop counter. Its owned relic facts
agree; the Connector shop reuses inventory-counter projection although the
merchant renders a plain relic icon. No gameplay-rule/counter mutation mismatch
is established. Preserve all prior blocked reports; later equality does not
admit differing policy inputs. Early-return false ending flags do not prove
different final facts.

Neither pair exercises repaired noncombat potion use; there are no such lifecycle
proof rows. P3 buys/discards/claims potions and uses Dexterity Potion in combat.
Earlier focused use/discard controls retain their scope, without new noncombat
use coverage or a demonstrated regression here. Source inventory of all delivery
paths does not qualify all public fact semantics/content interactions. The
separate shop background-task completion risk remains open.

All prior protected files, frozen archive, restored idle app and original full
weights/Adam verify. Preserve owner-assessment-v1's final report-format verifier
failure after all raw deliveries passed; corrected saved-only v2 uses the existing
format-specific build-report helper and changes no source evidence. No new game,
optimizer update or automatic next experiment. Next fix Connector event enabled
semantics and context-specific shop counter visibility with source/saved cases,
checking surfaces/referents/menus and owned-versus-offer contexts. Never globally
strip counters, patch old inputs or change game rules. No replacement long
command is prepared yet; compatibility/training/promotion/controller admission
remains blocked. Keep varied fitting-only teaching/interference after finite
qualification. See docs/native-action-lifecycle-ending-result.md, its evidence
and current backlog.

The event enablement, shop counter and awaited shop-task repairs are now source/
saved and short-live qualified under unchanged game v0.111.0 / 41cef1ea, CLI56 /
worker24 / converter16 / layout12. New official adapter is Connector30, source
97c14e74bcb82ed6c0f231dce5ee3ecc45a3a676, environment47 ID
sha256:ee1008673da84267143e3fdecb4bd54b3484b3e10b20dfebc4bb05e5cf16beed.
Event public enablement combines button state and native lock. Shop relics use
the merchant icon's facts; owned inventory retains actual visible counters,
including zero. No public field is silently filtered from old inputs or rules
rewritten. Compiled helpers resolve the seven saved differing inputs diagnostically.
All 486 old actual deliveries and 486 current policy replays verify in 62.47s;
old live blocked reports retain identity/status and do not become new passes.

All card/relic/potion purchase and concrete removal wrappers retain their actual
native Task<bool>, including awaited AfterItemPurchased hooks. Gate before
atomic advancement and all ordinary/potion bindings. Changed gold, stock or
acquired items do not imply completion. The managed active-screen update records
exact overlays opened in the task's causal execution context, even across awaits;
only the current ready owned child can proceed. Pre-existing/foreign/unready
screens cannot borrow identity. A closed child does not release an unfinished
final hook. Successful native false-result cancellation is complete; unknown,
faulted, task-canceled and foreign-run/inventory states remain blocked. Task
provenance is authenticated diagnostic data only, never policy input.

All 257 compiled Host tests, 36 compiled fact vectors, eight proof and four Python
script-safety tests pass. Compiler inventory has 158 Connector delivery methods,
one added tracker entry, no removed delivery paths. Counts include helpers and
routers, not independently proven mechanics. Both fresh paired removal controls
SH0P803/804 pass 12 actual deliveries/eight states: confirm spends 100 gold and
removes one card; cancel changes neither. Actual pending/owned-child/terminal
task proof, raw reconstruction and clean app/profile/archive resets verify.
Awaited shop-task completion risk is guarded; arbitrary unawaited native effects
and all content combinations are not universally qualified.

Preserve rejected SH0P801 and its exact launch sources; its child was interactive
but the diagnostic checker rejected an omitted nullable pending result. The
format fix still rejects premature boolean results. SH0P802 is unattempted;
no old control/world/action is retried. Preserve the first read-only qualification
driver's log collision; v2 uses separate case outputs and no new games. Preserve
development and build-preparation failures. The mistaken old build-recipe path
was caught before any game; original bytes were restored against their pinned
hash. All 21,031 protected prior files, original full weights/Adam, frozen archive
and idle app verify exact. Both adapter builds reproduce; portable checks pass.
Game private runtime stays fixed; no system dependency installation/update occurs.

One new owner command is scripts/compare-shop-endings-v1.sh, fresh natural pairs
E2E609/E2E610 with original players. Same fixed app/fresh profiles, 128 gameplay
CPU seconds, 384 choices, ten-minute pairs and 40-minute outer cap. No fixtures,
forced endings, historical retries or automatic follow-up. It is unstarted.
Exact playable inputs/menus, full terminal facts/reads, native summary, actual
shop-task proof chains and verified resets remain required; limits are incomplete.
Assess before broader admission and fitting-only teaching/interference. No
training, promotion, controller or strength claim. See
docs/native-shop-readiness-repair.md, its evidence and current backlog. Final exact repository and preflight
receipts are recorded after source freeze in the new preparation workspace.

The owner completed E2E609/E2E610 under tuple47: both blocked. All four hosts
reach genuine losses; both official native summaries and clean resets verify.
Owner wall 782.08 seconds / CPU 292.43; no outer cap. Official gameplay CPU
81.12 / 122.62 is below the unchanged 128-second guard. Original game and all
adapters/players remain exact. Do not rerun the completed launcher or worlds.

Saved owner-assessment-v1 independently reconstructs all 781 actual deliveries
in 56.03 seconds: p2 144 native/143 official, p3 247 per host. P2 first differs
at input 87 after the same combat Attack Potion use: generated Body Slam has
only its normal description in native, but Connector adds (Deals 0 damage).
Menus and all earlier facts match; original player chooses Body Slam versus
Skip with the same draw key. Subsequent play genuinely diverges; do not align
later suffixes or label each downstream difference a new mechanic defect.
Standalone terminal facts differ only at run floor, native 8/official 9.

Frozen shipped NChooseACardSelectionScreen explicitly calls NCard.UpdateVisuals
with PileType.None. CLI generated selection also uses None. Our Connector
NativeGeneratedCardChoice omits the argument to shared BuildCard, inheriting
Hand; native description OnTable/InCombat flags depend on that context. Next
repair the Connector rendering context, not CLI damage text or game math.
Audit all shared card-export calls against actual widgets and make contexts
explicit, with saved/source conditional-description cases rather than a
Body Slam name exception or description-field filtering.

P3 differs at only input 168: space versus native newline before Regal Pillow's
15-HP bonus. Both choose Rest, heal 8 to 47 HP and retain all 247 action indices
and matching standalone terminal persistent state/all reads. Native heal text
inserts the newline; CLI strips it, Connector cards normalize it but rest does
not. Standardize the visible-text convention without dropping words, numbers,
glyphs or ordered facts. Old blocked reports stay unchanged. Early-return false
ending flags do not by themselves prove different endpoint facts.

Two p3 natural card purchases at inputs 29/30 complete with valid native-task
proofs before divergence. No locked event, Pendulum offer or repaired noncombat
potion use occurs; prior focused controls retain their scope. All 21,031 prior
protected files, frozen archive, restored idle app and original numerical weights/
full Adam verify exact. Expanded assessment map pins 21,336 files. No game or
historical action replay, source repair, optimizer update or automatic next
experiment occurs in this assessment. No replacement long command exists yet.
Compatibility/training/promotion/controller admission remains blocked. See
docs/native-shop-ending-result.md, its evidence and current backlog; preserve
the finite finish line before fitting-only teaching/interference.

Connector31 now implements the card rendering and visible-text repairs in
new artifacts/native-card-rendering namespaces; old reports remain unchanged.
All 17 shared card-export calls require explicit display contexts. Eight visible
widget sites use actual NCard.DisplayingPile; missing widgets fail closed.
Combat hand/preview/catalog/public-pile callers bind their exact context. Legacy
description helper pile arguments are required too. No Body Slam name exception,
CLI math change or comparator description filter is introduced. One production
helper applies the CLI LF-to-space convention to card and rest descriptions,
preserving all other codepoints, quantities, order, unknowns and glyphs.

Game v0.111.0/41cef1ea, CLI56/worker24/converter16/layout12 and both original full
players/Adam remain exact. Tuple48 is sha256:4c445e402d31ceea743165d203b03c1b9b6744f1a6a8396a797bb4a412efbc81; source revision
4d0b95d38b0f8e0e0c273a7b4fa5fb7a0a0ad1ca. Connector builds reproduce; 265 Host tests,
portable checks, 17 compiled caller bindings and 112 native formatter vectors
pass. The latter use one new privileged managed source world, zero policy or
gameplay actions, isolated profile and pinned private runtime9.0.7. Keep source
and saved evidence distinct from official-app Live qualification and game effects.

Saved/source v3 reconstructs all 781 historical deliveries in 73.21s.
Repaired diagnostic inputs/choices match through player2 input87 and all 247
player3 choices. Player2's corrected choice is Body Slam on both hosts; leave
that diagnostic choice uncommitted and do not reuse either later old suffix as
a repaired ending. Player3's full terminal facts/reads match diagnostically.
There are 670 current diagnostic choices, 668 unchanged historical acknowledgements
and no game delivery. Preserve all 21,356 prior files and failed source/saved
probe attempts. The first saved reprojection omitted the separate surface-card
Read copy; v3 fixes that diagnostic without relaxing exact comparison.

One owner command scripts/compare-render-endings-v1.sh is prepared and unstarted.
Use fresh natural E2E611/E2E612, same fixed app with fresh profiles, 128 gameplay
CPU seconds, 384-choice guard, ten-minute pairs and 40-minute outer cap. Genuine
endings, exact playable inputs/menus/full terminal facts/reads, official native
summary, task proofs and verified resets remain necessary. Limits stay incomplete;
uncertain delivery is preserved without retry. Assess before broader admission
or fitting-only teaching/interference. No automatic training, promotion,
controller, strength claim or follow-up. See docs/native-card-rendering-repair.md,
its evidence and current backlog. Exact final repository/preflight receipts are
recorded separately after source freeze in the new preparation workspace.

The owner completed E2E611/E2E612 under tuple48: both natural workflow pairs
pass, with 166 and 126 matching decisions per host. All four runs reach genuine
losses (floors 9/7); both official Continue/native summaries and clean resets pass.
The owner uses 635.39 wall / 161.57 CPU seconds, without an outer cap. Official
gameplay CPU 41.30 / 30.91 stays below 128. Do not rerun the completed launcher,
worlds or historical controls.

Separate saved-only owner-assessment-v2 reconstructs all 584 actual deliveries
in 59.45s: all 292 paired playable inputs/menus and original-player
choices/draws/probabilities/values match, as do full terminal persistent state and
all public reads. Preserve the original candidate panel and earlier failures.
Terminal presentation graph differences remain listed under the unchanged contract;
headless ending facts and official Continue/summary controls differ, while all
ending facts/reads and actual official native summary proofs are mandatory.

Player 2 completes three purchases (Blood Potion, Shrug It Off, Havoc), and uses
Blood Potion in the shop. Its actual accepted native action 80 finishes successfully
with retained task proof and pending 0; both hosts heal 36 to 52 HP. This is new
natural noncombat potion-completion evidence, not merely changed inventory.
Player 3 completes one atomic selection. Generated powers and base Rest are reached,
but the specific Body Slam/Regal Pillow historical regressions are not. Prior
source/saved regressions remain exact, without replaying their old worlds.

The frozen game/CLI56/Connector31/worker24/converter16/layout12 and both original
numerical weights/full Adam are unchanged; all 21,356 prior files verify and the
expanded protection map pins 21,647 files. Frozen archive
and restored idle app verify. The first saved-audit helper import was one directory
too high; preserve its failure/active marker. The separate v2 corrects that read-only
checker path, with no game/profile/action replay or production repair.

The finite two-original-player natural-workflow milestone is verified in its
declared scope. Next bind assessed evidence to a new learner entry/start-resume
compatibility guard and prepare varied fitting-only teaching plus the separate
shared-policy-interference comparison. Reuse the completed sibling card-zone/
exhaustion audit; keep matched work, original/reference controls and prospective
world splits. Never use prior held-out plans, final evaluation worlds or these
completed compatibility worlds as fitting labels. Do not restart unchanged PPO
or expand qualification into exhaustive combinations. Changed/trained checkpoints
need their own scoped input/live checks; promotion/scaling still needs fresh
paired original/trained official evaluation under ADR 0006.

This assessment mints no training guard receipt, grants no broad live admission
and starts no learning, collection, promotion, adaptive controller or automatic
follow-up. No next long command is prepared. See docs/native-render-ending-result.md,
its evidence and current backlog. Normal losses prove environment workflow here,
not competent play, universal mechanics or improved full-game strength.

The owner authorized connecting the assessed tuple48 result to the learner guard,
then preparing a varied fitting curriculum and separate interference test. New
native_learner_guard/native_curriculum_* files leave all historical runners and
the frozen game/CLI56/Connector31/worker24/converter16/layout12 unchanged. The
new receipt binds exact original/imported full states and Adam, assessed current
live delivery, 292 complete paired inputs, frozen execution/runtime identities
and the fixed study. Only original curriculum collection and declared diagnostic
fitting on copies are admitted. Ordinary PPO, broad live admission, promotion,
scaling and adaptive controllers are not admitted. New checkpoints get recorded
checks and do not inherit live scope; fresh mode-specific canaries precede evaluation.

The main plan fixes eight fitting/four withheld new worlds before search. Public
outcome-blind round 2/late-novelty roots yield at most 16 fitting entries; source
worlds, not branches/entries, are independent. Four legal first-divergence teacher
proposals per fitting root use native remaining fights and strict existing local
win/resource-preserving HP comparison. Confirm selected improvements. Privileged
branch outcomes stay outside public student inputs and ordinary PPO. The quality
gate needs four independent fitting worlds, both source players, two strictly
improved worlds, two enemy compositions and three decks, clean source games and
all withheld roots. No withheld/final/canary world labels or best-epoch selection.

Reference and teacher copies for both originals each receive 64 updates/2,048
examples with matched world contributions and warm full Adam; critic/credit/score
and 128-CPU-second whole-run objective remain fixed. Freeze every final first.
The separate interference arm routes the same teacher final through original
noncombat and public taught-combat/nested ownership, with no extra fitting. It is
an experimental control, not a permanent restriction. Six changed-policy/mode
native/official genuine-ending canaries gate 32 withheld-fight and 128 fresh-game
attempts across 16 fresh worlds, two fixed initializers and four modes. Preserve
failure/cap/missing denominators and world-clustered uncertainty. No automatic
promotion or claim from all-zero wins.

Control-v3 on VTC905/906 passes in 128.45s: two natural
games/two declared teacher branches, 11 sealed units, actual pause/full-Adam resume,
16 updates on copies, missing-scope rejection and exact routing/RNG probes. Its
quality gate is relaxed for pipeline qualification and its finals/worlds never
enter main. Saved-only short-assessment-v1 reconstructs 339 actual deliveries
and exactly recomputes all 16 copied updates/full Adam in 65.63s, no games.
Those 16 diagnostic reconstruction steps are separately accounted; originals stay
at 5,658/6,045. All 21,669 prior files, frozen archive/runtime/SDK/current full CLI
inventory and idle app verify exact. Pin Python/NumPy/Node/uv/host/thread settings;
reject drift at start/resume rather than promising arbitrary patch immunity.

Preserve v1's pre-game guard source-map alias failure and exact source snapshot.
Preserve v2's 160-action natural source and active rejected unit: an inherited
candidate_before belonged to an older CLI despite candidate/build being updated.
The new guard pins the entire current verified CLI56 inventory to the current
build report before any work. It filters/rewrites no file and changes no game or
CLI byte. Preserve unattempted reserved worlds VTC901/902/904, preparation failure
sources and all old reports. Never retry uncertain/stopped controls.

One next owner command scripts/prepare-varied-teaching-v1.sh is frozen and
preflighted for collection only: 8 fitting/4 withheld worlds, about 10–25 minutes,
one 30-minute/3,600-CPU-second/4-GB session, with separate cached repository gate.
No main fitting, canary, evaluation or automatic follow-up starts from this
command. Clean sealed boundaries resume exactly; existing uncommitted units
block without clearing/replaying. Assess the teacher bank before later separately
selected phases. Main workspace/worlds remain unstarted. See
docs/native-varied-teaching.md, evidence and current backlog; final exact
repository and handoff receipts live in the new preparation workspace.

Final exact-source qualification supersedes the provisional control-v3 handoff:
repository type checking found four annotations/narrowing issues in the new unit
tests. No production learner/game code changed. Preserve the failed repository
receipt and exact provisional preparation backup. Control-v4 uses fresh VTC907/908
and passes in 111.51s, with 11 sealed units and 16 updates on disposable
copies. Saved-only short-assessment-v2 reconstructs all 361 deliveries and every
copied weight/full-Adam moment and counter in 57.84s. Both successful controls
therefore total 32 registered copy updates; their two saved-only mathematical
reconstructions total 32 additional separately accounted diagnostic steps.
Originals and main-study copies receive zero updates. Main recipe now pins exact
control-v4/source bundle and its final preflight guard; study-v1 remains unstarted.
The one owner command and collection-only stopping point remain unchanged.

The owner completed the main varied collection (study-v1 / config4bbaa639...)
in 652.76 wall / 561.22 CPU seconds, no outer cap. All 12 natural source games
are clean. Sixteen fitting/four withheld public roots produce 12 admitted lessons
from all eight fitting worlds, both source players, eight enemy compositions and
12 decks. Reference/teacher meaningful positions total 164/161. All 64 teacher
proposals were attempted (56 complete, eight capped), with three selected strict
improvements confirmed in declared isolated runs. Preserve all 79 attempts;
never rerun the collection or enlarge caps/search automatically.

Saved-only collection-assessment-v1 independently reconstructs all 6,738 actual
deliveries and 79 seals, original outcome-blind roots, proposed legal prefixes,
the selected confirmations and exact public bank. All eight caps (root05/root14
four candidates each) hit the declared remaining-fight round guard; their actual
receipt/prefix/shutdown evidence verifies and supplies no candidate labels. An
already complete original source plan may still be admitted at root14. Caps are
not new official/CLI discrepancies or completed teacher fights.

The gate passes with three improved independent worlds, but gains are only
1/1/5 HP in already-won floor2 fights, all sourced by player2 (VTF001/005/007).
No loss-to-win conversion or stronger full-game player is demonstrated. Do not
move the prospectively fixed quality bar or scale automatically. All 21,669 prior
protected files, frozen game/runtime/SDK/full CLI and original complete states/
Adam remain exact. Main fitting/canaries/evaluation stay unstarted; the audit
makes zero new games/updates. See docs/native-varied-teaching-collection-result.md,
its evidence and current backlog. Next is separately selected matched fitting on
four copies (64 updates each / 256 total), with exact warm-Adam resumption and
checkpoint-recorded guard checks. Freeze finals, then qualify each changed mode
with its own six official/native genuine-ending canaries before withheld/full-run
and separate same-final routing interference evaluation. No automatic next phase,
ordinary PPO, promotion, scaling or adaptive controller is authorized by this result.

The owner authorized preparing the main 256-update fitting comparison on four
copies, with the game and original full weights/Adam frozen. Keep the completed
study-v1 recipe, bank and all original core learning/verification files unchanged.
New native_fitting_session and fit-varied-teaching-v1 wrapper use a separate
operational launch receipt requiring the exact saved bank assessment, exact
source/runtime, old current-player guard and completed integration controls.
The launch manifest binds 28,855 prior files and its own code/tests. Ordinary
PPO, promotion, scaling, controller and automatic evaluation stay blocked.

Saved-bank short control passes in 143.28s: four disposable actors receive 16
matched updates, plus four updates on a resume fork. A fresh process restores
complete saved warm Adam; four separately counted numerical reconstruction steps
reproduce every weight/moment/counter. Critic weights stay fixed; reference and
teacher models differ, work/world draws match, checkpoint recorded checks pass,
and original full states/frozen inputs remain exact. These 20 diagnostic updates
and four reconstruction steps are excluded from main. Never substitute these
short finals for original main initializers.

One owner command scripts/fit-varied-teaching-v1.sh runs fitting only: four copies,
64 updates/2,048 draws each (256/8,192 total), equal world contributions, exact
warm-Adam continuation and recorded checks after each checkpoint. Original Adam
steps stay 5658/6045; fitted copies must end at 5722/6109. Seal two imports,
64 epochs and the all-finals barrier (67 units); fixed epoch16, no best-epoch or
withheld selection. Clean boundaries resume with the same command; unfinished
updates preserve evidence and block replay. Launch snapshots/session receipts
are separately retained and included in output caps.

Allow about 6–12 minutes; one 30-minute/3600-CPU-second/4-GB fitting session plus
cached repository check. It starts no game or evaluation and stops after all
four finals freeze. Main fitting remains unstarted at preparation handoff.
Assess the owner result before six changed-final/mode official/native natural
ending canaries, withheld/fresh full-game tests and the separate same-final
routing interference comparison. See docs/native-varied-fitting-comparison.md,
its evidence and current backlog. Final repository/preflight/handoff receipts
live under artifacts/native-varied-fitting/preparation-v1.

The owner completed the four-copy fitting stage: all fixed 256 updates and
four epoch16 finals are sealed, frozen_finals_id dbcb5980..., report b5c79b14...,
same study4bbaa639/bank0099b16/environment48. The owner used 563.02 wall/508.20
CPU seconds, no outer cap, about 331 MB peak RAM/119 MB output. Do not rerun fitting.

Saved-only owner-assessment-v1 independently reconstructs all 256 numerical
updates, every saved weight and complete Adam moment/counter, work record and
recorded receipt exactly. Four bounded independent copy audits use disposable
paths; their 256 mathematical reconstruction steps are separately counted, not
new registered study updates. All 67 sealed units and 66 unique checkpoint
regressions pass. Work is 64 updates/2048 draws per copy, 256 draws per fitting
world per copy; critic unchanged. Original Adam 5658/6045 stays exact; copies end
5722/6109. All original weights, frozen engine/CLI/connector/runtime and protected
inputs remain exact. Fixed final epoch16 preceded all external evaluation.

Own-plan mean label probability rises from 43–46% to 79–82%. On the three specific
changed fitting menus, teacher copies prefer 3/3 (p2) and 2/3 (p3) teacher actions;
reference clones 0/3 each, originals 0/3 and 1/3. This is seen-menu fitting evidence,
not fresh gameplay, generalization or victory. The p3 third target remains
unlearned by this greedy diagnostic; do not add epochs or select another final.

Next prepare the six declared fresh native/official natural-ending canaries,
binding each reference/teacher/routed mode to these exact frozen full states/Adam
and unchanged sources/build. No changed policy has live qualification yet; no
canary/evaluation workspace is started by this assessment. Only successful exact
natural endings/summaries/resets gate separately selected withheld and fresh
full-game / same-final interference tests. No automatic next run, ordinary PPO,
promotion, scaling or controller. See docs/native-varied-fitting-result.md, its
evidence and current backlog; keep GitHub work items aligned with this result.

The owner authorized preparing six fresh native/official canary pairs for the
exact independently assessed dbcb5980… finals, preserving the game and all
original/fitted weights and full Adam. New native_final_canary_session plus
compare-varied-finals-v1 wrapper use a separate operational attempt-scope
receipt; all historical study/fitting/runner/converter files remain unchanged.
Pin source/test hashes, fitting assessment/resource/report, all six full state
and Adam bindings, predeclared VTV201–206 cases and 29,714 prior files.
This attempt scope grants no inherited live admission or ordinary PPO permission.

Saved-mode control passes in 194.82s: six exact factories × 292 paired saved menus,
1,752 comparisons, matching complete input/action/feature/distribution/value,
ownership/navigation/RNG outputs with the required actor. These are explicitly
counterfactual chooser inferences on old recorded states, not new-policy actual
deliveries or game trajectories. Zero worlds/games/updates; no live scope is
granted. Current canary/evaluation workspaces remain unstarted at handoff.

One owner command scripts/compare-varied-finals-v1.sh runs the six fixed pairs
only, about 25–45 minutes. A separate 70-minute/7200-CPU-second/4-GB outer session
allows the whole panel without changing ten-minute pair boundaries or 128
gameplay CPU seconds/384 choices per host. The original study's default session
metadata remains immutable; the operational launcher passes this full-panel
deadline explicitly. Source/workspace/output caps bind the actual canary journal
and launch receipts; fixed game/runtime/app and prior bank/fitting are read-only
inputs. One managed app is reused serially, with fresh isolated profiles.

Require exact playable inputs/menus/receipts, genuine matching natural endings,
full terminal facts/persistent state/all reads, official native summary and clean
resets. Presentation-only terminal graph differences stay retained, never realign
divergent suffixes. Limits remain incomplete. Clean sealed prefixes resume with
the same command; unfinished/changed cases preserve markers/profiles and block
automatic replay. All six named mode/case pairs must pass. No forced outcomes,
new fitting, heldout/fresh evaluation, PPO, promotion, scaling or controller follows.
Assess the owner canary result before separately selected evaluation. Do not
rerun the completed fitting stage. See docs/native-varied-final-canaries.md,
its evidence, current backlog and new preparation receipts; update GitHub with
this prepared/unstarted status and preserve earlier histories.

The owner completed the exact-final canary attempt: VTV201/202 reference and
VTV203 player-2 teacher pairs pass with genuine matching losses, native ending
facts/all public reads, official summaries and clean resets. VTV204 player-3
teacher native reaches a loss after 261 choices, but official stops after 239
delivered choices at 128.184731264 host CPU seconds, before a genuine ending.
VTV205/206 routed modes remain unattempted. Preserve the six-pair denominator:
three passes, one incomplete, two missing. No global qualification is granted.

Saved-only owner-assessment-v1 independently reconstructs all 1,448 actual
deliveries, the three seals and all shop/atomic/reward/summary proofs. The
incomplete fourth pair matches 239 delivered choices and 240 offered menus,
including its last unsubmitted nonterminal menu. A diagnostic-only prefix
verifier retains the raw checks, explicitly requires this exact CPU abort and
grants no ending scope; the frozen full-ending verifier remains unchanged.
No observed common-prefix public-input/menu/choice/delivery divergence is found.
Do not impute the native suffix/ending to the official host.

The outer cap is null (1432.02 wall / 550.05 CPU seconds). The per-host official
guard counts Python coordinator delta plus Godot and SDK Node CPU from before
game launch; it is not inference-only time. Component CPU attribution was not
retained, so the cause within those processes is unmeasured. The SDK message
"No checkpoint choice supplied" follows intentional guard abort, not a missing
legal action. Keep the 128-second objective; next propose a separately frozen
saved/source CPU-accounting and official-runner performance investigation.

All 29,714 protected prior files, exact dbcb5980... finals and complete Adam,
original full weights/Adam and tuple48 game/runtime remain unchanged. Native
hosts shut down cleanly, official checks pass and the app restores its baseline.
Preserve VTV204's active marker and raw evidence; the launcher correctly blocks
automatic replay. Do not retry its world, clear the marker, raise the compute
constraint, refit, skip the failed denominator or rerun the old command. Zero
new games/updates in assessment; no withheld/full-game/interference evaluation,
ordinary PPO, promotion, scaling, controller or next experiment is automatic.
See docs/native-varied-final-canary-result.md, its evidence and the backlog;
supersede the prepared/unstarted handoff on GitHub while retaining history.

## Information boundary

Agents may consume only public player-observable state. Privileged engine state may be recorded
only in separately marked debugging fields and must never reach training or evaluation inputs
unless the experiment is explicitly labeled privileged.

## Repository safety

- Do not commit game binaries, assemblies, assets, save files, API keys, or raw proprietary data.
- Keep generated trajectories and model artifacts outside Git under `artifacts/`.
- Preserve patch identifiers, seeds, model versions, objective versions, and compute measurements
  in every run record.
- Count crashes and unsupported decisions; never silently discard them from evaluation.

## Working apps and storage

New recipes that launch the shipped app must explicitly bind the versioned working-app reuse
policy. Reuse one fixed app for the serial worker, with a fresh profile and immutable evidence
per attempt. Managed-engine simulations already share frozen inputs and do not need an app copy
per game. Preserve old recipes for historical reproduction; do not use their retention defaults
for new work.

For native worker v9 and later, share the verified immutable local support-code cache as well
as the frozen game/runtime/SDK. Warm worker startup must not clone or patch a Git checkout.
Keep mutable sessions, ledgers, navigation state and profiles separate. Preserve interrupted
or changed caches for inspection; never clear them automatically. See
`docs/native-a8-worker-potion-repairs.md`. Native queued actions need exact acceptance and
completion checks; an unchanged belt while gathering a card choice is not itself a failure.

Runner wrappers must read the case workspace from the pinned recipe and use that same path for
cached results, resource tracking and outputs. Do not duplicate a versioned workspace literal
in the wrapper. Keep historical output locations and measurements unchanged when repairing a
path mismatch, and record any excluded storage explicitly.

Keep the frozen master unchanged, hold the worker lock through child shutdown and verified reset,
and enforce the managed-pool storage cap. Interrupted or changed workers must stop for inspection;
do not silently clear their marker or create replacement copies on retry. Preserve logs, saves,
receipts and unexpected files. Parallel reuse and explicit worker repair/retirement remain
separately qualified follow-ups. See `docs/working-app-reuse.md` and #147/#146.

## Verification

New large native collectors must retain sealed paths and compact outcomes, not every
episode's decision history. Verify compressed worker journals as ordered streams, keeping
at most the current episode and a bounded record window. Use the separately versioned
streaming implementation; preserve historical pinned collectors/auditors for reproduction.
An interrupted worker's verified completed prefix is diagnostic evidence only, under an
explicit recovery manifest with the original interrupted/missing attempts still counted.
Never clear its marker, reuse its profile or replay an uncertain seed to complete a panel.

Run `uv run spireshift check` before committing. Tests that enforce the objective contract and
public-state boundary are release blocking.

## Execution boundary

The user authorizes Codex to run short builds, audits, tests and jobs autonomously. Leave tasks
expected to take five minutes or more for the user to launch and monitor. Estimate from saved
timings and use explicit resource caps; do not start or monitor long experiments. Preserve the
current run's evidence, and provide one specific next command when a long stage is needed.
