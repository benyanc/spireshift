# SpireShift engineering instructions

## Binding objective

SpireShift maximizes terminal full-run victory probability subject to a fixed whole-run
computation budget. Act completion, floor reached, HP, and resource preservation are auxiliary
targets and diagnostics. They must never silently replace terminal victory as the primary
optimization or headline evaluation metric.

Every experiment must load a versioned `ObjectiveSpec`. Changes to the primary objective,
terminal condition, or compute constraint require an architecture decision record and explicit
test updates.

## Foundation before adaptive search

Do not train or promote an adaptive budget controller until the base policy/value system passes
the frozen readiness evaluation. The readiness evaluation must cover policy-only performance,
value regret, calibration, confident catastrophic errors, held-out generalization, and whether
model-guided search improves at equal compute.

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

## Verification

Run `uv run spireshift check` before committing. Tests that enforce the objective contract and
public-state boundary are release blocking.
