# Paired combat-search diagnostic

The first combat-advancement discovery was valid but negative. On the same 160 train seeds as the
base-v3 terminal-frontier discovery, greedy combat search reduced mean maximum floor from 7.4563 to
6.2688, reduced floor-10-or-later runs from 27 to 9, won no runs, and used 14.77 times as much wall
time. Validation and teacher generation for that configuration are therefore blocked.

The v1 diagnostic asks which part of the selection rule caused the regression. It runs the base
checkpoint and five search variants on the same eight train-owned seeds beginning at train offset
80:

- `shadow` computes every search recommendation but always executes the base action;
- `greedy` applies every search recommendation, reproducing the rejected selection rule;
- `margin-005`, `margin-010`, and `margin-020` apply a recommendation only when its paired-world
  search value exceeds the base action by at least 0.05, 0.10, or 0.20.

All variants use identical hidden-world sampling salt, two paired worlds, an eight-transition
horizon, and the same 256-transition hard cap. The v2 configuration and policy identities leave the
completed v1 artifact unchanged.

Each immutable case records the full-run terminal result and maximum floor, action-trace identity,
decision wall and thread-CPU time, simulations, hidden-world resampling, fallbacks, every recommended
and executed override, and its selected-versus-base search margin. The report recomputes paired
floor wins, ties, and losses and progress per search CPU-hour. Shadow execution must exactly match
the base outcome on every seed. An applied threshold may advance only when it has complete terminal
runs, does not lose terminal victories, has positive paired floor improvement, wins more paired
floors than it loses, and has positive progress per search CPU-hour.

The frozen specification is
`sha256:102f5033e3f7b39d3889698dfbfbdc977d5b5047d12f91e0d8ccef0c17b106d3`.
This is a train-only diagnostic and cannot support a validation, test-set, or adaptive-search claim.

## Next operator command

Run this one resource-capped command and return its final output. The evaluator preserves completed
case artifacts for a separately named resumed resource run if interrupted. It is sustained work and
must be started and observed by the operator.

```bash
uv run spireshift resources run \
  --kind rollout \
  --report artifacts/resources/combat-search-diagnostic-v1.json \
  --metrics artifacts/resources/combat-search-diagnostic-v1-metrics.json \
  --artifact-root artifacts/evaluations/combat-search-diagnostic-v1 \
  --workers 1 \
  --max-wall-seconds 7200 \
  --max-cpu-seconds 7200 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 16000000000 \
  -- \
  uv run --extra evangambit spireshift model evaluate-combat-search \
    configs/combat-search-diagnostic/sts2-v0.107.1-base-v3-train-v1.json \
    artifacts/models/sts2-v0.107.1-base-v3/checkpoint.json \
    --report artifacts/models/sts2-v0.107.1-base-v3/training-report.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --output-dir artifacts/evaluations/combat-search-diagnostic-v1
```
