# Search compute-versus-quality benchmark

The first production search benchmark asks whether additional root-search computation improves the
chosen action on held-out STS2 combat states. It compares the existing `shallow`, `medium`, and
`expensive` fixed budgets before any learned compute allocator is introduced.

This is a validation experiment. It can guide search and model development, but it cannot support a
final test-set or adaptive-search claim.

## Frozen denominator

The production split is frozen in
`manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json`. It assigns 1,000 complete
run seeds to 800 train, 100 validation, and 100 sealed test runs with SHA-256 ranking. Its manifest
ID is `sha256:389533a4a7b4eaf6aa7895cf0a96210834f2ada70610e42595e0b2d050e6f8a4`.

The first benchmark state set is frozen in
`manifests/benchmarks/sts2-v0.107.1-evangambit-validation-v1.json`. It takes combat-decision index
zero from the first 32 ranked validation runs. Its state-set ID is
`sha256:0d1acac2c99daad3b87f236e370c809bcc5a6b51c4dac1a0a1e7f3f395779076`.

Each case also freezes the expected public state hash and legal-action count under
`terminal-victory-search-rollout-v1`. Execution fails the case if capture later reaches different
public state, even when its run seed and combat index still match.

Every listed case remains in the denominator. Capture errors, worker failures, timeouts, truncations,
malformed evidence, and replay failures cannot silently remove a difficult state. Future training
data for this ruleset must use only seeds assigned to the train partition.

The source specification can be re-frozen and checked against the split with:

```bash
uv run spireshift search freeze-benchmark-states \
  configs/search-benchmark/sts2-v0.107.1-evangambit-validation-v1.json \
  /tmp/sts2-search-validation-v1.json \
  --split-manifest \
  manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json
```

The command refuses any case whose complete run is outside the validation partition.

## Experimental controls

Each case restores one public combat checkpoint and runs all three search tiers. The tiers use nested
simulation prefixes, so a larger budget contains the smaller budget's action/seed assignments.
The production budgets are 32, 64, and 256 simulations. A preflight of all frozen states observed
between 5 and 17 legal root actions, so the 32-simulation tier visits every candidate at least once.

Search does not grade itself. A separate evaluation seed domain gives every legal candidate the
same 64 held-out seeds. These paired candidate samples are disjoint from every search seed. Failed
or truncated evaluation samples count as terminal-value zero. This conservative rule prevents a
fragile candidate from improving because its failures disappeared.

For every tier, the report records:

- independently evaluated terminal value and regret from the best candidate;
- whether the selected action ties for the independent best;
- predicted and observed death risk, Brier score, and aggregate expected calibration error;
- simulations, transitions, worker CPU time, decision wall time, and p50/p95/p99 wall time; and
- act completion, post-action HP, and final HP as diagnostics only.

The optimized quantity remains terminal full-run victory. Act and HP measurements do not replace
the objective.

## Production execution

The admitted simulator checkout and manifest are local ignored artifacts:

- `artifacts/backend/evangambit-v0.107.1`
- `artifacts/backend/evangambit-v0.107.1-admitted.json`

Run the benchmark through the resource wrapper. This is a sustained job and should be started and
observed by a person:

```bash
uv run spireshift resources run \
  --kind benchmark \
  --report artifacts/resources/search-compute-quality-v0.107.1.json \
  --metrics artifacts/resources/search-compute-quality-v0.107.1-metrics.json \
  --artifact-root artifacts/search/compute-quality-v0.107.1 \
  --workers 8 \
  --max-wall-seconds 14400 \
  --max-cpu-seconds 100000 \
  --max-storage-bytes 20000000000 \
  --max-memory-bytes 32000000000 \
  -- \
  uv run --extra evangambit spireshift search benchmark-fixed \
    artifacts/search/compute-quality-v0.107.1 \
    --states manifests/benchmarks/sts2-v0.107.1-evangambit-validation-v1.json \
    --backend evangambit \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --shallow-simulations 32 \
    --medium-simulations 64 \
    --expensive-simulations 256 \
    --evaluation-samples 64 \
    --workers 8 \
    --evaluation-workers 8
```

This schedules exactly 27,456 simulations: 11,264 across the three search tiers and 16,192 paired
candidate evaluations. A one-state 27-simulation integration smoke completed generation in about
six seconds on the current machine; scaling that observation suggests roughly 45–90 minutes for the
production generation job, with substantial uncertainty from run length and process startup. The
report writes realized simulation and transition totals to the resource wrapper's metrics sidecar.

Configured cost rates are optional. Add `--rates-config artifacts/local/cost-rates.toml` and
`--rate-profile local` only after creating a rate file with values that apply to the machine. Without
rates, the report keeps cost fields null and labels the cost estimate incomplete.

## Exact verification

Verification checks the state-set and report identities, all linked SHA-256 digests, backend and
ruleset identity, fixed-tier pairing, independent evaluation evidence, reconstructed metrics, and an
exact replay of every completed simulation. It is a second sustained job:

```bash
uv run spireshift resources run \
  --kind benchmark \
  --report artifacts/resources/search-compute-quality-v0.107.1-verification.json \
  --artifact-root artifacts/search/compute-quality-v0.107.1 \
  --workers 1 \
  --max-wall-seconds 43200 \
  --max-cpu-seconds 100000 \
  --max-storage-bytes 20000000000 \
  --max-memory-bytes 32000000000 \
  -- \
  uv run --extra evangambit spireshift search verify-benchmark \
    artifacts/search/compute-quality-v0.107.1/search-compute-quality-report.json \
    --output artifacts/search/compute-quality-v0.107.1/verification.json
```

The benchmark result is ready for interpretation only when `verification.json` reports `valid: true`
and both resource reports pass `spireshift resources verify`.

The one-state exact replay took about 12 seconds. The verifier currently replays simulations
serially, so the full verification may take roughly 3–6 hours. This estimate is why generation and
verification are separate user-launched jobs.

## Interpretation boundary

Thirty-two states can expose large compute-quality effects and infrastructure failures, but it does
not provide a precise estimate for every encounter, character, or patch. Calibration with only 32
selected decisions is especially provisional. The result should be reported with its denominator,
completion rate, raw per-state outcomes, and uncertainty intervals added during analysis. Search
budgets and thresholds may be chosen from this validation result; the 100-run test partition remains
sealed until those choices are frozen.
