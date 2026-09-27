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

## Current operator command

Run exactly this one command and return its final JSON output. It is the only sustained task in the
current work package and must be started and observed by the operator. It trains the base-v4
candidate from the verified 1,299-state curriculum plus the 15 policy-only causal preferences.

```bash
uv run spireshift resources run \
  --kind training \
  --report artifacts/resources/production-base-v4-metrics.json \
  --artifact-root artifacts/models/sts2-v0.107.1-base-v4 \
  --workers 1 \
  --max-wall-seconds 7200 \
  --max-cpu-seconds 14400 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 16000000000 \
  -- \
  uv run spireshift model train-curriculum \
    artifacts/bootstrap/teacher-train-v3-production-dagger-v1-combined/bootstrap-teacher-dataset.json \
    artifacts/bootstrap/teacher-validation-v3/bootstrap-teacher-dataset.json \
    artifacts/models/sts2-v0.107.1-base-v4/checkpoint.json \
    --report artifacts/models/sts2-v0.107.1-base-v4/training-report.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --causal-preferences artifacts/dagger/sts2-v0.107.1-base-v2-train-v1/causal-preferences.json \
    --intervention-spec configs/combat-search-intervention/sts2-v0.107.1-base-v3-combat-resolution-train-v2.json \
    --intervention-report artifacts/evaluations/combat-resolution-intervention-v2/combat-search-intervention-report.json \
    --ruleset-manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --epochs 60 \
    --learning-rate 0.005 \
    --l2-regularization 0.0001 \
    --gradient-clip 5 \
    --vector-dimension 4096 \
    --interaction-dimension 8192 \
    --tactical-horizon 32 \
    --pairwise-noise-floor 0.25 \
    --calibration-bins 10 \
    --shuffle-seed 0 \
    --adagrad-epsilon 0.00000001 \
    --selection-fraction 0.25 \
    --selection-salt production-base-model-selection-v1
```

Do not start evaluation yet. The base-v4 checkpoint and report must pass identity, held-out policy,
and liveness review before a frozen test comparison is allowed.
