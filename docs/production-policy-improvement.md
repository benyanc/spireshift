# Cycle-safe production policy improvement

The accepted base-v2 policy remains the production foundation. It reached farther than the simple
baseline but won zero of 32 frozen test runs. Base-v3 also won zero runs and did not improve mean
maximum floor, so this iteration collects new evidence with base-v2 rather than promoting base-v3
or deploying tactical search.

The production DAgger collector runs complete train-owned trajectories with the shared
`PublicNoOpActionGuard`. It records every decision and preserves fallback and cycle evidence. It
selects at most ten actionable states per run for later teacher labeling:

- rare states relative to the verified base-v2 curriculum;
- high-entropy decisions where base-v2 is uncertain;
- three of each run's deepest actionable states, so early easy decisions do not dominate.

Selection used 32 fresh train runs at offsets 136-167. These complete runs do not overlap the
base-v2 reference curriculum or the earlier intervention window. All 32 runs terminated without a
failure, cycle, or decision limit. The collector selected 320 unique states across five decision
types and 13 source-floor bins, including 96 terminal-frontier states. The frozen state set is
`sha256:23771cca8a8154abb6d8cb696ee4d63d21bac1409aa4a9e2dfa62162752b82a1`.

The collection still contained zero victories, so it does not unblock terminal-value training. It
does clear the coverage and liveness gate for paired teacher labeling. The selected states contain
1,114 legal candidates; at 16 paired samples per candidate, teacher labeling scheduled 17,824
bounded counterfactual simulations. Each continuation now uses the same public no-op fallback as
the collector and records its fallback evidence in a production DAgger teacher schema.

Teacher labeling completed all 320 states and 17,824 simulations in 25 minutes 28 seconds. Every
continuation terminated; none required the fallback. The labels contain progress variation in 111
states, 20 hard-target-eligible states, 19.82 effective labeled states, and 91.56% paired-winner
agreement between sample halves. The dataset passed complete verification as
`sha256:59fcdfab13431b78171c4609d7807dccddae99ce81caa3c52c8602ac5e1ce507`.

The new dataset and accepted base-v2 curriculum have identical policy, ruleset, objective, teacher,
and sampling configurations. Their 112 complete-run seeds are disjoint. They are therefore eligible
for one verified composition containing 1,299 labeled states. Composition verifies about 1.3 GB of
existing evidence and may take more than a minute even though it performs no simulation or training.

Composition completed in 111 seconds. The resulting 1,299 cases contain 4,799 candidates, 76,784
paired simulations, 569 progress-varying states, 45 hard-target-eligible states, 51.62 effective
labeled states, and 86.07% half-split winner agreement. All 320 new DAgger states are unique relative
to the earlier curriculum; the composed corpus has 1,268 unique public states. Its dataset identity
is `sha256:bf26c88358111fd70a1a30c8e9bd59be29080a3d69d93d3714223955545c22ac`. The composition resource
report is `sha256:d143b606b347f2b66abf88ffff3eef58ac9c36de8befb33fec0dbf8d3bff6269`.
Full integrity verification then checked all 1,299 cases with no errors and confirmed the same
dataset identity. The verification resource report is
`sha256:a28896bfa0ba558cc2b9705342893fdb1372b0801d0bf0508857a9bf8da28235`.

The completed collection also converted the tactical diagnostic into 15 causal preferences: 11
favor the counterfactual action, one favors the original action, and three remain low-weight ties.
These preferences remain separate from the larger DAgger state set, with their original report
identities preserved. The v4 training adapter verifies them against the original intervention
cases, reconstructs their public-state inputs, and applies them only to the policy head. They cannot
alter the terminal-value, tactical-risk, or maximum-floor heads. Complete-run model-selection
subfolds also remain separate for this causal evidence.

