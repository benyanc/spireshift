# Mock calibration and uncertainty evidence v1

Issue 26 makes calibration, catastrophic-error auditing, and inference-time uncertainty signals
executable. The checked result wraps the issue 24 checkpoint
`sha256:7f620aeb48248ded3842fff44a4a12397360ceb5236e87b70317e32a3bb15191` and uses the frozen
eight-run validation dataset
`sha256:3277617d15148d5b2d19408496dc06b5b90de3e71f89dccbaa7ac100cddba327`.

The checkpoint-bound hash ranking assigns seeds 20, 31, 36, and 37 to calibrator fitting. Seeds 28,
42, 44, and 49 form the disjoint audit subfold. The audit contains seven decisions, 112 independent
run-value outcomes, and 176 candidate-conditioned tactical-risk outcomes. No test run is loaded.

The fitted affine-logit transforms are:

| Head | Slope | Intercept | Fit outcomes | Positive rate |
|---|---:|---:|---:|---:|
| Run value | 1.788996 | 0.224529 | 112 | 0.750000 |
| Tactical death risk | 1.291829 | -0.326704 | 176 | 0.085227 |

The separate audit result is:

| Head and metric | Raw | Calibrated |
|---|---:|---:|
| Run-value Brier score | 0.229812 | 0.247588 |
| Run-value log loss | 0.649692 | 0.693878 |
| Run-value expected calibration error | 0.101903 | 0.129396 |
| Run-value prediction variance | 0.007402 | 0.012265 |
| Tactical-risk Brier score | 0.133283 | 0.148790 |
| Tactical-risk log loss | 0.392404 | 0.436315 |
| Tactical-risk expected calibration error | 0.050591 | 0.109262 |
| Tactical-risk prediction variance | 0.012898 | 0.005296 |

Calibration worsens every proper scoring rule in this small audit. This negative result is retained
as evidence that four tiny fit runs cannot support a strength claim and that calibration must be
judged out of sample. The implementation result is the reproducible measurement boundary, not an
assertion that this particular transform should be promoted.

Policy agreement on the audit subfold is 0.857143 with zero measured independent value regret.
Three choices exceed the 0.8 confidence threshold, and none crosses the 0.1 catastrophic-regret
threshold. One of seven decisions is a false-safe tactical-risk error: its calibrated selected risk
is at most 0.2 while at least half of its independent outcomes die within the configured horizon.

The calibration artifact identity is
`sha256:04e1a78f91f8c72d3ce0125a8981494fd189dec96d340bd3699e5c4f5e5e61ca`. The report identity
is `sha256:ee800395c256a8a678682fcd7c37036d66874d49453e67e91b565cc4c003d08e`.
The report includes each audit decision's eight uncertainty proxies, chosen and teacher actions,
disagreement, independent regret, empirical tactical risk, and failure flags.

Tests regenerate both artifacts exactly, prove complete-run subfold disjointness, check bounded and
candidate-aligned inference signals, validate strict JSON Schemas, reject identity tampering, and
exercise fitting and verification through the command line.

The artifacts carry claim scope `mock_pipeline_validation`. They demonstrate the intended
calibration and uncertainty audit on a two-decision mock environment. They do not establish useful
STS2 calibration, base-model readiness, or the predictive value of these signals for allocating
search.
