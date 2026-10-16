# Assessing a finished native A8 pilot

The follow-up checks saved results and explains whether the selected player improved on the
reserved development seeds. It never starts a game, fits weights, selects a new checkpoint or
changes the source experiment. It shares no worker or mutable output directory with training.

The initial v4 assessment was prepared before opening its results. After the owner reported the
stopped run, assessment v2 adds worker-error details and corrects the confirmation-selection
audit. The original v4 runner, learner, helpers, environment, score and seed manifest remain
unchanged. See [the v4 stop report](native-a8-pilot-v4-stop.md).

## One command after the pilot finishes

```bash
bash scripts/assess-native-a8-pilot-v4.sh
```

Expect under a minute; the explicit cap is three minutes, 180 CPU seconds, 1 GB memory and
100 MB assessment output. The wrapper reads source/output paths and limits from its recipe.
If the final pilot summary does not exist, it exits immediately without reading partial games,
creating assessment output, waiting or polling. A stopped pilot receives a stopped-status report
with its sealed summary counts and error, without a quality comparison or episode-audit claim.

For a finished pilot, output is saved separately under
`artifacts/native-assessments/sts2-v0.111.0-a8-pilot-v4-v3/`: `report.md` is the readable result;
`report.json` contains the numerical comparison and source fingerprints. Repeating the command
verifies the existing report and its sources. It does not silently overwrite an interrupted or
changed assessment. Resource reports remain separate under `artifacts/resources/`.

## What the assessment checks

- Reconstruct every planned panel and its original denominator. Missing/extra cases, crossed
  seed partitions or duplicated native seeds invalidate a completed comparison.
- Verify native ending flags, case/trace hashes, worker delivery-audit hashes, source-at-launch
  bytes, checkpoint/update lineage and the fixed whole-run CPU budget. Historical source bytes
  are checked against their frozen recipe; later edits to the current learner do not relabel
  old experiments or require a historical run to use today's source hashes.
- Check the model, public menu, action index, temperature and RNG binding for each saved choice.
  Evaluation streams must match the recipe and pair the same run seed across checkpoints.
- Audit the original confirmation-only selection rule and the saved selection freeze. Development
  results never select a replacement model. Training updates must count only clean training
  games and their recorded selections.
- Report failures by seed, error, reached floor and final decision family; show action-family
  coverage and PPO diagnostics separately. Repeated-state counts are diagnostics, not proof
  that an action or the policy was wrong.

The assessment rechecks saved delivery audits and their source hashes. It does not rerun the
engine, independently replay native mechanics or recompute policy probabilities/gradients.
Raw game observations remain private, outside Git.

## How to interpret the result

Full-game wins are primary. Each player's reserved win rate has a two-sided exact binomial 95%
interval. A conservative 95% interval for selected-minus-initial win rate combines 97.5% exact
marginal intervals using the union bound; it remains valid with dependence within a paired seed.
Zero observed wins must not produce a zero-width victory interval.

Floor progress is auxiliary. The main floor comparison gives a failed game zero progress and
uses every originally planned seed in the denominator. Reached-before-failure and completed-only
means are separately named diagnostics. This does not rewrite the original pilot's saved metrics
or confirmation selection. Selection uses wins first, then the declared bounded auxiliary
return, then completion rate; failed games receive zero auxiliary return. The exploratory floor
interval resamples complete paired seeds, using 2,000 fixed-seed percentile-bootstrap replicates;
it does not resample individual decisions or count repeated confirmations as new seeds.

The result distinguishes evidence of more wins, auxiliary progress only and no clear improvement.
Sixteen development seeds and one action-RNG stream per seed are a small pilot. Neither a floor
gain nor a few observed wins completes the foundation scorecard. No result here automatically
promotes a model, grants base readiness, enables adaptive thinking or starts a larger experiment.
Greedy-policy quality remains a separate check before readiness; v4 explicitly evaluates its
categorical distribution at temperature 0.8.

## Historical regression

A separate v3 assessment recipe tests the finished historical pilot without new games. It
verifies all 336 saved attempts and preserves its four failures: both development players have
zero wins in 16 seeds; the selected mean floor is 8.625 versus 7.4375 with failures scored zero.
The paired difference is +1.1875 floors; the fixed exploratory 95% interval is
[-1.1875, +3.3125], so improvement remains inconclusive. The old reached-floor mean remains 8.75.
This is verification of an already inspected result, not a new blind evaluation or v4 evidence.

### Correction to the initial selection audit

Assessment v1 incorrectly substituted reached-floor averages for the learner's exact auxiliary
score when checking checkpoint selection. That could misidentify the selected checkpoint when
acts differ, failures occur or saturation changes an average's ordering. V2 recomputes each saved
outcome using the frozen `TrainingScoreSpec`, including acts, the saturating floor term and zero
return for failures, and verifies the exact confirmation ranking. A synthetic reversal test
catches the old shortcut. The v3 selected checkpoint and its quality conclusion are unchanged.
V4 never reached development evaluation and receives no quality verdict. Original v1 recipes
and reports remain preserved; the wrapper now uses separate v2 recipes and outputs.

The v3 assessment source fingerprints, report identity, resources and timings are recorded in
`docs/evidence/native-a8-pilot-assessment-v1.json`; the correction and stopped v4 result are in
`docs/evidence/native-a8-pilot-v4-stop-v1.json`. Synthetic tests cover corrupted evidence,
seed/RNG ownership, native-ending consistency, failed-game scoring, missing attempts, live-result
protection, cached verification, historical source preservation and zero-win uncertainty.

## Completed v5 assessment

The owner completed v5 and Codex already ran `scripts/assess-native-a8-pilot-v5.sh` under a
three-minute cap. Its separate v1 recipe/report preserve the existing assessment policy and
current source bytes. All 336 attempts and 1,427 saved files verify. The initial checkpoint
was retained, so development-selected is the same model/RNG as development-initial. Read
[the v5 result](native-a8-pilot-v5-result.md) before interpreting a zero paired floor difference
as a trained-model comparison. This post-result audit starts no games or updates.
