# Native A8 input normalization: saturation fixed, gameplay benefit unproven

Both methods complete **336/336 ordinary endings**, with zero failures, missing games,
wins, completed acts or game-app copies. Normalization prevents hidden activation saturation
in every recorded training probe. It does **not** establish stronger gameplay in this trial.
Small average progress gains over each initializer remain uncertain.

## Reserved development games

Both methods use the same 16 previously reserved native seeds and action-RNG streams on the
frozen Ironclad/A8 game. Evaluation samples the policy at the declared temperature of 0.8.
Round eight is selected on confirmation for both methods, before development is opened.
The actual trained players are evaluated separately from their respective initializers.

| Method | Initial average floor | Trained average floor | Trained best floor | Wins |
| --- | ---: | ---: | ---: | ---: |
| Unscaled | 6.5000 | 7.2500 | 17 | 0/16 |
| Normalized | 6.5000 | 7.0625 | 12 | 0/16 |

Exploratory paired-seed 95% intervals include zero in every comparison:

- Unscaled trained minus its initializer: **+0.7500 floors**, interval **[-0.5000, +2.3125]**.
- Normalized trained minus its initializer: **+0.5625 floors**, interval **[-0.1875, +1.3750]**.
- Normalized trained minus unscaled trained: **-0.1875 floors**, interval **[-1.6250, +0.8750]**.

These use 10,000 fixed-seed resamples of 16 complete-run pairs. They are exploratory intervals,
not independent training replications. Each method was trained once. Zero observed wins in
16 development games has a marginal exact 95% interval extending to 20.6%, so the result does
not prove the underlying win rate is zero. It also does not support useful win improvement,
normalization superiority, normalization inferiority or equivalence.

The declared auxiliary score is nonlinear in floor progression. The normalized trained
player has a slightly **higher** mean auxiliary score, 0.0189482 versus 0.0188612 unscaled,
despite its lower average floor. Their +0.0000870 score difference has a paired interval
[-0.0019214, +0.0017895]. Each trained-versus-initial score interval also includes zero.
Thus the average-floor ranking alone is not grounds for selecting a method. No score is
interpreted as terminal-victory probability, and no model is promoted from this inspected panel.

These development seeds differ from the previous credit experiment. Comparing its 7.1875-floor
means directly with this experiment's means would mix different seed difficulty.

## Numerical result during real training

The saved assessment reconstructs the exact sampled indices, encoded inputs and before/after
activation statistics using each round's saved weights. Each round probes 128 choice-bearing
TRAIN states, equally weighted by state; these are diagnostics, not independent outcome labels.
Across both methods, 2,048 selected states and 4,096 before/after measurements are checked.

| Round | Unscaled saturation after update | Normalized saturation after update |
| --- | ---: | ---: |
| 1 | 14.91% | 0% |
| 2 | 21.76% | 0% |
| 3 | 32.92% | 0% |
| 4 | 38.46% | 0% |
| 5 | 39.61% | 0% |
| 6 | 46.51% | 0% |
| 7 | 48.15% | 0% |
| 8 | 52.36% | 0% |

Saturation means an absolute tanh activation greater than 0.99. Normalized saturation is also
zero before every update; unscaled starts at 8.51% on round one's sampled states. The final
probe's mean tanh derivative is 0.7000 normalized versus 0.1759 unscaled. This confirms a lasting
conditioning change under actual learning, not only a test of scaling old frozen weights.
Each method generates its own training trajectories, so its probe states need not match the
other method's states. Zero saturation is not a test of semantic coverage or policy quality.

All rounds finish their three PPO epochs without the KL stop. Final behavior KL ranges from
0.00320 to 0.00618 unscaled and 0.00120 to 0.00401 normalized. Fixed hyperparameters do not
make their functional update sizes identical. Changing normalization changes initial action
probabilities as well; equal initial floor means do not establish identical starting policies.

## Accounting and verification

Only hashed actor input scale changes. Both methods retain the same 512-input/32-unit actor,
initial numerical weights, direct features, critic inputs, cross-fitted action credit, training
seeds, score, update rules and caps. Every supplied legal action remains learnable. Both have
256 TRAIN trajectories, 512 altogether. Realized work differs: **25,917 decisions / 615 updates**
unscaled versus **25,883 / 618** normalized. They have equal collection/update rules, not equal
realized optimizer work. Every game ends in an ordinary loss; the best collected game reaches
floor 17 and neither method completes an act.

Including wrappers, the two arms take **975.83 and 953.72 seconds**, **32.16 minutes combined**.
They retain **599.37 MB combined**, with a peak memory use of **1.976 GB**. They reuse the frozen
game and shared cache with **zero app copies**; all protected-input/profile checks pass.

The saved-only audit verifies all 672 episodes, 67,963 decisions, source and trace seals,
native endings, worker delivery evidence, seed ownership, checkpoint chains, cross-fit fold
ownership and confirmation-only selection. It checks 2,878 source files and reconstructs every
recorded activation probe. It takes **33.62 seconds** with no new games, fitting, optimizer
updates or checkpoint selection. A separate saved-seed calculation checks auxiliary-score
intervals. Private inputs and audit code are pinned in the
[evidence record](evidence/native-a8-normalization-comparison-result-v1.json).

## Next work

The numerical repair works under this finite scope, but saturation alone does not explain
the lack of useful policy improvement. Keep the normalized policy as an unpromoted candidate.
Do not choose a default or tune hyperparameters from these now-inspected development games.

The next priority is **#35's independent-game gradient and batch-size controls**: measure how
consistently different groups of complete TRAIN games recommend the same parameter changes,
and distinguish the signal from a batch of 32 games from its many correlated decisions.
Begin with bounded saved-TRAIN checks. Do not pool different rounds as one on-policy batch or
pretend that resampling saved games creates new independent outcomes. If a larger-batch trial
is justified, hold the method/score/total game budget fixed, declare fresh evaluation seeds,
and measure actual cost and learning. It remains owner-run if expected to exceed five minutes.

Strong-base readiness, full-run wins and adaptive thinking remain unmet. Other difficulties,
larger unchanged PPO/GA runs and an adaptive controller stay deferred.
