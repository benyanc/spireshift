# Starting-choice training from exhaustive evidence

[Issue #127](https://github.com/benyanc/spireshift/issues/127) uses the completed
[starting-option collection](starting-option-evidence.md) to train one small adjustment to
accepted base-v2. The earlier base-v7 experiment made no accepted update. Its starting-choice
preferences covered only three fitting runs and one selection run. The new collection passed
its frozen coverage gate: 64 complete train seeds, all 192 terminal branches, no failures or
truncations, 130 eligible fitting comparisons and 42 selection comparisons. There are still
zero full-run wins. Better coverage is permission for this bounded experiment, not proof that
the policy has improved or that terminal-value learning is ready.

## Completed owner-run result

The owner completed training and saved-input verification on 2026-10-05. Verification returned
`valid: true`, but **no epoch qualified**. Base-v8 selected epoch zero with an empty residual,
`candidate_eligible: false`, `status: rejected_or_no_update` and `checkpoint_promoted: false`.
Accepted base-v2 therefore remains unchanged. Issue #127 is complete as a negative experiment.

All 40 epochs passed the original selection-anchor safety checks. All 40 failed the frozen
overall preference-advancement requirement; 33 passed the separate strong-advancement requirement.
Epoch 40 had the best overall and strong selection losses:

| Selection diagnostic | Parent loss | Epoch-40 loss | Improvement | Required improvement |
| --- | ---: | ---: | ---: | ---: |
| Overall, 42 comparisons across 15 runs | 0.707422507714 | 0.706496113535 | 0.000926394179 | 0.001 |
| Higher-floor comparisons, 22 across 11 runs | 0.708525690942 | 0.705754127191 | 0.002771563751 | 0.001 |
| Weaker enemy-damage comparisons, 20 across 13 runs | 0.706401769408 | 0.706585494012 | -0.000183724604 | No separate gate |

Lower loss is better. Component rows overlap in complete-run ownership and do not sum directly
to the overall run-normalized loss. The learner improved some auxiliary comparisons, but the
overall gain fell short of the unchanged minimum. Selection directional accuracy rose from
12/42 to 13/42; higher-floor accuracy rose from 7/22 to 8/22. This is not evidence of improved
full-run win rate. The best epoch remains rejected; do not extend the run or lower the threshold
to accept it after seeing the result.

The final all-204 development-validation checks pass because they audit the unchanged epoch-zero
fallback, not epoch 40. All 180 later decisions remain unchanged. Fitting, selection and validation
coverage report no unknown option IDs; selection ID 132 is covered by original fitting anchors.
There are still zero positive terminal-victory labels and no promoted candidate.

The training job took 50.719 wall seconds and 38.798 CPU seconds, with approximately 517 MB peak
resident memory and 4 MB output. No resource cap was hit. Saved identities:

- Model: `sha256:ab1942b2ea4eea6aaee39724f66c41f23db7d1523573434379210b018112e0c9`.
- Training report: `sha256:da8125f404051f2251273e7ac91ff75eeacb5250f5c5fc1105fbe3f7cffebd6f`.
- Resource report: `sha256:4e94edaefb367f7e121809bc691a71c4f2eef341c1aad8a3aa6be68feef353a7`.

The owner completed the [saved-data diagnosis](starting-evidence-diagnosis.md) under
[issue #42](https://github.com/benyanc/spireshift/issues/42). It reconciles the experiment and finds
nine groups of opposing fitting lessons, with different public menus; only one group has
incompatible strict margins after parent offsets. There are no complete hashed-contrast aliases,
and the initial strong/weak gradients have a positive cosine. These observations do not establish
the cause of rejection. [Issue #128](https://github.com/benyanc/spireshift/issues/128) implements one
[bounded fresh-seed repeatability study](starting-choice-repeatability.md) before another training
intervention. Its guide has the one current owner command; collection/analysis is pending.
Any later training change needs a new frozen recipe and fresh
confirmation, since the current selection and development-validation results have been inspected.

## Archived owner command and output handling

The completed experiment used:

```bash
bash scripts/train-starting-evidence-policy-v1.sh
```

This loads and verifies the saved data, trains one starting-choice residual, saves a base-v8
candidate, and verifies the saved result. It starts no game attempts, new collection, replay,
follow-up training or full-run evaluation. The owner launches and monitors the job.

The training job uses one worker and caps of **10 wall minutes**, 1,200 CPU seconds, 4 GB memory
and 1 GB output. Ten minutes is a limit, not a duration estimate. Reading and verifying the
original curricula can take more than 30 seconds before optimization begins. The script prints
when input preparation starts and when saved-result verification begins. The final verification
reads files and recomputes diagnostics; it does not retrain or replay the game.

A rejected run is a valid completed experiment. The command is retained for reproducibility;
there is no need to run it again. With both saved outputs present, it verifies files only.

Outputs remain outside Git:

- `artifacts/models/sts2-v0.107.1-base-v8/checkpoint.json`;
- `artifacts/models/sts2-v0.107.1-base-v8/training-report.json`;
- `artifacts/resources/starting-evidence-policy-base-v8-train-v1-attempt-N.json`.

A completed rerun only verifies and displays the saved result. An incomplete checkpoint/report
pair is preserved and refused with an explanation. An interrupted attempt that published neither
output can be retried with the same script; its previous resource report remains intact and the
new attempt receives another report path. Optimization restarts from the frozen parent; there is
no partially trained checkpoint resume.

## Frozen inputs and complete-run ownership

The wrapper config is
`configs/starting-option-policy/sts2-v0.107.1-base-v2-exhaustive-evidence-v1.json`, identity
`sha256:d727ff3716365e292d097bd4a95f0ce2b5a42750c6e7a39b6745e8304f9fe2c0`.
Its evidence recipe is
`sha256:6ec3d5ede4e68067d8c23788175d9de6a9258519eec8bb66c8e5fcc25f1ab0b6`.

It binds the actual accepted parent/report, original training and development-validation curricula,
split, ruleset, objective and public encoder. It also binds the verified collection
`sha256:6b1a04ddb0190531d153a9f13a79d00d744270cd1a91f866f7cc8f2c7bb899d8`, its unchanged collection
config, and the completed base-v7 report as the source of original anchor ownership and settings.
Base-v7 supplies no weights or labels to this update.

The original 64 anchor runs keep their previous **49 fitting / 15 selection** assignment from
#125; their 545 records remain split into 416 fitting and 129 selection anchors. The fresh
64 evidence runs keep their pre-outcome **48 fitting / 16 selection** assignment from #126.
The combined update has 97 fitting and 31 selection runs. These explicit groups are checked
against both sources, rather than reapplying a quantile split to a combined or successful subset.
Every action comparison from a run stays together. The original **204 development-validation
states** remain separate and unchanged.

Every source observation, legal-action binding, branch trace, comparison, content identity and
data-sufficiency result is verified before fitting. Ties are reported and excluded; activity-only
comparisons have zero policy weight. Strict comparisons in either direction are included, with
unit weights for floor/boss/act advancement and the existing quarter weights for weaker frontier
diagnostics. Three correlated comparisons from one seed do not supply three independent runs:
both gradients and reported losses normalize at the complete-run boundary.

## The same learner and acceptance limits

The update reuses the shared anchored trainer: 40 full-batch AdaGrad epochs, learning rate 0.0005,
parent-policy anchoring 2, preference strength 1, proximal penalty 0.1, gradient clip 1 and epsilon
1e-8. The loader checks these settings and all thresholds against the frozen #125 source recipe.
The residual is zero initialized and uses the unchanged public categorical starting-option encoder
with 4,096 coordinates. Only the residual changes; every original policy/value/risk/floor head and
every later decision stays unchanged. Content identity reconstructs the original parent exactly.

Vocabulary is fitted only from eligible fitting comparisons and fitting anchors. Selection and
validation never add categories. The collection's selection-only ID 132 is checked against the
original fitting anchors, and any still unknown option uses the existing shared `unknown`
category. The report records this distinction explicitly.
The bounded saved-input check confirmed that ID 132 is already present in the original fitting
anchors, so it can be known without learning from selection. It also verified all 64 evidence
cases, the actual frozen parent/assignment identities and zero-residual parity on one real saved
public menu in 0.937 seconds, with no optimization or game attempts.

An epoch must pass the original selection-anchor safety checks and improve both overall and
strong selection preference loss by at least 0.001. Among passing epochs, the original minimum-loss
rule selects one without refitting. The selected result is checked once against all 204 original
development-validation states, keeping the same auxiliary gate, pair-loss increase 0.01,
accuracy drop 0.02, regret increase 0.0002 and mean distribution drift 0.05. Validation cannot
choose another epoch or relax a failed threshold. No advancing epoch means an empty residual
and an ineligible result. A failing validation result remains rejected.

The v8 checkpoint/report retain explicit recipe, fold, vocabulary, parent and residual identities.
The saved-result verifier reloads the sources and recomputes coverage, parent/selected metrics,
selected-epoch evidence and all validation choices. Direct production-policy construction rejects
an ineligible v8 candidate and checks the same report integrity. Older schemas remain supported.

These labels describe one realized future per option under fixed base-v2 continuation. They do
not estimate expected win probability or certify real-game equivalence. Development validation
has already been reused. A passing candidate still requires a separately frozen full-run comparison
before promotion. Terminal full-game victory under the whole-run compute budget remains primary;
terminal-value and adaptive-controller training remain blocked.

The coding agent runs short toy tests and bounded saved-file checks only. Its earlier full-data
inspection reached a 30-second cap without starting optimization; the owner subsequently completed
training and full saved-input verification. The coding agent launched no real-data training or game
attempts. GitHub Actions was not triggered.
