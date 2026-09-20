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
10. deterministic and seeded legal-random unattended live play with offline run auditing; and
11. isolated parallel seeded rollouts with retries, immutable evidence, and batch replay; and
12. content-addressed complete-run train, validation, and test splits.

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
uv run spireshift live snapshot --output artifacts/live/current-snapshot.json
uv run spireshift demo --seed 7
uv run spireshift benchmark --episodes 100
uv run spireshift rollout run-mock --episodes 100 --workers 4
uv run spireshift split verify manifests/splits/mock-v1-seeds-000000-000999-v1.json
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
ruleset identity, and replay stops on an identity mismatch. The v0.107.1 EvanGambit manifest remains
`pending_conformance` until the differential suite admits it.

The [environment conformance suite](docs/environment-conformance.md) applies one executable contract
to reset, actions, stepping, cloning, replay, information isolation, and terminal reward. Its trace
comparator reports exact field-level divergences and refuses incompatible patch or information-policy
comparisons.

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

[Frozen data splits](docs/data-splits.md) bind every seed, complete run, encounter instance, and
decision record to content-addressed train, validation, and test evidence. Dataset audits reject
partial trajectories and any record assignment that disagrees with the frozen run partition.

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
