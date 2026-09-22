# EvanGambit v0.107.1 SpireShift admission

Issue #70 evaluated the pinned `evangambit/sts2@37e4264` full-run environment through the
SpireShift adapter on the project's Apple silicon host. The installed authoritative game, upstream
source, adapter source, compiled NativeAOT library, interface schemas, and patch were each bound by
the resulting manifest.

The contract ran complete seeded trajectories for seeds 1 and 7. All ten mandatory checks passed:

| Check | Result |
| --- | --- |
| Patch and ruleset identity | Pass |
| Deterministic reset | Pass |
| Legal-action enumeration | Pass |
| Legal stepping | Pass |
| Illegal-action isolation | Pass |
| Faithful cloning | Pass |
| Hidden-state resampling | Pass |
| Exact replay | Pass, 9 decisions |
| Public-state isolation | Pass, 20 observations |
| Binary terminal-victory reward | Pass, 18 decisions |

The adapter deliberately replaced EvanGambit's shaped intermediate reward with the project objective:
zero on every non-winning transition and one only on terminal victory. Hidden seeds, RNG state,
future content, and native handles were absent from the projected observations.

The admitted manifest is specific to macOS arm64 and the native library with SHA-256
`7121ced81b7004c848910966706c5d85e42442652da0f29426b697c1e2397e06`. The executable admission
record is
[`evangambit-v0.107.1-spireshift-admission.json`](evangambit-v0.107.1-spireshift-admission.json),
and the underlying contract result is
[`evangambit-v0.107.1-spireshift-conformance.json`](evangambit-v0.107.1-spireshift-conformance.json).

This evidence does not establish complete simulator fidelity. Six legacy captures omit per-turn
hands, 182 reachable cards lack live play captures, 46 later ancient relics remain unimplemented,
and Neow, shop, reward, and event odds include approximations. Those limitations remain in dataset
provenance and benchmark denominators.
