# Why native A8 pilot v5 did not retain a trained improvement

The investigation finds noisy whole-run updates and a value baseline that usually fails to
reduce residual variation. These are measured training weaknesses, not proof that they alone
caused the confirmation result. The production learner and all pilot artifacts remain unchanged.

## How certain is the decline?

The two trained checkpoints scored below the initializer on 16 confirmation seeds. Exploratory
paired bootstrap intervals for the average floor difference include zero: round 4 minus initial
is -0.75 floors [-1.875, +0.375]; round 8 minus initial is -0.375 [-1.6875, +0.8125]. These are
post-result confirmation diagnostics, not independent development evidence. Selection retained
the initializer, so development repeated that same player. We have not proved population-wide
degradation, or compared trained checkpoints independently on development seeds.

## What the investigation establishes

### 1. The critic usually adds noise

The saved behavior critic is supposed to remove predictable variation from final run outcomes.
On **choice-bearing training decisions**, its explained variance was:

| Behavior round | Explained variance | Squared error / in-sample constant reference |
| --- | ---: | ---: |
| 1, untrained critic | 0.000 | 1.120 |
| 2 | -0.116 | 1.221 |
| 3 | +0.033 | 0.968 |
| 4 | -0.018 | 1.272 |
| 5 | -1.283 | 2.932 |
| 6 | -0.159 | 1.610 |
| 7 | -0.407 | 1.481 |
| 8 | -0.238 | 1.313 |

Negative explained variance means subtracting the critic increases residual target variance.
Six of the seven rounds after the first fit have this problem. The constant reference uses the
same batch's mean for diagnosis; these ratios are not an independently fitted alternative or
a gameplay comparison. Removing forced single-action decisions does not remove the finding.

An additional exact policy-gradient reconstruction on all 32 training games in rounds 1 and 8
checks the effect on actor updates, with entropy omitted and batch centering retained. In round
8 the actual critic produces **18.5% more per-episode actor-gradient trace variance** than the
centered constant reference. The two mean gradient directions have cosine 0.810. Replacing the
critic alone is not a demonstrated solution: the constant-reference gradients are also noisy.
Its round-8 halves oppose in 72% of resplits versus 64% with the critic; its mean-gradient SNR
proxy is 0.801 versus 0.874. These noisy batch proxies do not establish a better baseline.
Absolute gradient variance alone must not be presented as proof that critic removal helps.

### 2. The update has very few independent outcome lessons

There were 26,061 training decisions, but only **256 independent training runs**, 32 per round.
Each round has just 7–10 distinct final target values: every run loses before completing an act,
so the bootstrap target is determined only by its final floor. Each decision in a given run
receives that same target, minus a predicted state value. A useful action and a mistaken action
in the same game receive no direct counterfactual distinction. This is a valid Monte Carlo
policy-gradient form, but may require much more data to separate action quality from seed luck.
It is not a coding error merely because the return is delayed.

In round 8, 100 fixed random splits of its 32 independent episodes into halves give opposing
mean actor-gradient directions in **64%** of splits; the median cosine is -0.049. Round 1's
median is +0.105, with 21% opposing splits. These are descriptive, correlated resplits of two
existing batches, not 100 independent experiments or a confidence interval for true gradients.
Their weakness remains with the constant reference. Stable update direction has not been shown.

### 3. Representation becomes less responsive, but it is not incapable of learning

A deterministic probe takes the first 24 multi-action training states reached per family,
where available: **278 states, 1,042 candidates**. It is a limited diagnostic sample, not a
uniform sample of all gameplay. There are no exact candidate-vector alias pairs within its
menus. Only 0.0247% of hash buckets per candidate are hard-clipped on average. The earlier
name/amount collapse and widespread hard clipping are not established causes here.

There is substantial tanh saturation: in its 24 combat states, the fraction of candidate/hidden
activations, averaged across those states, with absolute value above 0.99 rises from **10.2% initially to 58.9% after round 8**.
Those activations have small local derivatives. Across all sampled families, the state-average
fraction rises from 4.1% to 20.8%. This can hinder conditional learning and merits a normalization
control; it does not prove that the model needs more layers or cannot use state.

A deliberately artificial supervised control pairs saved Rest/Smith menus with low/high public
HP and labels Rest for low HP, Smith for high HP. These are invented diagnostic labels, **not
optimal-gameplay labels**. Eight original training runs supply 16 fitting examples; nine other
training runs supply 18 held-aside examples. Both the initial and round-8 networks reach 100%
classification on those 18 examples after 300 small control updates each; average target
probability is 97.5% and 96.6%, respectively. No production checkpoint is written. This shows
that clear state-dependent feedback can train this architecture on this limited task. It does
not establish general game competence, globally sufficient capacity or a good policy teacher.

