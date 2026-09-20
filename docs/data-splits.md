# Frozen complete-run data splits

SpireShift assigns data to train, validation, and test partitions at the complete-run boundary. A
decision record and every encounter instance inherit the partition of their run. Records never carry
an independently selectable split, which prevents adjacent states from one trajectory from entering
different partitions.

The first checked manifest covers mock seeds 0 through 999:

| Partition | Runs | Permitted use |
|---|---:|---|
| Train | 800 | Model fitting, teacher generation, and on-policy collection |
| Validation | 100 | Model selection, calibration choices, and readiness thresholds |
| Test | 100 | Frozen final measurement after choices are complete |

The manifest uses `sha256-ranked-v1`: it hashes every seed with the declared public salt, ranks the
digests, assigns the exact configured counts, and then stores every resulting seed explicitly. The
loader recomputes the assignment and content-addressed manifest ID. Changing one seed, count, salt,
ruleset, objective, or encounter-policy field requires a new manifest identity.

```bash
uv run spireshift split verify \
  manifests/splits/mock-v1-seeds-000000-000999-v1.json

uv run spireshift split seeds \
  manifests/splits/mock-v1-seeds-000000-000999-v1.json test
```

## Run and encounter membership

A dataset index lists terminal runs and their decision records. Each run declares one frozen seed and
one partition. Each encounter instance is identified by `(run_id, encounter_id)` and belongs to that
same run. Encounter types may occur in multiple partitions; an encounter *instance* and all of its
decisions cannot. A separate out-of-distribution protocol may later hold out encounter types without
changing this leakage boundary.

Dataset indices are also content-addressed. Freeze an index specification only after collection has
finished:

```bash
uv run spireshift split freeze-index \
  manifests/splits/mock-v1-seeds-000000-000999-v1.json \
  path/to/dataset-index-specification.json \
  path/to/frozen-dataset-index.json

uv run spireshift split audit \
  manifests/splits/mock-v1-seeds-000000-000999-v1.json \
  path/to/frozen-dataset-index.json
```

The audit rejects a changed content hash, wrong manifest or ruleset, unknown seed, incorrect declared
partition, duplicate run or record, incomplete non-terminal run, missing record, undeclared encounter,
and non-contiguous decision sequence. `partition_dataset_records` performs this audit before exposing
records grouped by partition; model and teacher-data loaders should use that boundary.

The checked index at `tests/fixtures/splits/dataset-index-v1.json` includes one complete run from
each partition and two adjacent records per run. Its checked audit demonstrates that all six records
remain grouped by run.

## Versioning rules

- Freeze a new split manifest for a new seed universe, ruleset, objective, ratio, or assignment salt.
- Preserve old manifests and indices; writers refuse to replace a file with different content.
- Fit models only on train runs. Use validation for choices and test for the final frozen estimate.
- Record the split-manifest and dataset-index IDs with every dataset, checkpoint, and benchmark.
- Split a cross-patch experiment by its declared P0/P1 protocol; do not silently remap old seeds.
