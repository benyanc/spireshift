#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Owner-run saved-artifact audit. This script does not train, replay, or play games.
uv run spireshift resources run \
  --kind other \
  --report artifacts/resources/trajectory-policy-base-v6-diagnostic-v2.json \
  --artifact-root artifacts/diagnostics/sts2-v0.107.1-base-v6-policy-v1 \
  --workers 1 \
  --max-wall-seconds 600 \
  --max-cpu-seconds 600 \
  --max-storage-bytes 50000000 \
  --max-memory-bytes 2000000000 \
  -- \
  uv run spireshift model diagnose-trajectory-policy \
    configs/trajectory-policy/sts2-v0.107.1-base-v2-frontier-preferences-v1.json \
    artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
    artifacts/models/sts2-v0.107.1-base-v6/checkpoint.json \
    --parent-report artifacts/models/sts2-v0.107.1-base-v2/training-report.json \
    --candidate-report artifacts/models/sts2-v0.107.1-base-v6/training-report.json \
    --collection artifacts/preferences/sts2-v0.107.1-base-v2-frontier-score-train-v1/trajectory-mutation-preference-collection.json \
    --search-report artifacts/trajectory-search/sts2-v0.107.1-base-v2-act1-frontier-score-train-v4/run-level-trajectory-search.json \
    --search-config configs/trajectory-search/sts2-v0.107.1-base-v2-act1-frontier-score-train-v4.json \
    --train-report artifacts/bootstrap/teacher-train-v2/bootstrap-teacher-dataset.json \
    --validation-report artifacts/bootstrap/teacher-validation-v2/bootstrap-teacher-dataset.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --ruleset-manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --output artifacts/diagnostics/sts2-v0.107.1-base-v6-policy-v1/diagnostic.json
