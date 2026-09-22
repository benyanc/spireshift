# Experiment resources, caps, and cost

Every result intended for comparison or publication must have a content-addressed
`experiment-resources-v1` sidecar. The resource wrapper launches the experiment as an exact argument
vector without a shell and monitors the complete process tree.

The report automatically captures:

- operating system, architecture, Python version, CPU model and core counts, total memory, and
  NVIDIA GPU identity when `nvidia-smi` is available;
- worker count, process-tree CPU seconds and CPU hours, wall time, average CPU utilization, peak
  resident memory, process count, and final and peak artifact storage;
- trajectories, simulations, transitions, and their throughput when the child writes the
  `experiment-metrics-v1` file;
- GPU seconds/hours and energy only when a measurement source supplies them;
- configured CPU, GPU, storage, and electricity rates plus component costs, a known subtotal, and
  an explicit list of missing measurements or rates.

SpireShift's teacher, model-training, calibration, DAgger, tactical benchmark, rollout,
search-worker, fixed-search, and mock benchmark commands write their available counters automatically
when the wrapper provides a metrics path. They do not invent GPU time or energy measurements.

Copy the example rates and replace them with the rates that apply to the machine or provider:

```bash
cp configs/cost-rates.example.toml artifacts/local/cost-rates.toml
```

The checked example values are documentation, not project defaults. A run without configured rates
keeps cost components `null` and marks the cost estimate incomplete.

Run a teacher-generation job with hard caps:

```bash
uv run spireshift resources run \
  --kind teacher_generation \
  --report artifacts/resources/teacher-v0.107.1.json \
  --metrics artifacts/resources/teacher-v0.107.1-metrics.json \
  --artifact-root artifacts/teacher/v0.107.1 \
  --workers 8 \
  --rates-config artifacts/local/cost-rates.toml \
  --rate-profile local \
  --max-wall-seconds 21600 \
  --max-cpu-seconds 100000 \
  --max-storage-bytes 50000000000 \
  --max-memory-bytes 32000000000 \
  -- \
  uv run spireshift teacher generate-mock \
    artifacts/teacher/v0.107.1/train.json \
    --runs 100
```

The wrapper returns exit code 124 when a cap fires. It terminates descendants and does not delete the
artifact roots, so append-only records and atomic checkpoints already written remain available. The
resource report names the triggered resource, configured limit, observed value, command exit code,
and whether partial artifacts were preserved. Experiment writers remain responsible for atomic or
append-only file formats.

Verify the report identity and internal hour/second relationships with:

```bash
uv run spireshift resources verify artifacts/resources/teacher-v0.107.1.json
```

Use `spireshift resources hardware` before a large run to inspect which hardware fields can be
captured. CPU utilization is measured directly. GPU use and energy remain missing unless the runtime
or an external meter writes them into the metrics file; missing means unavailable, never zero.
