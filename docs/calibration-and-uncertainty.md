# Calibration and uncertainty

SpireShift fits probability calibration after base-model training without changing the learned
checkpoint. The resulting wrapper calibrates terminal run value and candidate tactical-death risk,
then exposes decision-level signals for later value-of-computation training.

## Complete-run validation subfolds

Calibration uses only a verified frozen `validation` teacher dataset. It deterministically ranks
complete run IDs by the checkpoint ID, a recorded salt, and the run ID, then assigns the configured
fraction to a calibration-fit subfold. Every remaining complete run enters the calibration-audit
subfold. Decisions from one run can never appear in both.

The probability transforms are fit only on the fit subfold. All reported scores, failure cases, and
per-decision uncertainty records come only from the audit subfold. These are held out from
calibrator fitting, but they remain validation data: the frozen test partition stays sealed for the
eventual readiness decision.

## Probability transforms and metrics

Run value and tactical death risk receive separate affine-logit Platt transforms:

```text
calibrated(p) = sigmoid(slope * logit(p) + intercept)
```

Run-value samples pair the state prediction with independent terminal outcomes for the teacher's
selected candidate. Tactical-risk samples pair every candidate prediction with independent
defeat-within-horizon outcomes. Search samples are never reused to grade either head.

The audit compares raw and calibrated predictions using Brier score, log loss, expected and maximum
calibration error, populated reliability bins, prediction variance, and normalized distance from
0.5. Calibration can make held-out performance worse; the report retains that result rather than
selectively suppressing it.

The failure audit also records:

- high-confidence policy choices whose independently evaluated terminal-value regret exceeds a
  recorded threshold; and
- selected actions predicted safe whose independently measured tactical-death rate exceeds a
  recorded threshold.

Thresholds diagnose errors on validation data. They are not readiness thresholds and do not change
the terminal-victory objective.

## Inference-time uncertainty signals

`CalibratedMultiHeadModel.predict` preserves candidate alignment and returns:

- normalized policy entropy;
- top-two policy margin;
- calibrated run-value ambiguity;
- selected-action calibrated tactical risk and ambiguity;
- maximum calibrated tactical risk among legal candidates; and
- absolute calibration corrections for run value and selected-action risk.

These are uncertainty proxies rather than a claim of epistemic uncertainty. They remain separate,
interpretable inputs so a later value-of-computation model can test which signals predict actual
search improvement. The calibration report joins every signal vector to teacher disagreement,
independently evaluated action regret, and empirical tactical risk.

## Reproduce and verify

After generating the validation dataset described in [initial models](initial-models.md), run:

```bash
uv run spireshift calibrate fit \
  tests/fixtures/model-checkpoint-v1.json \
  artifacts/models/mock-validation.json \
  artifacts/models/mock-calibration.json \
  --report artifacts/models/mock-calibration-report.json

uv run spireshift calibrate verify \
  artifacts/models/mock-calibration.json \
  artifacts/models/mock-calibration-report.json \
  tests/fixtures/model-checkpoint-v1.json \
  artifacts/models/mock-validation.json
```

Both artifacts are content addressed and immutable. Verification reloads their identities,
regenerates the fit/audit assignment, refits both transforms, recomputes every audit metric and
record, and requires byte-equivalent structured content. Their serialized contracts are
[model-calibration-v1.json](../schemas/model-calibration-v1.json) and
[model-calibration-report-v1.json](../schemas/model-calibration-report-v1.json).

The checked mock result is documented in
[mock calibration and uncertainty evidence](evidence/mock-calibration-v1.md).
