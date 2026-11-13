# A8 Act 1 success replay comparison

The [later-act study](native-a8-shared-later-act-result-v1.md) finished
128 paired evaluation games with zero full-run wins. Act 1 clears
were 3/64 for the frozen parents and 1/64 for the fitted copies.
The new comparison gives the shared head more examples of
successful choices from normal starts.

## Training data

The saved audit found 63 eligible training games across 50 distinct
worlds in the scoring-head and later-act studies. One trajectory per
world contributes its native Act 1 prefix through the first living
Act 2 map observation. Selection prefers a shared-head trajectory and
uses initializer order to resolve duplicates. The exporter checks
the full game seal, exact menus, choice receipts and native Proceed
from the current boss rewards. It writes 8,574 choice-bearing answers
from 10,886 native deliveries. The original run, checkpoints and logs
stay in their existing locations.

The 38 fitting worlds contain 6,496 choice-bearing answers. Two
worlds from each of the six Act 1 bosses form a 12-world offline
holdout with 2,078 answers. Those worlds are reserved from this fit.
The source trajectories had prior training ownership. Fresh
normal-start gameplay is evaluated on separate worlds. Prepared
starts, controls, interrupted runs and earlier evaluation games
supply no labels.

## Fit and evaluate

The comparison starts with the same two sealed round-64 shared
parents used in the later-act study. Each new copy gets 256
actor updates with equal draws per training world. The schedule
visits every admitted answer. All candidates reach the scorer.
The two parents and their Adam states stay frozen, and each
copy retains its parent's critic weights and critic Adam state.
Held-out joint loss measures agreement on saved public menus.

Each frozen fitted copy plays the same 32 fresh worlds as its
parent. The model owns every decision on all four arms, with
the same frozen native build and rules. Full-run A8 wins are
primary. Act 1 clears and floor progress help interpret the result.
The existing final-test worlds stay reserved.

The short control applied two updates per disposable copy, reloaded
both full checkpoints, and verified native endings and matching
starting observations in all four control games on a separate world.
The frozen build and all four original checkpoints and their Adam
states passed verification. The control receipt is
`sha256:45b711610b4fa8edfde219a204c557bfb4e944bb378a6e8a1a71f8496bcb9b60`.

Close STS2 and allow about 20–40 minutes. The launcher has a
one-hour cap and seals fits and games in the private study directory.

```bash
bash scripts/train-a8-act1-success-replay-v1.sh
```
