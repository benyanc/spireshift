# Native A8 optimizer study and learning curve

Updated 2026-10-18. #143 / #35 / #146 remain open. The previous input comparison was flat;
we have not established a strong native player. This implementation tests whether the learner
needs less noisy batches and more fitting per collected game before changing action credit again.

**Completed result:** all 2,368 games finish without failures. Standard mean floor rises
6.28125→9.09375, versus 7.40625 for the larger-batch candidate; both final methods have zero
full wins. [Assessment, measured costs and next work](native-optimizer-learning-result.md).
The prospective protocol below is preserved; its command now verifies saved results.

## What the short study actually found

Two saved, clean, on-policy TRAIN cohorts contain 32 games each, from numerical initializers
0 and 1. Saved behavior probabilities, public inputs, file seals and complete-run ownership verify.
Starting from the original weights and zero Adam state, the standard update exactly reproduces
both historical first-round model IDs. This is evidence that the implemented update is connected
and reproducible. It does not establish good decisions.

The frozen study tries three settings, each from the same initializer and games in each cohort:

| Setting | Actor learning rate | Passes through the batch | In-sample clipped surrogate gain, seeds 0 / 1 |
| --- | ---: | ---: | ---: |
| Standard | 0.001 | 3 | 0.01031 / 0.01173 |
| Larger step | 0.003 | 3 | 0.01632 / 0.01976 |
| More passes | 0.001 | 9 | 0.02638 / 0.02824 |

Nine passes fit the assigned training signal 2.4–2.6 times as much as three passes. Every update
reaches its epoch limit; none reaches the existing per-update KL limit. This measures agreement
with saved advantages, **not action quality, future wins or independent gameplay improvement**.
Higher learning rate is retained as an attempted diagnostic setting; it is not the next live arm.

Separate 16-game halves suggest weakly related update directions: data-gradient cosine is
−0.1019 and +0.0057. Each half fits its own baseline and advantage normalization. These are
single-split diagnostics from two cohorts, not population confidence intervals, a causal diagnosis
or proof that 128 is an optimal batch size. Stronger reuse can also learn noisy lessons more firmly.

The study launches zero games, performs 825 numerical updates, and takes 88.42 resource-tracked
seconds with 723 MB peak memory. It changes no historical checkpoint or result. The six attempted
fits remain diagnostic artifacts and are never promoted or used as fresh PPO experience.

## Implementation and short live check

Compact read-only sparse rows retain exact indices and float64 values instead of one Python
dictionary per candidate. There is no numeric quantization. On a saved 32-game / 3,413-decision
batch, the compact path reproduces the exact historical model after 81 updates. Preparation adds
about 168 MB resident memory and retains a 54.44 MB packed payload. This is an observation on that
batch, not a guarantee for 128 longer games. Streaming keeps one raw episode at a time.

The live restart control finishes eight games and 24 optimizer updates over three launches:
54.45 resource-tracked seconds, 681 MB peak RAM, 11.55 MB output, zero failures and zero app copies.
Both arms start from identical weights and Adam state. Restoring completed units leaves their
model and optimizer files unchanged; opening the complete result launches nothing further.
Its effective batches are two games: it tests worker/fit/resume integration, not learning quality
or a real 128-game batch. Tests separately verify exact loss, gradient, weights, Adam and credit
parity, whole-run partitions, failure accounting and refusal of uncertain uncommitted work.

The new learning-curve runner uses the already qualified public crossed inputs, frozen game,
runtime, SDK and support cache. Mutable profiles and delivery ledgers remain per worker. Historical
sources and recipes stay byte-identical. All current legal choices and decision families remain
learnable. The floor/act bootstrap return, whole-run credit, model size, learning rates, exploration
and per-update PPO guards stay declared and unchanged; terminal full-run wins remain primary.

## The next experiment

| Property | Standard | Candidate |
| --- | ---: | ---: |
| Independent games before an update | 32 | 128 |
| Maximum passes through each batch | 3 | 9 |
| Training games per player | 512 | 512 |
| Training batches per player | 16 | 4 |
| Numerical initializers | 2, 3 | 2, 3 |

The candidate intentionally changes batch size and reuse together. A gain would support this
bundle; it would not identify which change helped. Both methods get the same game budget and
paired seed plans. The unchanged per-update PPO guard can stop an update before its pass limit.
The candidate uses more numerical fitting compute and updates the player less
frequently, so this is **not equal training compute**. Actual decisions, optimizer steps, CPU,
memory and failures remain recorded. Same seeds/draws cannot make divergent policies visit the
same states.

Each frozen player is evaluated on 16 reserved development seeds at 0, 128, 256, 384 and 512
training games. Initializers 2 and 3 have distinct TRAIN and development sets; methods are paired
within each initializer. These are fresh seeds, separate from the completed experiments and the
short control. Final models are compared with their own initial players and with each other;
intermediate results are diagnostic. No best-checkpoint selection, tuning during the run, automatic
promotion or untouched-test claim follows. Two replicates / 32 final games per method remain a
small development study, not a precise win-rate benchmark.

The fixed plan contains **2,368 game attempts: 2,048 TRAIN and 320 development**, across 340 sealed
units. It is four times the previous 128-game training horizon per player. Eight-game collection
chunks preserve completed work without shrinking the actual 32/128-game training batches. Failed
games stay in original denominators; at most two per 128-game training stage or evaluation are
allowed. Failed workers must prove shutdown before replacement, and failed seeds are never retried.
Interrupted prefixes remain diagnostic only.

This experiment stops at the fixed 512-game horizon. If both methods remain flat or regress across
the fresh replicates, do not automatically extend unchanged PPO, tune on final development results,
or claim the model merely needs millions more games. Prioritize a change to the quality of action
credit or qualified search/demonstration lessons. If progress repeats, first confirm it on new seeds
before scaling. The base/value/search readiness gate still precedes adaptive thinking; GA and other
difficulties remain deferred.

## One owner command

Close the Steam game, then run:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/train-native-a8-optimizer-v1.sh
```

Budget roughly **2–3 hours**, estimated from the completed 288-game comparison, saved fits and
short control; improved players may take longer. Each invocation has a three-hour work budget,
two workers, a 4 GB memory cap and 6 GB retained-output cap. It reuses complete repository checks
only for exact unchanged files; otherwise it runs the full check before collecting games.

Clean 15-minute sessions continue automatically within the same finite plan. Progress reports show
batch average/best floor, wins and failures, plus each frozen development result. A failed/capped
session or uncertain unit stops for inspection instead of retrying. At a clean budget pause, the
same command resumes saved collections and full Adam state. After completion it only verifies the
saved result. No new experiment, app copies or automatic follow-up training occurs.

Optional `--status` is read-only; `--one-session` limits a launch to one bounded session. Neither is
required for the normal command. The long experiment has **not** been launched by Codex.

Recipe: `configs/native-learning/sts2-v0.111.0-a8-optimizer-learning-curve-v1.json`.
Measured evidence and exact report IDs: [native optimizer evidence](evidence/native-optimizer-learning-v1.json).
