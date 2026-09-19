# ADR 0001: Terminal victory and foundation-first development

## Status

Accepted.

## Decision

SpireShift optimizes terminal full-run victory subject to a whole-run compute constraint. Act
completion and short-term resources are auxiliary signals. Adaptive search begins only after the
base policy/value system passes a frozen readiness evaluation.

## Consequences

- Environment rewards are terminal and binary.
- Experiment configurations require an objective specification.
- Combat search connects to run value rather than optimizing HP alone.
- Curriculum metrics cannot become headline results without being labeled incomplete.
- The adaptive-controller milestone depends on a formal base-model gate.
