# On-policy collection and selective teacher relabeling

SpireShift uses a reproducible DAgger-style iteration to expose the base model to states created by
its own decisions. A model trained only on teacher trajectories may never see its own recovery
states or compounding mistakes. Each iteration therefore runs the student policy to terminal states
on new seeds from the frozen training partition and preserves every decision in the resulting
complete runs.

The selection process has two teacher budgets. A cheap probe evaluates every collected decision and
is used only to decide whether a full label is worth buying. The expensive teacher then labels the
selected subset with separate search and evaluation seed domains. Probe and relabel sampling seeds
must differ, and every stored target retains its individual simulation seeds and outcomes.

A decision is selected when one or more of these deterministic triggers fires:

- `teacher_disagreement`: the probe teacher and student select different candidates;
- `rare_state`: the state's model-feature signature occupies no more than a configured fraction of
  the reference training records;
- `confident_error`: the student confidence exceeds its threshold while independent probe values
  estimate regret above the configured threshold; or
- `high_entropy`: normalized policy entropy exceeds its threshold.

These are selection triggers rather than final conclusions. The artifact separately records whether
the larger relabel teacher confirms the disagreement or confident error, along with its independently
evaluated regret. This distinction exposes noisy probe false positives instead of silently presenting
them as model failures.

## Reproducibility and split safety

An iteration is bound to the source model, reference teacher dataset, objective, ruleset, split
manifest, representation encoder, selection settings, and both teacher configurations. Collection is
restricted to the training partition and rejects seeds already present in the reference dataset.
Validation and test runs cannot enter the loop.

Every run stores contiguous student decisions through a terminal outcome. Each decision contains the
exact model input, candidate-aligned prediction, student action and successor state, reference-state
frequency, probe target, selection reasons, optional expensive target, and final run outcome.
Verification reconstructs the source model, replays every student trajectory, regenerates every
probe and relabel rollout, and requires byte-equivalent structured content before accepting the
content identity. A companion content-addressed dataset index receives the same complete-run split
audit used by the original teacher data.

The summary reports student victories and defeats, decisions and candidates, selection-reason counts,
relabels avoided, and separate probe and relabel simulation totals. Avoided labels therefore remain
visible as a compute result rather than an inferred saving.

## Commands

Collect and verify one iteration from a previously generated training dataset and checkpoint:

```bash
uv run spireshift dagger collect-mock \
  artifacts/models/mock-checkpoint.json \
  artifacts/models/mock-train.json \
  artifacts/models/dagger-0.json \
  --iteration 0 \
  --runs 8

uv run spireshift dagger verify \
  artifacts/models/dagger-0.json \
  artifacts/models/mock-checkpoint.json \
  artifacts/models/mock-train.json
```

Train the next student from the original teacher data plus only the selected expensive labels:

```bash
uv run spireshift model train \
  artifacts/models/mock-train.json \
  artifacts/models/mock-validation.json \
  artifacts/models/mock-checkpoint-dagger-1.json \
  --report artifacts/models/mock-training-report-dagger-1.json \
  --augmentation \
    artifacts/models/dagger-0.json \
    artifacts/models/mock-checkpoint.json
```

`--augmentation ITERATION SOURCE_CHECKPOINT` may be repeated. Each iteration is fully regenerated
against its source checkpoint before its selected labels enter training. The new checkpoint records
the sorted iteration IDs, and its report records the source model, complete-run count, collected
decision count, and selected record count for every augmentation.

The contracts are [dagger-iteration-v1.json](../schemas/dagger-iteration-v1.json) and
[dagger-verification-v1.json](../schemas/dagger-verification-v1.json). The checked mock result is
documented in [mock-selective-dagger-v1.md](evidence/mock-selective-dagger-v1.md).

The reference implementation proves the collection, selection, relabeling, aggregation, and audit
path on the mock backend. STS2 training still depends on representative trajectories from an
admitted simulator.
