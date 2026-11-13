#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

spireshift_assessment_config=configs/native-assessment/sts2-v0.111.0-a8-pilot-v5-v1.json
IFS=$'\t' read -r spireshift_pilot_workspace spireshift_assessment_workspace spireshift_wall spireshift_cpu spireshift_storage spireshift_memory < <(
  uv run --no-sync python - "$spireshift_assessment_config" <<'PY'
import json, sys
with open(sys.argv[1]) as stream:
    recipe = json.load(stream)
with open(recipe["experiment_config"]) as stream:
    experiment = json.load(stream)
limits = recipe["resource_limits"]
print("\t".join(str(v) for v in (experiment["workspace"], recipe["workspace"],
    limits["wall_seconds"], limits["cpu_seconds"], limits["storage_bytes"],
    limits["resident_memory_bytes"])))
PY
)

if [[ ! -f "$spireshift_pilot_workspace/summary.json" ]]; then
  printf 'The pilot has no final result yet. No partial games were read; no assessment files were created.\n'
  printf 'Let it finish and use this same command afterward. No waiting or monitoring follows.\n'
  exit 0
fi

spireshift_attempt=1
while [[ -e "artifacts/resources/native-a8-pilot-v5-assessment-v1-attempt-$spireshift_attempt.json" || -L "artifacts/resources/native-a8-pilot-v5-assessment-v1-attempt-$spireshift_attempt.json" ]]; do
  spireshift_attempt=$((spireshift_attempt + 1))
done
printf 'Checking the finished saved pilot: same reserved seeds, original failure counts and uncertainty.\n'
printf 'Expected duration: under one minute; hard cap three minutes. No games, training or checkpoint changes.\n'
uv run --no-sync spireshift resources run \
  --kind other \
  --report "artifacts/resources/native-a8-pilot-v5-assessment-v1-attempt-$spireshift_attempt.json" \
  --artifact-root "$spireshift_assessment_workspace" \
  --workers 1 \
  --max-wall-seconds "$spireshift_wall" \
  --max-cpu-seconds "$spireshift_cpu" \
  --max-storage-bytes "$spireshift_storage" \
  --max-memory-bytes "$spireshift_memory" \
  -- \
  uv run --no-sync python -m spireshift.native_pilot_assessment "$spireshift_assessment_config"
