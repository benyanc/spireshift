# Initial policy, run-value, and tactical-risk models

SpireShift's first learned system is a deterministic, dependency-free sparse baseline. It exists to
make the complete training and evaluation boundary executable before a larger neural model is
connected to the admitted STS2 simulator. It consumes only verified teacher datasets and the
versioned `model-input-v1` contract.

One checkpoint contains three heads:

- a legal-candidate policy distilled from the teacher's search-visit distribution;
- a run-value head trained on the independent terminal-victory probability of the action selected
  by the teacher; and
- a candidate-conditioned tactical-risk head trained on the probability of terminal defeat within
  a configured number of decisions.

The policy and tactical-risk heads score a variable number of candidates. They combine each
candidate's features with hashed state-by-candidate interactions, allowing the same action mechanic
to receive different scores in different public states. The run-value head uses state features. All
three heads use the public, mechanics-aware representation; source action IDs are returned only as
aligned decode handles and never enter the feature vectors.

Every input contains exactly the legal candidates advertised by the environment. The loader verifies
their order, all-true legality mask, source-handle uniqueness, public-state binding, and
content-addressed representation identity before training or prediction.

## Targets and held-out evaluation

Search samples create only the policy target. Separate independent rollout samples create the value,
risk, regret, and calibration evidence, so the search that chose an action does not grade that
action. Run-value calibration expands the selected action's independent rollouts into binary
terminal outcomes. Tactical-risk calibration uses every candidate's binary defeat-within-horizon
outcomes.

The training entry point requires one frozen `train` dataset and one frozen `validation` dataset.
It verifies both datasets, rejects overlapping complete runs, and checks that their ruleset and
objective identities match. The test partition is never accepted for fitting or validation. The
report records both content-addressed dataset IDs, split-manifest ID, teacher settings, complete seed
lists, model settings, training history, and held-out metrics.

Held-out metrics include:

- action agreement with the teacher and policy cross-entropy;
- mean and 95th-percentile independent terminal-value regret;
- run-value mean absolute error, Brier score, expected calibration error, and calibration bins; and
- tactical-risk Brier score, expected calibration error, and calibration bins.

The checkpoint and report are content addressed and immutable. Learned floating-point values are
rounded to 12 decimal places at the artifact boundary so the same training run receives the same
identity across supported operating systems. Loading recomputes identities, validates model and
representation versions, and rejects malformed or duplicate sparse weights.

Training can also accept verified selective-DAgger iterations. Only records carrying an expensive
relabel target enter optimization. The checkpoint binds their iteration IDs, while the report keeps
the source model, complete-run count, collected decision count, and selected-label count. See
[on-policy collection and selective teacher relabeling](selective-dagger.md).

## Reproduce the checked mock result

Generate disjoint train and validation teacher datasets:

```bash
uv run spireshift teacher generate-mock artifacts/models/mock-train.json \
  --partition train \
  --seeds 0 2 3 4 5 6 7 8 9 10 11 12 \
  --search-simulations 16 \
  --evaluation-samples 16

uv run spireshift teacher generate-mock artifacts/models/mock-validation.json \
  --partition validation \
  --seeds 20 28 31 36 37 42 44 49 \
  --search-simulations 16 \
  --evaluation-samples 16
```

Train and verify the three-head checkpoint:

```bash
uv run spireshift model train \
  artifacts/models/mock-train.json \
  artifacts/models/mock-validation.json \
  artifacts/models/mock-checkpoint.json \
  --report artifacts/models/mock-training-report.json \
  --vector-dimension 256 \
  --interaction-dimension 512

uv run spireshift model verify \
  artifacts/models/mock-checkpoint.json \
  --report artifacts/models/mock-training-report.json
```

The serialized contracts are
[model-checkpoint-v1.json](../schemas/model-checkpoint-v1.json) and
[model-training-report-v1.json](../schemas/model-training-report-v1.json). The reproducible checked
result is documented in [mock-initial-model-v1.md](evidence/mock-initial-model-v1.md).

This baseline proves that the data, optimization, checkpoint, and held-out evaluation path works. It
does not establish STS2 gameplay quality. That claim requires representative full-run data from an
admitted simulator, a stronger model selected only on validation data, and a one-time frozen test
evaluation under the readiness protocol.
