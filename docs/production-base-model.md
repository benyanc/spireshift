# Production curriculum base model

The first STS2 base model consumes the complete curriculum-v2 train and validation datasets. It is
a deterministic sparse model intended to answer a narrow question before larger architectures or
adaptive search are introduced: does the paired teacher evidence produce a useful low-cost policy
under a frozen complete-run split?

The model fits three always-active candidate-conditioned heads:

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

Version 3 can also fit a candidate-conditioned terminal-victory head. It promotes that head only
when the train fitting subfold, train model-selection subfold, and frozen validation partition each
contain at least one completed victory and one completed non-victory. Capped outcomes are censored,
not mislabeled as losses. The terminal head selects its epoch on the train-owned selection subfold,
is refit from scratch on all train runs, and reports calibration and Brier skill on validation.
The checkpoint/report pair records the exact completed, victorious, losing, and censored counts for
every partition.

The existing base-v2 and base-v3 datasets contain zero victories, so their terminal-victory heads
remain explicitly blocked. Their checkpoints cannot be loaded as though they contained a terminal
value estimate. Floor and risk predictions remain auxiliary evidence and cannot satisfy the
terminal-victory readiness gate. Version-1 and version-2 artifacts remain read compatible.

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

## Operator-started paired full-run pilot

The next sustained job compares the learned policy with `ProgressBootstrapPolicy` on the same 32
frozen test seeds. Every seed-policy case is written independently, so `--resume` can reuse verified
completed cases after an interrupted command. Failed cases stay in the denominator. The report
separates victories, terminal completion, maximum floor, decision latency, and paired differences;
auxiliary floor progress cannot replace terminal victories.

An automated coding agent prepares and verifies this command but does not start or monitor it:

```bash
uv run spireshift resources run \
  --kind rollout \
  --report artifacts/resources/production-policy-evaluation-v1.json \
  --metrics artifacts/resources/production-policy-evaluation-v1-metrics.json \
  --artifact-root artifacts/evaluations/sts2-v0.107.1-base-v2-policy-pilot \
  --workers 4 \
  --max-wall-seconds 14400 \
  --max-cpu-seconds 50000 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 16000000000 \
  -- \
  uv run --extra evangambit spireshift model evaluate-curriculum \
    artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
    --report artifacts/models/sts2-v0.107.1-base-v2/training-report.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --output-dir artifacts/evaluations/sts2-v0.107.1-base-v2-policy-pilot \
    --runs 32 \
    --workers 4 \
    --max-decisions-per-run 4096
```

After the command finishes, verify the aggregate against every immutable case and its frozen
checkpoint, training report, split, objective, and ruleset:

```bash
uv run spireshift model verify-evaluation-curriculum \
  artifacts/evaluations/sts2-v0.107.1-base-v2-policy-pilot/production-policy-evaluation.json \
  artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
  --report artifacts/models/sts2-v0.107.1-base-v2/training-report.json \
  --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json

uv run spireshift resources verify \
  artifacts/resources/production-policy-evaluation-v1.json
```

If execution stops before the aggregate report is created, rerun the inner
`evaluate-curriculum` command with `--resume`; it verifies and reuses existing cases and executes
only missing seed-policy pairs. Use a new resource-report path for that resumed invocation.

## Learned-policy curriculum v3 candidate

The learned-policy curriculum produced a valid base-v3 candidate from 979 train records across 80
complete runs and 256 validation records across 24 disjoint runs. Its checkpoint is
`sha256:327ba33da07880634c8d884312220ac61b8923f2ad0354b25c11d2ad4c56db2c`; its training
report is `sha256:6cc0f8d7728636c87ab5ecf0e64f5ae420d2b3a87394c7bc0d921a13fa5c7543`.
All four prespecified auxiliary-policy checks passed. Compared with base-v2, mean progress regret
improved from 0.002580 to 0.002004 and hard-teacher action agreement increased from 49.0% to 54.7%.
Weighted pairwise cross-entropy worsened from 0.6497 to 0.6812, decisive-pair accuracy fell from
78.4% to 57.0%, and tactical-risk Brier skill fell from 0.268 to 0.105. Base-v3 therefore remains a
candidate pending the same frozen-test full-run evaluation; training metrics alone do not promote
it over base-v2. Terminal-value training remains blocked because train and validation contain no
victories.

