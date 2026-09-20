# Parallel rollout and replay infrastructure

SpireShift runs each seeded episode in a separate operating-system process. The coordinator limits
concurrency, gives each attempt its own directory, retries failed attempts, and writes one immutable
batch report after every requested seed reaches a final outcome.

Run 100 mock episodes across four workers:

```bash
uv run spireshift rollout run-mock \
  --episodes 100 \
  --seed-start 0 \
  --workers 4 \
  --maximum-attempts 2
```

Pass `--seeds 7 19 42` to select exact seeds or `--output-dir PATH` to choose the destination. The
default destination is a timestamped directory under `artifacts/rollouts/`.

Each attempt writes:

```text
attempts/seed-<seed>/attempt-<number>/run.jsonl
attempts/seed-<seed>/attempt-<number>/worker-result.json
```

Both files use exclusive creation and cannot replace prior evidence. Every JSONL record is flushed
to durable storage as it is appended. Each result records its worker process ID. A worker
independently replays its completed record, and the coordinator repeats that replay and digest check
before accepting the attempt. A timeout, abnormal exit, malformed result, digest mismatch, or failed
replay causes a new attempt until the configured limit is reached. Earlier attempt directories
remain intact.

The final `rollout-report.json` contains every attempt and one outcome per requested seed. Its
`benchmark_denominator` is always the number of requested seeds. Exhausted crashes therefore count
as failed runs and cannot improve the reported victory rate by disappearing from the sample. The
report separately exposes completion rate, failed attempts, worker crashes, and recovered runs.

Audit a saved batch without launching workers:

```bash
uv run spireshift rollout replay artifacts/rollouts/<batch>/rollout-report.json
```

The audit replays each supported transition and checks the record digest, ruleset, objective,
policy, controller, worker identity, attempt sequence, aggregate counts, and requested-run
denominators. It also rejects paths that escape the batch directory.

The checked fixture at `tests/fixtures/rollout/mock-batch-v1/` is a two-worker, two-seed reference
batch. Current replay support covers the deterministic seeded mock backend. New engine backends must
implement and pass their own exact transition replay before their completed runs can enter benchmark
results.
