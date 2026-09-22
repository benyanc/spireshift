# Isolated search workers

Search simulations run in fresh operating-system processes. A task contains no live engine object or
hidden state. It contains a backend identity and a public checkpoint made from the run seed, public
action-ID prefix, patch and ruleset identities, and expected public state hash.

Each worker performs these steps:

1. Load the admitted backend inside its own process.
2. Reset to the run seed and replay the public action prefix.
3. Require the restored patch, ruleset, and public state hash to match the checkpoint.
4. Clone that state with one explicit hidden-world seed.
5. Require public legal actions and the source observation to remain unchanged.
6. Apply the candidate action and continue under the declared policy until terminal or the hard
   transition limit.

The worker writes its result with exclusive creation. Its evidence includes the process ID, request
digest, CPU and wall time, sampled-world count, simulated transitions, terminal outcome or
truncation, and final public state hash. A timeout, abnormal exit, stale checkpoint, identity drift,
or malformed result stays in the requested-task denominator.

Prepared task documents use `search-simulation-task-v1`. Run them with bounded concurrency:

```bash
uv run spireshift search workers artifacts/search/tasks/*.json \
  --workers 4 \
  --worker-timeout 120 \
  --output-dir artifacts/search/workers/my-batch
```

The `mock` backend needs no paths. An `evangambit` task supplies the pinned upstream checkout and
admitted manifest paths; every worker independently applies the admission checks before restoring
the checkpoint.

Audit a saved batch with:

```bash
uv run spireshift search verify-workers \
  artifacts/search/workers/my-batch/search-worker-report.json
```

Verification checks paths, request and result digests, identities, aggregate crash and throughput
metrics, then deterministically reruns every completed task. Rerunning a large production batch is a
user-invoked long-running operation. The checked two-task mock fixture exercises this audit in CI.

The current design creates one process per simulation for strict failure isolation and portable
behavior across macOS, Linux, and Windows. The fixed-budget search layer can batch tasks through this
interface. If process startup becomes material in the compute-quality benchmark, a later persistent
worker implementation must preserve the same immutable checkpoint, timeout, and evidence contracts.
