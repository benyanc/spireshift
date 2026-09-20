# Benchmark protocol

## Primary comparison

Compare terminal victory at equal whole-run compute budgets using paired seeds.

Required systems eventually include heuristic, policy-only, PPO, fixed MCTS, fixed learned PUCT,
heuristic adaptive PUCT, learned adaptive PUCT, and episode-budget PUCT.

## Required metadata

Every run records:

- the content-addressed patch manifest ID and complete ruleset identity, including engine, adapter,
  mechanics, interface schemas, and information policy;
- objective and patch identifiers;
- seed and character/difficulty configuration;
- agent, model, and search versions;
- legal actions and selected action;
- compute tier and measured cost;
- state hashes;
- terminal result;
- crashes and unsupported decisions.

## Splits

Training and evaluation are split by complete run and seed. Adjacent decisions from one run may not
be randomly divided across train and test sets.

## Base-model readiness

Adaptive allocation experiments remain blocked until pilot-derived readiness thresholds are frozen
and the base policy/value system passes them on held-out data.
