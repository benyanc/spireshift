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

## Result

The owner-run experiment completed all 384 trajectories in 191.61 wall seconds. Every run reached a
terminal defeat without a failure, cycle, decision-limit stop, or no-op fallback. The aggregate is
`sha256:0222c0d8b3fde25b37f1d0efb42ca26696829a2532c0ae42a2b0b7074c66c370`; independent
verification checked all 384 immutable cases and produced
`sha256:4f2a0b190cc6e2d5b3ddb86d7cbd6ba92a6a4254930aecd029a11fc94a9cb924`. The resource report is
`sha256:a3043da36ff376794631dc4ff428396f624e84772c65c7ee85cfe07a2b778694`.

Exploration was real rather than nominal: 1,426 of 25,723 eligible decisions selected a non-argmax
action, producing 372 unique action traces. The realized rates closely matched their frozen 2%, 5%,
and 10% targets. None of those trajectories won. Mean maximum floor also declined as exploration
increased: 7.047 at 2%, 6.930 at 5%, and 6.867 at 10%. The deepest trajectory reached floor 13;
none reached the Act 1 boss at floor 17.

This rejects sparse independent action sampling as the next improvement mechanism. The evidence does
not support increasing the rate, adding more attempts with the same sampler, fitting a terminal-value
head, or consuming held-out seeds. The next bounded objective is a train-only run-level search that
keeps and mutates promising coherent trajectories, using Act 1 boss reach and clear as auxiliary
milestones while preserving terminal victory as the final objective.

The resource wrapper was invoked without a metrics sidecar, so its trajectory and transition count
fields are null. The verified discovery aggregate supplies the exact 384-trajectory and
31,390-decision counts; the missing sidecar does not require a rerun. Future operator commands must
pass an explicit `--metrics` path.
