# Environment conformance and differential fidelity

`environment-conformance-v1` is the admission contract for every SpireShift environment. It tests
the same public interface regardless of whether the backend is the installed game, an exact worker,
or a fast simulator.

## Contract checks

The suite runs each check in isolation and records failures as report data:

1. environment, ruleset, and observation patch identities agree;
2. same-seed resets reproduce the public observation and legal actions;
3. legal actions are non-empty where required, unique, serializable, and idempotent;
4. legal steps preserve transition linkage and produce valid self-hashed observations;
5. illegal actions are rejected without changing the next transition;
6. faithful clones are independent and produce identical successors;
7. hidden-resampled clones can produce a different plausible future;
8. recorded actions replay every public transition exactly;
9. public state is serializable and excludes RNG, seeds, hidden/future fields, and privileged data;
10. rewards remain binary and positive only on terminal victory.

A check is `pass`, `fail`, or `inconclusive`. A missing observation of stochastic divergence is
inconclusive rather than silently passing. Any failed check fails the report.

```bash
uv run spireshift conformance run-mock \
  --output artifacts/conformance/mock-report.json
```

## Differential traces

The trace format contains only public observations, complete legal-action sets, selected actions,
successors, and terminal outcomes. The comparator first requires the same patch, observation/action
schemas, information policy, and seed. Incompatible traces receive an `incomparable` verdict.

For comparable traces, every field and decision is checked. A mismatch report contains the exact
JSON path and expected/actual values. Reports say when their configured divergence limit truncates
the output.

```bash
uv run spireshift conformance trace-mock \
  --seed 7 --fixture-id reference \
  --output artifacts/conformance/reference.json
uv run spireshift conformance trace-mock \
  --seed 7 --fixture-id candidate \
  --output artifacts/conformance/candidate.json
uv run spireshift conformance compare \
  artifacts/conformance/reference.json \
  artifacts/conformance/candidate.json \
  --output artifacts/conformance/differential.json
```

Raw game captures remain outside this repository. Future exact adapters will project them into this
public trace format after the information-boundary audit in issue #15.

## EvanGambit v0.107.1 evidence

The pinned `evangambit/sts2@37e4264` source was built locally on macOS arm64 and evaluated against
its committed v0.107.1/build 23811903 live-game captures. The content-addressed evidence inventory
is [evangambit-v0.107.1-conformance.json](evidence/evangambit-v0.107.1-conformance.json).

- 4,801 of 4,802 C# tests passed; the single skip is an explicitly opt-in performance probe.
- All 31 native-boundary, cloning, replay, and observation-layout tests passed.
- The live-fixture suite ran 426 checks: 420 passed and six legacy per-turn-hand checks were skipped
  because those captures predate hand recording.
- No divergence was observed in the executed fixtures, and the upstream divergence catalog had no
  open item at the pinned revision.
- The same live-fixture suite fails to import on Python 3.11 because the pinned source uses Python
  3.12 f-string syntax despite declaring Python 3.11 support.

This is a conditional result over the captured surface. It does not establish complete fidelity.
The upstream evidence itself identifies uncaptured reachable cards, unimplemented later relics, and
incomplete exact odds. The ruleset remains `pending_conformance` until a SpireShift adapter passes
this contract and its public projection is compared with authoritative traces.
