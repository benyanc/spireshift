# Milestone-conditioned run-level trajectory search

The accepted base-v2 policy reaches farther than the deterministic baseline but has produced no
terminal victories. Sparse independent exploration also failed: 384 train-only trajectories made
1,426 non-argmax decisions, yet none passed floor 13. This experiment replaces independent random
changes with coherent trajectory search.

For each train seed, generation zero is an exact base-v2 trajectory. Each later candidate replays a
retained parent's public-state-aligned prefix, changes one legal decision, and then returns to
base-v2. The beam keeps the four best distinct action traces across generations. A child can
therefore preserve useful earlier changes and add another later change. Retained outcomes are ranked
lexicographically by:

1. terminal full-run victory;
2. entry into Act 2;
3. reaching the Act 1 boss;
4. maximum floor;
5. a deterministic action-trace hash used only to break exact ties.

The environment's terminal-victory flag remains the only positive reward. Boss reach and Act 1
clear are auxiliary foundation signals and are never relabeled as victories.

## Frozen pilot

The v1 pilot uses 16 previously unused train seeds at ranked offsets 232 through 247. It runs at
most eight mutation generations, keeps a beam of four trajectories, and tries four mutations per
parent. The resulting upper bound is 1,872 trajectories before early stopping and duplicate-trace
removal. Work is parallel only across seeds, so parent selection remains deterministic.

The command performs an admitted-backend preflight before searching. It requires public `act` and
`floor` fields, `underdocks` as the initial act, floor 17 as the Act 1 boss threshold, and
`overgrowth` as Act 2 entry. It never clones or resamples hidden state. Exact reset-and-replay keeps
the first pilot independent of the hidden-world clone defect tracked in issue #105.

Cases are immutable and resumable at the seed boundary. They preserve every policy distribution,
selected action, parent, mutation, replay divergence, liveness event, no-op fallback, milestone,
generation incumbent, and content identity. The verifier recomputes identities, complete train-seed
coverage, parent order, exact-policy baseline behavior, monotonic incumbent ranks, summaries, and
readiness from the cases.

The project owner starts the sustained run. Run this single command from the repository root:

```bash
uv run spireshift resources run \
  --kind rollout \
  --report artifacts/resources/trajectory-search-base-v2-act1-train-v1.json \
  --metrics artifacts/resources/trajectory-search-base-v2-act1-train-v1-metrics.json \
  --artifact-root artifacts/trajectory-search/sts2-v0.107.1-base-v2-act1-train-v1 \
  --workers 8 \
  --max-wall-seconds 14400 \
  --max-cpu-seconds 50000 \
  --max-storage-bytes 3000000000 \
  --max-memory-bytes 16000000000 \
  -- \
  uv run --extra evangambit spireshift model search-run-trajectories \
    configs/trajectory-search/sts2-v0.107.1-base-v2-act1-train-v1.json \
    artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
    --report artifacts/models/sts2-v0.107.1-base-v2/training-report.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --output-dir artifacts/trajectory-search/sts2-v0.107.1-base-v2-act1-train-v1 \
    --resume
```

Any best trajectory that reaches the boss or enters Act 2 is enough to justify a separate replay and
labeling package. A terminal victory additionally unblocks mixed terminal-value evidence once the
existing defeats are included. If no seed reaches the boss, the pilot stops; scaling the same search
is not authorized until the policy representation or environment milestone surface is audited.
