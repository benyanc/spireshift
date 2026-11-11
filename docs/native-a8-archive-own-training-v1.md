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

Close STS2 before running the study. Allow about 12 to 25 minutes, with
a 45-minute outer cap.

```bash
bash scripts/train-a8-from-archive-v1.sh
```
