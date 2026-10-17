# Small end-to-end learning controls

Implemented and assessed 2026-10-17 under #35 / #146. This is a synthetic diagnostic,
not another STS2 training run, a mechanics qualification, or an additional readiness gate.
The owner-run 256-game gradient study's 24 pinned Python inputs remain unchanged.

## What the control checks

The actual native public encoder, quarter input scaling, 512-input / 32-hidden-unit
actor, diagnostic critic, whole-game cross-fitted ridge baseline, advantage normalization,
PPO clipping/entropy, Adam updates, and behavior-KL stopping all run unchanged. Settings
come directly from the frozen normalized recipe. No production initializer/checkpoint,
native trajectory, game worker, game installation or profile is opened or updated.

Each task starts from the same native numerical initializer with a separately identified
synthetic environment. Seeds 0/1/2 independently initialize and sample each task. The
initializer favors Commit, which is wrong in the first two tasks. Every round collects
64 fresh complete artificial episodes, then updates; 32 rounds are fixed in advance.

Only the sampled binary terminal outcome supplies the actor's return. There are no
supervised optimal-action labels or intermediate rewards. The native score specification
supplies baseline feature scaling only: floor remains zero and the progress potential is
exactly zero. A game's outcome never fits its own baseline. Forced continuation menus
remain in the same production normalization and update denominator.

The three environments have completely specified solutions:

| Task | Rule | Maximum expected victory |
| --- | --- | --- |
| Immediate | Decline wins; Commit loses | 100% |
| Delayed | Same initial choice, then five forced continuation steps before the outcome | 100% |
| Contextual risk | At low HP, Commit wins 10%, Decline 55%; at high HP, Commit wins 85%, Decline 55% | 70% |

Low/high HP and both menu orders are equally represented in exact evaluation. Actions
keep their meaning when menu order changes. Evaluation enumerates these public contexts
and uses known environment probabilities, without sampling evaluation outcomes or fitting
on evaluation data. This checks learning a known task, **not held-out generalization**.
There is only one consequential choice per episode: this is not a long-horizon strategy
test or a full native wrapper/transition/experience-verification test.

The final round alone is evaluated for acceptance; no checkpoint selection or search
for the best epoch. Frozen criteria require at least 75% probability for the optimal
action in every public context and at least +10 percentage points expected victory in
each of the nine task/seed arms. These are control thresholds, not a gameplay claim.

## Observed result

The finite experiment completed, but the overall learning check **did not pass**.
No thresholds, rewards, settings or duration were changed to make it pass.

| Task | Initial expected victory | Final expected victory across seeds | Optimizer steps per seed | Passing seeds |
| --- | --- | --- | --- | --- |
| Immediate | 7.60–7.66% | 46.35–50.88% | 96 | 0/3 |
| Delayed | 7.60–7.66% | 99.29–99.65% | 288 | 3/3 |
| Contextual risk | 48.07–48.08% | 48.06–54.25% | 288 | 0/3 |

The delayed task shows that sampled terminal outcomes, credit, normalization and actual
optimizer updates can overturn the weak initializer. It does not establish that delaying
reward improves learning: the extra forced menus create three times as many decision
minibatches and optimizer steps. Equal episode counts are not equal optimizer work.
The immediate task improved substantially but did not reach the predeclared threshold
within its shorter update budget. Neither observation alone proves an optimizer defect.

On the contextual task, every final greedy player chooses the same action at both HP
levels (50% optimal-choice accuracy). For seed 0, the probability of Commit is approximately
10.16% at low HP and 10.21% at high HP. Seed 1 remains around 92.55% at both; seed 2 is
around 45.95% at low HP and 45.99% at high HP. The desired reversal was not learned.
This identifies a reproducible synthetic weakness under this budget, not the proven cause
of native-game losses, proof that the actor cannot represent the solution, or evidence
that more games necessarily fix it.

The four-round frozen-actor control makes actual optimizer calls: the diagnostic critic
changes, but actor weights and exact policy performance remain identical. Removing HP
from the contextual evaluation makes the two public inputs identical; greedy accuracy
is exactly 50%, and expected victory stays below the best unconditional policy's 55%.
No scores or optimal-choice labels enter policy inputs.

There were **18,688 artificial episodes / 2,052 synthetic optimizer steps**, zero real
games, zero app copies, zero native episodes read and zero production updates/checkpoints.
Runtime: 34.09 seconds including the resource wrapper, 33.72 CPU seconds, 121.37 MB peak
resident memory, 4.11 MB retained output. No resource cap was reached. The fixed limits
were three minutes, one numerical thread, 1 GB memory and 20 MB output.

## Interpretation and next work

The learning loop is capable of improvement, but the current recipe is not reliably
learning even this small situation-dependent choice within the frozen budget. Keep this
result alongside the owner's batch study; do not use it to select or promote a native
player, normalize away a negative result, or start a larger unchanged run.

Next targeted design: compare direct synthetic teaching against PPO on exactly the same
context-dependent inputs, with all attempted settings recorded. This can help distinguish
available actor capacity from weak reward-driven conditioning. Match actual optimizer
work when comparing immediate/delayed controls. Any native training recipe change waits
for assessment of the owner's larger independent-game pool. Broader architecture,
genetic algorithm, other ascension and adaptive-controller work remain deferred.

## Reproduce or view the saved result

```bash
bash scripts/check-native-ppo-known-tasks-v1.sh
```

The script is safe beside native collection: one numerical thread, separate artifact
directory, no source mutation, workers or environment synchronization. A cached result
is displayed without fitting. An incomplete output directory is preserved and cannot
silently restart. A changed recipe/source fails before use. A completed negative learning
result is a valid experiment result and returns success; inspect `learning_control_pass`
separately from `status` and the resource runner's completion flag.

Recipe: `configs/native-controls/ppo-known-tasks-v1.json`.
Result: `artifacts/synthetic-learning/native-ppo-known-tasks-v1/report.json`.
Detailed per-task/seed updates and sampled outcomes remain beside that report.
Resource report: `artifacts/resources/native-ppo-known-tasks-v1-attempt-1.json`.
Small portable evidence summary: `docs/evidence/native-ppo-known-tasks-v1.json`.
