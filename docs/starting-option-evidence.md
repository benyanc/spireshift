# Exhaustive starting-option evidence

[Issue #126](https://github.com/benyanc/spireshift/issues/126) follows the completed negative
starting-option experiment. Base-v7 trained for 47.33 seconds, but none of its 40 epochs passed
the unchanged preference-advancement checks. The best selection loss improvement was 0.000011615429,
below the required 0.001. The saved model selects epoch zero with no residual weights; accepted
base-v2 remains unchanged. This is not evidence of improved gameplay.

Only three fitting preferences and one selection preference covered starting Ancient decisions.
Public option IDs were covered; more categorical IDs alone cannot repair that small sample. The next
bounded step collects every initial option on more independent runs, instead of extracting only
the starting mutations that happened to occur on a selected beam-search lineage.

## Frozen protocol

The frozen configuration is
`configs/starting-option-evidence/sts2-v0.107.1-base-v2-train-v1.json`, with identity
`sha256:31895f922b6da640032b7f1e7e49b764d1d389e454542ede85b57e0428f34bd5`.
It binds the accepted base-v2 model/report, admitted v0.107.1 ruleset, terminal-victory objective,
corrected public-frontier ranking and 64 train seeds at offsets 248–311. A bounded saved-file
inspection confirmed that these seeds overlap neither the original base-v2 training corpus nor
the previous 16-run preference collection. Validation/test seeds are excluded.

Before observing any outcomes, the existing salted 25% selection rule assigns these **complete
runs** to 48 fitting seeds and 16 selection seeds. All options and comparisons from a seed retain
that ownership, including ties and failures. Outcomes never choose ownership. Subsequent training
must respect these explicit groups rather than repartition the successful subset.

For each seed:

1. Validate the public initial Ancient menu and bind all three legal actions to visible option IDs
   through the versioned starting-option encoder. Validate the visible resource context as well.
2. Run the exact base-v2 continuation once for its preferred starting option.
3. Reset the same seed for each of the other two options. Require the identical public source
   observation and ordered legal actions, force only decision zero, and return to base-v2 for every
   later decision. Use the existing public no-op guard and liveness limits.
4. Keep every branch and all three pair comparisons. Strict preferences can favor the original
   choice or either alternative. Keep ties explicitly; activity-only differences remain excluded
   from eligible policy preferences. A failed or truncated branch makes its run ineligible for
   labels, while retaining the other branches and the whole run in the denominator.

The upper bound is 192 complete trajectories and 192 correlated action comparisons, **not 192
independent runs**. Each option sees one exact seeded future under this fixed continuation policy.
This is conditional outcome evidence, not an estimate of expected win probability, confidence over
hidden futures, universal option quality or simulator/game equivalence. A later study may need
independent stochastic continuations; this package makes no hidden-state clones and avoids the
unresolved clone defect in #105.

Pair ordering retains terminal victory first, then Act 1 clear, boss reach and maximum floor, then
the corrected public frontier diagnostics. Actual winning branches retain their real terminal flag;
floor or HP differences are never labeled victories. No model is trained or promoted by collection,
and sufficient starting evidence does not pass the base-model readiness gate or unblock adaptive
computation.

## Prespecified evidence gate

The collection is sufficient for proposing a later training integration only when:

- all 64 cases have all three terminal, untruncated branches;
- at least 16 fitting runs have eligible strict preferences;
- at least eight selection runs have eligible strict preferences;
- at least four selection runs have terminal/floor/boss/act-clear advancement comparisons.

These are minimum coverage targets, not a statistical power claim. The report shows all checks,
ties, activity-only differences, failures, truncated trajectories, actual victories, public option
coverage and selection IDs absent from fitting. Fitting and selection remain separate; the latter
cannot extend a future fitting vocabulary. Too little signal is a completed negative result, not
permission to change thresholds, scale the identical protocol or launch training automatically.

## One owner-run command

From the repository directory, run:

```bash
bash scripts/collect-starting-option-evidence-v1.sh
```

This starts collection and saved-file verification only. It uses four workers, with caps of
**30 wall minutes**, 3,600 CPU seconds, 4 GB memory and 1 GB output. The wall cap is a limit, not a
duration prediction. The terminal reports progress every eight completed seeds and prints the
final coverage and evidence gate. Share that final summary before another experiment is prepared.

Results stay outside Git under
`artifacts/starting-options/sts2-v0.107.1-base-v2-train-v1/starting-option-evidence.json` and `cases/`.
Each attempt preserves a separate resource report under
`artifacts/resources/starting-option-evidence-base-v2-train-v1-attempt-N.json`.

If interrupted, the same script resumes only missing seeds. Complete case files are published
atomically without replacing existing files. Failed cases remain immutable evidence; retrying a
completed collection simply verifies and prints its saved report, with no further game attempts.
Recorded trajectory/transition counters exclude work lost inside exceptions; all such failures
remain explicit in the benchmark and candidate denominators and resource totals.

The verifier checks source representation/action binding, content identities, exact initial-state
alignment, baseline/alternative parentage, unchanged later policy decisions, trajectory/frontier
contracts, all pair ranks, every configured seed, file references, summaries and the sufficiency
gate. It checks saved evidence without engine replay; it does not independently certify real-game
execution. Short mock tests also cover victory-first ranking, reversed preferences, ties,
unsupported public inputs, failures, interrupted resume and completed reruns.

The coding agent has not launched real collection, training, replay or game evaluation. Owner-run
coverage and outcome evidence remain pending. A later training recipe will bind these new artifact
identities, retain the immutable parent and original all-204 development-validation limits, and
require a separate frozen full-run comparison before promotion.
