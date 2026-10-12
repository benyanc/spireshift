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

Use complete-run outcomes to improve the unified policy across every decision family, then test
the frozen player on independent seeds at equal compute. Repeatable auxiliary progress is a
development milestone; genuine full wins remain the goal. More games alone do not establish a
useful workflow. Revise a stalled method using evidence, and keep the readiness gate before
adaptive thinking. See ADR 0003 and the ordered backlog.

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

Run `uv run spireshift check` before committing. Tests that enforce the objective contract and
public-state boundary are release blocking.

## Execution boundary

The user authorizes Codex to run short builds, audits, tests and jobs autonomously. Leave tasks
expected to take five minutes or more for the user to launch and monitor. Estimate from saved
timings and use explicit resource caps; do not start or monitor long experiments. Preserve the
current run's evidence, and provide one specific next command when a long stage is needed.
