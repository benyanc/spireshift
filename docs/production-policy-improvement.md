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
1,114 legal candidates; at 16 paired samples per candidate, the next command schedules 17,824
bounded counterfactual simulations. Each continuation now uses the same public no-op fallback as
the collector and records its fallback evidence in a production DAgger teacher schema.

The completed collection also converted the tactical diagnostic into 15 causal preferences: 11
favor the counterfactual action, one favors the original action, and three remain low-weight ties.
These preferences remain separate from the larger DAgger state set, with their original report
identities preserved. They do not by themselves justify training or promotion.

## Current operator command

Run exactly this one command and return its final JSON output. It is the only sustained task in the
current work package and must be started and observed by the operator.

```bash
uv run spireshift resources run \
  --kind teacher_generation \
  --report artifacts/resources/production-dagger-teacher-base-v2-train-v1.json \
  --metrics artifacts/resources/production-dagger-teacher-base-v2-train-v1-metrics.json \
  --artifact-root artifacts/bootstrap/teacher-production-dagger-base-v2-train-v1 \
  --workers 8 \
  --max-wall-seconds 14400 \
  --max-cpu-seconds 50000 \
  --max-storage-bytes 2000000000 \
  --max-memory-bytes 16000000000 \
  -- \
  uv run --extra evangambit spireshift bootstrap generate \
    artifacts/bootstrap/teacher-production-dagger-base-v2-train-v1 \
    --states artifacts/dagger/sts2-v0.107.1-base-v2-train-v1/state-set.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --backend evangambit \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --policy-checkpoint artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
    --policy-report artifacts/models/sts2-v0.107.1-base-v2/training-report.json \
    --samples-per-candidate 16 \
    --workers 8 \
    --worker-timeout 120 \
    --resume
```

Do not start curriculum composition, training, or test evaluation yet. The teacher result must be
verified before it is combined with the accepted base-v2 curriculum.
