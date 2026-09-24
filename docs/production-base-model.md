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

Version 2 uses sparse AdaGrad to prevent large or frequently repeated hashed features from driving
unbounded updates. Epoch selection never touches validation data: complete train runs are
deterministically divided into a 75% fitting subfold and a 25% model-selection subfold. Policy,
soft-baseline, risk, and each floor head select their own epoch, after which those epoch counts are
refit from scratch on all train runs. The frozen validation partition is evaluated once after
refitting.

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

## Rejected version-1 run

The first operator-started run is preserved as negative evidence. Checkpoint
`sha256:236b64103ac3b5f84d27c7f774f6c91a876c141046381ab2de2b5c58a14247e2` was internally
valid but failed the auxiliary gate. Its pairwise cross-entropy was 0.9619 versus 0.6931 for a
uniform predictor and 0.7848 for the soft-target baseline. Tactical-risk Brier skill was -0.6631,
and every nonconstant floor threshold had negative skill. Training losses rose while some weights
grew above 300 in absolute value. This checkpoint must not be integrated into play or search.

The run used 131.05 wall seconds, 123.96 CPU seconds, 525 MB peak memory, and 3.0 MB of artifact
storage. Its resource report is
`sha256:05479556dbb5d6e4d73291504c617526259146360a964fc2737d8de3e58f2a3c`.

## Accepted version-2 auxiliary model

The operator-started v2 run passed all four prespecified policy checks. Its checkpoint is
`sha256:b0b727319ecd5544df519d703c190a01d08b0aa37f8098a3bc8bcbcfd33a0571`, and its training
report is `sha256:246f9a1ae30ee77f52ea22d3eb70a98828ba2f31d06191cf4a80ea64b2b9a434`.
Held-out pairwise cross-entropy is 0.6497, below uniform 0.6931 and the matched soft-target model's
0.7228. Decisive-pair accuracy is 78.41%, mean progress regret is 0.002580, and tactical-risk
Brier skill is +0.2684. Floor prediction remains diagnostic: floor 4 has positive Brier skill, but
most other nonconstant thresholds are slightly negative.

The run used 200.35 wall seconds, 192.97 CPU seconds, 526 MB peak memory, and 3.05 MB of artifact
storage. Its resource report is
`sha256:6d0298e824f133a81e3ade5daf6201af18a33e7b2db3177fb5821ac405bc1f37`.

The following sustained reproduction command remains person-started and person-observed:

```bash
uv run spireshift resources run \
  --kind training \
  --report artifacts/resources/production-base-v2.json \
  --metrics artifacts/resources/production-base-v2-metrics.json \
  --artifact-root artifacts/models/sts2-v0.107.1-base-v2 \
  --workers 1 \
  --max-wall-seconds 3600 \
  --max-cpu-seconds 7200 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 16000000000 \
  -- \
  uv run spireshift model train-curriculum \
    artifacts/bootstrap/teacher-train-v2/bootstrap-teacher-dataset.json \
    artifacts/bootstrap/teacher-validation-v2/bootstrap-teacher-dataset.json \
    artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
    --report artifacts/models/sts2-v0.107.1-base-v2/training-report.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
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

After it finishes, verify the immutable artifacts:

```bash
uv run spireshift model verify-curriculum \
  artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
  --report artifacts/models/sts2-v0.107.1-base-v2/training-report.json

uv run spireshift resources verify \
  artifacts/resources/production-base-v2.json
```

## Bounded admitted-backend inference smoke

`ProductionCheckpointPolicy` loads only an identity-verified checkpoint/report pair whose held-out
auxiliary policy gate passed. It checks the frozen ruleset and terminal-victory objective, constructs
the public candidate-aligned representation, preserves legal-action order, and returns a legal
argmax action. The same policy satisfies the shared policy interface used by policy-only episodes
and tactical continuation rollouts. The blocked terminal-value head is never exposed as a run-value
estimate.

The bounded smoke below is an integration check rather than a full-run evaluation. It executes at
most eight decisions over two seeds and records exact candidate alignment, legal selection, model
and ruleset identities, and end-to-end representation-plus-inference latency.

```bash
uv run --extra evangambit spireshift model smoke-curriculum \
  artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
  --report artifacts/models/sts2-v0.107.1-base-v2/training-report.json \
  --upstream-root artifacts/backend/evangambit-v0.107.1 \
  --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
  --seeds 0 1 \
  --max-decisions-per-seed 4 \
  --output artifacts/models/sts2-v0.107.1-base-v2/inference-smoke.json

uv run spireshift model verify-curriculum-smoke \
  artifacts/models/sts2-v0.107.1-base-v2/inference-smoke.json \
  artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
  --report artifacts/models/sts2-v0.107.1-base-v2/training-report.json
```

The [frozen completed smoke](evidence/production-model-inference-smoke-v0.107.1.json) is
`sha256:80b9742fc4aaf2e5058904230d399eb3bc234c9970a6c1d99e299df611b9d058`.
It aligned every candidate and selected a legal action across all eight decisions, including two
combat states. Median end-to-end inference latency was 5.06 ms and maximum latency was 6.67 ms on
the recorded Apple M4 Pro host. This establishes backend compatibility and latency only; it does
not measure gameplay quality or full-run readiness.

The checkpoint and report schemas are
[`production-model-checkpoint-v2.json`](../schemas/production-model-checkpoint-v2.json) and
[`production-model-training-report-v2.json`](../schemas/production-model-training-report-v2.json).
The inference evidence schema is
[`production-model-inference-smoke-v1.json`](../schemas/production-model-inference-smoke-v1.json).
The loader retains read-only verification compatibility with the rejected version-1 artifacts.
