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

Selection uses 32 fresh train runs at offsets 136-167. These complete runs do not overlap the
base-v2 reference curriculum or the earlier intervention window. The output is a versioned,
teacher-ready state set only if all runs stay live and the collection reaches its minimum coverage.

The same command converts the completed tactical diagnostic into 15 causal preferences: 11 favor
the counterfactual action, one favors the original action, and three remain low-weight ties. These
preferences remain separate from the larger DAgger state set, with their original report identities
preserved. They do not by themselves justify training or promotion.

## Current operator command

Run exactly this one command and return its final JSON output. It is the only sustained task in the
current work package and must be started and observed by the operator.

```bash
uv run spireshift resources run \
  --kind rollout \
  --report artifacts/resources/production-dagger-base-v2-train-v1.json \
  --metrics artifacts/resources/production-dagger-base-v2-train-v1-metrics.json \
  --artifact-root artifacts/dagger/sts2-v0.107.1-base-v2-train-v1 \
  --workers 4 \
  --max-wall-seconds 7200 \
  --max-cpu-seconds 20000 \
  --max-storage-bytes 2000000000 \
  --max-memory-bytes 16000000000 \
  -- \
  uv run --extra evangambit spireshift dagger collect-production \
    configs/dagger/sts2-v0.107.1-base-v2-train-v1.json \
    artifacts/dagger/sts2-v0.107.1-base-v2-train-v1 \
    --checkpoint artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
    --report artifacts/models/sts2-v0.107.1-base-v2/training-report.json \
    --reference-dataset artifacts/bootstrap/teacher-train-v3-combined/bootstrap-teacher-dataset.json \
    --intervention-spec configs/combat-search-intervention/sts2-v0.107.1-base-v3-combat-resolution-train-v2.json \
    --intervention-report artifacts/evaluations/combat-resolution-intervention-v2/combat-search-intervention-report.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --resume
```

Do not start teacher labeling, training, or test evaluation yet. The collection result determines
the exact state-set identity and whether the next stage is allowed to proceed.
