# Architecture

SpireShift separates game integration, decision algorithms, recording, and evaluation behind typed
contracts.

```text
patch manifest -> environment adapter -> public observation -> legal actions
                                     -> policy/search -> verified action
                                     -> transition -> append-only recorder
                                     -> identity-checked replay and evaluation
```

Every environment exposes an immutable ruleset identity derived from its patch manifest. The runner
rejects patch drift before recording and during transitions. A replay refuses to proceed unless its
recorded engine, adapter, mechanics, schemas, and information policy match the active environment.

## Information boundary

`Observation.public_state` is the only state available to policies and search. An adapter may keep
private engine state internally, but it cannot expose future random values or other hidden game
information through the public contract.

The versioned JSON Schemas and C# protocol records share checked fixtures. CI rejects incompatible
serialization changes and observations containing unmarked privileged fields.

## Environment backends

The seeded mock backend validates the complete pipeline. Candidate live-game and simulator backends
must pass the same contract suite before use in training or evaluation.

[ADR 0002](decisions/0002-environment-and-solver-bakeoff.md) selects a two-engine stack:

- STS2 Headless/Connector provides the frozen authoritative reference, with `sts2-cli` as the
  active exact-engine upstream;
- the EvanGambit NativeAOT emulator provides cheap cloning and full-run training/search;
- differential traces admit each emulator patch before its data is used for reported results.

The v0.107.1 EvanGambit stack is pinned but remains `pending_conformance`; a matching game version is
necessary evidence, not proof of simulator fidelity.

Third-party observation formats never flow directly into a policy. Each backend is projected into
SpireShift's versioned public contract, and every unsupported decision or divergence is recorded.

The first live projection uses the pinned STS2MCP v0.4.0 read endpoint for the installed v0.107.1
build. Its SpireShift transport exposes GET only, requires a local origin, verifies game and bridge
identity, and fails closed on unaudited top-level fields. Live action delivery is a separate
transactional boundary so state capture cannot accidentally mutate the game.

## Search and models

Initial tiers are policy-only, shallow, medium, and expensive. The policy/value foundation is
trained and frozen for readiness evaluation before the adaptive budget controller is introduced.