Base-v4 training completed in 481 seconds. Its checkpoint is
`sha256:bec02c5f8808d1b9780eece83da16848017105366c1382f655860fb39227a215`, its training report is
`sha256:37f08f7457a7f82f40cff407931cd64aeb7c9ffaaccdd2bcaf5144dca7fbecdb`, and the resource report is
`sha256:e1e96dfc0ea86305fa55202e6869f0cdffcbb628ed041d93bf33104d11b73eff`.

The raw base-v4 policy is rejected. On the frozen validation curriculum its pairwise cross-entropy
was 0.7720, decisive-pair accuracy was 46.24%, and only the regret check passed. However, its
decisive accuracy on the 12 non-tied causal preferences rose to 66.67%, compared with 16.67% for
base-v2. The new evidence taught the intended distinction but overwhelmed broader policy quality.

`model blend-curriculum` now performs a deterministic recovery step. It evaluates a fixed grid of
policy-weight interpolations from base-v2 to base-v4 on the same validation curriculum, then chooses
the largest base-v4 share that passes every predeclared auxiliary policy check. It blends only the
policy head; the base-v4 auxiliary heads and complete causal provenance remain unchanged. The full
grid and its validation and causal metrics are stored in the versioned checkpoint and report, while
the frozen test split remains untouched.

The selected base-v5 policy uses 55% base-v4 and 45% base-v2. It passes all four policy checks with
0.6637 pairwise cross-entropy, 69.89% decisive-pair accuracy, and 0.002499 mean progress regret. On
the causal evidence it reaches 58.33% decisive accuracy, assigns 50.68% mean probability to the
search action when beneficial, and only 29.30% when harmful. The verified base-v5 checkpoint is
`sha256:3cd6aa0351b3b206e4d692e620a5bdee568f10dee152bd2d697bde226a8b06d8`; its report is
`sha256:7f992ad6eee798736f58a2d356febcebca310e35e79d852696257f6b7b465a1c`.

## Current operator command

The base-v5 admitted-backend smoke is frozen as
[`production-model-inference-smoke-v5-v0.107.1.json`](evidence/production-model-inference-smoke-v5-v0.107.1.json),
with identity `sha256:8106e3ef385162c9f29f1ce76f6c0c6a86273bc12bbafe99befa426674c23bb6`.
All eight decisions were candidate-aligned, legal, and public-state only. The sample included two
combat decisions; median inference latency was 4.83 ms and maximum latency was 6.98 ms. The artifact
verified against the exact base-v5 checkpoint and report, so the frozen test comparison is now
allowed.

The previous evaluator paired a checkpoint only with the simple progress heuristic. The v4
evaluation contract instead binds both checkpoint/report pairs and executes base-v5 and accepted
base-v2 on the same untouched test seeds. It stores candidate and reference cases independently for
safe resume and reports terminal outcomes, liveness, fallback use, latency, and paired floor deltas.

Run exactly this one resource-capped command and return its final JSON output. It is the only
sustained task in the current work package and must be started and observed by the operator.

```bash
uv run spireshift resources run \
  --kind rollout \
  --report artifacts/resources/production-base-v5-vs-v2-test-v1.json \
  --metrics artifacts/resources/production-base-v5-vs-v2-test-v1-metrics.json \
  --artifact-root artifacts/evaluations/sts2-v0.107.1-base-v5-vs-v2-test-v1 \
  --workers 4 \
  --max-wall-seconds 14400 \
  --max-cpu-seconds 50000 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 16000000000 \
  -- \
  uv run --extra evangambit spireshift model evaluate-curriculum \
    artifacts/models/sts2-v0.107.1-base-v5/checkpoint.json \
    --report artifacts/models/sts2-v0.107.1-base-v5/training-report.json \
    --reference-checkpoint artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
    --reference-report artifacts/models/sts2-v0.107.1-base-v2/training-report.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --output-dir artifacts/evaluations/sts2-v0.107.1-base-v5-vs-v2-test-v1 \
    --runs 32 \
    --workers 4 \
    --max-decisions-per-run 4096
```

This evaluation can show whether the causal-policy recovery improves base-v2 under the frozen
protocol. Zero victories would still keep terminal-value and learned-search readiness blocked.
