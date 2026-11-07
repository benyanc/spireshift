# Learning more from each game

The next experiment changes how public information reaches the player. A shared
linear health feature shifts every action score equally, so it cannot by itself
change which action is preferred. The existing hidden layer can express that
relationship, but the earlier conditional-learning test showed very weak learning.

The new encoding also supplies products of bounded public state measurements and
each candidate's public fields. In simple terms, the player can learn separate
effects for **health with this action**, **energy with this card**, or **progress
with this choice**. These are learned weights, not rules saying healing is good
or health loss is bad. It receives no correct-action labels in native PPO.

The ordinary graph encoding is retained as a component. Extra terms share its
hashed coordinates, so this is not a mathematically lossless representation and
hash collisions remain possible. The action menu, 18 direct coordinates, critic
inputs and network size remain unchanged: 512 inputs, 32 hidden units, 17,473
actor-plus-critic parameters. No action family or parameter group is frozen.
The numeric features are the existing 19 bounded public value measurements;
all other observed mechanics still reach the original graph component.

## Completed synthetic comparison

Recipe: `configs/native-controls/action-context-v1.json`. All three encodings use
three training seeds, 32 rounds of 64 fresh artificial episodes, the existing PPO
settings and binary final rewards only. Each episode has a consequential choice
followed by five forced continuation steps. All decisions remain in training.

The analytic task makes Commit preferable at high health and Decline preferable
at low health. Its best possible expected victory is 70%. This rule belongs only
to the artificial task, not Slay the Spire's gameplay. Separate teachers receive
oracle labels for diagnosis; PPO sees only sampled final outcomes.

| Encoding | PPO expected victory across seeds | PPO learning criterion passed | Direct teacher passed |
| --- | --- | --- | --- |
| Original quarter-scaled graph | 48.07–54.26% | 0 / 3 | 0 / 3 |
| Graph plus shared numeric facts | 48.08–62.06% | 0 / 3 | 3 / 3 |
| Graph plus numeric × candidate fields | **68.68–69.32%** | **3 / 3** | **3 / 3** |

The predeclared criterion requires at least 75% probability of the optimal action
in both contexts and at least ten percentage points of exact expected-victory
gain from the player's own initial policy. The crossed PPO players put
94.67–98.01% probability on the appropriate choices. All select the appropriate
action greedily at four predeclared health values absent from fitting; expected
victory there is 61.65–62.27%, versus a 63.75% optimum. These interpolated contexts
are a small generalization check, not a new game or independently sampled test set.

Every primary learner completes **288 Adam steps, 36,864 decision presentations
and 6,144 choice presentations**. Although the runner permits the unchanged PPO
KL stopping rule, realized work happens to match across all encodings. Initial
parameters and action probabilities match exactly. All new arms use zero initial
hidden-output weights to make that possible, unlike the earlier historical
initializer; this is a common change, not part of the encoding contrast. Hidden
weights subsequently learn normally. Trajectories are on-policy for each arm;
after policies diverge, their sampled actions/outcomes need not match.

The missing-health teacher controls remain unable to distinguish the contexts.
Saved-result assessment rechecks all **318 artifact seals** and reconstructs
the final/held evaluations from **21 saved numerical models**, without fitting.
The comparison takes 91.99 seconds and 134.41 MB peak process-tree RAM, retaining
14.75 MB. It uses 18,432 artificial episodes and 6,048 artificial optimizer steps
including teachers/controls; zero native games or production updates.

This supports the representation change on a measured learning weakness. It does
not establish the unique cause of native losses, general game mastery, adequate
model capacity for every mechanic, or better native gameplay.

## Completed native checks

The saved-state probe rebinds 278 public decisions to their sealed original TRAIN
episodes: 93 games, 1,175 candidate rows and 13 decision families, including
combat, rest, shops, card packs, selection, optional rewards and navigation.
Every menu/direct coordinate/critic input is preserved. No candidate aliases are
observed under any of the three encodings. This takes 4.98 seconds and 152.13 MB
peak RAM; no new games or optimizer steps. It is finite representative coverage,
not proof about every possible mechanic or future state.

The separately pinned native bridge control then completes eight actual
Ironclad/A8 games and 12 optimizer steps in 65.04 seconds, with 694.26 MB peak RAM
and 10.70 MB retained. It exercises both encodings, exact reconstruction of the
saved behavior probabilities, whole-game cross-fitted credit, serialization and
post-update play. All worker journals are checked as ordered streams. No failed
games, missing games, shared-input changes or app copies occur. The two-game
panels tie; this control checks integration, not learning quality.

Historical admitted Python sources, old models, experiments and original failures
remain unchanged. Native PPO keeps the same versioned floor/act bootstrap score
and full-trace credit. Full-run terminal victory remains the evaluation objective.
There is no health penalty, healing bonus, oracle teacher, adaptive controller
or production checkpoint promotion in this change.

Repository verification passes: **1,606 tests**, formatting/lint, strict Python
types, C# build and protocol contracts, with zero build warnings/errors. The test
suite takes 298.59 seconds on this run; use that timing when deciding whether a
future full check belongs to the owner under the five-minute execution boundary.

## Next owner run

Run this one command from any directory:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/train-native-a8-context-v1.sh
```

The prepared comparison uses two training seeds per encoding, four rounds of
32 games per player, and 16 starting plus 16 final development games per player:
**640 planned native games**. Expect 25–40 minutes. The hard limits are one hour,
7,200 process-tree CPU seconds, 4 GB RAM and 6 GB generated files. It launches
at most two isolated native workers concurrently and shares the frozen game and
support-code cache. No app copies are made.

Every batch displays wins, average floor, best floor/acts and failures. Controls,
training and development use distinct declared seeds; paired encodings use the
same planned seeds, sampling streams, starting parameters, objective and PPO
settings. Each player uses its own fresh on-policy games. Actual decisions and
optimizer work can differ and are recorded. Final checkpoints alone are compared;
there is no picking a lucky intermediate result or automatic follow-up.

The collector retains compact outcomes/paths, audits journals as streams and
releases previous raw episode histories. Fitting retains encoded training samples
and compact value features, not every game's public JSON. A stuck worker is retired
and audited before a fresh worker takes the next seed; its partial game is excluded
from training and remains in the denominator. Missing/corrupt evidence or more than
two failed games in a panel stops the experiment. Interrupted runs are preserved;
rerunning displays/verifies a finished result or refuses an unfinished directory.

The shell wrapper reads workspace and resource limits directly from the recipe.
Read-only preflight of the longer recipe has passed. **The longer trial has not
been started by Codex.** A successful run only completes the comparison; it cannot
grant bulk-learning, base-policy or adaptive-search readiness.

Then compare original versus crossed **final-minus-initial** performance, paired
by development seed and numerical training seed. Report wins first, then floor/act
progress, failures, actual work and resource cost. With only two training seeds
and 16 development games each, this remains exploratory. If it improves repeatably,
scale a declared learning curve; if it remains flat, test optimizer efficiency
and better action credit/teachers before an unchanged large run.

Portable counts, model/report IDs and resource receipts are in
[the evidence record](evidence/native-action-context-v1.json). Generated public
game states, traces and model parameters remain private under `artifacts/`.
