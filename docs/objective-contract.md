# Objective contract

Every experiment must declare a versioned objective. The initial contract is
`terminal-victory-v1`.

## Primary reward

```text
victory = 1
loss = 0
nonterminal transition = 0
```

The optimization target is terminal victory under a whole-run compute constraint. Training may
use auxiliary prediction losses, but auxiliary events must not contribute to environment reward.

## Compute constraint

Compute is accumulated across the complete run. Every decision records its tier, simulation count,
CPU time, and wall time when available. Comparisons must report both algorithmic work and measured
runtime on named hardware.

## Tactical-to-run valuation

Combat search evaluates persistent post-combat states using the run-value model. Immediate HP is a
diagnostic and model input, not the tactical search objective in isolation.

## Changes

Changing the primary reward, terminal condition, or compute constraint requires:

1. a new objective identifier;
2. an architecture decision record;
3. updated contract tests;
4. separate reporting from earlier experiments.