Training used 349.69 wall seconds, 336.27 CPU seconds, 849 MB peak memory, and 4.57 MB of artifact
storage. Its resource report is
`sha256:41207dce9fc851a759a1592c3537a789965a625fd4d864fc33c5b65c03654d9a`. The
[base-v3 inference smoke](evidence/production-model-inference-smoke-v3-v0.107.1.json) is
`sha256:eb02b268cc0f24cc750755098d0e13eb95efc3b452e9621b3f7244ba7fff4ec3`. It aligned
all eight decisions, selected legal actions using public state only, and measured 5.27 ms median
and 7.24 ms maximum end-to-end latency.

The following sustained command evaluates base-v3 against the progress baseline on the same 32
frozen test seeds used for base-v2:

```bash
uv run spireshift resources run \
  --kind rollout \
  --report artifacts/resources/production-base-v3-policy-evaluation-pilot.json \
  --metrics artifacts/resources/production-base-v3-policy-evaluation-pilot-metrics.json \
  --artifact-root artifacts/evaluations/sts2-v0.107.1-base-v3-policy-pilot \
  --workers 4 \
  --max-wall-seconds 14400 \
  --max-cpu-seconds 50000 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 16000000000 \
  -- \
  uv run --extra evangambit spireshift model evaluate-curriculum \
    artifacts/models/sts2-v0.107.1-base-v3/checkpoint.json \
    --report artifacts/models/sts2-v0.107.1-base-v3/training-report.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --output-dir artifacts/evaluations/sts2-v0.107.1-base-v3-policy-pilot \
    --runs 32 \
    --workers 4 \
    --max-decisions-per-run 4096
```

The completed base-v3 pilot is
`sha256:d45465af532cf3a2f0ea796aa1ac02f97d513aa45b4050940a00630718ea9489`. It won
zero runs and reached mean maximum floor 7.25, compared with 7.28125 for base-v2 on the same seeds.
At the seed level, v3 reached a higher floor 12 times, a lower floor nine times, and tied 11 times;
the mean paired difference was -0.03125 floors, with a deterministic paired-bootstrap 95% interval
of [-0.594, 0.531]. This does not establish an improvement.

Base-v3 also hit the 4,096-decision cap on seeds 174, 241, and 244, while base-v2 terminated all 32
runs. Those three cases added 12,312 decisions and reduced v3's terminal rate to 90.625%. Base-v2
remains the production checkpoint; base-v3 is retained as a negative-result artifact and as input
to the liveness work in issue #96. The first 32 test seeds are pilot evidence and must not be reused
to tune and reselect another checkpoint. The remaining 68 test seeds stay sealed for the later final
benchmark. The v3 pilot used 80.40 wall seconds and its verified resource report is
`sha256:025a494efdf8622cc565433077bdc61e2e6e65a5b75e9313a3c53b7315b7466b`.

## Production-policy liveness diagnostics

Evaluation format v2 records only public evidence and stops a deterministic cycle before the
global decision cap. A cycle requires the same public state, selected action, and resulting public
state eight times. Each case records the repeated transition count, its first occurrence and first
repeat, the decision type, whether the public state was unchanged, and at most the final 16 public
transition hashes. The aggregate separates `policy_cycle_runs` from unexplained
`decision_limit_runs`. These diagnostics do not expose engine-private state.

The first prespecified 100-seed validation suite is
`sha256:b8240f031c0e3d82031651528cdc412f9fe25bb05125a3fd64e09a63a08bc459`. It
found zero unexplained decision-limit truncations and three learned-policy cycles, on validation
seeds 225, 335, and 627. All three selected `evangambit:relic_reward:4` on a relic-selection state
and received the identical public state eight times. The baseline terminated all 100 runs. The
resource report is
`sha256:6b820720a2ecdd74dfae47b33f66e6a25da3202982b355a2c8d685498f6aec75`;
the suite used 50.37 wall seconds, 60.14 CPU seconds, 134 MB peak memory, and 1.50 MB storage.

