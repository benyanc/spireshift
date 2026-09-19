# Architecture

SpireShift separates game integration, decision algorithms, recording, and evaluation behind typed
contracts.

```text
environment adapter -> public observation -> legal actions
                    -> policy/search -> verified action
                    -> transition -> append-only recorder
                    -> deterministic replay and evaluation
```

## Information boundary

`Observation.public_state` is the only state available to policies and search. An adapter may keep
private engine state internally, but it cannot expose future random values or other hidden game
information through the public contract.

The versioned JSON Schemas and C# protocol records share checked fixtures. CI rejects incompatible
serialization changes and observations containing unmarked privileged fields.

## Environment backends

The seeded mock backend validates the complete pipeline. Candidate live-game and simulator backends
must pass the same contract suite before use in training or evaluation.

## Search and models

Initial tiers are policy-only, shallow, medium, and expensive. The policy/value foundation is
trained and frozen for readiness evaluation before the adaptive budget controller is introduced.
