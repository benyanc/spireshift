# Mock initial-model evidence v1

Issue 24 makes the initial policy, run-value, and tactical-risk learning path executable. The checked
result uses the frozen mock split and preserves the test partition for future final evaluation.

The training dataset contains 12 complete runs and 21 decision records from seeds
`0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12`. The held-out validation dataset contains eight complete
runs and 14 decision records from seeds `20, 28, 31, 36, 37, 42, 44, 49`. Each teacher uses 16 UCB
search simulations per decision and 16 separate evaluation rollouts per candidate. The training and
validation dataset identities are respectively
`sha256:2f6c4ba9293442283520cd8f718b2a47974c84c730e265a1475211f596fe4144` and
`sha256:3277617d15148d5b2d19408496dc06b5b90de3e71f89dccbaa7ac100cddba327`.

The sparse factorized model trained for 80 epochs with learning rate 0.03, L2 regularization
0.0001, a 256-bucket base vector, a 512-bucket state-candidate interaction vector, and shuffle seed
0. Its three training losses decreased from the first to the final epoch:

| Head | First epoch | Final epoch |
|---|---:|---:|
| Policy cross-entropy | 0.387136 | 0.355168 |
| Run-value cross-entropy | 0.679303 | 0.629900 |
| Tactical-risk cross-entropy | 0.583748 | 0.353477 |

The disjoint validation result is:

| Metric | Result |
|---|---:|
| Policy action agreement | 0.928571 |
| Policy cross-entropy | 0.361905 |
| Mean independent value regret | 0.000000 |
| 95th-percentile independent value regret | 0.000000 |
| Run-value mean absolute error | 0.176401 |
| Run-value Brier score | 0.205900 |
| Run-value expected calibration error | 0.108212 |
| Tactical-risk Brier score | 0.107614 |
| Tactical-risk expected calibration error | 0.058785 |

Run-value calibration contains 224 raw independent binary outcomes. Tactical-risk calibration
contains 352 candidate-conditioned outcomes. The full report preserves the populated calibration
bins rather than only the aggregate scores.

The model checkpoint identity is
`sha256:bd456c18339fc12a41eb909df5182fdfd48c29e5e779f1b44823e22d85333360`. The training-report
identity is `sha256:7b86564d66224886706495662cf0b1bcc856a5cbfc69924e5040f8b32a418e44`.
Contract tests validate both documents against strict JSON Schemas. Unit tests regenerate them
exactly, verify deterministic training and improving losses, round-trip candidate-aligned
predictions, reject train/validation misuse, reject identity tampering, and exercise the training and
verification commands.

The report labels its claim scope `mock_pipeline_validation`. The mock game has very few states and
actions, so the high agreement and zero sampled regret are evidence that the learning and audit
pipeline is coherent, not evidence of useful Slay the Spire 2 strength or readiness for adaptive
search.
