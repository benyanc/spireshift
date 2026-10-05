# Starting-choice training from exhaustive evidence

[Issue #127](https://github.com/benyanc/spireshift/issues/127) uses the completed
[starting-option collection](starting-option-evidence.md) to train one small adjustment to
accepted base-v2. The earlier base-v7 experiment made no accepted update. Its starting-choice
preferences covered only three fitting runs and one selection run. The new collection passed
its frozen coverage gate: 64 complete train seeds, all 192 terminal branches, no failures or
truncations, 130 eligible fitting comparisons and 42 selection comparisons. There are still
zero full-run wins. Better coverage is permission for this bounded experiment, not proof that
the policy has improved or that terminal-value learning is ready.

## One current owner command

From the repository directory, run only:

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

Share the final terminal summary, especially `selected_epoch`, `candidate_eligible`,
`validation_checks` and the verification result. A rejected run is a valid completed experiment.
No quality claim or production promotion is made before the owner returns the result.

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

The coding agent runs short toy tests and bounded saved-file checks only. The full saved-data
preparation hit a 30-second inspection cap without starting optimization; it is left to the owner
command above. The real model has not been trained by the coding agent. GitHub Actions is not
triggered.
