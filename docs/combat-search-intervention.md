# Single-intervention combat-search diagnostic

The paired threshold sweep verified the search implementation but rejected every action-changing
configuration. Greedy search reduced mean maximum floor from 7.75 to 6.75. A 0.05 advantage gate
reduced it to 7.125. The 0.10 and 0.20 gates produced identical action traces, spent about 45 times
the base policy's decision CPU, and produced no floor or victory improvement. Fixed threshold tuning
is therefore blocked.

This diagnostic measures the causal value of individual recommendations. It follows the base-v3
checkpoint trajectory while the existing search policy runs in shadow mode. For recommendations
chosen by a deterministic content-hash reservoir, it clones the exact source state, executes exactly
one search-recommended action, and returns control to the base checkpoint for the rest of the run.
The unchanged base trajectory supplies the paired outcome.

The frozen train-owned specification uses 16 runs beginning at train offset 80. It samples at most
two recommendations per seed from each prespecified search-margin stratum: `[0, 0.01)`,
`[0.01, 0.05)`, `[0.05, 0.20)`, and `[0.20, infinity)`. This bounds the run at 128 exact-state
counterfactuals while covering weak and strong recommendations across each trajectory. Every case
records the policy probabilities, paired-world candidate values, terminal/bootstrap counts, search
cost, continuation outcome, and terminal-victory-first paired label.

The report can establish whether the existing margin contains useful override signal and whether
there are enough beneficial and harmful examples to fit an override gate. It always emits
`validation_allowed=false`; it cannot promote search, authorize validation, or support an adaptive
search claim by itself. The frozen specification is
`sha256:0af0712dbda7e31da61612f2c6fa5807d899671c42b1e354925f5a1a178dae55`.

## Next operator command

Run this one resource-capped command and return its final output. This is sustained exact-engine
work and must be started and observed by the operator. If interrupted, use a separately named
resource report and add `--resume` to the inner command; completed seed cases are verified and
reused.

```bash
uv run spireshift resources run \
  --kind rollout \
  --report artifacts/resources/combat-search-intervention-v1.json \
  --metrics artifacts/resources/combat-search-intervention-v1-metrics.json \
  --artifact-root artifacts/evaluations/combat-search-intervention-v1 \
  --workers 1 \
  --max-wall-seconds 7200 \
  --max-cpu-seconds 7200 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 16000000000 \
  -- \
  uv run --extra evangambit spireshift model evaluate-combat-search-interventions \
    configs/combat-search-intervention/sts2-v0.107.1-base-v3-train-v1.json \
    artifacts/models/sts2-v0.107.1-base-v3/checkpoint.json \
    --report artifacts/models/sts2-v0.107.1-base-v3/training-report.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --output-dir artifacts/evaluations/combat-search-intervention-v1
```
