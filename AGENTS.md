# SpireShift engineering instructions

## Binding objective

SpireShift maximizes terminal full-run victory probability subject to a fixed whole-run
computation budget. Act completion, floor reached, HP, and resource preservation are auxiliary
targets and diagnostics. They must never silently replace terminal victory as the primary
optimization or headline evaluation metric.

Every experiment must load a versioned `ObjectiveSpec`. Changes to the primary objective,
terminal condition, or compute constraint require an architecture decision record and explicit
test updates.

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
