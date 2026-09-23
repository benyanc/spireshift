# SpireShift

SpireShift is a research environment and full-run agent for studying budgeted deliberation in
Slay the Spire 2.

The project asks whether an agent can maximize terminal victory while deciding both what action
to take and how much computation to spend. A strong inexpensive policy handles routine choices;
search is reserved for decisions where it is expected to improve full-run victory probability.

## Current status

The repository currently contains the research contracts and a seeded mock vertical slice:

1. environment reset and public observation;
2. legal-action enumeration;
3. terminal-victory policy;
4. whole-run compute accounting;
5. append-only run recording;
6. deterministic replay and verification;
7. fixed-seed benchmark reporting;
8. a pinned live-state projection for the installed v0.107.1 game;
9. guarded, state-bound, at-most-once live action delivery;
10. deterministic and seeded legal-random unattended live play with offline run auditing;
11. isolated parallel seeded rollouts with retries, immutable evidence, and batch replay;
12. content-addressed complete-run train, validation, and test splits;
13. mechanics-aware, candidate-aligned model inputs with a deterministic sparse vectorizer;
14. content-addressed teacher trajectories with disjoint search and evaluation samples; and
15. a deterministic three-head policy, terminal-value, and tactical-risk training baseline with
    held-out regret and calibration reporting; and
16. complete on-policy student collection with selective, cost-accounted teacher relabeling and
    verified DAgger augmentation; and
17. checkpoint-bound calibration fit/audit subfolds, proper scoring rules, catastrophic-error
    analysis, and decision-level uncertainty signals; and
18. a compute-bounded tactical-to-run value handoff with exact returns, truncated rollouts,
    run-value bootstraps, persistent-state preservation, and an HP-greedy ablation; and
19. a fail-closed EvanGambit production adapter with targeted actions, public-state projection,
    exact cloning, hidden-state resampling, and content-addressed backend admission evidence; and
20. one public mechanics service for legal actions, model features, exact rule enumeration, and
    explicitly marked hidden-world probability estimates; and
21. isolated search-simulation workers with public checkpoint restoration, hidden-world sampling,
    hard timeouts, immutable evidence, and CPU/wall-time throughput accounting; and
22. cross-platform experiment resource tracking with hard caps, hardware and throughput evidence,
    configurable cost rates, and explicit missing-measurement reporting; and
23. an EvanGambit-backed fixed root-UCT baseline with paired shallow, medium, and expensive budgets,
    terminal-victory values, failure-preserving evidence, and exact replay; and
24. a frozen validation compute-quality harness with paired independent candidate evaluation,
    terminal-value regret, death-risk calibration, compute and tail-latency metrics, and exact replay; and
25. a production bootstrap curriculum with a stronger public-state continuation policy, paired
    terminal-first candidate labels, milestone distributions, isolated workers, and resumable
    failure-preserving evidence.

No game binaries or proprietary assets are stored in this repository. Live-game integration will
remain a thin, versioned layer around a locally installed bridge.

## Quick start

```bash
uv sync
uv run spireshift doctor
uv run spireshift doctor --manifest artifacts/local/sts2-installation.json
uv run spireshift manifest verify \
  --installation artifacts/local/sts2-installation.json \
  manifests/patches/sts2-v0.107.1-evangambit-37e4264.json
uv run spireshift conformance run-mock
uv run spireshift mechanics audit-mock
uv run spireshift live snapshot --output artifacts/live/current-snapshot.json
uv run spireshift demo --seed 7
uv run spireshift benchmark --episodes 100
uv run spireshift rollout run-mock --episodes 100 --workers 4
uv run spireshift split verify manifests/splits/mock-v1-seeds-000000-000999-v1.json
uv run spireshift represent mock --seed 7 --vectorized
uv run spireshift teacher generate-mock artifacts/teacher/mock-v1.json --runs 1
uv run spireshift model verify tests/fixtures/model-checkpoint-v1.json \
  --report tests/fixtures/model-training-report-v1.json
uv run spireshift check
```

To let the weak baseline continue the visible installed game until a terminal state:

```bash
uv run spireshift live autoplay \
  --apply \
  --strategy deterministic \
  --record artifacts/live/runs/my-run.jsonl
uv run spireshift live verify-run artifacts/live/runs/my-run.jsonl
```

Generated runs are written under `artifacts/`, which is intentionally ignored by Git.

Game detection searches every configured Steam library. Set `SPIRESHIFT_GAME_DIR` to require a
specific installation. The optional manifest command writes only paths, release/runtime metadata,
file sizes, and hashes; it never copies game binaries, assets, saves, or decompiled content.

Patch manifests under `manifests/patches/` bind a game build, rule engine, adapter, mechanics
artifacts, schema versions, and information policy to an immutable SHA-256 identity. Local mechanics
files or directories can be fingerprinted with `spireshift manifest freeze SPEC OUTPUT`; their
contents and local paths are omitted from the resulting manifest. Every run records the complete
ruleset identity, and replay stops on an identity mismatch. The original v0.107.1 EvanGambit
candidate manifest remains immutable and `pending_conformance`. A separate macOS arm64 manifest
records the exact adapter and native library that passed admission; no status is inherited by
another build or patch.

The [environment conformance suite](docs/environment-conformance.md) applies one executable contract
to reset, actions, stepping, cloning, replay, information isolation, and terminal reward. Its trace
comparator reports exact field-level divergences and refuses incompatible patch or information-policy
comparisons.

The [production training backend](docs/production-backend.md) projects the pinned EvanGambit
NativeAOT environment through that contract, strips upstream shaped rewards, rejects unadmitted
identities, and documents how to reproduce the checked admission.

