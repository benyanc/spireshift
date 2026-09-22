# Production training backend

SpireShift projects the pinned
[`evangambit/sts2@37e4264`](https://github.com/evangambit/sts2/commit/37e4264115546b6ac640d54aab3d7e2ac6983d2d)
full-run environment into the same `EnvironmentAdapter` contract used by the mock pipeline. The
upstream repository and compiled library remain external. No game binaries, generated native
libraries, or decompiled sources are stored here.

## Boundary

The adapter allowlists public run information, preserves the upstream public observation vector,
maps phases to SpireShift decision types, and enumerates legal integer actions. Cards and implemented
potions that require an enemy target become separate `(action, target)` candidates. A faithful clone
reproduces the exact future for replay; a search clone resamples only information the player has not
observed.

EvanGambit's shaped reward is private to its own training code. SpireShift discards it at the
boundary and emits `1` only for a terminal victory and `0` otherwise. Seeds, RNG state, hidden draw
order, future encounters, future rewards, and native handles never enter `public_state`.

The normal loader accepts only an `admitted` manifest. Conformance is the sole path that may open a
`pending_conformance` manifest. Loading fails on a different upstream revision, tracked local source
changes, patch identity drift, adapter-source drift, native-library drift, missing optional
dependencies, or an unsupported host artifact.

## Reproduce admission

Clone and build the immutable upstream revision outside this repository:

```bash
git clone https://github.com/evangambit/sts2.git /path/to/evangambit-sts2
git -C /path/to/evangambit-sts2 checkout 37e4264115546b6ac640d54aab3d7e2ac6983d2d
bash /path/to/evangambit-sts2/scripts/build.sh osx-arm64
uv sync --extra evangambit
```

Capture the installed authoritative game identity and run the contract through the pending
manifest:

```bash
uv run spireshift doctor --manifest artifacts/local/sts2-installation.json
uv run --extra evangambit spireshift backend conformance \
  /path/to/evangambit-sts2 \
  --manifest manifests/patches/sts2-v0.107.1-evangambit-37e4264.json \
  --seeds 1 7 \
  --output artifacts/backend/evangambit-conformance.json
```

Admission creates a new content-addressed manifest; it never edits the pending manifest:

```bash
uv run --extra evangambit spireshift backend admit \
  /path/to/evangambit-sts2 \
  --conformance artifacts/backend/evangambit-conformance.json \
  --installation artifacts/local/sts2-installation.json \
  --report artifacts/backend/evangambit-admission.json \
  --admitted-manifest artifacts/backend/evangambit-admitted.json
uv run spireshift backend verify \
  artifacts/backend/evangambit-admission.json \
  --manifest artifacts/backend/evangambit-admitted.json
```

The checked macOS arm64 run passed identity, deterministic reset, action enumeration, stepping,
illegal-action isolation, faithful cloning, hidden-state resampling, replay, public-state isolation,
and terminal-reward checks. Its evidence is
[`evangambit-v0.107.1-spireshift-admission.json`](evidence/evangambit-v0.107.1-spireshift-admission.json).

## Scope

Admission is specific to STS2 v0.107.1, upstream revision `37e4264`, the recorded SpireShift adapter
digest, and the recorded macOS arm64 native library. Other platforms and later patches require their
own compiled-artifact fingerprints and fresh evidence.

The upstream evidence still reports six legacy captures without per-turn hands, 182 reachable cards
without live play captures, 46 later ancient relics without implementations, and approximate Neow,
shop, reward, and event odds. Admission means this exact stack may produce explicitly identified
training data. It does not turn those limitations into exact mechanics or remove them from benchmark
denominators.
