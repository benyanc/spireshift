# Model-owned A8 learning from the archive fits

The archive fits improved the scores of actions recorded in two unseen
human Act 1 clears. The same copies recorded zero A8 wins and zero Act 1
clears in their 24 fresh games. This comparison tests whether training on
the states those models actually reach improves their complete runs.
[Archive fitting result](native-a8-archive-copy-fit-v1.md) ·
[Unseen demonstrations](native-a8-archive-act1-v1.md).

Initialize two new copies from the exact archive-fitted actors, critics
and full Adam. Each initializer plays two batches of eight new normal-start
Ironclad/A8 worlds and applies the existing model-only PPO update after
each batch. Every legal choice reaches the model. Only delivered decisions
from the current behavior checkpoint on clean terminal training games
enter PPO. The frozen original checkpoints, both archive-fitted parent
states, runtime and game build are checked throughout.

Freeze the two updated copies and compare them against their respective
archive-fitted parents on 12 separate normal-start worlds. Both arms use
the same full-menu policy and matched sampling. The 48-game comparison
reports native full-run wins, paired outcomes and Act 1 progress. The
saved report uses `original` for the archive-fitted parent and `fitted`
for its on-policy continuation. Capped, failed and unattempted games
remain in the denominator. The final-test worlds remain reserved.

The short check completed four native losses, six updates on each
disposable copy and two exact six-choice reloads. It verified 471 native
deliveries and all frozen states. The short-check report is
`sha256:8a8ea73264816c606bb9c55e2e6c437408a0388f7e0a3eac7821dec00ccbdbd0`.
The longer study uses fresh copies of the original archive fits.

## Saved result

All 32 training games and 48 development games ended in native Act 1
losses. The two copies took 96 optimizer updates across four sealed
batches. Training reached three Act 1 bosses and 122 of its 154 combat
rooms reached rewards. The learner return for each game came entirely
from its terminal floor because there were zero act clears and wins.

| Development arm | A8 wins | Act 1 clears | Act 1 bosses reached | Mean maximum floor |
| --- | ---: | ---: | ---: | ---: |
| Archive-fitted parents | 0/24 | 0/24 | 1/24 | 7.79 |
| PPO continuations | 0/24 | 0/24 | 0/24 | 7.29 |

The continuations finished ahead in three matched pairs, tied in 18 and
finished behind in three. Eighteen losses per arm occurred in ordinary
fights. The first changed action occurred on the same public menu in all
24 pairs, including 17 combat menus. Highest-score agreement on the two
previously unseen human paths moved from 53.4% to 53.9% for player 2 and
from 50.2% to 50.9% for player 3. This is a comparison on the archived
decision states. The fresh games give no evidence of stronger A8 play.

The saved audit verified 86 seals, 4,892 files, 8,977 native deliveries,
all matched starts and all 80 native endings. It matched the raw binding
and delivery streams and reused the sealed independent native
projections. No local ordered-answer factors occurred in this panel.
The build, original and archive-fitted weights and all Adam states
passed exact verification. [Saved evidence](evidence/native-a8-archive-own-training-result-v1.json).

Prioritize independent successful normal-start trajectories for
learning. The [Act 1 archive intake](native-a8-archive-act1-v1.md)
identified repeated selector lifecycle gaps that block such examples.