[Deterministic mechanics and public probabilities](docs/mechanics-services.md) give policies,
learned models, search, and advisors the same legal actions, masks, and rule-derived features. Exact
enumeration and sampled public-world estimates are distinguished in every query and audit.

The [read-only live-state adapter](docs/live-state-adapter.md) verifies the local game and bridge
identity, projects only public state, enumerates provisional legal actions, and records any omitted
source fields. Its network transport is localhost-only and has no write method.

The checked [public-state fixture audit](docs/evidence/live-fixture-audit-v0.107.1.md) covers all 18
actionable single-player state types in the pinned bridge and compares every projected action with an
independent exact oracle. Run it offline with `uv run spireshift live audit-fixtures`.

The [full-run action coverage gate](docs/evidence/live-action-coverage-v0.107.1.md) freezes The
Defect at Ascension 0, requires all 18 states, 13 decision types, and 28 action kinds, and admits only
verified terminal runs or explicitly recorded unsupported decisions.

[Guarded live-action execution](docs/live-action-execution.md) binds every request to that exact
snapshot and legal-action ID. A durable ledger blocks duplicates and concurrent writers, while
timeouts and lost acknowledgements latch recovery instead of triggering an automatic retry.
The same safety boundary is used by the unattended loop described in that document.

[Parallel rollout infrastructure](docs/rollout-infrastructure.md) launches each seeded episode in an
isolated process, retries failures without overwriting evidence, and independently replays completed
runs. Exhausted worker crashes remain in the benchmark denominator.

[Isolated search workers](docs/search-workers.md) restore a public checkpoint inside each process,
sample one independently seeded hidden world, and record task-level crashes, CPU time, wall time,
throughput, and immutable results for fixed-budget planning.

[Fixed-budget combat search](docs/fixed-budget-search.md) runs nested shallow, medium, and expensive
root-UCT budgets from one public checkpoint. It records terminal-victory candidate values, stochastic
world coverage, failures, CPU and wall time, tail latency, and licensed-backend attribution.

The [production bootstrap teacher](docs/bootstrap-teacher.md) turns train-only public combat states
into paired terminal-victory and auxiliary progress targets for the first useful base policy. Its
long generation command is resource-capped, resumable, and intentionally left for a person to start.

[Search compute-versus-quality benchmarking](docs/compute-quality-benchmark.md) binds 32 production
validation states to a complete-run split, grades each legal candidate on paired held-out seeds, and
reports regret, calibration, compute, diagnostics, failures, and exact replay evidence.

[Experiment resource and cost accounting](docs/resource-accounting.md) wraps long-running commands,
captures hardware and process-tree usage, enforces optional wall/CPU/storage/memory caps, preserves
partial artifacts, and produces content-addressed cost sidecars.

[Frozen data splits](docs/data-splits.md) bind every seed, complete run, encounter instance, and
decision record to content-addressed train, validation, and test evidence. Dataset audits reject
partial trajectories and any record assignment that disagrees with the frozen run partition.

[Compositional model inputs](docs/model-representations.md) encode typed mechanics, persistent
resources, variable-length entities, decision context, and every legal candidate. Source action IDs
remain decode handles and are excluded from all model features.

[Teacher-data generation](docs/teacher-data.md) records search visits, candidate values, stochastic
variance, complete-run outcomes, and equal-budget independent action evaluations. A verifier
regenerates every sampled outcome and audits complete-run split ownership.

[Initial multi-head model training](docs/initial-models.md) distills those targets into a cheap
candidate policy, terminal run-value estimate, and candidate-conditioned tactical death risk. It
requires disjoint frozen train and validation runs and reports independently evaluated regret and
calibration in a content-addressed training report.

[Selective DAgger collection](docs/selective-dagger.md) runs the student on new complete training
runs, probes every decision cheaply, and reserves expensive labels for disagreements, rare states,
suspected confident errors, and high-entropy decisions. Verified selected labels can augment the next
model checkpoint with complete provenance.

[Calibration and uncertainty auditing](docs/calibration-and-uncertainty.md) deterministically splits
complete validation runs into calibrator-fit and audit subfolds. It reports proper scoring rules,
high-confidence catastrophic errors, false-safe risk predictions, and interpretable inference-time
signals for later value-of-computation training while leaving the final test split sealed.

[Tactical-to-run value handoff](docs/tactical-to-run-value.md) ranks combat successors by estimated
terminal victory using exact terminal outcomes, truncated continuations, and run-value bootstraps.
It binds learned artifacts to the active ruleset and objective, preserves persistent public state,
and accounts for every simulated transition and model inference.

## Objective

The binding objective is defined in [PROJECT_CHARTER.md](PROJECT_CHARTER.md) and
[docs/objective-contract.md](docs/objective-contract.md):

> Maximize terminal full-run victory probability subject to a fixed whole-run computation budget.

Act completion, floor progression, HP, and resources are auxiliary signals rather than substitute
objectives.

## Development sequence

1. Validate the environment and information boundary.
2. Build reproducible fixed-budget baselines.
3. Train and validate a strong mechanics-aware base policy/value system.
4. Pass the frozen base-model readiness gate.
5. Add fixed learned PUCT.
6. Learn per-decision and whole-run computation allocation.
7. Evaluate zero-shot and limited-data recovery across official patches.

See [docs/architecture.md](docs/architecture.md) and
[docs/benchmark-protocol.md](docs/benchmark-protocol.md).

The environment bakeoff and pinned candidate evidence are recorded in
[ADR 0002](docs/decisions/0002-environment-and-solver-bakeoff.md) and
[docs/environment-candidates.json](docs/environment-candidates.json).
