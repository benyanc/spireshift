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
- agent, model, search, representation-encoder, and vectorizer versions;
- legal actions and selected action;
- compute tier and measured cost;
- teacher search visits, independent evaluation samples, and their disjoint seed domains when
  learned targets are involved;
- state hashes;
- terminal result;
- crashes and unsupported decisions.

Seed sets and the benchmark denominator are frozen before workers launch. A seed remains in the
denominator when its retries end in a crash, timeout, malformed artifact, or failed replay. Reports
must expose completion rate, failed attempts, worker crashes, and recovered runs alongside victory
rate. Completed runs count only after their immutable records pass exact transition replay. The
[parallel rollout protocol](rollout-infrastructure.md) implements these rules for the mock backend.

## Splits

Training and evaluation are split by complete run and seed. Adjacent decisions from one run may not
be randomly divided across train and test sets.

Every dataset and checkpoint records the content-addressed split-manifest and dataset-index IDs.
Encounter instances inherit their complete run's partition. Training fits on train runs, model and
threshold selection use validation runs, and final estimates use test runs after choices are frozen.
The [data-split audit](data-splits.md) must pass before records enter a model or reported benchmark.

## Base-model readiness

Adaptive allocation experiments remain blocked until pilot-derived readiness thresholds are frozen
and the base policy/value system passes them on held-out data.
