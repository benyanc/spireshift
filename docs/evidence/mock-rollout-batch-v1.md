# Mock parallel rollout evidence v1

The checked batch in `tests/fixtures/rollout/mock-batch-v1/` launches seeds 0 and 1 in isolated
workers against the frozen `mock-v1` ruleset.

| Measure | Result |
|---|---:|
| Requested runs / benchmark denominator | 2 |
| Completed and replay-verified runs | 2 |
| Victories | 1 |
| Worker crashes | 0 |
| Victory rate | 0.5 |

The batch report, worker results, and JSONL transition records are all checked into the fixture. The
contract suite validates their versioned JSON schemas, then independently checks file digests and
replays both seeded runs.

Failure behavior is covered separately with injected worker crashes. One test verifies that a later
attempt recovers while preserving the failed attempt. Another exhausts every attempt and proves that
both crashed seeds remain in the denominator with a zero victory rate.