The public evidence exposed an admitted-backend action collision: a five-item reward screen can
advertise index 4 as a compacted reward action while `StepRelicReward` interprets index 4 as
discarding potion slot 0 whenever a potion reward is pending. If that slot is empty, the backend
rejects the advertised action and returns an unchanged state. Evaluation format v3 therefore adds a
generic controller that suppresses an action after it produces the same public state twice, provided
another legal action remains. It records every suppression, invocation, and exhausted state. A
bounded smoke over the three failures terminated all three learned runs, reached floors 6, 7, and 8,
and used the fallback six times without exhausting a legal-action set.

The exact reproduction command for the same prespecified 100 validation seeds with the generic
fallback is below. It does not use the 32 opened test outcomes or the 68 sealed test seeds:

```bash
uv run spireshift resources run \
  --kind rollout \
  --report artifacts/resources/production-base-v3-validation-liveness-v2.json \
  --metrics artifacts/resources/production-base-v3-validation-liveness-v2-metrics.json \
  --artifact-root artifacts/evaluations/sts2-v0.107.1-base-v3-validation-liveness-v2 \
  --workers 4 \
  --max-wall-seconds 14400 \
  --max-cpu-seconds 50000 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 16000000000 \
  -- \
  uv run --extra evangambit spireshift model evaluate-curriculum \
    artifacts/models/sts2-v0.107.1-base-v3/checkpoint.json \
    --report artifacts/models/sts2-v0.107.1-base-v3/training-report.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --output-dir artifacts/evaluations/sts2-v0.107.1-base-v3-validation-liveness-v2 \
    --partition validation \
    --runs 100 \
    --workers 4 \
    --max-decisions-per-run 4096 \
    --cycle-repetition-threshold 8 \
    --liveness-tail-length 16 \
    --no-op-fallback-threshold 2
```

After it finishes, verify both content-addressed reports:

```bash
uv run spireshift model verify-evaluation-curriculum \
  artifacts/evaluations/sts2-v0.107.1-base-v3-validation-liveness-v2/production-policy-evaluation.json \
  artifacts/models/sts2-v0.107.1-base-v3/checkpoint.json \
  --report artifacts/models/sts2-v0.107.1-base-v3/training-report.json \
  --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json

uv run spireshift resources verify \
  artifacts/resources/production-base-v3-validation-liveness-v2.json
```

The completed fallback evaluation is
`sha256:62ae329defdb5c19a920a8c1a1a0c70429017cf24a637fc758e25cc6090caa8f`.
All 100 learned-policy and 100 baseline runs terminated, with zero decision-limit runs, policy
cycles, and exhausted fallback states. The guard intervened six times across only the three known
learned-policy seeds; the other 197 policy/seed cases retained identical outcomes, maximum floors,
and action-trace hashes. The formerly cycling runs terminated at floors 6, 7, and 8, raising learned
mean maximum floor from 7.05 to 7.14. The verified resource report is
`sha256:8260bdf72ac74cdf1749206dbe459fff504c24a8f0151c971ee596d3faefa181`;
the rerun used 53.20 wall seconds, 63.15 CPU seconds, 142 MB peak memory, and 1.56 MB storage.

This satisfies the production-policy liveness gate. It establishes termination behavior only:
base-v3 remains rejected because it did not improve frozen-test gameplay quality, and the remaining
68 test seeds remain sealed for the final benchmark.

The checkpoint and report schemas are
[`production-model-checkpoint-v2.json`](../schemas/production-model-checkpoint-v2.json) and
[`production-model-training-report-v2.json`](../schemas/production-model-training-report-v2.json).
The inference evidence schema is
[`production-model-inference-smoke-v1.json`](../schemas/production-model-inference-smoke-v1.json).
The paired evaluation schemas are
[`production-policy-evaluation-v3.json`](../schemas/production-policy-evaluation-v3.json) and
[`production-policy-evaluation-case-v3.json`](../schemas/production-policy-evaluation-case-v3.json).
The loader retains read-only verification compatibility with the version-1 base-v2 and rejected
base-v3 pilot artifacts and the version-2 validation diagnostic.
