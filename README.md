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
7. fixed-seed benchmark reporting.

No game binaries or proprietary assets are stored in this repository. Live-game integration will
be implemented as a thin read-only adapter after the environment bakeoff.

## Quick start

```bash
uv sync
uv run spireshift doctor
uv run spireshift doctor --manifest artifacts/local/sts2-installation.json
uv run spireshift demo --seed 7
uv run spireshift benchmark --episodes 100
uv run spireshift check
```

Generated runs are written under `artifacts/`, which is intentionally ignored by Git.

Game detection searches every configured Steam library. Set `SPIRESHIFT_GAME_DIR` to require a
specific installation. The optional manifest command writes only paths, release/runtime metadata,
file sizes, and hashes; it never copies game binaries, assets, saves, or decompiled content.

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
