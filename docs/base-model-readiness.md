# Base-model readiness gate

SpireShift does not start learned-PUCT or adaptive-compute experiments merely because a policy
reaches higher floors. The base model must pass a frozen, validation-owned scorecard whose binding,
denominators, thresholds, interval method, and failure rules are content addressed before the
readiness evaluation.

The first contract is
[`sts2-v0.107.1-base-v2-validation-v1.json`](../configs/readiness/sts2-v0.107.1-base-v2-validation-v1.json),
with scorecard ID
`sha256:85ab25083fb040c9d4a90297973f29fa1bb141d5fc6b83395837ce1024277d50`.
It binds the base-v2 checkpoint, training report, train and validation datasets, complete-run split,
ruleset, terminal-victory objective, and representation encoder. A later checkpoint must receive a
new binding before its readiness run; its thresholds and validation protocol must not be changed in
response to that run.

## Frozen gates

The contract requires all of the following:

- **Auxiliary policy:** at least 55% decisive-pair accuracy, pairwise cross-entropy no greater than
  `ln(2)`, mean progress regret no greater than 0.003, tactical-risk Brier skill of at least 0.05,
  and tactical-risk expected calibration error no greater than 0.10.
- **Inference:** at least eight candidate-aligned, legal, public-state decisions, with p95 inference
  latency no greater than 50 milliseconds.
- **Independent terminal audit:** at least 100 audit decisions and 1,600 independently sampled
  terminal outcomes, including at least 80 victories, 80 defeats, and 25 decisions whose legal
  actions have different empirical terminal values.
- **Terminal quality:** terminal-value Brier skill of at least 0.05, expected calibration error no
  greater than 0.10, mean independent action regret no greater than 0.05, and p95 regret no greater
  than 0.20.
- **Confident failures:** at least 25 high-confidence decisions must be auditable; at most two and at
  most 5% may be catastrophic. False-safe tactical-risk errors may affect at most 10% of audited
  decisions.
- **Complete runs:** the exact 100 validation seeds must all complete and terminate without policy
  cycles, decision-limit truncations, execution failures, or exhausted fallback states. Outcomes
  must include at least eight victories and eight defeats.
- **Victory performance:** the learned victory-rate 95% Wilson lower bound must be at least 2%. Its
  lower bound must also be no lower than the baseline's 95% Wilson upper bound. This conservative
  comparison prevents an auxiliary floor gain from substituting for evidence about the declared
  terminal-victory objective.

The independent audit format stores the underlying candidate outcomes rather than trusting supplied
aggregates. Loading
[`production-model-readiness-audit-v1.json`](../schemas/production-model-readiness-audit-v1.json)
recomputes calibration, regret, signal variation, catastrophic errors, and false-safe errors from
those records. Calibration fit and audit seeds must be non-empty, disjoint validation subfolds.

## Current decision

The checked base-v2 assessment is
[`production-base-v2-readiness-v1.json`](evidence/production-base-v2-readiness-v1.json), with report
ID `sha256:4da2031c4a2f8af0c10819ef716e30b13267eb3a984130c6899588d868272a6e`.

Base-v2 passes the frozen binding, auxiliary policy, tactical-risk, candidate-alignment, and latency
checks. It is **not ready**. Its train and validation curricula contain no victories, so the
terminal-value head is explicitly blocked. There is also no independent terminal audit or qualifying
100-seed validation full-run report. The report records all nine failed or missing terminal checks.
Its floor and pairwise gains remain separate diagnostics and cannot change that decision.

Recompute the current fail-closed decision without running the game:

```bash
uv run spireshift model assess-readiness \
  configs/readiness/sts2-v0.107.1-base-v2-validation-v1.json \
  artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
  --report artifacts/models/sts2-v0.107.1-base-v2/training-report.json \
  --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
  --smoke artifacts/models/sts2-v0.107.1-base-v2/inference-smoke.json \
  --output artifacts/readiness/production-base-v2-readiness-v1.json
```

The assessment command returns a failing process status when `ready=false`, after preserving the
report. Verify either a passing or failing assessment by recomputing it from its source artifacts:

```bash
uv run spireshift model verify-readiness \
  docs/evidence/production-base-v2-readiness-v1.json \
  configs/readiness/sts2-v0.107.1-base-v2-validation-v1.json \
  artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
  --report artifacts/models/sts2-v0.107.1-base-v2/training-report.json \
  --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
  --smoke artifacts/models/sts2-v0.107.1-base-v2/inference-smoke.json
```

For a complete future assessment, add `--audit` with a verified independent validation audit and
`--evaluation` with a verified v3 policy evaluation over the exact frozen validation seeds. The
scorecard fails on absent evidence, identity changes, test-owned runs, changed seed denominators,
degenerate outcomes, weak calibration, confident catastrophic errors, or incomplete runs.
