#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
spireshift_config=configs/engine-qualification/sts2-v0.111.0-mechanics-coverage-v7.json
spireshift_qualification=configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json
spireshift_node="${SPIRESHIFT_NODE:-/Users/benjamin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node}"
IFS=$'\t' read -r spireshift_workspace spireshift_wall spireshift_cpu spireshift_storage spireshift_memory < <(
  uv run python - "$spireshift_config" <<'PY'
import json, sys
with open(sys.argv[1]) as stream:
    recipe = json.load(stream)
limits = recipe["resource_limits"]
print("\t".join(str(v) for v in (recipe["workspace"], limits["wall_seconds"],
    limits["cpu_seconds"], limits["storage_bytes"], limits["resident_memory_bytes"])))
PY
)
if [[ -f "$spireshift_workspace/sweep-summary.json" ]]; then
  printf 'Coverage already finished. Displaying its saved summary; no new tests or training follow.\n'
  uv run python - "$spireshift_workspace/sweep-summary.json" <<'PY'
import json, sys
from spireshift.core.manifest import manifest_identifier
with open(sys.argv[1]) as stream:
    report = json.load(stream)
assert report["report_id"] == manifest_identifier({k:v for k,v in report.items() if k != "report_id"})
print(json.dumps(report, indent=2))
PY
  exit 0
fi
spireshift_attempt=1
while [[ -e "artifacts/resources/native-mechanics-coverage-v2-attempt-$spireshift_attempt.json" || -L "artifacts/resources/native-mechanics-coverage-v2-attempt-$spireshift_attempt.json" ]]; do
  spireshift_attempt=$((spireshift_attempt + 1))
done
printf 'Rechecking all native non-mock cards and combat potions after the three sweep repairs.\n'
printf '1,849 planned checks; verified short controls are reused. No training or next experiment follows.\n'
printf 'Previous full sweep took 44 minutes. Allow roughly 40-90 minutes; hard cap four hours, 4 GB memory and 4 GB generated evidence.\n'
printf 'One native process at a time shares the frozen engine and one small interface-code cache. No app copies.\n'
printf 'Each isolated failure is preserved, its worker is proved stopped, and other cases continue.\n'
printf 'Progress prints every 25 checks and each new failure. Conditional unplayable cards are reported separately.\n'
printf 'Saved complete cases are verified and reused. An interrupted case requires inspection; it is never silently retried.\n'
uv run spireshift resources run \
  --kind other \
  --report "artifacts/resources/native-mechanics-coverage-v2-attempt-$spireshift_attempt.json" \
  --artifact-root "$spireshift_workspace" \
  --workers 1 \
  --max-wall-seconds "$spireshift_wall" \
  --max-cpu-seconds "$spireshift_cpu" \
  --max-storage-bytes "$spireshift_storage" \
  --max-memory-bytes "$spireshift_memory" \
  -- \
  uv run spireshift engine check-mechanics-coverage \
    "$spireshift_qualification" "$spireshift_config" --node "$spireshift_node" --stage sweep
