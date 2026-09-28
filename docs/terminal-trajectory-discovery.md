# Terminal-positive trajectory discovery

The accepted base-v2 policy is reliable but has produced no victories. That makes additional
terminal-value fitting meaningless: a learner shown only defeats cannot learn the difference
between winning and losing complete runs.

This experiment tests the cheapest remaining explanation before run-level search: perhaps base-v2
is close to a viable trajectory but its deterministic argmax repeats one or two bad choices. Each
profile follows base-v2 normally and, at a frozen fraction of multi-action decisions, selects a
different legal action from the model's candidate-aligned distribution. Selection is derived from
the checkpoint, train seed, profile, attempt, decision index, and public state hash, so parallel
scheduling cannot change a trajectory.

The frozen experiment covers 64 train seeds at ranked offsets 168-231, after the production DAgger
window. It runs two attempts for each of three profiles: 2%, 5%, and 10% sparse intervention. That
is 384 complete-run attempts. Validation and test seeds are rejected by construction. Cases record
every chosen action, the model argmax, intervention evidence, terminal result, maximum floor,
liveness, and fallback behavior. Partial case files are immutable and `--resume` fills only missing
coordinates.

Run this one resource-capped command from the repository root:

```bash
uv run spireshift resources run \
  --kind rollout \
  --report artifacts/resources/terminal-discovery-base-v2-train-v1.json \
  --artifact-root artifacts/terminal-discovery/sts2-v0.107.1-base-v2-train-v1 \
  --workers 8 \
  --max-wall-seconds 7200 \
  --max-cpu-seconds 50000 \
  --max-storage-bytes 2000000000 \
  --max-memory-bytes 16000000000 \
  -- \
  uv run --extra evangambit spireshift model discover-terminal-trajectories \
    configs/terminal-discovery/sts2-v0.107.1-base-v2-train-v1.json \
    artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
    --report artifacts/models/sts2-v0.107.1-base-v2/training-report.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --output-dir artifacts/terminal-discovery/sts2-v0.107.1-base-v2-train-v1 \
    --resume
```

The aggregate recommends one of two next steps. Any winning cases are frozen for exact replay and
later labeling; terminal-value training remains blocked until both victories and defeats are
present. If the experiment finds no wins despite realizing the configured interventions, simple
sampling is rejected as the next improvement mechanism and the project moves to run-level search.
