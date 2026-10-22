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