### 4. Tested gradient calculations are correct; a separate control edge case exists

Central finite differences agree with the analytic PPO gradients to better than 7e-13 absolute
error on 30 coordinates across combat, rest and shop training states, covering each actor
parameter block and the critic. This checks those points, including entropy and temperature;
it is not a proof of every possible optimizer path. No sign/temperature derivative defect was
found. Actual actor advantages are normalized, all round updates ran three epochs and none hit
its KL stop. Small raw rewards and a permanent baseline-proximity restriction are not supported
explanations for this pilot.

The first artificial control exposed an **integer learning-rate dtype bug** in the shared Adam
kernel: `np.full(..., value_rate)` creates an integer array when `value_rate=0`, then truncates a
fractional actor rate to zero. The control's 600 attempted steps changed no model weights. That
invalid control is preserved and excluded as learnability evidence. Repeating it with explicit
`value_rate=0.0` gives the successful control above. **V5 used positive floating-point rates**,
so this is not its cause. Fix/reject integer rate inputs before a critic-disabled ablation, with
a focused regression test. Do not interpret the invalid control as a broken production model.

## Ordered backlog changes

1. **#35: improve and measure critic/credit quality first.** Add per-round, choice-bearing
   critic explained variance, constant-reference error and run-level gradient agreement.
   Compare a deliberately simple, action-independent train-only baseline against a critic
   chosen/fitted using whole-run-grouped training splits. If it cannot reduce variance, do not
   assume a more elaborate bootstrapped advantage estimator will help. First make integer/float
   optimizer rates behave consistently. No frozen v5 source or outcome is rewritten.
2. **#35: test an objective-preserving credit improvement.** Consider public progress potentials
   and return-to-go, then a GAE comparison only after value prediction works. Version the new
   return/advantage contract. Prove the redistributed rewards telescope to the existing full-run
   score up to a policy-independent initial constant, including endings, skips, loops and
   failure exclusions. Wins remain primary; no immediate HP/card/room bonus silently replaces
   the objective. This is a candidate experiment, not a promised fix.
3. **#143: preserve meaningful inputs and control saturation.** Test a normalized, less duplicated
   state/action representation on the same artificial conditional controls and whole-run-held
   training examples. Preserve entity/amount ownership, current costs, optional actions, public
   memory and all supplied action families. Measure saturation and distinguishability. A bigger
   network is conditional on demonstrated representational failure, not the default response.
4. **#146 / #134: predeclare a small causal comparison.** Change one factor, use matched training
   seeds/action RNG/compute across arms, estimate timings first and leave long execution to the
   owner. Measure gradient agreement as independent training runs per batch increases, rather
   than equating more optimizer steps with more evidence. Freeze the best trained candidate on
   confirmation before development, and report it separately from an incumbent that might be
   the initializer. This avoids a second baseline self-comparison being presented as a trained
   policy test. More unchanged PPO/GA, a mechanics sweep and adaptive thinking stay deferred.

The [PPO paper](https://arxiv.org/abs/1707.06347) describes the surrogate/minibatch method; clipping
does not guarantee improvement from a noisy finite batch. [Generalized Advantage Estimation](https://arxiv.org/abs/1506.02438)
provides a bias/variance tradeoff using value predictions, not a substitute for checking their
quality. These references motivate possible controls; they are not evidence of this game's cause.

## Reproduction and boundary

The permanent saved-only moment audit is `python -m spireshift.native_learning_diagnosis
<experiment-config> <new-artifact-directory>`. It verifies all 256 train episodes, their byte
seals and frozen source/score/seed ownership, then checks **531 source files**. It opens no
reserved development episodes and starts no workers or optimizer. Unit controls cover perfect,
constant, biased and wrong critics plus zero target variance and invalid numbers.

Private probe code, counterfactual examples and reports remain under
`artifacts/diagnostics/native-a8-pilot-v5-v1/`. The public
[evidence record](evidence/native-a8-pilot-v5-learning-diagnosis-v1.json) pins those scripts,
reports, checkpoint inputs and resource measurements. The valid and invalid artificial controls
attempted 600 updates each, all in memory. No full training, game attempt or production model
change followed. Each diagnostic job had a three-minute cap; the longest took 20.25 seconds.
The repository check passes 1,420 tests, formatting, types and the C# build. A native gameplay
ablation is still needed to establish causal improvement.
