# Production curriculum base model

The first STS2 base model consumes the complete curriculum-v2 train and validation datasets. It is
a deterministic sparse model intended to answer a narrow question before larger architectures or
adaptive search are introduced: does the paired teacher evidence produce a useful low-cost policy
under a frozen complete-run split?

The model fits three active candidate-conditioned heads:

- a policy score trained on every candidate pair whose paired outcomes carry evidence beyond the
  configured noise floor;
- tactical death risk, defined as terminal defeat within 32 simulated decisions; and
- an ordinal maximum-floor distribution over every nondegenerate threshold in the train data.

Pair confidence is `max(0, abs(2p - 1) - 0.25)` multiplied by the recorded half-split stability
factor. This retains useful within-state comparisons even when the curriculum's global state weight
is zero. The trainer also fits the existing weighted soft-target formulation as an evaluation-only
baseline with the same features, dimensions, optimizer, and train records.

The terminal-victory head remains explicitly blocked. Both production datasets contain zero
victories, so fitting a constant losing value would create no useful value signal. The checkpoint
records that status and cannot be loaded as though it contained a terminal-value head. Floor and
risk predictions remain auxiliary evidence and cannot satisfy the terminal-victory readiness gate.

## Frozen inputs

- Train dataset:
  `sha256:8773cadbd7f9ab0a8aa80b7bf63577b2a1a38c8798e64a1a7f718796ebf2263c`
  (545 states from 64 complete train runs).
- Validation dataset:
  `sha256:0b0557d938f9a44ffea9f9ea7c4331e785336698202a3e9bc14fca9eb8352867`
  (204 states from 24 complete validation runs).
- Split manifest:
  `manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json`.

Loading verifies each teacher dataset, its content identities, partition ownership, ruleset,
objective, candidate order, public model input, and signal gate. Train and validation complete-run
seeds must be disjoint.

## Prespecified auxiliary gate

The held-out report must satisfy all four checks before this sparse policy is considered useful
auxiliary progress:

1. confidence-weighted pairwise cross-entropy is below `ln(2)`, the uniform pair predictor;
2. accuracy on decisive validation pairs is above 50%;
3. mean progress-utility regret is below the deterministic source-order policy; and
4. pairwise cross-entropy is below the separately trained weighted soft-target baseline.

The report also records action agreement, effective pair weight and decisive accuracy by decision
type, comparison with the soft-target baseline, risk and floor calibration, outcome prevalence,
constant-rate Brier baselines, and Brier skill. Passing this gate does not promote the model to
full-run readiness. That still requires nondegenerate terminal-victory evidence, policy-only and
search integration, latency measurements, and the frozen readiness scorecard.

## Operator-started training run

This is a sustained experiment. A person starts and observes it; an automated coding agent should
only prepare and verify the command and assess the finished artifacts.

```bash
uv run spireshift resources run \
  --kind training \
  --report artifacts/resources/production-base-v1.json \
  --metrics artifacts/resources/production-base-v1-metrics.json \
  --artifact-root artifacts/models/sts2-v0.107.1-base-v1 \
  --workers 1 \
  --max-wall-seconds 3600 \
  --max-cpu-seconds 7200 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 16000000000 \
  -- \
  uv run spireshift model train-curriculum \
    artifacts/bootstrap/teacher-train-v2/bootstrap-teacher-dataset.json \
    artifacts/bootstrap/teacher-validation-v2/bootstrap-teacher-dataset.json \
    artifacts/models/sts2-v0.107.1-base-v1/checkpoint.json \
    --report artifacts/models/sts2-v0.107.1-base-v1/training-report.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --epochs 60 \
    --learning-rate 0.02 \
    --l2-regularization 0.0001 \
    --gradient-clip 5 \
    --vector-dimension 4096 \
    --interaction-dimension 8192 \
    --tactical-horizon 32 \
    --pairwise-noise-floor 0.25 \
    --calibration-bins 10 \
    --shuffle-seed 0
```

After it finishes, verify the immutable artifacts:

```bash
uv run spireshift model verify-curriculum \
  artifacts/models/sts2-v0.107.1-base-v1/checkpoint.json \
  --report artifacts/models/sts2-v0.107.1-base-v1/training-report.json

uv run spireshift resources verify \
  artifacts/resources/production-base-v1.json
```

The checkpoint and report schemas are
[`production-model-checkpoint-v1.json`](../schemas/production-model-checkpoint-v1.json) and
[`production-model-training-report-v1.json`](../schemas/production-model-training-report-v1.json).
