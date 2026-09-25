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

Every headline experiment also requires a verified `experiment-resources-v1` sidecar containing the
hardware identity, worker count, trajectories, simulations, transitions, CPU/GPU hours, wall time,
throughput, peak memory and storage, configured rates, and estimated cost. Missing GPU, energy, or
rate measurements must remain null and appear in the report's missing list. A known-cost subtotal
must not be presented as a complete cost. See
[experiment resource and cost accounting](resource-accounting.md).

Seed sets and the benchmark denominator are frozen before workers launch. A seed remains in the
denominator when its retries end in a crash, timeout, malformed artifact, or failed replay. Reports
must expose completion rate, failed attempts, worker crashes, and recovered runs alongside victory
rate. Completed runs count only after their immutable records pass exact transition replay. The
[parallel rollout protocol](rollout-infrastructure.md) implements these rules for the mock backend.

The first production compute-quality protocol freezes 32 validation runs, executes nested fixed
search budgets, and grades every candidate on the same held-out seeds from a separate seed domain.
Its report exposes terminal-value regret, death-risk calibration, compute, and tail latency with
exact evidence replay. See [search compute-versus-quality benchmark](compute-quality-benchmark.md).

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

Before thresholds are frozen, the initial model report must at least establish that the training
pipeline learns all declared heads, preserves complete-run train/validation isolation, and emits
action agreement, independently evaluated terminal-value regret, and value/risk calibration. Mock
results validate this machinery only; STS2 readiness requires representative full-run data from an
admitted simulator and a final test evaluation after model and thresholds are frozen. See
[initial policy, run-value, and tactical-risk models](initial-models.md).

The executable contract, thresholds, independent-audit format, and current fail-closed base-v2
decision are recorded in [base-model readiness](base-model-readiness.md). Auxiliary policy and floor
metrics are reported separately and cannot satisfy any terminal gate.

Probability calibration uses a checkpoint-bound split of complete validation runs. Calibrator
parameters are fit on one subfold and all calibration scores, sharpness measures, confident
catastrophic errors, false-safe risk predictions, and uncertainty records are reported on the other.
Both subfolds remain validation data; neither result may be described as the final readiness test.
See [calibration and uncertainty](calibration-and-uncertainty.md).

Combat-search leaves are valued as terminal-victory probabilities. Exact terminal rewards,
truncated-rollout endpoint values, and direct run-value bootstraps retain separate provenance and
configurable weights. Every fixed-search report includes a local HP/survival ablation so a proxy
cannot silently become the optimized objective. See
[tactical-to-run value handoff](tactical-to-run-value.md).
